import re
from collections import Counter

import chess
import pytest

from chesser import move_resolver
from chesser.move_resolver import Chunk, MoveParts, ParsedBlock


def make_comment_block(raw, display, depth=1):
    return ParsedBlock(type_="comment", raw=raw, display_text=display, depth=depth)


def make_move_block(raw, fen="", depth=1):
    """relying on a core function of the move resolving engine"""
    mpr = move_resolver.get_move_parts(raw)
    return ParsedBlock(type_="move", raw=raw, move_parts_raw=mpr, fen=fen, depth=depth)


def make_subvar_block(type_, fen="", depth=1):
    return ParsedBlock(type_=type_, fen=fen, depth=depth)


@pytest.mark.parametrize(
    "text,expected_chunks",
    [
        ("", []),  # Empty string
        (" ", [Chunk("comment", "{ }")]),  # Whitespace only
        (" \n ", [Chunk("comment", "{ \n }")]),  # Whitespace only
        (  # Single line, unbraced
            "Just a simple freeform comment.",
            [Chunk("comment", "{Just a simple freeform comment.}")],
        ),
        (  # Multiple sentences and newlines, still implied
            "Freeform comment. Another line.\nYet more.\n\n",
            [Chunk("comment", "{Freeform comment. Another line.\nYet more.\n\n}")],
        ),
        (  # Implied comment with subvar interrupt
            "comment start (1.e4 e5)",
            [
                Chunk("comment", "{comment start }"),
                Chunk("subvar", "START 1"),
                Chunk("move", "1.e4"),
                Chunk("move", "e5"),
                Chunk("subvar", "END 1"),
            ],
        ),
        (  # Implied comment with fenseq interrupt
            "Some note <fenseq data-fen='...'>1...c5</fenseq>",
            [
                Chunk("comment", "{Some note }"),
                Chunk("fenseq", "<fenseq data-fen='...'>1...c5</fenseq>"),
            ],
        ),
        (  # Implied with trailing closing brace
            "Hello world }",
            [Chunk("comment", "{Hello world }")],
        ),
        (  # Implied followed by explicit comment
            "Hello {world}",
            [
                Chunk("comment", "{Hello }"),
                Chunk("comment", "{world}"),
            ],
        ),
        (  # Explicit followed by implied
            "{Hello} world",
            [
                Chunk("comment", "{Hello}"),
                Chunk("comment", "{ world}"),
            ],
        ),
        (  # Explicit missing closing brace (we'll not assert the print for now)
            "{Hello world",
            [Chunk("comment", "{Hello world}")],
        ),
        (  # Leftover whitespace treaated as a comment
            "{Hello world}   \n",
            [
                Chunk("comment", "{Hello world}"),
                Chunk("comment", "{   \n}"),
            ],
        ),
    ],
)
def test_extract_ordered_chunks_comments(text, expected_chunks):
    actual = move_resolver.extract_ordered_chunks(text)
    assert actual == expected_chunks


