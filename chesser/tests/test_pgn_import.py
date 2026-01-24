from io import StringIO

import chess
import chess.pgn
import pytest

from chesser.pgn_import import extract_move_text

PGN_QGD = """\
[Event "?"]
[Site "?"]
[Date "2026.01.24"]
[Round "?"]
[White "Queen's Gambit Declined"]
[Black ""]
[Result "*"]

1.d4 d5 2.c4 e6 3.Nc3 Nf6 4.cxd5 exd5 5.Bg5 {Yada yada yada.} 5...Be7 {Be7 starting comment} (5...Nbd7 { more comment } 6.e3 { even more comment} (6.Nxd5?? Nxd5! 7.Bxd8 Bb4+ { final comment.})) 6.e3 O-O
"""  # noqa: E501


def read_game(pgn_text: str) -> chess.pgn.Game:
    game = chess.pgn.read_game(StringIO(pgn_text))
    assert game is not None, "PGN did not parse into a game"
    return game


def find_node_by_san(
    game: chess.pgn.Game, san_sequence: list[str]
) -> chess.pgn.GameNode:
    """
    Walk the *mainline* by SAN tokens and return the node of the last SAN.
    Example: ["d4","d5",...,"Be7"] returns the Be7 node.
    """
    node: chess.pgn.GameNode = game
    board = game.board()
    for san in san_sequence:
        assert node.variations, f"No continuation when expecting SAN {san}"
        nxt = node.variations[0]
        got = board.san(nxt.move)
        assert got == san, f"Expected SAN {san}, got {got}"
        board.push(nxt.move)
        node = nxt
    return node


@pytest.mark.parametrize(
    "needle",
    [
        # Be7 comment should be wrapped
        "{Be7 starting comment}",
        # sibling alternative line should be present and parenthesized
        "(",
        "5...Nbd7",
        "{more comment}",
        "6.e3",
        "{even more comment}",
        # nested subvariation must exist and keep ?? and !
        "(6.Nxd5??",
        "Nxd5!",
        "7.Bxd8",
        "Bb4+",
        "{final comment.}",
        ")",
    ],
)
def test_extract_move_text_attaches_sibling_variation_and_preserves_numbering(
    needle: str,
) -> None:
    game = read_game(PGN_QGD)

    # Walk to mainline Be7 node
    be7_node = find_node_by_san(
        game,
        ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "cxd5", "exd5", "Bg5", "Be7"],
    )

    text = extract_move_text(be7_node)
    assert needle in text, f"Missing expected fragment: {needle}\n\nGot:\n{text}"


def test_extract_move_text_has_no_numeric_nags() -> None:
    game = read_game(PGN_QGD)
    be7_node = find_node_by_san(
        game,
        ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "cxd5", "exd5", "Bg5", "Be7"],
    )

    text = extract_move_text(be7_node)

    # Should not contain $4 etc after conversion / rendering
    assert "$" not in text, f"Found numeric NAGs unexpectedly:\n{text}"

    # We *do* expect the blunder glyph to be preserved (comes from ?? in the PGN)
    assert "??" in text, f"Expected '??' to be preserved:\n{text}"


def test_parentheses_and_braces_are_balanced_in_extracted_text() -> None:
    game = read_game(PGN_QGD)
    be7_node = find_node_by_san(
        game,
        ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "cxd5", "exd5", "Bg5", "Be7"],
    )

    text = extract_move_text(be7_node)

    assert text.count("(") == text.count(")"), f"Unbalanced parentheses:\n{text}"
    assert text.count("{") == text.count("}"), f"Unbalanced braces:\n{text}"


def test_variation_order_main_then_siblings_not_garbled() -> None:
    """
    Ensures nested alt (6.Nxd5?? ...) appears AFTER 6.e3 inside the (5...Nbd7 ...) line.
    """
    game = read_game(PGN_QGD)
    be7_node = find_node_by_san(
        game,
        ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "cxd5", "exd5", "Bg5", "Be7"],
    )

    text = extract_move_text(be7_node)

    idx_e3 = text.find("6.e3")
    idx_alt = text.find("6.Nxd5??")

    assert idx_e3 != -1 and idx_alt != -1, f"Expected both moves in text:\n{text}"
    assert idx_e3 < idx_alt, f"Expected 6.e3 to appear before 6.Nxd5??:\n{text}"
