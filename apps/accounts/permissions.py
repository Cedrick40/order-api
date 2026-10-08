from rest_framework.permissions import BasePermission

from .models import User


class IsStaffRole(BasePermission):
    """Staff or admin."""
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in (User.Role.STAFF, User.Role.ADMIN))


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.ADMIN)