from django.db import models
from django.db.models import Q


class Product(models.Model):
    sku = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(price__gt=0), name="product_price_gt_0"),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"


class Inventory(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="inventory")
    quantity = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=0), name="inventory_quantity_gte_0"),
        ]

    def __str__(self):
        return f"{self.product.sku}: {self.quantity}"