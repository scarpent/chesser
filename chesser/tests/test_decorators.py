import json

import pytest
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory

from chesser.decorators import demo_readonly


def _attach_session_and_messages(request):
    """Ensure request has session + messages, like real middleware."""
    middleware = SessionMiddleware(lambda req: HttpResponse())
    middleware.process_request(request)
    request.session.save()

    storage = FallbackStorage(request)
    setattr(request, "_messages", storage)  # noqa: B010
    return request


def _ok_view(request):
    return HttpResponse("ok")


@pytest.mark.django_db
def test_demo_readonly_allows_when_not_demo(settings):
    settings.IS_DEMO = False
    rf = RequestFactory()
    request = _attach_session_and_messages(rf.post("/whatever/"))

    wrapped = demo_readonly()(_ok_view)
    response = wrapped(request)
    assert response.status_code == 200
    assert response.content == b"ok"


@pytest.mark.django_db
def test_demo_readonly_redirects_with_message_for_form_posts(settings):
    settings.IS_DEMO = True
    rf = RequestFactory()
    request = _attach_session_and_messages(rf.post("/import-json/"))

    wrapped = demo_readonly(redirect_to="import")(_ok_view)
    response = wrapped(request)

    assert response.status_code == 302
    assert response["Location"].endswith("/import/")

    msgs = list(getattr(request, "_messages"))  # noqa: B009
    assert len(msgs) == 1
    assert "Demo mode" in msgs[0].message


@pytest.mark.django_db
def test_demo_readonly_returns_403_json_for_ajax(settings):
    settings.IS_DEMO = True
    rf = RequestFactory()
    request = _attach_session_and_messages(rf.post("/save-variation/"))

    wrapped = demo_readonly(json_response=True)(_ok_view)
    response = wrapped(request)

    assert response.status_code == 403
    payload = json.loads(response.content.decode("utf-8"))
    assert payload["status"] == "demo_disabled"
    assert "Demo mode" in payload["message"]
