import json
from datetime import timezone as dt_timezone

import chess
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.html import strip_tags

from chesser import util
from chesser.models import Chapter, Move, QuizResult, SharedMove, Variation
from chesser.pgn_import import extract_pgn_directives

NORMALIZED_ANNOTATIONS = {
    # Counterplay
    "⇆": "⇄",
    # Winning advantage (ASCII → Unicode)
    "+-": "±",
    "-+": "∓",
    # Slight advantage (common ASCII forms → Informant glyphs)
    "+=": "⩲",  # White slightly better
    "+/=": "⩲",
    "=+/": "⩲",  # rare typo variant
    "=+": "⩱",  # Black slightly better
    "=/+": "⩱",
    # Equality cleanup
    "==": "=",  # sometimes typed
    # Checkmate (older notation)
    "++": "#",
    # Delta variants (with the idea)
    "Δ": "△",
    # Only move
    "[]": "□",
    # Zugzwang (optional, only if you allow ASCII shorthand)
    "ZZ": "⊙",
    # Unclear position (optional, very risky outside eval fields)
    "~": "∞",
    # Attack
    "->": "→",
}


def normalize_annotation(value: str) -> str:
    """
    Normalize an *annotation token* (not free-form text).

    - trims whitespace
    - collapses common ASCII variants to canonical glyphs
    - returns "" for falsy/blank inputs
    """
    if not value:
        return ""

    token = value.strip()
    if not token:
        return ""

    return NORMALIZED_ANNOTATIONS.get(token, token)


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

    if variation.is_intro != import_data.get("is_intro", False):
        changes.add("is_intro")
    if variation.archived != import_data.get("archived", False):
        changes.add("archived")

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


def get_normalized_mainline(import_data) -> str:
    # valid mainline string should have no html, I think
    raw = strip_tags(import_data.get("mainline", "")).strip()
    if not raw:
        raise ValueError("Mainline not found or empty")

    normalized = util.normalize_notation(raw)
    if normalized != raw:
        print("Normalized mainline notation")
    return normalized


@transaction.atomic
def import_variation(
    import_data, source_variation_id=0, end_move=None, force_update=False
):
    """source_variation_id used for cloning"""

    if not force_update:
        if variation_id := import_data.get("variation_id"):
            try:
                Variation.objects.get(pk=variation_id)
                # alternatively, it would be easy enough to remove
                # variation id from import if we're okay with it 🤷
                raise ValueError(
                    f"Variation #{variation_id} already exists; not importing"
                )
            except Variation.DoesNotExist:
                pass  # good to go; note that we'll not reuse the ID
    else:
        if variation_id := import_data.get("variation_id"):
            print(
                "⚠️  force_update=True: ignoring variation_id collision "
                f"checks (variation_id={variation_id})"
            )

    color = import_data.get("color", "").lower()
    chapter, created = Chapter.objects.get_or_create(
        title=import_data["chapter_title"],
        color=color,
    )
    label = "Creating" if created else "Getting"
    print("➤ " * 32)
    print(f"{label} chapter: {chapter}")

    mainline = get_normalized_mainline(import_data)

    end_index = 1000
    if end_move:
        # 1.e4 e5 2.Nf3 Nc6
        #            3   4
        end_index = end_move * 2 - (1 if color == "white" else 0)
        mainline = " ".join(mainline.split()[:end_index])
        print(f"Shortening mainline to: {mainline}")

    import_created_at = import_data.get("created_at")
    created_at = (
        get_utc_datetime(import_created_at) if import_created_at else timezone.now()
    )

    variation, created = Variation.objects.get_or_create(
        chapter=chapter,
        mainline_moves_str=mainline,
        defaults={
            "chapter": chapter,
            "created_at": created_at,
        },
    )

    if not created and variation.chapter != chapter:
        print(
            f"⚠️  Variation exists in a different chapter: "
            f"'{variation.chapter.title}' vs '{chapter.title}'"
        )

    label = "Creating" if created else "Updating"
    print(f"{label} variation #{variation.id}: {variation.mainline_moves_str}")

    if not created:
        changes = get_changes(variation, import_data)
        if changes:
            print(f"💥 Changes: {','.join(changes)}")
        else:
            print("🔒️ No changes")

        message = f"Mainline already exists for this chapter, #{variation.id}"
        if force_update:
            print(f"⚠️  {message} — force_update=True, proceeding with update")
        else:
            print(message)
            raise ValueError(message)

    variation.source = import_data.get("source")
    # This is displayed with x-text in the template so shouldn't *need* this, but...
    variation.title = strip_tags(import_data["variation_title"])
    variation.is_intro = import_data.get("is_intro", False)
    variation.archived = import_data.get("archived", False)
    variation.start_move = import_data["start_move"]
    if created and import_data["level"] >= 0:
        variation.level = import_data["level"]
        variation.next_review = get_utc_datetime(import_data["next_review"])
    else:
        print("Not updating level and next_review")

    variation.save()

    board = chess.Board(chess.STARTING_FEN)
    for idx, move_import in enumerate(import_data["moves"]):

        if end_move and idx >= end_index:
            print(f'Skipping moves from {move_import["move_num"]}-{move_import["san"]}')
            break

        board.push_san(move_import["san"])

        move, created = Move.objects.get_or_create(
            variation=variation,
            move_num=move_import["move_num"],
            sequence=idx,
        )
        raw_text = move_import.get("text") or ""
        text_without_directives, directive_shapes = extract_pgn_directives(raw_text)
        stripped_annotation = strip_tags(move_import.get("annotation") or "")

        move.fen = board.fen()
        move.san = strip_tags(move_import["san"])
        move.annotation = normalize_annotation(stripped_annotation)
        move.text = util.clean_html(text_without_directives)
        move.alt = util.normalize_alt_moves(move_import.get("alt") or "")
        move.alt_fail = util.normalize_alt_moves(move_import.get("alt_fail") or "")
        # we'll prefer shapes from regular import field; maybe we should warn if both...
        shapes_raw = move_import.get("shapes") or directive_shapes
        move.shapes = json.dumps(shapes_raw) if shapes_raw else ""

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

    # create shared moves if possible
    source_variation = (
        Variation.objects.get(id=source_variation_id) if source_variation_id else None
    )
    linked = shared_move_auto_linker(variation, source_variation, preview=False)
    print(f"Linked {linked} shared moves")

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


