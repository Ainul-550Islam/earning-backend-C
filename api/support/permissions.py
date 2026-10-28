# api/support/permissions.py
from rest_framework.permissions import BasePermission

class IsSupportAgent(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff or request.user.is_superuser:
            return True
        return hasattr(request.user, 'support_agent') and request.user.support_agent.is_active

class IsSupervisorOrAbove(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        try:
            return request.user.support_agent.role in ['supervisor', 'manager', 'account_manager']
        except Exception:
            return False

class IsTicketOwnerOrAgent(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_superuser:
            return True
        return obj.user == request.user

class IsDisputeOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.user == request.user

class CanManageAgents(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        try:
            return request.user.support_agent.role in ['supervisor', 'manager', 'account_manager']
        except Exception:
            return request.user.is_staff