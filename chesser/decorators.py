"""Small, focused view decorators.

Currently this module only contains demo-mode write protection.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect

F = TypeVar("F", bound=Callable[..., HttpResponse])


def is_demo_mode() -> bool:
    """Return True when the site is running in demo (read-only) mode."""
    return bool(getattr(settings, "IS_DEMO", False))


def demo_write_guard(*, json_response: bool = False, redirect_to: str = "home"):
    """Block write actions in demo mode.

    - json_response=True: return 403 JSON for fetch/XHR endpoints.
    - otherwise: redirect with a Django warning message.
    """

    def decorator(view_func: F) -> F:
        @wraps(view_func)
        def _wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            if is_demo_mode():
                msg = "Demo mode: this action is disabled (read-only)."

                if json_response:
                    return JsonResponse(
                        {"status": "demo_disabled", "message": msg},
                        status=403,
                    )

                messages.warning(request, f"🧪 {msg}")
                return redirect(redirect_to)

            return view_func(request, *args, **kwargs)

        return _wrapped  # type: ignore[return-value]

    return decorator
