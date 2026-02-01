import re
from io import StringIO

import chess
import chess.pgn

from chesser import util

# PGN directives like [%csl ...] and [%cal ...]
_DIRECTIVE_RE = re.compile(r"\[%([a-zA-Z]+)\s+([^\]]*)\]")

_CAL_CSL_COLORS = {"G": "green", "R": "red", "B": "blue", "Y": "yellow"}
_SQUARE_RE = re.compile(r"^[a-h][1-8]$")
_ARROW_RE = re.compile(r"^[a-h][1-8][a-h][1-8]$")

# NAG = Numeric Annotation Glyphs (PGN supports either NAG numbers or glyphs)
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


def primary_glyph(nags: set[int]) -> str:
    for n in (1, 2, 3, 4, 5, 6):
        if n in nags:
            return NAG_LOOKUP[n]
    return ""


def nags_to_glyphs(nags: set[int]) -> str:
    # Prefer common punctuation-style NAGs in a stable order,
    # then append any other known NAGs (e.g. =, ±, ∞) deterministically.
    common = [1, 2, 3, 4, 5, 6]
    rest = sorted(n for n in nags if n not in common)
    order = common + rest
    return "".join(NAG_LOOKUP[n] for n in order if n in nags and n in NAG_LOOKUP)


def get_mainline_moves_str(moves):
    white_to_move = True
    move_string = ""
    for move in moves:
        prefix = f"{move['move_num']}." if white_to_move else ""
        white_to_move = not white_to_move
        move_string += f"{prefix}{move['san']} "
    return move_string.strip()


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

        moves.append(
            {
                "move_num": move_number,
                "san": san,
                "annotation": primary_glyph(next_node.nags),
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


def move_token(parent_board, move, nags: set[int], force_number: bool) -> str:
    san = parent_board.san(move) + nags_to_glyphs(nags)

    # White moves always get a number
    if parent_board.turn == chess.WHITE:
        return f"{parent_board.fullmove_number}.{san}"

    # Black moves only get "..."" if forced
    if force_number:
        return f"{parent_board.fullmove_number}...{san}"

    return san


def render_variation_line(start: chess.pgn.GameNode) -> str:
    """
    Render a variation starting at `start` (a move node), continuing down its mainline.
    Prints move numbers and keeps the important ordering:
      - print a move
      - its comment
      - then (at each position) print main reply first, then sibling alternatives
    """
    parts: list[str] = []
    cur: chess.pgn.GameNode | None = start

    # At the start of a variation, Black moves should show "..."
    force_number = True

    while cur is not None and cur.move is not None:
        parent = cur.parent
        pb = parent.board()

        parts.append(move_token(pb, cur.move, cur.nags, force_number))

        # Once we print a move, continuation is smooth again
        force_number = False

        if cur.comment:
            parts.append(f"{{{cur.comment.strip()}}}")
            # After a comment, black move numbers should restart
            force_number = True

        # If there is a continuation, we want:
        #   main next move, its comment, then sibling alternatives at that
        #   same position, then continue beyond the main next move.
        if cur.variations:
            main = cur.variations[0]

            # emit the main next move immediately (so siblings appear "after" it)
            nb = cur.board()  # position after cur.move (i.e., before next ply)
            parts.append(move_token(nb, main.move, main.nags, force_number))
            force_number = False

            if main.comment:
                parts.append(f"{{{main.comment.strip()}}}")
                force_number = True

            # emit sibling alternatives to that next ply
            for alt in cur.variations[1:]:
                parts.append(f"({render_variation_line(alt)})")
                force_number = True  # variation break resets numbering

            # continue from main's continuation (already emitted main's token/comment)
            cur = main.variations[0] if main.variations else None
        else:
            cur = None

    return " ".join(parts).strip()


def extract_move_text(node: chess.pgn.GameNode) -> str:
    parts: list[str] = []

    # 1) comment on the move itself
    if node.comment:
        parts.append(f"{{{node.comment.strip()}}}")

    # 2) sibling alternatives to THIS move (i.e., other replies at the parent position)
    # attach them to the mainline move only (which is what your loop is iterating)
    if node.parent is not None:
        for alt in node.parent.variations[1:]:
            if alt is not node:
                parts.append(f"({render_variation_line(alt)})")

    return "\n\n".join(parts).strip()


def extract_pgn_directives(text: str) -> tuple[str, list[dict]]:
    """
    Extract Lichess/ChessBase-style PGN directives from comment text:
      - [%csl ...] => circles
      - [%cal ...] => arrows
    Discard all other directives (e.g. clk/eval) by stripping them from text.
    Returns (text_without_directives, shapes).
    """
    if not text:
        return "", []

    shapes: list[dict] = []

    def add_circle(color_letter: str, sq: str):
        brush = _CAL_CSL_COLORS.get(color_letter)
        if not brush or not _SQUARE_RE.match(sq):
            return
        shape = {"orig": sq, "brush": brush}
        if shape not in shapes:
            shapes.append(shape)

    def add_arrow(color_letter: str, coords: str):
        brush = _CAL_CSL_COLORS.get(color_letter)
        if not brush or not _ARROW_RE.match(coords):
            return

        orig = coords[:2]
        dest = coords[2:]

        # Treat "arrow to self" as a circle highlight
        if orig == dest:
            shape = {"orig": orig, "brush": brush}
        else:
            shape = {"orig": orig, "dest": dest, "brush": brush}

        if shape not in shapes:
            shapes.append(shape)

    for m in _DIRECTIVE_RE.finditer(text):
        key = m.group(1).lower()
        payload = (m.group(2) or "").strip()

        if key == "csl":
            # Example payload: "Rf3,Yd4"
            for token in re.split(r"[\s,]+", payload):
                if token:
                    add_circle(token[0], token[1:])
        elif key == "cal":
            # Example payload: "Gg4f3,Rc1h6"
            for token in re.split(r"[\s,]+", payload):
                if token:
                    add_arrow(token[0], token[1:])

    # strip all directives (including csl/cal, eval, clk, etc.)
    cleaned = _DIRECTIVE_RE.sub("", text)
    if cleaned != text:
        # there were directives: strip remaining leading space and other extra
        # (be careful not to strip newlines; we should have better tests...)
        cleaned = re.sub(r"^\s*{ +", "{", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r" +", " ", cleaned).strip()

    if cleaned in ("{}", "{ }"):
        cleaned = ""

    return cleaned, shapes
