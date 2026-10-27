import logging

import pytest

from apps.audit.models import AuditLog
from apps.audit.services import record_audit
from apps.catalog import services as catalog_services
from apps.catalog.models import Inventory
from tests.conftest import PASSWORD

PRODUCTS = "/api/v1/products"
ORDERS = "/api/v1/orders"
AUDIT = "/api/v1/audit-logs"


@pytest.mark.django_db
def test_every_response_carries_a_request_id(api):
    r = api.get("/api/v1/me")
    assert len(r["X-Request-ID"]) == 32


@pytest.mark.django_db
def test_safe_client_request_id_is_kept_and_unsafe_one_is_replaced(api):
    ok = api.get("/api/v1/me", HTTP_X_REQUEST_ID="trace-123")
    assert ok["X-Request-ID"] == "trace-123"
    bad = api.get("/api/v1/me", HTTP_X_REQUEST_ID="bad id with spaces")
    assert bad["X-Request-ID"] != "bad id with spaces"
    assert len(bad["X-Request-ID"]) == 32


@pytest.mark.django_db
def test_each_request_is_logged_with_method_path_and_status(api, caplog):
    caplog.set_level(logging.INFO, logger="api.request")
    api.get("/api/v1/me")
    assert any("GET /api/v1/me 401" in record.getMessage() for record in caplog.records)


@pytest.mark.django_db
def test_product_creation_is_audited_with_actor_and_request_id(login_as):
    staff, _ = login_as("staff")
    r = staff.post(PRODUCTS, {"sku": "A-1", "name": "A", "price": "10.00", "initial_stock": 4}, format="json")
    entry = AuditLog.objects.get(action="product.created")
    assert entry.actor_email == "staff@example.com"
    assert entry.entity_type == "product" and entry.entity_id == r.data["id"]
    assert entry.after["sku"] == "A-1" and entry.after["initial_stock"] == 4
    assert entry.request_id and entry.request_id == r["X-Request-ID"]


@pytest.mark.django_db
def test_product_update_records_before_and_after(login_as, make_product):
    product = make_product(price="15.00")
    staff, _ = login_as("staff")
    staff.patch(f"{PRODUCTS}/{product.id}", {"price": "18.00"}, format="json")
    entry = AuditLog.objects.get(action="product.updated")
    assert entry.before["price"] == "15.00"
    assert entry.after["price"] == "18.00"


@pytest.mark.django_db
def test_stock_adjustment_records_quantities_and_reason(login_as, make_product):
    product = make_product(stock=10)
    staff, _ = login_as("staff")
    staff.post(f"{PRODUCTS}/{product.id}/stock/adjust", {"change": -3, "reason": "damaged"}, format="json")
    entry = AuditLog.objects.get(action="stock.adjusted")
    assert entry.before == {"quantity": 10}
    assert entry.after == {"quantity": 7, "change": -3, "reason": "damaged"}


@pytest.mark.django_db
def test_rejected_requests_create_no_audit_entries(login_as, make_product):
    product = make_product(stock=1)
    customer, _ = login_as("customer")
    r = customer.post(ORDERS, {"items": [{"product_id": product.id, "quantity": 5}]}, format="json")
    assert r.status_code == 409
    assert AuditLog.objects.count() == 0


@pytest.mark.django_db
def test_if_the_audit_write_fails_the_change_is_rolled_back(login_as, make_product, monkeypatch):
    product = make_product(stock=10)
    _, staff = login_as("staff")

    def broken_audit(**kwargs):
        raise RuntimeError("audit store is down")

    monkeypatch.setattr("apps.catalog.services.record_audit", broken_audit)
    with pytest.raises(RuntimeError):
        catalog_services.adjust_stock(product=product, change=5, reason="delivery", actor=staff)
    assert Inventory.objects.get(product=product).quantity == 10


@pytest.mark.django_db
def test_audit_entries_cannot_be_modified_or_deleted():
    entry = record_audit(actor=None, action="test.created", entity_type="test", entity_id=1)
    entry.action = "changed"
    with pytest.raises(RuntimeError):
        entry.save()
    with pytest.raises(RuntimeError):
        entry.delete()


@pytest.mark.django_db
def test_every_write_action_produces_exactly_one_audit_entry(api, login_as):
    registered = api.post(
        "/api/v1/auth/register",
        {"email": "new@example.com", "password": PASSWORD, "full_name": "New"},
        format="json",
    )
    assert registered.status_code == 201
    admin, _ = login_as("admin")
    staff, _ = login_as("staff")
    customer, _ = login_as("customer")

    created = staff.post(PRODUCTS, {"sku": "A-1", "name": "A", "price": "10.00", "initial_stock": 10}, format="json")
    product_id = created.data["id"]
    staff.patch(f"{PRODUCTS}/{product_id}", {"price": "12.00"}, format="json")
    staff.post(f"{PRODUCTS}/{product_id}/stock/adjust", {"change": 5, "reason": "delivery"}, format="json")
    placed = customer.post(ORDERS, {"items": [{"product_id": product_id, "quantity": 2}]}, format="json")
    assert placed.status_code == 201
    order_id = placed.data["id"]
    assert staff.post(f"{ORDERS}/{order_id}/confirm").status_code == 200
    assert customer.post(f"{ORDERS}/{order_id}/cancel").status_code == 200
    assert admin.patch(f"/api/v1/users/{registered.data['id']}/role", {"role": "staff"}, format="json").status_code == 200
    assert staff.post(f"{PRODUCTS}/{product_id}/deactivate").status_code == 200

    actions = list(AuditLog.objects.order_by("id").values_list("action", flat=True))
    assert actions == [
        "user.registered", "product.created", "product.updated", "stock.adjusted",
        "order.placed", "order.confirmed", "order.cancelled", "user.role_changed", "product.deactivated",
    ]


@pytest.mark.django_db
def test_only_admin_can_read_the_audit_log(login_as):
    record_audit(actor=None, action="test.created", entity_type="test", entity_id=1)
    customer, _ = login_as("customer")
    staff, _ = login_as("staff")
    admin, _ = login_as("admin")
    assert customer.get(AUDIT).status_code == 403
    assert staff.get(AUDIT).status_code == 403
    r = admin.get(AUDIT)
    assert r.status_code == 200
    assert r.data["count"] == 1


@pytest.mark.django_db
def test_audit_filters_work_and_bad_filters_get_friendly_errors(login_as):
    admin, _ = login_as("admin")
    record_audit(actor=None, action="order.placed", entity_type="order", entity_id=1)
    record_audit(actor=None, action="product.created", entity_type="product", entity_id=2)
    r = admin.get(AUDIT, {"entity_type": "order"})
    assert [e["entity_type"] for e in r.data["results"]] == ["order"]
    assert admin.get(AUDIT, {"entity_id": "abc"}).status_code == 400
    assert admin.get(AUDIT, {"date": "yesterday"}).status_code == 400


@pytest.mark.django_db
def test_unexpected_errors_return_a_safe_500_with_a_request_id(login_as, monkeypatch):
    def explode(**kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr("apps.catalog.services.create_product", explode)
    staff, _ = login_as("staff")
    r = staff.post(PRODUCTS, {"sku": "X-1", "name": "X", "price": "5.00"}, format="json")
    assert r.status_code == 500
    assert r.data["error"]["code"] == "SERVER_ERROR"
    assert "secret internal detail" not in str(r.data)
    assert r.data["error"]["details"]["request_id"] == r["X-Request-ID"]