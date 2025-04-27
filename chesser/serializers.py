import json
import re
from dataclasses import dataclass, field
from typing import Literal, Optional

import chess
import chess.pgn
from django.utils import timezone

from chesser import util
from chesser.models import Move

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
    # TODO: export quiz history, too? perhaps optionally...
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


# === Parser/Renderer v1 ====================================================


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

        if move.text:
            beginning_of_move_group = True

            if version == 2:
                parsed_blocks = get_parsed_blocks(move, board.copy())
                # subvar_html = render_parsed_blocks(parsed_blocks, board.copy())

                blocks = [
                    f"<p style='padding: 4px; border: 1px solid #ccc'>{block}</p>"
                    for block in parsed_blocks
                ]
                subvar_html = f"<p>{move.text}</p>{'\n'.join(blocks)}"

            else:  # v1
                moves_with_fen = extract_moves_with_fen(board.copy(), move)
                subvar_html = generate_subvariations_html(move, moves_with_fen)

            html += f"</h3>{subvar_html}"

        board.push_san(move.san)  # Mainline moves better be valid

    html = htmlize_chessable_tags(html)

    return html


# TODO: this goes away after cleanup is all done and import also cleans
def htmlize_chessable_tags(html):
    html = html.replace("@@SANStart@@", "<b>").replace("@@SANEnd@@", "</b>")
    html = html.replace("@@ul@@", "<ul>").replace("@@/ul@@", "</ul>")
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
        # TODO: don't <br/> by block level things like <ul>
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


# === Parser v2 =============================================================


@dataclass
class Chunk:
    type_: Literal["comment", "move", "fenseq", "subvar"]
    data: str


@dataclass
class ParsedBlock:
    # chunk types: "comment", "subvar", "fenseq", "move"
    type_: Literal["comment", "start", "end", "move"]
    raw: str = ""
    errors: list[str] = field(default_factory=list)
    display_text: str = ""  # for normalized comments, moves
    move_num: Optional[int] = None
    dots: str = ""  # . or ... or nothing
    san: str = ""  # basic SAN used to advance board, regardless of move #s
    fen: str = ""  # fen representing the state *before* this move
    link_fen: bool = False  # render ⏮️ as link fen (for former fenseq / @@StartFEN@@)
    depth: int = 0  # for subvar depth tracking


@dataclass
class RenderableBlock:
    type_: Literal["comment", "move"]
    html: str
    raw: str
    errors: list[str] = field(default_factory=list)


def get_simple_move_parsed_block(literal_move: str, depth: int) -> ParsedBlock:
    """
    Breaks a literal move string into its core parts:
    move number, dots, and SAN.

    At this stage, the input has already been cleaned and tokenized —
    so we expect reasonably structured data, but we aren't verifying
    full chess legality yet.

    This function:
    - Extracts optional move number (e.g. "1" from "1.e4", "1. e4" "1...e5")
    - Extracts dots following the number ("." or "..." or "........" & so on)
    - Extracts the SAN (Standard Algebraic Notation) portion
    - Strips any leading/trailing whitespace from the SAN

    We do not validate the move content here:
    - Malformed SANs, impossible moves, etc. are allowed
    - Path validation happens later during move resolution

    The goal is to be strict in how we parse and clean fields,
    but flexible in accepting whatever we have at this point.
    We probably have mostly clean data at this point and errors
    won't be catastrophic later. God knows Chessable has enough
    broken subvariations themselves.
    """
    move_parts = re.search(r"^(\d*)(\.*)(.*)", literal_move)
    move_num = int(move_parts.group(1)) if move_parts.group(1) else None
    dots = move_parts.group(2)
    san = move_parts.group(3).strip()
    return ParsedBlock(
        type_="move",
        raw=literal_move,
        move_num=move_num,
        dots=dots,
        san=san,
        depth=depth,
    )


def get_parsed_blocks(move: Move, board: chess.Board) -> list[ParsedBlock]:
    chunks = extract_ordered_chunks(move.text)
    parsed_blocks = get_parsed_blocks_first_pass(chunks)
    resolved_blocks = resolve_moves(parsed_blocks, move, board)
    return resolved_blocks


def resolve_moves(
    blocks: list[ParsedBlock], move: Move, board: chess.Board
) -> list[ParsedBlock]:
    """
    Given initial parsed blocks and a starting board,
    attempts to resolve moves, normalize structure,
    and produce a cleaned list of blocks, dropping
    redundant moves as needed.
    """
    resolved_blocks = []
    # board_stack = [board.copy()]
    # maybe also track move sequence to handle redundancies

    for block in blocks:
        # handle comments and fenseq markers cleanly
        # for moves: validate SAN, drop duplicates
        # resolved_blocks.append(...)

        resolved_blocks.append(block)  # stub for now, just pass the data back

    return resolved_blocks


