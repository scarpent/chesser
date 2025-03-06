import re

import chess
import chess.pgn

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


def serialize_variation(variation, generate_html=False):
    color = variation.chapter.course.color

    html = generate_variation_html(variation) if generate_html else None

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
        "mainline": variation.mainline_moves,
        "source_html": get_source_html(variation.source),
        "html": html,
    }
    # TODO: May eventually have rendered "final move text" for after the quiz. For now
    # we're showing plain text from moves, but that could have FENs or other encoding.

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
                "san": move.san,
                "annotation": move.annotation,
                "move_verbose": move.move_verbose,
                "text": move.text,
                "alt": move.alt or "",
                "alt_fail": move.alt_fail or "",
                "shapes": move.shapes or "",
            }
        )
    variation_data["moves"] = moves
    variation_data["annotations"] = temp_annotations

    return variation_data


def get_source_html(source):
    """
    {"my_course": {"course": "My White Openings", "chapter": "Caro-Kann 2K", "variation_title": "Caro-Kann 3...Bg4", "variation_id": 21090319, "note": ""}, "original_course": {"course": "Keep It Simple: 1. e4", "chapter": "1. Quickstarter Guide", "variation_title": "Quickstarter Guide #56 - Caro-Kann", "variation_id": 6611081, "note": ""}}
    """  # noqa: E501
    mine = ""
    original = ""

    if my_course := source.get("my_course"):
        mine = (
            '<p><a href="https://www.chessable.com/variation/'
            f'{my_course["variation_id"]}/" target="_blank">'
            "Source Variation</a></p>"
        )
        if note := my_course.get("note"):
            mine += f"<p>{note}</p>"

    if original_course := source.get("original_course"):
        original = (
            f'<p>{original_course["course"]} ➤<br/>{original_course["chapter"]} ➤<br/>'
            '<a href="https://www.chessable.com/variation/'
            f'{original_course["variation_id"]}/" target="_blank">'
            f'{original_course["variation_title"]}</a></p>'
        )
        if note := original_course.get("note"):
            original += f"<p>{note}</p>"

    if mine + original == "":
        return "<p>No source information available.</p>"

    return mine + original


def generate_variation_html(variation):
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
            html += "<h3 class='variation-mainline'>\n"
            beginning_of_move_group = False

        move_str += f"{move.san}{move.annotation}"

        html += (
            '<span class="move mainline-move" '
            f'data-index="{move.sequence}">{move_str}</span>\n'
        )

        if move.text:
            beginning_of_move_group = True
            moves_with_fen = extract_moves_with_fen(board.copy(), move.text)
            from pprint import pprint

            pprint(moves_with_fen)

            subvar_html = generate_subvariations_html(move, moves_with_fen)
            html += f"</h3>\n{subvar_html}\n"

        board.push_san(move.san)  # Mainline moves better be valid

    html = htmlize_chessable_tags(html)

    return html


def htmlize_chessable_tags(html):
    html = html.replace("@@SANStart@@", "<b>").replace("@@SANEnd@@", "</b>")
    html = html.replace("@@ul@@", "</p><ul>").replace("@@/ul@@", "</ul><p>")
    html = html.replace("@@li@@", "<li>").replace("@@/li@@", "</li>")
    return html


def generate_subvariations_html(move, move_fen_map):
    """
    {sicilian}
    (1...c5 {or french}) (1...e6 {or caro}) (1...c6?!)
    (1...e5  2.Nc3)

    move_fen_map is a list of (move, fen) pairs for each navigable subvar move

    try to match up the text/html with the FENs, perhaps we can assume it
    all lines up beautifully, if we do our work on import/validation
    """

    counter = -1
    html = "<p>\n"
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
                        f'data-index="{counter}">{matched_move}</span>\n'
                    )
                    break
            else:
                break

    html += f"{remaining_text.strip()}"

    return (
        '<div class="subvariations" '
        f'data-mainline-index="{move.sequence}">\n{html}\n</p>\n</div>'
    )


def extract_moves_with_fen(board, pgn_text):
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
        for move in moves:
            try:
                # extract just the valid san part for updating board
                move_regex = r"^(\d*\.*)(O-O-O|O-O|[A-Za-z0-9]+)"
                m = re.match(move_regex, move)
                if not m:
                    # e.g. a hanging exclam, Nf6 !
                    print(f"Skipping invalid move: {move}")
                    break
                move_san = m.group(2)
                # print(f"move: {move}")
                board_copy.push_san(move_san)  # Apply move in SAN format
                fen_sequence.append((move, board_copy.fen()))  # Store move + FEN
            except ValueError:
                print(f"Skipping invalid move: {move}")
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


