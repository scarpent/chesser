import json
import random
from itertools import groupby

from django.conf import settings
from django.contrib import messages
from django.db.models import OuterRef, Subquery
from django.db.models.functions import Lower
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.views import View
from django.views.decorators.csrf import csrf_exempt, csrf_protect

from chesser import importer, util
from chesser.models import Chapter, Course, QuizResult, Variation
from chesser.serializers import serialize_variation


def home(request, course_id=None, chapter_id=None):
    home_view = HomeView(course_id=course_id, chapter_id=chapter_id)
    return render(request, "home.html", home_view.data)


def review(request, variation_id=None):
    if variation_id is None:
        extra_study = False
        variation = Variation.due_for_review()
    else:
        # Can review "on demand", but it won't update level/next_review
        extra_study = True
        # fmt: off
        variation = get_object_or_404(
            Variation.objects.select_related(
                "chapter__course"
            ).prefetch_related(
                "moves",
                "quiz_results",
            ),
            pk=variation_id,
        )  # fmt: on

    if variation is None:
        variation_data = {}
    else:
        variation_data = serialize_variation(variation)

    total_due_now, total_due_soon = Variation.due_counts()
    review_data = {
        "extra_study": extra_study,
        "total_due_now": total_due_now,
        "total_due_soon": total_due_soon,
    }

    context = {
        "variation_data": json.dumps(variation_data),
        "review_data": json.dumps(review_data),
    }
    return render(request, "review.html", context)


def review_random(request):
    """Select a random variation for review (extra study)
    We'll look for higher level variations that we haven't
    seen and won't see for a while."""

    now = timezone.now()
    two_months_later = now + timezone.timedelta(days=60)
    one_month_ago = now - timezone.timedelta(days=30)

    latest_qr = QuizResult.objects.filter(variation=OuterRef("pk")).order_by(
        "-datetime"
    )

    course_id = request.GET.get("course_id")
    chapter_id = request.GET.get("chapter_id")

    qs = Variation.objects.all()
    if course_id:
        qs = qs.filter(chapter__course_id=course_id)
    if chapter_id:
        qs = qs.filter(chapter_id=chapter_id)

    candidates = (
        qs.annotate(last_review=Subquery(latest_qr.values("datetime")[:1]))
        .filter(
            level__gte=8,
            next_review__gte=two_months_later,
            last_review__lte=one_month_ago,
        )
        .select_related("chapter__course")
        .prefetch_related("moves", "quiz_results")
    )

    if candidates.exists():
        variation = random.choice(list(candidates))
    else:
        print("🎲 Couldn't limit random choice; choosing from all")
        variation = random.choice(list(Variation.objects.all()))

    return redirect("review_with_id", variation_id=variation.id)


@csrf_exempt
def report_result(request):
    if request.method == "POST":
        data = json.loads(request.body)
        variation_id = data.get("variation_id")
        passed = data.get("passed")

        variation = get_object_or_404(Variation, pk=variation_id)
        variation.handle_quiz_result(passed)

        total_due_now, total_due_soon = Variation.due_counts()
        return JsonResponse(
            {
                "status": "success",
                "total_due_now": total_due_now,
                "total_due_soon": total_due_soon,
            },
        )

    return JsonResponse(
        {"status": "error", "message": "Invalid request method"}, status=400
    )


def get_import_context(form_defaults=None):
    form_defaults = form_defaults or {}

    # Fetch courses as a lookup: {id: title}
    courses = {c["id"]: c["title"] for c in Course.objects.all().values("id", "title")}

    # Build chapter list with label "Course: Chapter"
    chapters = [
        {
            "id": str(chapter.id),
            "label": f"{courses.get(chapter.course_id, 'Unknown')}: {chapter.title}",
        }
        for chapter in Chapter.objects.select_related("course").order_by(
            "course_id", "title"
        )
    ]
    if chapters:
        form_defaults.setdefault("chapter_id", chapters[0]["id"])

    return {
        "import_data": json.dumps(
            {
                "chapters": chapters,
                "form_defaults": form_defaults,
            }
        )
    }


