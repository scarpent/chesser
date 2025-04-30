import json
import re
from collections import defaultdict, namedtuple
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

MoveParts = namedtuple("MoveParts", ["move_num", "dots", "san", "annotation"])


@dataclass
class Chunk:
    type_: Literal["comment", "move", "fenseq", "subvar"]
    data: str


@dataclass
class ParsedBlock:
    # we started with chunk types: "comment", "subvar", "fenseq", "move"
    type_: Literal["comment", "start", "end", "move"]
    raw: str = ""
    errors: list[str] = field(default_factory=list)
    display_text: str = ""  # for normalized comments, moves
    move_parts_raw: Optional[MoveParts] = None
    move_parts_resolved: Optional[MoveParts] = None
    # fen representing state after this move (for normal render linking)
    fen: str = ""
    # fen_before represents the state before a subvar's first move, is exclusive to
    # fenseq/@@StartFEN@@ blocks, and tells us to render ⏮️ as a link to the before_fen
    fen_before: str = ""
    depth: int = 0  # for subvar depth tracking

    @property
    def verbose_move(self):
        # verbose is normalized for comparisons; no annotation
        move_num = self.move_num or ""
        return f"{move_num}{self.dots}{self.san}"


@dataclass
class RenderableBlock:
    type_: Literal["comment", "move"]
    html: str
    raw: str
    errors: list[str] = field(default_factory=list)


