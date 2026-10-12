from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsStaffRole

from . import services
from .models import Product
from .serializers import (
    InventorySerializer,
    ProductCreateSerializer,
    ProductSerializer,
    StockAdjustSerializer,
)


class ProductViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch", "head", "options"]  # no PUT, no DELETE (D10)

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsStaffRole()]

    def get_serializer_class(self):
        if self.action == "create":
            return ProductCreateSerializer
        if self.action == "stock":
            return InventorySerializer
        if self.action == "stock_adjust":
            return StockAdjustSerializer
        return ProductSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # used when generating API docs
            return Product.objects.none()
        queryset = Product.objects.select_related("inventory")
        if self.request.user.role not in (User.Role.STAFF, User.Role.ADMIN):
            queryset = queryset.filter(is_active=True)
        search = self.request.query_params.get("search")
        if search and self.action == "list":
            queryset = queryset.filter(Q(name__icontains=search) | Q(sku__icontains=search))
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = ProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        product = services.deactivate_product(product=self.get_object(), actor=request.user)
        return Response(ProductSerializer(product).data)

    @action(detail=True, methods=["get"])
    def stock(self, request, pk=None):
        product = self.get_object()
        return Response(InventorySerializer(product.inventory).data)

    @action(detail=True, methods=["post"], url_path="stock/adjust")
    def stock_adjust(self, request, pk=None):
        product = self.get_object()
        serializer = StockAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inventory = services.adjust_stock(product=product, actor=request.user, **serializer.validated_data)
        return Response(InventorySerializer(inventory).data)