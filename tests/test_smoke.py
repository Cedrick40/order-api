import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_create_user_with_email_login():
    User = get_user_model()
    user = User.objects.create_user(email="a@example.com", password="Pass12345!")
    assert user.role == "customer"
    assert user.check_password("Pass12345!")