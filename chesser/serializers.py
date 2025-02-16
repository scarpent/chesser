def serialize_variation(variation):
    color = variation.chapter.course.color
    variation_data = {
        "variation_id": variation.id,
        "title": variation.title,
        "chapter": variation.chapter.title,
        "color": color,
        "start": variation.start_index,
        "level": variation.level,
        "mainline": variation.mainline_moves,
    }
    moves = []

    white_to_move = True
    for move in variation.moves.all():
        dots = "." if white_to_move else "..."
        white_to_move = not white_to_move
        move_verbose = f"{move.move_num}{dots}{move.san}"
        moves.append(
            {
                "san": move.san,
                "move_verbose": move_verbose,
                "alt": move.alt,
                "alt_fail": move.alt_fail,
                "text": move.text,
                "annotation": move.annotation,
            }
        )
    variation_data["moves"] = moves

    return variation_data
