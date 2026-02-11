import json
import re
from collections import defaultdict
from dataclasses import dataclass

import chess
from django.utils import timezone
from django.utils.html import format_html, strip_tags
from django.utils.safestring import mark_safe

from chesser import util
from chesser.models import Move, SharedMove, get_matching_moves, get_shared_candidates
from chesser.move_resolver import ParsedBlock, get_parsed_blocks

ANNOTATIONS = {
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
    "□": "□ Only Move",
    "⇄": "⇄ Counterplay",
    "⊙": "⊙ Zugzwang",
    "↑": "↑ Initiative",
    "→": "→ Attack",
}


BLOCK_TAG_RE = re.compile(
    rf"</?({'|'.join(util.BLOCK_TAGS)})\b[^>]*>",
    re.IGNORECASE,
)


def serialize_variation(variation, mode="review"):
    include_html = mode == "variation"
    include_alt_shapes = mode == "variation"
    for_edit = mode == "edit"

    color = variation.chapter.color

    now = timezone.now()
    time_since_last_review = util.get_time_ago(
        now, variation.get_latest_quiz_result_datetime()
    )
    time_until_next_review = util.format_time_until(now, variation.next_review)

    source_html = get_source_html(variation.source) if include_html else None
    html = generate_variation_html(variation) if include_html else None

    variation_data = {
        "variation_id": variation.id,
        "title": variation.title,
        "chapter_id": variation.chapter.id,
        "chapter": variation.chapter.title,
        "color": color,
        "is_intro": variation.is_intro,
        "archived": variation.archived,
        "start_index": variation.start_index,
        "start_move": variation.start_move,
        "level": variation.level,
        "time_since_last_review": time_since_last_review,
        "time_until_next_review": time_until_next_review,
        "created_at": util.format_local_date(variation.created_at),
        "mainline": variation.mainline_moves_str,
        "source_html": source_html,
        "html": html,
        "analysis_url": util.get_analysis_url(variation),
    }

    temp_annotations = ANNOTATIONS.copy()
    moves = []
    for move in variation.moves.all():
        # preserve "unknown" annotations in dropdown
        shared_annotation = move.shared_move.annotation if move.shared_move else None
        for annotation in (move.annotation, shared_annotation):
            if annotation and annotation not in temp_annotations:
                temp_annotations[annotation] = f"unknown: {annotation}"
                print(
                    "unknown annotation in variation "
                    f"{variation.id}: {move.move_verbose} ➤ {annotation}"
                )

        moves.append(serialize_move(move, for_edit=for_edit))

    if include_alt_shapes:
        add_alt_shapes_to_moves(moves)

    variation_data["moves"] = moves
    variation_data["annotations"] = temp_annotations
    variation_data["history"] = get_history(variation)

    return variation_data


def serialize_move(move, for_edit=False):
    # editor has special handling for all move data;
    # other modes only need the "resolved" moves

    shared = move.shared_move  # is there a shared move?

    move_data = {
        "move_id": move.id,
        "fen": move.fen,
        "san": move.san,
        "annotation": move.annotation,
        "move_verbose": move.move_verbose,
        "text": move.text,
        "alt": move.alt,
        "alt_fail": move.alt_fail,
        "shapes": move.shapes,
        "shared_move_id": str(shared.id) if shared else "",
    }

    if shared:
        shared_fields = {
            "text": shared.text,
            "annotation": shared.annotation,
            "alt": shared.alt,
            "alt_fail": shared.alt_fail,
            "shapes": shared.shapes,
        }
        if for_edit:
            # we don't strictly need "shared": we could get this info
            # from shared_candidates, but it makes things easier in
            # the UI to have it here
            move_data["shared"] = shared_fields
        else:
            move_data.update(shared_fields)

    if for_edit:
        fen = move.fen
        san = move.san
        color = move.variation.chapter.color

        move_data["shared_candidates"] = get_shared_candidates(fen, san, color)
        move_data["shared_dropdown"] = get_shared_dropdown(
            fen, san, color, shared_move=shared
        )
        move_data["matching_move_count"] = get_matching_moves(fen, san, color).count()

    return move_data


