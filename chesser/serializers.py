import io

import chess
import chess.pgn

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

    if generate_html:
        html = (
            variation_html if variation.id == 1 else generate_variation_html(variation)
        )
    else:
        html = None

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
    # TODO: May eventually have rendered "final move text" for after the quiz. For now
    # we're showing plain text from moves, but that could have FENs or other encoding.

    temp_annotations = annotations.copy()
    moves = []
    for move in variation.moves.all():
        if move.annotation and move.annotation not in temp_annotations:
            # add this to annotation dict so we can re-save it
            temp_annotations[move.annotation] = f"unknown: {move.annotation}"
            print(
                f"unknown annotation in variation {variation.id}: {move.move_verbose}"
            )

        moves.append(
            {
                "san": move.san,
                "annotation": move.annotation,
                "move_verbose": move.move_verbose,
                "text": move.text,
                "alt": move.alt or "",
                "alt_fail": move.alt_fail or "",
                "shapes": move.shapes or "",
            }
        )
    variation_data["moves"] = moves
    variation_data["annotations"] = temp_annotations

    return variation_data


def generate_variation_html(variation):

    if variation.id == 2:
        parsed_pgn = parse_pgn(variation)
        import json

        print(json.dumps(parsed_pgn, indent=2))
        print(f"len(parsed_moves): {len(parsed_pgn)}")

    html = ""
    white_to_move = True
    beginning_of_move_group = True
    pgn_moves = ""
    for index, move in enumerate(variation.moves.iterator()):
        if white_to_move:
            move_str = f"{move.move_num}."  # White always has dot and number
            pgn_moves += f"{move.move_num}.{move.san} "  # For PGN parsing
        else:
            move_str = f"{move.move_num}..." if beginning_of_move_group else ""
            pgn_moves += f" {move.san} "  # For PGN parsing

        white_to_move = not white_to_move

        if beginning_of_move_group:
            html += "<h3 class='variation-mainline'>\n"
            beginning_of_move_group = False

        move_str += f"{move.san}{move.annotation}"

        html += (
            f'<span class="move mainline-move" data-index="{index}">{move_str}</span>\n'
        )

        if move.text:
            beginning_of_move_group = True
            html += f"</h3>\n<p>{move.text}</p>\n"  # TODO: Parse PGN for subvars, etc

    return html


def parse_pgn(variation):
    full_pgn = ""
    for move in variation.moves.all().iterator():
        move_text = f"{move.text.strip()}\n" if move.text else ""
        full_pgn += f"{move.move_verbose}\n{move_text}"
    # full_pgn = "1.e4 e5 2.Nf3 Nf6 3.Nc3"

    pgn = io.StringIO(full_pgn)
    game = chess.pgn.read_game(pgn)

    parsed_moves = []

    node = game  # Root node

    while node.variations:
        node = node.variations[0]  # Follow mainline
        move_san = node.san()  # Get SAN notation
        move_fen = node.board().fen()  # Get FEN after the move

        move_data = {
            "san": move_san,
            "fen": move_fen,
            "comment": node.comment.strip() if node.comment else "",
            "subvariations": [],
        }

        # Extract subvariations
        for subvar in node.variations[1:]:  # Ignore the first variation (mainline)
            sub_moves = []
            sub_node = subvar
            while sub_node:
                sub_moves.append(
                    {
                        "san": sub_node.san(),
                        "fen": sub_node.board().fen(),
                        "comment": (
                            sub_node.comment.strip() if sub_node.comment else ""
                        ),
                    }
                )
                sub_node = sub_node.variations[0] if sub_node.variations else None

            move_data["subvariations"].append(sub_moves)

        parsed_moves.append(move_data)

    return parsed_moves


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
