import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from chesser.models import Chapter, Course, QuizResult, Variation
from chesser.serializers import serialize_variation


def home(request):
    nav = get_course_links(request)
    home_data = {
        "home_data": json.dumps(
            {
                "nav": nav,
                "recent": get_recently_reviewed(),
                "upcoming": get_upcoming_time_planner(),
                "levels": get_level_report(),
            }
        )
    }
    return render(request, "home.html", home_data)


def get_level_report():
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

    for label, level in levels:
        if level == 10:
            count = Variation.objects.filter(level__gte=level).count()
        else:
            count = Variation.objects.filter(level=level).count()

        if count > 0:
            level_counts.append((label, count))

    return level_counts


def get_upcoming_time_planner():
    times = []
    now = timezone.now()

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
    ]
    previous_count = -1
    for label, hours in ranges:
        count = get_variation_count_for_time_range(now, hours)
        if previous_count != count or count == 0:
            previous_count = count
            times.append((label, count))

    print(times)

    return times


def get_variation_count_for_time_range(now, hours):
    # use timedelta to find the time range
    end_time = now + timezone.timedelta(hours=hours)
    return Variation.objects.filter(
        next_review__lt=end_time,
    ).count()


def get_recently_reviewed():
    recently_reviewed = QuizResult.objects.filter().order_by("-datetime")[:30]
    reviewed = []
    seen = set()
    for result in recently_reviewed:
        if result.variation_id not in seen:
            seen.add(result.variation_id)
            the_date = result.datetime.strftime("%m-%d %H:%M")
            reviewed.append(
                (result.variation_id, f"{result.variation.title} ({the_date})")
            )
            if len(seen) > 5:
                break
    print(reviewed)
    return reviewed


def get_course_links(request):
    nav = {
        "course_id": "",
        "course_name": "",
        "chapter_id": "",
        "chapter_name": "",
        "courses": {},
        "chapters": {},
        "variations": {},
    }
    course = request.GET.get("course")
    chapter = request.GET.get("chapter")
    if not course:
        for course in Course.objects.all():
            nav["courses"][course.id] = course.title
    elif not chapter:
        for chapter in (
            Chapter.objects.filter(course=course).order_by("title").iterator()
        ):
            nav["chapters"][chapter.id] = chapter.title

        nav["course_id"] = course
        nav["course_name"] = Course.objects.get(id=course).title
    else:
        for variation in (
            Variation.objects.filter(chapter=chapter).order_by("title").iterator()
        ):
            nav["variations"][variation.id] = variation.title

        nav["course_id"] = course
        nav["course_name"] = Course.objects.get(id=course).title
        nav["chapter_id"] = chapter
        nav["chapter_name"] = Chapter.objects.get(id=chapter).title

    return nav


def review(request, variation_id=None):
    if variation_id is None:
        extra_study = False
        variation = Variation.due_for_review()
    else:
        # Can review "on demand", but it won't update level/next_review
        extra_study = True
        variation = get_object_or_404(
            Variation.objects.select_related("chapter__course").prefetch_related(
                "moves"
            ),
            pk=variation_id,
        )

    if variation is None:
        variation_data = {}
    else:
        variation_data = serialize_variation(variation)

    context = {
        "variation_data": json.dumps(variation_data),
        "extra_study": json.dumps(extra_study),
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

        return JsonResponse({"status": "success"})

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

    if variation is None:
        variation_data = {}
    else:
        variation_data = serialize_variation(variation, generate_html=True)

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

    if variation is None:
        variation_data = {}
    else:
        variation_data = serialize_variation(variation, generate_html=True)

    context = {"variation_data": json.dumps(variation_data)}
    return render(request, "variation.html", context)
