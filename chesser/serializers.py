import json
import re

import chess
import chess.pgn
from django.utils import timezone

from chesser import util
from chesser.move_resolver import get_parsed_blocks

annotations = {
    "none": "No annotation",
    "?": "? Poor",
    "?!": "?! Dubious",
    "!?": "!? Interesting",
    "!": "! Good",
    "!!": "!! Brilliant",
    "??": "?? Blunder",
    "=": "= Drawish",
    "∞": "∞ Unclear",
    "⩲": "⩲ White Slight",
    "⩱": "⩱ Black Slight",
    "±": "± White Moderate",
    "∓": "∓ Black Moderate",
    "+-": "+- White Decisive",
    "-+": "-+ Black Decisive",
}


def serialize_variation(variation, all_data=False, version=1):
    color = variation.chapter.course.color

    now = timezone.now()
    time_since_last_review = util.get_time_ago(
        now, variation.get_latest_quiz_result_datetime()
    )
    time_until_next_review = util.format_time_until(now, variation.next_review)

    source_html = get_source_html(variation.source) if all_data else None
    html = generate_variation_html(variation, version=version) if all_data else None
    url_moves = "_".join([move.san for move in variation.moves.all()])
    # we'll add current fen/index in UI
    lichess_url = f"https://lichess.org/analysis/pgn/{url_moves}?color={color}&#"

    variation_data = {
        "variation_id": variation.id,
        "title": variation.title,
        "course_id": variation.chapter.course.id,
        "chapter_id": variation.chapter.id,
        "chapter": variation.chapter.title,
        "color": color,
        "start_index": variation.start_index,
        "start_move": variation.start_move,
        "level": variation.level,
        "time_since_last_review": time_since_last_review,
        "time_until_next_review": time_until_next_review,
        "created_at": util.format_local_date(variation.created_at),
        "mainline": variation.mainline_moves,
        "source_html": source_html,
        "html": html,
        "analysis_url": lichess_url,
    }

    temp_annotations = annotations.copy()
    moves = []
    for move in variation.moves.all():
        if move.annotation and move.annotation not in temp_annotations:
            # add this to annotation dict so we can re-save it
            temp_annotations[move.annotation] = f"unknown: {move.annotation}"
            print(
                f"unknown annotation in variation {variation.id}: {move.move_verbose}"
            )

        moves.append(
            {
                "move_id": move.id,
                "san": move.san,
                "annotation": move.annotation,
                "move_verbose": move.move_verbose,
                "text": move.text,
                "alt": move.alt or "",
                "alt_fail": move.alt_fail or "",
                "shapes": move.shapes or "",
            }
        )

    if all_data:
        add_alt_shapes_to_moves(moves)

    variation_data["moves"] = moves
    variation_data["annotations"] = temp_annotations
    variation_data["history"] = get_history(variation)

    return variation_data


def serialize_variation_to_import_format(variation):
    return {
        "variation_id": variation.id,
        "source": variation.source,
        "color": variation.course.color,
        "chapter_title": variation.chapter.title,
        "variation_title": variation.title,
        "level": variation.level,
        "created_at": variation.created_at.replace(microsecond=0).isoformat(),
        "next_review": variation.next_review.replace(microsecond=0).isoformat(),
        "last_review": (
            variation.get_latest_quiz_result_datetime()
            .replace(microsecond=0)
            .isoformat()
            if variation.quiz_results.exists()
            else util.END_OF_TIME_STR
        ),
        "start_move": variation.start_move,
        "moves": [
            {
                "move_id": m.id,
                "move_num": m.move_num,
                "san": m.san,
                "annotation": m.annotation or "",
                "text": m.text or "",
                "alt": m.alt or "",
                "alt_fail": m.alt_fail or "",
                "shapes": json.loads(m.shapes or "[]"),
            }
            for m in variation.moves.all().order_by("sequence")
        ],
        "mainline": variation.mainline_moves,
    }


def get_history(variation):
    """
    Returns a list of dictionaries with quiz history for the variation.
    Each dictionary contains the datetime, level, and passed status.
    """
    history = []
    now = timezone.now()
    for quiz_result in variation.quiz_results.all().order_by("-datetime"):
        history.append(
            {
                "datetime": util.get_time_ago(now, quiz_result.datetime),
                "level": quiz_result.level,
                "passed": "✅" if quiz_result.passed else "❌",
            }
        )
    return history


def parse_san_moves(alt_moves):
    """handles various lists: 1, 2, 3 or 1,2,3 or 1 2 3"""
    return [move.strip() for move in re.split(r"[\s,]+", alt_moves) if move]


