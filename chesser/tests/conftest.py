"""
Pytest fixtures for Chesser.

Static files in tests (manifest vs non-manifest behavior)
--------------------------------------------------------

Chesser uses WhiteNoise with a manifest-based staticfiles storage in normal
operation. In production-like runs, `{% static %}` resolves *source paths* via
`staticfiles.json` and returns hashed filenames. This is intentional: templates
should reference source names (e.g. `icons/favicon.ico`), and the build step
(`collectstatic`) decides the hashed output name.

Important nuance for tests:
- Django's test client does *not* fetch static assets. It renders templates and
  returns HTML, but it won't actually request `/static/...` URLs. So most tests
  can pass without a test-time `collectstatic` run, even if JS/CSS files change.
- However, strict manifest storage can still surface errors during tests if
  something triggers manifest resolution at runtime (e.g. middleware startup,
  code calling `static()` / `storage.url()` at import time, or accidental
  leakage where hashed filenames are treated as source inputs). When that happens,
  failures look like: "Missing staticfiles manifest entry for '...'."

Recommended steady-state:
- Do *not* run `collectstatic` for the test suite by default. Keep tests fast and
  focused on behavior (responses, redirects, rendered content), not static build
  artifacts.

Opt-in production-parity mode:
- When debugging static/manifest issues (or when you explicitly want prod-like
  behavior), you can enable a one-time `collectstatic` run for tests. This builds
  a real manifest into a temporary STATIC_ROOT and makes `{% static %}` behave as
  it does in production.

To enable:
    CHESSER_TEST_COLLECTSTATIC=1 pytest

Diagnostic escape hatch (not recommended as default):
- For troubleshooting only, tests can be switched to a non-manifest storage
  backend. This bypasses manifest lookups and makes `{% static %}` behave like a
  simple `STATIC_URL + path` join, which can quickly confirm whether a failure is
  "static pipeline" vs "view/template logic".

    @pytest.fixture(autouse=True)
    def non_manifest_static_storage(settings):
        settings.STORAGES["staticfiles"] = {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        }

This is intentionally not enabled by default because it can hide bugs that would
otherwise surface before release.
"""

import os

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

_collectstatic_done = False


@pytest.fixture()
def test_user(db):
    return User.objects.create_user(username="testuser", password="testpassword")


@pytest.fixture(autouse=True)
def collectstatic_for_tests(settings, tmp_path_factory):
    """
    Optional: build a real staticfiles manifest for tests (production-parity mode).

    Enabled only when CHESSER_TEST_COLLECTSTATIC=1 is set in the environment.
    Runs once per test session (guarded) but remains function-scoped so it can
    use pytest-django's `settings` fixture.
    """
    if os.getenv("CHESSER_TEST_COLLECTSTATIC") != "1":
        return

    global _collectstatic_done
    if _collectstatic_done:
        return

    static_root = tmp_path_factory.mktemp("staticfiles")
    settings.STATIC_ROOT = str(static_root)

    call_command("collectstatic", interactive=False, verbosity=0, clear=True)

    _collectstatic_done = True
