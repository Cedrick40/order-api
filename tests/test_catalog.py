import pytest
from django.db import IntegrityError, transaction

from apps.catalog.models import Inventory, Product

PRODUCTS = "/api/v1/products"


def skus(response):
    return {p["sku"] for p in response.data["results"]}


@pytest.mark.django_db
def test_unauthenticated_cannot_list_products(api):
    assert api.get(PRODUCTS).status_code == 401


@pytest.mark.django_db
def test_customer_sees_only_active_products_and_no_exact_stock(login_as, make_product):
    make_product(sku="A-1")
    make_product(sku="B-2", active=False)
    client, _ = login_as("customer")
    r = client.get(PRODUCTS)
    assert r.status_code == 200
    assert skus(r) == {"A-1"}
    assert "quantity" not in r.data["results"][0]
    assert r.data["results"][0]["in_stock"] is True


@pytest.mark.django_db
def test_staff_sees_inactive_products_too(login_as, make_product):
    make_product(sku="A-1")
    make_product(sku="B-2", active=False)
    client, _ = login_as("staff")
    assert skus(client.get(PRODUCTS)) == {"A-1", "B-2"}


@pytest.mark.django_db
def test_customer_gets_404_for_inactive_product(login_as, make_product):
    product = make_product(active=False)
    client, _ = login_as("customer")
    r = client.get(f"{PRODUCTS}/{product.id}")
    assert r.status_code == 404
    assert r.data["error"]["code"] == "NOT_FOUND"


@pytest.mark.django_db
def test_search_filters_by_name_or_sku(login_as, make_product):
    make_product(sku="RICE-1", name="Rice")
    make_product(sku="OIL-1", name="Cooking oil")
    client, _ = login_as("customer")
    assert skus(client.get(PRODUCTS, {"search": "rice"})) == {"RICE-1"}


@pytest.mark.django_db
def test_customer_cannot_create_product(login_as):
    client, _ = login_as("customer")
    r = client.post(PRODUCTS, {"sku": "X-1", "name": "X", "price": "5.00"}, format="json")
    assert r.status_code == 403
    assert r.data["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_staff_creates_product_with_initial_stock(login_as):
    client, _ = login_as("staff")
    r = client.post(
        PRODUCTS,
        {"sku": " oil-2l ", "name": "Cooking oil 2L", "price": "15.50", "initial_stock": 8},
        format="json",
    )
    assert r.status_code == 201
    assert r.data["sku"] == "OIL-2L"
    assert Inventory.objects.get(product__sku="OIL-2L").quantity == 8


@pytest.mark.django_db
def test_duplicate_sku_gives_friendly_error(login_as, make_product):
    make_product(sku="DUP-1")
    client, _ = login_as("staff")
    r = client.post(PRODUCTS, {"sku": "dup-1", "name": "Again", "price": "5.00"}, format="json")
    assert r.status_code == 400
    assert "already exists" in r.data["error"]["message"]


@pytest.mark.django_db
@pytest.mark.parametrize("bad_price", ["0", "-5"])
def test_price_must_be_greater_than_zero(login_as, bad_price):
    client, _ = login_as("staff")
    r = client.post(PRODUCTS, {"sku": "P-1", "name": "P", "price": bad_price}, format="json")
    assert r.status_code == 400
    assert "greater than 0" in r.data["error"]["message"]


@pytest.mark.django_db
def test_deactivate_hides_product_from_customers(login_as, make_product):
    product = make_product()
    staff, _ = login_as("staff")
    assert staff.post(f"{PRODUCTS}/{product.id}/deactivate").status_code == 200
    customer, _ = login_as("customer")
    assert skus(customer.get(PRODUCTS)) == set()


@pytest.mark.django_db
def test_products_cannot_be_deleted(login_as, make_product):
    product = make_product()
    staff, _ = login_as("staff")
    r = staff.delete(f"{PRODUCTS}/{product.id}")
    assert r.status_code == 405
    assert Product.objects.filter(pk=product.id).exists()


@pytest.mark.django_db
def test_customer_cannot_view_stock_but_staff_can(login_as, make_product):
    product = make_product(stock=7)
    customer, _ = login_as("customer")
    assert customer.get(f"{PRODUCTS}/{product.id}/stock").status_code == 403
    staff, _ = login_as("staff")
    r = staff.get(f"{PRODUCTS}/{product.id}/stock")
    assert r.status_code == 200
    assert r.data["quantity"] == 7


@pytest.mark.django_db
def test_staff_can_add_stock(login_as, make_product):
    product = make_product(stock=10)
    staff, _ = login_as("staff")
    r = staff.post(f"{PRODUCTS}/{product.id}/stock/adjust", {"change": 5, "reason": "delivery"}, format="json")
    assert r.status_code == 200
    assert Inventory.objects.get(product=product).quantity == 15


@pytest.mark.django_db
def test_removing_too_much_stock_is_rejected_and_nothing_changes(login_as, make_product):
    product = make_product(stock=10)
    staff, _ = login_as("staff")
    r = staff.post(f"{PRODUCTS}/{product.id}/stock/adjust", {"change": -50, "reason": "damaged"}, format="json")
    assert r.status_code == 409
    assert r.data["error"]["code"] == "INSUFFICIENT_STOCK"
    assert r.data["error"]["details"]["available"] == 10
    assert Inventory.objects.get(product=product).quantity == 10


@pytest.mark.django_db
def test_stock_adjustment_needs_nonzero_change_and_reason(login_as, make_product):
    product = make_product()
    staff, _ = login_as("staff")
    url = f"{PRODUCTS}/{product.id}/stock/adjust"
    assert staff.post(url, {"change": 0, "reason": "x"}, format="json").status_code == 400
    assert staff.post(url, {"change": 3}, format="json").status_code == 400


@pytest.mark.django_db
def test_database_itself_refuses_negative_stock(make_product):
    product = make_product(stock=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        Inventory.objects.filter(product=product).update(quantity=-1)


@pytest.mark.django_db
def test_database_itself_refuses_zero_price(make_product):
    product = make_product()
    with pytest.raises(IntegrityError), transaction.atomic():
        Product.objects.filter(pk=product.pk).update(price=0)