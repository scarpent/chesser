import pytest
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
def test_variation_page_unauthenticated():
    client = Client()
    response = client.get(reverse("variation_default"))
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


@pytest.mark.django_db
def test_variation_page_authenticated(test_user):
    """This page doesn't make sense without content
    but this still tests the page."""
    client = Client()
    client.login(username="testuser", password="testpassword")

    response = client.get(reverse("variation_default"))
    assert response.status_code == 200
    assert "extra study" in response.content.decode()
