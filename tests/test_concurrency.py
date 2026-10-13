import threading

import pytest
from django.db import connection

from apps.catalog.models import Inventory
from apps.orders import services
from apps.orders.models import Order
from core.exceptions import InsufficientStock


@pytest.mark.django_db(transaction=True)
def test_twenty_simultaneous_buyers_for_five_units_never_oversell(make_user, make_product):
    product = make_product(stock=5)
    users = [make_user(email=f"buyer{i}@example.com") for i in range(20)]
    outcomes = []
    guard = threading.Lock()
    start_together = threading.Barrier(len(users))

    def buyer(user):
        try:
            start_together.wait()
            try:
                services.place_order(user=user, items=[{"product_id": product.id, "quantity": 1}])
                outcome = "bought"
            except InsufficientStock:
                outcome = "sold out"
            except Exception as exc:  # anything else is a bug we want to see
                outcome = f"error: {exc!r}"
        finally:
            connection.close()
        with guard:
            outcomes.append(outcome)

    threads = [threading.Thread(target=buyer, args=(u,)) for u in users]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert outcomes.count("bought") == 5, outcomes
    assert outcomes.count("sold out") == 15, outcomes
    assert Inventory.objects.get(product=product).quantity == 0
    assert Order.objects.count() == 5