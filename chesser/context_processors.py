from django.conf import settings


def template_settings(request):
    return {
        "BUILD_TIMESTAMP": settings.BUILD_TIMESTAMP,  # used for cache busting at times
        "BUILD_STARTED_AT": settings.BUILD_STARTED_AT,
        "IS_DEMO": getattr(settings, "IS_DEMO", False),
        "CHESS_PIECE_SET": getattr(settings, "CHESS_PIECE_SET", "fantasy"),
        "CHESS_BOARD_COLOR": getattr(settings, "CHESS_BOARD_COLOR", "brown"),
    }