variation_html = """
<h3 class="variation-mainline">
    <span class="move mainline-move" data-index="0">1.e4!</span>
    <span class="move mainline-move" data-index="1">Nc6</span>
</h3>
<p>
    The Nimzovich Defence. It is not that bad if you use it just as a
    transpositional tool to reach 1 e4 e5 positions - the independent lines,
    however, are not that reliable for Black, or just downright bad.
</p>
<h3 class="variation-mainline">
    <span class="move mainline-move" data-index="2">2.Nf3</span>
</h3>
<div class="subvariations" data-mainline-index="2">
    <p>
    Instead, 2.d4 is good as well. But 2.Nf3 is logical and easier to handle.
    </p>
    <p>
    How might that work? Well, let's see:
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/pppppppp/2n5/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq - 0 2"
        data-index="0"
        >2.d4</span
    >
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/pppp1ppp/2n5/4p3/3PP3/8/PPP2PPP/RNBQKBNR w KQkq - 0 3"
        data-index="1"
        >e5</span
    >
    We could transpose to the Scotch Game here, but engine says to pick up the
    d-pawn. Masters prefer dxe5 and plebs d5. (Engine likes both, but d5
    slightly better.)
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/pppp1ppp/2n5/3Pp3/4P3/8/PPP2PPP/RNBQKBNR b KQkq - 0 3"
        data-index="2"
        >3.d5</span
    >
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/ppppnppp/8/3Pp3/4P3/8/PPP2PPP/RNBQKBNR w KQkq - 1 4"
        data-index="3"
        >Nce7</span
    >
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/ppppnppp/8/3Pp3/4P3/5N2/PPP2PPP/RNBQKB1R b KQkq - 2 4"
        data-index="4"
        >4.Nf3</span
    >
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/pppp1ppp/6n1/3Pp3/4P3/5N2/PPP2PPP/RNBQKB1R w KQkq - 3 5"
        data-index="5"
        >Ng6</span
    >
    White is better and scores well with h4. With other moves, Black is doing
    better in pleb games, and it's no surprise because these positions seem hard
    to play in practice.
    </p>
    <p>
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/pppppppp/2n5/8/4P3/2N5/PPPP1PPP/R1BQKBNR b KQkq - 2 2"
        data-index="6"
        >2.Nc3</span
    >
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/pppp1ppp/2n5/4p3/4P3/2N5/PPPP1PPP/R1BQKBNR w KQkq - 0 3"
        data-index="7"
        >e5</span
    >
    Did someone order a Vienna?
    </p>
</div>
<h3 class="variation-mainline">
    <span class="move mainline-move" data-index="3">2...d5</span>
</h3>
<div class="subvariations" data-mainline-index="3">
    <p>Scandi style play - it is very questionable though.</p>
    <p>
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/ppp1pppp/2np4/8/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 3"
        data-index="0"
        >2...d6</span
    >
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/ppp1pppp/2np4/8/3PP3/5N2/PPP2PPP/RNBQKB1R b KQkq - 0 3"
        data-index="1"
        >3.d4</span
    >
    <span
        class="move subvar-move"
        data-fen="r2qkbnr/ppp1pppp/2np4/8/3PP1b1/5N2/PPP2PPP/RNBQKB1R w KQkq - 1 4"
        data-index="2"
        >Bg4?</span
    >
    This pin is somewhat premature.
    <span
        class="move subvar-move"
        data-fen="r2qkbnr/ppp1pppp/2np4/3P4/4P1b1/5N2/PPP2PPP/RNBQKB1R b KQkq - 0 4"
        data-index="3"
        >4.d5!</span
    >
    Just gaining time. The most natural reply happens to fail spectacularly,
    which is a nice added bonus.
    <span
        class="move subvar-move"
        data-fen="r2qkbnr/ppp1pppp/3p4/3Pn3/4P1b1/5N2/PPP2PPP/RNBQKB1R w KQkq - 1 5"
        data-index="4"
        >4...Ne5</span
    >
    <span
        class="move subvar-move"
        data-fen="r2qkbnr/ppp1pppp/3p4/3PN3/4P1b1/8/PPP2PPP/RNBQKB1R b KQkq - 0 5"
        data-index="5"
        >5.Nxe5!</span
    >
    Oh no, my queen!
    </p>
    <p>
    The following complications are not that simple to learn, but White is close
    to winning and you get to bash out some cool moves!
    </p>
</div>
<h3 class="variation-mainline">
    <span class="move mainline-move" data-index="4">3.exd5</span>
    <span class="move mainline-move" data-index="5">Qxd6</span>
    <span class="move mainline-move" data-index="6">4.Nc3</span>
    <span class="move mainline-move" data-index="7">Qh5?</span>
    <span class="move mainline-move" data-index="8">5.Nb5!</span>
</h3>
<p>
    Quite an embarrassing moment for Black - now ...Kd8 is the only move and it is
    not pretty.
</p>
</div>
"""
