import json

from django.shortcuts import render

from chesser.models import Variation
from chesser.serializers import serialize_quiz


def home(request):
    return render(request, "home.html")


def nav(request):
    return render(request, "move_nav.html")


def practice(request):
    variation = (
        Variation.objects.select_related("chapter__course")
        .prefetch_related("moves")
        .first()
    )
    quiz_data = serialize_quiz(variation)
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