def test_extract_ordered_chunks_assertions():
    with pytest.raises(AssertionError) as excinfo:
        move_resolver.extract_ordered_chunks("{abc{")
    assert str(excinfo.value) == "Unexpected opening brace in comment chunk"

    with pytest.raises(AssertionError) as excinfo:
        move_resolver.extract_ordered_chunks("{abc <fenseq")
    assert str(excinfo.value) == "Unexpected <fenseq> tag in comment chunk"


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            '<fenseq data-fen="...">1.e4</fenseq>',
            [Chunk("fenseq", '<fenseq data-fen="...">1.e4</fenseq>')],
        ),
        (
            "<fenseq>1.e4</fenseq>",
            [Chunk("fenseq", "<fenseq>1.e4</fenseq>")],
        ),
        (
            "<fenseq>1.e4</fenseq><fenseq>1.d4</fenseq>",
            [
                Chunk("fenseq", "<fenseq>1.e4</fenseq>"),
                Chunk("fenseq", "<fenseq>1.d4</fenseq>"),
            ],
        ),
        (  # broken fenseq turns into comment
            "{testing}<fenseq>1.e4",
            [
                Chunk("comment", "{testing}"),
                Chunk("comment", "{<fenseq>1.e4}"),
            ],
        ),
        (  # broken fenseq turns everything into comment
            "<fenseq>1.e4 (1.d4 d5)",
            [
                Chunk("comment", "{<fenseq>1.e4 (1.d4 d5)}"),
            ],
        ),
        (
            "{testing}<fenseq>1.e4</fenseq> more text...",
            [
                Chunk("comment", "{testing}"),
                Chunk("fenseq", "<fenseq>1.e4</fenseq>"),
                Chunk("comment", "{ more text...}"),
            ],
        ),
        (  # known fixable paren imbalance
            "(1.e4 {test}<fenseq>1.e4</fenseq>",
            [
                Chunk("subvar", "START 1"),
                Chunk("move", "1.e4"),
                Chunk("comment", "{test}"),
                Chunk("subvar", "END 1"),
                Chunk("fenseq", "<fenseq>1.e4</fenseq>"),
            ],
        ),
    ],
)
def test_extract_ordered_chunks_fenseq(text, expected):
    assert move_resolver.extract_ordered_chunks(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "(1.e4 e5)",
            [
                Chunk("subvar", "START 1"),
                Chunk("move", "1.e4"),
                Chunk("move", "e5"),
                Chunk("subvar", "END 1"),
            ],
        ),
        (
            "(1.e4 e5 (1...d5 2.exd5) 2.Nf3)",
            [
                Chunk("subvar", "START 1"),
                Chunk("move", "1.e4"),
                Chunk("move", "e5"),
                Chunk("subvar", "START 2"),
                Chunk("move", "1...d5"),
                Chunk("move", "2.exd5"),
                Chunk("subvar", "END 2"),
                Chunk("move", "2.Nf3"),
                Chunk("subvar", "END 1"),
            ],
        ),
        (
            "(1.e4 e5) \n <fenseq data-fen='...'>1...c5</fenseq>",
            [
                Chunk("subvar", "START 1"),
                Chunk("move", "1.e4"),
                Chunk("move", "e5"),
                Chunk("subvar", "END 1"),
                Chunk("comment", "{ \n }"),
                Chunk("fenseq", "<fenseq data-fen='...'>1...c5</fenseq>"),
            ],
        ),
        (
            "(1.e4 e5) \n <fenseq 1...c5 (1.e4 e5)",
            [
                Chunk("subvar", "START 1"),
                Chunk("move", "1.e4"),
                Chunk("move", "e5"),
                Chunk("subvar", "END 1"),
                Chunk("comment", "{ \n }"),
                Chunk("comment", "{<fenseq 1...c5 (1.e4 e5)}"),
            ],
        ),
        (  # TODO: we could/should turn this into a comment, but, meh;
            # it's unlikely and we won't deal with all cases
            '<fenseq 1...c5 <fenseq data-fen="...">1.e4</fenseq>',
            [
                Chunk("fenseq", '<fenseq 1...c5 <fenseq data-fen="...">1.e4</fenseq>'),
            ],
        ),
        (  # broken fenseq and comment could result in unbalanced
            # braces but again we won't deal with all cases
            "<fenseq 1...c5 {and a comment}",
            [
                Chunk("comment", "{<fenseq 1...c5 {and a comment}"),
            ],
        ),
        (
            "(1.e4 e5) (1.d4 d5)",
            [
                Chunk("subvar", "START 1"),
                Chunk("move", "1.e4"),
                Chunk("move", "e5"),
                Chunk("subvar", "END 1"),
                Chunk("comment", "{ }"),
                Chunk("subvar", "START 1"),
                Chunk("move", "1.d4"),
                Chunk("move", "d5"),
                Chunk("subvar", "END 1"),
            ],
        ),
        (
            "(1.e4 e5) abc (1.d4 d5)",
            [
                Chunk("subvar", "START 1"),
                Chunk("move", "1.e4"),
                Chunk("move", "e5"),
                Chunk("subvar", "END 1"),
                Chunk("comment", "{ abc }"),
                Chunk("subvar", "START 1"),
                Chunk("move", "1.d4"),
                Chunk("move", "d5"),
                Chunk("subvar", "END 1"),
            ],
        ),
        (
            "(1.e4 e5 {(}(1...d5 2.exd5){)} 2.Nf3)",
            [
                Chunk("subvar", "START 1"),
                Chunk("move", "1.e4"),
                Chunk("move", "e5"),
                Chunk("comment", "{(}"),
                Chunk("subvar", "START 2"),
                Chunk("move", "1...d5"),
                Chunk("move", "2.exd5"),
                Chunk("subvar", "END 2"),
                Chunk("comment", "{)}"),
                Chunk("move", "2.Nf3"),
                Chunk("subvar", "END 1"),
            ],
        ),
        (
            "(1.e4 e5 {A)} 2.Nf3) abc",
            [
                Chunk("subvar", "START 1"),
                Chunk("move", "1.e4"),
                Chunk("move", "e5"),
                Chunk("comment", "{A)}"),
                Chunk("move", "2.Nf3"),
                Chunk("subvar", "END 1"),
                Chunk("comment", "{ abc}"),
            ],
        ),
        (  # unbalanced
            "(1.e4 e5",
            [
                Chunk("subvar", "START 1"),
                Chunk("move", "1.e4"),
                Chunk("move", "e5"),
            ],
        ),
        (  # unbalanced
            "(1.e4 e5 (1...d5",
            [
                Chunk("subvar", "START 1"),
                Chunk("move", "1.e4"),
                Chunk("move", "e5"),
                Chunk("subvar", "START 2"),
                Chunk("move", "1...d5"),
            ],
        ),
    ],
)
def test_extract_ordered_chunks_subvar(text, expected):
    assert move_resolver.extract_ordered_chunks(text) == expected


