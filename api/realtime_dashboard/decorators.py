"""
Decorators for Real-time Dashboard Backend viewset actions.

DRY FIX (v1.2.0): The "missing required query param → 400" pattern was
repeated in 4 viewset action methods:
    - DashboardLayoutViewSet.by_type       (?layout_type=)
    - WidgetConfigurationViewSet.by_widget  (?widget_id=)
    - UserDashboardViewSet.by_user          (?user_id=)
    - WebSocketConnectionViewSet.by_user    (?user_id=)

All four had identical code:
    param = request.query_params.get('param_name')
    if not param:
        return Response({'success': False, 'error': 'param_name parameter is required'}, status=400)

Replaced with a single @require_query_param('param_name') decorator.

SECURITY FIX (v1.1.0): require_dashboard now calls
self.check_object_permissions() to prevent IDOR on activate/deactivate.

DRY FIX (v1.5.0 — 360-degree audit, second pass): require_widget and
require_dashboard each manually built their own 404 Response dict
(`{'success': False, 'error': f'... not found'}`), independently of
exceptions.py's custom_exception_handler — which already centralizes
exactly that shape for every other error path in the app, via
WidgetNotFoundError/DashboardNotFoundError. Those two classes were
defined, correctly mapped to HTTP 404 in _APP_EXCEPTION_STATUS_MAP, and
never once raised anywhere — found while checking, after the CRUD-layer
audit, whether the same "defined but not connected" pattern existed
outside the service layer too. It did, just for exception classes
instead of methods. Now these decorators raise them instead of
hand-building a third parallel implementation of the same response shape.
"""
from functools import wraps
from typing import Callable, Union, cast

from .exceptions import WidgetNotFoundError, DashboardNotFoundError


def require_query_param(*param_names: str):
    """
    DRY decorator that validates required query parameters before the
    action runs.

    Usage:
        @require_query_param('widget_id')
        @action(detail=False, methods=['get'])
        def by_widget(self, request):
            widget_id = request.query_params['widget_id']  # guaranteed present

        @require_query_param('user_id', 'date')           # multiple params
        @action(detail=False, methods=['get'])
        def by_user_date(self, request): ...

    If any listed parameter is absent or empty, returns 400 with a
    descriptive error message listing which parameter is missing.
    The action body only runs when ALL parameters are present.
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(self, request, *args, **kwargs):
            from rest_framework import status
            from rest_framework.response import Response
            for name in param_names:
                if not request.query_params.get(name):
                    return Response(
                        {
                            'success': False,
                            'error': f"'{name}' query parameter is required.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            return f(self, request, *args, **kwargs)
        return wrapper
    return decorator


def require_widget(f: Callable) -> Callable:
    """
    Pre-fetch DashboardWidget by pk URL kwarg and attach to request.widget.

    Raises WidgetNotFoundError (→ 404 via custom_exception_handler) when
    the widget does not exist, so the action body can access
    request.widget unconditionally.
    """
    @wraps(f)
    def wrapper(self, request, *args, **kwargs):
        from .models.dashboard_widget import DashboardWidget
        # MYPY FIX (v9): kwargs.get('pk') types as Any | None; DRF only
        # ever attaches these decorators to detail-route actions, where
        # the URL pattern guarantees 'pk' is present in kwargs — the cast
        # documents that routing invariant instead of adding a None-check
        # that can't actually be hit through this decorator's call path.
        pk = cast(Union[str, int], kwargs.get('pk'))
        try:
            request.widget = DashboardWidget.objects.get(pk=pk)
        except DashboardWidget.DoesNotExist:
            raise WidgetNotFoundError(f'Widget {pk} not found')
        return f(self, request, *args, **kwargs)
    return wrapper


def require_dashboard(f: Callable) -> Callable:
    """
    Pre-fetch UserDashboard by pk URL kwarg, enforce object-level
    permissions, and attach to request.dashboard.

    SECURITY: calls self.check_object_permissions(request, dashboard)
    before the action runs, preventing IDOR on activate/deactivate/etc.
    Raises DashboardNotFoundError (→ 404 via custom_exception_handler)
    when the dashboard does not exist.
    """
    @wraps(f)
    def wrapper(self, request, *args, **kwargs):
        from .models.user_dashboard import UserDashboard
        pk = cast(Union[str, int], kwargs.get('pk'))  # see require_widget above
        try:
            request.dashboard = UserDashboard.objects.get(pk=pk)
        except UserDashboard.DoesNotExist:
            raise DashboardNotFoundError(f'Dashboard {pk} not found')
        # Enforce IsDashboardOwner before handing off to the action.
        self.check_object_permissions(request, request.dashboard)
        return f(self, request, *args, **kwargs)
    return wrapper
