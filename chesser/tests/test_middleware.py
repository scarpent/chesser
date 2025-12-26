def test_unauthenticated_ajax_returns_401(client):
    """
    Unauthenticated AJAX/JSON requests should get 401, not a redirect to /login/.
    """
    resp = client.get(
        "/",
        HTTP_ACCEPT="application/json",
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert resp.status_code == 401
    # A redirect would include Location
    assert "Location" not in resp.headers


def test_unauthenticated_browser_redirects_to_login_with_next(client):
    """
    Normal browser requests should redirect to /login/ with next=...
    """
    resp = client.get("/some/protected/page/?q=1")
    assert resp.status_code == 302

    location = resp.headers["Location"]
    assert location.startswith("/login/?")
    assert "next=%2Fsome%2Fprotected%2Fpage%2F%3Fq%3D1" in location
