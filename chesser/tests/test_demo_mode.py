import io
import json

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_demo_blocks_fetch_write_with_json_403_and_header(client, settings, test_user):
    """
    In demo mode, unsafe writes should be blocked globally by middleware.

    For fetch/JSON requests:
      - 403
      - JSON payload with status=demo_disabled
      - X-Chesser-Demo-Readonly: 1
    """
    settings.IS_DEMO = True
    client.login(username="testuser", password="testpassword")

    # Body doesn't matter; middleware should intercept before view logic runs.
    resp = client.post(
        reverse("save_variation"),
        data=json.dumps(
            {"variation_id": 123, "title": "x", "start_move": 1, "moves": []}
        ),
        content_type="application/json",
        HTTP_X_REQUESTED_WITH="fetch",
        HTTP_ACCEPT="application/json",
    )

    assert resp.status_code == 403
    assert resp.headers.get("X-Chesser-Demo-Readonly") == "1"

    payload = json.loads(resp.content.decode("utf-8"))
    assert payload["status"] == "demo_disabled"
    assert "Demo mode" in payload["message"]


@pytest.mark.django_db
def test_demo_blocks_upload_json_redirects_to_import(client, settings, test_user):
    """
    In demo mode, /upload-json-data/ should be blocked and redirect to the
    import page (via DEMO_REDIRECT_BY_PREFIX).

    Demo block messaging is intentionally suppressed (banner is sufficient),
    so do not assert messages here.
    """
    settings.IS_DEMO = True
    client.login(username="testuser", password="testpassword")

    file_obj = io.BytesIO(b'{"ok": true}')
    file_obj.name = "upload.json"

    resp = client.post(
        reverse("upload_json_data"),
        data={"uploaded_file": file_obj},
        HTTP_REFERER="/somewhere-else/",
    )

    assert resp.status_code == 302
    assert resp.headers["Location"] == reverse("import")