def get_parsed_blocks_first_pass(chunks: list[Chunk]) -> list[ParsedBlock]:
    parsed_blocks = []
    i = 0
    depth = 0
    move_prefix = re.compile(r"^\d+\.+$")  # e.g. "1." or "2..."

    while i < len(chunks):
        chunk = chunks[i]
        print(f"🔍 Parsing chunk: {chunk.type_} ➤ {chunk.data.strip()[:40]}...")

        # ➡️ Every branch must advance `i`
        # (exception for two move handler that can fall through to single move)

        if chunk.type_ == "subvar":
            if chunk.data.startswith("START"):
                depth += 1
                this_subvar_depth = depth
            else:  # starts with END
                this_subvar_depth = depth
                depth = max(depth - 1, 0)
            parsed_blocks.append(
                ParsedBlock(
                    type_="start" if chunk.data.startswith("START") else "end",
                    depth=this_subvar_depth,
                )
            )
            i += 1
            continue

        # Reassemble moves with spaces that were split up in extractor
        # e.g. "1. e4" ➤ ["1.", "e4"] ➤ "1.e4" ➤ normalized!
        if (
            chunk.type_ == "move"
            and i + 1 < len(chunks)
            and chunks[i + 1].type_ == "move"
        ):
            # move blocks are the only ones that we can count on having been stripped
            next_data = chunks[i + 1].data

            if move_prefix.match(chunk.data) and not move_prefix.match(next_data):
                parsed_blocks.append(
                    get_simple_move_parsed_block(chunk.data + next_data, depth)
                )
                i += 2
                continue
            # else fall through to single move block handler

        if chunk.type_ == "move":  # a single move
            parsed_blocks.append(get_simple_move_parsed_block(chunk.data, depth))
            i += 1
            continue

        elif chunk.type_ == "comment":
            raw = ""
            # combine consecutive comments into one
            while i < len(chunks) and chunks[i].type_ == "comment":
                raw += chunks[i].data.strip("{}")
                i += 1

            parsed_blocks.append(get_cleaned_comment_parsed_block(raw, depth))
            continue

        elif chunk.type_ == "fenseq":  # turn this into a sequence of moves
            parsed_blocks.extend(parse_fenseq_chunk(chunk.data))
            i += 1
            continue

        else:
            raise ValueError(
                f"Unknown chunk type: {chunk.type_} ➤ {chunk.data.strip()[:40]}"
            )

    return parsed_blocks


def parse_fenseq_chunk(raw: str) -> list[ParsedBlock]:
    """
    e.g.
    <fenseq data-fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1">
        1.d4 d5 2.e3
    </fenseq>

    turn this intermediate representation into a mostly typical move block list
    * we expect/allow no comments or subvariations; it's meant to be simple
    * we should mostly get "condensed" moves, e.g. 1.e4, but we'll handle 1. e4

    we could make data-fen be optional and use game starting fen if omitted...
    """
    match = re.search(
        r"""<fenseq\s+[^>]*data-fen=["']([^"']+)["'][^>]*>(.*?)</fenseq>""",
        raw,
        re.DOTALL,
    )
    # "fenseq" type blocks should always match or they'd already be "comment"
    assert match, f"Invalid fenseq block: {raw}"

    fen, move_text = match.groups()
    # remove spaces after move numbers
    move_text = re.sub(r"\b(\d+\.+)\s*", r"\1", move_text).strip()

    assert move_text, f"Empty move text in fenseq block: {raw}"

    DEPTH = 1  # fenseq blocks are always depth 1
    blocks = [ParsedBlock("start", depth=DEPTH, fen=fen)]
    for move in move_text.split():
        blocks.append(get_simple_move_parsed_block(move, DEPTH))
    blocks.append(ParsedBlock("end", depth=DEPTH))

    return blocks


def get_cleaned_comment_parsed_block(raw: str, depth: int) -> ParsedBlock:
    # we don't expect/want <br/> tags in move.text but they're easy to handle
    cleaned = re.sub(r"<br\s*/?>", "\n", raw)
    # remove whitespace around newlines
    cleaned = re.sub(r"[ \t\r\f\v]*\n[ \t\r\f\v]*", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)  # collapse newlines
    cleaned = re.sub(r" +", " ", cleaned)  # collapse spaces
    return ParsedBlock(
        type_="comment",
        raw=raw,
        display_text=cleaned,
        depth=depth,
    )


