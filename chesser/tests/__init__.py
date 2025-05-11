import re
from collections import Counter

import chess

from chesser import move_resolver
from chesser.move_resolver import ParsedBlock


def make_comment_block(raw, display, depth=1):
    return ParsedBlock(type_="comment", raw=raw, display_text=display, depth=depth)


def make_move_block(raw, fen="", depth=1):
    """relying on a core function of the move resolving engine"""
    mpr = move_resolver.get_move_parts(raw)
    return ParsedBlock(type_="move", raw=raw, move_parts_raw=mpr, fen=fen, depth=depth)


def make_subvar_block(type_, fen="", depth=1):
    return ParsedBlock(type_=type_, fen=fen, depth=depth)


def get_parsed_blocks_from_string(pgn_string: str, depth=0, move_str_unbalanced=False):
    """
    Takes a structured PGN string and returns a list of ParsedBlock objects.

    e.g.
    ( 1.e4 e5 )                 spaces are required for chunking things
    ( 1.e4 {comment} 1...e5 )   no spaces in comments to make it easier to parse
    ( 1.e4 ( 1.d4 2.d5 ) 1...e5 )
    (F<fen> 1.d4 d5)            anything after F is used as a fen, to emulate fenseq
                                (spaces won't work since we split on them - convert
                                 them to underscores)

    outer parens are optional; they'll be added around the whole pgn_string
    only if no parens are found; we can test things out of a subvar, too:
    {comment} ( 1.e4 e5 ) {comment}

    move_str_unbalanced allows us to test deliberately unbalanced PGN strings,
    but we have to be deliberate about it!
    """
    if "(" not in pgn_string:
        pgn_string = f"( {pgn_string} )"

    starting_depth = depth
    blocks = []
    bits = pgn_string.split()
    for bit in bits:
        if bit.startswith("("):
            depth += 1
            fen = bit[2:].replace("_", " ") if bit.startswith("(F") else ""
            blocks.append(make_subvar_block("start", fen=fen, depth=depth))
        elif bit.startswith(")"):
            blocks.append(make_subvar_block("end", depth=depth))
            depth -= 1
        elif bit.startswith("{"):
            blocks.append(make_comment_block(bit, bit[1:-1], depth=depth))
        else:
            blocks.append(make_move_block(bit, depth=depth))

        if move_str_unbalanced is False:
            assert depth >= 0, "Unbalanced parens in pgn string"

    if move_str_unbalanced is False:
        assert depth == starting_depth, "Unbalanced parens in pgn string"

    return blocks


def get_boards_after_moves(moves: str):
    board = chess.Board()
    index = {}
    for san in moves.split():
        board.push_san(san)
        index.setdefault(san, []).append(board.copy())
    return index


def merge_boards(*move_strings: str) -> dict[str, list[chess.Board]]:
    """
    Merge multiple SAN sequences into a dict of SAN → list[Board].

    Keeps all occurrences to support duplicate SANs like Nxd4 Nxd4.
    Test harness will resolve them by order; extras are harmless.
    """
    merged = {}
    for moves in move_strings:
        new = get_boards_after_moves(moves)
        for san, boards in new.items():
            merged.setdefault(san, []).extend(boards)
    return merged


def make_pathfinder(blocks, mainline_verbose, board=None, move_id=1234):
    board = board or chess.Board()
    return move_resolver.PathFinder(blocks, move_id, mainline_verbose, board, None)


def get_verbose_sans_list(blocks: list[ParsedBlock]):
    """
    ParsedBlock.move_verbose will look for and return in order:
    1) assembed move parts resolved (num/dots/san/annotations)
    2) assembled move parts raw (whatever parts are available)
    3) raw
    """
    return [b.move_verbose for b in blocks if b.type_ == "move"]


def assert_expected_fens(boards, blocks, expected_sans):
    """
    Asserts that the list of move blocks has FENs matching those expected
    from the reference board positions in `boards`.

    Parameters:
    ----------
    boards : dict[str, list[chess.Board]]
        A mapping of SAN → list of Board objects, in the order they occurred.
        This supports scenarios where the same SAN appears multiple times in
        a variation (e.g., 4.Nxd4 Nxd4 in the Scotch).

    blocks : list[ParsedBlock]
        The resolved blocks from the parser. We will pull all 'move' blocks
        and check their .fen values.

    expected_sans : list[str]
        The expected simple sans, one per move block. These can be derived
        from verbose move strings as they are in assert_resolved_moves(), or
        just supplied when we need to indicate unresolved fen-less moves.

    Behavior:
    --------
    - For each SAN in `expected_sans`, we look up the corresponding
      board in the `boards` dictionary.
    - If the same SAN appears multiple times, we use a Counter to track
      which index to pull from the list — this disambiguates duplicate SANs.
    - If the SAN is not found or the index is out of range, we insert an
      empty string for comparison.

    Example:
    --------
    Suppose this sequence:

        moves = "e4 e5 Nf3 Nc6 d4 exd4 Nxd4 Nxd4"

    Produces this dictionary from `get_boards_after_moves()`:

        boards = {
            "e4": [<Board1>],
            "e5": [<Board2>],
            "Nf3": [<Board3>],
            "Nc6": [<Board4>],
            "d4": [<Board5>],
            "exd4": [<Board6>],
            "Nxd4": [<Board7>, <Board8>]  # White and Black Nxd4
        }

    And your expected sans are:

        expected_sans = ["e5", "Nf3", "Nc6", "d4", "exd4", "Nxd4", "Nxd4"]

    This function will:
        - Track each SAN using Counter()
        - Lookup:
            boards["e5"][0]
            boards["Nf3"][0]
            ...
            boards["Nxd4"][0]  ← White
            boards["Nxd4"][1]  ← Black

    And assert that the corresponding move blocks have matching `.fen` values.
    """

    # 🔁 Resolve each SAN to its FEN using positionally disambiguated list
    counters = Counter()
    expected_fens = []
    for san in expected_sans:
        if not san.strip():
            expected_fens.append("")
            continue
        board_list = boards.get(san, [])
        idx = counters[san]
        board = board_list[idx] if idx < len(board_list) else None
        expected_fens.append(board.fen() if board else "")
        counters[san] += 1

    move_fens = [b.fen for b in blocks if b.type_ == "move"]

    if move_fens != expected_fens:
        expected_lines = [
            f"{san:<8} ➤ {fen}" for san, fen in zip(expected_sans, expected_fens)
        ]
        actual_lines = [
            f"{b.move_verbose:<8} ➤ {b.fen}" for b in blocks if b.type_ == "move"
        ]

        raise AssertionError(
            f"\nExpected FENs:\n{chr(10).join(expected_lines)}\n\n"
            f"Actual FENs:\n{chr(10).join(actual_lines)}"
        )


