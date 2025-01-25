from django.urls import reverse
from django.test import Client

def test_home_page():
    client = Client()
    response = client.get(reverse('home'))
    assert response.status_code == 200