@pytest.mark.parametrize(
    "raw, depth, expected_display",
    [
        ("   This is   a test.   ", 0, " This is a test. "),
        ("Line 1\n   Line 2", 0, "Line 1\nLine 2"),
        ("Line 1\n\n\nLine 2", 0, "Line 1\n\nLine 2"),
        ("Multiple    spaces", 0, "Multiple spaces"),
        ("  \n   \n\n\n", 0, "\n\n"),
        ("A\n   \n   \nB", 1, "A\n\nB"),
    ],
)
def test_get_cleaned_comment_parsed_block(raw, depth, expected_display):
    block = move_resolver.get_cleaned_comment_parsed_block(raw, depth)
    assert block.type_ == "comment"
    assert block.raw == raw
    assert block.display_text == expected_display
    assert block.depth == depth


@pytest.mark.parametrize(
    "chunks, expected",
    [
        (
            [
                Chunk("comment", "1"),
                Chunk("comment", " \n \n "),
                Chunk("comment", "2  3"),
            ],
            [make_comment_block("1 \n \n 2  3", "1\n\n2 3", depth=0)],
        ),
        (
            [
                Chunk("subvar", "START 1"),
                Chunk("move", "1.e4"),
                Chunk("move", "e5"),
                Chunk("subvar", "END 1"),
            ],
            [
                make_subvar_block("start"),
                make_move_block("1.e4"),
                make_move_block("e5"),
                make_subvar_block("end"),
            ],
        ),
        (
            [
                Chunk("subvar", "START 1"),
                Chunk("move", "1.e4"),
                Chunk("subvar", "START 2"),
                Chunk("move", "1... d5"),
                Chunk("subvar", "END 2"),
                Chunk("subvar", "END 1"),
            ],
            [
                make_subvar_block("start"),
                make_move_block("1.e4"),
                make_subvar_block("start", depth=2),
                make_move_block("1... d5", depth=2),
                make_subvar_block("end", depth=2),
                make_subvar_block("end"),
            ],
        ),
        (
            [
                Chunk("comment", "{hello }"),
                Chunk("subvar", "START 1"),
                Chunk("move", "1.e4"),
                Chunk("move", "e5"),
                Chunk("comment", "{ world}"),
                Chunk("subvar", "END 1"),
                Chunk("comment", "{!<br/>}"),
            ],
            [
                make_comment_block("hello ", "hello ", depth=0),
                make_subvar_block("start"),
                make_move_block("1.e4"),
                make_move_block("e5"),
                make_comment_block(" world", " world"),
                make_subvar_block("end"),
                make_comment_block("!<br/>", "!\n", depth=0),
            ],
        ),
        (
            [
                Chunk("fenseq", "<fenseq data-fen='...'>1.e4 e5 2. Nf3</fenseq>"),
            ],
            [
                make_subvar_block("start", fen="..."),
                make_move_block("1.e4"),
                make_move_block("e5"),
                make_move_block("2. Nf3"),
                make_subvar_block("end"),
            ],
        ),
    ],
)
def test_get_parsed_blocks_first_pass(chunks, expected):
    assert move_resolver.get_parsed_blocks_first_pass(chunks) == expected


