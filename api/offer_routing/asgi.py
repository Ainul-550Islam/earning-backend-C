"""
ASGI configuration for the offer_routing application.

This module exports:
  - websocket_urlpatterns  →  used by the project-level asgi.py
  - get_asgi_application() →  convenience builder for standalone use

Required Django settings:
    INSTALLED_APPS  += ['channels']
    ASGI_APPLICATION = '<project>.asgi.application'
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [('127.0.0.1', 6379)]},
        }
    }

WebSocket endpoints exposed:
    ws/offer-routing/dashboard/    — per-tenant real-time route stats
    ws/offer-routing/caps/         — real-time cap usage / limit alerts
    ws/offer-routing/decisions/    — live routing decision stream
    ws/offer-routing/performance/  — live performance KPIs
"""

import logging
import os

from django.core.asgi import get_asgi_application

logger = logging.getLogger(__name__)

# ── WebSocket URL patterns ─────────────────────────────────────────────────────
# Always import websocket_urlpatterns — used by the host project's asgi.py
from .websocket_routing import websocket_urlpatterns  # noqa: E402

__all__ = ['websocket_urlpatterns', 'get_offer_routing_asgi_app']


def get_offer_routing_asgi_app():
    """
    Build and return a fully-wired ASGI application for offer_routing.

    If Django Channels + a channel layer are configured this returns a
    ProtocolTypeRouter that handles both HTTP and WebSocket traffic.
    If Channels is not installed it falls back to a plain HTTP-only
    ASGI application so the REST API continues to work unaffected.

    Usage in project asgi.py:
        from offer_routing.asgi import get_offer_routing_asgi_app
        application = get_offer_routing_asgi_app()
    """
    django_asgi_app = get_asgi_application()

    try:
        from channels.routing import ProtocolTypeRouter, URLRouter
        from channels.auth import AuthMiddlewareStack
        from channels.security.websocket import AllowedHostsOriginValidator
        from django.conf import settings

        if not getattr(settings, 'CHANNEL_LAYERS', None):
            logger.warning(
                "offer_routing ASGI: CHANNEL_LAYERS not configured. "
                "Falling back to HTTP-only mode — WebSocket endpoints unavailable."
            )
            return django_asgi_app

        application = ProtocolTypeRouter({
            # ── HTTP traffic ──────────────────────────────────────────────────
            "http": django_asgi_app,

            # ── WebSocket traffic ─────────────────────────────────────────────
            # AllowedHostsOriginValidator rejects connections from unknown origins
            # AuthMiddlewareStack populates scope['user'] from the session cookie
            "websocket": AllowedHostsOriginValidator(
                AuthMiddlewareStack(
                    URLRouter(websocket_urlpatterns)
                )
            ),
        })
        logger.info(
            "offer_routing ASGI: ProtocolTypeRouter ready — "
            "%d WebSocket endpoints registered",
            len(websocket_urlpatterns),
        )
        return application

    except ImportError:
        logger.info(
            "offer_routing ASGI: django-channels not installed. "
            "Running in HTTP-only mode."
        )
        return django_asgi_app

    except Exception as exc:
        logger.error(
            "offer_routing ASGI: failed to build ProtocolTypeRouter (%s). "
            "Falling back to HTTP-only mode.", exc,
            exc_info=True,
        )
        return django_asgi_app