def import_view(request):
    # Clear any leftover messages to avoid duplicates
    list(messages.get_messages(request))

    form_defaults = request.session.pop("import_form_defaults", {})
    return render(
        request, "import.html", get_import_context(form_defaults=form_defaults)
    )


def handle_upload_errors(request, error_message):
    messages.error(request, f"🔴 {error_message}")
    request.session["import_form_defaults"] = request.POST.dict()
    return redirect("import")


@csrf_protect
def upload_json_data(request):
    if request.method != "POST":
        return handle_upload_errors(request, "Invalid request method")

    file = request.FILES.get("uploaded_file")
    if not file:
        return handle_upload_errors(request, "No file selected")

    file_content = file.read().decode("utf-8")
    try:
        json.loads(file_content)
    except json.JSONDecodeError:
        return handle_upload_errors(request, "Invalid JSON")

    with open("/tmp/upload.json", "w") as temp_file:
        temp_file.write(file_content)

    messages.success(request, "File Uploaded ✅")
    return redirect("import")


@method_decorator(csrf_protect, name="dispatch")
class ImportVariationView(View):
    def dispatch(self, request, *args, **kwargs):
        if request.method != "POST":
            return redirect("import")
        return super().dispatch(request, *args, **kwargs)

    def handle_import_errors(self, error_message):
        messages.error(self.request, f"🔴 {error_message}")
        self.request.session["import_form_defaults"] = self.form_data.dict()
        return redirect("import")

    def post(self, request):
        self.request = request
        self.form_data = request.POST
        form_json = request.POST.get("json_data")

        try:
            self.incoming_json = json.loads(form_json)
        except json.JSONDecodeError:
            return self.handle_import_errors("Invalid JSON")

        try:
            self.set_variation_title()
            self.set_start_move()
            self.set_next_review()
            self.set_chapter_info()
            end_move = self.get_end_move()  # must come after set_start_move
        except ValueError as e:
            return self.handle_import_errors(str(e))

        imported, message = importer.import_variation(
            self.incoming_json,
            end_move=end_move,
        )
        if not imported:
            return self.handle_import_errors(message)

        messages.success(
            request, mark_safe(f"Variation {message} imported successfully ✅")
        )
        return redirect("import")

    def set_variation_title(self):
        title = (
            self.form_data.get("variation_title", "").strip()
            or self.incoming_json.get("variation_title", "").strip()
        )
        if not title or title == "TBD":
            raise ValueError("Variation Title not given and not in JSON")
        self.incoming_json["variation_title"] = title
        messages.success(self.request, f"🟢 Title: {title}")

    def set_start_move(self):
        try:
            start = int(self.form_data.get("start_move", 2))
            self.incoming_json["start_move"] = start
            messages.success(self.request, f"🟢 Starts @ {start}")
        except ValueError:
            messages.warning(
                self.request, "🟡 Invalid or missing start move; defaulting to 2"
            )
            self.incoming_json["start_move"] = 2

    def get_end_move(self):
        end_move = self.form_data.get("end_move", "").strip()
        if not end_move:
            return None

        try:
            end_move = int(end_move)
            if end_move <= self.incoming_json["start_move"]:
                raise ValueError("End move must be greater than start move")
        except ValueError as e:
            raise ValueError(f"Invalid end move: {e}")

        messages.warning(self.request, f"🟡 Discarding moves after {end_move}")
        return end_move

    def set_next_review(self):
        if next_review := self.form_data.get("next_review_date"):
            time_ = timezone.now().strftime("%H:%M:%S")
            dt_str = f"{next_review}T{time_}"
        elif next_review := self.incoming_json.get("next_review"):
            dt_str = next_review
        else:
            dt_str = util.END_OF_TIME_STR

        self.incoming_json["next_review"] = dt_str

        try:
            # importer will also run get_utc_datetime on next_review;
            # let's validate along with other things we can catch up front
            local_datetime = importer.get_utc_datetime(dt_str)
        except ValueError:
            raise ValueError("Invalid date format for next review")

        local = timezone.localtime(local_datetime)
        messages.success(self.request, f"🟢 Next Review: {local}")

    def set_chapter_info(self):
        chapter = Chapter.objects.select_related("course").get(
            pk=int(self.form_data.get("chapter_id"))
        )
        self.incoming_json["color"] = chapter.course.color
        self.incoming_json["chapter_title"] = chapter.title
        messages.success(self.request, f"🟢 {chapter.course.title} ➤ {chapter.title}")


