import pytest
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
def test_edit_page_unauthenticated():
    client = Client()
    response = client.get(reverse("edit_default"))
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


@pytest.mark.django_db
def test_edit_authenticated(test_user):
    client = Client()
    client.login(username="testuser", password="testpassword")

    response = client.get(reverse("edit_default"))
    assert response.status_code == 200
    assert "Variation Name:" in response.content.decode()
