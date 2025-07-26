from django.test import RequestFactory

from chesser.context_processors import template_settings


def test_template_settings(settings):
    settings.BUILD_TIMESTAMP = "1234567890"
    request = RequestFactory().get("/")
    context = template_settings(request)
    assert context == {
        "BUILD_TIMESTAMP": "1234567890",
        "CHESS_PIECE_SET": "fantasy",
        "CHESS_BOARD_COLOR": "brown",
    }
