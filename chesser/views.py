import json

from django.shortcuts import get_object_or_404, render

from chesser.models import Variation
from chesser.serializers import serialize_quiz


def home(request):
    return practice(request)


def practice(request, variation_id=None):
    if variation_id is None:
        # this will be the actual practice/review mode
        variation = (
            Variation.objects.select_related("chapter__course")
            .prefetch_related("moves")
            .first()
        )
    else:
        # this would be like chessable's "overstudy", although
        # would like to call it something else
        variation = get_object_or_404(
            Variation.objects.select_related("chapter__course").prefetch_related(
                "moves"
            ),
            pk=variation_id,
        )

    quiz_data = serialize_quiz(variation)
    context = {"quiz_data": json.dumps(quiz_data)}
    return render(request, "practice.html", context)