def test_get_parsed_blocks_first_pass_invalid_type():
    with pytest.raises(ValueError) as excinfo:
        move_resolver.get_parsed_blocks_first_pass([Chunk("fahr", "vegnugen")])
    assert "Unknown chunk type" in str(excinfo.value)


@pytest.mark.parametrize(
    "test_input",
    [
        ('<fenseq data-fen="start_fen">1.e4 e5 2.Nf3 2...Nc6</fenseq>'),
        ("<fenseq data-fen='start_fen'>1. e4 e5 2. Nf3 2... Nc6</fenseq>"),
    ],
)
def test_parse_fenseq_chunk_valid(test_input):
    blocks = move_resolver.parse_fenseq_chunk(test_input)
    assert len(blocks) == 6
    sans = [block.move_parts_raw.san for block in blocks if block.type_ == "move"]
    expected = ["e4", "e5", "Nf3", "Nc6"]
    assert sans == expected
    assert blocks[0].fen == "start_fen"
    assert all(b.fen == "" for b in blocks[1:])
    assert all(b.depth == 1 for b in blocks)
    assert all(b.type_ == "move" for b in blocks[1:-1])
    assert (blocks[0].type_, blocks[-1].type_) == ("start", "end")


def test_parse_fenseq_chunk_with_comments():
    test_input = '<fenseq data-fen="start_fen">1.e4 {comment} e5 2.Nf3 {another comment} 2...Nc6</fenseq>'  # noqa: E501

    blocks = move_resolver.parse_fenseq_chunk(test_input)

    expected = [
        make_subvar_block("start", fen="start_fen"),
        make_move_block("1.e4"),
        make_comment_block("{comment}", "comment"),
        make_move_block("e5"),
        make_move_block("2.Nf3"),
        make_comment_block("{another comment}", "another comment"),
        make_move_block("2...Nc6"),
        make_subvar_block("end"),
    ]
    assert blocks == expected


def test_parse_fenseq_chunk_empty():
    assert (
        move_resolver.parse_fenseq_chunk('<fenseq data-fen="start_fen"> </fenseq>')
        == []
    )


def test_parse_fenseq_chunk_invalid():
    try:
        move_resolver.parse_fenseq_chunk("<fenseq>1.e4 e5</fenseq>")
    except AssertionError as e:
        assert "Invalid fenseq chunk" in str(e)


@pytest.mark.parametrize(
    "text, move_num, dots, san, annotation",
    [
        ("1.e4", 1, ".", "e4", ""),
        ("1...e5", 1, "...", "e5", ""),
        ("e4", None, "", "e4", ""),
        ("2.d4", 2, ".", "d4", ""),
        ("10...Nc6", 10, "...", "Nc6", ""),
        ("7.Qxf7#", 7, ".", "Qxf7", "#"),
        ("d5", None, "", "d5", ""),
        ("1...", 1, "...", "", ""),
        ("1.", 1, ".", "", ""),
        ("...", None, "...", "", ""),
        ("", None, "", "", ""),
        ("....", None, "....", "", ""),
        ("12345", 12345, "", "", ""),
        ("1. e4", 1, ".", "e4", ""),
        ("1.  e4  ", 1, ".", "e4", ""),
        ("   e4", None, "", "e4", ""),
        ("e4   ", None, "", "e4", ""),
        ("1..  .e4", None, "", "1..  .e4", ""),  # we won't handle everything
    ],
)
def test_get_move_parsed_block(text, move_num, dots, san, annotation):
    block = move_resolver.get_move_parsed_block(text, depth=0)
    assert block.move_parts_raw.num == move_num
    assert block.move_parts_raw.dots == dots
    assert block.move_parts_raw.san == san
    assert block.move_parts_raw.annotation == annotation