@dataclass
class ResolveStats:
    subvar_total: int = 0
    fenseq_total: int = 0

    moves_attempted: int = 0
    moves_resolved: int = 0
    moves_discarded: int = 0

    max_subvar_depth: int = 0

    resolved_matches_raw_explicit: int = 0  # move_num, dots, san all match
    resolved_matches_raw_implicit: int = 0  # items present match
    # maybe later we'll look more at annotations
    resolved_move_distance: defaultdict[int, int] = field(
        default_factory=lambda: defaultdict(int)
    )

    resolved_on_attempt: defaultdict[int, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    matched_root_san: int = 0
    mainline_siblings: int = 0
    mainline_siblings_resolved: int = 0
    first_matched_root_but_no_next: int = 0
    discarded: int = 0

    failure_blocks: list[str] = field(default_factory=list)

    def print_stats(self):
        print("\nParsing Stats Summary:\n")
        print(f"subvar total: {self.subvar_total}")
        print(f"fenseq total: {self.fenseq_total}")

        print(f"moves attempted: {self.moves_attempted}")
        print(f"moves resolved: {self.moves_resolved}")

        print(f"Max subvar depth: {self.max_subvar_depth}")

        print(f"Resolved match explicit: {self.resolved_matches_raw_explicit}")
        print(f"Resolved match implicit: {self.resolved_matches_raw_implicit}")
        print(
            f"Resolved move distance: {dict(sorted(self.resolved_move_distance.items()))}"  # noqa: E501
        )

        print(
            f"Resolved on attempt N: {dict(sorted(self.resolved_on_attempt.items()))}"
        )
        print(f"Matched root san: {self.matched_root_san}")
        print(f"Discarded: {self.discarded}")
        print(f"Mainline siblings: {self.mainline_siblings}")
        print(f"Mainline siblings resolved: {self.mainline_siblings_resolved}")
        print(f"First matched root but no next: {self.first_matched_root_but_no_next}")
        print("\n")
        if self.failure_blocks:
            print(f"{len(self.failure_blocks)} failed blocks:")
            for block in self.failure_blocks[:10]:  # Show first 10
                self.stdout.write(f"  - {block}")


def get_parsed_blocks(move: Move, board: chess.Board) -> list[ParsedBlock]:
    chunks = extract_ordered_chunks(move.text)
    parsed_blocks = get_parsed_blocks_first_pass(chunks)
    # resolved_blocks = resolve_moves(parsed_blocks, move, board)
    return parsed_blocks


def get_move_parsed_block(text: str, depth: int) -> ParsedBlock:
    return ParsedBlock(
        type_="move",
        raw=text,
        move_parts_raw=get_move_parts(text),
        depth=depth,
    )


MOVE_PARTS_REGEX = re.compile(
    r"""(?x)                # verbose 💬
    ^(\d*)                  # optional move number
    (\.*)\s*                # optional dots
    (
      [a-zA-Z]              # first san char must be a letter e4, Ba3, ...
      [a-zA-Z0-9-=]*        # allows for O-O and a8=Q
      [a-zA-Z0-9]           # last san char must be a number/letter (cap, really)
    )?
    ([^a-zA-Z0-9]*)$        # optional trailing annotation, including + and #
                            # which are part of san, but not required there
    """
)


def get_move_parts(text: str) -> MoveParts:
    """
    Breaks a literal move string into its core parts:
    move number, dots, san, and annotation. Check + and mate #
    will be included with annotation, even though they are part
    of the san.

    This split is very permissive. *Something* will match.

    - Extracts optional move number (e.g. "1" from "1.e4", "1. e4" "1...e5")
    - Extracts dots following the number ("." or "..." or "........" & so on)
    - Extracts the SAN (Standard Algebraic Notation) portion
    - Extracts any trailing annotation (e.g. "+", "#", "!?", etc.)
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
    m = MOVE_PARTS_REGEX.search(text.strip())
    if m:
        return MoveParts(
            move_num=int(m.group(1)) if m.group(1) else None,
            dots=m.group(2) or "",
            san=m.group(3) or "",
            annotation=m.group(4) or "",
        )
    else:
        return MoveParts(None, "", text.strip(), "")


def get_resolved_move_distance(
    resolved_move_num, resolved_dots, raw_move_num, raw_dots
):
    """
    Returns:
        -1 if ambiguous (missing raw num or dots)
         0 if match
        >0 ply distance otherwise

    Dot types:
        "."   → white to move = ply = (move_num - 1) * 2
        "..." → black to move = ply = (move_num - 1) * 2 + 1
    """
    if raw_move_num is None or raw_dots not in (".", "..."):
        return -1

    def move_to_ply(num, dots):
        return (num - 1) * 2 + (1 if dots == "..." else 0)

    resolved_ply = move_to_ply(resolved_move_num, resolved_dots)
    raw_ply = move_to_ply(raw_move_num, raw_dots)
    return abs(resolved_ply - raw_ply)


@dataclass
class StackFrame:
    board: chess.Board
    root_fen: str = ""
    root_san: str = ""
    move_counter: int = 0  # pass or fail
    # only resolved moves are added to this list
    parsed_moves: list[ParsedBlock] = field(default_factory=list)

    latest_san: str = ""
    latest_verbose: str = ""

    san: str = ""
    root_san: str = ""
    root_verbose: str = ""
    last_san: str = ""
    last_verbose: str = ""


class PathFinder:

    def __init__(
        self,
        blocks: list[ParsedBlock],
        move: Move,
        board: chess.Board,
        stats: Optional[ResolveStats] = None,
    ):
        self.blocks = blocks
        self.mainline_move = move
        self.board = board
        self.board_stack = [
            StackFrame(
                board=self.board.copy(),
                root_fen=self.board.fen(),
                root_san=move.san,  # will be a clean mainline san
            )
        ]
        self.stats = stats or ResolveStats()
        self.index = 0
        self.end_of_list = len(blocks)

    @property
    def current(self):
        return self.board_stack[-1]

    def get_next_move(self):
        if (
            self.index + 1 < self.end_of_list
            and self.blocks[self.index + 1].type_ == "move"
        ):
            return self.blocks[self.index + 1]
        else:
            return None

    def handle_start_block(self, block: ParsedBlock):
        if block.fen_before:
            # fenseq; let's try to mostly treat same as subvar
            chessboard = chess.Board(block.fen_before)
            self.stats.fenseq_total += 1
            print("↘️  fenseq")
        else:
            chessboard = self.current.board.copy()
            self.stats.subvar_total += 1
            self.stats.max_subvar_depth = max(self.stats.max_subvar_depth, block.depth)
            print(f"↘️  subvar (depth {block.depth})")

        if block.depth == 1:
            root_san = self.current.root_san
        else:
            if self.current.parsed_moves:
                raw_san = self.current.parsed_moves[-1].move_parts_raw.san
                resolved_san = self.current.parsed_moves[-1].move_parts_resolved.san
            else:
                print("❓️ No parsed moves when depth != 1")
                raw_san = ""
                resolved_san = ""

            if raw_san != resolved_san:
                print(
                    "📌 in start block, nested subvar, and stack raw san != "
                    f"resolved san: {raw_san} != {resolved_san}"
                )

            root_san = raw_san if self.current.parsed_moves else ""  # TODO: or resolved
        self.board_stack.append(
            StackFrame(
                board=chessboard,
                root_fen=chessboard.fen(),
                root_san=root_san,
            )
        )

    def bust_a_move(self, block: ParsedBlock, attempt: int = 1) -> bool:
        # don't just stand there... 🎶
        san = block.move_parts_raw.san
        try:
            move_obj = self.current.board.parse_san(san)
            self.current.board.push(move_obj)
        except Exception:
            print(f"❌ Failed to push move: {block.raw}")
            block.errors.append(f"Failed SAN during path finding: {san}")
            return False

        # turn = True means it's white's move, but that is *now*, so we
        # reverse things to apply to this move we just played for dots

        block.move_parts_resolved = MoveParts(
            move_num=(self.current.board.ply() + 1) // 2,
            dots="..." if self.current.board.turn else ".",
            san=san,
            annotation=block.move_parts_raw.annotation,
        )
        block.fen = self.current.board.fen()

        # I don't think we can decide on display text yet

        self.stats.moves_resolved += 1
        self.stats.resolved_on_attempt[attempt] += 1

        self.current.parsed_moves.append(block)
        print(f"✅ resolved move: {block.raw} ➤ {move_obj}")  # \n\t\t{block}")
        print(f"\traw parts: {block.move_parts_raw}")
        print(f"\tresolved parts: {block.move_parts_resolved}")
        return True

    def resolve_moves(self) -> list[ParsedBlock]:

        resolved_blocks = []

        while self.index < self.end_of_list:
            block = self.blocks[self.index]

            if block.type_ == "comment":
                resolved_blocks.append(block)
                self.index += 1
                continue

            elif block.type_ == "start":
                self.handle_start_block(block)
                resolved_blocks.append(block)
                self.index += 1
                continue

            elif block.type_ == "end":
                resolved_blocks.append(block)
                self.board_stack.pop()
                self.index += 1
                continue

            else:  # move
                assert block.type_ == "move", f"Unexpected block type: {block.type_}"

            self.stats.moves_attempted += 1
            self.current.move_counter += 1  # pass or fail

            # first, let's just try whatever the move is...
            # perhaps most of the time it will be valid 🤞
            move_played = self.bust_a_move(block, attempt=1)

            if move_played:
                # resolved moves should/better/absolutely must(?) have all the parts
                if (
                    block.move_parts_raw.move_num == block.move_parts_resolved.move_num
                    and block.move_parts_raw.dots == block.move_parts_resolved.dots
                    and block.move_parts_raw.san == block.move_parts_resolved.san
                ):
                    self.stats.resolved_matches_raw_explicit += 1

                # raw move parts may or may not have been there, we'll call it an
                # implicit match if whatever there matches
                elif (
                    (
                        block.move_parts_raw.move_num is None
                        or block.move_parts_raw.move_num
                        == block.move_parts_resolved.move_num
                    )
                    and (
                        block.move_parts_raw.dots == ""
                        or block.move_parts_raw.dots == block.move_parts_resolved.dots
                    )
                    and block.move_parts_raw.san == block.move_parts_resolved.san
                ):
                    self.stats.resolved_matches_raw_implicit += 1

                # 1...e4 ➤ 1.e4  2...e4 ➤ 1.e4
                # 1.e4 2.e5 ➤ 1.e4 1...e5
                # distance:
                # -1 = implied match (missing raw num or dots)
                # 0 = exact match
                move_distance = get_resolved_move_distance(
                    block.move_parts_resolved.move_num,
                    block.move_parts_resolved.dots,
                    block.move_parts_raw.move_num,
                    block.move_parts_raw.dots,
                )
                self.stats.resolved_move_distance[move_distance] += 1

                # however this will break our naive non-move number parsing:
                # (1...e5 2.Nf3 {or} 1...c5 2.c3)
                # c5 is a valid black second move
                # we'll start looking at raw vs resolved to try being smart

            if move_played:
                self.index += 1
                resolved_blocks.append(block)
                continue

            # wild explorations... keep in mind mainline move root vs other roots...

            first = self.current.move_counter == 1
            # maybe the first just repeated the previous (root) san,
            # and we can drop this one and move on...

            next_ = self.get_next_move()

            matched_root_san = self.current.root_san == block.move_parts_raw.san
            if matched_root_san:
                self.stats.matched_root_san += 1

            if first and matched_root_san and block.depth == 1:
                mainline_move_parts = get_move_parts(self.mainline_move.move_verbose)
                distance = get_resolved_move_distance(
                    mainline_move_parts.move_num,
                    mainline_move_parts.dots,
                    block.move_parts_raw.move_num,
                    block.move_parts_raw.dots,
                )
                if distance != 0:
                    print("❌")
                # distance = 0 on all matches!
                # if distance != 0:

            # TODO: should be looking at depth here? or make sure subvar root
            # is working as expected
            if first and matched_root_san and next_:
                self.stats.discarded += 1
                # expect that this will happen quite a bit;
                # should we see if the next move works first?
                # TODO: maybe should have some move num validation?
                print(
                    "🗑️  Discarding failed move block that has "
                    f"same san as previous: {block.move_parts_raw.san}"
                )
                self.index += 1
                continue
            if first and matched_root_san and not next_:
                self.stats.first_matched_root_but_no_next += 1
            dots = "." if self.mainline_move.white_to_move else "..."
            if (
                first
                and block.depth == 1
                and self.mainline_move.move_num == block.move_parts_raw.move_num
                and dots == block.move_parts_raw.dots
            ):
                # subvar move is a sibling of the mainline move
                temp_board = self.current.board.copy()
                temp_board.pop()
                print(
                    "❗️ first subvar move is sibling to mainline move; "
                    "figure out how to handle this..."
                )
                self.stats.mainline_siblings += 1
                try:
                    move_obj = temp_board.parse_san(block.move_parts_raw.san)
                    temp_board.push(move_obj)
                    print("✅ sibling move resolved! 🚀")
                    self.stats.mainline_siblings_resolved += 1
                except Exception:
                    print("❌ sibling move didn't resolve")

                # TODO: more here in verifying if things resolved to "wrong" move

            # if not first:
            #     # another common case is "implied" subvariations, without parens
            #     # e.g. (1.e4 e5 2.Nf3 {or} 2.Nc3 {or} 2.d4)
            #     # 2.Nc3 will work if we pop 2.Nf3...
            #     print("🛠️  implied subvar? undoing move and trying again")
            #     self.current.board.pop()
            #     move_played = self.bust_a_move(block, attempt=2)
            #     if move_played:
            #         self.index += 1
            #         resolved_blocks.append(block)
            #         continue

            self.index += 1

        return self.blocks


"""
former ActiveFenseq notes/comments/examples...

things to consider and handle if we can; when things fail...
* try going back to start of fenseq
* to end of previous subvar
* to mainline
* try other things!

<fenseq data-fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1">1.c4 e6 2.Nf3 d5 3.b3 { or } 1.c4 e6 2.Nf3 d5 3.g3 Nf6 4.b3 {...} 1.c4 e6 2.Nf3 d5 3.b3 {...} 3...d4 {...}</fenseq>

variation 754, move 14950, mainline 2.Nc3
<fenseq data-fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1">1.d4 d5 2.c4 e6 3.Nc3 {...} 2.Nc3 {...} 2...Nf6 {...}</fenseq>

variation 754, move 14958, mainline 6.f3
<fenseq data-fen="rn1qkb1r/pp2pppp/5n2/3p4/3P1Bb1/2N5/PPP2PPP/R2QKBNR w KQkq - 1 6">6.Nf3 Nc6 {...} 6.Qd2 {, but after} 6...Nc6 {, they will probably play} 7.f3 {anyway, which transposes to 6.f3 after all.}</fenseq>

after pushing the move:

ipdb> board.ply()
1
ipdb> board.fullmove_number  # but this doesn't seem to be "right"?
1
ipdb> board.turn  # white = True, black = False
False
ipdb> board.peek()
Move.from_uci('e2e4')

before pushing:

board.san(move_obj)

...

board.pop() to undo the move
"""  # noqa: E501


def get_parsed_blocks_first_pass(chunks: list[Chunk]) -> list[ParsedBlock]:
    parsed_blocks = []
    i = 0
    depth = 0

    while i < len(chunks):
        chunk = chunks[i]
        # print(f"🔍 Parsing chunk: {chunk.type_} ➤ {chunk.data.strip()[:40]}...")

        # ➡️ Every branch must advance `i`

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

        elif (
            chunk.type_ == "move"
        ):  # a single move, whether 1.e4 or 1. e4 or something malformed
            parsed_blocks.append(get_move_parsed_block(chunk.data, depth))
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
        1.d4 d5 2.e3 {comment}
    </fenseq>

    turn this fenseq blob into a mostly typical subvar block list
    * fenseq sequences are expected to be depth 1, and *may* have comments
    * we should mostly get "condensed" moves, e.g. 1.e4, but we'll handle 1. e4

    we could make data-fen be optional and use game starting fen if omitted...

    this is a bit hairy at the moment but it actually works now so that's good
    """
    match = re.search(
        r"""<\s*fenseq[^>]*data-fen=["']([^"']+)["'][^>]*>(.*?)</fenseq>""",
        raw,
        re.DOTALL,
    )
    # "fenseq" type blocks should always match or they'd already be "comment" type
    # assert match, f"Invalid fenseq chunk: {raw}"
    if not match:
        print(f"🚨 Invalid fenseq block: {raw}")
        return []

    fen, inner_text = match.groups()
    # we don't expect fenseq tags to have parens; we'll strip
    # them here so that we can always add them below
    inner_text = inner_text.strip().strip("()")

    if not inner_text:
        print(f"⚠️  Empty inner text in fenseq chunk: {raw}")
        return []

    # extract_ordered_chunks requires parens to process as a subvar
    inner_text = f"({inner_text})"

    DEPTH = 1
    blocks = [ParsedBlock("start", depth=DEPTH, fen_before=fen)]

    chunks = extract_ordered_chunks(inner_text)

    for chunk in chunks:
        if chunk.type_ == "move":
            # moves are the only things we try stripping down in this pass
            blocks.append(get_move_parsed_block(chunk.data.strip(), DEPTH))
        elif chunk.type_ == "comment":
            blocks.append(
                ParsedBlock(
                    type_="comment",
                    raw=chunk.data,
                    display_text=chunk.data.strip("{}"),
                )
            )
        elif chunk.type_ == "subvar":
            # we might ignore these in favor of the hardcoded fenseq
            # start/end and we might discard extras and just treat
            # flatly and hope for the best
            pass
        else:
            print(
                "⚠️  Unexpected chunk inside fenseq: "
                f"{chunk.type_} ➤ {chunk.data.strip()}"
            )

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
            # moves are the only things we strip in this pass
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
            if c.isspace():
                if token_start is not None:
                    token = text[token_start:i]
                    if re.match(r"^\d+\.*\s*$", token):
                        # still building a move number like "1." or "1..."
                        pass
                    else:
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
