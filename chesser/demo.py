# chesser/demo.py
from __future__ import annotations

from django.contrib import messages
from django.contrib.messages.api import MessageFailure
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect

DEMO_READONLY_MSG = "Demo mode: this action is disabled (read-only)."
DEMO_READONLY_HEADER = "X-Chesser-Demo-Readonly"


def request_wants_json(request: HttpRequest) -> bool:
    """
    Best-effort signal that the caller expects a JSON response.

    Supported signals:
      - our own fetch calls: X-Requested-With: fetch
      - Accept: application/json
      - Content-Type: application/json
    """
    xrw = (request.headers.get("X-Requested-With") or "").lower()
    if xrw == "fetch":
        return True

    accept = (request.headers.get("Accept") or "").lower()
    if "application/json" in accept:
        return True

    content_type = (request.headers.get("Content-Type") or "").lower()
    if "application/json" in content_type:
        return True

    return False


def demo_block_response(
    request: HttpRequest,
    *,
    json_response: bool | None = None,
    redirect_to: str = "referer",
    message: str | None = None,
) -> HttpResponse:
    """
    Standard demo-mode write protection response.

    - For fetch/JSON callers: JSON 403 + X-Chesser-Demo-Readonly: 1
    - For normal browser POSTs: Django message + redirect

    redirect_to:
      - "referer": redirect back to HTTP_REFERER if available; else "home"
      - otherwise: treated as a Django URL name (e.g. "import") or a path
    """
    msg = message or DEMO_READONLY_MSG

    if json_response is None:
        json_response = request_wants_json(request)

    if json_response:
        resp = JsonResponse({"status": "demo_disabled", "message": msg}, status=403)
        resp[DEMO_READONLY_HEADER] = "1"
        return resp

    # Best-effort: if messages middleware isn't installed/active, don't 500.
    try:
        messages.warning(request, f"🧪 {msg}")
    except MessageFailure:
        pass

    if redirect_to == "referer":
        referer = request.META.get("HTTP_REFERER")
        if referer:
            return redirect(referer)
        return redirect("home")

    return redirect(redirect_to)
