import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.timesince import timesince
from django.views.decorators.csrf import csrf_exempt

from chesser.models import Chapter, Course, QuizResult, Variation
from chesser.serializers import serialize_variation


def home(request):
    nav = get_course_links(request)
    course_id = nav["course_id"]
    chapter_id = nav["chapter_id"]
    now = timezone.now()
    home_data = {
        "home_data": json.dumps(
            {
                "nav": nav,
                "recent": get_recently_reviewed(now),
                "next_due": get_next_due(
                    now, course_id=course_id, chapter_id=chapter_id
                ),
                "upcoming": get_upcoming_time_planner(
                    now, course_id=course_id, chapter_id=chapter_id
                ),
                "levels": get_level_report(course_id=course_id, chapter_id=chapter_id),
            }
        )
    }
    return render(request, "home.html", home_data)


def get_level_report(course_id=None, chapter_id=None):
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

    variations = Variation.objects.all()
    if course_id:
        variations = variations.filter(course_id=course_id)
    if chapter_id:
        variations = variations.filter(chapter_id=chapter_id)

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


def get_next_due(now, course_id=None, chapter_id=None):
    output = ""
    variations = Variation.objects.all()
    if course_id:
        variations = variations.filter(course_id=course_id)
    if chapter_id:
        variations = variations.filter(chapter_id=chapter_id)

    if variations.filter(next_review__lte=now).count():
        output = "Right now, and then "

    if (
        next_due := variations.filter(next_review__gt=now)
        .order_by("next_review")
        .first()
    ):
        time_until = next_due.next_review - now
        days = time_until.days
        hours, remainder = divmod(time_until.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if days:
            output += pluralize(days, "day")
        if hours:
            output += pluralize(hours, "hour")
        if minutes:
            output += pluralize(minutes, "minute")
        if not hours and not minutes or minutes < 2:
            output += pluralize(seconds, "second")
    else:
        output = "♾️"

    return f"Next review: {output}"


def pluralize(count, label):
    if count != 1:
        label += "s"
    return f" {count} {label}"


def get_upcoming_time_planner(now, course_id=None, chapter_id=None):
    ranges = [
        ("Now", 0),
        ("1 hour", 1),
        ("2 hours", 2),
        ("4 hours", 4),
        ("8 hours", 8),
        ("16 hours", 16),
        ("1 day", 1 * 24),
        ("2 days", 2 * 24),
        ("3 days", 3 * 24),
        ("4 days", 4 * 24),
        ("5 days", 5 * 25),
        ("6 days", 6 * 24),
        ("1 week", 1 * 7 * 24),
        ("2 weeks", 2 * 7 * 24),
        ("3 weeks", 3 * 7 * 24),
        ("1 month", 1 * 30 * 24),
        ("2 months", 2 * 30 * 24),
        ("4 months", 4 * 30 * 24),
        ("6 months", 6 * 30 * 24),
    ]
    times = []
    previous_count = -1
    for label, hours in ranges:
        count = get_variation_count_for_time_range(
            now, hours, course_id=course_id, chapter_id=chapter_id
        )
        if previous_count != count:
            previous_count = count
            times.append(
                {
                    "label": label,
                    "count": count,
                }
            )
    return times


def get_variation_count_for_time_range(now, hours, course_id=None, chapter_id=None):
    end_time = now + timezone.timedelta(hours=hours)
    variations = Variation.objects.all()
    if course_id:
        variations = variations.filter(course_id=course_id)
    if chapter_id:
        variations = variations.filter(chapter_id=chapter_id)

    return variations.filter(next_review__lt=end_time).count()


def get_recently_reviewed(now):
    recently_reviewed = QuizResult.objects.filter().order_by("-datetime")[:50]
    reviewed = []
    seen = set()
    for result in recently_reviewed:
        if result.variation_id not in seen:
            seen.add(result.variation_id)

            # TODO: Consider django naturaltime from humanize;
            # requires enabling django.contrib.humanize in INSTALLED_APPS.

            time_ago = timesince(result.datetime, now)
            date_unit = time_ago.split(",")[0] + " ago"  # Largest unit
            reviewed.append(
                {
                    "variation_id": result.variation_id,
                    "variation_title": result.variation.title,
                    "datetime": date_unit,
                    "level": result.level,
                    "passed": "✅" if result.passed else "❌",
                }
            )

            if len(seen) > 12:
                break
    return reviewed


def get_course_links(request):
    nav = {
        "course_id": "",
        "course_name": "",
        "chapter_id": "",
        "chapter_name": "",
        "courses": [],
        "chapters": [],
        "variations": [],
    }
    course_id = request.GET.get("course")
    chapter_id = request.GET.get("chapter")
    if not course_id:
        for course in Course.objects.all():
            variation_count = Variation.objects.filter(chapter__course=course).count()
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
            .order_by("move_sequence")
            .iterator()
        ):
            nav["variations"].append(
                {
                    "id": variation.id,
                    "title": variation.title,
                    "level": variation.level,
                    "move_sequence": variation.move_sequence,
                }
            )

        nav["course_id"] = course_id
        nav["course_name"] = Course.objects.get(id=course_id).title
        nav["chapter_id"] = chapter_id
        nav["chapter_name"] = Chapter.objects.get(id=chapter_id).title

    return nav


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
