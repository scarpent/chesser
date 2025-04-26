import pytest

from chesser import serializers


@pytest.mark.parametrize(
    "upcoming_text, expected",
    [
        ("1. e4 {Strong opening move} e5", False),
        ("opening move} e5 {is a good response...}", True),
        ("opening move} e5", True),
        ("no context so no brackets", False),
        ("{something", False),
        ("still {something", False),
    ],
)
def test_is_in_comment(upcoming_text, expected):
    assert serializers.is_in_comment(upcoming_text) == expected


@pytest.mark.parametrize(
    "text,expected_chunks",
    [
        ("", []),  # Empty string
        (" ", [("comment", "{ }")]),  # Whitespace only
        (" \n ", [("comment", "{ \n }")]),  # Whitespace only
        (  # Single line, unbraced
            "Just a simple freeform comment.",
            [("comment", "{Just a simple freeform comment.}")],
        ),
        (  # Multiple sentences and newlines, still implied
            "Freeform comment. Another line.\nYet more.\n\n",
            [("comment", "{Freeform comment. Another line.\nYet more.\n\n}")],
        ),
        (  # Implied comment with subvar interrupt
            "comment start (1.e4 e5)",
            [
                ("comment", "{comment start }"),
                ("subvar", "START 1"),
                ("move", "1.e4"),
                ("move", "e5"),
                ("subvar", "END 1"),
            ],
        ),
        (  # Implied comment with fenseq interrupt
            "Some note <fenseq data-fen='...'>1...c5</fenseq>",
            [
                ("comment", "{Some note }"),
                ("fenseq", "<fenseq data-fen='...'>1...c5</fenseq>"),
            ],
        ),
        (  # Implied with trailing closing brace
            "Hello world }",
            [("comment", "{Hello world }")],
        ),
        (  # Implied followed by explicit comment
            "Hello {world}",
            [
                ("comment", "{Hello }"),
                ("comment", "{world}"),
            ],
        ),
        (  # Explicit followed by implied
            "{Hello} world",
            [
                ("comment", "{Hello}"),
                ("comment", "{ world}"),
            ],
        ),
        (  # Explicit missing closing brace (we'll not assert the print for now)
            "{Hello world",
            [("comment", "{Hello world}")],
        ),
        (  # Leftover whitespace treaated as a comment
            "{Hello world}   \n",
            [
                ("comment", "{Hello world}"),
                ("comment", "{   \n}"),
            ],
        ),
    ],
)
def test_extract_ordered_chunks_comments(text, expected_chunks):
    actual = serializers.extract_ordered_chunks(text)
    assert actual == expected_chunks


