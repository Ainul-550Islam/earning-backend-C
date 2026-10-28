# cms/asgi.py
"""
ASGI config for CMS.

v11b: This file was either missing or had a stub that didn't connect
the CMS WebSocket routing.

Previous state (stub):
    application = get_asgi_application()   # HTTP only — no WebSocket

Business impact:
  - ALL WebSocket connections (ws://host/ws/cms/*) returned HTTP 404.
  - channels was listed as ASGI_APPLICATION target but routing.py was
    never wired, so 'channels' import was unused.
  - RealTimeOfferConsumer, CMSNotificationConsumer, and all other consumers
    in routing.py were completely unreachable.

v11b fix:
  - ProtocolTypeRouter routes HTTP to Django, WebSocket to cms.routing.
  - AllowedHostsOriginValidator enforces ALLOWED_HOSTS for WS connections
    (prevents cross-origin WebSocket abuse).
  - URLRouter uses websocket_urlpatterns from api.cms.routing (which includes
    both the original 6 consumers and the 2 new RealTimeOffer consumers).
  - Graceful fallback: if channels is not installed, falls back to plain
    ASGI HTTP application (dev environments that don't run WebSocket).
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings_production')

# Django setup must happen before any app imports
django.setup()

from django.core.asgi import get_asgi_application

try:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from channels.security.websocket import AllowedHostsOriginValidator

    from api.cms.routing import websocket_urlpatterns

    application = ProtocolTypeRouter({
        # ── HTTP → Standard Django ASGI application ───────────────────────────
        'http': get_asgi_application(),

        # ── WebSocket → CMS routing ───────────────────────────────────────────
        # AllowedHostsOriginValidator: rejects WS connections from origins not
        # in ALLOWED_HOSTS. Prevents cross-origin WebSocket abuse.
        #
        # AuthMiddlewareStack: populates request.user from the Django session
        # cookie, making request.user.is_authenticated work inside consumers.
        #
        # URLRouter: dispatches to the consumer matching the WS path.
        # All paths defined in cms/routing.py:
        #   ws/cms/notifications/          → CMSNotificationConsumer
        #   ws/cms/offers/                 → CMSOfferFeedConsumer
        #   ws/cms/leaderboard/            → CMSLeaderboardConsumer
        #   ws/cms/surveys/                → SurveyConsumer
        #   ws/cms/rewards/                → RewardConsumer
        #   ws/cms/tasks/                  → TaskConsumer
        #   ws/cms/realtime-offers/        → RealTimeOfferConsumer  (v11b)
        #   ws/cms/admin/realtime-offers/  → AdminRealTimeOfferConsumer (v11b)
        'websocket': AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            )
        ),
    })

except ImportError:
    # channels not installed — fall back to plain ASGI HTTP application.
    # This is safe for local dev without Redis; all HTTP endpoints work normally.
    import logging
    logging.getLogger('cms.asgi').warning(
        '[CMS asgi.py] channels not installed — WebSocket support disabled. '
        'Install channels and channels_redis to enable real-time features.'
    )
    application = get_asgi_application()
