from django.db import transaction

from core.exceptions import InsufficientStock

from .models import Inventory, Product


@transaction.atomic
def create_product(*, sku, name, price, description="", initial_stock=0):
    product = Product.objects.create(sku=sku, name=name, price=price, description=description)
    Inventory.objects.create(product=product, quantity=initial_stock)
    return product


@transaction.atomic
def deactivate_product(*, product, actor):
    product.is_active = False
    product.save(update_fields=["is_active", "updated_at"])
    return product


@transaction.atomic
def adjust_stock(*, product, change, reason, actor):
    # Lock this inventory row so two adjustments can't overwrite each other.
    inventory = Inventory.objects.select_for_update().get(product=product)
    new_quantity = inventory.quantity + change
    if new_quantity < 0:
        raise InsufficientStock(
            message=f"Can't remove {abs(change)} units of {product.name}: only {inventory.quantity} in stock.",
            details={"product_id": product.id, "available": inventory.quantity, "requested": abs(change)},
        )
    inventory.quantity = new_quantity
    inventory.save(update_fields=["quantity", "updated_at"])
    # reason and actor are written to the audit log in Slice 4.4
    return inventory