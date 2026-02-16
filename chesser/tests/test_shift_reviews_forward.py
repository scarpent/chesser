from datetime import timedelta
from unittest import mock

import pytest
from django.core.management import call_command
from django.utils import timezone

from chesser.models import Chapter, Variation
from chesser.util import END_OF_TIME_DT

FROZEN_NOW = timezone.now().replace(microsecond=0)


@pytest.fixture()
def chapter(db):
    return Chapter.objects.create(title="Test Chapter", color="white")


def _make_variation(chapter, title, next_review):
    return Variation.objects.create(
        title=title,
        chapter=chapter,
        mainline_moves_str=title,
        next_review=next_review,
    )


def _call_shift(minutes=10):
    with mock.patch("django.utils.timezone.now", return_value=FROZEN_NOW):
        call_command("shift_reviews_forward", "--minutes", str(minutes))


@pytest.mark.django_db
def test_concrete_shift_with_mixed_review_times(chapter):
    """
    Five variations with a spread of review times, plus one at end-of-time.
    After shifting with --minutes 10, the earliest should land at now+10m
    and all others should shift by the same delta. End-of-time stays put.
    """
    now = FROZEN_NOW

    # Concrete times relative to now
    v_past_far = _make_variation(chapter, "a", now - timedelta(hours=2))
    v_past_near = _make_variation(chapter, "b", now - timedelta(minutes=30))
    v_now = _make_variation(chapter, "c", now)
    v_future_near = _make_variation(chapter, "d", now + timedelta(hours=1))
    v_future_far = _make_variation(chapter, "e", now + timedelta(days=3))
    v_end = _make_variation(chapter, "f", END_OF_TIME_DT)

    _call_shift(minutes=10)

    # The oldest was v_past_far at now-2h.
    # Target is now+10m, so delta = 2h10m.
    expected_delta = timedelta(hours=2, minutes=10)

    for v in [v_past_far, v_past_near, v_now, v_future_near, v_future_far, v_end]:
        v.refresh_from_db()

    # Each non-end-of-time variation shifts by exactly the same delta
    assert v_past_far.next_review == now - timedelta(hours=2) + expected_delta
    assert v_past_near.next_review == now - timedelta(minutes=30) + expected_delta
    assert v_now.next_review == now + expected_delta
    assert v_future_near.next_review == now + timedelta(hours=1) + expected_delta
    assert v_future_far.next_review == now + timedelta(days=3) + expected_delta

    # Sanity: the earliest is now exactly at now+10m
    assert v_past_far.next_review == now + timedelta(minutes=10)

    # End-of-time must NOT be shifted
    assert v_end.next_review == END_OF_TIME_DT


@pytest.mark.django_db
def test_shift_preserves_relative_gaps(chapter):
    """The gaps between non-end-of-time variations are unchanged."""
    now = FROZEN_NOW

    v1 = _make_variation(chapter, "a", now - timedelta(hours=5))
    v2 = _make_variation(chapter, "b", now - timedelta(hours=2))
    v3 = _make_variation(chapter, "c", now + timedelta(hours=1))

    gap_1_2 = v2.next_review - v1.next_review
    gap_2_3 = v3.next_review - v2.next_review

    _call_shift()

    v1.refresh_from_db()
    v2.refresh_from_db()
    v3.refresh_from_db()

    assert v2.next_review - v1.next_review == gap_1_2
    assert v3.next_review - v2.next_review == gap_2_3


@pytest.mark.django_db
def test_shift_custom_minutes(chapter):
    """The --minutes flag controls where the earliest lands."""
    now = FROZEN_NOW

    v = _make_variation(chapter, "a", now - timedelta(hours=1))
    _make_variation(chapter, "b", END_OF_TIME_DT)

    _call_shift(minutes=60)

    v.refresh_from_db()
    # Was 1h behind now, shifted so it lands at now+60m
    assert v.next_review == now + timedelta(minutes=60)


@pytest.mark.django_db
def test_shift_only_end_of_time_variations(chapter):
    """Only end-of-time variations — nothing to shift, no error."""
    _make_variation(chapter, "a", END_OF_TIME_DT)

    _call_shift()

    v = Variation.objects.get(title="a")
    assert v.next_review == END_OF_TIME_DT


@pytest.mark.django_db
def test_shift_excludes_archived(chapter):
    """Archived variations should not be shifted."""
    now = FROZEN_NOW

    v_active = _make_variation(chapter, "a", now - timedelta(hours=1))
    v_archived = _make_variation(chapter, "b", now - timedelta(hours=2))
    v_archived.archived = True
    v_archived.save()

    _call_shift(minutes=10)

    v_active.refresh_from_db()
    v_archived.refresh_from_db()

    # Active variation shifted
    assert v_active.next_review == now + timedelta(minutes=10)
    # Archived variation untouched
    assert v_archived.next_review == now - timedelta(hours=2)


@pytest.mark.django_db
def test_shift_default_is_10_minutes(chapter):
    """If --minutes is omitted, earliest lands at now + 10 minutes."""
    now = FROZEN_NOW

    v = _make_variation(chapter, "a", now - timedelta(hours=1))

    # Call WITHOUT passing --minutes
    with mock.patch("django.utils.timezone.now", return_value=FROZEN_NOW):
        call_command("shift_reviews_forward")

    v.refresh_from_db()

    # Oldest was 1h behind now → should land at now + 10m
    assert v.next_review == now + timedelta(minutes=10)