def get_shared_dropdown(fen, san, color, shared_move=None) -> list[dict]:
    candidates = get_shared_candidates(fen, san, color)
    dropdown = []

    if not candidates:
        dropdown.append({"value": "", "label": "Not shared"})
    else:
        label = "Unlink shared move" if shared_move else "Shared move not linked"
        dropdown.append({"value": "", "label": label})

    for candidate_id, _ in candidates.items():
        label = f"Shared move (#{candidate_id})"
        dropdown.append({"value": str(candidate_id), "label": label})

    dropdown.append({"value": "__new__", "label": "New shared move"})

    return dropdown


def serialize_shared_move(
    shared_moves: list[SharedMove], matching_moves: list[Move]
) -> dict:
    """
    Return structure for edit_shared.html:
    - shared_moves: editable
    - move_groups: read-only, grouped by shared fields, with linked shared_move IDs

    Move groups are read only, mostly, but we can set/unset a shared move, and also
    copy shared values to the individual moves.
    """
    move_data = {
        "shared_moves": [],
        "move_groups": [],
        "total_matching_moves": len(matching_moves),
    }

    temp_annotations = ANNOTATIONS.copy()

    # Editable SharedMove blocks
    for shared_move in shared_moves:
        move_data["shared_moves"].append(
            {
                "id": shared_move.id,
                "text": shared_move.text,
                "annotation": shared_move.annotation,
                "alt": shared_move.alt,
                "alt_fail": shared_move.alt_fail,
                "shapes": shared_move.shapes,
                "linked_move_ids": list(shared_move.moves.values_list("id", flat=True)),
            }
        )
        # Similar to variation serialization, preserve unknowns
        if shared_move.annotation and shared_move.annotation not in temp_annotations:
            temp_annotations[shared_move.annotation] = (
                f"unknown: {shared_move.annotation}"
            )

    # Group Move instances by shared fields and shared move id
    grouped = defaultdict(list)
    for move in matching_moves:
        key = (
            move.text,
            move.annotation,
            normalize_alts(move.alt),
            normalize_alts(move.alt_fail),
            normalize_shapes(move.shapes),
            str(move.shared_move.id) if move.shared_move else "",
        )
        grouped[key].append(move)

    for (
        text,
        annotation,
        alt,
        alt_fail,
        shapes,
        shared_move_id,
    ), group in grouped.items():

        move_data["move_groups"].append(
            {
                "count": len(group),
                "text": text,
                "annotation": annotation,
                "alt": alt,
                "alt_fail": alt_fail,
                "shapes": shapes,
                "move_sequence": group[0].sequence,
                "example_variation": {
                    "id": group[0].variation.id,
                    "title": group[0].variation.title,
                    "chapter": group[0].variation.chapter.title,
                },
                "shared_move_id": shared_move_id,
                "shared_dropdown": get_shared_dropdown(
                    group[0].fen,
                    group[0].san,
                    group[0].variation.chapter.color,
                    shared_move=shared_move_id,
                ),
                "in_sync": move_is_in_sync_with_shared(group[0]),  # all same in group
                "move_ids": [move.id for move in group],
                "variation_ids": [move.variation.id for move in group],
            }
        )
        if annotation and annotation not in temp_annotations:
            temp_annotations[annotation] = f"unknown: {annotation}"

    move_data["move_groups"].sort(key=lambda g: g["count"], reverse=True)
    move_data["annotations"] = temp_annotations

    return move_data


def move_is_in_sync_with_shared(move):
    if not move.shared_move:
        return False

    return (
        move.text == move.shared_move.text
        and move.annotation == move.shared_move.annotation
        and move.alt == move.shared_move.alt
        and move.alt_fail == move.shared_move.alt_fail
        and move.shapes == move.shared_move.shapes
    )


