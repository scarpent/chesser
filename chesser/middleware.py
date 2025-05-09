from django.conf import settings
from django.shortcuts import redirect


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip the login check for admin and login URLs
        if not request.user.is_authenticated:
            if request.path not in [settings.LOGIN_URL, "/admin/"]:
                return redirect(settings.LOGIN_URL)
        response = self.get_response(request)
        return response
