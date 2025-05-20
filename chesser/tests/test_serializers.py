import pytest

from chesser import serializers, util
from chesser.models import Chapter, Course, Move, Variation
from chesser.tests import assert_equal


@pytest.mark.skip(reason="disabled while working on real tests")
@pytest.mark.django_db
def test_exercise_serializers():
    """
    just to exercise things a bit until we write proper tests...
    """
    course = Course.objects.create(title="Test Course", color="white")
    chapter = Chapter.objects.create(title="Test Chapter", course=course)
    variation = Variation.objects.create(
        title="Test Variation",
        course=course,
        chapter=chapter,
        start_move=2,
        mainline_moves_str="1.e4 e5",
    )
    Move.objects.create(
        variation=variation,
        move_num=1,
        sequence=0,
        san="e4",
        text="(1...d5 2.exd5 {Lorem ipsum}) (1.d4 d5 (1...c5))",
    )
    fen = "r1bqkbnr/pp1ppp1p/2n3p1/2p5/2P5/2N3P1/PP1PPPBP/R1BQK1NR b KQkq - 1 4"
    Move.objects.create(
        variation=variation,
        move_num=1,
        sequence=1,
        san="e5",
        text="check, mate " + f'<fenseq data-fen="{fen}">4...bg7</fenseq>',
    )
    serializers.serialize_variation(variation, all_data=False)
    serializers.serialize_variation(variation, all_data=True)
    serializers.get_final_move_simple_subvariations_html(variation)


def test_assert_equal_helper():
    """
    Test the assert_equal helper function.
    """
    assert_equal("test", "test")
    assert_equal(["a", "b"], ["a", "b"])
    assert_equal(123, 123)
    assert_equal([1, 2, 3], [1, 2, 3])
    assert_equal({"key": "value"}, {"key": "value"})

    with pytest.raises(AssertionError):
        assert_equal("test", "TEST")
    with pytest.raises(AssertionError):
        assert_equal(123, 456)
    with pytest.raises(AssertionError):
        assert_equal([1, 2, 3], [1, 2, 4])
    with pytest.raises(AssertionError):
        assert_equal({"key": "value"}, {"key": "VALUE"})


@pytest.mark.parametrize(
    "input_text,expected_chunks",
    [
        (
            "\ninline <i>text</i> only\n",
            ["\ninline <i>text</i> only\n"],
        ),
        (
            "<ul><li>item</li></ul>",
            ["<ul><li>item</li></ul>"],
        ),
        (
            "before <ul><li>item</li></ul> after",
            ["before ", "<ul><li>item</li></ul>", " after"],
        ),
        (
            "<pre>preformatted</pre> and then <blockquote>quote</blockquote>",
            ["<pre>preformatted</pre>", " and then ", "<blockquote>quote</blockquote>"],
        ),
        (
            "line 1\nline 2\n\nline 3",
            ["line 1\nline 2\n\nline 3"],
        ),
        (
            "x <ul><li>a</li></ul>\n\n<pre>b</pre> y",
            ["x ", "<ul><li>a</li></ul>", "\n\n", "<pre>b</pre>", " y"],
        ),
        (
            "<ul><li>no lead</li></ul> tail",
            ["<ul><li>no lead</li></ul>", " tail"],
        ),
        (
            "head <blockquote>mid</blockquote>",
            ["head ", "<blockquote>mid</blockquote>"],
        ),
        (
            "yada yada <ul><li>unfinished list</li>",  # malformed unclosed
            ["yada yada ", "<ul>", "<li>unfinished list</li>"],
        ),
        (
            "</ul> unopened",  # malformed unopened
            ["</ul>", " unopened"],
        ),
    ],
)
def test_chunk_html_for_wrapping(input_text, expected_chunks):
    result = serializers.chunk_html_for_wrapping(input_text)
    assert_equal(expected_chunks, result)


@pytest.mark.parametrize(
    "chunk,expected",
    [
        ("<ul>", True),
        ("<UL>", True),  # case-insensitive
        ("<ul><li>item</li></ul>", True),
        ("<blockquote>", True),
        ("<pre>foo</pre>", True),
        ("<code>", False),  # not block
        ("<span>", False),
        ("inline text", False),
        ("</ul>", True),
        ("</blockquote>", True),
        ("<ul", True),  # malformed but still detected
        ("<pre class='x'>", True),  # still starts with <pre>
        ("  <ul>  ", True),  # whitespace tolerance
        ("<invalid>", False),
        ("<b>", False),
        ("<div>", "div" in util.BLOCK_TAGS),  # flexible test if you ever include it
    ],
)
def test_is_block_element(chunk, expected):
    assert serializers.is_block_element(chunk) == expected


@pytest.mark.parametrize(
    "chunks,in_paragraph,expected_html,expected_in_paragraph",
    [
        (["hello world"], False, "<p>hello world ", True),
        (["hello\nworld"], False, "<p>hello<br/>world ", True),
        (
            ["before", "<ul><li>item</li></ul>", "after"],
            False,
            "<p>before</p><ul><li>item</li></ul><p>after ",
            True,
        ),
        (["one\n\ntwo"], False, "<p>one</p><p>two ", True),
        (
            ["<ul><li>foo</li></ul>", "tail text"],
            False,
            "<ul><li>foo</li></ul><p>tail text ",
            True,
        ),
        (
            ["before", "<pre>code</pre>", "after\n\n\nagain"],
            False,
            "<p>before</p><pre>code</pre><p>after</p><p><br/>again ",
            True,
        ),
        (
            ["head ", "<blockquote>quoted</blockquote>", " tail"],
            False,
            "<p>head</p><blockquote>quoted</blockquote><p>tail ",
            True,
        ),
        (["hello world"], True, "hello world ", True),
        (["<ul><li>item</li></ul>"], True, "</p><ul><li>item</li></ul>", False),
        (["<ul><li>item</li></ul>"], False, "<ul><li>item</li></ul>", False),
    ],
)
def test_render_chunks_with_br(
    chunks, in_paragraph, expected_html, expected_in_paragraph
):
    state = serializers.RendererState(in_paragraph=in_paragraph)
    actual_html = serializers.render_chunks_with_br(chunks, state)
    assert_equal(expected_html, actual_html)
    assert state.in_paragraph == expected_in_paragraph
