import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

PASSWORD = "Rk7!vQ2m#Lp9"


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def make_user(db):
    User = get_user_model()

    def _make(email="user@example.com", role="customer"):
        return User.objects.create_user(email=email, password=PASSWORD, role=role)

    return _make


@pytest.fixture
def login_as(make_user):
    """Create a user with a role and return (client logged in, user)."""
    def _login(role="customer", email=None):
        user = make_user(email=email or f"{role}@example.com", role=role)
        client = APIClient()
        client.force_authenticate(user=user)
        return client, user

    return _login