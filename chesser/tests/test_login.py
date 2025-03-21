import pytest
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
def test_admin_page_unauthenticated():
    client = Client()
    response = client.get("/admin/")
    assert response.status_code == 302
    # ultimately we redirect to our own login page
    assert response.url == "/admin/login/?next=/admin/"


@pytest.mark.django_db
def test_login_page_unauthenticated():
    client = Client()
    response = client.get(reverse("login"))
    assert response.status_code == 200
    assert "Username:" in response.content.decode()


@pytest.mark.django_db
def test_login_page_authenticated(test_user):
    client = Client()
    client.login(username="testuser", password="testpassword")

    response = client.get(reverse("login"))
    assert response.status_code == 200
    assert "Username:" in response.content.decode()
