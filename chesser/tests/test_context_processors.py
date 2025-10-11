from django.test import RequestFactory

from chesser.context_processors import template_settings


def test_template_settings(settings):
    request = RequestFactory().get("/")
    context = template_settings(request)
    assert context["CHESS_PIECE_SET"] == "fantasy"
    assert context["CHESS_BOARD_COLOR"] == "brown"
