from decimal import Decimal

import pytest

from apps.catalog.models import Inventory, Product
from apps.orders import services
from apps.orders.models import Order, OrderItem

ORDERS = "/api/v1/orders"


def stock_of(product):
    return Inventory.objects.get(product=product).quantity


def place(client, *lines):
    items = [{"product_id": product.id, "quantity": qty} for product, qty in lines]
    return client.post(ORDERS, {"items": items}, format="json")


@pytest.mark.django_db
def test_place_order_calculates_total_and_deducts_stock(login_as, make_product):
    rice = make_product(sku="RICE", name="Rice 5kg", price="15.00", stock=10)
    oil = make_product(sku="OIL", name="Cooking oil 2L", price="15.50", stock=5)
    client, _ = login_as("customer")
    r = place(client, (rice, 2), (oil, 1))
    assert r.status_code == 201
    assert r.data["status"] == "PENDING"
    assert r.data["total_amount"] == "45.50"
    assert stock_of(rice) == 8
    assert stock_of(oil) == 4


@pytest.mark.django_db
def test_server_ignores_prices_and_totals_sent_by_client(login_as, make_product):
    rice = make_product(price="15.00", stock=10)
    client, _ = login_as("customer")
    payload = {"items": [{"product_id": rice.id, "quantity": 1, "unit_price": "0.01"}], "total_amount": "0.01"}
    r = client.post(ORDERS, payload, format="json")
    assert r.status_code == 201
    assert r.data["total_amount"] == "15.00"


@pytest.mark.django_db
def test_price_is_a_snapshot_and_later_changes_do_not_alter_the_order(login_as, make_product):
    rice = make_product(price="15.00", stock=10)
    client, _ = login_as("customer")
    order_id = place(client, (rice, 1)).data["id"]
    Product.objects.filter(pk=rice.pk).update(price=Decimal("99.00"))
    detail = client.get(f"{ORDERS}/{order_id}")
    assert detail.data["items"][0]["unit_price"] == "15.00"
    assert detail.data["total_amount"] == "15.00"


@pytest.mark.django_db
def test_not_enough_stock_rejects_whole_order_and_changes_nothing(login_as, make_product):
    rice = make_product(sku="RICE", name="Rice 5kg", stock=10)
    oil = make_product(sku="OIL", name="Cooking oil 2L", stock=1)
    client, _ = login_as("customer")
    r = place(client, (rice, 2), (oil, 5))
    assert r.status_code == 409
    assert r.data["error"]["code"] == "INSUFFICIENT_STOCK"
    assert "Cooking oil 2L" in r.data["error"]["message"]
    assert stock_of(rice) == 10
    assert stock_of(oil) == 1
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_crash_midway_rolls_back_stock_and_order(login_as, make_product, monkeypatch):
    rice = make_product(stock=10)
    _, user = login_as("customer")

    def crash(*args, **kwargs):
        raise RuntimeError("simulated crash")

    monkeypatch.setattr(OrderItem.objects, "bulk_create", crash)
    with pytest.raises(RuntimeError):
        services.place_order(user=user, items=[{"product_id": rice.id, "quantity": 3}])
    assert stock_of(rice) == 10
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_duplicate_product_lines_ask_if_it_was_a_mistake(login_as, make_product):
    rice = make_product(sku="RICE", name="Rice 5kg", stock=10)
    oil = make_product(sku="OIL", name="Cooking oil 2L", stock=10)
    client, _ = login_as("customer")
    r = place(client, (rice, 1), (oil, 1), (rice, 3))
    assert r.status_code == 400
    error = r.data["error"]
    assert error["code"] == "DUPLICATE_PRODUCT"
    assert "Rice 5kg appears twice (lines 1 and 3)" in error["message"]
    assert "quantity 4" in error["message"]
    assert Order.objects.count() == 0
    assert stock_of(rice) == 10


@pytest.mark.django_db
def test_empty_order_and_bad_quantity_are_rejected(login_as, make_product):
    rice = make_product(stock=10)
    client, _ = login_as("customer")
    empty = client.post(ORDERS, {"items": []}, format="json")
    assert empty.status_code == 400
    assert "at least one item" in empty.data["error"]["message"]
    zero = place(client, (rice, 0))
    assert zero.status_code == 400
    assert "Quantity must be 1 or more" in zero.data["error"]["message"]