def normalize_alts(alt_str):
    if not alt_str:
        return ""
    return ", ".join(
        sorted(part.strip() for part in alt_str.split(",") if part.strip())
    )


def normalize_shapes(shapes_str):
    """normalize shapes JSON so we can compare them for grouping"""
    if not shapes_str:
        return ""
    try:
        shapes_list = json.loads(shapes_str)
    except Exception:
        return shapes_str  # fallback: malformed JSON, use as is

    shapes_list = sorted(
        shapes_list,
        key=lambda s: (s.get("brush", ""), s.get("orig", ""), s.get("dest", "")),
    )

    return json.dumps(shapes_list, separators=(",", ":"))


def serialize_variation_to_import_format(variation):
    return {
        "variation_id": variation.id,
        "source": variation.source,
        "color": variation.chapter.color,
        "chapter_title": variation.chapter.title,
        "variation_title": variation.title,
        "is_intro": variation.is_intro,
        "archived": variation.archived,
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
                # "fen": m.fen  # probably don't need this
                "san": m.san,
                "annotation": m.get_resolved_field("annotation"),
                "text": m.get_resolved_field("text"),
                "alt": m.get_resolved_field("alt"),
                "alt_fail": m.get_resolved_field("alt_fail"),
                "shapes": json.loads(m.get_resolved_field("shapes")),
            }
            for m in variation.moves.all().order_by("sequence")
        ],
        "mainline": variation.mainline_moves_str,
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


def normalize_links(source) -> list[dict]:
    """We allow either a single link dict or a list of link dicts in source."""
    link = (source or {}).get("link")
    if not link:
        return []
    if isinstance(link, dict):
        return [link]
    if isinstance(link, list):
        return [x for x in link if isinstance(x, dict)]
    return []


def get_links_from_source(source) -> list[str]:
    """Returns a list of HTML fragments to be concatenated by the caller.

    Different output structures for single or multiple links:

    Single:

        Source: 3.Bc4 Italian Game (Wikibooks)

    Multiple:

        Sources:
          • 3.Bc4 Italian Game (Wikibooks)
          • Blah, blah, blah
    """
    parts = []
    links = normalize_links(source)

    if len(links) == 1:
        info = links[0]
        url = util.safe_href(info.get("url", ""))
        text = strip_tags(info.get("text", ""))

        if url and text:
            parts.append(
                format_html(
                    '<p>Source: <a href="{}" target="_blank" rel="noopener">{}</a></p>',
                    url,
                    text,
                )
            )
        elif text:
            parts.append(format_html("<p>Source: {}</p>", text))

    elif len(links) > 1:
        parts.append('<br>Sources:\n<ul style="margin-top: 5px">')

        for info in links:
            url = util.safe_href(info.get("url", ""))
            text = strip_tags(info.get("text", ""))

            if url and text:
                parts.append(
                    format_html(
                        '<li><a href="{}" target="_blank" rel="noopener">{}</a></li>',
                        url,
                        text,
                    )
                )
            elif text:
                parts.append(format_html("<li>{}</li>", text))

        parts.append("</ul>")

    return parts