@pytest.mark.parametrize(
    "text, expected",
    [
        ("", (None, "", "", "")),
        ("e4", (None, "", "e4", "")),
        ("  e4  ", (None, "", "e4", "")),
        ("1.e4", (1, ".", "e4", "")),
        ("1...e4", (1, "...", "e4", "")),
        ("1... e4", (1, "...", "e4", "")),
        ("1.e4+", (1, ".", "e4", "+")),
        ("a8=Q#", (None, "", "a8=Q", "#")),
        ("999", (999, "", "", "")),
        ("___", (None, "", "", "___")),
        ("14.O-O-O!!", (14, ".", "O-O-O", "!!")),
        ("78. Ke3 !", (78, ".", "Ke3", "!")),
    ],
)
def test_get_move_parts(text, expected):
    assert move_resolver.get_move_parts(text) == expected

    m = move_resolver.MOVE_PARTS_REGEX.search(text.strip())
    assert m is not None
    assert m.lastindex == 4  # Ensures group(4) always exists


@pytest.mark.parametrize(
    "resolved_num, resolved_dots, raw_num, raw_dots, expected",
    [
        (1, ".", 1, ".", 0),
        (1, "...", 1, "...", 0),
        (2, ".", 1, ".", 2),
        (2, "...", 1, "...", 2),
        (2, "...", 1, ".", 3),
        (1, "...", None, "...", -1),
        (1, "...", 1, "....", -1),
    ],
)
def test_get_resolved_move_distance(
    resolved_num, resolved_dots, raw_num, raw_dots, expected
):
    resolved = MoveParts(resolved_num, resolved_dots, "e4", "")
    raw = MoveParts(raw_num, raw_dots, "e4", "")
    result = move_resolver.get_resolved_move_distance(resolved, raw)
    assert result == expected


def test_get_resolved_move_distance_invalid():
    resolved = None
    raw = MoveParts(1, "...", "e5", "")
    with pytest.raises(ValueError) as excinfo:
        move_resolver.get_resolved_move_distance(resolved, raw)
    assert "resolved_move_parts not provided; raw_move_parts =" in str(excinfo.value)


# ==================================================== move resolution helpers


def get_parsed_blocks_from_string(pgn_string: str, depth=0):
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

        assert depth >= 0, "Unbalanced parens in pgn string"

    assert depth == starting_depth, "Unbalanced parens in pgn string"

    return blocks


def get_boards_after_moves(moves: str):
    board = chess.Board()
    index = {}
    for san in moves.split():
        board.push_san(san)
        index[san] = board.copy()
    return index


def merge_boards(*move_strings):
    """
    If we're careful with our test cases, we can combine multiple
    variations into one set of reference boards. We just have to make
    sure we don't have a san that resolves to more than one board!
    """
    merged = {}
    for moves in move_strings:
        merged.update(get_boards_after_moves(moves))
    return merged


def make_pathfinder(blocks, mainline_verbose, board=None, move_id=1234):
    board = board or chess.Board()
    return move_resolver.PathFinder(blocks, move_id, mainline_verbose, board, None)


def get_verbose_sans_list(blocks: list[ParsedBlock]):
    # move verbose will use raw move parts or just raw if
    # no resolved; consider if we only want to look at resolved
    # assemble_move_parts(self.move_parts_resolved)
    return [b.move_verbose() for b in blocks if b.type_ == "move"]


