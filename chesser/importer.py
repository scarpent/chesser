import json
from datetime import timezone as dt_timezone

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from chesser.models import Course, Move, QuizResult, Variation


def get_utc_datetime(date_string):
    """
    chessable is in UTC but we expect an ISO8601 date with no Z,
    e.g. "2025-03-09T04:19:46" (that's how we build the import file)"

    using `from datetime import timezone` instead of django's;
    we're doing a timezone-aware conversion from a known format
    """
    if parsed_datetime := parse_datetime(date_string):
        utc_datetime = parsed_datetime.replace(tzinfo=dt_timezone.utc)
        return utc_datetime
    else:
        raise ValueError(
            f"Invalid date_string format: {date_string}, expected YYYY-MM-DDTHH:MM:SS"
        )


def get_changes(variation, import_data):
    changes = set()

    if variation.source != import_data["source"]:
        changes.add("source")
    if variation.title != import_data["variation_title"]:
        changes.add("title")
    if variation.start_move != import_data["start_move"]:
        changes.add("start_move")

    for idx, move_import in enumerate(import_data["moves"]):
        try:
            move = Move.objects.get(
                variation=variation,
                move_num=move_import["move_num"],
                sequence=idx,
            )
        except Move.DoesNotExist:
            changes.add("new moves")
            continue

        if move.move_num != move_import["move_num"]:
            changes.add(f"move_num {move.move_num}, seq {idx}")
        if move.san != move_import["san"]:
            changes.add("san")
        if move.annotation != move_import["annotation"]:
            changes.add("annotation")
        if move.text != move_import["text"]:
            changes.add("text")
        if move.alt != move_import.get("alt", ""):
            changes.add("alt")
        if move.alt_fail != move_import.get("alt_fail", ""):
            changes.add("alt_fail")

        incoming_shapes = (
            json.dumps(move_import["shapes"]) if move_import["shapes"] else ""
        )
        if move.shapes != incoming_shapes:
            changes.add("shapes")

    return changes


@transaction.atomic
def import_variation(import_data, end_move=None):
    course = Course.objects.get(color=import_data["color"])
    chapter, created = course.chapter_set.get_or_create(
        course=course, title=import_data["chapter_title"]
    )
    label = "Creating" if created else "Getting"
    print("➤ " * 32)
    print(f"{label} chapter: {chapter}")

    mainline = import_data["mainline"].strip()
    end_index = 1000
    if end_move:
        # 1.e4 e5 2.Nf3 Nc6
        #            3   4
        end_index = end_move * 2 - (1 if course.color == "white" else 0)
        mainline = " ".join(mainline.split()[:end_index])
        print(f"Shortening mainline to: {mainline}")

    variation, created = Variation.objects.get_or_create(
        course=course,
        mainline_moves_str=mainline,
        defaults={
            "chapter": chapter,
            "created_at": timezone.now(),
        },
    )

    if not created and variation.chapter != chapter:
        print(
            f"⚠️ Variation exists in a different chapter: "
            f"'{variation.chapter.title}' vs '{chapter.title}'"
        )

    label = "Creating" if created else "Updating"
    print(f"{label} variation #{variation.id}: {variation.mainline_moves}")

    if not created:
        changes = get_changes(variation, import_data)
        if changes:
            print(f"💥 Changes: {','.join(changes)}")
        else:
            print("🔒️ No changes")
        # later we might re-import in some cases
        message = f"Mainline already exists in this course, #{variation.id}"
        print(message)
        return False, message

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

        if end_move and idx >= end_index:
            print(f'Skipping moves from {move_import["move_num"]}-{move_import["san"]}')
            break

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

    return True, f"#{variation.id} (L{variation.level})"
