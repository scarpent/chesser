import json

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from chesser.models import Chapter, Variation


@pytest.fixture()
def chapter(db):
    return Chapter.objects.create(title="Test Chapter", color="white")


def _make_variation(chapter, level, next_review):
    return Variation.objects.create(
        title="Test Variation",
        chapter=chapter,
        mainline_moves_str="1.e4",
        level=level,
        next_review=next_review,
    )


def _post_result(client, variation_id, passed=True):
    return client.post(
        reverse("report_result"),
        data=json.dumps({"variation_id": variation_id, "passed": passed}),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_review_page_unauthenticated():
    client = Client()
    response = client.get(reverse("review_default"))
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


@pytest.mark.django_db
def test_review_page_authenticated(test_user):
    client = Client()
    client.login(username="testuser", password="testpassword")

    response = client.get(reverse("review_default"))
    assert response.status_code == 200
    assert "review-stats" in response.content.decode()


@pytest.mark.django_db
def test_report_result_due_variation_accepted(test_user, chapter):
    """A variation that is due (next_review in the past) should be accepted."""
    client = Client()
    client.login(username="testuser", password="testpassword")

    past = timezone.now() - timezone.timedelta(hours=1)
    v = _make_variation(chapter, level=3, next_review=past)
    old_level = v.level

    resp = _post_result(client, v.pk)
    assert resp.status_code == 200
    assert json.loads(resp.content)["status"] == "success"

    v.refresh_from_db()
    assert v.level == old_level + 1


@pytest.mark.django_db
def test_report_result_not_yet_due_ignored(test_user, chapter):
    """A variation with level > 0 and next_review in the future should be ignored."""
    client = Client()
    client.login(username="testuser", password="testpassword")

    future = timezone.now() + timezone.timedelta(days=30)
    v = _make_variation(chapter, level=5, next_review=future)
    old_level = v.level

    resp = _post_result(client, v.pk)
    assert resp.status_code == 200
    assert json.loads(resp.content)["status"] == "ignored"

    v.refresh_from_db()
    assert v.level == old_level  # unchanged


@pytest.mark.django_db
def test_report_result_level_zero_always_accepted(test_user, chapter):
    """Level 0 (unlearned) variations are always accepted regardless of next_review."""
    client = Client()
    client.login(username="testuser", password="testpassword")

    future = timezone.now() + timezone.timedelta(days=999)
    v = _make_variation(chapter, level=0, next_review=future)

    resp = _post_result(client, v.pk)
    assert resp.status_code == 200
    assert json.loads(resp.content)["status"] == "success"

    v.refresh_from_db()
    assert v.level == 1
