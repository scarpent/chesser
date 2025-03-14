import pytest
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
def test_home_page_unauthenticated():
    client = Client()
    response = client.get(reverse("home"))
    assert response.status_code == 302
