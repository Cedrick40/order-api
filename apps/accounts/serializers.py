from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .models import Customer
from apps.audit.services import record_audit

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    full_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    @transaction.atomic
    def create(self, validated_data):
        full_name = validated_data.pop("full_name")
        phone = validated_data.pop("phone", "")
        user = User.objects.create_user(**validated_data)  # email + password
        Customer.objects.create(user=user, full_name=full_name, phone=phone)
        record_audit(
            actor=user, action="user.registered", entity_type="user", entity_id=user.id,
            after={"email": user.email, "role": user.role},
        )
        return user


class MeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="customer.full_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "role", "full_name"]


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "role"]
        read_only_fields = ["id", "email"]