def assert_expected_fens(boards, blocks, expected):
    sans = " ".join(expected)
    sans = re.sub(r"\b\d+\.+", "", sans)
    expected_sans = sans.split()

    # 🔍 Detect duplicate SANs (potentially ambiguous)
    duplicates = [san for san, count in Counter(expected_sans).items() if count > 1]
    if duplicates:
        print(f"⚠️  Duplicate SANs detected in expected list: {', '.join(duplicates)}")

    expected_fens = [
        boards[san].fen() if san in boards else "" for san in expected_sans
    ]
    move_fens = [b.fen for b in blocks if b.type_ == "move"]

    if move_fens != expected_fens:
        expected_lines = [
            f"{san:<8} ➤ {fen}" for san, fen in zip(expected_sans, expected_fens)
        ]
        actual_lines = [
            f"{b.move_verbose():<8} ➤ {b.fen}" for b in blocks if b.type_ == "move"
        ]

        expected_display = "\n".join(expected_lines)
        actual_display = "\n".join(actual_lines)

        raise AssertionError(
            f"\nExpected FENs:\n{expected_display}\n\nActual FENs:\n{actual_display}"
        )


def resolve_subvar(move_str, root_move_str, root_board):
    blocks = get_parsed_blocks_from_string(move_str)
    pf = make_pathfinder(blocks, root_move_str, root_board)
    return pf.resolve_moves()


def assert_resolved_moves(*, boards, root_move, root_board, move_str, expected):
    """
    boards: Dict of reference board states after moves, provides starting
            states (boards) for mainline sans, and fens for those positions.

    root_move: The mainline move that is the root of all "move.text"
               subvars. This will be a proper fully resolved move,
               less annotation, e.g.: 1.e4 or 1...e5

    root_board: The chess.Board state after the mainline root_move

    move_str: A structured test move string with moves and comments,
              following rules in get_parsed_blocks_from_string.

              Can use all-caps SANs (e.g. BAD, 4...LAD) to mark expected
              unplayable moves. They'll pass move parsing and be obvious.

              Moves must be quite normalized, no spaces, obvs.

    expected: List of expected moves. These are the best moves we can
              extract from the resolved moves, whether fully resolved
              and playable or just raw moves that may or may not be valid

              e.g.:
                ( 1.e4 e5 ) -> ["1.e4", "1...e5"]
                ( 1.e4 e5 ( 1...d5 ) ) -> ["1.e4", "1...e5", "1...d5"]
                ( 1.e4 e5 ( 1...BAD ) {comment} ) -> ["1.e4", "e5", "1...BAD"]

              Also uses sans to look up fens for all of the valid board
              states. Note that you must have unique sans for either side,
              this won't handle a sequence like 4.Nxd4 Nxd4 in the Scotch.
    """
    blocks = resolve_subvar(move_str, root_move, root_board)
    assert get_verbose_sans_list(blocks) == expected
    assert_expected_fens(boards, blocks, expected)
    return blocks


# ============================================================= test the tests


def test_get_parsed_moves_from_string():
    parsed_blocks = get_parsed_blocks_from_string(
        "{argle} ( 1.e4 e5 2.Nf3 {bargle} 2...Nc6 ) {goodbye}"
    )

    assert all(
        isinstance(block, ParsedBlock) for block in parsed_blocks
    ), "All blocks should be ParsedBlock instances"

    expected_types = "comment start move move move comment move end comment".split()
    assert len(parsed_blocks) == len(expected_types)
    assert all(
        block.type_ == expected
        for block, expected in zip(parsed_blocks, expected_types)
    ), "Block types should match expected values"

    expected_depths = "0 1 1 1 1 1 1 1 0".split()
    assert all(
        block.depth == int(expected)
        for block, expected in zip(parsed_blocks, expected_depths)
    ), "Block depths should match expected values"

    parsed_blocks = get_parsed_blocks_from_string("(Fabc 1.e4 e5 )")
    assert len(parsed_blocks) == 4
    assert parsed_blocks[0].type_ == "start"
    assert parsed_blocks[0].fen == "abc"
    assert parsed_blocks[1].type_ == "move"
    assert parsed_blocks[2].type_ == "move"
    assert parsed_blocks[3].type_ == "end"

    parsed_blocks = get_parsed_blocks_from_string("( 1.e4 e5 ( 1...d5 ) 2.Nf3 )")

    assert len(parsed_blocks) == 8
    expected = [
        ("start", 1),
        ("move", 1),
        ("move", 1),
        ("start", 2),
        ("move", 2),
        ("end", 2),
        ("move", 1),
        ("end", 1),
    ]
    assert all(
        (block.type_, block.depth) == expected
        for block, expected in zip(parsed_blocks, expected)
    ), "Block types and depths should match expected values"

    assert get_verbose_sans_list(parsed_blocks) == [
        "1.e4",
        "e5",
        "1...d5",
        "2.Nf3",
    ], "Resolved moves should match expected values"


