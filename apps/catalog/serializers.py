from decimal import Decimal

from rest_framework import serializers

from . import services
from .models import Inventory, Product


class ProductSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(max_length=40)
    price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        error_messages={"min_value": "Price must be greater than 0."},
    )
    in_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "sku", "name", "description", "price", "is_active", "in_stock"]
        read_only_fields = ["id", "is_active"]

    def get_in_stock(self, obj) -> bool:
        return obj.inventory.quantity > 0

    def validate_sku(self, value):
        value = value.strip().upper()
        existing = Product.objects.filter(sku=value)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("A product with this SKU already exists.")
        return value


class ProductCreateSerializer(ProductSerializer):
    initial_stock = serializers.IntegerField(min_value=0, default=0, write_only=True)

    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields + ["initial_stock"]

    def create(self, validated_data):
        return services.create_product(actor=self.context["request"].user,**validated_data)


class InventorySerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Inventory
        fields = ["product_id", "quantity", "updated_at"]


class StockAdjustSerializer(serializers.Serializer):
    change = serializers.IntegerField()
    reason = serializers.CharField(max_length=255)

    def validate_change(self, value):
        if value == 0:
            raise serializers.ValidationError(
                "Change must not be zero. Use a positive number to add stock or a negative number to remove it."
            )
        return value