def serialize_quiz(variation):
    color = variation.chapter.course.color
    quiz_data = {
        "color": color,
        "start": variation.start_index,
        "end": variation.end_index,
    }
    moves = []
    for move in variation.moves.all():
        moves.append(
            {
                "san": move.san,
                "alt": list(move.alt.keys()),
                "alt_fail": list(move.alt_fail.keys()),
            }
        )
        # TODO: add arrows, circles, etc., to last move?
    quiz_data["moves"] = moves

    return quiz_data
