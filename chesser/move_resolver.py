import re
from collections import defaultdict, namedtuple
from copy import copy
from dataclasses import dataclass, field
from typing import Literal, Optional

import chess

from chesser.models import Move

AMBIGUOUS = -1

"""
Previously Parser v2 in serializers.py

Possible further breakdown?

Chunk and ParsedBlock logic → parser_blocks.py
PathFinder and ResolveStats → resolver.py
Keep move_resolver.py as an integration layer
"""


@dataclass
class Chunk:
    type_: Literal["comment", "move", "fenseq", "subvar"]
    data: str


MoveParts = namedtuple("MoveParts", ["num", "dots", "san", "annotation"])


def assemble_move_parts(move_parts: MoveParts) -> str:
    """Create "verbose" string representation."""
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
    display_text: str = ""
    # raw comes from a move as it appears in a subvar, it may or may not have
    # a move number and dots, e.g. 1.e4 or e4 or 1...e5 or e5
    move_parts_raw: Optional[MoveParts] = None
    # resolved moves have had their SAN run through a chess.Board and *if*
    # they were valid, will have been "resolved" with a move number and dots
    # to tell us exactly what ply/move we're on; it's possible that after
    # "playing" the SAN, we ended up on a different move number/dots than
    # expected! then we can look at "distance" to see the state of things
    move_parts_resolved: Optional[MoveParts] = None
    # use distance to make decisions about path and in some cases repair broken subvars
    # AMBIGUOUS means we don't know: maybe we resolved to 1...e5 but only had e5
    raw_to_resolved_distance: int = AMBIGUOUS  # unknown to start
    # for move blocks: fen representing state after this move (normal link rendering)
    # for start blocks: fen representing state before the sequence;
    #                   i.e. fenseq/@@StartFEN@@, enables rendering ⏮️ as a link
    fen: str = ""
    depth: int = 0  # for subvar depth tracking
    log: list[str] = field(default_factory=list)

    @property
    def is_playable(self):
        return self.type_ == "move" and self.move_parts_resolved is not None

    def clone(self):
        new = copy(self)
        new.log = self.log.copy()
        return new

    def equals_raw(self, other):
        # pre-resolved moves have num/dots/san and are the same
        # other than annotations which are ignored here
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
    # ad hoc stats, just needs a unique label to count
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
      [a-zA-Z0-9]           # last san char usually a number but could be cap
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
      (currently: not allowing spaces between number and dots)
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
            annotation=(m.group(4) or "").strip(),
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
    """
    if raw_move_parts.num is None or raw_move_parts.dots not in (".", "..."):
        return AMBIGUOUS
    elif resolved_move_parts is None:
        err = f"resolved_move_parts not provided; raw_move_parts = {raw_move_parts}"
        raise ValueError(err)

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
    # resolved moves AND passed through moves are added here
    resolved_stack: list[ParsedBlock] = field(default_factory=list)

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
        self.resolved_blocks = []  # "finished" blocks, whether or not truly "resolved"
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

    def handle_start_block(self, block: ParsedBlock):
        if block.fen:
            # fenseq; let's try to mostly treat same as subvar
            chessboard = chess.Board(block.fen)
            self.stats.sundry["subfen"] += 1
        else:
            chessboard = self.current.board.copy()
            self.stats.sundry["subvar"] += 1
            self.stats.subvar_depths[block.depth] += 1

        if block.depth == 1 or not self.current.resolved_stack:
            root_block = self.current.root_block.clone()
        else:  # else use the last of current resolved moves, or could
            # be a passed through move where things will be expected to 🧨
            root_block = self.current.resolved_stack[-1].clone()

        # the original root root will always remain 0
        root_block.depth = block.depth

        self.stack.append(StackFrame(board=chessboard, root_block=root_block))

        block.log.append("stack")
        for frame in self.stack:
            fen = frame.board.fen()
            message = f"\t{frame.root_block.raw} ➤ {frame.root_block.depth} ➤ {fen}"
            block.log.append(message)

    def parse_move(self, block: ParsedBlock) -> ParsedBlock:
        assert block.type_ == "move"
        clone = block.clone()
        board = self.current.board.copy()
        san = clone.move_parts_raw.san

        try:
            move_obj = board.parse_san(san)
        except (
            chess.IllegalMoveError,
            chess.InvalidMoveError,
            chess.AmbiguousMoveError,
        ) as e:
            clone.log.append(
                f"❌ parse_san {e}: {san} | board move "
                f"{board.fullmove_number}, white turn {board.turn}"
            )
            # seems plausible that an already parsed move could be handed in,
            # having been made illegal on its journey, so we should unresolve it
            clone.move_parts_resolved = None
            return clone

        board.push(move_obj)
        self.stats.sundry["moves resolved"] += 1

        # turn = True means it's white's move *now*, so we reverse things
        # to figure out dots for move just played

        move_parts_resolved = MoveParts(
            num=(board.ply() + 1) // 2,
            dots="..." if board.turn else ".",
            san=san,
            annotation=clone.move_parts_raw.annotation,
        )

        resolved_move_distance = get_resolved_move_distance(
            move_parts_resolved, clone.move_parts_raw
        )

        clone.move_parts_resolved = move_parts_resolved
        clone.raw_to_resolved_distance = resolved_move_distance
        clone.fen = board.fen()

        clone.log.append(
            f"Resolved ➤ {tuple(clone.move_parts_raw)} ➤ "
            f"{tuple(clone.move_parts_resolved)}"
        )

        return clone

    def push_move(self, block: ParsedBlock):
        assert block.type_ == "move"
        if block.is_playable:
            try:
                move_obj = self.current.board.parse_san(block.move_parts_raw.san)
            except Exception:
                # TODO we don't expect this if we're properly parsing/pushing/etc,
                # but it's happening with many variations today, e.g. #881 6.Qc1
                # move id 17638 - that one is a broken subvar - should find out
                # if it's a bug or needs a guard, etc.
                move_parts = tuple(block.move_parts_raw)
                message = f"🚨 Error on parse_san during push_move {move_parts}"
                block.log.append(message)
                self.stats.sundry["push_move error"] += 1  # about 25 of these
            else:
                self.current.board.push(move_obj)
                self.stats.sundry["moves pushed"] += 1

        self.current.resolved_stack.append(block)

    def pass_through_move(self, block: ParsedBlock):
        assert block.type_ == "move"
        # this is a counterpart to push_move, to share
        # its resolved stack side effect
        self.stats.sundry["moves passed thru"] += 1
        self.current.resolved_stack.append(block)

    def increment_move_count(self, block: ParsedBlock):
        # move count whether pass or fail; in particular we want to know
        # when we're on the first move of a subvar to compare against mainline
        self.current.move_counter += 1
        label = "first" if self.current.move_counter == 1 else "other"
        if block.move_parts_raw.num:
            self.stats.sundry[f"~ {label} moves has num"] += 1
        dots = block.move_parts_raw.dots if block.move_parts_raw.dots else "none"
        self.stats.sundry[f"~ {label} moves dots {dots}"] += 1
        self.stats.sundry["moves evaluated"] += 1

    def attach_log_to_previous_start_block(self, log_message: str):
        # go backwards through resolved blocks until we find a start block
        for block in self.resolved_blocks[::-1]:
            if block.type_ == "start":
                block.log.append(log_message)
                break

    def is_duplicate_of_root_block(self, block: ParsedBlock):
        # e.g. mainline 1.e4, subvar (1.e4 e5)
        if self.current.move_counter == 1 and block.equals_raw(self.current.root_block):
            # we'll update stats and log this even though we're not *doing*
            # the discarding in here; it just seems cleaner to keep here
            self.stats.sundry["➤ root dupe discarded"] += 1
            self.attach_log_to_previous_start_block(
                "🗑️  Discarding move block same as root: " f"{block.move_parts_raw}"
            )
            return True
        else:
            return False

    def get_root_sibling(self, block: ParsedBlock):
        # e.g. mainline 1.e4, subvar (1.d4 d5)
        if (
            self.current.move_counter == 1
            and self.current.board_previous
            and self.current.root_block.is_playable
        ):
            distance_from_root = get_resolved_move_distance(
                self.current.root_block.move_parts_resolved, block.move_parts_raw
            )
            if distance_from_root == 0:
                self.stats.sundry["➤ root siblings"] += 1
                self.current.board = self.current.board_previous.copy()

                pending_block = self.parse_move(block)

                if pending_block.is_playable:
                    pending_block.log.append("👥 sibling move resolved 🔍️")
                    self.stats.sundry["➤ root siblings resolved"] += 1
                    return pending_block
                else:
                    pending_block.log.append("❌ sibling move failed to resolve")

        return None

    def get_alternate_move(self, block: ParsedBlock):
        # e.g. (1.e4 e5 2.Nf3 {or} 2.Nc3 {or} 2.d4)
        # ➤ we'll say it must be a "full" move, with num and dots, so we cna
        #   properly assess relationship
        # ➤ should we only count it as an alternate if it follows a comment?

        # we need a counterpart to equals_raw to check for same move num/dots
        # but not same san, and maybe we compare current raw to previous resolved
        block.log.append("↗️  alternate move check will happen here ↗️")
        self.stats.sundry["➤ alternate move getter/checker"] += 1
        return None

    def advance_to_next_block(self, append: Optional[ParsedBlock] = None):
        if append:
            self.resolved_blocks.append(append)

            if append.is_playable:
                pending_distance = append.raw_to_resolved_distance
                if self.current.move_counter == 1:
                    self.stats.first_move_distances[pending_distance] += 1
                else:
                    self.stats.other_move_distances[pending_distance] += 1

        self.index += 1

    def resolve_moves(self) -> list[ParsedBlock]:

        while self.index < self.end_of_list:
            block = self.blocks[self.index]

            if block.type_ == "comment":
                self.advance_to_next_block(append=block)
                continue

            elif block.type_ == "start":
                self.handle_start_block(block)
                self.advance_to_next_block(append=block)
                continue

            elif block.type_ == "end":
                self.stack.pop()
                self.advance_to_next_block(append=block)
                continue

            else:  # move
                assert block.type_ == "move", f"Unexpected block type: {block.type_}"

            """
            TODO: examples

            90.1659 Ng3, Ngf1, has a syzygy of knight moves that are a good test

            chesser #1169, chessable #42465164 4...Nf6 issue with subvar parens -- looks like chessable self-heals; maybe when we're on a new subvar and get this, we could try ending the previous subvar?

            "implied" subvariations
            e.g. (1.e4 e5 2.Nf3 {or} 2.Nc3 {or} 2.d4)

            #881 6.Qc1 move id 17638 - this is a broken subvar and one I'm not sure we should try fixing on the fly, although we *might* end trying different subvar searching strategies between subvars, since it may be common enough that it would be great if we could smartly handle it
            6.Qc1 (6.Nc3 6...Nxc3)(6.Qa5) should be 6...Qa5 and also shouldn't be a new subvar
                consider that one considered strategy is to go back to mainline root, but that would break things here! (keep gathering cases...) (this is a good case for root sibling...)

            <fenseq data-fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1">1.c4 e6 2.Nf3 d5 3.b3 { or } 1.c4 e6 2.Nf3 d5 3.g3 Nf6 4.b3 {...} 1.c4 e6 2.Nf3 d5 3.b3 {...} 3...d4 {...}</fenseq>

            variation 754, move 14950, mainline 2.Nc3
            <fenseq data-fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1">1.d4 d5 2.c4 e6 3.Nc3 {...} 2.Nc3 {...} 2...Nf6 {...}</fenseq>

            variation 754, move 14958, mainline 6.f3
            <fenseq data-fen="rn1qkb1r/pp2pppp/5n2/3p4/3P1Bb1/2N5/PPP2PPP/R2QKBNR w KQkq - 1 6">6.Nf3 Nc6 {...} 6.Qd2 {, but after} 6...Nc6 {, they will probably play} 7.f3 {anyway, which transposes to 6.f3 after all.}</fenseq>
            """  # noqa: E501

            self.increment_move_count(block)
            pending_block = self.parse_move(block)

            if pending_block.is_playable and pending_block.raw_to_resolved_distance > 1:
                # let's be strict to get a better feel for the data, off by
                # more than one will need special handling and we'll apply
                # that in order below, for now we just pass it through
                self.stats.sundry["➤ strictly: initial dist > 1"] += 1
                self.pass_through_move(pending_block)
                self.advance_to_next_block(append=pending_block)
                continue

            # "handled" cases ------------------------------------------------

            if self.is_duplicate_of_root_block(pending_block):
                self.advance_to_next_block(append=None)
                continue

            if root_sibling := self.get_root_sibling(pending_block):
                self.push_move(root_sibling)
                self.advance_to_next_block(append=root_sibling)
                continue

            # if alternate move
            if alternate_move := self.get_alternate_move(pending_block):
                self.push_move(alternate_move)
                self.advance_to_next_block(append=alternate_move)
                continue

            # fall through ---------------------------------------------------

            # until we handle more cases above, this is going to be error prone

            # temporarily more strict with requiring < 1 distance; later
            # we can probably repair a lot of cases but for now we want to
            # see where things are failing, so we just pass through those > 0

            if (
                pending_block.is_playable
                and pending_block.raw_to_resolved_distance <= 1
            ):
                self.push_move(pending_block)
            else:
                self.stats.sundry["➤ strictly: thru fall dist > 1"] += 1
                self.pass_through_move(pending_block)

            self.advance_to_next_block(append=pending_block)

        return self.resolved_blocks


def get_parsed_blocks_first_pass(chunks: list[Chunk]) -> list[ParsedBlock]:
    parsed_blocks = []
    i = 0
    depth = 0

    while i < len(chunks):  # ➡️ Every branch must advance `i`
        chunk = chunks[i]

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