def get_source_html(source):
    """See Variation in models.py for source structure."""
    parts = get_links_from_source(source)

    # My course (Chessable variation link)
    if my_course := source.get("my_course"):
        variation_id = int(my_course["variation_id"])

        parts.append(
            format_html(
                "<p>Source Variation "
                '<a href="https://www.chessable.com/variation/{}/" '
                'target="_blank" rel="noopener">{}</a></p>',
                variation_id,
                variation_id,
            )
        )

        if note := my_course.get("note", "").strip():
            parts.append(format_html("<p>{}</p>", mark_safe(util.clean_html(note))))

    # Original course (also Chessable variation link; we show/sanitize more fields)
    if original_course := source.get("original_course"):
        variation_id = int(original_course["variation_id"])

        cleaned_course = strip_tags(original_course.get("course", ""))
        cleaned_chapter = strip_tags(original_course.get("chapter", ""))
        cleaned_title = strip_tags(original_course.get("variation_title", ""))

        parts.append(
            format_html(
                "<p>{} ➤<br>{} ➤<br>{} "
                '<a href="https://www.chessable.com/variation/{}/" '
                'target="_blank" rel="noopener">{}</a></p>',
                cleaned_course,
                cleaned_chapter,
                cleaned_title,
                variation_id,
                variation_id,
            )
        )

        if note := original_course.get("note", "").strip():
            parts.append(format_html("<p>{}</p>", mark_safe(util.clean_html(note))))

    if not parts:
        return "<br>"

    # We might have tried cleaning the whole thing here,
    # but that would strip out <p>, etc
    return "".join(parts)


def generate_variation_html(variation):
    html = ""
    white_to_move = True
    beginning_of_move_group = True
    pgn_moves = ""
    board = chess.Board()
    for move in variation.moves.iterator():
        resolved_annotation = move.get_resolved_field("annotation")
        resolved_move_text = move.get_resolved_field("text")

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

        move_str += f"{move.san}{resolved_annotation}"

        html += format_html(
            '<span class="move mainline-move" data-index="{}">{}</span>',
            move.sequence,
            move_str,
        )

        board.push_san(move.san)  # Mainline moves better be valid

        if resolved_move_text:
            beginning_of_move_group = True
            parsed_blocks = get_parsed_blocks(move, board.copy())
            subvar_html = generate_subvariations_html(move.sequence, parsed_blocks)

            html += f"</h3>{subvar_html}"

    if not beginning_of_move_group:
        html += "</h3>"

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
            html += f" {util.clean_html(comment)} "
        elif block.type_ == "move":
            move_text = block.move_verbose if previous_type != "move" else block.raw
            html += f" {strip_tags(move_text)} "
        previous_type = block.type_

    if html:
        html = f"<h3>{move.move_verbose}</h3>\n{html}"

    return html


@dataclass
class RenderState:
    counter: int = -1  # unique data-index
    in_paragraph: bool = False
    previous_type: str = ""
    next_type: str = ""
    debug: bool = False


def render_comment_block(block: ParsedBlock, state: RenderState) -> str:
    """
    Comments may have text but might also only have formatting
    like newlines which we preserve depending on the context.
    """
    cleaned_text = util.clean_html(block.display_text)
    chunks = chunk_html_for_wrapping(cleaned_text)
    html = render_chunks_with_br(chunks, state)

    if state.debug:
        print(f"➡️ |\n{cleaned_text}\n|⬅️")
        print(f"\n🧊 Chunks:\n{chunks}")
        print(f"\n💦 Rendered:\n{html}|in para = {state.in_paragraph}\n")

    return html


def render_start_block(block: ParsedBlock, state: RenderState) -> str:
    """For something that's useful for debugging but doesn't need to be on all
    the time, you might start with:

        html = f"<!-- Start Block Log: {block.log} -->"

    That will break a set of tests (see: test_render_start_block), which are
    easily fixed.

    Security note: don't emit block.log directly into HTML. Even inside an HTML
    comment, untrusted content can "break out" of the comment (e.g. via '-->')
    and turn the rest into real markup, creating an injection/XSS risk. If you
    ever need this, gate it behind DEBUG and ensure the emitted content is
    escaped/neutralized for the context (or log to server output instead).
    """
    html = ""

    if block.fen:
        if not state.in_paragraph:
            html += "<p>"
            state.in_paragraph = True
        state.counter += 1

        html += format_html(
            '<span class="move subvar-move" data-fen="{}" data-index="{}">⏮️</span>',
            block.fen,
            state.counter,
        )

    elif block.depth > 1:
        # use depth and emoji for debug/visualization: <p>{block.depth}🌻
        para = format_html('<p class="subvar-indent depth-{}">', block.depth)
        if not state.in_paragraph:  # probably already in a paragraph at depth 2
            html += para
            state.in_paragraph = True
        else:
            # TODO: look out for <p></p>? (not seeing any big gaps so far)
            html += "</p>" + para

    return html


