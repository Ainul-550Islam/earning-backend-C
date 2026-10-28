# api/admin_panel/middleware.py
"""
Admin Activity Tracking Middleware.
Logs all admin API actions automatically.
"""
import json
import logging
import time
from typing import Optional

from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from .utils import get_client_ip, get_user_agent

logger = logging.getLogger(__name__)

# Paths that should NOT be tracked (read-only / noise)
SKIP_TRACKING_PATHS = [
    '/admin/jsi18n/',
    '/admin/autocomplete/',
    '/api/schema/',
    '/api/docs/',
    '/static/',
    '/media/',
    '/favicon.ico',
    '/health/',
    '/api/admin-panel/dashboard/',   # high-frequency refresh
]

# Methods that represent mutations (track these)
MUTATION_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']

# Only track admin paths
TRACKED_PATH_PREFIXES = [
    '/api/admin-panel/',
    '/admin/',
]


class AdminActivityMiddleware(MiddlewareMixin):
    """
    Tracks admin user API activity.
    - Logs to AdminActivity model (if available)
    - Adds X-Admin-Request-ID header to responses
    - Records response time
    """

    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)

    def process_request(self, request):
        """Attach start time and request ID to request."""
        import uuid
        request._admin_request_id = str(uuid.uuid4())[:8].upper()
        request._admin_start_time = time.monotonic()
        return None

    def process_response(self, request, response):
        """After response: log admin activity if applicable."""
        # Add request ID header
        if hasattr(request, '_admin_request_id'):
            response['X-Admin-Request-ID'] = request._admin_request_id

        # Add timing header
        if hasattr(request, '_admin_start_time'):
            elapsed_ms = int((time.monotonic() - request._admin_start_time) * 1000)
            response['X-Response-Time'] = f"{elapsed_ms}ms"

        # Only track authenticated admin users
        if not self._should_track(request):
            return response

        # Async log (non-blocking)
        try:
            self._log_activity(request, response)
        except Exception as e:
            logger.warning(f"AdminActivityMiddleware log error: {e}")

        return response

    def _should_track(self, request) -> bool:
        """Determine if this request should be tracked."""
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return False
        if not (user.is_staff or user.is_superuser):
            return False

        path = request.path
        # Skip noise paths
        for skip in SKIP_TRACKING_PATHS:
            if path.startswith(skip):
                return False

        # Only track admin paths
        is_admin_path = any(path.startswith(prefix) for prefix in TRACKED_PATH_PREFIXES)
        if not is_admin_path:
            return False

        # Only track mutations (POST/PUT/PATCH/DELETE) OR GET on sensitive paths
        if request.method not in MUTATION_METHODS and '/admin/' not in path:
            return False

        return True

    def _log_activity(self, request, response):
        """Log admin activity to the database."""
        try:
            from .models.activity import AdminActivity
        except ImportError:
            return  # models not yet migrated

        user = request.user
        path = request.path
        method = request.method
        ip = get_client_ip(request)
        user_agent = get_user_agent(request)
        status_code = response.status_code

        # Try to extract model context from path
        # e.g. /api/admin-panel/users/123/ → model=users, object_id=123
        model_name, object_id = self._extract_model_context(path)

        # Map HTTP method to action label
        action = self._method_to_action(method, path, status_code)

        # Extract changes from request body (mutations only)
        changes = {}
        if method in MUTATION_METHODS:
            try:
                body = getattr(request, 'data', {})
                if hasattr(body, 'dict'):
                    body = body.dict()
                # Filter out sensitive fields
                SENSITIVE = {'password', 'token', 'secret', 'api_key', 'smtp_password'}
                changes = {k: v for k, v in (body or {}).items() if k not in SENSITIVE}
            except Exception:
                changes = {}

        activity_status = 'success' if status_code < 400 else 'failed'

        try:
            AdminActivity.objects.create(
                actor=user,
                action=action,
                model_name=model_name or '',
                object_id=str(object_id) if object_id else '',
                changes=changes,
                ip=ip,
                user_agent=user_agent,
                status=activity_status,
                path=path[:500],
                method=method,
                response_code=status_code,
            )
        except Exception as e:
            logger.error(f"Failed to save AdminActivity: {e}")

    def _extract_model_context(self, path: str):
        """
        Try to extract model name and object ID from URL path.
        e.g. /api/admin-panel/users/42/ → ('users', 42)
        """
        import re
        patterns = [
            r'/api/admin-panel/([a-z-]+)/(\d+)/',
            r'/api/admin-panel/([a-z-]+)/',
            r'/admin/([a-z_]+)/([a-z_]+)/(\d+)/',
        ]
        for pattern in patterns:
            match = re.search(pattern, path)
            if match:
                groups = match.groups()
                if len(groups) >= 2 and groups[-1].isdigit():
                    return groups[-2], groups[-1]
                elif len(groups) >= 1:
                    return groups[0], None
        return None, None

    def _method_to_action(self, method: str, path: str, status_code: int) -> str:
        """Map HTTP method to a human-readable action string."""
        if status_code >= 400:
            return f'{method.lower()}_failed'
        mapping = {
            'POST': 'create',
            'PUT': 'update',
            'PATCH': 'partial_update',
            'DELETE': 'delete',
            'GET': 'view',
        }
        base = mapping.get(method, method.lower())
        # Add context from path
        if 'bulk' in path:
            return 'bulk_action'
        if 'toggle' in path:
            return 'toggle'
        if 'export' in path:
            return 'export'
        if 'login' in path:
            return 'admin_login'
        if 'logout' in path:
            return 'admin_logout'
        return base


