import pytest

from chesser import move_resolver
from chesser.move_resolver import Chunk, MoveParts
from chesser.tests import (
    assert_resolved_moves,
    get_boards_after_moves,
    get_parsed_blocks_from_string,
    make_comment_block,
    make_move_block,
    make_pathfinder,
    make_subvar_block,
    merge_boards,
)


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
        # (  # known fixable paren imbalance
        #     "(1.e4 {test}<fenseq>1.e4</fenseq>",
        #     [
        #         Chunk("subvar", "START 1"),
        #         Chunk("move", "1.e4"),
        #         Chunk("comment", "{test}"),
        #         Chunk("subvar", "END 1"),
        #         Chunk("fenseq", "<fenseq>1.e4</fenseq>"),
        #     ],
        # ),
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


def test_resolve_moves_basic_pipeline_handling():
    boards = get_boards_after_moves("e4")
    parsed_blocks = get_parsed_blocks_from_string("{hi}", depth=1)
    path_finder = make_pathfinder(parsed_blocks, "1.e4", boards["e4"][0])

    blocks = path_finder.resolve_moves()

    assert len(blocks) == 3
    assert blocks[0].type_ == "start"
    assert blocks[0].fen == ""
    assert blocks[1].type_ == "comment"
    assert blocks[1].raw == "{hi}"
    assert blocks[2].type_ == "end"
    assert all(b.depth == 2 for b in blocks)


def test_resolve_moves_disambiguation_handled():
    boards = get_boards_after_moves("e4 e5 Nf3 Nc6 d4 exd4 Nxd4 Nxd4")

    # fmt: off
    assert_resolved_moves(
        boards=boards,
        root_move="1.e4",
        root_board=boards["e4"][0],
        move_str="( 1...e5 2.Nf3 Nc6 3.d4 exd4 4.Nxd4 Nxd4 )",
        expected=["1...e5", "2.Nf3", "2...Nc6", "3.d4", "3...exd4", "4.Nxd4", "4...Nxd4"],  # noqa: E501
    )
    # fmt: on


def test_assert_expected_fens_provides_nice_assertion_error():
    """
    kind of a "test the test" test but we'll do it here instead
    of test_test_helpers.py so we don't have to import more stuff
    """
    boards = get_boards_after_moves("e4 e5 Nf3")

    with pytest.raises(AssertionError) as excinfo:
        assert_resolved_moves(
            boards=boards,
            root_move="1.e4",
            root_board=boards["e4"][0],
            move_str="( 1...e5 2.Nf3 )",
            expected=["1...e5", "2.Nf3"],
            expected_fens_san_keys=["e5", "ERR"],
        )

    expected = "\nExpected FENs:\ne5       ➤ rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2\nERR      ➤ \n\nActual FENs:\n1...e5   ➤ rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2\n2.Nf3    ➤ rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2"  # noqa: E501

    assert str(excinfo.value) == expected


def test_unresolved_moves_are_passed_through():
    boards = get_boards_after_moves("e4 e5 Nf3 Nc6 d4")

    # nothing resolved, all pass-through
    assert_resolved_moves(
        boards=boards,
        root_move="1.e4",
        root_board=boards["e4"][0],
        move_str="( 1.SAD BAD 2.LAD NOT RAD )",
        expected=["1.SAD", "BAD", "2.LAD", "NOT", "RAD"],
        expected_fens_san_keys=["", "", "", "", ""],
    )

    # pass-through moves and resolved moves can mix-and-match
    assert_resolved_moves(
        boards=boards,
        root_move="1.e4",
        root_board=boards["e4"][0],
        move_str="( 1.BAD e5 2.SAD Nf3 3.Nc6 d5 )",
        expected=["1.BAD", "1...e5", "2.SAD", "2.Nf3", "2...Nc6", "d5"],
        expected_fens_san_keys=["", "e5", "", "Nf3", "Nc6", ""],
    )

    # the party can resume after we ignore a bad move and continue,
    # if the following moves resolve appropriately
    assert_resolved_moves(
        boards=boards,
        root_move="1.e4",
        root_board=boards["e4"][0],
        move_str="( 1.a8 e5 2.Nf3 Nc6 d4 )",
        expected=["1.a8", "1...e5", "2.Nf3", "2...Nc6", "3.d4"],
        expected_fens_san_keys=["", "e5", "Nf3", "Nc6", "d4"],
    )


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
        root_board=boards["e4"][0],
        move_str="( 1...e5 )",
        expected=["1...e5"],
    )
    assert blocks[0].fen == ""

    # black mainline root directly to white subvar move
    assert_resolved_moves(
        boards=boards,
        root_move="1...e5",
        root_board=boards["e5"][0],
        move_str="2.Nf3 Nc6 3.d4",
        expected=["2.Nf3", "2...Nc6", "3.d4"],
    )

    # white subvar to black subvar direct (behavior should be the same)
    assert_resolved_moves(
        boards=boards,
        root_move="1.e4",
        root_board=boards["e4"][0],
        move_str="( 1...e5 2.Nf3 ( 2...Nc6 ) )",
        expected=["1...e5", "2.Nf3", "2...Nc6"],
    )

    # black subvar to white subvar direct
    assert_resolved_moves(
        boards=boards,
        root_move="1...e5",
        root_board=boards["e5"][0],
        move_str="( 2.Nf3 Nc6 ( 3.d4 ) )",
        expected=["2.Nf3", "2...Nc6", "3.d4"],
    )

    # test independent continuing subvars
    boards = merge_boards("e4 e5 Nf3", "e4 d5 exd5")
    assert_resolved_moves(
        boards=boards,
        root_move="1.e4",
        root_board=boards["e4"][0],
        move_str="( 1...e5 2.Nf3 ) {comment} ( 1...d5 2.exd5 )",
        expected=["1...e5", "2.Nf3", "1...d5", "2.exd5"],
    )


