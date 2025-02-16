def serialize_variation(variation):
    color = variation.chapter.course.color
    variation_data = {
        "variation_id": variation.id,
        "title": variation.title,
        "chapter": variation.chapter.title,
        "color": color,
        "start": variation.start_index,
        "level": variation.level,
    }
    moves = []
    for move in variation.moves.all():
        moves.append({"san": move.san, "alt": move.alt, "alt_fail": move.alt_fail})
    variation_data["moves"] = moves

    return variation_data
