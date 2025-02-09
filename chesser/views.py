import json

from django.shortcuts import render


def home(request):
    return render(request, "home.html")


def nav(request):
    return render(request, "move_nav.html")


def practice(request):
    # Example JSON data structure
    # maybe we don't need/want fens here! (they may be useful for variation
    # view and clicking through subvars, but the quiz itself can be leaner...)
    quiz_data = {
        "color": "white",
        "start": 0,  # opening state before opposing move
        "end": 4,  # or 99?
        "moves": [  # always starts at the beginning...
            {
                "san": "e4",
                "alt": ["d4", "Nf3", "c4"],
                "alt_fail": [],
            },
            {
                "san": "e5",
                "alt": [],
                "alt_fail": [],
            },
            {
                "san": "Nf3",
                "alt": ["Nc3"],  # alternative "good" moves that pass
                "alt_fail": ["d4"],  # alternative good moves that fail
            },
            {
                "san": "Nc6",
                "alt": [],
                "alt_fail": [],
            },
            {
                "san": "d4",
                "alt": ["Nc3", "Bc4", "Bb5"],
                "alt_fail": [],
            },
            {  # normally we would end on "our" move, but make sure is handled
                "san": "exd4",
                "alt": [],
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