def add_alt_shapes_to_moves(moves_list):
    board = chess.Board()
    for move_dict in moves_list:
        shapes = []

        # Evaluate alts first before applying mainline move
        if alt_moves := parse_san_moves(move_dict["alt"]):
            for alt_move in alt_moves:
                try:
                    alt_move = board.parse_san(alt_move)
                    add_alt_shape(shapes, alt_move, "yellow")
                except ValueError:
                    print(f"Ignoring invalid alt move: {alt_move}")

        if alt_fail_moves := parse_san_moves(move_dict["alt_fail"]):
            for alt_fail_move in alt_fail_moves:
                try:
                    alt_fail_move = board.parse_san(alt_fail_move)
                    add_alt_shape(shapes, alt_fail_move, "red")
                except ValueError:
                    print(f"Ignoring invalid alt fail move: {alt_fail_move}")

        move = board.push_san(move_dict["san"])
        if shapes:
            add_alt_shape(shapes, move, "green")  # mainline move (quiz answer)

        move_dict["alt_shapes"] = json.dumps(shapes) if shapes else ""


def add_alt_shape(shapes, move, color):
    from_square = chess.square_name(move.from_square)
    to_square = chess.square_name(move.to_square)
    shapes.append({"orig": from_square, "dest": to_square, "brush": color})


def get_source_html(source):
    """
    {"my_course": {"course": "My White Openings", "chapter": "Caro-Kann 2K", "variation_title": "Caro-Kann 3...Bg4", "variation_id": 21090319, "note": ""}, "original_course": {"course": "Keep It Simple: 1. e4", "chapter": "1. Quickstarter Guide", "variation_title": "Quickstarter Guide #56 - Caro-Kann", "variation_id": 6611081, "note": ""}}
    """  # noqa: E501
    mine = ""
    original = ""

    if my_course := source.get("my_course"):
        mine = (
            '<p id="source-variation">Source Variation '
            '<a href="https://www.chessable.com/variation/'
            f'{my_course["variation_id"]}/" target="_blank">'
            f'{my_course["variation_id"]}</a></p>'
        )
        if note := my_course.get("note", "").strip():
            mine += f"<p>{note}</p>"

    if original_course := source.get("original_course"):
        original = (
            f'<p id="original-variation">{original_course["course"]} ➤<br/>'
            f'{original_course["chapter"]} ➤<br/>'
            f'{original_course["variation_title"]} '
            '<a href="https://www.chessable.com/variation/'
            f'{original_course["variation_id"]}/" target="_blank">'
            f'{original_course["variation_id"]}</a></p>'
        )
        if note := original_course.get("note", "").strip():
            original += f"<p>{note}</p>"

    if mine + original == "":
        return "<p>No source information available.</p>"

    return mine + original


def generate_variation_html(variation, version=1):
    html = ""
    white_to_move = True
    beginning_of_move_group = True
    pgn_moves = ""
    board = chess.Board()
    for move in variation.moves.iterator():

        if white_to_move:
            move_str = f"{move.move_num}."  # White always has dot and number
            pgn_moves += f"{move.move_num}.{move.san} "  # For PGN parsing
        else:
            move_str = f"{move.move_num}..." if beginning_of_move_group else ""
            pgn_moves += f" {move.san} "  # For PGN parsing

        white_to_move = not white_to_move

        if beginning_of_move_group:
            html += "<h3 class='variation-mainline'>"
            beginning_of_move_group = False

        move_str += f"{move.san}{move.annotation}"

        html += (
            '<span class="move mainline-move" '
            f'data-index="{move.sequence}">{move_str}</span>'
        )

        # v2 expects mainline move will already be played
        if version == 2:
            board.push_san(move.san)  # Mainline moves better be valid

        if move.text:
            beginning_of_move_group = True

            if version == 2:
                parsed_blocks = get_parsed_blocks(move, board.copy())
                subvar_html = generate_subvariations_html(move, parsed_blocks)
            else:  # v1
                moves_with_fen = extract_moves_with_fen(board.copy(), move)
                subvar_html = generate_subvariations_html_v1(move, moves_with_fen)

            html += f"</h3>{subvar_html}"

        # v1 had this at the end of the loop for some reason
        if version != 2:
            board.push_san(move.san)  # Mainline moves better be valid

    return html


def generate_subvariations_html(move, parsed_blocks):
    counter = -1  # for unique data-index
    html = ""
    previous_type = ""
    for block in parsed_blocks:
        if block.type_ == "comment":
            comment = block.display_text.replace("\n", "<br/>")
            html += f" {comment} "

        elif block.type_ == "start":
            # TODO: formatting decisions, should level 2+ subvars get newlines, etc...
            html += f"<!-- Start Block Log: {block.log} -->"
            if block.fen:
                counter += 1
                html += (
                    f'<span class="move subvar-move" data-fen="{block.fen}" '
                    f'data-index="{counter}">⏮️</span>'
                )

        elif block.type_ == "move":
            resolved = "" if block.move_parts_resolved else " ❌"

            move_text = block.move_verbose() if previous_type != "move" else block.raw

            if block.fen:
                counter += 1
                # trailing space here is consequential for wrapping
                # need to work on overall whitespace/rendering of course
                html += (
                    f'<span class="move subvar-move" data-fen="{block.fen}" '
                    f'data-index="{counter}">{move_text}{resolved}</span> '
                )
            else:
                html += f" {move_text} {resolved} "

            # how expensive is this? likely won't keep doing the
            # board but should always include the parsed block for moves
            try:
                board = chess.Board(block.fen)
            except Exception:
                board = "(no board)"
            html += f"<!-- {block}\n{board} -->"  # phew! this is useful

        previous_type = block.type_

    return (
        '<div class="subvariations" '
        f'data-mainline-index="{move.sequence}">{html}</div>'
    )