def test_resolve_moves_disambiguation_unhandled():
    """This builds a position where both White and Black
    play Nxd4, which is unhandled in the test harness today,
    and should produce a mismatch.

    We expect the second Nxd4 to overwrite the first in boards lookup.
    """
    boards = get_boards_after_moves("e4 e5 Nf3 Nc6 d4 exd4 Nxd4 Nxd4")

    expected = ["1...e5", "2.Nf3", "2...Nc6", "3.d4", "3...exd4", "4.Nxd4", "4...Nxd4"]

    with pytest.raises(AssertionError) as excinfo:
        assert_resolved_moves(
            boards=boards,
            root_move="1.e4",
            root_board=boards["e4"],
            move_str="( 1...e5 2.Nf3 Nc6 3.d4 exd4 4.Nxd4 Nxd4 )",
            expected=expected,
        )

    assert "Expected FENs" in str(excinfo.value)


# ====================================================== move resolution tests


def test_resolve_moves_basic_pipeline_handling():
    boards = get_boards_after_moves("e4")
    parsed_blocks = get_parsed_blocks_from_string("{hi}", depth=1)
    path_finder = make_pathfinder(parsed_blocks, "1.e4", boards["e4"])

    blocks = path_finder.resolve_moves()

    assert len(blocks) == 3
    assert blocks[0].type_ == "start"
    assert blocks[0].fen == ""
    assert blocks[1].type_ == "comment"
    assert blocks[1].raw == "{hi}"
    assert blocks[2].type_ == "end"
    assert all(b.depth == 2 for b in blocks)


def test_resolve_moves_subvar_continues():
    """
    Simple scenario of subvar first move directly
    following root move, whether from mainline or subvar.

    Simple stuff to confirm basic building blocks, we hope.
    """
    boards = get_boards_after_moves("e4 e5 Nf3 Nc6 d4")  # reference boards

    # white mainline root directly to black subvar move
    blocks = assert_resolved_moves(
        boards=boards,
        root_move="1.e4",
        root_board=boards["e4"],
        move_str="( 1...e5 )",
        expected=["1...e5"],
    )
    assert blocks[0].fen == ""

    # black mainline root directly to white subvar move
    assert_resolved_moves(
        boards=boards,
        root_move="1...e5",
        root_board=boards["e5"],
        move_str="2.Nf3 Nc6 3.d4",
        expected=["2.Nf3", "2...Nc6", "3.d4"],
    )

    # white subvar to black subvar direct (behavior should be the same)
    assert_resolved_moves(
        boards=boards,
        root_move="1.e4",
        root_board=boards["e4"],
        move_str="( 1...e5 2.Nf3 ( 2...Nc6 ) )",
        expected=["1...e5", "2.Nf3", "2...Nc6"],
    )

    # black subvar to white subvar direct
    assert_resolved_moves(
        boards=boards,
        root_move="1...e5",
        root_board=boards["e5"],
        move_str="( 2.Nf3 Nc6 ( 3.d4 ) )",
        expected=["2.Nf3", "2...Nc6", "3.d4"],
    )

    # test independent continuing subvars
    boards = merge_boards("e4 e5 Nf3", "e4 d5 exd5")
    assert_resolved_moves(
        boards=boards,
        root_move="1.e4",
        root_board=boards["e4"],
        move_str="( 1...e5 2.Nf3 ) {comment} ( 1...d5 2.exd5 )",
        expected=["1...e5", "2.Nf3", "1...d5", "2.exd5"],
    )


