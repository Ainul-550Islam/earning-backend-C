"""
urls_and_celery_additions.py
────────────────────────────
Paste these snippets into your main project files.
"""

# ══════════════════════════════════════════════════════════════
# 1.  earning_backend/urls.py  (your root URLconf)
# ══════════════════════════════════════════════════════════════

URLS_SNIPPET = """
from django.urls import path, include

urlpatterns = [
    # ... your existing patterns ...

    # Telemetry Observability — all endpoints under /telemetry/
    path('telemetry/', include('api.telemetry_observability.urls')),
]

# After this, endpoints are at:
#   GET /telemetry/ping/
#   GET /telemetry/readiness/
#   *   /telemetry/api/v1/telemetry/metrics/
#   *   /telemetry/api/v1/telemetry/logs/
#   *   /telemetry/api/v1/telemetry/traces/
#   *   /telemetry/api/v1/telemetry/alerts/
#   *   /telemetry/api/v1/telemetry/health/
#   *   /telemetry/api/v1/telemetry/dashboards/
#   *   /telemetry/api/v1/telemetry/analytics/
"""


# ══════════════════════════════════════════════════════════════
# 2.  celery.py  (your main Celery application file)
# ══════════════════════════════════════════════════════════════

CELERY_SNIPPET = """
# In your existing celery.py, after `app = Celery(...)`:

from api.telemetry_observability.celery_schedule import TELEMETRY_BEAT_SCHEDULE

# Merge telemetry periodic tasks into your existing beat schedule
app.conf.beat_schedule = {
    **getattr(app.conf, 'beat_schedule', {}),
    **TELEMETRY_BEAT_SCHEDULE,
}
"""


# ══════════════════════════════════════════════════════════════
# 3.  asgi.py  (only if using Django Channels WebSocket)
# ══════════════════════════════════════════════════════════════

ASGI_SNIPPET = """
# In your existing asgi.py:

from channels.routing       import ProtocolTypeRouter, URLRouter
from channels.auth          import AuthMiddlewareStack
from api.telemetry_observability.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns   # telemetry real-time streams
            # + your_other_websocket_patterns
        )
    ),
})

# WebSocket endpoints:
#   ws://<host>/ws/telemetry/metrics/
#   ws://<host>/ws/telemetry/logs/
#   ws://<host>/ws/telemetry/traces/
#   ws://<host>/ws/telemetry/alerts/
#   ws://<host>/ws/telemetry/health/
"""
