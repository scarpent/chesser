import pytest

from chesser import util


def test_clean_html_removes_disallowed_tags_and_attributes():
    raw = """
        <p>hello <script>alert("bad")</script></p>
        <a href="javascript:alert('xss')" onclick="evil()">link</a>
        <span class="sneaky" style="color:red">hi</span>
        <fenseq data-fen="startpos">sequence</fenseq>
        <a href="https://safe.com">safe</a>
    """
    cleaned = util.clean_html(raw)

    assert "<script>" not in cleaned
    assert "javascript:" not in cleaned
    assert "onclick=" not in cleaned
    assert "class=" not in cleaned
    assert "style=" not in cleaned
    assert "<p>" not in cleaned

    assert "<fenseq data-fen=" in cleaned
    assert '<a href="https://safe.com"' in cleaned


fix_notation_game = "1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 g6 6.Be3 Bg7 7.f3 Nc6 8.Qd2 O-O 9.O-O-O d5 10.Kb1 Nxd4 11.e5 Nf5 12.exf6 Bxf6 13.Nxd5 Qxd5 14.Qxd5 Nxe3 15.Qd3 Nxd1 16.Qxd1 Be6 17.Bb5 a6 18.Ba4 b5 19.Bb3 Bxb3 20.axb3 a5 21.Ka2 a4 22.b4 Rfc8 23.Ka3 Rd8 24.Qe2 Rd5 25.Rd1 Rad8 26.Rxd5 Rxd5 27.f4 h5 28.g3 e6 29.h3 Kg7 30.c3 Kg8 31.Qe4 Kg7 32.Qe3 Kg8 33.Qb6 Kg7 34.Qc6 Rd1 35.Ka2 Rd5 36.g4 hxg4 37.hxg4 Kf8 38.Kb1 Kg7 39.Kc2 Kg8 40.c4 bxc4 41.b5 a3 42.bxa3 c3 43.b6 Rd2+ 44.Kc1 Rb2 45.b7 Bd4 46.Qc8+ Kh7 47.b8=Q Be3+ 48.Kd1 c2+ 49.Qxc2 Rxb8 50.f5 exf5 51.Qh2+"  # noqa: E501


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("abc", ""),
        ("1.e4zealous", "1.e4"),
        ("21... f7", "21...f7"),
        ("102. Qa8", "102.Qa8"),
        ("1. e4e5", "1.e4 e5"),
        ("1.e4e5", "1.e4 e5"),
        ("1. e4 e5", "1.e4 e5"),
        ("1.e4 e5", "1.e4 e5"),
        ("1.   e4   e5   2.Nf3   Nf6", "1.e4 e5 2.Nf3 Nf6"),
        ("1.e4e52.d4d53.exd5Qxd5", "1.e4 e5 2.d4 d5 3.exd5 Qxd5"),
        ("1... e52. Nf3", "1...e5 2.Nf3"),
        (
            "e1=Q21. f8=Nh1=B22.a8=Rb1=Q+23.c8=B#",
            "e1=Q 21.f8=N h1=B 22.a8=R b1=Q+ 23.c8=B#",
        ),
        ("45. exd8=Qfxg1=R+", "45.exd8=Q fxg1=R+"),
        (
            "30. Bd3Be731. Bxf4Bxg332. Bc2+Bxb6#",
            "30.Bd3 Be7 31.Bxf4 Bxg3 32.Bc2+ Bxb6#",
        ),
        ("59.Kf5Ke360.Kxf7Kxe2", "59.Kf5 Ke3 60.Kxf7 Kxe2"),
        ("34. R1d3Ref835. Reg8+R8f6#", "34.R1d3 Ref8 35.Reg8+ R8f6#"),
        ("34. R1xd3Rexf835. Rexg8+R8xf6#", "34.R1xd3 Rexf8 35.Rexg8+ R8xf6#"),
        ("23. Rh7Ra124.Re3+Rd2#", "23.Rh7 Ra1 24.Re3+ Rd2#"),
        ("72.Q1d7Q1xd773.Qef7Qhxa8", "72.Q1d7 Q1xd7 73.Qef7 Qhxa8"),
        ("72.N1d7N1xd773.Nef7Nhxa8", "72.N1d7 N1xd7 73.Nef7 Nhxa8"),
        ("1. Qh1Qxb72.Nd4Nxg1", "1.Qh1 Qxb7 2.Nd4 Nxg1"),
        ("12. O-OO-O-O13.Bc4", "12.O-O O-O-O 13.Bc4"),
        ("14... O-O15.O-O-O+", "14...O-O 15.O-O-O+"),
        (
            "1.e4c52.Nf3d63.d4cxd44.Nxd4Nf65.Nc3g66.Be3Bg77.f3Nc68.Qd2O-O9.O-O-Od510.Kb1Nxd411.e5Nf512.exf6Bxf613.Nxd5Qxd514.Qxd5Nxe315.Qd3Nxd116.Qxd1Be617.Bb5a618.Ba4b519.Bb3Bxb320.axb3a521.Ka2a422.b4Rfc823.Ka3Rd824.Qe2Rd525.Rd1Rad826.Rxd5Rxd527.f4h528.g3e629.h3Kg730.c3Kg831.Qe4Kg732.Qe3Kg833.Qb6Kg734.Qc6Rd135.Ka2Rd536.g4hxg437.hxg4Kf838.Kb1Kg739.Kc2Kg840.c4bxc441.b5a342.bxa3c343.b6Rd2+44.Kc1Rb245.b7Bd446.Qc8+Kh747.b8=QBe3+48.Kd1c2+49.Qxc2Rxb850.f5exf551.Qh2+",  # noqa: E501
            fix_notation_game,
        ),
        (fix_notation_game, fix_notation_game),
        ("12.O-O+", "12.O-O+"),
        ("12.O-O#", "12.O-O#"),
        ("12...O-O-O+", "12...O-O-O+"),
        ("1.exd8=Q+", "1.exd8=Q+"),
        ("1...cxb1=N#", "1...cxb1=N#"),
        ("1.exd6 e.p.", "1.exd6"),
        ("1.e4 e5 1-0", "1.e4 e5"),
        ("1.e4 e5 *", "1.e4 e5"),
        ("1.e4 e5 1/2-1/2", "1.e4 e5"),
        ("1.Nfxe5+ Nxe5", "1.Nfxe5+ Nxe5"),
        ("1.Qh4e1", "1.Qh4 e1"),  # or whatever you expect
        ("\n\t 1. e4 \n e5 \t2. Nf3", "1.e4 e5 2.Nf3"),
        ("1.e4!? e5?! 2.Nf3!!", "1.e4 e5 2.Nf3"),
        ("1.e4!? e5?! 2.Nf3!!", "1.e4 e5 2.Nf3"),
        ("1.e4+?! e5 2.Nf3", "1.e4+ e5 2.Nf3"),
        ("1.e4?!+ e5 2.Nf3!#", "1.e4+ e5 2.Nf3#"),
        ("12.O-O-O#!?", "12.O-O-O#"),
    ],
)
def test_normalize_notation(test_input, expected):
    assert util.normalize_notation(test_input) == expected