class AdminSessionMiddleware(MiddlewareMixin):
    """
    Tracks admin user sessions.
    - Creates/updates AdminSession on each authenticated admin request.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)

    def process_request(self, request):
        return None

    def process_response(self, request, response):
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return response
        if not (user.is_staff or user.is_superuser):
            return response

        # Don't block response; best-effort update
        try:
            self._update_session(request, user)
        except Exception:
            pass

        return response

    def _update_session(self, request, user):
        try:
            from .models.activity import AdminSession
        except ImportError:
            return

        ip = get_client_ip(request)
        user_agent = get_user_agent(request)

        # Use Django session key as session identifier
        session_key = getattr(request.session, 'session_key', None)
        if not session_key:
            return

        try:
            session, created = AdminSession.objects.get_or_create(
                user=user,
                session_key=session_key,
                defaults={
                    'ip': ip,
                    'user_agent': user_agent,
                    'started_at': timezone.now(),
                    'is_active': True,
                }
            )
            if not created:
                session.last_seen = timezone.now()
                session.is_active = True
                session.save(update_fields=['last_seen', 'is_active'])
        except Exception as e:
            logger.debug(f"AdminSession update error: {e}")


class MaintenanceModeMiddleware(MiddlewareMixin):
    """
    Blocks non-admin users when maintenance mode is active.
    Reads from cache for performance.
    """
    from .constants import MAINTENANCE_BYPASS_PATHS as BYPASS_PATHS

    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)

    def process_request(self, request):
        from django.http import JsonResponse
        from .constants import CACHE_KEY_SYSTEM_SETTINGS, MAINTENANCE_BYPASS_PATHS

        path = request.path
        # Always bypass for admin/static paths
        for bypass in MAINTENANCE_BYPASS_PATHS:
            if path.startswith(bypass):
                return None

        # Check maintenance mode via cache
        try:
            from django.core.cache import cache
            in_maintenance = cache.get('admin_panel:maintenance_mode_active', False)

            if in_maintenance:
                user = getattr(request, 'user', None)
                # Admins can bypass
                if user and user.is_authenticated and (user.is_staff or user.is_superuser):
                    return None

                # Get maintenance message from cache
                message = cache.get(
                    'admin_panel:maintenance_message',
                    "We're currently performing maintenance. Please check back soon."
                )
                return JsonResponse({
                    'error': message,
                    'code': 'MAINTENANCE_MODE',
                    'status': 503,
                }, status=503)
        except Exception:
            pass

        return None