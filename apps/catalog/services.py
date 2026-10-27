from django.db import transaction

from apps.audit.services import record_audit
from core.exceptions import InsufficientStock

from .models import Inventory, Product


def product_snapshot(product):
    return {
        "sku": product.sku,
        "name": product.name,
        "description": product.description,
        "price": str(product.price),
        "is_active": product.is_active,
    }


@transaction.atomic
def create_product(*, sku, name, price, actor, description="", initial_stock=0):
    product = Product.objects.create(sku=sku, name=name, price=price, description=description)
    Inventory.objects.create(product=product, quantity=initial_stock)
    record_audit(
        actor=actor, action="product.created", entity_type="product", entity_id=product.id,
        after={**product_snapshot(product), "initial_stock": initial_stock},
    )
    return product


@transaction.atomic
def update_product(*, product, changes, actor):
    before = product_snapshot(product)
    for field, value in changes.items():
        setattr(product, field, value)
    product.save()
    record_audit(
        actor=actor, action="product.updated", entity_type="product", entity_id=product.id,
        before=before, after=product_snapshot(product),
    )
    return product


@transaction.atomic
def deactivate_product(*, product, actor):
    before = product_snapshot(product)
    product.is_active = False
    product.save(update_fields=["is_active", "updated_at"])
    record_audit(
        actor=actor, action="product.deactivated", entity_type="product", entity_id=product.id,
        before=before, after=product_snapshot(product),
    )
    return product


@transaction.atomic
def adjust_stock(*, product, change, reason, actor):
    inventory = Inventory.objects.select_for_update().get(product=product)
    old_quantity = inventory.quantity
    new_quantity = old_quantity + change
    if new_quantity < 0:
        raise InsufficientStock(
            message=f"Can't remove {abs(change)} units of {product.name}: only {old_quantity} in stock.",
            details={"product_id": product.id, "available": old_quantity, "requested": abs(change)},
        )
    inventory.quantity = new_quantity
    inventory.save(update_fields=["quantity", "updated_at"])
    record_audit(
        actor=actor, action="stock.adjusted", entity_type="product", entity_id=product.id,
        before={"quantity": old_quantity},
        after={"quantity": new_quantity, "change": change, "reason": reason},
    )
    return inventory