def test_extract_ordered_chunks_assertions():
    with pytest.raises(AssertionError) as excinfo:
        serializers.extract_ordered_chunks("{abc{")
    assert str(excinfo.value) == "Unexpected opening brace in comment block"

    with pytest.raises(AssertionError) as excinfo:
        serializers.extract_ordered_chunks("{abc <fenseq")
    assert str(excinfo.value) == "Unexpected <fenseq> tag in comment block"


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            '<fenseq data-fen="...">1.e4</fenseq>',
            [("fenseq", '<fenseq data-fen="...">1.e4</fenseq>')],
        ),
        (
            "<fenseq>1.e4</fenseq>",
            [("fenseq", "<fenseq>1.e4</fenseq>")],
        ),
        (
            "{testing}<fenseq>1.e4",
            [
                ("comment", "{testing}"),
                ("comment", "<fenseq>1.e4"),
            ],
        ),
        (
            "{testing}<fenseq>1.e4</fenseq> more text...",
            [
                ("comment", "{testing}"),
                ("fenseq", "<fenseq>1.e4</fenseq>"),
                ("comment", "{ more text...}"),
            ],
        ),
        (  # known fixable paren imbalance
            "(1.e4 {test}<fenseq>1.e4</fenseq>",
            [
                ("subvar", "START 1"),
                ("move", "1.e4"),
                ("comment", "{test}"),
                ("subvar", "END 1"),
                ("fenseq", "<fenseq>1.e4</fenseq>"),
            ],
        ),
    ],
)
def test_extract_ordered_chunks_fenseq(text, expected):
    assert serializers.extract_ordered_chunks(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "(1.e4 e5)",
            [
                ("subvar", "START 1"),
                ("move", "1.e4"),
                ("move", "e5"),
                ("subvar", "END 1"),
            ],
        ),
        (
            "(1.e4 e5 (1...d5 2.exd5) 2.Nf3)",
            [
                ("subvar", "START 1"),
                ("move", "1.e4"),
                ("move", "e5"),
                ("subvar", "START 2"),
                ("move", "1...d5"),
                ("move", "2.exd5"),
                ("subvar", "END 2"),
                ("move", "2.Nf3"),
                ("subvar", "END 1"),
            ],
        ),
        (
            "(1.e4 e5) \n <fenseq data-fen='...'>1...c5</fenseq>",
            [
                ("subvar", "START 1"),
                ("move", "1.e4"),
                ("move", "e5"),
                ("subvar", "END 1"),
                ("comment", "{ \n }"),
                ("fenseq", "<fenseq data-fen='...'>1...c5</fenseq>"),
            ],
        ),
        (
            "(1.e4 e5) (1.d4 d5)",
            [
                ("subvar", "START 1"),
                ("move", "1.e4"),
                ("move", "e5"),
                ("subvar", "END 1"),
                ("comment", "{ }"),
                ("subvar", "START 1"),
                ("move", "1.d4"),
                ("move", "d5"),
                ("subvar", "END 1"),
            ],
        ),
        (
            "(1.e4 e5) abc (1.d4 d5)",
            [
                ("subvar", "START 1"),
                ("move", "1.e4"),
                ("move", "e5"),
                ("subvar", "END 1"),
                ("comment", "{ abc }"),
                ("subvar", "START 1"),
                ("move", "1.d4"),
                ("move", "d5"),
                ("subvar", "END 1"),
            ],
        ),
        (
            "(1.e4 e5 {(}(1...d5 2.exd5){)} 2.Nf3)",
            [
                ("subvar", "START 1"),
                ("move", "1.e4"),
                ("move", "e5"),
                ("comment", "{(}"),
                ("subvar", "START 2"),
                ("move", "1...d5"),
                ("move", "2.exd5"),
                ("subvar", "END 2"),
                ("comment", "{)}"),
                ("move", "2.Nf3"),
                ("subvar", "END 1"),
            ],
        ),
        (
            "(1.e4 e5 {A)} 2.Nf3) abc",
            [
                ("subvar", "START 1"),
                ("move", "1.e4"),
                ("move", "e5"),
                ("comment", "{A)}"),
                ("move", "2.Nf3"),
                ("subvar", "END 1"),
                ("comment", "{ abc}"),
            ],
        ),
        (  # unbalanced
            "(1.e4 e5",
            [
                ("subvar", "START 1"),
                ("move", "1.e4"),
                ("move", "e5"),
            ],
        ),
        (  # unbalanced
            "(1.e4 e5 (1...d5",
            [
                ("subvar", "START 1"),
                ("move", "1.e4"),
                ("move", "e5"),
                ("subvar", "START 2"),
                ("move", "1...d5"),
            ],
        ),
    ],
)
def test_extract_ordered_chunks_subvar(text, expected):
    assert serializers.extract_ordered_chunks(text) == expected


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
    block = serializers.get_cleaned_comment_parsed_block(raw, depth)
    assert block.block_type == "comment"
    assert block.raw == raw
    assert block.display_text == expected_display
    assert block.subvar_depth == depth


def make_comment_block(raw, display, depth=0):
    return serializers.ParsedBlock(
        block_type="comment",
        raw=raw,
        display_text=display,
        subvar_depth=depth,
    )


