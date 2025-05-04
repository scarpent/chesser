import json
import re
from collections import defaultdict, namedtuple
from copy import copy
from dataclasses import dataclass, field
from typing import Literal, Optional

import chess
import chess.pgn
from django.utils import timezone

from chesser import util
from chesser.models import Move

AMBIGUOUS = -1

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

                # subvar_html = render_parsed_blocks(parsed_blocks, board.copy())

                # blocks = [
                #     f"<p style='padding: 4px; border: 1px solid #ccc'>{block}</p>"
                #     for block in parsed_blocks
                # ]
                # subvar_html = f"<p>{move.text}</p>{'\n'.join(blocks)}"

            else:  # v1
                moves_with_fen = extract_moves_with_fen(board.copy(), move)
                subvar_html = generate_subvariations_html_v1(move, moves_with_fen)

            html += f"</h3>{subvar_html}"

        # v1 had this at the end of the loop for some reason
        if version != 2:
            board.push_san(move.san)  # Mainline moves better be valid

    html = htmlize_chessable_tags(html)

    return html


def generate_subvariations_html(move, parsed_blocks):
    counter = -1  # for unique data-index
    html = ""
    previous_type = ""
    for block in parsed_blocks:
        if block.type_ == "comment":
            comment = block.display_text.replace("\n", "<br/>")
            html += f" {comment} "

        elif block.type_ == "start" and block.fen:
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


# TODO: this goes away after cleanup is all done and import also cleans
def htmlize_chessable_tags(html):
    html = html.replace("@@SANStart@@", "<b>").replace("@@SANEnd@@", "</b>")
    html = html.replace("@@ul@@", "<ul>").replace("@@/ul@@", "</ul>")
    html = html.replace("@@li@@", "<li>").replace("@@/li@@", "</li>")
    return html


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


MoveParts = namedtuple("MoveParts", ["num", "dots", "san", "annotation"])


def assemble_move_parts(move_parts: MoveParts) -> str:
    """
    Assembles the move parts into a string representation.
    """
    num = str(move_parts.num) if move_parts.num else ""
    dots = move_parts.dots
    san = move_parts.san
    annotation = move_parts.annotation

    return f"{num}{dots}{san}{annotation}".strip()


@dataclass
class ParsedBlock:
    # we started with chunk types: "comment", "subvar", "fenseq", "move"
    type_: Literal["comment", "start", "end", "move"]
    raw: str = ""
    display_text: str = ""  # for normalized comments, moves
    move_parts_raw: Optional[MoveParts] = None
    move_parts_resolved: Optional[MoveParts] = None
    raw_to_resolved_distance: int = AMBIGUOUS  # unknown to start
    # for move blocks: fen representing state after this move (normal link rendering)
    # for start blocks: fen representing state before the sequence;
    #                   i.e. fenseq/@@StartFEN@@, enables rendering ⏮️ as a link
    fen: str = ""
    depth: int = 0  # for subvar depth tracking
    log: list[str] = field(default_factory=list)

    @property
    def is_resolved(self):
        return self.type_ == "move" and self.move_parts_resolved is not None

    @property
    def is_valid_move(self):
        return self.type_ == "move" and self.move_parts_resolved is not None

    def clone(self):
        new = copy(self)
        new.log = self.log.copy()
        return new

    def equals_raw(self, other):
        nums_equal = (
            self.move_parts_raw.num
            and self.move_parts_raw.num == other.move_parts_raw.num
        )
        dots_equal = (
            self.move_parts_raw.dots
            and self.move_parts_raw.dots == other.move_parts_raw.dots
        )
        return (
            self.type_ == other.type_ == "move"
            and nums_equal
            and dots_equal
            and self.move_parts_raw.san == other.move_parts_raw.san
        )

    def move_verbose(self):
        if self.move_parts_resolved:
            return assemble_move_parts(self.move_parts_resolved)
        elif self.move_parts_raw:
            return assemble_move_parts(self.move_parts_raw)
        else:
            return self.raw

    def debug(self):
        if self.type_ == "comment":
            info = f"{{{self.raw[:10].strip()}...}}"
        elif self.type_ in ["start", "end"]:
            prefix = "🌳" if self.type_ == "start" else "🍂"
            info = f"{prefix} subvar {self.depth} {self.fen}"
        else:
            info = self.raw

        print(f"  • {self.type_} {info}")
        for line in self.log:
            print(f"    {line}")


