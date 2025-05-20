import pytest

from chesser import serializers, util
from chesser.models import Chapter, Course, Move, Variation
from chesser.move_resolver import ParsedBlock
from chesser.tests import assert_equal


# @pytest.mark.skip(reason="disabled while working on real tests")
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


@pytest.mark.parametrize(
    "display_text, expected_html, expected_state",
    [
        # inline only
        ("Hello world", "<p>Hello world ", True),
        # inline with newline
        ("Line 1\nLine 2", "<p>Line 1<br/>Line 2 ", True),
        # double newline => paragraph break
        ("One\n\nTwo", "<p>One</p><p>Two ", True),
        # block tag gets passed through, no paragraph wrapping
        ("<ul><li>One</li></ul>", "<ul><li>One</li></ul>", False),
        # mixed: inline before/after block
        (
            "before<ul><li>item</li></ul>after",
            "<p>before</p><ul><li>item</li></ul><p>after ",
            True,
        ),
        (  # mixed
            "before<ul><li>item</li></ul>",
            "<p>before</p><ul><li>item</li></ul>",
            False,
        ),
    ],
)
def test_render_comment_block(display_text, expected_html, expected_state):
    # might not really need so many cases since we've already tested separately
    # in test_render_chunks_with_br, but not bad to run several through...
    state = serializers.RendererState()
    block = ParsedBlock(type_="comment", display_text=display_text)
    html = serializers.render_comment_block(block, state)
    assert_equal(expected_html, html)
    assert state.in_paragraph == expected_state


def test_render_comment_block_debug_output(capsys):
    state = serializers.RendererState(debug=True)
    block = ParsedBlock(type_="comment", display_text="line 1\nline 2")

    serializers.render_comment_block(block, state)

    out = capsys.readouterr().out
    assert "➡️ |" in out
    assert "line 1" in out
    assert "💦 Rendered:" in out
    assert "<p>line 1<br/>line 2 " in out


@pytest.mark.parametrize(
    "block_data, initial_state, expected_html, expected_state",
    [
        # Case 1: Start block with FEN, not already in paragraph
        (
            {"type_": "start", "fen": "some-fen", "depth": 1, "log": "log1"},
            {"in_paragraph": False, "counter": -1},
            '<!-- Start Block Log: log1 --><p><span class="move subvar-move" data-fen="some-fen" data-index="0">⏮️</span>',  # noqa: E501
            {"in_paragraph": True, "counter": 0},
        ),
        # Case 2: Start block with FEN, already in paragraph
        (
            {"type_": "start", "fen": "other-fen", "depth": 1, "log": "log2"},
            {"in_paragraph": True, "counter": 4},
            '<!-- Start Block Log: log2 --><span class="move subvar-move" data-fen="other-fen" data-index="5">⏮️</span>',  # noqa: E501
            {"in_paragraph": True, "counter": 5},
        ),
        # Case 3: Start block with depth > 1, not already in paragraph
        (
            {"type_": "start", "fen": "", "depth": 3, "log": "log3"},
            {"in_paragraph": False, "counter": 0},
            '<!-- Start Block Log: log3 --><p class="subvar-indent depth-3"> ',
            {"in_paragraph": True, "counter": 0},
        ),
        # Case 4: Start block with depth > 1, already in paragraph
        (
            {"type_": "start", "fen": "", "depth": 2, "log": "log4"},
            {"in_paragraph": True, "counter": 2},
            '<!-- Start Block Log: log4 --></p><p class="subvar-indent depth-2"> ',
            {"in_paragraph": True, "counter": 2},
        ),
        # Case 5: No fen, depth 1
        (
            {"type_": "start", "fen": "", "depth": 1, "log": "log5"},
            {"in_paragraph": True, "counter": 0},
            "<!-- Start Block Log: log5 -->",
            {"in_paragraph": True, "counter": 0},
        ),
    ],
)
def test_render_start_block(block_data, initial_state, expected_html, expected_state):
    block = ParsedBlock(**block_data)
    state = serializers.RendererState(
        in_paragraph=initial_state["in_paragraph"], counter=initial_state["counter"]
    )
    html = serializers.render_start_block(block, state)
    assert_equal(expected_html, html)
    assert state.in_paragraph == expected_state["in_paragraph"]
    assert state.counter == expected_state["counter"]


def test_print_block_type_info(capsys):
    # comment block
    block = ParsedBlock(type_="comment", display_text="hello")
    serializers.print_block_type_info(block)
    out = capsys.readouterr().out
    assert "block type: comment" in out
    assert "➡️ |" in out
    assert "hello" in out

    # move block
    block = ParsedBlock(type_="move", raw="e4")
    serializers.print_block_type_info(block)
    out = capsys.readouterr().out
    assert "block type: move" in out
    assert "e4 | e4" in out

    # fallback block (e.g. start)
    block = ParsedBlock(type_="start", depth=2)
    serializers.print_block_type_info(block)
    out = capsys.readouterr().out
    assert "block type: start 2" in out


@pytest.mark.parametrize(
    "block_data, initial_state, expected_html, expected_state",
    [
        # Case 1: depth > 1, next_type is comment, not in paragraph
        (
            {"type_": "end", "depth": 3},
            {"in_paragraph": False, "next_type": "comment"},
            '<p></p><p class="subvar-indent depth-2">',
            {"in_paragraph": True},
        ),
        # Case 2: depth > 1, next_type is move, already in paragraph
        (
            {"type_": "end", "depth": 2},
            {"in_paragraph": True, "next_type": "move"},
            '</p><p class="subvar-indent depth-1">',
            {"in_paragraph": True},
        ),
        # Case 3: depth > 1, next_type not move or comment
        (
            {"type_": "end", "depth": 2},
            {"in_paragraph": True, "next_type": "start"},
            "",
            {"in_paragraph": True},
        ),
        # Case 4: depth == 1 should do nothing
        (
            {"type_": "end", "depth": 1},
            {"in_paragraph": False, "next_type": "comment"},
            "",
            {"in_paragraph": False},
        ),
    ],
)
def test_render_end_block(block_data, initial_state, expected_html, expected_state):
    block = ParsedBlock(**block_data)
    state = serializers.RendererState(
        in_paragraph=initial_state.get("in_paragraph", False),
        next_type=initial_state.get("next_type", ""),
    )
    html = serializers.render_end_block(block, state)
    assert_equal(expected_html, html)
    assert state.in_paragraph == expected_state["in_paragraph"]
