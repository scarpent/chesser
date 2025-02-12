def serialize_quiz(variation):
    color = variation.chapter.course.color
    quiz_data = {
        "variation_id": variation.id,
        "title": variation.title,
        "chapter": variation.chapter.title,
        "color": color,
        "start": variation.start_index,
        "level": variation.level,
        # TODO: previous results!
    }
    moves = []
    for move in variation.moves.all():
        moves.append({"san": move.san, "alt": move.alt, "alt_fail": move.alt_fail})
        # TODO: add arrows, circles, etc., to last move?
    quiz_data["moves"] = moves

    return quiz_data