# === Parser/Renderer v1 ====================================================


def generate_subvariations_html_v1(move, move_fen_map):
    """
    {sicilian}
    (1...c5 {or french}) (1...e6 {or caro}) (1...c6?!)
    (1...e5  2.Nc3)

    move_fen_map is a list of (move, fen) pairs for each navigable subvar move

    try to match up the text/html with the FENs, perhaps we can assume it
    all lines up beautifully, if we do our work on import/validation
    """

    counter = -1
    html = ""
    remaining_text = move.text
    for san, fen in move_fen_map:
        while True:
            m = re.search(re.escape(san), remaining_text)
            if m:
                mstart = m.start()
                mend = m.end()
                html += remaining_text[:mstart]
                remaining_text = remaining_text[mend:]
                matched_move = m.group(0)
                if is_in_comment(remaining_text):
                    html += matched_move
                    continue
                else:
                    counter += 1
                    html += (
                        f'<span class="move subvar-move" data-fen="{fen}" '
                        f'data-index="{counter}">{matched_move}</span>'
                    )
                    break
            else:
                break

    html += f"{remaining_text.strip()}"
    if "<br/>" not in html:
        html = html.replace("\n", "<br/>")

    # much more to do here of course
    html = html.replace("<fenseq", " ⏮️ <fenseq")

    return (
        '<div class="subvariations" '
        f'data-mainline-index="{move.sequence}">{html}</div>'
    )


def extract_moves_with_fen(board, move):
    pgn_text = move.text

    # Step 1: Remove text inside comment {} brackets
    cleaned_pgn = re.sub(r"\{.*?\}", "", pgn_text)

    # Step 2: Find all move sequences inside parentheses ()
    move_blocks = re.findall(r"\((.*?)\)", cleaned_pgn)

    # Step 4: Process each move sequence
    move_fen_map = []  # Store (move_list, corresponding FEN)

    for block in move_blocks:
        moves = block.strip().split()  # Split into individual moves
        board_copy = board.copy()  # Copy board state before applying moves

        fen_sequence = []
        for move_ in moves:
            try:
                # extract just the valid san part for updating board
                move_regex = r"^(\d*\.*)(O-O-O|O-O|[A-Za-z0-9]+)"
                m = re.match(move_regex, move_)
                if not m:
                    # e.g. a hanging exclam, Nf6 !
                    print(
                        "Bailing out on invalid subvar move non-match "
                        f"({move.variation.id}, {move.move_verbose}): {move_}"
                    )
                    break
                move_san = m.group(2)
                # print(f"move: {move}")
                board_copy.push_san(move_san)  # Apply move in SAN format
                fen_sequence.append((move_, board_copy.fen()))  # Store move + FEN
            except ValueError:
                print(
                    "Bailing out on invalid subvar move ValueError "
                    f"({move.variation.id}, {move.move_verbose}): {move_}"
                )
                break  # Skip broken variations

        if fen_sequence:
            move_fen_map.append(fen_sequence)

    # We might not need this structured list and can just
    # build it flat, but for now we'll flatten at end

    flattened = flatten_move_fen_map(move_fen_map)
    return flattened


def is_in_comment(upcoming_text):
    """
    Determines if a given index in a string is within a PGN comment
    {inside brackets}. We might be in the middle of a comment. We're
    assuming PGN comments can't be nested, or that we won't allow them
    to be.

    Args:
        upcoming_text (str): The remaining text to be processed.

    Returns:
        bool: True if the index is within a bracketed section, False otherwise.
    """

    next_open = upcoming_text.find("{")  # finds the first open bracket
    next_close = upcoming_text.find("}")  # and so on

    if next_open + next_close == -2:  # No brackets found
        return False
    elif next_close == -1:
        # No closing bracket found (there really should always be, if we
        # can assume properly formatted pgn! we really should clean things
        # up on import to make sure we do...)
        return False
    elif next_open == -1:  # No opening bracket found
        return True

    return next_close < next_open  # True if closing bracket comes first


def flatten_move_fen_map(nested_list):
    """Recursively flattens a nested list of move-FEN pairs."""
    flat_list = []
    for item in nested_list:
        if isinstance(item, list):
            flat_list.extend(flatten_move_fen_map(item))  # Recursively flatten
        else:
            flat_list.append(item)  # Add move-FEN pair
    return flat_list