def get_shareable_string(move):
    return (
        move.text + move.annotation + move.alt + move.alt_fail + move.shapes
    ).strip()


def get_exact_shared_match(move_qs, move):
    return move_qs.filter(
        text=move.text,
        annotation=move.annotation,
        alt=move.alt,
        alt_fail=move.alt_fail,
        shapes=move.shapes,
    ).first()


def create_or_get_shared_move(move, opening_color):
    shared_move, _ = SharedMove.objects.get_or_create(
        san=move.san,
        fen=move.fen,
        opening_color=opening_color,
        defaults={
            "text": move.text,
            "annotation": move.annotation,
            "alt": move.alt,
            "alt_fail": move.alt_fail,
            "shapes": move.shapes,
        },
    )
    return shared_move


@transaction.atomic
def shared_move_auto_linker(variation, source_variation=None, preview=False) -> int:
    """preview may be used eventually to offer a
    button to update if there are shareable moves"""
    opening_color = variation.chapter.color
    moves_linked = 0

    for move in variation.moves.all():
        if move.shared_move and move.sequence > 0:
            # shared_move probably never true on initial import, but perhaps
            # later we'll allow on-demand auto-linking; and let's not auto-link
            # the first move
            continue

        shareable_fields = get_shareable_string(move)

        # cloning from another variation -- we can make more concrete decisions here
        if source_variation:
            try:
                # bail out when we run out of moves (num/seq) or diverge (fen/san)
                source_move = source_variation.moves.get(
                    move_num=move.move_num,
                    sequence=move.sequence,
                    fen=move.fen,
                    san=move.san,
                )
            except Move.DoesNotExist:
                break

            move.shared_move = source_move.shared_move

            if move.shared_move:
                moves_linked += 1
                if not preview:
                    move.save()
                continue

            source_fields = get_shareable_string(source_move)
            shared_moves = SharedMove.objects.filter(
                san=move.san,
                fen=move.fen,
                opening_color=opening_color,
            )

            if shared_moves.count() == 1 and not shareable_fields and not source_fields:
                shared_move = shared_moves.first()
                moves_linked += 1
                if not preview:
                    move.shared_move = shared_move
                    move.save()
                    source_move.shared_move = shared_move
                    source_move.save()
                continue

            if not shared_moves.exists():
                shared_move = create_or_get_shared_move(source_move, opening_color)
                moves_linked += 1
                if not preview:
                    move.shared_move = shared_move
                    move.save()
                    source_move.shared_move = shared_move
                    source_move.save()
            continue

        # standard import / variation creation, look for easy sharing opportunities
        shared_moves = SharedMove.objects.filter(
            san=move.san,
            fen=move.fen,
            opening_color=opening_color,
        )

        if shared_moves.count() > 1:
            exact_match = get_exact_shared_match(shared_moves, move)
            if exact_match:
                moves_linked += 1
                if not preview:
                    move.shared_move = exact_match
                    move.save()
            continue

        if shared_moves.count() == 1:
            exact_match = shared_moves.first()
            if move.shareable_fields_match(exact_match) or not shareable_fields:
                moves_linked += 1
                if not preview:
                    move.shared_move = exact_match
                    move.save()
            continue

        # shared_moves.count() == 0
        matching_blank_moves = Move.objects.filter(
            san=move.san,
            fen=move.fen,
            variation__chapter__color=opening_color,
            text="",
            annotation="",
            alt="",
            alt_fail="",
            shapes="",
            shared_move__isnull=True,
        ).exclude(pk=move.pk)

        if matching_blank_moves.exists():
            shared_move = create_or_get_shared_move(move, opening_color)
            moves_linked += matching_blank_moves.count() + 1
            if not preview:
                move.shared_move = shared_move
                move.save()
                matching_blank_moves.update(shared_move=shared_move)

    return moves_linked
