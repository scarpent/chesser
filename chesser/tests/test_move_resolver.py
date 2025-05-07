import chess
import pytest

from chesser import move_resolver
from chesser.move_resolver import Chunk, MoveParts, ParsedBlock


def make_comment_block(raw, display, depth=1):
    return ParsedBlock(
        type_="comment",
        raw=raw,
        display_text=display,
        depth=depth,
    )


def make_move_block(raw, fen="", depth=1):
    """relying on a core function of the move resolving engine"""
    return ParsedBlock(
        type_="move",
        raw=raw,
        move_parts_raw=move_resolver.get_move_parts(raw),
        fen=fen,
        depth=depth,
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
                ParsedBlock(type_="start", depth=1),
                make_move_block("1.e4"),
                make_move_block("e5"),
                ParsedBlock(type_="end", depth=1),
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
                ParsedBlock(type_="start", depth=1),
                make_move_block("1.e4"),
                ParsedBlock(type_="start", depth=2),
                make_move_block("1... d5", depth=2),
                ParsedBlock(type_="end", depth=2),
                ParsedBlock(type_="end", depth=1),
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
                ParsedBlock(type_="start", depth=1),
                make_move_block("1.e4"),
                make_move_block("e5"),
                make_comment_block(" world", " world"),
                ParsedBlock(type_="end", depth=1),
                make_comment_block("!<br/>", "!\n", depth=0),
            ],
        ),
        (
            [
                Chunk("fenseq", "<fenseq data-fen='...'>1.e4 e5 2. Nf3</fenseq>"),
            ],
            [
                ParsedBlock(type_="start", depth=1, fen="..."),
                make_move_block("1.e4"),
                make_move_block("e5"),
                make_move_block("2. Nf3"),
                ParsedBlock(type_="end", depth=1),
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
        ParsedBlock(type_="start", fen="start_fen", depth=1),
        make_move_block("1.e4"),
        make_comment_block("{comment}", "comment"),
        make_move_block("e5"),
        make_move_block("2.Nf3"),
        make_comment_block("{another comment}", "another comment"),
        make_move_block("2...Nc6"),
        ParsedBlock(type_="end", depth=1),
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


def wrap_with_subvar(blocks, depth=1):
    # later can add fenseq handling with fen on start
    start_block = ParsedBlock(type_="start", depth=depth)
    end_block = ParsedBlock(type_="end", depth=depth)
    for block in blocks:
        if block.type_ == "start":
            depth += 1
        block.depth = depth
        if block.type_ == "end":
            depth -= 1
    return [start_block] + blocks + [end_block]


def make_subvar_from_sans(moves_string: str, depth=1):
    # could also {add comments} and chunk accordingly...
    sans = moves_string.split()
    blocks = [make_move_block(san, depth=depth) for san in sans]
    return wrap_with_subvar(blocks, depth=depth)


def get_boards_after_moves(moves: str):
    board = chess.Board()
    index = {}
    for san in moves.split():
        board.push_san(san)
        index[san] = board.copy()
    return index


def make_pathfinder(blocks, mainline_verbose, board=None, move_id=1234):
    board = board or chess.Board()
    return move_resolver.PathFinder(blocks, move_id, mainline_verbose, board, None)


def get_resolved_moves(blocks: list[ParsedBlock]):
    # move verbose will use raw move parts or just raw if no resolved;
    # consider if we only want to look at resolved
    # assemble_move_parts(self.move_parts_resolved)
    return [b.move_verbose() for b in blocks if b.type_ == "move"]


def get_move_fens(blocks: list[ParsedBlock]):
    return [b.fen for b in blocks if b.type_ == "move" and b.fen]


# ====================================================== move resolution tests


def test_resolve_moves_basic_pipeline_handling():
    boards = get_boards_after_moves("e4")
    parsed_blocks = wrap_with_subvar([make_comment_block("{hi}", "hi")], depth=2)
    path_finder = make_pathfinder(parsed_blocks, "1.e4", boards["e4"])

    blocks = path_finder.resolve_moves()

    assert len(blocks) == 3
    assert blocks[0].type_ == "start"
    assert blocks[0].fen == ""
    assert blocks[1].type_ == "comment"
    assert blocks[1].raw == "{hi}"
    assert blocks[2].type_ == "end"
    assert all(b.depth == 2 for b in blocks)


def test_resolve_moves_subvar_continues_from_white_root():
    boards = get_boards_after_moves("e4 e5")
    parsed_blocks = wrap_with_subvar([make_move_block("1...e5")])
    path_finder = make_pathfinder(parsed_blocks, "1.e4", boards["e4"])

    blocks = path_finder.resolve_moves()

    assert len(blocks) == 3
    assert blocks[1].type_ == "move"
    assert blocks[1].fen == boards["e5"].fen()
    assert tuple(blocks[1].move_parts_resolved) == (1, "...", "e5", "")


def test_resolve_moves_subvar_continues_from_black_root():
    boards = get_boards_after_moves("e4 e5")
    blocks = make_subvar_from_sans("2.Nf3 Nc6 3.d4")
    pf = make_pathfinder(blocks, "1...e5", boards["e5"])

    resolved = pf.resolve_moves()

    assert get_resolved_moves(resolved) == ["2.Nf3", "2...Nc6", "3.d4"]
