"""
WebSocket Authentication Utility.
Supports three authentication strategies:
1. Session authentication (cookie-based, same-origin browser clients).
2. JWT authentication (query param ?token=<jwt>, for React frontend).
3. DRF Token authentication (legacy, ?token=<drf_token>).
"""
from __future__ import annotations
import logging
from typing import Any
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from ..exceptions import WebSocketAuthError

logger = logging.getLogger(__name__)


async def authenticate_websocket_user(scope: dict) -> Any:
    if not isinstance(scope, dict):
        raise WebSocketAuthError("Invalid scope: expected a dict.")

    # 1. Session-based auth (populated by AuthMiddlewareStack)
    user = scope.get("user")
    if user is not None and not isinstance(user, AnonymousUser) and user.pk is not None:
        if not getattr(user, "is_active", True):
            raise WebSocketAuthError(f"User pk={user.pk} is inactive.")
        logger.debug("WS auth: session user pk=%s authenticated.", user.pk)
        return user

    # 2. Token from query string (?token=<value>)
    token = _extract_token_from_scope(scope)
    if token:
        # Try JWT first (adminAccessToken is a JWT)
        user = await _authenticate_by_jwt(token)
        if user is not None:
            logger.debug("WS auth: JWT user pk=%s authenticated.", user.pk)
            return user

        # Fallback: DRF Token
        user = await _authenticate_by_drf_token(token)
        if user is not None:
            logger.debug("WS auth: DRF token user pk=%s authenticated.", user.pk)
            return user

    raise WebSocketAuthError(
        "WebSocket authentication failed: no valid session or token provided."
    )


def _extract_token_from_scope(scope: dict) -> str:
    query_string = scope.get("query_string", b"")
    if isinstance(query_string, bytes):
        query_string = query_string.decode("utf-8", errors="replace")
    params: dict[str, str] = {}
    for part in query_string.split("&"):
        if "=" in part:
            k, _, v = part.partition("=")
            params[k.strip().lower()] = v.strip()
    token = params.get("token", "")
    if token:
        return token
    auth = params.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


@database_sync_to_async
def _authenticate_by_jwt(token: str) -> Any:
    """Authenticate using JWT (SimpleJWT) — used by React frontend."""
    if not token:
        return None
    try:
        from rest_framework_simplejwt.tokens import AccessToken
        from rest_framework_simplejwt.exceptions import TokenError
        from django.contrib.auth import get_user_model

        User = get_user_model()
        access_token = AccessToken(token)
        user_id = access_token.get("user_id")
        if not user_id:
            return None
        user = User.objects.get(pk=user_id)
        if not user.is_active:
            logger.warning("WS JWT auth: inactive user pk=%s.", user.pk)
            return None
        return user
    except Exception as e:
        logger.debug("WS JWT auth failed: %s", e)
        return None


@database_sync_to_async
def _authenticate_by_drf_token(token: str) -> Any:
    """Authenticate using DRF Token (legacy fallback)."""
    if not token:
        return None
    try:
        from rest_framework.authtoken.models import Token
        tok_obj = Token.objects.select_related("user").get(key=token)
        if not tok_obj.user.is_active:
            return None
        return tok_obj.user
    except Exception:
        return None