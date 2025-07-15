from django.test import RequestFactory

from chesser.context_processors import build_info


def test_build_info_uses_settings_value(settings):
    settings.BUILD_TIMESTAMP = "1234567890"
    request = RequestFactory().get("/")
    context = build_info(request)
    assert context == {"BUILD_TIMESTAMP": "1234567890"}