def resolve_subvar(move_str, root_move_str, root_board, move_str_unbalanced=False):
    blocks = get_parsed_blocks_from_string(
        move_str, move_str_unbalanced=move_str_unbalanced
    )
    pf = make_pathfinder(blocks, root_move_str, root_board)
    return pf.resolve_moves()


def assert_resolved_moves(
    *,
    boards: dict[str, list[chess.Board]],
    root_move: str,
    root_board: chess.Board,
    move_str: str,
    move_str_unbalanced: bool = False,
    expected: list[str],
    expected_fens_san_keys: list[str] = None,
):
    """
    boards:
        A dict of SANs ➤ board mappings. These serve
        as reference board states after moves, providing a starting
        board for mainline sans, and fens for those positions.
        Duplicate SANs are supported and resolved in positional
        order via Counter-based indexing during FEN matching.
        (We can handle the Scotch 4.Nxd4 Nxd4 with this.)

    root_move:
        The mainline move that is the root of all "move.text"
        subvars. This will be a proper fully resolved move,
        less annotation, e.g.: 1.e4 or 1...e5

    root_board:
        The board state after the mainline root_move.

    move_str:
        A structured test move string with moves and comments,
        following rules in get_parsed_blocks_from_string.

        Can use all-caps SANs (e.g. BAD, 4...LAD) to mark expected
        unplayable moves. They'll pass move parsing and be obvious.

        Moves must be quite normalized, no spaces, obvs. Balanced
        subvar farens are required unless allow_unbalanced is True.

            move_str_unbalanced:
        If True, allows parsing of a deliberately unbalanced `move_str`
        (e.g. an open subvar not closed before a fenseq). This is only for
        tests and has no effect on the move parser itself.

        If True, allows tests to pass in intentionally unbalanced PGN-like
        strings (e.g. open subvars not closed). This flag is strictly for the
        test harness and disables the default assertion that checks for
        matching parentheses in the parsed blocks.

        This is useful when importing known edge-case strings (e.g. from
        Chessable pipelines) that lead into fenseq blocks or similar recovery
        cases. It does NOT affect the underlying move parser behavior.

    expected:
        List of expected moves. These are the best moves we can
        extract from the resolved moves, whether fully resolved
        and playable or just raw moves that may or may not be valid

        e.g.:
        ( 1.e4 e5 ) -> ["1.e4", "1...e5"]
        ( 1.e4 e5 ( 1...d5 ) ) -> ["1.e4", "1...e5", "1...d5"]
        ( 1.e4 e5 ( 1...BAD ) {comment} ) -> ["1.e4", "e5", "1...BAD"]

        And then it can also determine expected fens for these moves
        if expected_fens_san_keys is not provided, whether or not they
        resolve. (Works well for many tests, but when there's more
        ambiguity it may be tricky to interpret results/errors.)

    expected_fens_san_keys:
        A list of SANs to look up reference FEN strings
        for playable moves, and empty strings for unplayable moves.

        If this is omitted, everything in expected should be properly
        resolve as a fen or "" based on sans extracted from `expected`.

        Even if expected tells the tale, this can be good for clarity.
        And sometimes this will be requird to get it right, e.g. in:
        test_resolve_moves_fenseq_does_not_do_normal_first_move_things
    """
    blocks = resolve_subvar(
        move_str, root_move, root_board, move_str_unbalanced=move_str_unbalanced
    )
    verbose_sans = get_verbose_sans_list(blocks)
    assert verbose_sans == expected, f"\nExpected: {expected}\nActual:   {verbose_sans}"

    if not expected_fens_san_keys:
        sans = " ".join(expected)
        sans = re.sub(r"\b\d+\.+", "", sans)  # remove numbers and dots
        expected_fens_san_keys = sans.split()  # really, the san keys to boards dict

    assert_expected_fens(boards, blocks, expected_fens_san_keys)

    return blocks
