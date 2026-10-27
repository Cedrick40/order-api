from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .permissions import IsAdminRole
from .serializers import MeSerializer, RegisterSerializer, RoleSerializer
from . import services

User = get_user_model()


class RegisterView(generics.GenericAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(MeSerializer(user).data, status=status.HTTP_201_CREATED)


class MeView(generics.RetrieveAPIView):
    serializer_class = MeSerializer

    def get_object(self):
        return self.request.user


class UserRoleView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAdminRole]
    http_method_names = ["patch"]
    
    def perform_update(self, serializer):
        if "role" in serializer.validated_data:
            services.change_role(
                user=serializer.instance, new_role=serializer.validated_data["role"], actor=self.request.user
            )