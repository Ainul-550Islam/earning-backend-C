"""
Domain-specific DRF permissions for Telemetry Observability.

WIRING — use in viewsets:
    from .permissions import TelemetryBasePermission, CanManageAlerts

    class AlertViewSet(viewsets.ModelViewSet):
        def get_permissions(self):
            if self.action in ('acknowledge', 'resolve'):
                return [CanManageAlerts()]
            return [TelemetryBasePermission()]

DRY: never hardcode IsAuthenticated in individual views.
     Import the domain-specific class that expresses intent clearly.
"""
from rest_framework import permissions


# ---------------------------------------------------------------------------
# Base: authenticated + active
# ---------------------------------------------------------------------------

class TelemetryBasePermission(permissions.IsAuthenticated):
    """
    Default permission for all telemetry endpoints.
    Requires the user to be authenticated and have is_active=True.
    Replaces bare IsAuthenticated everywhere in this app.
    """

    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and getattr(request.user, 'is_active', False)
        )


# ---------------------------------------------------------------------------
# Read/Write split helpers
# ---------------------------------------------------------------------------

class ReadOnlyOrAuthenticated(TelemetryBasePermission):
    """
    GET / HEAD / OPTIONS are allowed for any authenticated user.
    POST / PUT / PATCH / DELETE require the telemetry:write permission.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.has_perm('telemetry_observability.telemetry_write')


class IsAdminOrReadOnly(TelemetryBasePermission):
    """
    Staff / superuser: full access.
    Others: read-only (SAFE_METHODS).
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.is_staff or request.user.is_superuser:
            return True
        return request.method in permissions.SAFE_METHODS


class IsServiceAccount(TelemetryBasePermission):
    """
    Allow service accounts (e.g. metric-ingestion agents) to write.
    A service account has user.is_service_account = True (custom field)
    or belongs to a group named 'service_accounts'.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if getattr(request.user, 'is_service_account', False):
            return True
        return request.user.groups.filter(name='service_accounts').exists()


class HasAPIKey(permissions.BasePermission):
    """
    Allow requests that carry the X-API-Key header.
    Does NOT require session authentication — suitable for machine-to-machine.
    Combine with TelemetryBasePermission using OR: [HasAPIKey | TelemetryBasePermission]
    """

    def has_permission(self, request, view):
        api_key = request.META.get('HTTP_X_API_KEY') or request.headers.get('X-API-Key')
        return bool(api_key)


# ---------------------------------------------------------------------------
# Domain permissions (model-level Django perms)
# ---------------------------------------------------------------------------

class CanViewMetrics(TelemetryBasePermission):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.user.has_perm('telemetry_observability.view_metricevent')
        )


class CanCreateMetrics(TelemetryBasePermission):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.user.has_perm('telemetry_observability.add_metricevent')
        )


class CanViewLogs(TelemetryBasePermission):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.user.has_perm('telemetry_observability.view_logentry')
        )


class CanCreateLogs(TelemetryBasePermission):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.user.has_perm('telemetry_observability.add_logentry')
        )


class CanViewTraces(TelemetryBasePermission):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.user.has_perm('telemetry_observability.view_tracespan')
        )


class CanViewAlerts(TelemetryBasePermission):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.user.has_perm('telemetry_observability.view_alert')
        )


class CanManageAlerts(TelemetryBasePermission):
    """
    Read: view_alert perm.
    Write (acknowledge / resolve / create): change_alert perm.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_perm('telemetry_observability.view_alert')
        return request.user.has_perm('telemetry_observability.change_alert')


class CanViewHealth(TelemetryBasePermission):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.user.has_perm('telemetry_observability.view_healthstatus')
        )


class CanManageDashboards(TelemetryBasePermission):
    """
    Read: view_dashboardwidget perm.
    Write: change_dashboardwidget perm.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_perm('telemetry_observability.view_dashboardwidget')
        return request.user.has_perm('telemetry_observability.change_dashboardwidget')
