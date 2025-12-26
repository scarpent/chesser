from urllib.parse import parse_qs, urlparse

from django.test import Client
from django.urls import reverse


def test_admin_page_unauthenticated():
    client = Client()
    response = client.get("/admin/")
    assert response.status_code == 302

    # Response.url is the redirect target.
    parsed = urlparse(response.url)
    assert parsed.path == "/login/"

    qs = parse_qs(parsed.query)
    assert qs["next"] == ["/admin/"]

    assert not response.url.startswith("/admin/login/")


def test_login_page_unauthenticated():
    client = Client()
    response = client.get(reverse("login"))
    assert response.status_code == 200
    assert "Username:" in response.content.decode()


def test_login_page_authenticated(test_user):
    client = Client()
    client.login(username="testuser", password="testpassword")

    response = client.get(reverse("login"))
    assert response.status_code == 200
    assert "Username:" in response.content.decode()
