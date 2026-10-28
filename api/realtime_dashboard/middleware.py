"""
Django middleware for Real-time Dashboard Backend.

OWNERSHIP FIX:
  - WebSocketMiddleware previously instantiated WebSocketManager() directly.
    The middleware only INJECTS the manager via request — it doesn't call
    business methods — so the direct reference is acceptable here (it's
    infrastructure plumbing, not business logic). However the comment is
    updated to clarify that callers should prefer WebSocketManagerService
    for any actual business operations.

  - DashboardMiddleware previously queried UserDashboard.objects directly
    with raw filter kwargs. It now uses DashboardService.get_user_dashboards()
    so the query logic lives in exactly one owner (the service layer).

To activate, add to MIDDLEWARE in settings.py:
    'api.realtime_dashboard.middleware.WebSocketMiddleware',
    'api.realtime_dashboard.middleware.DashboardMiddleware',
"""
from typing import Callable
from django.http import HttpRequest, HttpResponse

from .websocket_manager import WebSocketManager


class WebSocketMiddleware:
    """
    Middleware that injects a shared WebSocketManager into each HTTP
    request so downstream views can access connection state.

    Note: views and services that need to perform business operations
    (broadcast, cleanup) should use WebSocketManagerService, not the
    injected manager directly. The injected manager is provided for
    read-only introspection (e.g., checking connection count).

    Usage in a view:
        manager = request.websocket_manager
        count = manager.get_active_connections()  # read-only OK
        # For writes, use WebSocketManagerService instead.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.manager = WebSocketManager()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.websocket_manager = self.manager  # type: ignore[attr-defined]  # injected by WebSocketMiddleware
        return self.get_response(request)


class DashboardMiddleware:
    """
    Middleware that pre-fetches the active dashboards for the authenticated
    user and attaches them to `request.user_dashboards`.

    OWNERSHIP FIX: previously called `UserDashboard.objects.by_user().active()`
    directly, duplicating query logic that belongs to DashboardService.
    Now delegates to DashboardService.get_user_dashboards() — the single
    owner of "fetch active dashboards for user" logic.

    Unauthenticated requests receive an empty list.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, 'user', None)
        if user is not None and getattr(user, 'is_authenticated', False):
            # Lazy import avoids circular imports at module load time.
            from .services.dashboard_service import DashboardService
            request.user_dashboards = (  # type: ignore[attr-defined]  # injected by DashboardMiddleware
                DashboardService().get_user_dashboards(str(user.pk))
            )
        else:
            request.user_dashboards = []  # type: ignore[attr-defined]  # injected by DashboardMiddleware

        return self.get_response(request)