def get_sorted_variations():
    return (
        Variation.objects.select_related("course", "chapter")
        .annotate(sort_key=Lower("mainline_moves_str"))
        .order_by("course_id", "chapter__title", "sort_key")
        .iterator()
    )


def clone(request):
    return redirect("import")


def variations_tsv(request):
    def row_generator():
        for v in get_sorted_variations():
            yield (
                f"{v.course.title}\t"
                f"{v.chapter.title}\t"
                f"{v.title}\t"
                f"{v.mainline_moves}\t"
                f"{settings.CHESSER_URL}/variation/{v.id}/\n"
            )

    return StreamingHttpResponse(row_generator(), content_type="text/plain")


def variations_table(request):
    def row_generator():
        qs = get_sorted_variations()

        yield "<html><body><table>\n"
        yield (
            '<tr style="background-color: lightblue; text-align: left"><th>Start</th>'
            "<th>C</th><th>#</th><th>Variation</th><th>Moves</th></tr>\n"
        )

        URL_BASE = f"{settings.CHESSER_URL}/variation"
        total = 0
        for chapter_title, group in groupby(qs, key=lambda v: v.chapter.title):
            group_list = list(group)
            count_in_chapter = len(group_list)

            yield (
                f'<tr style="background-color: lightblue; font-weight: bold;">'
                f'<td colspan="5">{chapter_title}: {count_in_chapter}</td></tr>\n'
            )

            for idx, v in enumerate(group_list, start=1):
                total += 1
                highlight = (
                    ' style="background-color: #f0f0f0;"' if idx % 2 == 0 else ""
                )
                yield (
                    f"<tr{highlight}>"
                    f"<td>{v.start_move}</td>"
                    f"<td>{v.course.title[0]}</td>"
                    f'<td style="text-align: right">'
                    f'<a href="{URL_BASE}/{v.id}/">{v.id}</a></td>'
                    f'<td style="white-space: nowrap;">{v.title}</td>'
                    f'<td style="white-space: nowrap;">{v.mainline_moves}</td>'
                    "</tr>\n"
                )

        yield (
            f'<tr style="background-color: lightblue; font-weight: bold;">'
            f'<td colspan="5">Total variations: {total}</td></tr>\n'
            f"</table></body></html>"
        )

    return StreamingHttpResponse(row_generator(), content_type="text/html")


def edit(request, variation_id=None):
    if variation_id is None:
        variation = Variation.objects.first()
    else:
        variation = get_object_or_404(
            Variation.objects.select_related("chapter__course").prefetch_related(
                "moves"
            ),
            pk=variation_id,
        )

    variation_data = serialize_variation(variation) if variation else {}
    context = {"variation_data": json.dumps(variation_data)}

    return render(request, "edit.html", context)


@csrf_exempt
def save_variation(request):
    if request.method == "POST":
        data = json.loads(request.body)
        variation_id = data.get("variation_id")
        print(f"saving variation {variation_id}")
        variation = get_object_or_404(Variation, pk=variation_id)
        variation.title = data["title"]
        variation.start_move = data["start_move"]
        variation.save()

        for idx, move in enumerate(variation.moves.all()):
            move.san = data["moves"][idx]["san"]
            move.annotation = data["moves"][idx]["annotation"]
            move.text = data["moves"][idx]["text"]
            move.alt = data["moves"][idx]["alt"]
            move.alt_fail = data["moves"][idx]["alt_fail"]
            move.shapes = data["moves"][idx]["shapes"]
            move.save()

        return JsonResponse({"status": "success"})

    return JsonResponse(
        {"status": "error", "message": "Invalid request method"}, status=400
    )


