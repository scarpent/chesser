from django.contrib.staticfiles.storage import StaticFilesStorage
from whitenoise.storage import CompressedManifestStaticFilesStorage


class HashedURLStorage(CompressedManifestStaticFilesStorage):
    """
    Staticfiles storage with explicit, predictable hashed URL behavior.

    Chesser uses WhiteNoise's manifest-based storage so `{% static %}` resolves
    *source paths* (e.g. `icons/favicon.ico`) to hashed filenames via
    `staticfiles.json`, matching production behavior.

    Why this override exists:
    - WhiteNoise (and Django internals) may sometimes pass filenames back through
      `storage.url()` that are already hashed/stored.
    - The default manifest storage assumes inputs are *source* paths and will
      attempt to re-resolve them through the manifest.
    - If a hashed filename is mistakenly treated as a source path, this results
      in "Missing staticfiles manifest entry" errors.

    This class makes `url()` effectively idempotent:
    - If `name` is a source path present in the manifest, it is resolved to the
      hashed filename.
    - If resolution fails, `name` is assumed to already be a stored/hashed file
      and is returned as-is under STATIC_URL.

    Testing note:
    Static/manifest behavior can surface differently in tests depending on
    whether `collectstatic` has been run. See `chesser/tests/conftest.py` for
    details on the opt-in test configuration that builds a real manifest when
    production-parity debugging is needed.
    """

    def url(self, name):
        try:
            # If `name` is a source path in the manifest, resolve to hashed name.
            name = self.stored_name(name)
        except ValueError:
            # Not in manifest — likely already a hashed/stored filename.
            return StaticFilesStorage.url(self, name)

        return StaticFilesStorage.url(self, name)