def make_move_block(raw, move_num, dots, san, depth, fen=""):
    return serializers.ParsedBlock(
        block_type="move",
        raw=raw,
        move_num=move_num,
        dots=dots,
        san=san,
        fen=fen,
        subvar_depth=depth,
    )


@pytest.mark.parametrize(
    "chunks, expected",
    [
        (
            [
                ("comment", "1"),
                ("comment", " \n \n "),
                ("comment", "2  3"),
            ],
            [make_comment_block("1 \n \n 2  3", "1\n\n2 3")],
        ),
        (
            [
                ("subvar", "START 1"),
                ("move", "1.e4"),
                ("move", "e5"),
                ("subvar", "END 1"),
            ],
            [
                make_move_block("1.e4", 1, ".", "e4", depth=1),
                make_move_block("e5", None, "", "e5", depth=1),
            ],
        ),
        (
            [
                ("subvar", "START 1"),
                ("move", "1."),
                ("move", "e4"),
                ("subvar", "START 2"),
                ("move", "1..."),
                ("move", "d5"),
                ("subvar", "END 2"),
                ("subvar", "END 1"),
            ],
            [
                make_move_block("1.e4", 1, ".", "e4", depth=1),
                make_move_block("1...d5", 1, "...", "d5", depth=2),
            ],
        ),
        (
            [
                ("comment", "{hello }"),
                ("subvar", "START 1"),
                ("move", "1.e4"),
                ("move", "e5"),
                ("comment", "{ world}"),
                ("subvar", "END 1"),
                ("comment", "{!<br/>}"),
            ],
            [
                make_comment_block("hello ", "hello ", depth=0),
                make_move_block("1.e4", 1, ".", "e4", depth=1),
                make_move_block("e5", None, "", "e5", depth=1),
                make_comment_block(" world", " world", depth=1),
                make_comment_block("!<br/>", "!\n", depth=0),
            ],
        ),
        (
            [
                ("fenseq", "<fenseq data-fen='...'>1.e4 e5 2. Nf3</fenseq>"),
            ],
            [
                make_move_block("1.e4", 1, ".", "e4", depth=1, fen="..."),
                make_move_block("e5", None, "", "e5", depth=1),
                make_move_block("2.Nf3", 2, ".", "Nf3", depth=1),
            ],
        ),
    ],
)
def test_get_parsed_blocks_first_pass(chunks, expected):
    assert serializers.get_parsed_blocks_first_pass(chunks) == expected


def test_get_parsed_blocks_first_pass_invalid_type():
    with pytest.raises(ValueError) as excinfo:
        serializers.get_parsed_blocks_first_pass([("fahr", "vegnugen")])
    assert "Unknown chunk type" in str(excinfo.value)


@pytest.mark.parametrize(
    "test_input",
    [
        ('<fenseq data-fen="start_fen">1.e4 e5 2.Nf3 2...Nc6</fenseq>'),
        ("<fenseq data-fen='start_fen'>1. e4 e5 2. Nf3 2... Nc6</fenseq>"),
    ],
)
def test_parse_fenseq_chunk_valid(test_input):
    blocks = serializers.parse_fenseq_chunk(test_input)
    assert len(blocks) == 4
    assert [block.san for block in blocks] == ["e4", "e5", "Nf3", "Nc6"]
    assert blocks[0].fen == "start_fen"
    assert all(b.fen == "" for b in blocks[1:])
    assert all(b.subvar_depth == 1 for b in blocks)
    assert all(b.block_type == "move" for b in blocks)


def test_parse_fenseq_chunk_invalid():
    try:
        serializers.parse_fenseq_chunk('<fenseq data-fen="start_fen"> </fenseq>')
    except AssertionError as e:
        assert "Empty move text" in str(e)

    try:
        serializers.parse_fenseq_chunk("<fenseq>1.e4 e5</fenseq>")
    except AssertionError as e:
        assert "Invalid fenseq block" in str(e)
