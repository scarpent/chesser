import json
import random
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import groupby

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import (
    Case,
    Count,
    IntegerField,
    Q,
    Value,
    When,
)
from django.db.models.functions import Lower
from django.http import (
    FileResponse,
    HttpResponseBadRequest,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from django.views import View
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_POST

from chesser import importer, util
from chesser.models import Chapter, Move, QuizResult, SharedMove, Variation
from chesser.serializers import (
    get_final_move_simple_subvariations_html,
    serialize_shared_move,
    serialize_variation,
    serialize_variation_to_import_format,
)

QUIZ_RESULT_DEBOUNCE_HOURS = timedelta(hours=3)


def home(request, color=None, chapter_id=None):
    home_view = HomeView(color=color, chapter_id=chapter_id)
    return render(
        request,
        "home.html",
        {"home_data_json": json.dumps(home_view.home_data)},
    )


def service_worker(request):
    return FileResponse(
        open("chesser/service-worker.js", "rb"), content_type="application/javascript"
    )


def custom_404_view(request, exception):
    return render(
        request,
        "error.html",
        {
            "title": "404 Off Book",
            "heading": "404 🤷‍♀️",
            "message": "Your queen is in another castle.",
            "subtext": "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        },
        status=404,
    )


def custom_500_view(request):
    return render(
        request,
        "error.html",
        {
            "title": "chesserverror",
            "heading": "1...500?!",
            "message": "We're sorry.",
            "subtext": "Surely elves will fix... 🛠️",
        },
        status=500,
    )


def trigger_error(request):
    raise Exception("💣️ test error 🧨")


def review(request, variation_id=None):
    if variation_id is None:
        extra_study = False
        variation = Variation.due_for_review()
    else:
        # Can review "on demand", but it won't update level/next_review
        extra_study = True
        # fmt: off
        variation = get_object_or_404(
            Variation.objects.select_related(
                "chapter"
            ).prefetch_related(
                "moves",
                "quiz_results",
            ),
            pk=variation_id,
        )  # fmt: on

        # However! We can learn a new variation on demand and make it count
        learn = request.GET.get("learn") == "1"
        if learn and variation.level == 0:
            # don't update next review; it will stay scheduled whenever until completed
            extra_study = False

    if variation is None:
        if request.GET.get("finish") == "1":
            return redirect("home")
        variation_data = {}
        final_move_html = ""
    else:
        variation_data = serialize_variation(variation, mode="review")
        final_move_html = get_final_move_simple_subvariations_html(variation)

    total_due_now, total_due_soon = Variation.due_counts()
    review_data = {
        "extra_study": extra_study,
        "total_due_now": total_due_now,
        "total_due_soon": total_due_soon,
        "final_move_html": final_move_html,
    }

    context = {
        "variation_data": json.dumps(variation_data),
        "review_data": json.dumps(review_data),
    }
    return render(request, "review.html", context)


def review_random(request):
    """Random review of any variation, including unlearned ones"""

    color = request.GET.get("color")
    chapter_id = request.GET.get("chapter_id")

    qs = Variation.objects.all()
    if color:
        qs = qs.filter(chapter__color=color)
    if chapter_id:
        qs = qs.filter(chapter_id=chapter_id)

    if not qs.exists():  # no variations at all, or none matching filters
        return redirect("review_default")

    variation = random.choice(list(qs))
    return redirect("review_with_id", variation_id=variation.id)


@csrf_exempt
@require_POST
def report_result(request):
    data = json.loads(request.body)
    variation_id = data.get("variation_id")
    passed = data.get("passed")

    if variation_id is None or passed is None:
        return JsonResponse(
            {"status": "error", "message": "Missing parameters"}, status=400
        )

    variation = get_object_or_404(Variation, pk=variation_id)

    if last_result := (
        QuizResult.objects.filter(variation=variation).order_by("-datetime").first()
    ):
        if now() - last_result.datetime < QUIZ_RESULT_DEBOUNCE_HOURS:
            return JsonResponse(
                {
                    "status": "ignored",
                    "message": "Already reported within debounce window",
                },
            )

    variation.handle_quiz_result(passed)

    total_due_now, total_due_soon = Variation.due_counts()
    return JsonResponse(
        {
            "status": "success",
            "total_due_now": total_due_now,
            "total_due_soon": total_due_soon,
        },
    )


def get_import_context(form_defaults=None):
    form_defaults = form_defaults or {}

    # Build chapter list with label "White: Chapter" or "Black: Chapter"
    chapters = [
        {
            "id": str(chapter.id),
            "label": f"{chapter.color.title()}: {chapter.title}",
        }
        for chapter in Chapter.objects.annotate(
            color_order=Case(
                When(color="white", then=Value(0)),
                When(color="black", then=Value(1)),
                default=Value(99),
                output_field=IntegerField(),
            )
        ).order_by("color_order", "title")
    ]

    if chapters:
        form_defaults.setdefault("chapter_id", chapters[0]["id"])

    return {
        "import_data": json.dumps(
            {
                "chapters": chapters,
                "form_defaults": form_defaults,
            }
        )
    }


def import_view(request):
    form_defaults = request.session.pop("import_form_defaults", {})

    if variation_id := request.GET.get("clone"):
        try:
            variation = Variation.objects.get(pk=variation_id)
            form_defaults["original_variation_id"] = variation.id
            form_defaults["clone_variation_title"] = variation.title
            form_defaults["original_variation_moves"] = variation.mainline_moves
        except Variation.DoesNotExist:
            messages.error(request, f"❌ Could not find variation #{variation_id}")

    return render(
        request, "import.html", get_import_context(form_defaults=form_defaults)
    )


def handle_upload_errors(request, error_message):
    messages.error(request, f"🔴 {error_message}")
    request.session["import_form_defaults"] = request.POST.dict()
    return redirect("import")


@csrf_protect
@require_POST
def upload_json_data(request):
    file = request.FILES.get("uploaded_file")
    if not file:
        return handle_upload_errors(request, "No file selected")

    try:
        file_content = file.read().decode("utf-8")
        json.loads(file_content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return handle_upload_errors(request, "Not a valid JSON file")

    with open("/tmp/upload.json", "w") as temp_file:
        temp_file.write(file_content)

    messages.success(request, "File Uploaded ✅")
    return redirect("import")


@method_decorator(csrf_protect, name="dispatch")
class ImportVariationView(View):
    def dispatch(self, request, *args, **kwargs):
        if request.method != "POST":
            return redirect("import")
        return super().dispatch(request, *args, **kwargs)

    def handle_import_errors(self, error_message):
        messages.error(self.request, f"🔴 {error_message}")
        self.request.session["import_form_defaults"] = self.form_data.dict()
        return redirect("import")

    def post(self, request):
        self.request = request
        self.form_data = request.POST
        self.incoming_json = {}
        form_json_or_pgn = request.POST.get("json_or_pgn_data")

        try:
            self.incoming_json = json.loads(form_json_or_pgn)
        except json.JSONDecodeError:
            pass

        if not self.incoming_json:
            # If the JSON is invalid, we can try to parse it as PGN
            try:
                pgn_to_json = importer.convert_pgn_to_json(form_json_or_pgn)
                self.incoming_json = pgn_to_json
            except ValueError:
                return self.handle_import_errors("Invalid JSON/PGN")

        self.chapter_title = self.incoming_json.get("chapter_title", "Unknown").strip()
        self.color = self.incoming_json.get("color", "").strip().lower()
        if self.color not in ["white", "black"]:
            return self.handle_import_errors("Color must be set as 'white' or 'black'")

        try:
            self.set_variation_title()
            self.set_start_move()
            self.set_chapter_info()
            end_move = self.get_end_move()  # must come after set_start_move
            self.incoming_json["next_review"] = util.END_OF_TIME_STR
            variation_info = importer.import_variation(
                self.incoming_json,
                end_move=end_move,
            )
        except ValueError as e:
            return self.handle_import_errors(str(e))

        messages.success(
            request, mark_safe(f"Variation {variation_info} imported successfully ✅")
        )
        return redirect("import")

    def set_variation_title(self):
        title = (
            self.form_data.get("variation_title", "").strip()
            or self.incoming_json.get("variation_title", "").strip()
        )
        if not title or title == "TBD":
            raise ValueError("Variation Title not given and not in JSON")
        self.incoming_json["variation_title"] = title
        messages.success(self.request, f"🟢 Title: {title}")

    def set_start_move(self):
        try:
            start = int(self.form_data.get("start_move", 2))
            self.incoming_json["start_move"] = start
            messages.success(self.request, f"🟢 Starts @ {start}")
        except ValueError:
            messages.warning(
                self.request, "🟡 Invalid or missing start move; defaulting to 2"
            )
            self.incoming_json["start_move"] = 2

    def get_end_move(self):
        end_move = self.form_data.get("end_move", "").strip()
        if not end_move:
            return None

        try:
            end_move = int(end_move)
            if end_move <= self.incoming_json["start_move"]:
                raise ValueError("End move must be greater than start move")
        except ValueError as e:
            raise ValueError(f"Invalid end move: {e}")

        messages.warning(self.request, f"🟡 Discarding moves after {end_move}")
        return end_move

    def set_chapter_info(self):
        if chapter_id := self.form_data.get("chapter_id"):
            chapter = Chapter.objects.get(pk=int(chapter_id))
            created = False
            self.chapter_title = chapter.title  # override any incoming title
        else:
            chapter, created = Chapter.objects.get_or_create(
                title=self.chapter_title,
                color=self.color,
            )

        label = "Creating" if created else "Using existing"
        print("➤ " * 32)
        print(f"{label} chapter: {chapter}")

        self.incoming_json["color"] = chapter.color
        self.incoming_json["chapter_title"] = chapter.title
        messages.success(self.request, f"🟢 {chapter.color.title()} ➤ {chapter.title}")


def get_sorted_variations(chapter_id=None):
    queryset = Variation.objects.select_related("chapter").annotate(
        sort_key=Lower("mainline_moves_str"),
        intro_priority=Case(
            When(is_intro=True, then=0),
            default=1,
            output_field=IntegerField(),
        ),
    )

    if chapter_id is not None:
        queryset = queryset.filter(chapter_id=chapter_id)
        return queryset.order_by("intro_priority", "sort_key").iterator()
    else:
        # When would we get sorted variations without a chapter?
        return queryset.order_by(
            Case(
                When(chapter__color="white", then=Value(0)),
                When(chapter__color="black", then=Value(1)),
                output_field=IntegerField(),
            ),
            "chapter__title",
            "intro_priority",
            "sort_key",
        ).iterator()


def handle_clone_errors(request, form_data, error_message):
    messages.error(request, f"🔴 {error_message}")
    request.session["import_form_defaults"] = form_data.dict()
    return redirect("import")


@require_POST
def clone(request):
    form_data = request.POST
    original_variation_id = int(form_data.get("original_variation_id"))
    variation_title = form_data.get("clone_variation_title", "").strip()

    new_variation = form_data.get("clone_mainline", "").strip()
    if not variation_title or not new_variation:
        return handle_clone_errors(
            request, form_data, "New variation title or moves not given"
        )

    normalized_variation = util.normalize_notation(new_variation)
    if normalized_variation != new_variation:
        normalized_label = " (normalized)"
        new_variation = normalized_variation
    else:
        normalized_label = ""

    variation_link = (
        f'<a href="/variation/{original_variation_id}/">#{original_variation_id}</a>'
    )
    messages.success(request, mark_safe(f"🧬 Cloning Variation {variation_link}"))
    messages.success(request, f"🧬 Title: {variation_title}")
    messages.success(request, f"🧬 Moves{normalized_label}: {new_variation}")

    variation = get_object_or_404(Variation, pk=original_variation_id)
    import_data = serialize_variation_to_import_format(variation)
    original_sans = [m["san"] for m in import_data["moves"]]
    new_sans = util.strip_move_numbers(new_variation).split(" ")

    if original_sans == new_sans:
        return handle_clone_errors(
            request, form_data, "New moves are identical to original moves"
        )

    diverged_at = None
    for i, (orig, new) in enumerate(zip(original_sans, new_sans)):
        if orig != new:
            diverged_at = i
            break
    if diverged_at is None:
        diverged_at = len(original_sans)

    new_moves = []
    for index, san in enumerate(new_sans[diverged_at:], start=diverged_at):
        move_number = index // 2 + 1
        new_moves.append(
            {
                "move_num": move_number,
                "san": san,
                "annotation": "",
                "text": "",
                "shapes": [],
            }
        )

    if not new_moves:
        return handle_clone_errors(
            request,
            form_data,
            "There is nothing new under the sun, nor in the cloned moves... ☀️",
        )

    new_moves_str = " ".join([f'{m["move_num"]}-{m["san"]}' for m in new_moves])
    messages.success(
        request, f"🧬 Diverged at index: {diverged_at}, new moves: {new_moves_str}"
    )

    import_data.pop("variation_id")  # so we don't hit the dupe check on import
    import_data["variation_title"] = variation_title
    import_data["moves"] = import_data["moves"][:diverged_at] + new_moves
    import_data["mainline"] = new_variation
    import_data["level"] = 0
    import_data["next_review"] = util.END_OF_TIME_STR
    try:
        variation_info = importer.import_variation(
            import_data, source_variation_id=original_variation_id
        )
    except ValueError as e:
        return handle_clone_errors(request, form_data, str(e))

    messages.success(
        request, mark_safe(f"🧬 Variation cloned successfully ➤ {variation_info} ✅")
    )
    return redirect("import")


def export(request, variation_id=None):
    variation = get_object_or_404(
        Variation.objects.prefetch_related("moves", "chapter"), pk=variation_id
    )
    export_data = serialize_variation_to_import_format(variation)
    return JsonResponse(
        export_data,
        json_dumps_params={"indent": 4, "ensure_ascii": False},
    )


def variations_tsv(request):
    def row_generator():
        for v in get_sorted_variations():
            intro = "📌" if v.is_intro else ""
            yield (
                f"{v.chapter.color.title()}\t"
                f"{v.chapter.title}\t"
                f"{intro} {v.title}\t"
                f"{v.mainline_moves}\t"
                f"{settings.CHESSER_URL}/variation/{v.id}/\n"
            )

    return StreamingHttpResponse(
        row_generator(), content_type="text/plain; charset=utf-8"
    )


def variations_table(request):
    def row_generator():
        qs = get_sorted_variations()

        yield "<html><body><table>\n"
        yield (
            '<tr style="background-color: lightblue; text-align: left">'
            "<th>Start</th><th>C</th><th>#</th><th>Variation</th><th>Moves</th></tr>\n"
        )

        URL_BASE = f"{settings.CHESSER_URL}/variation"
        total = 0
        for chapter_title, group in groupby(qs, key=lambda v: v.chapter.title):
            group_list = list(group)
            count_in_chapter = len(group_list)

            yield (
                f'<tr style="background-color: lightblue; font-weight: bold;">'
                f'<td colspan="5">{chapter_title}: {count_in_chapter}</td></tr>\n'
            )

            previous_moves = []
            for idx, v in enumerate(group_list, start=1):
                total += 1
                highlight = (
                    ' style="background-color: #f0f0f0;"' if idx % 2 == 0 else ""
                )

                moves_html, current_moves = util.get_common_move_prefix_html(
                    v.mainline_moves, previous_moves, use_class=False
                )
                previous_moves = current_moves
                intro = "📌" if v.is_intro else ""

                yield (
                    f"<tr{highlight}>"
                    f"<td>{v.start_move}</td>"
                    f"<td>{v.chapter.color.title()[0]}</td>"
                    f'<td style="text-align: right">'
                    f'<a href="{URL_BASE}/{v.id}/">{v.id}</a></td>'
                    f'<td style="white-space: nowrap;">{v.title} {intro}</td>'
                    f'<td style="white-space: nowrap;">{moves_html}</td>'
                    "</tr>\n"
                )

        yield (
            f'<tr style="background-color: lightblue; font-weight: bold;">'
            f'<td colspan="5">Total variations: {total}</td></tr>\n'
            f"</table></body></html>"
        )

    return StreamingHttpResponse(
        row_generator(), content_type="text/html; charset=utf-8"
    )


def edit(request, variation_id=None):
    if variation_id is None:
        variation = Variation.objects.first()
    else:
        variation = get_object_or_404(
            Variation.objects.select_related("chapter").prefetch_related("moves"),
            pk=variation_id,
        )

    variation_data = serialize_variation(variation, mode="edit") if variation else {}
    context = {"variation_data": json.dumps(variation_data)}

    return render(request, "edit.html", context)


def edit_shared_move(request):
    fen = request.GET.get("fen")
    san = request.GET.get("san")
    color = request.GET.get("color")
    variation_id = request.GET.get("variation_id")

    if not all([fen, san, color, variation_id]):
        return HttpResponseBadRequest(
            "Missing required parameters: fen, san, color, variation_id"
        )

    shared_moves = list(
        SharedMove.objects.filter(fen=fen, san=san, opening_color=color)
    )

    moves = list(
        Move.objects.filter(
            fen=fen,
            san=san,
            variation__chapter__color=color,
        ).select_related(
            "variation",
            "variation__chapter",
            "shared_move",
        )
    )
    move_verbose = moves[0].move_verbose if moves else san

    move_data = serialize_shared_move(shared_moves, moves)

    move_data["fen"] = fen
    move_data["san"] = san
    move_data["color"] = color
    move_data["move_verbose"] = move_verbose
    move_data["variation_id"] = variation_id

    variation = get_object_or_404(
        Variation.objects.select_related("chapter").prefetch_related("moves"),
        pk=variation_id,
    )
    move_index = util.get_move_index_from_fen(fen)
    move_data["analysis_url"] = util.get_analysis_url(variation, index=move_index)

    context = {"move_data": json.dumps(move_data)}

    return render(request, "edit_shared.html", context)


def get_normalized_shapes(shapes):
    """JSON stringify on frontend will strip out spaces; let's put them back"""
    try:
        shapes_list = json.loads(shapes) if shapes else []
    except json.JSONDecodeError:
        print(f"⚠️  Invalid shapes JSON: {shapes!r}")
        shapes_list = []
    if not shapes_list:
        return ""
    else:
        return json.dumps(shapes_list, separators=(", ", ": "))


@csrf_exempt
@require_POST
@transaction.atomic
def save_variation(request):
    data = json.loads(request.body)
    variation_id = data.get("variation_id")
    print(f"💾 Saving variation {variation_id}")
    variation = get_object_or_404(Variation, pk=variation_id)
    variation.title = data["title"]  # no sanitization; displayed as x-text
    variation.start_move = data["start_move"]
    variation.save()

    opening_color = variation.chapter.color
    for idx, move in enumerate(variation.moves.all()):
        move_data = data["moves"][idx]

        shared_move_id = move_data.get("shared_move_id")
        if shared_move_id == "__new__":
            target_move = SharedMove.objects.create(
                fen=move.fen,
                san=move.san,
                opening_color=opening_color,
            )
            shared_move = target_move
        elif shared_move_id.isdigit():
            shared_id = int(shared_move_id)
            target_move = get_object_or_404(SharedMove, pk=int(shared_id))
            assert target_move.fen == move.fen, "SharedMove FEN mismatch"
            assert target_move.san == move.san, "SharedMove SAN mismatch"
            shared_move = target_move
        else:
            target_move = move
            shared_move = None

        target_move.annotation = util.strip_all_html(move_data["annotation"])
        target_move.text = util.clean_html(move_data["text"])
        target_move.alt = util.strip_all_html(move_data["alt"])
        target_move.alt_fail = util.strip_all_html(move_data["alt_fail"])
        target_move.shapes = get_normalized_shapes(move_data["shapes"])
        target_move.save()

        move.shared_move = shared_move  # link/unlink as needed
        move.save()

    return JsonResponse({"status": "success"})


@csrf_exempt
@require_POST
@transaction.atomic
def save_shared_move(request):
    data = json.loads(request.body)
    color = data.get("color")
    san = data.get("san")
    fen = data.get("fen")
    print(f"💾 Saving shared {color} {san} {fen}")

    for shared_move in data["shared_moves"]:
        shared_move_id = shared_move["id"]
        sharedmove = SharedMove.objects.get(id=shared_move_id)
        sharedmove.annotation = util.strip_all_html(shared_move["annotation"])
        sharedmove.text = util.clean_html(shared_move["text"])
        sharedmove.alt = util.strip_all_html(shared_move["alt"])
        sharedmove.alt_fail = util.strip_all_html(shared_move["alt_fail"])
        sharedmove.shapes = get_normalized_shapes(shared_move["shapes"])
        sharedmove.save()
        print(f"💾 Saved shared move #{shared_move_id}")

    for grouped_move in data["grouped_moves"]:
        shared_move_id = grouped_move["shared_move_id"]
        move_ids = grouped_move["move_ids"]
        shared_move = None  # will unlink if not set by __new__ or ID
        if shared_move_id == "__new__":
            print("💾 Creating new shared move")
            move_id = move_ids[0]
            move = get_object_or_404(Move, id=move_id)
            shared_move = SharedMove.objects.create(
                fen=fen,
                san=san,
                opening_color=color,
                text=move.text,
                annotation=move.annotation,
                alt=move.alt,
                alt_fail=move.alt_fail,
                shapes=move.shapes,
            )
        elif shared_move_id.isdigit():
            shared_move = get_object_or_404(SharedMove, id=int(shared_move_id))

        # we'll be trusting of our inputs here -- this is an area
        # to watch out if ever expanding to a multi-user app
        moves = Move.objects.filter(id__in=move_ids, san=san, fen=fen)
        # but we've added san/fen for safety, since update bypasses save protection
        moves.update(shared_move=shared_move)
        shared_move_label = f"#{shared_move.id}" if shared_move else "None"
        print(f"Setting shared move to {shared_move_label} for {len(move_ids)} moves")

        if shared_move and grouped_move["sync"] and shared_move_id != "__new__":
            # no need to sync if new since we've *just* created the
            # shared move with the same values as the moves
            print(f"Syncing shared move #{shared_move_id} values")
            for move in moves.iterator():
                move.text = shared_move.text
                move.annotation = shared_move.annotation
                move.alt = shared_move.alt
                move.alt_fail = shared_move.alt_fail
                move.shapes = shared_move.shapes
                move.save(
                    update_fields=["text", "annotation", "alt", "alt_fail", "shapes"]
                )

    return JsonResponse({"status": "success"})


def variation(request, variation_id=None):
    if variation_id is None:
        variation = Variation.objects.first()
    else:
        variation = get_object_or_404(
            Variation.objects.select_related("chapter").prefetch_related("moves"),
            pk=variation_id,
        )

    variation_data = (
        serialize_variation(variation, mode="variation") if variation else {}
    )
    context = {"variation_data": json.dumps(variation_data)}

    return render(request, "variation.html", context)


def home_upcoming(request, color=None, chapter_id=None):
    color = request.GET.get("color")
    chapter_id = request.GET.get("chapter_id")
    home_view = HomeView(color=color, chapter_id=chapter_id, upcoming_only=True)
    return JsonResponse(home_view.data)


"""
29 July 2025 production timings for home vs home_upcoming

⏱ Testing /
⏳ Try 100/100: 0.357816s
✅ Avg time for /: .3735s
⏱ Testing /home-upcoming/
⏳ Try 100/100: 0.218543s
✅ Avg time for /home-upcoming/: .2760s

Nice improvement but I wonder if it's really worth it to have a
separate endpoint. Seems bloated to return everything but it's
simpler, code-wise, and not that much slower.
"""


class HomeView:
    def __init__(self, color=None, chapter_id=None, upcoming_only=False):
        self.now = timezone.now()

        self.color = color
        self.chapter_id = chapter_id

        self.home_data = {
            "next_due": self.get_next_due(),
            "upcoming": self.get_upcoming_time_planner(),
        }
        if not upcoming_only:
            self.home_data.update(
                {
                    "nav": self.get_nav_data(),
                    "recent": self.get_recently_reviewed(),
                    "recently_added": self.get_recently_added(),
                    "levels": self.get_level_report(),
                }
            )

    @property
    def data(self):
        return self.home_data

    def get_variations(self):
        variations = Variation.objects.all()
        if self.color:
            variations = variations.filter(chapter__color=self.color)
        if self.chapter_id:
            variations = variations.filter(chapter_id=self.chapter_id).prefetch_related(
                "quiz_results"
            )
        return variations

    def get_nav_data(self):
        nav = {
            "color": "",
            "chapter_id": "",
            "chapter_title": "",
            "colors": [],
            "chapters": [],
            "variations": [],
            "total_var_count": 0,  # total white + black variations
            "color_var_count": 0,  # total white or black variations
        }
        if not self.color:
            for color in ["white", "black"]:
                variation_count = Variation.objects.filter(chapter__color=color).count()
                nav["total_var_count"] += variation_count
                nav["colors"].append(
                    {
                        "id": 1 if color == "white" else 2,
                        "title": color.title(),
                        "variation_count": variation_count,
                    }
                )
        elif not self.chapter_id:
            for chapter in (
                Chapter.objects.filter(color=self.color).order_by("title").iterator()
            ):
                variation_count = Variation.objects.filter(chapter=chapter).count()
                nav["color_var_count"] += variation_count
                nav["chapters"].append(
                    {
                        "id": chapter.id,
                        "title": chapter.title,
                        "variation_count": variation_count,
                    }
                )

            nav["color"] = self.color
        else:
            variations = get_sorted_variations(self.chapter_id)
            previous_moves = []
            for variation in variations:
                time_since_last_review = util.get_time_ago(
                    self.now, variation.get_latest_quiz_result_datetime()
                )
                time_until_next_review = util.format_time_until(
                    self.now, variation.next_review
                )

                moves_html, current_moves = util.get_common_move_prefix_html(
                    variation.mainline_moves_str, previous_moves
                )
                # TODO: might want to try sharing some code with serializer here
                nav["variations"].append(
                    {
                        "id": variation.id,
                        "title": variation.title,
                        "is_intro": variation.is_intro,
                        "level": variation.level,
                        "start_move": variation.start_move,
                        "time_since_last_review": time_since_last_review,
                        "time_until_next_review": time_until_next_review,
                        "mainline_moves_str": variation.mainline_moves_str,
                        "mainline_moves_html": moves_html,
                    }
                )
                previous_moves = current_moves

            nav["color"] = self.color
            nav["chapter_id"] = self.chapter_id
            nav["chapter_title"] = Chapter.objects.get(id=self.chapter_id).title

        return nav

    def get_level_report(self):
        level_counts = []

        levels = [
            (" 0 - Not started", 0),
            (" 1 - 7 hours", 1),
            (" 2 - 1 day", 2),
            (" 3 - 3 days", 3),
            (" 4 - 1 week", 4),
            (" 5 - 2 weeks", 5),
            (" 6 - 1 month", 6),
            (" 7 - 2 months", 7),
            (" 8 - 4 months", 8),
            (" 9 - 6 months", 9),
            ("10+", 10),
        ]

        variations = self.get_variations()
        for label, level in levels:
            if level == 10:
                count = variations.filter(level__gte=level).count()
            else:
                count = variations.filter(level=level).count()

            if count > 0:
                badge = "🌱" if level == 0 else "🌳" if level >= 9 else ""
                level_counts.append(
                    {
                        "label": f"{label} {badge}",
                        "count": count,
                    }
                )

        return level_counts

    def get_next_due(self):
        output = ""
        emoji = "🔮"
        variations = self.get_variations()
        if variations.filter(next_review__lte=self.now).count():
            output = "Now, and then in "
            emoji = "⏰"

        if (
            next_due := variations.filter(next_review__gt=self.now)
            .order_by("next_review")
            .first()
        ):
            output += util.format_time_until(self.now, next_due.next_review)
        else:
            output += "…?"

        # There is a next due js timer that expects this format
        # when less than one minute: "Next: 59s" (doesn't matter
        # what comes before or after)
        return f"{emoji} Next: {output}"

    def get_upcoming_time_planner(self):
        ranges = [
            ("Now", 0),
            ("1 hour", 1),
            # ("2 hours", 2),
            ("4 hours", 4),
            ("8 hours", 8),
            ("12 hours", 12),
            ("1 day", 1 * 24),
            # ("2 days", 2 * 24),
            ("3 days", 3 * 24),
            # ("4 days", 4 * 24),
            # ("5 days", 5 * 25),
            # ("6 days", 6 * 24),
            ("1 week", 1 * 7 * 24),
            # ("2 weeks", 2 * 7 * 24),
            # ("3 weeks", 3 * 7 * 24),
            ("1 month", 1 * 30 * 24),
            ("2 months", 2 * 30 * 24),
            ("4 months", 4 * 30 * 24),
            ("6 months", 6 * 30 * 24),
        ]
        times = []
        previous_count = -1
        for label, hours in ranges:
            count = self.get_variation_count_for_time_range(hours)
            if previous_count != count:
                previous_count = count
                times.append(
                    {
                        "label": label,
                        "count": count,
                    }
                )
        return times

    def get_variation_count_for_time_range(self, hours):
        end_time = self.now + timezone.timedelta(hours=hours)
        variations = self.get_variations()
        return variations.filter(next_review__lt=end_time).count()

    def get_recently_reviewed(self):
        variation_ids = self.get_variations().values_list("id", flat=True)
        recently_reviewed = (
            QuizResult.objects.filter(variation_id__in=variation_ids)
            .select_related("variation")
            .order_by("-datetime")[:25]
        )

        return [
            {
                "id": result.id,
                "variation_id": result.variation_id,
                "variation_title": result.variation.title,
                "datetime": util.get_time_ago(self.now, result.datetime),
                "level": result.level,
                "passed": "✅" if result.passed else "❌",
            }
            for result in recently_reviewed
        ]

    def get_recently_added(self):
        two_weeks_ago = self.now - timezone.timedelta(days=14)
        variations = (
            self.get_variations()
            .filter(Q(created_at__gte=two_weeks_ago) | Q(level=0))
            .order_by("-created_at")[:20]
        )
        added = []
        for variation in variations:
            added.append(
                {
                    "variation_id": variation.id,
                    "variation_title": variation.title,
                    "level": variation.level,
                    "created_at": util.get_time_ago(self.now, variation.created_at),
                    "next_review": util.format_time_until(
                        self.now, variation.next_review
                    ),
                }
            )

        return added


def stats(request):
    def row_generator():
        yr, mo, dy = settings.STATS_START_DATE
        all_start = timezone.make_aware(datetime(yr, mo, dy))
        qs = QuizResult.objects.filter(datetime__gte=all_start, level__gt=0)
        all_total = qs.count()
        passed = qs.filter(passed=True).count()
        percent = int((passed / all_total) * 100) if all_total else 0
        # excluding level 0, which is only "learning" and we won't judge
        level_labels = [f"L{n}" for n in range(1, 10)] + ["L10+"]

        favicon = "favicon-dev.ico" if settings.DEBUG else "favicon.ico"

        yield f"<html><head><title>Stats</title><meta name='viewport' content='width=device-width, initial-scale=1.0' /><link rel='icon' href='/static/icons/{favicon}' type='image/x-icon' /><body style='color: #d7af91; background-color: #222; font-family: Helvetica, sans-serif; font-size: 18px; margin-bottom: 222px; padding-top: 50px;'><div><h1>Stats!</h1>"  # noqa: E501

        # Daily Summary
        LAST_DAYS = 8
        yield f"<div class='levels-container'><h2>Daily Summary (Last {LAST_DAYS} Days)</h2>"  # noqa: E501
        yield "<table><tr>"
        yield "<th style='padding: 4px; text-align: right'>Date</th><th style='padding: 4px; text-align: right'>Result</th>"  # noqa: E501
        for label in level_labels:
            yield f"<th style='padding: 4px; text-align: right'>{label}</th>"
        yield "</tr>"

        days = LAST_DAYS
        level_totals = defaultdict(int)
        total_passed_all_days = 0
        total_reviewed_all_days = 0

        for delta in range(days - 1, -1, -1):
            day = timezone.localtime(timezone.now()) - timezone.timedelta(days=delta)
            start = timezone.make_aware(
                datetime.combine(day.date(), datetime.min.time())
            )
            end = start + timezone.timedelta(days=1)

            day_qs = qs.filter(datetime__gte=start, datetime__lt=end)
            day_total = day_qs.count()
            day_passed = day_qs.filter(passed=True).count()
            total_passed_all_days += day_passed
            total_reviewed_all_days += day_total

            day_percent = int((day_passed / day_total) * 100) if day_total else 0
            result_cell = (
                f"{day_passed}/{day_total} ({day_percent}%)" if day_total else "–"
            )

            level_counts = defaultdict(lambda: {"passed": 0, "total": 0})
            levels = day_qs.values("level").annotate(
                total_count=Count("id"),
                passed_count=Count("id", filter=Q(passed=True)),
            )
            for row in levels:
                lvl = row["level"]
                key = f"L{lvl}" if lvl < 10 else "L10+"
                level_counts[key]["total"] += row["total_count"]
                level_totals[key] += row["total_count"]

            yield f"<tr><td style='padding: 4px; text-align: right'>{day.date()}</td><td style='padding: 4px; text-align: right'>{result_cell}</td>"  # noqa: E501
            for label in level_labels:
                data = level_counts.get(label)
                if data and day_total:
                    val = f"{data['total']}"
                else:
                    val = "–"
                yield f"<td style='padding: 4px; text-align: right'>{val}</td>"
            yield "</tr>"

        # Final Avg row
        avg_percent = (
            int((total_passed_all_days / total_reviewed_all_days) * 100)
            if total_reviewed_all_days
            else 0
        )
        avg_passed = round(total_passed_all_days / days)
        avg_total = round(total_reviewed_all_days / days)
        avg_percent = int((avg_passed / avg_total) * 100) if avg_total else 0
        result_avg_cell = f"{avg_passed}/{avg_total} ({avg_percent}%)"

        yield f"<tr><td style='padding: 4px; text-align: right'><b>Avg</b></td><td style='padding: 4px; text-align: right'><b>{result_avg_cell}</b></td>"  # noqa: E501
        for label in level_labels:
            total = level_totals.get(label, 0)
            avg = round(total / days) if days else 0
            yield f"<td style='padding: 4px; text-align: right'><b>{avg}</b></td>"
        yield "</tr>"

        yield "</table></div>"

        # Overall
        yield "<div class='reviews-container'><h2>Quiz Results</h2>"
        yield (
            "<table><tr>"
            "<th></th>"
            "<th style='padding: 4px; text-align: right'>Passed</th>"
            "<th style='padding: 4px; text-align: right'>Total</th>"
            "<th style='padding: 4px; text-align: right'>Percent</th>"
            "</tr>"
        )
        yield (
            "<tr><td>All</td>"
            f"<td style='padding: 4px; text-align: right'>{passed}</td>"
            f"<td style='padding: 4px; text-align: right'>{all_total}</td>"
            f"<td style='padding: 4px; text-align: right'>{percent}%</td></tr>"
            "</table></div>"
        )

        # By Level
        yield "<div class='levels-container'><h2>Results by Level</h2>"
        yield "<table><tr>"
        yield "<th style='padding: 4px; text-align: right'>Level</th>"
        yield "<th style='padding: 4px; text-align: right'>Passed</th>"
        yield "<th style='padding: 4px; text-align: right'>Total</th>"
        yield "<th style='padding: 4px; text-align: right'>Percent</th></tr>"

        level_data = (
            qs.values("level")
            .annotate(
                total_count=Count("id"), passed_count=Count("id", filter=Q(passed=True))
            )
            .order_by("level")
        )
        for row in level_data:
            level = row["level"]
            total = row["total_count"]
            passed = row["passed_count"]
            percent = int((passed / total) * 100) if total else 0
            yield (
                f"<tr><td style='padding: 4px; text-align: right'>L{level}</td>"
                f"<td style='padding: 4px; text-align: right'>{passed}</td>"
                f"<td style='padding: 4px; text-align: right'>{total}</td>"
                f"<td style='padding: 4px; text-align: right'>{percent}%</td></tr>"
            )
        yield "</table></div>"

        # Weekly Summary
        yield "<div class='reviews-container'><h2>Weekly Summary</h2>"
        yield "<table><tr>"
        yield "<th style='padding: 4px; text-align: right'>Week Starting</th>"
        yield "<th style='padding: 4px; text-align: right'>Result</th>"
        for label in level_labels:
            yield f"<th style='padding: 4px; text-align: right'>{label}</th>"
        yield "</tr>"

        current = all_start
        one_week = timezone.timedelta(days=7)
        while current <= timezone.now():
            week_end = current + one_week
            week_qs = qs.filter(datetime__gte=current, datetime__lt=week_end)
            week_total = week_qs.count()
            week_passed = week_qs.filter(passed=True).count()
            week_percent = int((week_passed / week_total) * 100) if week_total else 0
            result_cell = (
                f"{week_passed}/{week_total} ({week_percent}%)" if week_total else "–"
            )

            level_counts = defaultdict(lambda: {"passed": 0, "total": 0})
            levels = week_qs.values("level").annotate(
                total_count=Count("id"),
                passed_count=Count("id", filter=Q(passed=True)),
            )
            for row in levels:
                lvl = row["level"]
                key = f"L{lvl}" if lvl < 10 else "L10+"
                level_counts[key]["total"] += row["total_count"]
                level_counts[key]["passed"] += row["passed_count"]

            yield f"<tr><td style='padding: 4px; text-align: right'>{current.date()}</td><td style='padding: 4px; text-align: right'>{result_cell}</td>"  # noqa: E501
            for label in level_labels:
                data = level_counts.get(label)
                if data:
                    pct = (
                        int((data["passed"] / data["total"]) * 100)
                        if data["total"]
                        else 0
                    )
                    val = f"{data['passed']}/{data['total']} ({pct}%)"
                else:
                    val = "–"
                align = (
                    "right"
                    if str(val)
                    .replace("/", "")
                    .replace("(", "")
                    .replace(")", "")
                    .replace("%", "")
                    .replace(" ", "")
                    .isdigit()
                    is False
                    else "right"
                )
                yield f"<td style='padding: 4px; text-align: {align}'>{val}</td>"
            yield "</tr>"

            current = week_end

        yield "</table></div>"

        # Upcoming Reviews
        # add back L0 since it is of interest for upcoming workload
        level_labels = ["L0"] + level_labels
        NEXT_DAYS = 30
        yield f"<div class='reviews-container'><h2>Upcoming Reviews (Next {NEXT_DAYS} Days)</h2>"  # noqa: E501
        yield "<table><tr><th style='padding: 4px; text-align: right'>Date</th>"
        for label in level_labels:
            yield f"<th style='padding: 4px; text-align: right'>{label}</th>"
        yield "<th style='padding: 4px; text-align: right'>Total</th></tr>"

        today = timezone.localtime().date()
        for offset in range(NEXT_DAYS):
            day = today + timezone.timedelta(days=offset)
            day_start = timezone.make_aware(datetime.combine(day, datetime.min.time()))
            day_end = day_start + timezone.timedelta(days=1)

            day_qs = (
                Variation.objects.filter(
                    next_review__gte=day_start, next_review__lt=day_end
                )
                .values("level")
                .annotate(count=Count("id"))
            )

            level_counts = defaultdict(int)
            total_for_day = 0
            for row in day_qs:
                lvl = row["level"]
                key = f"L{lvl}" if lvl < 10 else "L10+"
                level_counts[key] += row["count"]
                total_for_day += row["count"]

            yield f"<tr><td style='padding: 4px; text-align: right'>{day}</td>"

            for label in level_labels:
                val = level_counts.get(label) or "–"
                yield f"<td style='padding: 4px; text-align: right'>{val}</td>"
            yield f"<td style='padding: 4px; text-align: right'>{total_for_day}</td></tr>"  # noqa: E501

        yield "</table></div></div></body></html>"

    return StreamingHttpResponse(
        row_generator(), content_type="text/html; charset=utf-8"
    )
