import pytest

from chesser import serializers
from chesser.serializers import Chunk, ParsedBlock


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
    actual = serializers.extract_ordered_chunks(text)
    assert actual == expected_chunks


def test_extract_ordered_chunks_assertions():
    with pytest.raises(AssertionError) as excinfo:
        serializers.extract_ordered_chunks("{abc{")
    assert str(excinfo.value) == "Unexpected opening brace in comment chunk"

    with pytest.raises(AssertionError) as excinfo:
        serializers.extract_ordered_chunks("{abc <fenseq")
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
    assert serializers.extract_ordered_chunks(text) == expected


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
    assert block.type_ == "comment"
    assert block.raw == raw
    assert block.display_text == expected_display
    assert block.depth == depth


def make_comment_block(raw, display, depth=0):
    return ParsedBlock(
        type_="comment",
        raw=raw,
        display_text=display,
        depth=depth,
    )


def make_move_block(raw, move_num, dots, san, depth, fen=""):
    return ParsedBlock(
        type_="move",
        raw=raw,
        move_num=move_num,
        dots=dots,
        san=san,
        fen=fen,
        depth=depth,
    )


@pytest.mark.parametrize(
    "chunks, expected",
    [
        (
            [
                Chunk("comment", "1"),
                Chunk("comment", " \n \n "),
                Chunk("comment", "2  3"),
            ],
            [make_comment_block("1 \n \n 2  3", "1\n\n2 3")],
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
                make_move_block("1.e4", 1, ".", "e4", depth=1),
                make_move_block("e5", None, "", "e5", depth=1),
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
                make_move_block("1.e4", 1, ".", "e4", depth=1),
                ParsedBlock(type_="start", depth=2),
                make_move_block("1... d5", 1, "...", "d5", depth=2),
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
                make_move_block("1.e4", 1, ".", "e4", depth=1),
                make_move_block("e5", None, "", "e5", depth=1),
                make_comment_block(" world", " world", depth=1),
                ParsedBlock(type_="end", depth=1),
                make_comment_block("!<br/>", "!\n", depth=0),
            ],
        ),
        (
            [
                Chunk("fenseq", "<fenseq data-fen='...'>1.e4 e5 2. Nf3</fenseq>"),
            ],
            [
                ParsedBlock(type_="start", depth=1, fen_before="..."),
                make_move_block("1.e4", 1, ".", "e4", depth=1),
                make_move_block("e5", None, "", "e5", depth=1),
                make_move_block("2. Nf3", 2, ".", "Nf3", depth=1),
                ParsedBlock(type_="end", depth=1),
            ],
        ),
    ],
)
def test_get_parsed_blocks_first_pass(chunks, expected):
    assert serializers.get_parsed_blocks_first_pass(chunks) == expected


def test_get_parsed_blocks_first_pass_invalid_type():
    with pytest.raises(ValueError) as excinfo:
        serializers.get_parsed_blocks_first_pass([Chunk("fahr", "vegnugen")])
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
    assert len(blocks) == 6
    assert [block.san for block in blocks] == ["", "e4", "e5", "Nf3", "Nc6", ""]
    assert blocks[0].fen_before == "start_fen"
    assert all(b.fen_before == "" for b in blocks[1:])
    assert all(b.depth == 1 for b in blocks)
    assert all(b.type_ == "move" for b in blocks[1:-1])
    assert (blocks[0].type_, blocks[-1].type_) == ("start", "end")


def test_parse_fenseq_chunk_with_comments():
    test_input = '<fenseq data-fen="start_fen">1.e4 {comment} e5 2.Nf3 {another comment} 2...Nc6</fenseq>'  # noqa: E501

    blocks = serializers.parse_fenseq_chunk(test_input)

    expected = [
        ParsedBlock(type_="start", fen_before="start_fen", depth=1),
        make_move_block("1.e4", 1, ".", "e4", depth=1),
        make_comment_block("{comment}", "comment"),
        make_move_block("e5", None, "", "e5", depth=1),
        make_move_block("2.Nf3", 2, ".", "Nf3", depth=1),
        make_comment_block("{another comment}", "another comment"),
        make_move_block("2...Nc6", 2, "...", "Nc6", depth=1),
        ParsedBlock(type_="end", depth=1),
    ]
    assert blocks == expected