def test_resolve_moves_discards_dupe_root_in_subvar():
    boards = get_boards_after_moves("d4 d5 c4 e6 Nc3")  # reference boards

    # # white dupes, two levels
    assert_resolved_moves(
        boards=boards,
        root_move="1.d4",
        root_board=boards["d4"][0],
        move_str="( 1.d4 d5 2.c4 ( 2.c4 e6 ) )",
        expected=["1...d5", "2.c4", "2...e6"],
    )

    # black dupes, two levels
    assert_resolved_moves(
        boards=boards,
        root_move="1...d5",
        root_board=boards["d5"][0],
        move_str="( 1...d5 2.c4 e6 ( 2...e6 3.Nc3 ) )",
        expected=["2.c4", "2...e6", "3.Nc3"],
    )

    # just to see that 2...e6 first resolves fine, too
    # even though we normally wouldn't encounter this
    assert_resolved_moves(
        boards=boards,
        root_move="1...d5",
        root_board=boards["d5"][0],
        move_str="( 1...d5 2.c4 2...e6 ( 2...e6 3.Nc3 ) )",
        expected=["2.c4", "2...e6", "3.Nc3"],
    )


def test_resolve_moves_with_root_sibling():
    boards = merge_boards("e4", "d4 d5 c4", "d4 d5 Nf3 Nf6")  # reference boards

    # # white mainline root with sibling and white subvar root with sibling
    assert_resolved_moves(
        boards=boards,
        root_move="1.e4",
        root_board=boards["e4"][0],
        move_str="( 1.d4 d5 2.c4 ( 2.Nf3 Nf6 ) )",
        expected=["1.d4", "1...d5", "2.c4", "2.Nf3", "2...Nf6"],
    )

    # white fails to resolve sibling
    # shows that "resolved" moves can have invalid "pass-through" moves
    assert_resolved_moves(
        boards=boards,
        root_move="1.d4",
        root_board=boards["d4"][0],
        move_str="( 1.BAD LAD )",
        expected=["1.BAD", "LAD"],
    )

    boards = merge_boards("d4 d5 c4 e6", "d4 e5 dxe5 Nc6", "d4 e5 dxe5 d6 exd6")

    # # black mainline root with sibling and black subvar root with sibling
    assert_resolved_moves(
        boards=boards,
        root_move="1...d5",
        root_board=boards["d5"][0],
        move_str="( 1...e5 2.dxe5 Nc6 ( 2...d6 exd6 ) )",
        expected=["1...e5", "2.dxe5", "2...Nc6", "2...d6", "3.exd6"],
    )

    # black fails to resolve sibling (a level deeper)
    assert_resolved_moves(
        boards=boards,
        root_move="1.d4",
        root_board=boards["d4"][0],
        move_str="( 1...d5 2.c4 e6 ( 2...BAD ) )",
        expected=["1...d5", "2.c4", "2...e6", "2...BAD"],
    )

    # independent subvars with root siblings
    boards = merge_boards("d4", "e4 e5", "b3 d5")
    assert_resolved_moves(
        boards=boards,
        root_move="1.d4",
        root_board=boards["d4"][0],
        move_str="( 1.e4 e5 ) ( 1.b3 d5 )",
        expected=["1.e4", "1...e5", "1.b3", "1...d5"],
    )


