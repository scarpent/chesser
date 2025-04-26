from django.conf import settings


def build_info(request):
    return {
        "BUILD_TIMESTAMP": settings.BUILD_TIMESTAMP,
    }
