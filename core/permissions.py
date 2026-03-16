# from earning_backend.api.admin_panel import permissions
from api.admin_panel import permissions
from rest_framework.permissions import BasePermission
from rest_framework import permissions


class IsOwner(BasePermission):
    """
    Custom permission to only allow owners of an object to access it.
    """
    
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class IsAdminOrReadOnly(BasePermission):
    """
    Custom permission to allow read-only access to everyone, but write access only to admins.
    """
    
    def has_permission(self, request, view):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        return request.user and request.user.is_staff
    
   

class IsSuperUser(permissions.BasePermission):
    """
    Allows access only to superusers.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)


class IsFraudAnalyst(permissions.BasePermission):
    """
    Allows access to fraud analysts.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and
            (request.user.is_staff or 
             hasattr(request.user, 'role') and 
             request.user.role in ['fraud_analyst', 'admin', 'superuser'])
        )


class IsReadOnlyOrAnalyst(permissions.BasePermission):
    """
    Allows read-only access to everyone, but write access only to fraud analysts.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        return bool(
            request.user and 
            request.user.is_authenticated and
            (request.user.is_staff or 
             hasattr(request.user, 'role') and 
             request.user.role in ['fraud_analyst', 'admin', 'superuser'])
        )


class IsUserOrAnalyst(permissions.BasePermission):
    """
    Allows users to access their own data, and analysts to access all data.
    """
    def has_object_permission(self, request, view, obj):
        # Check if user is fraud analyst or superuser
        if request.user and request.user.is_authenticated:
            if request.user.is_superuser or request.user.is_staff:
                return True
            
            # Check for fraud analyst role
            if hasattr(request.user, 'role') and request.user.role in ['fraud_analyst', 'admin']:
                return True
            
            # Check if user owns the object
            if hasattr(obj, 'user'):
                return obj.user == request.user
            elif hasattr(obj, 'owner'):
                return obj.owner == request.user
        
        return False