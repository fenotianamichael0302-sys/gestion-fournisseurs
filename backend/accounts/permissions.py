from rest_framework.permissions import BasePermission

from accounts.models import User


class IsAdministrator(BasePermission):
    def has_permission(self, request, view):
        return bool(
            view is not None
            and request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.ADMINISTRATEUR
        )


class CanManageProcurement(BasePermission):
    def has_permission(self, request, view):
        if view is None or not request.user or not request.user.is_authenticated:
            return False
        if request.user.role not in (User.Role.ADMINISTRATEUR, User.Role.ACHETEUR):
            return False
        return request.method != "DELETE" or request.user.role == User.Role.ADMINISTRATEUR

class CanManageSuppliers(CanManageProcurement):
    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return super().has_permission(request, view)
        return IsAdministrator().has_permission(request, view)