def test_resolve_moves_fenseq():
    # 1.e4 e5 2.Nf3 Nc6 ➤
    fen_Nc6 = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
    encoded_fen = fen_Nc6.replace(" ", "_")

    boards = get_boards_after_moves("e4 e5 Nf3 Nc6 d4 Nxd4")

    resolved_blocks = assert_resolved_moves(
        boards=boards,
        root_move="1.e4",
        root_board=boards["e4"][0],
        move_str=f"(F{encoded_fen} 3.d4 Nxd4 )",
        expected=["3.d4", "3...Nxd4"],
    )

    assert len(resolved_blocks) == 4
    assert resolved_blocks[0].type_ == "start"
    assert resolved_blocks[0].fen == fen_Nc6


def test_resolve_moves_fenseq_does_not_do_normal_first_move_things():
    fen_e4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    encoded_fen = fen_e4.replace(" ", "_")

    # doesn't discard duplicate root move; we require fenseq to be
    # cleaner than that
    boards = get_boards_after_moves("e4 e5")
    assert_resolved_moves(
        boards=boards,
        root_move="1.e4",
        root_board=boards["e4"][0],
        move_str=f"(F{encoded_fen} 1.e4 e5 )",
        expected=["1.e4", "1...e5"],
        expected_fens_san_keys=["", "e5"],
    )

    # doesn't resolve sibling move since it's not a "real root",
    # and fenseqs aren't as flexible as regular subvars; here we've
    # excluded d4 from the boards since it's never resolved/valid
    boards = get_boards_after_moves("e4")
    assert_resolved_moves(
        boards=boards,
        root_move="1.e4",
        root_board=boards["e4"][0],
        move_str=f"(F{encoded_fen} 1.d4 )",
        expected=["1.d4"],
        expected_fens_san_keys=[""],
    )


def test_resolve_moves_implied_subvar_slash_alternate_move():
    """
    {alternate move}
    (2.Nf3 {or} 2.Nc3)
    (2.Nf3 {or} 2.Nc3 2.Nf6)
    (2.Nf3 {or} 2.Nc3 {or} 2.d4)
    """
    boards = merge_boards("e4 e5 Nf3 Nc6", "e4 e5 Nc3 Nf6", "e4 e5 d4", "e4 d5")

    assert_resolved_moves(
        boards=boards,
        root_move="1...e5",
        root_board=boards["e5"][0],
        move_str="( 2.Nf3 {or} 2.Nc3 )",
        expected=["2.Nf3", "2.Nc3"],
    )

    # we don't treat 2.Nf6 as an implied subvar since it doesn't follow
    # a comment; in this case it *does* get resolved as a black move
    # (under the current parser regime, at least...)
    assert_resolved_moves(
        boards=boards,
        root_move="1...e5",
        root_board=boards["e5"][0],
        move_str="( 2.Nf3 {or} 2.Nc3 2.Nf6 )",
        expected=["2.Nf3", "2.Nc3", "2...Nf6"],
    )

    assert_resolved_moves(
        boards=boards,
        root_move="1...e5",
        root_board=boards["e5"][0],
        move_str="( 2.Nf3 {or} 2.Nc3 {or} 2.d4 )",
        expected=["2.Nf3", "2.Nc3", "2.d4"],
    )

    # previous move unresolved, exits out of implied subvar check
    assert_resolved_moves(
        boards=boards,
        root_move="1.e4",
        root_board=boards["e4"][0],
        move_str="( 1...BAD {or} 1...d5 )",
        expected=["1...BAD", "1...d5"],
    )

    # normal subvar sequence, enters implied check but falls through
    assert_resolved_moves(
        boards=boards,
        root_move="1.e5",
        root_board=boards["e5"][0],
        move_str="( 2.Nf3 {or} 2...Nc6 )",
        expected=["2.Nf3", "2...Nc6"],
    )


def test_known_open_subvar_leading_to_fenseq_pattern():
    """
    This open subvar leading to fenseq was previously our only
    trigger of "❌  Unbalanced parens, depth". Those were manually
    fixed, but even if our janky chessable pipeline export/import
    process brings more in, we should generally handle this fine.
    We don't worry too much about subvar bookkeeping for closing
    out the subvar. We just want to resolve moves. And fenseqs are
    easy to handle as their own new thing independent of what's
    happened before.
    """
    boards = get_boards_after_moves("e4 e5 Nf3 Nc6 d4")
    fen_Nc6 = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
    encoded_fen = fen_Nc6.replace(" ", "_")

    assert_resolved_moves(
        boards=boards,
        root_move="1.e4",
        root_board=boards["e4"][0],
        move_str=f"( 1...e5 (F{encoded_fen} 3.d4 )",
        move_str_unbalanced=True,
        expected=["1...e5", "3.d4"],
    )