def variation(request, variation_id=None):
    if variation_id is None:
        variation = Variation.objects.first()
    else:
        variation = get_object_or_404(
            Variation.objects.select_related("chapter__course").prefetch_related(
                "moves"
            ),
            pk=variation_id,
        )

    variation_data = serialize_variation(variation, all_data=True) if variation else {}
    context = {"variation_data": json.dumps(variation_data)}

    return render(request, "variation.html", context)


class HomeView:
    def __init__(self, course_id=None, chapter_id=None):
        self.now = timezone.now()

        self.course_id = course_id
        self.chapter_id = chapter_id

        home_stuff = {
            "nav": self.get_course_links(),
            "recent": self.get_recently_reviewed(),
            "recently_added": self.get_recently_added(),
            "next_due": self.get_next_due(),
            "upcoming": self.get_upcoming_time_planner(),
            "levels": self.get_level_report(),
        }

        self.home_data = {"home_data": json.dumps(home_stuff)}

    @property
    def data(self):
        return self.home_data

    def get_variations(self):
        variations = Variation.objects.all()
        if self.course_id:
            variations = variations.filter(course_id=self.course_id)
        if self.chapter_id:
            variations = variations.filter(chapter_id=self.chapter_id).prefetch_related(
                "quiz_results"
            )
        return variations

    def get_course_links(self):
        nav = {
            "course_id": "",
            "course_title": "",
            "chapter_id": "",
            "chapter_title": "",
            "courses": [],
            "chapters": [],
            "variations": [],
            "courses_var_count": 0,  # total white + black variations
            "chapters_var_count": 0,  # total white or black variations
        }
        if not self.course_id:
            for course in Course.objects.all():
                variation_count = Variation.objects.filter(
                    chapter__course=course
                ).count()
                nav["courses_var_count"] += variation_count
                nav["courses"].append(
                    {
                        "id": course.id,
                        "title": course.title,
                        "variation_count": variation_count,
                    }
                )
        elif not self.chapter_id:
            course = Course.objects.get(id=self.course_id)
            for chapter in (
                Chapter.objects.filter(course=course).order_by("title").iterator()
            ):
                variation_count = Variation.objects.filter(chapter=chapter).count()
                nav["chapters_var_count"] += variation_count
                nav["chapters"].append(
                    {
                        "id": chapter.id,
                        "title": chapter.title,
                        "variation_count": variation_count,
                    }
                )

            nav["course_id"] = course.id
            nav["course_title"] = course.title
        else:
            qs = (
                Variation.objects.filter(chapter_id=self.chapter_id)
                .annotate(sort_key=Lower("mainline_moves_str"))
                .order_by("sort_key")
            )
            for variation in qs.iterator():
                time_since_last_review = util.get_time_ago(
                    self.now, variation.get_latest_quiz_result_datetime()
                )
                time_until_next_review = util.format_time_until(
                    self.now, variation.next_review
                )

                nav["variations"].append(
                    {
                        "id": variation.id,
                        "title": variation.title,
                        "level": variation.level,
                        "start_move": variation.start_move,
                        "time_since_last_review": time_since_last_review,
                        "time_until_next_review": time_until_next_review,
                        "mainline_moves_str": variation.mainline_moves_str,
                    }
                )

            nav["course_id"] = self.course_id
            nav["course_title"] = Course.objects.get(id=self.course_id).title
            nav["chapter_id"] = self.chapter_id
            nav["chapter_title"] = Chapter.objects.get(id=self.chapter_id).title

        return nav

    def get_level_report(self):
        level_counts = []

        levels = [
            (" 0 - Not started", 0),
            (" 1 - 4 hours", 1),
            (" 2 - 1 day", 2),
            (" 3 - 3 days", 3),
            (" 4 - 1 week", 4),
            (" 5 - 2 weeks", 5),
            (" 6 - 1 month", 6),
            (" 7 - 2 months", 7),
            (" 8 - 4 months", 8),
            (" 9 - 6 months", 9),
            ("10+", 10),
        ]

        variations = self.get_variations()
        for label, level in levels:
            if level == 10:
                count = variations.filter(level__gte=level).count()
            else:
                count = variations.filter(level=level).count()

            if count > 0:
                level_counts.append(
                    {
                        "label": label,
                        "count": count,
                    }
                )

        return level_counts

    def get_next_due(self):
        output = ""
        emoji = "☀️"
        variations = self.get_variations()
        if variations.filter(next_review__lte=self.now).count():
            output = "Now, and then in "
            emoji = "⏰"

        if (
            next_due := variations.filter(next_review__gt=self.now)
            .order_by("next_review")
            .first()
        ):
            output += util.format_time_until(self.now, next_due.next_review)
        else:
            output += "…?"

        # There is a next due js timer that expects this format
        # when less than one minute: "Next: 59s" (doesn't matter
        # what comes before or after)
        return f"{emoji} Next: {output}"

    def get_upcoming_time_planner(self):
        ranges = [
            ("Now", 0),
            ("1 hour", 1),
            # ("2 hours", 2),
            ("4 hours", 4),
            ("8 hours", 8),
            ("16 hours", 16),
            ("1 day", 1 * 24),
            # ("2 days", 2 * 24),
            ("3 days", 3 * 24),
            # ("4 days", 4 * 24),
            # ("5 days", 5 * 25),
            # ("6 days", 6 * 24),
            ("1 week", 1 * 7 * 24),
            # ("2 weeks", 2 * 7 * 24),
            # ("3 weeks", 3 * 7 * 24),
            ("1 month", 1 * 30 * 24),
            ("2 months", 2 * 30 * 24),
            ("4 months", 4 * 30 * 24),
            ("6 months", 6 * 30 * 24),
        ]
        times = []
        previous_count = -1
        for label, hours in ranges:
            count = self.get_variation_count_for_time_range(hours)
            if previous_count != count:
                previous_count = count
                times.append(
                    {
                        "label": label,
                        "count": count,
                    }
                )
        return times

    def get_variation_count_for_time_range(self, hours):
        end_time = self.now + timezone.timedelta(hours=hours)
        variations = self.get_variations()
        return variations.filter(next_review__lt=end_time).count()

    def get_recently_reviewed(self):
        variations_qs = self.get_variations().values("id")  # Subquery, not list of IDs
        recently_reviewed = QuizResult.objects.filter(
            variation__in=variations_qs
        ).order_by("-datetime")[:50]

        reviewed = []
        seen = set()
        for result in recently_reviewed:
            if result.variation_id not in seen:
                seen.add(result.variation_id)

                reviewed.append(
                    {
                        "variation_id": result.variation_id,
                        "variation_title": result.variation.title,
                        "datetime": util.get_time_ago(self.now, result.datetime),
                        "level": result.level,
                        "passed": "✅" if result.passed else "❌",
                    }
                )

                if len(seen) > 20:
                    break
        return reviewed

    def get_recently_added(self):
        one_week_ago = timezone.now() - timezone.timedelta(days=7)

        recently_added = Variation.objects.filter(
            created_at__gte=one_week_ago
        ).order_by("-created_at")[:20]
        added = []
        for result in recently_added:
            added.append(
                {
                    "variation_id": result.id,
                    "variation_title": result.title,
                    "created_at": util.get_time_ago(self.now, result.created_at),
                    "next_review": util.format_time_until(self.now, result.next_review),
                }
            )

        return added
