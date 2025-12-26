from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils.http import urlencode


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
