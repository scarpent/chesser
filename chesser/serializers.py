import json
import re
from dataclasses import dataclass

import chess
from django.utils import timezone

from chesser import util
from chesser.models import Move
from chesser.move_resolver import ParsedBlock, get_parsed_blocks

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

BLOCK_TAG_RE = re.compile(
    rf"</?({'|'.join(util.BLOCK_TAGS)})\b[^>]*>",
    re.IGNORECASE,
)


def serialize_variation(variation, all_data=False):
    color = variation.chapter.course.color

    now = timezone.now()
    time_since_last_review = util.get_time_ago(
        now, variation.get_latest_quiz_result_datetime()
    )
    time_until_next_review = util.format_time_until(now, variation.next_review)

    source_html = get_source_html(variation.source) if all_data else None
    html = generate_variation_html(variation) if all_data else None
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
                    print(
                        f"Ignoring invalid alt move: {alt_move} "
                        f"(#{move_dict['move_id']} {move_dict['move_verbose']})"
                    )

        if alt_fail_moves := parse_san_moves(move_dict["alt_fail"]):
            for alt_fail_move in alt_fail_moves:
                try:
                    alt_fail_move = board.parse_san(alt_fail_move)
                    add_alt_shape(shapes, alt_fail_move, "red")
                except ValueError:
                    print(
                        f"Ignoring invalid alt fail move: {alt_fail_move} "
                        f"(#{move_dict['move_id']} {move_dict['move_verbose']})"
                    )

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
            html += "<h3 class='variation-mainline'>"
            beginning_of_move_group = False

        move_str += f"{move.san}{move.annotation}"

        html += (
            '<span class="move mainline-move" '
            f'data-index="{move.sequence}">{move_str}</span>'
        )

        board.push_san(move.san)  # Mainline moves better be valid

        if move.text:
            beginning_of_move_group = True
            parsed_blocks = get_parsed_blocks(move, board.copy())
            subvar_html = generate_subvariations_html(move, parsed_blocks)

            html += f"</h3>{subvar_html}"

    return html


def get_final_move_simple_subvariations_html(variation):
    html = ""
    previous_type = ""
    move = None

    # advance board to the final move
    board = chess.Board()
    for move in variation.moves.iterator():
        # Mainline moves better be valid
        # (but maybe should still fall back...)
        board.push_san(move.san)

    if not move:
        return html

    parsed_blocks = get_parsed_blocks(move, board.copy())

    for block in parsed_blocks:
        if block.type_ == "comment":
            comment = block.display_text
            html += f" {comment} "
        elif block.type_ == "move":
            move_text = block.move_verbose if previous_type != "move" else block.raw
            html += f" {move_text} "
        previous_type = block.type_

    if html:
        html = f"<h3>{move.move_verbose}</h3>\n{html}"

    return html


@dataclass
class RendererState:
    counter: int = -1  # unique data-index
    in_paragraph: bool = False
    previous_type: str = ""
    debug: bool = False
    move: object = Move


def render_comment_block(block: ParsedBlock, state: RendererState, **kwargs) -> str:
    """
    Comments may have text but might also only have formatting
    like newlines which we preserve depending on the context.
    """
    chunks = chunk_html_for_wrapping(block.display_text)
    html = render_chunks_with_br(chunks, state)

    if state.debug:
        print(f"➡️ |\n{block.display_text}\n|⬅️")
        print(f"\n🧊 Chunks:\n{chunks}")
        print(f"\n💦 Rendered:\n{html}|in para = {state.in_paragraph}\n")

    return html


def render_start_block(block: ParsedBlock, state: RendererState, **kwargs) -> str:
    html = f"<!-- Start Block Log: {block.log} -->"

    if block.fen:
        if not state.in_paragraph:
            html += "<p>"
            state.in_paragraph = True
        state.counter += 1
        html += (
            f'<span class="move subvar-move" data-fen="{block.fen}" '
            f'data-index="{state.counter}">⏮️</span>'
        )

    elif block.depth > 1:
        # use depth and emoji for debug/visualization: {block.depth}🌻
        para = f'<p class="subvar-indent depth-{block.depth}"> '
        if not state.in_paragraph:  # probably already in a paragraph at depth 2
            html += para
            state.in_paragraph = True
        else:
            # TODO: look out for <p></p>? (not seeing any big gaps so far)
            html += f"</p>{para}"

    return html


def render_end_block(
    block: ParsedBlock, state: RendererState, *, next_block_type=None
) -> str:
    """let's try organizing more deeply nested subvariations"""
    html = ""
    if block.depth > 1:
        # Check next block context (avoids leaking p tags if subvar is ending)
        if next_block_type in ["move", "comment"]:
            if not state.in_paragraph:  # probably already in a paragraph at depth 2
                html += "<p>"
                state.in_paragraph = True
            # depth/emoji for debug/visualization: 🪦{block.depth}
            html += f'</p><p class="subvar-indent depth-{block.depth - 1}">'

    return html


