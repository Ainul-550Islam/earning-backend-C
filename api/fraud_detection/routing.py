# =============================================================================
# fraud_detection/routing.py  — WEBSOCKET ROUTING (DRY, fixed)
#
# consumers.py WAS FLOATING — defined three WebSocket consumers but routing.py
# was importing from endpoint.py (HTTP paths) instead of consumers.py.
#
# Fixed: websocket_urlpatterns connects all three consumers.
# Add to project asgi.py:
#   from api.fraud_detection.routing import websocket_urlpatterns
# =============================================================================
from django.urls import re_path

from .consumers import (
    FraudMonitoringConsumer,
    FraudNotificationConsumer,
    FraudAnalyticsConsumer,
)

# ── WebSocket URL patterns ────────────────────────────────────────────────────
websocket_urlpatterns = [
    # Real-time fraud monitoring dashboard feed
    re_path(r"^ws/fraud/monitoring/$",         FraudMonitoringConsumer.as_asgi()),

    # Per-user fraud alert notifications
    re_path(r"^ws/fraud/notifications/(?P<user_id>\d+)/$", FraudNotificationConsumer.as_asgi()),

    # Live analytics streaming (risk scores, detection rates)
    re_path(r"^ws/fraud/analytics/$",          FraudAnalyticsConsumer.as_asgi()),
]
