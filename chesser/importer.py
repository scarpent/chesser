import json
from datetime import timezone

from django.utils.dateparse import parse_datetime

from chesser.models import Course, Move, QuizResult, Variation


def get_utc_datetime(date_string):
    # chessable is in UTC but we expect an ISO8601 date with no Z,
    # e.g. "2025-03-09T04:19:46" (that's how we build the import file)
    if parsed_datetime := parse_datetime(date_string):
        utc_datetime = parsed_datetime.replace(tzinfo=timezone.utc)
        return utc_datetime
    else:
        print(f"Invalid format for date_string: {date_string}")


def import_variation(import_data):
    course = Course.objects.get(color=import_data["color"])
    chapter, created = course.chapter_set.get_or_create(
        course=course, title=import_data["chapter_title"]
    )
    label = "Creating" if created else "Getting"
    print(f"{label} chapter: {chapter}")
    variation, created = Variation.objects.get_or_create(
        course=course,
        chapter=chapter,
        mainline_moves_str=import_data["mainline"],
    )
    label = "Creating" if created else "Updating"
    print(f"{label} variation #{variation.id}: {variation.mainline_moves}")

    variation.source = import_data["source"]
    variation.title = import_data["variation_title"]
    variation.start_move = import_data["start_move"]
    if created and import_data["level"] >= 0:
        variation.level = import_data["level"]
        variation.next_review = get_utc_datetime(import_data["next_review"])
    else:
        print("Not updating level and next_review")

    variation.save()

    for idx, move_import in enumerate(import_data["moves"]):
        move, created = Move.objects.get_or_create(
            variation=variation,
            move_num=move_import["move_num"],
            sequence=idx,
        )
        move.move_num = move_import["move_num"]
        move.san = move_import["san"]
        move.annotation = move_import["annotation"]
        move.text = move_import["text"]
        move.alt = move_import.get("alt", "")
        move.alt_fail = move_import.get("alt_fail", "")
        move.shapes = json.dumps(move_import["shapes"]) if move_import["shapes"] else ""

        move.save()

    if variation.level < 1 or not created:
        print("Not creating QuizResult for updated variation or new level 0 variation")
    elif not variation.quiz_results.first():
        print("Creating QuizResult")
        quiz_result = QuizResult.objects.create(
            variation=variation, passed=True, level=variation.level
        )
        quiz_result.datetime = get_utc_datetime(import_data["last_review"])
        quiz_result.save()
