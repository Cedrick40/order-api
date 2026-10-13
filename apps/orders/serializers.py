from rest_framework import serializers

from .models import Order, OrderItem


class OrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(
        min_value=1, error_messages={"min_value": "Quantity must be 1 or more."}
    )


class OrderCreateSerializer(serializers.Serializer):
    items = OrderItemInputSerializer(
        many=True, allow_empty=False, error_messages={"empty": "An order needs at least one item."}
    )


class OrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(source="product.name", read_only=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ["product_id", "name", "quantity", "unit_price", "line_total"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)

    class Meta:
        model = Order
        fields = ["id", "status", "total_amount", "customer_name", "created_at", "items"]