@pytest.mark.django_db
def test_unknown_or_inactive_products_cannot_be_ordered(login_as, make_product):
    hidden = make_product(sku="HIDDEN", active=False)
    client, _ = login_as("customer")
    unknown = client.post(ORDERS, {"items": [{"product_id": 9999, "quantity": 1}]}, format="json")
    assert unknown.status_code == 400
    assert unknown.data["error"]["code"] == "PRODUCT_UNAVAILABLE"
    inactive = place(client, (hidden, 1))
    assert inactive.status_code == 400
    assert inactive.data["error"]["code"] == "PRODUCT_UNAVAILABLE"


@pytest.mark.django_db
def test_unauthenticated_cannot_place_order(api, make_product):
    rice = make_product()
    assert place(api, (rice, 1)).status_code == 401


@pytest.mark.django_db
def test_staff_can_place_an_order_too(login_as, make_product):
    rice = make_product(stock=10)
    staff, _ = login_as("staff")
    assert place(staff, (rice, 1)).status_code == 201


@pytest.mark.django_db
def test_customers_see_only_their_own_orders_and_staff_see_all(login_as, make_product):
    rice = make_product(stock=10)
    alice, _ = login_as("customer", email="alice@example.com")
    bob, _ = login_as("customer", email="bob@example.com")
    place(alice, (rice, 1))
    place(bob, (rice, 1))
    assert alice.get(ORDERS).data["count"] == 1
    staff, _ = login_as("staff")
    assert staff.get(ORDERS).data["count"] == 2


@pytest.mark.django_db
def test_other_customers_order_gives_plain_not_found_message(login_as, make_product):
    rice = make_product(stock=10)
    alice, _ = login_as("customer", email="alice@example.com")
    bob, _ = login_as("customer", email="bob@example.com")
    order_id = place(alice, (rice, 1)).data["id"]
    r = bob.get(f"{ORDERS}/{order_id}")
    assert r.status_code == 404
    assert r.data["error"]["message"] == "We couldn't find that order on your account."


@pytest.mark.django_db
def test_cancel_restores_stock_and_cannot_be_repeated(login_as, make_product):
    rice = make_product(stock=10)
    client, _ = login_as("customer")
    order_id = place(client, (rice, 4)).data["id"]
    assert stock_of(rice) == 6
    first = client.post(f"{ORDERS}/{order_id}/cancel")
    assert first.status_code == 200
    assert first.data["status"] == "CANCELLED"
    assert stock_of(rice) == 10
    second = client.post(f"{ORDERS}/{order_id}/cancel")
    assert second.status_code == 409
    assert second.data["error"]["code"] == "INVALID_STATUS_TRANSITION"
    assert stock_of(rice) == 10


@pytest.mark.django_db
def test_customer_cannot_cancel_someone_elses_order_but_staff_can(login_as, make_product):
    rice = make_product(stock=10)
    alice, _ = login_as("customer", email="alice@example.com")
    bob, _ = login_as("customer", email="bob@example.com")
    order_id = place(alice, (rice, 2)).data["id"]
    assert bob.post(f"{ORDERS}/{order_id}/cancel").status_code == 404
    assert stock_of(rice) == 8
    staff, _ = login_as("staff")
    assert staff.post(f"{ORDERS}/{order_id}/cancel").status_code == 200
    assert stock_of(rice) == 10


@pytest.mark.django_db
def test_only_staff_can_confirm_and_status_rules_are_enforced(login_as, make_product):
    rice = make_product(stock=10)
    customer, _ = login_as("customer")
    order_id = place(customer, (rice, 1)).data["id"]

    denied = customer.post(f"{ORDERS}/{order_id}/confirm")
    assert denied.status_code == 403

    staff, _ = login_as("staff")
    ok = staff.post(f"{ORDERS}/{order_id}/confirm")
    assert ok.status_code == 200
    assert ok.data["status"] == "CONFIRMED"

    assert customer.post(f"{ORDERS}/{order_id}/cancel").status_code == 200
    again = staff.post(f"{ORDERS}/{order_id}/confirm")
    assert again.status_code == 409
    assert again.data["error"]["code"] == "INVALID_STATUS_TRANSITION"