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
        (" ", [("comment", " ")]),  # Whitespace only
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
            [("comment", "{comment start }"), ("subvar", "(1.e4 e5)")],
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
                ("comment", "   \n"),
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
    ],
)
def test_extract_ordered_chunks_fenseq(text, expected):
    assert serializers.extract_ordered_chunks(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "(1.e4 e5)",
            [("subvar", "(1.e4 e5)")],
        ),
        (
            "(1.e4 e5) (1.d4 d5)",
            [("subvar", "(1.e4 e5)"), ("subvar", " (1.d4 d5)")],
        ),
        (
            "(1.e4 e5) abc (1.d4 d5)",
            [("subvar", "(1.e4 e5)"), ("comment", "{ abc }"), ("subvar", "(1.d4 d5)")],
        ),
        (
            "(1.e4 e5 (1...d5 2.exd5) 2.Nf3)",
            [("subvar", "(1.e4 e5 (1...d5 2.exd5) 2.Nf3)")],
        ),
    ],
)
def test_extract_ordered_chunks_subvar(text, expected):
    assert serializers.extract_ordered_chunks(text) == expected