def extract_ordered_chunks(text: str) -> list[Chunk]:
    chunks = []
    mode = "neutral"  # can be: neutral, comment, subvar
    i = 0
    paren_depth = 0
    token_start = None  # move or comment start, tracked through iterations

    def flush_token():
        nonlocal token_start

        if token_start is None:
            return
        token = text[token_start:i]
        stripped = token.strip()
        if mode == "neutral":
            # we're closing out a comment; we'll first nag if needed
            end_char = "" if stripped and stripped[-1] == "}" else "}"
            if not end_char:
                print("⚠️  Found closing comment brace while in neutral mode")
            chunks.append(Chunk("comment", "{" + token + end_char))
        elif mode == "subvar" and stripped:  # pragma: no branch
            # one of the few (only) places we strip in this pass
            chunks.append(Chunk("move", stripped))
        else:
            raise ValueError(  # pragma: no cover
                f"Unexpected mode '{mode}' in flush_token at index {i}: {token}"
            )
        token_start = None

    while i < len(text):
        c = text[i]

        # Handle <fenseq ... </fenseq> as atomic
        if mode == "neutral" and text[i:].startswith("<fenseq"):
            flush_token()
            # we'll naively check for the end tag and accept irregular results
            # for unlikey html soup like <fenseq blah <fenseq>...</fenseq>
            end_tag = "</fenseq>"
            end = text.find(end_tag, i)
            if end != -1:
                end += len(end_tag)
                chunks.append(Chunk("fenseq", text[i:end]))
                i = end
                token_start = None
            else:
                print(f"⚠️  Unclosed <fenseq> (making a comment): {text[i:]}")
                token_start = i
                i = len(text)
                mode = "neutral"
                flush_token()
            continue

        # Comment start
        elif c == "{" and mode in ("neutral", "subvar"):
            flush_token()
            token_start = i
            mode = "comment"

        # Comment end
        elif c == "}" and mode == "comment":
            chunks.append(Chunk("comment", text[token_start : i + 1]))  # noqa: E203
            token_start = None
            mode = "neutral" if paren_depth < 1 else "subvar"

            if (
                mode == "subvar"
                and paren_depth == 1
                and text[i + 1 :].lstrip().startswith("<fenseq")  # noqa: E203
            ):
                print(f"✅  Fixing known unbalanced parens: {text[i:][:60]}")
                # no need to flush token; we're following the already appended comment
                chunks.append(Chunk("subvar", "END 1"))
                paren_depth = 0
                mode = "neutral"

        # Subvar start
        elif c == "(" and mode == "neutral":
            flush_token()
            paren_depth += 1
            # paren depth is added to the chunk value for visibility only;
            # a later step will have its own depth tracking and split into
            # subvar start/end types
            chunks.append(Chunk("subvar", f"START {paren_depth}"))
            mode = "subvar"

        # Subvar end
        elif c == ")" and mode == "subvar":
            flush_token()
            chunks.append(Chunk("subvar", f"END {paren_depth}"))
            paren_depth -= 1
            if paren_depth == 0:
                mode = "neutral"

        # Nested subvar
        elif c == "(" and mode == "subvar":
            paren_depth += 1
            chunks.append(Chunk("subvar", f"START {paren_depth}"))

        # Implied comment when we encounter a non-defined structure in neutral zone
        elif mode == "neutral":
            if token_start is None:
                token_start = i

        elif mode == "subvar":
            if c.isspace():  # whitespace ends a move token; for now we'll
                # tokenize 1.e4 and 1. e4 separately and figure out later
                flush_token()
            elif token_start is None:
                token_start = i

        elif mode == "comment":  # pragma: no branch
            # have yet to see these in the wild - using assertions until
            # we do, at which time we'll handle them one way or another
            assert text[i] != "{", "Unexpected opening brace in comment chunk"
            assert not text[i:].startswith(
                "<fenseq"
            ), "Unexpected <fenseq> tag in comment chunk"
            # parens are fine, though! we expect and encourage them (❤️)

        elif mode != "comment":  # pragma: no cover
            raise ValueError(  # impossible?
                f"Unexpected char '{c}' in mode '{mode}' at index {i}: {text[:30]}"
            )

        assert (  # impossible?
            paren_depth >= 0
        ), f"Unbalanced parens at index {i}, depth {paren_depth}: {text[:30]}"

        i += 1

    # Handle trailing move or comment
    if token_start is not None:
        if mode == "comment":
            token = text[token_start:i]
            end_char = "" if token.strip()[-1] == "}" else "}"
            if end_char:  # pragma: no branch
                # this might be hard to get to as well!
                print("⚠️  Didn't find trailing closing comment brace (adding)")
            chunks.append(Chunk("comment", token + end_char))
        else:
            flush_token()

    if paren_depth > 0:
        print(f"❌  Unbalanced parens, depth {paren_depth}: {text[:30]}")

    return chunks


