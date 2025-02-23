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


def serialize_variation(variation, generate_html=False):
    color = variation.chapter.course.color

    html = variation_html if generate_html else None

    variation_data = {
        "variation_id": variation.id,
        "title": variation.title,
        "chapter": variation.chapter.title,
        "color": color,
        "start_index": variation.start_index,
        "start_move": variation.start,
        "level": variation.level,
        "mainline": variation.mainline_moves,
        "html": html,
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


variation_html = """
<h3 class="variation-mainline">
    <span class="move mainline-move" data-index="0">1.e4!</span>
    <span class="move mainline-move" data-index="1">Nc6</span>
</h3>
<p>
    The Nimzovich Defence. It is not that bad if you use it just as a
    transpositional tool to reach 1 e4 e5 positions - the independent lines,
    however, are not that reliable for Black, or just downright bad.
</p>
<h3 class="variation-mainline">
    <span class="move mainline-move" data-index="2">2.Nf3</span>
</h3>
<div class="subvariations" data-mainline-index="2">
    <p>
    Instead, 2.d4 is good as well. But 2.Nf3 is logical and easier to handle.
    </p>
    <p>
    How might that work? Well, let's see:
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/pppppppp/2n5/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq - 0 2"
        data-index="0"
        >2.d4</span
    >
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/pppp1ppp/2n5/4p3/3PP3/8/PPP2PPP/RNBQKBNR w KQkq - 0 3"
        data-index="1"
        >e5</span
    >
    We could transpose to the Scotch Game here, but engine says to pick up the
    d-pawn. Masters prefer dxe5 and plebs d5. (Engine likes both, but d5
    slightly better.)
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/pppp1ppp/2n5/3Pp3/4P3/8/PPP2PPP/RNBQKBNR b KQkq - 0 3"
        data-index="2"
        >3.d5</span
    >
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/ppppnppp/8/3Pp3/4P3/8/PPP2PPP/RNBQKBNR w KQkq - 1 4"
        data-index="3"
        >Nce7</span
    >
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/ppppnppp/8/3Pp3/4P3/5N2/PPP2PPP/RNBQKB1R b KQkq - 2 4"
        data-index="4"
        >4.Nf3</span
    >
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/pppp1ppp/6n1/3Pp3/4P3/5N2/PPP2PPP/RNBQKB1R w KQkq - 3 5"
        data-index="5"
        >Ng6</span
    >
    White is better and scores well with h4. With other moves, Black is doing
    better in pleb games, and it's no surprise because these positions seem hard
    to play in practice.
    </p>
    <p>
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/pppppppp/2n5/8/4P3/2N5/PPPP1PPP/R1BQKBNR b KQkq - 2 2"
        data-index="6"
        >2.Nc3</span
    >
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/pppp1ppp/2n5/4p3/4P3/2N5/PPPP1PPP/R1BQKBNR w KQkq - 0 3"
        data-index="7"
        >e5</span
    >
    Did someone order a Vienna?
    </p>
</div>
<h3 class="variation-mainline">
    <span class="move mainline-move" data-index="3">2...d5</span>
</h3>
<div class="subvariations" data-mainline-index="3">
    <p>Scandi style play - it is very questionable though.</p>
    <p>
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/ppp1pppp/2np4/8/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 3"
        data-index="0"
        >2...d6</span
    >
    <span
        class="move subvar-move"
        data-fen="r1bqkbnr/ppp1pppp/2np4/8/3PP3/5N2/PPP2PPP/RNBQKB1R b KQkq - 0 3"
        data-index="1"
        >3.d4</span
    >
    <span
        class="move subvar-move"
        data-fen="r2qkbnr/ppp1pppp/2np4/8/3PP1b1/5N2/PPP2PPP/RNBQKB1R w KQkq - 1 4"
        data-index="2"
        >Bg4?</span
    >
    This pin is somewhat premature.
    <span
        class="move subvar-move"
        data-fen="r2qkbnr/ppp1pppp/2np4/3P4/4P1b1/5N2/PPP2PPP/RNBQKB1R b KQkq - 0 4"
        data-index="3"
        >4.d5!</span
    >
    Just gaining time. The most natural reply happens to fail spectacularly,
    which is a nice added bonus.
    <span
        class="move subvar-move"
        data-fen="r2qkbnr/ppp1pppp/3p4/3Pn3/4P1b1/5N2/PPP2PPP/RNBQKB1R w KQkq - 1 5"
        data-index="4"
        >4...Ne5</span
    >
    <span
        class="move subvar-move"
        data-fen="r2qkbnr/ppp1pppp/3p4/3PN3/4P1b1/8/PPP2PPP/RNBQKB1R b KQkq - 0 5"
        data-index="5"
        >5.Nxe5!</span
    >
    Oh no, my queen!
    </p>
    <p>
    The following complications are not that simple to learn, but White is close
    to winning and you get to bash out some cool moves!
    </p>
</div>
<h3 class="variation-mainline">
    <span class="move mainline-move" data-index="4">3.exd5</span>
    <span class="move mainline-move" data-index="5">Qxd6</span>
    <span class="move mainline-move" data-index="6">4.Nc3</span>
    <span class="move mainline-move" data-index="7">Qh5?</span>
    <span class="move mainline-move" data-index="8">5.Nb5!</span>
</h3>
<p>
    Quite an embarrassing moment for Black - now ...Kd8 is the only move and it is
    not pretty.
</p>
</div>
"""
