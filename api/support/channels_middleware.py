# api/support/channels_middleware.py
"""
Django Channels middleware for support WebSocket authentication.
Add to your asgi.py:
    from api.support.channels_middleware import JWTAuthMiddlewareStack
    application = ProtocolTypeRouter({
        "websocket": JWTAuthMiddlewareStack(
            URLRouter(support_websocket_patterns)
        ),
    })
"""
import logging
from urllib.parse import parse_qs

from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)

User = get_user_model()


@database_sync_to_async
def get_user_from_token(token: str):
    """Validate JWT token and return user."""
    try:
        from rest_framework_simplejwt.tokens import AccessToken
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        try:
            validated = AccessToken(token)
            user_id   = validated.get('user_id')
            return User.objects.get(id=user_id)
        except (InvalidToken, TokenError, User.DoesNotExist):
            return AnonymousUser()
    except ImportError:
        pass

    try:
        from rest_framework.authtoken.models import Token
        tok = Token.objects.select_related('user').get(key=token)
        return tok.user
    except Exception:
        pass

    return AnonymousUser()


class TokenAuthMiddleware:
    """
    WebSocket middleware that authenticates via:
    1. JWT Bearer token in query param: ?token=...
    2. DRF Token in query param: ?token=...
    3. Session (Django session authentication)
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode('utf-8')
        params       = parse_qs(query_string)
        token        = None

        if 'token' in params:
            token = params['token'][0]
        elif 'auth_token' in params:
            token = params['auth_token'][0]

        if token:
            scope['user'] = await get_user_from_token(token)
            logger.debug(f"WS auth: user={scope['user']}")
        elif scope.get('user') is None:
            scope['user'] = AnonymousUser()

        return await self.inner(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    """Combined auth middleware: JWT → Session fallback."""
    return TokenAuthMiddleware(AuthMiddlewareStack(inner))