from decimal import Decimal

from django.db import transaction

from apps.accounts.models import Customer
from apps.catalog.models import Inventory, Product
from core.exceptions import (
    DuplicateProduct,
    InsufficientStock,
    InvalidStatusTransition,
    ProductUnavailable,
)

from .models import Order, OrderItem

ALLOWED_TRANSITIONS = {
    Order.Status.PENDING: {Order.Status.CONFIRMED, Order.Status.CANCELLED},
    Order.Status.CONFIRMED: {Order.Status.CANCELLED},
    Order.Status.CANCELLED: set(),
}


def _join(numbers):
    words = [str(n) for n in numbers]
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def _reject_duplicates(items):
    """D2: if the same product appears on more than one line, ask instead of guessing."""
    lines = {}
    for position, item in enumerate(items, start=1):
        lines.setdefault(item["product_id"], []).append(position)

    duplicates = []
    for product_id, positions in lines.items():
        if len(positions) > 1:
            total = sum(i["quantity"] for i in items if i["product_id"] == product_id)
            duplicates.append({"product_id": product_id, "lines": positions, "suggested_quantity": total})
    if not duplicates:
        return

    first = duplicates[0]
    name = (
        Product.objects.filter(pk=first["product_id"], is_active=True).values_list("name", flat=True).first()
        or f"Product {first['product_id']}"
    )
    times = "twice" if len(first["lines"]) == 2 else f"{len(first['lines'])} times"
    raise DuplicateProduct(
        message=(
            f"{name} appears {times} (lines {_join(first['lines'])}). Was this a mistake? "
            f"Combine them into one line with quantity {first['suggested_quantity']} and send again."
        ),
        details={"duplicates": duplicates},
    )


@transaction.atomic
def place_order(*, user, items):
    _reject_duplicates(items)

    # Staff/admin can order too (permission matrix), so make sure a profile exists.
    customer, _ = Customer.objects.get_or_create(user=user, defaults={"full_name": user.email})

    # Lock the stock rows, always in ascending product order, so two orders that share
    # products can never wait on each other forever (deadlock). Other orders for the same
    # products now queue up behind this transaction.
    product_ids = sorted(item["product_id"] for item in items)
    inventories = {
        inventory.product_id: inventory
        for inventory in Inventory.objects.select_for_update(of=("self",))
        .select_related("product")
        .filter(product_id__in=product_ids)
        .order_by("product_id")
    }

    unavailable = [
        pid for pid in product_ids if pid not in inventories or not inventories[pid].product.is_active
    ]
    if unavailable:
        noun, verb = ("Product", "isn't") if len(unavailable) == 1 else ("Products", "aren't")
        raise ProductUnavailable(
            message=f"{noun} {_join(unavailable)} {verb} available, so the order wasn't placed.",
            details={"product_ids": unavailable},
        )

    # Check EVERYTHING before changing anything, and report every shortage at once.
    shortages = []
    for item in items:
        inventory = inventories[item["product_id"]]
        if inventory.quantity < item["quantity"]:
            shortages.append(
                {
                    "product_id": item["product_id"],
                    "name": inventory.product.name,
                    "available": inventory.quantity,
                    "requested": item["quantity"],
                }
            )
    if shortages:
        first = shortages[0]
        message = (
            f"Sorry, we only have {first['available']} of {first['name']} in stock, "
            f"and you asked for {first['requested']}."
        )
        if len(shortages) > 1:
            message += f" {len(shortages) - 1} other item(s) are also short."
        raise InsufficientStock(
            message=message,
            details={
                "product_id": first["product_id"],
                "available": first["available"],
                "requested": first["requested"],
                "shortages": shortages,
            },
        )

    # Everything is fine: deduct stock, snapshot prices, build the order.
    order = Order.objects.create(customer=customer)
    total = Decimal("0.00")
    order_items = []
    for item in items:
        inventory = inventories[item["product_id"]]
        quantity = item["quantity"]
        inventory.quantity -= quantity
        inventory.save(update_fields=["quantity", "updated_at"])
        price = inventory.product.price
        order_items.append(OrderItem(order=order, product=inventory.product, quantity=quantity, unit_price=price))
        total += price * quantity
    OrderItem.objects.bulk_create(order_items)

    order.total_amount = total
    order.save(update_fields=["total_amount", "updated_at"])
    # An audit entry is written here in Slice 4.4 (same transaction).
    return order


def _check_transition(order, target):
    if target not in ALLOWED_TRANSITIONS[order.status]:
        raise InvalidStatusTransition(
            message=f"An order that is {order.status.lower()} can't be changed to {target.lower()}.",
            details={"current_status": order.status, "requested_status": target},
        )


@transaction.atomic
def confirm_order(*, order_id, actor):
    order = Order.objects.select_for_update().get(pk=order_id)
    _check_transition(order, Order.Status.CONFIRMED)
    order.status = Order.Status.CONFIRMED
    order.save(update_fields=["status", "updated_at"])
    return order


@transaction.atomic
def cancel_order(*, order_id, actor):
    order = Order.objects.select_for_update().get(pk=order_id)
    _check_transition(order, Order.Status.CANCELLED)

    items = list(order.items.all())
    inventories = {
        inventory.product_id: inventory
        for inventory in Inventory.objects.select_for_update()
        .filter(product_id__in=[i.product_id for i in items])
        .order_by("product_id")
    }
    for item in items:
        inventory = inventories[item.product_id]
        inventory.quantity += item.quantity
        inventory.save(update_fields=["quantity", "updated_at"])

    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])
    return order