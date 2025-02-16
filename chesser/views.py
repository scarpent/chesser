import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt

from chesser.models import Variation
from chesser.serializers import serialize_variation


def home(request):
    home_data = {"home_data": json.dumps("This is the home page")}
    return render(request, "home.html", home_data)


def review(request, variation_id=None):
    if variation_id is None:
        variation = Variation.due_for_review()
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

    if variation is None:
        variation_data = {}
    else:
        variation_data = serialize_variation(variation)

    context = {"variation_data": json.dumps(variation_data)}
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


def importer(request):
    import_data = {"import_data": json.dumps("Import data!")}
    return render(request, "import.html", import_data)


def edit(request, variation_id=None):
    if variation_id is None:
        variation = Variation.objects.first()
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

    if variation is None:
        variation_data = {}
    else:
        variation_data = serialize_variation(variation)

    context = {"variation_data": json.dumps(variation_data)}
    return render(request, "edit.html", context)