def test_resolve_moves_discards_dupe_root_in_subvar():
    boards = get_boards_after_moves("d4 d5 c4 e6 Nc3")  # reference boards

    # # white dupes, two levels
    assert_resolved_moves(
        boards=boards,
        root_move="1.d4",
        root_board=boards["d4"],
        move_str="( 1.d4 d5 2.c4 ( 2.c4 e6 ) )",
        expected=["1...d5", "2.c4", "2...e6"],
    )

    # black dupes, two levels
    assert_resolved_moves(
        boards=boards,
        root_move="1...d5",
        root_board=boards["d5"],
        move_str="( 1...d5 2.c4 e6 ( 2...e6 3.Nc3 ) )",
        expected=["2.c4", "2...e6", "3.Nc3"],
    )

    # just to see that 2...e6 first resolves fine, too
    # even though we normally wouldn't encounter this
    assert_resolved_moves(
        boards=boards,
        root_move="1...d5",
        root_board=boards["d5"],
        move_str="( 1...d5 2.c4 2...e6 ( 2...e6 3.Nc3 ) )",
        expected=["2.c4", "2...e6", "3.Nc3"],
    )


def test_resolve_moves_with_root_sibling():
    boards = merge_boards("e4", "d4 d5 c4", "d4 d5 Nf3 Nf6")  # reference boards

    # white mainline root with sibling and white subvar root with sibling
    assert_resolved_moves(
        boards=boards,
        root_move="1.e4",
        root_board=boards["e4"],
        move_str="( 1.d4 d5 2.c4 ( 2.Nf3 Nf6 ) )",
        expected=["1.d4", "1...d5", "2.c4", "2.Nf3", "2...Nf6"],
    )

    # white fails to resolve sibling
    # shows that "resolved" moves can have invalid "pass-through" moves
    assert_resolved_moves(
        boards=boards,
        root_move="1.d4",
        root_board=boards["d4"],
        move_str="( 1.BAD LAD )",
        expected=["1.BAD", "LAD"],
    )

    boards = merge_boards("d4 d5 c4 e6", "d4 e5 dxe5 Nc6", "d4 e5 dxe5 d6 exd6")

    # black mainline root with sibling and black subvar root with sibling
    assert_resolved_moves(
        boards=boards,
        root_move="1...d5",
        root_board=boards["d5"],
        move_str="( 1...e5 2.dxe5 Nc6 ( 2...d6 exd6 ) )",
        expected=["1...e5", "2.dxe5", "2...Nc6", "2...d6", "3.exd6"],
    )

    # black fails to resolve sibling (a level deeper)
    assert_resolved_moves(
        boards=boards,
        root_move="1.d4",
        root_board=boards["d4"],
        move_str="( 1...d5 2.c4 e6 ( 2...BAD ) )",
        expected=["1...d5", "2.c4", "2...e6", "2...BAD"],
    )

    # independent subvars with root siblings
    boards = merge_boards("d4", "e4 e5", "b3 d5")
    assert_resolved_moves(
        boards=boards,
        root_move="1.d4",
        root_board=boards["d4"],
        move_str="( 1.e4 e5 ) ( 1.b3 d5 )",
        expected=["1.e4", "1...e5", "1.b3", "1...d5"],
    )


def test_resolve_moves_fenseq():
    boards = get_boards_after_moves("e4 e5 Nf3 Nc6 d4 Nxd4")
    # 1.e4 e5 2.Nf3 Nc6 ➤
    fen = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
    encoded_fen = fen.replace(" ", "_")

    resolved_blocks = assert_resolved_moves(
        boards=boards,
        root_move="1.e4",
        root_board=boards["e4"],
        move_str=f"(F{encoded_fen} 3.d4 Nxd4 )",
        expected=["3.d4", "3...Nxd4"],
    )

    assert len(resolved_blocks) == 4
    assert resolved_blocks[0].type_ == "start"
    assert resolved_blocks[0].fen == fen