def test_parse_fenseq_chunk_empty():
    assert (
        serializers.parse_fenseq_chunk('<fenseq data-fen="start_fen"> </fenseq>') == []
    )


def test_parse_fenseq_chunk_invalid():
    try:
        serializers.parse_fenseq_chunk("<fenseq>1.e4 e5</fenseq>")
    except AssertionError as e:
        assert "Invalid fenseq chunk" in str(e)


@pytest.mark.parametrize(
    "literal_move, expected_move_num, expected_dots, expected_san",
    [
        ("1.e4", 1, ".", "e4"),
        ("1...e5", 1, "...", "e5"),
        ("e4", None, "", "e4"),
        ("2.d4", 2, ".", "d4"),
        ("10...Nc6", 10, "...", "Nc6"),
        ("7.Qxf7#", 7, ".", "Qxf7#"),
        ("d5", None, "", "d5"),
        ("1...", 1, "...", ""),  # accepted: no SAN
        ("1.", 1, ".", ""),  # accepted: no SAN
        ("...", None, "...", ""),  # accepted: dots only
        ("", None, "", ""),  # accepted: truly empty
        ("....", None, "....", ""),  # accepted: weird but fine
        ("12345", 12345, "", ""),  # accepted: number, no SAN
        ("1. e4", 1, ".", "e4"),  # leading space between dot and SAN
        ("1.  e4  ", 1, ".", "e4"),  # extra spaces both sides
        ("   e4", None, "", "e4"),  # leading whitespace only
        ("e4   ", None, "", "e4"),  # trailing whitespace only
        ("1..  .e4", 1, "..", ".e4"),  # well, we will only try so much
    ],
)
def test_get_simple_move_parsed_block(
    literal_move, expected_move_num, expected_dots, expected_san
):
    block = serializers.get_simple_move_parsed_block(literal_move, depth=0)
    assert block.move_num == expected_move_num
    assert block.dots == expected_dots
    assert block.san == expected_san


@pytest.mark.parametrize(
    "input_san, expected_san",
    [
        # No annotations
        ("e4", "e4"),
        ("Nf3", "Nf3"),
        ("Qh5+", "Qh5+"),
        ("Rd8#", "Rd8#"),
        ("O-O", "O-O"),
        ("O-O-O", "O-O-O"),
        ("c8=Q#", "c8=Q#"),
        # Normal annotations
        ("e4!", "e4"),
        ("e4?", "e4"),
        ("e4!?", "e4"),
        ("e4?!", "e4"),
        ("O-O-", "O-O"),
        ("O-O-O=", "O-O-O"),
        ("d8=R=", "d8=R"),
        # Mixed with checks/mates
        ("Qh5+!", "Qh5+"),
        ("Rd8#!", "Rd8#"),
        ("Rd8#+!?∞", "Rd8#+"),  # invalid but partly parsed
        ("Qa4!+", "Qa4+"),
        ("Qa4!!#", "Qa4#"),
        # Other symbols
        ("e4⩱", "e4"),
        ("d4∞", "d4"),
        ("Nf3∅", "Nf3"),
        ("Nc6⩲", "Nc6"),
        ("Qd8+∅", "Qd8+"),
        ("Kg1#⩱", "Kg1#"),
        # Spaces (should be stripped too)
        ("  e4!  ", "e4"),
        ("  Nf3⩲ ", "Nf3"),
        ("Rd8# ", "Rd8#"),
        # leading numbers/dots
        ("1.e4", "e4"),
        ("2. Nf3", "Nf3"),
        ("3...Nc6", "Nc6"),
        ("4.Qd8+", "Qd8+"),
    ],
)
def test_normalize_san_for_parse(input_san, expected_san):
    assert serializers.normalize_san_for_parse(input_san) == expected_san
