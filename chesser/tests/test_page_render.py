import re
from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from chesser.models import Chapter, Variation

# Strip zones where raw '<' is expected and not our template output:
# pre/code for tutorial-style content, script for JS blobs, textarea for editors.
_SAFE_ZONE_RE = re.compile(
    r"<(script|pre|code|textarea)[^>]*>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)

# A broken tag: '<' immediately followed by whitespace.
# In correctly rendered Django HTML this should never appear — template
# auto-escaping turns bare '<' in values into '&lt;', and tag names must
# start directly after '<' with no whitespace.
_BROKEN_TAG_RE = re.compile(r"<\s")


def _decode(response) -> str:
    if hasattr(response, "streaming_content"):
        return b"".join(response.streaming_content).decode()
    return response.content.decode()


def _find_broken_tags(html: str) -> list[str]:
    """Return context snippets around any suspicious '<\\s' fragments."""
    cleaned = _SAFE_ZONE_RE.sub("", html)
    hits = []
    for m in _BROKEN_TAG_RE.finditer(cleaned):
        start = max(0, m.start() - 10)
        end = min(len(cleaned), m.end() + 60)
        hits.append(repr(cleaned[start:end].strip()))
    return hits


@pytest.fixture()
def auth_client(test_user):
    client = Client()
    client.login(username="testuser", password="testpassword")
    return client


@pytest.fixture()
def due_variation(db):
    chapter = Chapter.objects.create(title="Test Chapter", color="white")
    return Variation.objects.create(
        title="Test Variation",
        chapter=chapter,
        mainline_moves_str="1.e4",
        level=1,
        next_review=timezone.now() - timedelta(hours=1),
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name",
    ["home", "review_default", "stats", "import"],
)
def test_no_broken_tags_simple_pages(auth_client, url_name):
    response = auth_client.get(reverse(url_name))
    assert response.status_code == 200
    hits = _find_broken_tags(_decode(response))
    assert not hits, f"{url_name}: broken tag fragments:\n" + "\n".join(hits)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name",
    ["review_with_id", "edit_with_id", "variation"],
)
def test_no_broken_tags_variation_pages(auth_client, due_variation, url_name):
    url = reverse(url_name, kwargs={"variation_id": due_variation.id})
    response = auth_client.get(url)
    assert response.status_code == 200
    hits = _find_broken_tags(_decode(response))
    assert not hits, f"{url_name}: broken tag fragments:\n" + "\n".join(hits)
