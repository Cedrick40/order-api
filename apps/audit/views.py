import datetime

from rest_framework import generics, serializers

from apps.accounts.permissions import IsAdminRole

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogListView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AuditLog.objects.none()
        queryset = AuditLog.objects.all()
        params = self.request.query_params
        if params.get("entity_type"):
            queryset = queryset.filter(entity_type=params["entity_type"])
        if params.get("action"):
            queryset = queryset.filter(action=params["action"])
        if params.get("actor"):
            queryset = queryset.filter(actor_email__iexact=params["actor"])
        if params.get("entity_id"):
            try:
                entity_id = int(params["entity_id"])
                if not 0 <= entity_id <= 2_147_483_647:
                    raise ValueError
            except ValueError:
                raise serializers.ValidationError({"entity_id": "Must be a whole number."})
            queryset = queryset.filter(entity_id=entity_id)
        if params.get("date"):
            try:
                day = datetime.date.fromisoformat(params["date"])
            except ValueError:
                raise serializers.ValidationError({"date": "Use the format YYYY-MM-DD, for example 2026-10-12."})
            queryset = queryset.filter(created_at__date=day)
        return queryset