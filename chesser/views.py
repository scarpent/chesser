import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from chesser import util
from chesser.models import Chapter, Course, QuizResult, Variation
from chesser.serializers import serialize_variation


def home(request):
    home_view = HomeView(request)
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


def importer(request):
    import_data = {"import_data": json.dumps("Import data!")}
    return render(request, "import.html", import_data)


def upload_json_data(request):
    file = request.FILES.get("uploaded_file")
    if file and request.method == "POST":
        file_content = file.read().decode("utf-8")

        try:
            json.loads(file_content)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format."}, status=400)

        with open("/tmp/upload.json", "w") as temp_file:
            temp_file.write(file_content)

        return JsonResponse({"message": "Data saved successfully"}, status=200)

    return render(request, "import.html")


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
    def __init__(self, request):
        self.now = timezone.now()

        nav = self.get_course_links(request)
        self.course_id = nav["course_id"]
        self.chapter_id = nav["chapter_id"]

        home_stuff = {
            "nav": nav,
            "recent": self.get_recently_reviewed(),
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

    def get_course_links(self, request):
        nav = {
            "course_id": "",
            "course_name": "",
            "chapter_id": "",
            "chapter_name": "",
            "courses": [],
            "chapters": [],
            "variations": [],
            "courses_var_count": 0,  # total white + black variations
            "chapters_var_count": 0,  # total white or black variations
        }
        course_id = request.GET.get("course")
        chapter_id = request.GET.get("chapter")
        if not course_id:
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
        elif not chapter_id:
            course = Course.objects.get(id=course_id)
            for chapter_id in (
                Chapter.objects.filter(course=course).order_by("title").iterator()
            ):
                variation_count = Variation.objects.filter(chapter=chapter_id).count()
                nav["chapters_var_count"] += variation_count
                nav["chapters"].append(
                    {
                        "id": chapter_id.id,
                        "title": chapter_id.title,
                        "variation_count": variation_count,
                    }
                )

            nav["course_id"] = course.id
            nav["course_name"] = course.title
        else:
            for variation in (
                Variation.objects.filter(chapter=chapter_id)
                .order_by("mainline_moves_str")
                .iterator()
            ):

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

            nav["course_id"] = course_id
            nav["course_name"] = Course.objects.get(id=course_id).title
            nav["chapter_id"] = chapter_id
            nav["chapter_name"] = Chapter.objects.get(id=chapter_id).title

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

                if len(seen) > 15:
                    break
        return reviewed
