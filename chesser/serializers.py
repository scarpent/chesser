def get_quiz_start_index(color, move_num):
    """
    0   1.e4        1.d4
    1   1...e5      1...d5
    2   2.Nf3       2.c4
    3   2...Nc6     2...e6
    4   3.d4        3.Nc3
    5   3...exd4    3...Nf6
    6   4.Nxd4      4.Nf3
    7   4...Nf6     4...a6

    expecting with white to always start on at least move 2, but with black
    might want to start on move 1 and will have to revisit how js quiz
    handling works

    for white:
    ➤ if start move is 2, then quiz should start at index 0, the white move
    before the opposing move that will be shown when the quiz starts
    ➤ if end move is 4, then quiz should end at index 6

    for black:
    ➤ if start move is 2, then quiz should start at index 1
    ➤ if end move is 4, then quiz should end at index 7

    TODO: maybe this could/should be a property on the Variation model
    """
    ply = move_num * 2
    return ply - 4 if color == "white" else ply - 3


def get_quiz_end_index(color, move_num):
    ply = move_num * 2
    return ply - 2 if color == "white" else ply - 1


def serialize_quiz(variation):
    # variation holds start/end move numbers; we want to
    # translate into an index for the moves list
    color = variation.chapter.course.color
    quiz_data = {
        "color": color,
        "start": get_quiz_start_index(color, variation.start),
        "end": get_quiz_end_index(color, variation.end),
    }
    moves = []
    for move in variation.moves.all().order_by("move_id"):
        moves.append(
            {
                "san": move.san,
                "alt": list(move.alt.keys()),
                "alt_fail": list(move.alt_fail.keys()),
            }
        )
    quiz_data["moves"] = moves

    return quiz_data
