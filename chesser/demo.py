from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse

from chesser.models import Variation

DEMO_READONLY_MSG = "Demo mode: this action is disabled (read-only)."
DEMO_READONLY_HEADER = "X-Chesser-Demo-Readonly"

VARIATION_URL_NAME = "variation"
REVIEW_URL_NAME = "review_with_id"


@dataclass(frozen=True)
class DemoEntry:
    """
    A stable demo "slot".

    - key: stable identifier used by templates + seed_demo
    - title: the canonical title we expect to exist in the demo repertoire
    - icontains: fallback substring match so small title tweaks don't break everything
    - description: small blurb used on the homepage demo guide (optional)
    """

    key: str
    title: str
    icontains: str | None = None
    description: str = ""


DEMO_ENTRIES: list[DemoEntry] = [
    # How-to variations
    DemoEntry(
        key="howto_html",
        title="Basic HTML Formatting",
        icontains="Basic HTML",
        description="Allowed HTML and examples.",
    ),
    DemoEntry(
        key="howto_subvars",
        title="Subvariation Syntax",
        icontains="Subvariation Syntax",
        description="Rules and examples for PGN comment parsing and navigable subvariations.",  # noqa: E501
    ),
    # Example lines
    DemoEntry(
        key="scotch_nxd4",
        title="Scotch 4...Nxd4",
        icontains="Scotch 4...Nxd4",
        description="A pour move you can savor. 🥃",
    ),
    DemoEntry(
        key="italian_ng5",
        title="Italian 4.Ng5 Knight Attack",
        icontains="Italian 4.Ng5",
        description="Don’t fear the Ng5 reaper. 💀",
    ),
    DemoEntry(
        key="alekhine_osullivan",
        title="Alekhine’s - O’Sullivan Gambit",
        # This fallback avoids curly-quote / hyphen drift.
        icontains="Sullivan Gambit",
        description="A provocative gambit from a notorious troublemaker. ☘️",
    ),
    DemoEntry(
        key="scandi_jb",
        title="John B’s Favorite Scandi Line",
        icontains="Favorite Scandi",
        description="No nonsense. Raid the center. 🪓",
    ),
]


def resolve_demo_variations(*, strict: bool = False) -> dict[str, Optional[Variation]]:
    """
    Resolve demo entries to Variation objects.

    Matching strategy:
      1) exact title match
      2) title__icontains fallback (if provided)

    Returns: dict of key -> Variation (or None if missing)

    If strict=True, raises ValueError if any entry cannot be resolved.
    """
    resolved: dict[str, Optional[Variation]] = {}

    for entry in DEMO_ENTRIES:
        v = Variation.objects.filter(title=entry.title).first()
        if not v and entry.icontains:
            v = Variation.objects.filter(title__icontains=entry.icontains).first()

        resolved[entry.key] = v

    if strict:
        missing = [k for k, v in resolved.items() if v is None]
        if missing:
            raise ValueError(f"Missing demo variations for keys: {missing}")

    return resolved


def get_demo_links_payload() -> dict[str, dict]:
    """
    Payload for home page JSON (homeData.demo.*).

    Example:
      homeData.demo.italian_ng5.variation_url
      homeData.demo.italian_ng5.review_url
      homeData.demo.italian_ng5.title
      homeData.demo.italian_ng5.description

    Safe if an entry is missing: urls are None and id is None.
    """
    resolved = resolve_demo_variations(strict=False)
    out: dict[str, dict] = {}

    for entry in DEMO_ENTRIES:
        v = resolved.get(entry.key)

        if not v:
            out[entry.key] = {
                "id": None,
                "title": entry.title,
                "description": entry.description,
                "variation_url": None,
                "review_url": None,
            }
            continue

        out[entry.key] = {
            "id": v.id,
            "title": v.title,  # use real DB title (in case it changed)
            "description": entry.description,
            "variation_url": reverse(VARIATION_URL_NAME, args=[v.id]),
            "review_url": reverse(REVIEW_URL_NAME, args=[v.id]),
        }

    return out


def get_demo_home_payload() -> dict[str, object]:
    """
    Payload for the home page demo guide.

    - 'links' is the resolved, display-ready info
    - 'howto_items' and 'example_items' are just ordered lists of demo keys
    """
    return {
        "links": get_demo_links_payload(),
        "howto_items": [
            "howto_html",
            "howto_subvars",
        ],
        "example_items": [
            "italian_ng5",
            "scotch_nxd4",
            "alekhine_osullivan",
            "scandi_jb",
        ],
    }


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

    if redirect_to == "referer":
        referer = request.META.get("HTTP_REFERER")
        if referer:
            return redirect(referer)
        return redirect("home")

    return redirect(redirect_to)
