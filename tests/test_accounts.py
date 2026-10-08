import pytest

from apps.accounts.models import Customer
from tests.conftest import PASSWORD

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ME = "/api/v1/me"


@pytest.mark.django_db
def test_register_creates_customer_user_and_profile(api):
    r = api.post(REGISTER, {"email": "new@example.com", "password": PASSWORD, "full_name": "New User"})
    assert r.status_code == 201
    assert r.data["role"] == "customer"
    assert Customer.objects.filter(user__email="new@example.com").exists()


@pytest.mark.django_db
def test_register_duplicate_email_gives_friendly_error(api, make_user):
    make_user(email="dup@example.com")
    r = api.post(REGISTER, {"email": "dup@example.com", "password": PASSWORD, "full_name": "X"})
    assert r.status_code == 400
    assert r.data["error"]["code"] == "VALIDATION_ERROR"
    assert "already exists" in r.data["error"]["message"]


@pytest.mark.django_db
def test_register_weak_password_rejected(api):
    r = api.post(REGISTER, {"email": "w@example.com", "password": "123", "full_name": "W"})
    assert r.status_code == 400
    assert r.data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_login_returns_tokens_and_me_works(api, make_user):
    make_user(email="login@example.com")
    r = api.post(LOGIN, {"email": "login@example.com", "password": PASSWORD})
    assert r.status_code == 200
    assert "access" in r.data and "refresh" in r.data
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    me = api.get(ME)
    assert me.status_code == 200
    assert me.data["email"] == "login@example.com"


@pytest.mark.django_db
def test_login_wrong_password_returns_standard_error(api, make_user):
    make_user(email="wrong@example.com")
    r = api.post(LOGIN, {"email": "wrong@example.com", "password": "nope"})
    assert r.status_code == 401
    assert r.data["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.django_db
def test_me_without_token_is_401_with_standard_shape(api):
    r = api.get(ME)
    assert r.status_code == 401
    assert set(r.data["error"]) == {"code", "message", "details"}


@pytest.mark.django_db
def test_customer_cannot_change_roles(login_as, make_user):
    client, _ = login_as("customer")
    target = make_user(email="target@example.com")
    r = client.patch(f"/api/v1/users/{target.id}/role", {"role": "admin"})
    assert r.status_code == 403
    assert r.data["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_admin_can_change_role(login_as, make_user):
    client, _ = login_as("admin")
    target = make_user(email="target@example.com")
    r = client.patch(f"/api/v1/users/{target.id}/role", {"role": "staff"})
    assert r.status_code == 200
    target.refresh_from_db()
    assert target.role == "staff"


@pytest.mark.django_db
def test_admin_invalid_role_rejected(login_as, make_user):
    client, _ = login_as("admin")
    target = make_user(email="target@example.com")
    r = client.patch(f"/api/v1/users/{target.id}/role", {"role": "boss"})
    assert r.status_code == 400