import json
from datetime import timezone as dt_timezone
from io import StringIO

import chess
import chess.pgn
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from chesser import util
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

    if variation_id := import_data.get("variation_id"):
        try:
            Variation.objects.get(pk=variation_id)
            raise ValueError(f"Variation #{variation_id} already exists; not importing")
        except Variation.DoesNotExist:
            pass  # good to go; note that we'll not reuse the ID

    course = Course.objects.get(color=import_data["color"])
    chapter, created = course.chapter_set.get_or_create(
        course=course, title=import_data["chapter_title"]
    )
    label = "Creating" if created else "Getting"
    print("➤ " * 32)
    print(f"{label} chapter: {chapter}")

    mainline = import_data.get("mainline", "").strip()
    if not mainline:
        raise ValueError("Mainline not found or empty")

    normalized_mainline = util.normalize_notation(mainline)
    if normalized_mainline != mainline:
        print(f"Normalized mainline: {normalized_mainline}")
        mainline = normalized_mainline

    end_index = 1000
    if end_move:
        # 1.e4 e5 2.Nf3 Nc6
        #            3   4
        end_index = end_move * 2 - (1 if course.color == "white" else 0)
        mainline = " ".join(mainline.split()[:end_index])
        print(f"Shortening mainline to: {mainline}")

    # TODO: use created_at from import_data if it exists?

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
        raise ValueError(message)

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

    validate_mainline_string(
        [m.san for m in variation.moves.all()],
        variation.mainline_moves_str,
    )

    if variation.level < 1 or not created:
        print("Not creating QuizResult for updated variation or new level 0 variation")
    elif not variation.quiz_results.first():
        print("Creating QuizResult")
        passed = False if variation.level == 1 else True
        level = variation.level - 1 if passed else variation.level
        quiz_result = QuizResult.objects.create(
            variation=variation, passed=passed, level=level
        )
        quiz_result.datetime = get_utc_datetime(import_data["last_review"])
        quiz_result.save()

    variation_link = f'<a href="/variation/{variation.id}/">#{variation.id}</a>'
    return f"{variation_link} (L{variation.level})"


def validate_mainline_string(sans, mainline_str):
    board = chess.Board()

    for i, san in enumerate(sans):
        try:
            move = board.parse_san(san)
            board.push(move)
        except ValueError as e:
            raise ValueError(f"Invalid move '{san}' at index {i}: {e}")

    mainline_sans = util.strip_move_numbers(mainline_str).split()

    for i, (a, b) in enumerate(zip(sans, mainline_sans)):
        if a != b:
            raise ValueError(
                f"Mainline mismatch at index {i}:\n  sans:      {a},\n  mainline:  {b}"
            )

    if len(sans) != len(mainline_sans):
        raise ValueError(
            f"Move count mismatch:\n  sans length: {len(sans)},\n "
            f" mainline length: {len(mainline_sans)}"
        )

    return True


def convert_pgn_to_json(
    pgn_text,
    color="",
    chapter_title="",
    variation_title="",
    start_move=2,
):
    """
    Convert PGN to chesser JSON format with annotations and comments.
    Grabs all comments and subvariations, and appends them to .text

    TODO: would be nice to have move validation, but bad moves seem to
    be discarded by chess.pgn.read_game()
    """
    pgn_io = StringIO(pgn_text)
    game = chess.pgn.read_game(pgn_io)
    if not game:
        raise ValueError("No valid game found in PGN")

    board = game.board()
    moves = []
    move_number = 1

    node = game
    while node.variations:
        next_node = node.variations[0]
        san = board.san(next_node.move)

        # Collect annotation from NAG (Numeric Annotation Glyphs)
        annotation = ""
        nags = list(next_node.nags)
        if nags:
            nag = nags[0]
            if nag in NAG_LOOKUP:
                annotation = NAG_LOOKUP[nag]

        moves.append(
            {
                "move_num": move_number,
                "san": san,
                "annotation": annotation,
                "text": extract_move_text(next_node),
                "alt": "",
                "alt_fail": "",
                "shapes": [],
            }
        )

        board.push(next_node.move)
        node = next_node
        if board.turn == chess.WHITE:
            move_number += 1

    return {
        "source": {},
        "color": color,
        "chapter_title": chapter_title,
        "variation_title": variation_title,
        "start_move": start_move,
        "level": 0,
        "next_review": util.END_OF_TIME_STR,
        "last_review": util.END_OF_TIME_STR,
        "mainline": get_mainline_moves_str(moves),
        "moves": moves,
    }


def extract_move_text(node: chess.pgn.GameNode) -> str:
    """
    Returns only the move's comment and immediate subvariations,
    without the mainline children.
    """
    parts = []

    if node.comment:
        parts.append(node.comment.strip())

    for subvar in node.parent.variations[1:]:
        if subvar is not node:
            parts.append(f"({str(subvar).strip()})")

    return "\n\n".join(parts).strip()


def get_mainline_moves_str(moves):
    white_to_move = True
    move_string = ""
    for move in moves:
        prefix = f"{move['move_num']}." if white_to_move else ""
        white_to_move = not white_to_move
        move_string += f"{prefix}{move['san']} "
    return move_string.strip()


NAG_LOOKUP = {
    1: "!",
    2: "?",
    3: "!!",
    4: "??",
    5: "!?",
    6: "?!",
    10: "=",
    13: "∞",
    14: "⩲",  # White slightly better
    15: "⩱",  # Black slightly better
    16: "±",
    17: "∓",
    18: "+-",
    19: "-+",
}
