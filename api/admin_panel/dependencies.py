# api/admin_panel/dependencies.py
"""
DRF Dependencies & Dependency Injection for admin_panel.
FastAPI-style deps via DRF get_object_or_404 + service injection.
"""
from typing import Optional
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.request import Request
from django.contrib.auth import get_user_model

User = get_user_model()


def get_admin_user(request: Request):
    """Return current user if staff, else raise PermissionDenied."""
    if not request.user.is_authenticated:
        raise PermissionDenied("Authentication required.")
    if not request.user.is_staff:
        raise PermissionDenied("Admin access required.")
    return request.user


def get_superadmin_user(request: Request):
    """Return current user if superuser."""
    user = get_admin_user(request)
    if not user.is_superuser:
        raise PermissionDenied("Superadmin access required.")
    return user


def get_admin_role(request: Request) -> str:
    """Return admin role string for current user."""
    try:
        return request.user.admin_profile.role
    except Exception:
        if request.user.is_superuser:
            return 'superadmin'
        if request.user.is_staff:
            return 'admin'
        return 'viewer'


def get_system_config_service():
    """Inject SystemConfigService."""
    from api.admin_panel.services.SystemConfigService import SystemConfigService
    return SystemConfigService


def get_feature_flag_service():
    """Inject FeatureFlagService."""
    from api.admin_panel.services.FeatureFlagService import FeatureFlagService
    return FeatureFlagService


def get_maintenance_service():
    """Inject MaintenanceModeService."""
    from api.admin_panel.services.MaintenanceModeService import MaintenanceModeService
    return MaintenanceModeService


def get_integration_handler():
    """Inject IntegrationHandler."""
    from api.admin_panel.INTEGRATION_SYSTEM.integ_handler import IntegrationHandler
    return IntegrationHandler


def get_integration_registry():
    """Inject IntegrationRegistry singleton."""
    from api.admin_panel.INTEGRATION_SYSTEM.integ_registry import registry
    return registry


def get_event_bus():
    """Inject EventBus singleton."""
    from api.admin_panel.INTEGRATION_SYSTEM.event_bus import event_bus
    return event_bus


def get_admin_bridge():
    """Inject AdminBridge."""
    from api.admin_panel.INTEGRATION_SYSTEM.bridge import AdminBridge
    return AdminBridge


def get_user_or_404(user_id) -> User:
    """Get User by pk or raise NotFound."""
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise NotFound(f"User {user_id} not found.")


def get_pagination_params(request: Request) -> dict:
    """Extract pagination params from request."""
    try:
        page = max(1, int(request.query_params.get('page', 1)))
        page_size = min(200, max(1, int(request.query_params.get('page_size', 25))))
    except (ValueError, TypeError):
        page, page_size = 1, 25
    return {'page': page, 'page_size': page_size, 'offset': (page - 1) * page_size}


def get_date_range_params(request: Request) -> dict:
    """Extract date range from request query params."""
    from django.utils import timezone
    from datetime import timedelta
    end_str   = request.query_params.get('end_date')
    start_str = request.query_params.get('start_date')
    days      = int(request.query_params.get('days', 7))

    if end_str:
        from datetime import datetime
        end = datetime.strptime(end_str, '%Y-%m-%d').date()
    else:
        end = timezone.now().date()

    if start_str:
        from datetime import datetime
        start = datetime.strptime(start_str, '%Y-%m-%d').date()
    else:
        start = end - timedelta(days=days)

    return {'start': start, 'end': end, 'days': days}


def validate_required(data: dict, *fields) -> None:
    """Raise ValidationError if any required field is missing."""
    missing = [f for f in fields if not data.get(f)]
    if missing:
        raise ValidationError({f: 'This field is required.' for f in missing})