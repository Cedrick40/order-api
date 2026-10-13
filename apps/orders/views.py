from django.http import Http404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsStaffRole
from core.exceptions import OrderNotFound

from . import services
from .models import Order
from .serializers import OrderCreateSerializer, OrderSerializer


class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    def get_permissions(self):
        if self.action == "confirm":
            return [IsStaffRole()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        return OrderCreateSerializer if self.action == "create" else OrderSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        queryset = Order.objects.select_related("customer").prefetch_related("items__product")
        if self.request.user.role not in (User.Role.STAFF, User.Role.ADMIN):
            queryset = queryset.filter(customer__user=self.request.user)  # customers: own orders only
        return queryset

    def get_object(self):
        try:
            return super().get_object()
        except Http404:
            raise OrderNotFound()  # D3: same message whether it doesn't exist or isn't yours

    def create(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = services.place_order(user=request.user, items=serializer.validated_data["items"])
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        order = services.confirm_order(order_id=self.get_object().id, actor=request.user)
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = services.cancel_order(order_id=self.get_object().id, actor=request.user)
        return Response(OrderSerializer(order).data)