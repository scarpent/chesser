import json

from django.shortcuts import render


def home(request):
    return render(request, "home.html")


def nav(request):
    return render(request, "move_nav.html")


def practice(request):
    # Example JSON data structure
    quiz_data = {
        "color": "white",
        "start": 0,  # opening state before opposing move
        "end": 4,  # or 99?
        "moves": [
            {
                "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                "move": "e4",
                "alt": {"d4": 1, "Nf3": 1, "c4": 1},
                # maybe rank alt moves and show with annotations (A, B, C)
                # (could have multiple "A" moves, etc...) probably a checkbox
                # to show/hide these after the quiz is completed? OR, perhaps
                # the annotations should be defined with lines, circles, etc?
                # but would want to toggle them separately?
            },
            {
                "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                "move": "e5",
            },
            {
                "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
                "move": "Nf3",
                "alt": ["d5", "Nc3"],  # accepted good moves that don't fail the quiz
                "alt_fail": ["d5"],  # accepted good moves that fail the quiz
            },
            {
                "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",  # noqa: E501
                "move": "Nc6",
            },
            {
                "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/3PP3/5N2/PPP2PPP/RNBQKB1R b KQkq - 0 3",  # noqa: E501
                "move": "d4",
                "alt": ["Nc3", "Bc4", "Bb5"],
                "alt_fail": [],
            },
        ],
    }

    context = {"quiz_data": json.dumps(quiz_data)}
    return render(request, "practice.html", context)


def quiz_poc(request):
    # Example JSON data structure
    quiz_data = {
        "moves": [
            {
                "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                "move": "e4",
            },
            {
                "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                "move": "e5",
            },
            {
                "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
                "move": "Nf3",
            },
        ]
    }

    context = {"quiz_data": json.dumps(quiz_data)}
    return render(request, "quiz_poc.html", context)


def simple(request):
    return render(request, "simple.html")