def render_move_block(block: ParsedBlock, state: RendererState, **kwargs) -> str:
    html = ""
    resolved = "" if block.move_parts_resolved else " ❌"

    # TODO instead of block.raw, should use resolved move if we have it,
    # and decide it if should be "fully qualified" or not. Resolved move
    # will be good for showing what it actually became, if off by one, say,
    # but for now it helps seeing where things are off if we use original raw
    move_text = block.move_verbose if state.previous_type != "move" else block.raw

    if not state.in_paragraph:
        html += "<p>"
        state.in_paragraph = True

    if block.fen:
        state.counter += 1
        # trailing space here is consequential for wrapping and also relied
        # on to space things out appropriately (slighly usurping the rule
        # of render_chunks_with_br in that realm)
        html += (
            f'<span class="move subvar-move" data-fen="{block.fen}" '
            f'data-index="{state.counter}">{move_text}{resolved}</span> '
        )
    else:
        html += f" {move_text} {resolved} "

    # is this expensive enough to care about? likely won't keep doing
    # the board but should always include the parsed block for moves
    try:
        board = chess.Board(block.fen)
    except Exception:
        board = "(no board)"

    html += f"<!-- {block}\n{board} -->"  # phew! this is useful

    return html


def print_block_type_info(block: ParsedBlock):
    if block.type_ == "comment":
        text = f"➡️ |\n{block.display_text}\n|⬅️"
    elif block.type_ == "move":
        text = f"{block.raw} | {block.move_verbose}"
    else:
        text = block.depth
    print(f"block type: {block.type_} {text}")


def get_next_type(blocks: list, i: int) -> str | None:
    try:
        return blocks[i + 1].type_
    except IndexError:
        return None


BLOCK_RENDERERS = {
    "comment": render_comment_block,
    "start": render_start_block,
    "end": render_end_block,
    "move": render_move_block,
}


def generate_subvariations_html(
    move: Move,
    parsed_blocks: list[ParsedBlock],
    debug: bool = False,
) -> str:
    """
    Our train of blocks cars has been filled with a precious
    cargo of pgn slurry, which we'll finally pour into HTML.
    """
    state = RendererState(move=move, debug=debug)
    html = ""
    for i, block in enumerate(parsed_blocks):
        if debug:
            print_block_type_info(block)

        renderizer = BLOCK_RENDERERS.get(block.type_)
        assert renderizer, f"Unknown block type: {block.type_}"
        html += renderizer(
            block, state, next_block_type=get_next_type(parsed_blocks, i)
        )
        state.previous_type = block.type_

    if state.in_paragraph:
        html += "</p>"  # and no need to unset state here at the end 🪦

    return (
        '<div class="subvariations" '
        f'data-mainline-index="{move.sequence}">{html}</div>'
    )


def is_block_element(chunk: str) -> bool:
    tag_match = re.match(r"<(/)?(\w+)", chunk.strip())
    if not tag_match:
        return False
    tag = tag_match.group(2).lower()
    return tag in util.BLOCK_TAGS


def render_chunks_with_br(chunks: list[str], state: RendererState) -> str:
    """
    I think we should expect alternating block and non-block chunks?
    """
    output = []

    for i, chunk in enumerate(chunks):
        if i + 1 == len(chunks):
            is_last_chunk = True
            next_is_block = False
        else:
            next_is_block = is_block_element(chunks[i + 1])
            is_last_chunk = False

        if is_block_element(chunk):
            if state.in_paragraph:
                output.append("</p>")
                state.in_paragraph = False
            output.append(chunk)
        else:
            if not state.in_paragraph:
                output.append("<p>")
                state.in_paragraph = True
                chunk = chunk.lstrip()
            if next_is_block:
                chunk = chunk.rstrip()

            if is_last_chunk and chunk and not chunk[-1].isspace():
                chunk = chunk + " "  # e.g. ensure space after "or": 1.e4 {or} 1.d4
            chunk = chunk.replace("\n\n", "</p><p>")
            chunk_with_br = chunk.replace("\n", "<br/>")
            output.append(chunk_with_br)

    return "".join(output)


def chunk_html_for_wrapping(text: str) -> list[str]:
    """
    Splits input HTML into chunks:
    - Inline content (text and inline tags), possibly with newlines
    - Block elements like <ul>...</ul> or <pre>...</pre>

    Preserves tag structure — safe to post-process with <p> and <br/>.
    """
    chunks = []
    pos = 0
    length = len(text)

    while pos < length:
        match = BLOCK_TAG_RE.search(text, pos)
        if not match:
            # No more block tags; the rest is inline
            chunks.append(text[pos:])
            break

        start = match.start()
        if start > pos:
            # Add preceding inline text
            chunks.append(text[pos:start])

        # Find the full block tag content (including closing tag)
        tag = match.group(0)
        tag_name = match.group(1).lower()

        if tag.startswith(f"<{tag_name}"):
            # Need to find the corresponding closing tag
            close_tag = f"</{tag_name}>"
            close_pos = text.find(close_tag, match.end())
            if close_pos == -1:
                # Malformed? Just grab the opening tag and move on
                chunks.append(tag)
                pos = match.end()
            else:
                end_pos = close_pos + len(close_tag)
                chunks.append(text[match.start() : end_pos])  # noqa: E203
                pos = end_pos
        else:
            # Stray closing tag? Treat it as-is
            chunks.append(tag)
            pos = match.end()

    # use all chunks as is, even if only whitespace since it might
    # have newlines or other formatting we want to preserve
    return chunks
