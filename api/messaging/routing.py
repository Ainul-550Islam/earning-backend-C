"""
Messaging WebSocket URL Routing — All 4 consumer routes.

SECURITY — Origin validation (Cross-Site WebSocket Hijacking):
CSRF middleware never runs for the WebSocket protocol upgrade — it only
protects the regular Django/DRF request-response cycle. But
`utils.websocket_auth.authenticate_websocket_user()`'s first strategy
is session-cookie auth (`scope["user"]`, populated by AuthMiddlewareStack
straight from the browser's cookie jar). Put those two facts together
and, with no Origin check, *any* website can open a
`wss://.../ws/messaging/...` connection from a logged-in victim's
browser and it will carry their session cookie automatically — the
WebSocket equivalent of a CSRF hole. Plain `websocket_urlpatterns`
below does not close this; `application` (or `messaging_origin_validator`)
does.

Simple integration (recommended) — mount `application` directly, it
already includes AuthMiddlewareStack + Origin validation:

    # asgi.py
    from api.messaging.routing import application as messaging_ws_application
    application = ProtocolTypeRouter({
        "http": get_asgi_application(),
        "websocket": messaging_ws_application,
    })

Custom ASGI middleware (e.g. project-wide tenant-scoping middleware
that also needs to wrap the WS scope) — build your own stack and wrap
it with `messaging_origin_validator` instead of using `application`:

    from channels.auth import AuthMiddlewareStack
    from channels.routing import URLRouter
    from api.messaging.routing import websocket_urlpatterns, messaging_origin_validator

    application = ProtocolTypeRouter({
        "http": get_asgi_application(),
        "websocket": messaging_origin_validator(
            YourTenantScopingMiddleware(
                AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
            )
        ),
    })

Legacy/no-op integration (pre-Part-19 behaviour, NOT recommended — kept
only because `websocket_urlpatterns` may already be imported elsewhere):

    from api.messaging.routing import websocket_urlpatterns
    application = ProtocolTypeRouter({
        "http": get_asgi_application(),
        "websocket": AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    })
"""
from __future__ import annotations

from django.conf import settings
from django.urls import re_path
from channels.auth import AuthMiddlewareStack
from channels.routing import URLRouter
from channels.security.websocket import AllowedHostsOriginValidator, OriginValidator

from .consumers import ChatConsumer, SupportConsumer, PresenceConsumer, CallConsumer

websocket_urlpatterns = [
    # Chat room — peer-to-peer and group chats
    re_path(r"^ws/messaging/chat/(?P<chat_id>[0-9a-f\-]+)/$",
            ChatConsumer.as_asgi(), name="ws-chat"),

    # Support thread — affiliate ↔ agent
    re_path(r"^ws/messaging/support/(?P<thread_id>[0-9a-f\-]+)/$",
            SupportConsumer.as_asgi(), name="ws-support"),

    # Presence — online/away/offline tracking (one per user)
    re_path(r"^ws/messaging/presence/$",
            PresenceConsumer.as_asgi(), name="ws-presence"),

    # WebRTC call room — signaling only (offer/answer/ICE)
    re_path(r"^ws/messaging/call/(?P<room_id>[a-f0-9]+)/$",
            CallConsumer.as_asgi(), name="ws-call"),
]


def messaging_origin_validator(inner_application):
    """
    Wrap an ASGI application with WebSocket Origin validation.

    Resolves the allowed-origins list in this order, first non-empty
    match wins:

      1. settings.MESSAGING_WS_ALLOWED_ORIGINS — explicit opt-in list
         for this module specifically. Needed when the client that
         opens the WebSocket lives on a domain that is in neither of
         the two settings below (e.g. a decoupled frontend on its own
         domain, talking to this backend on a different one). Set to
         ["*"] to explicitly allow every origin — matches Channels'
         own OriginValidator convention; only appropriate if this
         endpoint has no cookie-based auth path, which is not the
         case here, so treat that value as a deliberate, documented
         exception rather than a default.
      2. settings.CORS_ALLOWED_ORIGINS — if django-cors-headers (or
         anything else defining this same setting name) is already
         configured for the REST API's browser clients, that list is,
         by definition, exactly the set of frontend origins this
         project trusts — reused as-is instead of asking the project
         to declare the same domains twice.
      3. settings.ALLOWED_HOSTS — Channels' own AllowedHostsOriginValidator
         fallback. Every real Django deployment must already set this
         correctly just for plain HTTP requests to resolve (Django
         rejects unrecognized Host headers), so it's a safe,
         zero-extra-config floor. It under-protects a decoupled
         frontend hosted on its own domain (that domain won't be in
         ALLOWED_HOSTS), but it always blocks arbitrary third-party
         sites, which is the actual attack this defends against.

    An empty/unset list at whichever tier is used is "deny all" (fail
    safe), never "allow all" — same rule this module already applies
    to trusting proxy headers (see middleware._get_client_ip): absence
    of configuration is never treated as blanket trust.
    """
    explicit_origins = getattr(settings, "MESSAGING_WS_ALLOWED_ORIGINS", None)
    if explicit_origins:
        return OriginValidator(inner_application, list(explicit_origins))

    cors_origins = getattr(settings, "CORS_ALLOWED_ORIGINS", None)
    if cors_origins:
        return OriginValidator(inner_application, list(cors_origins))

    return AllowedHostsOriginValidator(inner_application)


# Ready-to-mount default: AuthMiddlewareStack (session/JWT/token user
# resolution happens inside consumers via websocket_auth, but scope["user"]
# for the session-cookie path is populated here) wrapped in Origin
# validation. See module docstring for the custom-middleware alternative.
application = messaging_origin_validator(
    AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
)