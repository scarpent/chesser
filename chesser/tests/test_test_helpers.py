from chesser.move_resolver import ParsedBlock
from chesser.tests import get_parsed_blocks_from_string, get_verbose_sans_list


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

    # fmt: off
    assert get_verbose_sans_list(parsed_blocks) == [
        "1.e4", "e5", "1...d5", "2.Nf3",
    ], "Resolved moves should match expected values"
    # fmt: on
