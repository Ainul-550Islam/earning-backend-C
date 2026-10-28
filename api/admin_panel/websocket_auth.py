# api/admin_panel/websocket_auth.py
"""
WebSocket JWT Authentication Middleware for Django Channels.
Authenticates admin users connecting to /ws/admin/* via JWT token.

Add to asgi.py:
    from api.admin_panel.websocket_auth import JWTAuthMiddlewareStack
    application = ProtocolTypeRouter({
        "websocket": JWTAuthMiddlewareStack(URLRouter(admin_websocket_urlpatterns)),
    })
"""
from __future__ import annotations
import logging
from urllib.parse import parse_qs
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)
User = get_user_model()


@database_sync_to_async
def get_user_from_token(token: str):
    """Validate JWT token and return User or AnonymousUser."""
    if not token:
        return AnonymousUser()
    try:
        # Try djangorestframework-simplejwt
        from rest_framework_simplejwt.tokens import AccessToken
        from rest_framework_simplejwt.exceptions import TokenError
        try:
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            user = User.objects.get(pk=user_id, is_active=True, is_staff=True)
            return user
        except (TokenError, User.DoesNotExist, KeyError):
            return AnonymousUser()
    except ImportError:
        pass

    # Fallback: try Knox token
    try:
        from knox.models import AuthToken
        token_obj = AuthToken.objects.select_related('user').get(
            token_key=token[:8]
        )
        if token_obj.user.is_staff:
            return token_obj.user
        return AnonymousUser()
    except Exception:
        pass

    # Fallback: Django session key check
    try:
        from django.contrib.sessions.models import Session
        session = Session.objects.get(session_key=token)
        uid = session.get_decoded().get('_auth_user_id')
        if uid:
            user = User.objects.get(pk=uid, is_active=True, is_staff=True)
            return user
    except Exception:
        pass

    return AnonymousUser()


@database_sync_to_async
def check_admin_ip_whitelist(ip: str) -> bool:
    """Check if IP is allowed to connect to admin WebSocket."""
    try:
        from api.admin_panel.ip_whitelist import AdminIPWhitelist
        return AdminIPWhitelist.is_allowed(ip)
    except Exception:
        return True  # Default: allow all if whitelist not configured


class JWTAuthMiddleware(BaseMiddleware):
    """
    JWT authentication middleware for admin WebSocket connections.
    Extracts token from:
      1. Query param: ?token=<jwt>
      2. Cookie: admin_access_token
      3. Subprotocol header
    """

    async def __call__(self, scope, receive, send):
        # Only handle WebSocket
        if scope['type'] not in ('websocket', 'http'):
            return await super().__call__(scope, receive, send)

        # Extract token
        token = self._extract_token(scope)
        scope['user'] = await get_user_from_token(token)

        # IP check
        ip = self._get_ip(scope)
        scope['client_ip'] = ip

        if not scope['user'].is_authenticated:
            logger.warning(f"[WS Auth] Unauthenticated WS connection from {ip}")
            # Close with auth error code
            await send({'type': 'websocket.close', 'code': 4001})
            return

        if not scope['user'].is_staff:
            logger.warning(f"[WS Auth] Non-staff WS connection: {scope['user'].username}")
            await send({'type': 'websocket.close', 'code': 4003})
            return

        logger.debug(f"[WS Auth] Authenticated: {scope['user'].username} from {ip}")
        return await super().__call__(scope, receive, send)

    def _extract_token(self, scope) -> str:
        """Extract JWT token from query string, cookie, or headers."""
        # 1. Query param ?token=xxx
        query_string = scope.get('query_string', b'').decode()
        params = parse_qs(query_string)
        if 'token' in params:
            return params['token'][0]

        # 2. Cookie
        headers = dict(scope.get('headers', []))
        cookie_header = headers.get(b'cookie', b'').decode()
        for cookie in cookie_header.split(';'):
            cookie = cookie.strip()
            if cookie.startswith('admin_access_token='):
                return cookie.split('=', 1)[1]

        # 3. Authorization header
        auth_header = headers.get(b'authorization', b'').decode()
        if auth_header.startswith('Bearer '):
            return auth_header[7:]

        # 4. Sec-WebSocket-Protocol (token in subprotocol)
        protocol = headers.get(b'sec-websocket-protocol', b'').decode()
        if protocol.startswith('token,'):
            return protocol.split(',', 1)[1].strip()

        return ''

    def _get_ip(self, scope) -> str:
        """Extract real client IP from scope."""
        headers = dict(scope.get('headers', []))
        x_forwarded = headers.get(b'x-forwarded-for', b'').decode()
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        client = scope.get('client')
        return client[0] if client else '0.0.0.0'


def JWTAuthMiddlewareStack(inner):
    """Convenience wrapper — use in asgi.py."""
    return JWTAuthMiddleware(inner)