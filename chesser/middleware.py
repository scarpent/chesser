from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils.http import urlencode

from chesser.demo import demo_block_response


class LoginRequiredMiddleware:
    """
    Require authentication for almost everything, including /admin/.

    This forces all login to go through settings.LOGIN_URL
    and avoids exposing /admin/login/ at all.
    """

    ALLOW_PREFIXES = (
        settings.LOGIN_URL,  # "/login/"
        settings.STATIC_URL,  # "/static/"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            return self.get_response(request)

        path = request.path

        for prefix in self.ALLOW_PREFIXES:
            if prefix and path.startswith(prefix):
                return self.get_response(request)

        # For AJAX/API requests, don't redirect to HTML login
        accept = request.headers.get("Accept", "")
        xrw = request.headers.get("X-Requested-With", "")
        wants_json = "application/json" in accept
        is_ajax = xrw.lower() == "xmlhttprequest"

        if wants_json or is_ajax:
            return HttpResponse("Authentication required", status=401)

        # Redirect to your login page with next=...
        next_param = urlencode({"next": request.get_full_path()})
        login_url = f"{settings.LOGIN_URL}?{next_param}"
        return redirect(login_url)


class SecurityHeadersMiddleware:
    """
    Adds security headers that Django doesn't always provide out of the
    box (or that we want to control explicitly):
    - Content-Security-Policy
    - Permissions-Policy

    HSTS and SSL redirect are handled in settings via SecurityMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        csp = getattr(settings, "CHESSER_CSP", None)
        if csp:
            response.headers.setdefault("Content-Security-Policy", csp)

        permissions = getattr(settings, "CHESSER_PERMISSIONS_POLICY", None)
        if permissions:
            response.headers.setdefault("Permissions-Policy", permissions)

        return response


class DemoReadonlyMiddleware:
    """
    Demo mode write-protection backstop.

    Conceptual model:
      - Default behavior in demo: block unsafe writes
        everywhere (POST/PUT/PATCH/DELETE).
      - Some endpoints are "demo-aware no-ops" (e.g. report_result)
        and must be allowlisted.
      - A few blocked POSTs should redirect somewhere specific
        (e.g. import page), which we support via DEMO_REDIRECT_BY_PREFIX.

    This middleware should run AFTER SessionMiddleware + MessageMiddleware
    so that redirect-based blocks can show a message banner.
    """

    UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    # Endpoints that must still be allowed to run unsafe methods in demo mode.
    # Keep this list small and explicit.
    ALLOWLIST_PREFIXES = (
        "/login/",
        "/logout/",
        "/admin/login/",
        "/admin/logout/",
        "/report-result/",  # demo-aware no-op write (handled in-view)
    )

    # Optional redirect mapping for blocked (non-JSON) POSTs.
    # Keys are path prefixes; values are Django URL names (preferred) or paths.
    # This helps keep users on the page they were using, without needing decorators.
    DEMO_REDIRECT_BY_PREFIX = {
        "/upload-json-data/": "import",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def _redirect_target_for_path(self, path: str) -> str:
        for prefix, target in self.DEMO_REDIRECT_BY_PREFIX.items():
            if path.startswith(prefix):
                return target
        return "referer"

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if (
            getattr(settings, "IS_DEMO", False)
            and request.method in self.UNSAFE_METHODS
        ):
            path = request.path or "/"

            for prefix in self.ALLOWLIST_PREFIXES:
                if path.startswith(prefix):
                    return self.get_response(request)

            redirect_to = self._redirect_target_for_path(path)

            # Default deny: block the write attempt.
            # demo_block_response decides JSON vs redirect based on request headers.
            return demo_block_response(request, redirect_to=redirect_to)

        return self.get_response(request)