def extract_ordered_chunks_old(text: str) -> list[tuple[str, str]]:
    """
    The first big pass, identifying the main types of blocks in the text.
    We don't care about the content of the blocks yet, just their types.

    Character by character parser is fast and catching a number of rare
    cases so we don't overly pollute the general parser ahead. If it gets
    any more complex or we want to extend it, it really needs to be broken
    up into 3 sub-extractors, one for each type of block. But for now it
    is readable like a story, let's say.

    1) Suvariations, in parens, e.g. (1.e4! e5 {an open game} 2.Nf3)
    2) Fenseq, e.g. <fenseq data-fen="">...</fenseq>
    3) Comments, explicitly in {braces} or implied outside of (parens)
    4) Whitespace will be glommed onto neighboring elements; no stripping!
    """
    blocks = []
    i = 0
    length = len(text)
    start_before_whitespace = -1

    while i < length:
        if text[i].isspace():
            if start_before_whitespace == -1:
                start_before_whitespace = i
            i += 1
            continue

        start = start_before_whitespace if start_before_whitespace >= 0 else i
        start_before_whitespace = -1

        # --- SUBVAR --------------------------------------------------------
        if text[i] == "(":
            depth = 1
            in_comment = False
            i += 1
            while i < length and depth > 0:
                c = text[i]

                # ignore parens inside {(comments)}
                if c == "{" and not in_comment:
                    in_comment = True
                elif c == "}" and in_comment:
                    in_comment = False
                elif not in_comment:
                    if c == "(":
                        depth += 1
                    elif c == ")":
                        depth -= 1

                i += 1

            subvar = text[start:i]
            # there's not that many of these and most of them seem fenseq-related;
            # spent time trying to fix on the cleaner side, and got one case, but
            # still something missing; But remaining is a messy case, and just
            # the one, so we'll fix here because it's a lot easier to see here.
            if depth == 1 and re.search(r"}\s*<fenseq", subvar):
                print(f"✅  Fixing known unbalanced parens: {subvar}")
                subvar = subvar.replace("<fenseq", ")<fenseq")
            elif depth != 0:
                print(f"⚠️  Unbalanced parens in subvar: {subvar}")

            blocks.append(("subvar", subvar))
            continue

        # --- FENSEQ --------------------------------------------------------
        elif i < length - 1 and text[i:].startswith("<fenseq"):
            end_tag = "</fenseq>"
            end = text.find(end_tag, i)
            if end != -1:
                end += len(end_tag)
                blocks.append(("fenseq", text[start:end]))
                i = end
                continue
            else:
                # fallback: treat as comment if no close tag
                blocks.append(("comment", text[i:]))
                print(f"⚠️  fenseq> tag not closed in text: {text[i:]}")
                break

        # --- COMMENT -------------------------------------------------------
        else:
            # comments are mostly unstructured but there are *some* cases
            # of embedded clickable subvars, but we'll ignore those for now;
            # comments may or may not be enclosed in braces
            implied_comment = True
            if text[i] == "{":
                implied_comment = False
                i += 1

            while i < length:
                if implied_comment:
                    if text[i:].startswith("<fenseq"):
                        break
                    elif text[i] == "(":  # subvar
                        break
                    elif text[i] == "{":
                        # explicit comment following implicit; handle as separate chunks
                        break

                elif not implied_comment:
                    # these might be temporary, just wanting to see if we get them, but
                    # maybe we'll be more forgiving here and catch in later validation
                    assert text[i] != "{", "Unexpected opening brace in comment block"
                    assert not text[i:].startswith(
                        "<fenseq"
                    ), "Unexpected <fenseq> tag in comment block"
                    # parens are fine, though! we expect and encourage them ❤️

                i += 1
                if text[i - 1] == "}":
                    if implied_comment:
                        print('⚠️  Found closing brace while in "implied" comment')
                    break

            comment_chunk = text[start:i]
            comment = comment_chunk.strip()  # temporarily strip for checks

            if implied_comment:
                comment_chunk = "{" + comment_chunk  # explicit is better than implicit
            elif comment[-1] != "}":
                print('⚠️  Missing closing brace in "explicit" comment block')

            # final safety: ensure closing brace regardless of implied/explicit
            if comment and comment[-1] != "}":
                comment_chunk += "}"

            # we're not stripping any actual data; that'll come later
            blocks.append(("comment", comment_chunk))

    if start_before_whitespace >= 0:  # leftover whitespace at end, handle as comment
        blocks.append(("comment", text[start_before_whitespace:]))

    return blocks
