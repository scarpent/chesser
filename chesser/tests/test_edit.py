import json

import pytest
from django.test import Client
from django.urls import reverse

from chesser.models import Chapter, Move, SharedMove, Variation


@pytest.fixture()
def chapter(db):
    return Chapter.objects.create(title="Test Chapter", color="white")


@pytest.fixture()
def variation_with_moves(chapter):
    variation = Variation.objects.create(
        title="Test Variation",
        chapter=chapter,
        start_move=2,
        mainline_moves_str="1.e4 e5",
    )
    Move.objects.create(
        variation=variation,
        move_num=1,
        sequence=0,
        san="e4",
        fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    )
    Move.objects.create(
        variation=variation,
        move_num=1,
        sequence=1,
        san="e5",
        fen="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
    )
    return variation


@pytest.fixture()
def auth_client(test_user):
    client = Client()
    client.login(username="testuser", password="testpassword")
    return client


# --- edit view ---


@pytest.mark.django_db
def test_edit_page_unauthenticated():
    client = Client()
    response = client.get(reverse("edit_default"))
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


@pytest.mark.django_db
def test_edit_authenticated(test_user):
    client = Client()
    client.login(username="testuser", password="testpassword")

    response = client.get(reverse("edit_default"))
    assert response.status_code == 200
    assert "Variation Title:" in response.content.decode()


@pytest.mark.django_db
def test_edit_specific_variation(auth_client, variation_with_moves):
    response = auth_client.get(reverse("edit_with_id", args=[variation_with_moves.id]))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Test Variation" in content


# --- edit_shared_move view ---


