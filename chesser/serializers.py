annotations = {
    "none": "No annotation",
    "?": "? Poor",
    "?!": "?! Dubious",
    "!?": "!? Interesting",
    "!": "! Good",
    "!!": "!! Brilliant",
    "??": "?? Blunder",
    "=": "= Drawish",
    "∞": "∞ Unclear",
    "⩲": "⩲ White Slight",
    "⩱": "⩱ Black Slight",
    "±": "± White Moderate",
    "∓": "∓ Black Moderate",
    "+-": "+- White Decisive",
    "-+": "-+ Black Decisive",
}


def serialize_variation(variation):
    color = variation.chapter.course.color

    variation_data = {
        "variation_id": variation.id,
        "title": variation.title,
        "chapter": variation.chapter.title,
        "color": color,
        "start_index": variation.start_index,
        "start_move": variation.start,
        "level": variation.level,
        "mainline": variation.mainline_moves,
    }

    temp_annotations = annotations.copy()
    moves = []
    white_to_move = True
    for move in variation.moves.all():
        dots = "." if white_to_move else "..."
        white_to_move = not white_to_move

        annotation = move.annotation or ""
        if annotation and annotation not in temp_annotations:
            # add this to annotation dict so we can re-save it
            temp_annotations[annotation] = f"unknown: {annotation}"
            print(
                "unknown annotation in variation "
                f"{variation.id}, move {move.id}: {annotation}"
            )

        annotation = move.annotation if move.annotation else ""
        move_verbose = f"{move.move_num}{dots}{move.san}{annotation}"
        moves.append(
            {
                "san": move.san,
                "annotation": annotation,
                "move_verbose": move_verbose,
                "text": move.text,
                "alt": move.alt or "",
                "alt_fail": move.alt_fail or "",
                "shapes": move.shapes or "",
            }
        )
    variation_data["moves"] = moves
    variation_data["annotations"] = temp_annotations

    return variation_data
