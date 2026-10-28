"""
Custom permissions for Alerts API
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework import permissions


class IsOwnerOrReadOnly(BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    Read access is allowed to any authenticated user.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests
        if request.method in SAFE_METHODS:
            return True
            
        # Write permissions are only allowed to the owner of the object
        return obj.created_by == request.user


class IsAdminOrReadOnly(BasePermission):
    """
    Custom permission to only allow admin users to edit objects.
    Read access is allowed to any authenticated user.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any request
        if request.method in SAFE_METHODS:
            return True
            
        # Write permissions are only allowed to admin users
        return request.user and request.user.is_staff


class IsAlertManager(BasePermission):
    """
    Custom permission to only allow users with alert management privileges.
    Users must be staff members or have specific alert management permissions.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('alerts.manage_alerts') or
             request.user.has_perm('alerts.manage_alert_rules'))
        )


class CanViewSensitiveData(BasePermission):
    """
    Custom permission to only allow users to view sensitive alert data.
    This includes detailed error logs, system metrics, and incident details.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('alerts.view_sensitive_data') or
             request.user.has_perm('alerts.view_incident_details'))
        )


class CanManageNotifications(BasePermission):
    """
    Custom permission to only allow users to manage notification settings.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('alerts.manage_notifications') or
             request.user.has_perm('alerts.configure_channels'))
        )


class CanExportData(BasePermission):
    """
    Custom permission to only allow users to export alert data and reports.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('alerts.export_data') or
             request.user.has_perm('alerts.generate_reports'))
        )


class CanManageSystemHealth(BasePermission):
    """
    Custom permission to only allow users to manage system health checks.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('alerts.manage_system_health') or
             request.user.has_perm('alerts.configure_health_checks'))
        )


class CanResolveAlerts(BasePermission):
    """
    Custom permission to only allow users to resolve alerts.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('alerts.resolve_alerts') or
             request.user.has_perm('alerts.manage_incidents'))
        )


class CanAcknowledgeAlerts(BasePermission):
    """
    Custom permission to only allow users to acknowledge alerts.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('alerts.acknowledge_alerts') or
             request.user.has_perm('alerts.respond_to_alerts'))
        )


class CanConfigureThresholds(BasePermission):
    """
    Custom permission to only allow users to configure alert thresholds.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('alerts.configure_thresholds') or
             request.user.has_perm('alerts.manage_threshold_rules'))
        )


class CanViewAuditLogs(BasePermission):
    """
    Custom permission to only allow users to view audit logs.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('alerts.view_audit_logs') or
             request.user.has_perm('alerts.monitor_activity'))
        )


class IsServiceAccount(BasePermission):
    """
    Custom permission to only allow service accounts (non-human users).
    Useful for internal API calls and automated processes.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            hasattr(request.user, 'is_service_account') and
            request.user.is_service_account
        )


class HasAlertScope(BasePermission):
    """
    Custom permission to check if user has required alert scopes.
    This works with token-based authentication and OAuth2 scopes.
    """
    
    def __init__(self, scopes):
        self.scopes = scopes if isinstance(scopes, list) else [scopes]
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        # Check if user has the required scopes
        user_scopes = getattr(request.user, 'scopes', [])
        return all(scope in user_scopes for scope in self.scopes)


class IsInAlertTeam(BasePermission):
    """
    Custom permission to only allow users who are members of alert teams.
    Staff/superusers bypass the group-membership check, consistent with
    every other permission class in this module (IsAlertManager,
    CanResolveAlerts, CanAcknowledgeAlerts, etc.) -- without this, staff
    could resolve/acknowledge incidents but couldn't even list or view them.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_staff:
            return True

        # Check if user is in any alert team
        from django.contrib.auth.models import Group
        alert_teams = Group.objects.filter(name__in=[
            'Alert Managers', 'Incident Responders', 'On-Call Engineers',
            'SRE Team', 'DevOps Team', 'Monitoring Team'
        ])
        
        return request.user.groups.filter(id__in=alert_teams).exists()


class CanAccessDuringMaintenance(BasePermission):
    """
    Custom permission to allow access during system maintenance windows.
    Only specific users should be able to access the system during maintenance.
    """
    
    def has_permission(self, request, view):
        # Check if system is in maintenance mode
        from django.conf import settings
        if not getattr(settings, 'SYSTEM_MAINTENANCE_MODE', False):
            return True
            
        # During maintenance, only allow specific users
        return (
            request.user and 
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('alerts.access_during_maintenance') or
             getattr(request.user, 'is_maintenance_crew', False))
        )


class RateLimitExceeded(BasePermission):
    """
    Custom permission to implement rate limiting.
    This should be used with Django REST Framework's throttling classes.
    """
    
    def has_permission(self, request, view):
        # This permission is designed to be used with throttling
        # The actual rate limiting should be handled by DRF throttling classes
        return True


def get_custom_permissions():
    """
    Utility function to return all custom permission classes.
    Useful for testing and documentation purposes.
    """
    return [
        IsOwnerOrReadOnly,
        IsAdminOrReadOnly,
        IsAlertManager,
        CanViewSensitiveData,
        CanManageNotifications,
        CanExportData,
        CanManageSystemHealth,
        CanResolveAlerts,
        CanAcknowledgeAlerts,
        CanConfigureThresholds,
        CanViewAuditLogs,
        IsServiceAccount,
        HasAlertScope,
        IsInAlertTeam,
        CanAccessDuringMaintenance,
        RateLimitExceeded,
    ]