@dataclass
class ResolveStats:
    sundry: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # tells us if implicit match (-1), explicit match (0), or how far off (1+)
    first_move_distances: defaultdict[int, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    other_move_distances: defaultdict[int, int] = field(
        default_factory=lambda: defaultdict(int)
    )

    subvar_depths: defaultdict[int, int] = field(
        default_factory=lambda: defaultdict(int)
    )

    def print_stats(self):
        print("\nParsing Stats Summary:\n")
        for sun in sorted(self.sundry.keys()):
            print(f"{sun}: {self.sundry[sun]}")

        depths = str(dict(sorted(self.subvar_depths.items())))
        print(f"subvar depths: {depths}")

        move_distances = str(dict(sorted(self.first_move_distances.items())))
        print(f"first move distances: {move_distances}")

        move_distances = str(dict(sorted(self.other_move_distances.items())))
        print(f"other move distances: {move_distances}")

        print("\n")


def get_parsed_blocks(move: Move, board: chess.Board) -> list[ParsedBlock]:
    chunks = extract_ordered_chunks(move.text)
    parsed_blocks = get_parsed_blocks_first_pass(chunks)
    pathfinder = PathFinder(parsed_blocks, move, board)
    resolved_blocks = pathfinder.resolve_moves()
    return resolved_blocks


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
    (                       #
      [a-zA-Z]              # first san char must be a letter e4, Ba3, ...
      [a-zA-Z0-9-=]*        # allows for O-O and a8=Q
      [a-zA-Z0-9]           # last san char usually a a number but could be cap
                            # OQRNB (we'll be easy with a-zA-Z, still)
    )?                      # optional san
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

    This split is very permissive. Everything is optional, so *something*
    will match, even if just empties. But we'll likely get a san at least.

    - Extracts optional move number (e.g. "1" from "1.e4", "1. e4" "1...e5")
    - Extracts dots following the number ("." or "..." or "........" & so on)
    - Extracts the SAN (Standard Algebraic Notation) portion
    - Extracts any trailing annotation (e.g. "+", "#", "!?", etc.)
    - Strips any leading/trailing whitespace from the SAN

    We do not validate the move content here:
    - Malformed SANs, impossible moves, etc. are allowed
    - Path validation happens later during move resolution

    The goal is to be strict in how we parse and clean fields, but
    flexible in accepting whatever we have at this point. We probably
    have mostly clean data at this point and errors won't be catastrophic
    later. God knows Chessable has enough broken subvariations themselves.
    """
    m = MOVE_PARTS_REGEX.search(text.strip())
    if m:
        return MoveParts(
            num=int(m.group(1)) if m.group(1) else None,
            dots=m.group(2) or "",
            san=m.group(3) or "",
            annotation=m.group(4) or "",
        )
    else:
        return MoveParts(None, "", text.strip(), "")


def get_resolved_move_distance(
    resolved_move_parts: MoveParts, raw_move_parts: MoveParts
):
    """
    Returns:
        -1 if ambiguous (missing raw num or dots)
         0 if match
        >0 ply distance otherwise

    Dot types:
        "."   → white to move = ply = (move num - 1) * 2
        "..." → black to move = ply = (move num - 1) * 2 + 1

    TODO: perhaps we shouldn't use "abs" here; we'll see if we care
    about the direction of the move distance later...
    """
    if raw_move_parts.num is None or raw_move_parts.dots not in (".", "..."):
        return AMBIGUOUS

    def move_to_ply(num, dots):
        return (num - 1) * 2 + (1 if dots == "..." else 0)

    resolved_ply = move_to_ply(resolved_move_parts.num, resolved_move_parts.dots)
    raw_ply = move_to_ply(raw_move_parts.num, raw_move_parts.dots)
    return abs(resolved_ply - raw_ply)


@dataclass
class StackFrame:
    board: chess.Board
    root_block: ParsedBlock
    move_counter: int = 0  # pass or fail
    # only resolved moves are added to this list
    parsed_moves: list[ParsedBlock] = field(default_factory=list)

    board_previous: Optional[chess.Board] = field(init=False)

    def __post_init__(self):
        # make previous move handy for sibling checking
        self.board_previous = self.board.copy()
        try:
            self.board_previous.pop()
        except IndexError:
            # either the starting position or a fenseq with no prior moves
            self.board_previous = None


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

        # make a parsed move block for the mainline move -
        # it will always have all the information: move num, dots, san
        move_parts = get_move_parts(move.move_verbose)
        root_block = ParsedBlock(
            type_="move",
            raw=move.move_verbose,
            move_parts_raw=move_parts,
            move_parts_resolved=move_parts,
            fen=board.fen(),
            depth=0,  # this is the root root! 🌳 no move block would naturally be < 1
        )
        self.stack = [StackFrame(board=self.board.copy(), root_block=root_block)]

        self.stats = stats or ResolveStats()
        self.index = 0
        self.end_of_list = len(blocks)

    @property
    def current(self):
        return self.stack[-1]

    # TODO: goes away?
    def get_next_move(self):
        if (
            self.index + 1 < self.end_of_list
            and self.blocks[self.index + 1].type_ == "move"
        ):
            return self.blocks[self.index + 1]
        else:
            return None

    def handle_start_block(self, block: ParsedBlock):
        if block.fen:
            # fenseq; let's try to mostly treat same as subvar
            chessboard = chess.Board(block.fen)
            self.stats.sundry["subfen"] += 1
        else:
            chessboard = self.current.board.copy()
            self.stats.sundry["subvar"] += 1
            self.stats.subvar_depths[block.depth] += 1

        if block.depth == 1 or not self.current.parsed_moves:
            root_block = self.current.root_block.clone()
        else:  # else use the last of current resolved moves
            root_block = self.current.parsed_moves[-1].clone()

        # the original root root will always remain 0
        root_block.depth = block.depth

        self.stack.append(StackFrame(board=chessboard, root_block=root_block))

        block.log.append("stack")
        for frame in self.stack:
            fen = frame.board.fen()
            message = f"\t{frame.root_block.raw} ➤ {frame.root_block.depth} ➤ {fen}"
            block.log.append(message)

    def try_move(self, block: ParsedBlock, pending: bool = False) -> ParsedBlock:
        block_to_use = block.clone() if pending else block
        board = self.current.board.copy() if pending else self.current.board

        san = block_to_use.move_parts_raw.san

        try:
            move_obj = board.parse_san(san)
        except (
            chess.IllegalMoveError,
            chess.InvalidMoveError,
            chess.AmbiguousMoveError,
        ) as e:
            block_to_use.log.append(
                f"❌ parse_san {e}: {san} | board move "
                f"{board.fullmove_number}, white turn {board.turn}"
            )
            return block

        board.push(move_obj)

        # turn = True means it's white's move *now*, so we reverse things
        # to figure out dots for move just played

        move_parts_resolved = MoveParts(
            num=(board.ply() + 1) // 2,
            dots="..." if board.turn else ".",
            san=san,
            annotation=block.move_parts_raw.annotation,
        )

        resolved_move_distance = get_resolved_move_distance(
            move_parts_resolved, block.move_parts_raw
        )

        block_to_use.move_parts_resolved = move_parts_resolved
        block_to_use.raw_to_resolved_distance = resolved_move_distance
        block_to_use.fen = board.fen()

        block_to_use.log.append(
            f"R ➤ {tuple(block.move_parts_raw)} ➤ "
            f"{tuple(block_to_use.move_parts_resolved)}"
        )

        if not pending:
            self.stats.sundry["moves_resolved"] += 1
            self.current.parsed_moves.append(block_to_use)

        return block_to_use

    def increment_move_count(self, block: ParsedBlock):
        # move count whether pass or fail; in particular we want to know
        # when we're on the first move of a subvar to compare against mainline
        self.current.move_counter += 1

        if self.current.move_counter == 1:
            label = "first"
        else:
            label = "other"

        if block.move_parts_raw.num:
            self.stats.sundry[f"{label}_moves_has_num"] += 1
        dots = block.move_parts_raw.dots if block.move_parts_raw.dots else "none"
        self.stats.sundry[f"{label}_moves_dots {dots}"] += 1

        self.stats.sundry["moves_attempted"] += 1

    def is_duplicate_of_root_block(self, pending_block: ParsedBlock):
        # e.g. mainline 1.e4, subvar (1.e4 e5)
        if self.current.move_counter == 1 and pending_block.equals_raw(
            self.current.root_block
        ):
            self.stats.sundry["discarded root dupe"] += 1
            print(
                "🗑️  Discarding move block same as root: "
                f"{pending_block.move_parts_raw}"
            )
            return True
        else:
            return False

    def get_root_sibling(self, pending_block: ParsedBlock):
        # e.g. mainline 1.e4, subvar (1.d4 d5)
        if self.current.move_counter == 1 and self.current.board_previous:
            distance_from_root = get_resolved_move_distance(
                self.current.root_block.move_parts_resolved,
                pending_block.move_parts_raw,
            )
            if distance_from_root == 0:
                self.stats.sundry["root_siblings"] += 1
                self.current.board = self.current.board_previous.copy()

                another_pending_block = self.try_move(pending_block, pending=True)

                if another_pending_block.is_resolved:
                    another_pending_block.log.append("👥 sibling move resolved 🔍️")
                    self.stats.sundry["root_siblings_resolved"] += 1
                    return self.try_move(another_pending_block)
                else:
                    another_pending_block.log.append(
                        "❌ sibling move failed to resolve"
                    )

        return None

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
                self.stack.pop()
                self.index += 1
                continue

            else:  # move
                assert block.type_ == "move", f"Unexpected block type: {block.type_}"

            # TODO: var #90 Ng3, Ngf1, has a syzygy of knight moves that confound
            # and delight our parser! even if rare we should be able to handle this
            # with a little care...

            # TODO: there is a board state handling problem,
            # illustrated by #90.1659 - may be a rare case but
            # also great for forcing us to get it right

            self.increment_move_count(block)
            pending_block = self.try_move(block, pending=True)

            if pending_block.is_resolved:
                pending_distance = pending_block.raw_to_resolved_distance
                if self.current.move_counter == 1:
                    self.stats.first_move_distances[pending_distance] += 1
                else:
                    self.stats.other_move_distances[pending_distance] += 1

            if self.is_duplicate_of_root_block(pending_block):
                self.index += 1
                continue

            if root_sibling := self.get_root_sibling(pending_block):
                resolved_blocks.append(root_sibling)
                self.index += 1
                continue

            # if pending_block.is_resolved:
            #     raw = tuple(pending_block.move_parts_raw)
            #     resolved = tuple(pending_block.move_parts_resolved)

            #     if pending_distance == 0:
            #         # distance = 0: no doubt this is the move we want
            #         # distance = -1: AMBIGUOUS ➤ there's a good chance this
            #         #                is it, maybe enough to just go for it 🚀
            #         # distance = 1: *maybe* okay, seems there are some number
            #         #               of variations that are off by 1 ply
            #         self.try_move(block, pending=False)
            #         pending_block = None
            #         self.index += 1
            #         resolved_blocks.append(block)

            #         if block.raw_to_resolved_distance == 1:
            #             block.log.append(
            #                 "📉 Distance off by 1 after resolving. Going with it... "
            #                 f"{raw} ➤ {resolved}"
            #             )
            #         continue
            #     else:
            #         # example: chesser #1169, chessable #42465164 4...Nf6
            #         # issue with subvar parens -- looks like chessable self-heals;
            #         # maybe when we're on a new subvar and get this, we could
            #         # try ending the previous subvar?

            #         # example chesser #90, Ng3 -- Ngf1 fails and then resolves as
            #         # a sibling move -- next subvar we resolve Ng3 but not c5?
            #         #   move #1659 - interesting case of either knight reaching
            #         # g3 -- this illustrates getting it wrong where we accepted
            #         # off-by-one above and it breaks the subvar - will see if
            #         # we can be more discerning about this...

            #         # if move_distance > 2:
            #         #     print(block.depth, self.mainline_move.text)
            #         #     break point

            #         block.log.append(
            #             "📌 Distance too far off after resolving: "
            #             f"{pending_distance}. "
            #             f"{raw} ➤ {resolved}"
            #         )
            #         self.stats.sundry["distance_too_far"] += 1

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

            # should next try going back to start of each nested root
            # in particular there might be a fenseq pattern...

            # if pending_block:
            #     # TODO: leftover "too far" distance to be handled...
            #     # 😬 need much better handling here to make sure we're
            #     # maintaining and reading board state properly...

            self.try_move(block, pending=False)
            resolved_blocks.append(block)
            self.index += 1

        # could have a checksum of len self.blocks - a discarded count
        return resolved_blocks


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
    blocks = [ParsedBlock("start", depth=DEPTH, fen=fen)]

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