def render_end_block(block: ParsedBlock, state: RenderState) -> str:
    """let's try organizing more deeply nested subvariations"""
    html = ""
    if block.depth > 1:
        # Check next block context (avoids leaking p tags if subvar is ending)
        if state.next_type in ["move", "comment"]:
            if not state.in_paragraph:  # probably already in a paragraph at depth 2
                html += "<p>"
                state.in_paragraph = True
            # depth/emoji for debug/visualization: 🪦{block.depth}</p>
            html += f'</p><p class="subvar-indent depth-{block.depth - 1}">'

    # TODO: handle <p></p> case (test_render_end_block has an example)

    return html


def render_move_block(block: ParsedBlock, state: RenderState) -> str:
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
            f'<span class="move subvar-move" data-fen="{block.fen}" data-index="'
            f'{state.counter}">{strip_tags(move_text)}{resolved}</span> '
        )
    else:
        html += f" {move_text} {resolved} "

    """
    # is this expensive enough to care about? likely won't keep doing
    # the board but should always include the parsed block for moves
    try:
        board = chess.Board(block.fen)
    except Exception:
        board = "(no board)"

    # phew! this is useful for debugging; but it will break some special parens cleanup
    html += f"<!-- {block}\n{board} -->"
    """

    return html


def print_block_type_info(block: ParsedBlock):
    if block.type_ == "comment":
        text = f"➡️ |\n{block.display_text}\n|⬅️"
    elif block.type_ == "move":
        text = f"{block.raw} | {block.move_verbose}"
    else:
        text = block.depth
    print(f"block type: {block.type_} {text}")


def get_next_type(blocks: list[ParsedBlock], i: int) -> str:
    try:
        return blocks[i + 1].type_
    except IndexError:
        return ""


BLOCK_RENDERERS = {
    "comment": render_comment_block,
    "start": render_start_block,
    "end": render_end_block,
    "move": render_move_block,
}


def generate_subvariations_html(
    mainline_move_sequence: int,
    parsed_blocks: list[ParsedBlock],
    debug: bool = False,
) -> str:
    """
    Our train of blocks cars has been filled with a precious
    cargo of pgn slurry, which we'll finally pour into HTML.
    """
    state = RenderState(debug=debug)
    html = ""
    for i, block in enumerate(parsed_blocks):
        if debug:
            print_block_type_info(block)

        state.next_type = get_next_type(parsed_blocks, i)
        renderizer = BLOCK_RENDERERS.get(block.type_)
        assert renderizer, f"Unknown block type: {block.type_}"
        html += renderizer(block, state)
        state.previous_type = block.type_

    if state.in_paragraph:
        html += "</p>"  # and no need to unset state here at the end 🪦

    # This might be the place to do various cleanup? e.g. <p></p>,
    # although that one we might want to handle/prevent earlier.
    # There are also extra spaces between move spans and punctuation
    # [,.!?] which are more easily removed here, along with parens 🧹

    # TODO: should really have some tests for these cleanups

    # hr is already a break, and the extra br can cause too much space
    html = html.replace("<hr><br/>", "<hr>")
    html = re.sub(r"\( +<span", r"(<span", html)
    html = re.sub(r"<\/span> +([),.!?])", r"</span>\1", html)

    return (
        '<div class="subvariations" data-mainline-index="'
        f'{mainline_move_sequence}">{html}</div>'
    )


def is_block_element(chunk: str) -> bool:
    tag_match = re.match(r"<(/)?(\w+)", chunk.strip())
    if not tag_match:
        return False
    tag = tag_match.group(2).lower()
    return tag in util.BLOCK_TAGS


def render_chunks_with_br(chunks: list[str], state: RenderState) -> str:
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
