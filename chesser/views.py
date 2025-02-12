import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt

from chesser.models import Variation
from chesser.serializers import serialize_quiz


def home(request):
    home_data = {"home_data": json.dumps("This is the home page")}
    return render(request, "home.html", home_data)


def review(request, variation_id=None):
    if variation_id is None:
        # this will be the actual review/practice mode
        variation = (
            Variation.objects.select_related("chapter__course")
            .prefetch_related("moves")
            .first()
        )
    else:
        # this would be like chessable's "overstudy", although
        # would like to call it something else - we'll think about
        # if we want it to affect current level or not...
        variation = get_object_or_404(
            Variation.objects.select_related("chapter__course").prefetch_related(
                "moves"
            ),
            pk=variation_id,
        )

    quiz_data = serialize_quiz(variation)
    context = {"quiz_data": json.dumps(quiz_data)}
    return render(request, "review.html", context)


@csrf_exempt
def report_result(request):
    if request.method == "POST":
        data = json.loads(request.body)
        variation_id = data.get("variation_id")
        passed = data.get("passed")

        variation = get_object_or_404(Variation, pk=variation_id)
        variation.handle_quiz_result(passed)

        return JsonResponse({"status": "success"})

    return JsonResponse(
        {"status": "error", "message": "Invalid request method"}, status=400
    )