@pytest.mark.django_db
def test_edit_shared_move_unauthenticated(variation_with_moves):
    client = Client()
    move = variation_with_moves.moves.first()
    response = client.get(
        reverse("edit_shared_move"),
        {
            "fen": move.fen,
            "san": move.san,
            "color": "white",
            "variation_id": variation_with_moves.id,
        },
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_edit_shared_move_missing_params(auth_client):
    response = auth_client.get(reverse("edit_shared_move"))
    assert response.status_code == 400


@pytest.mark.django_db
def test_edit_shared_move_partial_params(auth_client):
    response = auth_client.get(
        reverse("edit_shared_move"), {"fen": "some-fen", "san": "e4"}
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_edit_shared_move_authenticated(auth_client, variation_with_moves):
    move = variation_with_moves.moves.first()
    response = auth_client.get(
        reverse("edit_shared_move"),
        {
            "fen": move.fen,
            "san": move.san,
            "color": "white",
            "variation_id": variation_with_moves.id,
        },
    )
    assert response.status_code == 200


# --- save_variation endpoint ---


@pytest.mark.django_db
def test_save_variation_unauthenticated(variation_with_moves):
    client = Client()
    response = client.post(
        reverse("save_variation"),
        data=json.dumps({"variation_id": variation_with_moves.id}),
        content_type="application/json",
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_save_variation(auth_client, variation_with_moves):
    moves = list(variation_with_moves.moves.order_by("sequence"))
    payload = {
        "variation_id": variation_with_moves.id,
        "title": "Updated Title",
        "chapter_id": str(variation_with_moves.chapter.id),
        "start_move": 2,
        "moves": [
            {
                "san": m.san,
                "shared_move_id": "",
                "annotation": "!",
                "text": "Test note",
                "alt": "",
                "alt_fail": "",
                "shapes": "",
            }
            for m in moves
        ],
    }

    response = auth_client.post(
        reverse("save_variation"),
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    variation_with_moves.refresh_from_db()
    assert variation_with_moves.title == "Updated Title"

    for move in variation_with_moves.moves.all():
        assert move.annotation == "!"
        assert move.text == "Test note"


@pytest.mark.django_db
def test_save_variation_invalid_chapter_id(auth_client, variation_with_moves):
    """Non-numeric chapter_id should return 400, not crash with 500."""
    moves = list(variation_with_moves.moves.order_by("sequence"))
    payload = {
        "variation_id": variation_with_moves.id,
        "title": "Test",
        "chapter_id": "Bishop's Opening",
        "start_move": 2,
        "moves": [
            {
                "san": m.san,
                "shared_move_id": "",
                "annotation": "",
                "text": "",
                "alt": "",
                "alt_fail": "",
                "shapes": "",
            }
            for m in moves
        ],
    }

    response = auth_client.post(
        reverse("save_variation"),
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["status"] == "error"


@pytest.mark.django_db
def test_save_variation_duplicate_mainline_in_chapter(
    auth_client, variation_with_moves
):
    """Moving to a chapter that already has this mainline returns 409."""
    other_chapter = Chapter.objects.create(title="Other Chapter", color="white")
    Variation.objects.create(
        title="Existing",
        chapter=other_chapter,
        start_move=2,
        mainline_moves_str=variation_with_moves.mainline_moves_str,
    )

    moves = list(variation_with_moves.moves.order_by("sequence"))
    payload = {
        "variation_id": variation_with_moves.id,
        "title": "Test",
        "chapter_id": str(other_chapter.id),
        "start_move": 2,
        "moves": [
            {
                "san": m.san,
                "shared_move_id": "",
                "annotation": "",
                "text": "",
                "alt": "",
                "alt_fail": "",
                "shapes": "",
            }
            for m in moves
        ],
    }

    response = auth_client.post(
        reverse("save_variation"),
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 409
    data = response.json()
    assert data["status"] == "error"
    assert "already exists" in data["message"]


@pytest.mark.django_db
def test_save_variation_creates_shared_move(auth_client, variation_with_moves):
    moves = list(variation_with_moves.moves.order_by("sequence"))
    payload = {
        "variation_id": variation_with_moves.id,
        "title": "Test Variation",
        "chapter_id": str(variation_with_moves.chapter.id),
        "start_move": 2,
        "moves": [
            {
                "san": moves[0].san,
                "shared_move_id": "__new__",
                "annotation": "",
                "text": "Shared text",
                "alt": "",
                "alt_fail": "",
                "shapes": "",
            },
            {
                "san": moves[1].san,
                "shared_move_id": "",
                "annotation": "",
                "text": "",
                "alt": "",
                "alt_fail": "",
                "shapes": "",
            },
        ],
    }

    response = auth_client.post(
        reverse("save_variation"),
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    moves[0].refresh_from_db()
    assert moves[0].shared_move is not None
    assert moves[0].shared_move.text == "Shared text"


@pytest.mark.django_db
def test_save_variation_with_shapes(auth_client, variation_with_moves):
    moves = list(variation_with_moves.moves.order_by("sequence"))
    shapes = [{"orig": "e2", "dest": "e4", "brush": "green"}]
    payload = {
        "variation_id": variation_with_moves.id,
        "title": "Test Variation",
        "chapter_id": str(variation_with_moves.chapter.id),
        "start_move": 2,
        "moves": [
            {
                "san": m.san,
                "shared_move_id": "",
                "annotation": "",
                "text": "",
                "alt": "",
                "alt_fail": "",
                "shapes": json.dumps(shapes) if i == 0 else "",
            }
            for i, m in enumerate(moves)
        ],
    }

    response = auth_client.post(
        reverse("save_variation"),
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200
    moves[0].refresh_from_db()
    assert moves[0].shapes != ""
    saved_shapes = json.loads(moves[0].shapes)
    assert saved_shapes[0]["orig"] == "e2"


# --- save_shared_move endpoint ---


@pytest.mark.django_db
def test_save_shared_move_unauthenticated(variation_with_moves):
    client = Client()
    response = client.post(
        reverse("save_shared_move"),
        data=json.dumps({}),
        content_type="application/json",
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_save_shared_move(auth_client, variation_with_moves):
    move = variation_with_moves.moves.first()
    shared = SharedMove.objects.create(
        fen=move.fen,
        san=move.san,
        opening_color="white",
        text="Original text",
    )
    move.shared_move = shared
    move.save()

    payload = {
        "fen": move.fen,
        "san": move.san,
        "color": "white",
        "shared_moves": [
            {
                "id": shared.id,
                "annotation": "!?",
                "text": "Updated shared text",
                "alt": "d4",
                "alt_fail": "",
                "shapes": "",
            }
        ],
        "grouped_moves": [],
    }

    response = auth_client.post(
        reverse("save_shared_move"),
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    shared.refresh_from_db()
    assert shared.text == "Updated shared text"
    assert shared.annotation == "!?"
    assert shared.alt == "d4"


@pytest.mark.django_db
def test_save_shared_move_creates_new(auth_client, variation_with_moves):
    move = variation_with_moves.moves.first()

    payload = {
        "fen": move.fen,
        "san": move.san,
        "color": "white",
        "shared_moves": [],
        "grouped_moves": [
            {
                "move_ids": [move.id],
                "shared_move_id": "__new__",
                "sync": False,
            }
        ],
    }

    response = auth_client.post(
        reverse("save_shared_move"),
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200

    move.refresh_from_db()
    assert move.shared_move is not None
    assert move.shared_move.fen == move.fen
    assert move.shared_move.san == move.san
