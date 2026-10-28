# api/admin_panel/routing.py
"""
WebSocket URL routing for admin_panel.
Add to your project's asgi.py or main routing.py:

    from api.admin_panel.routing import admin_websocket_urlpatterns
    application = ProtocolTypeRouter({
        "websocket": URLRouter(admin_websocket_urlpatterns),
    })
"""
from django.urls import re_path
from .consumers import (
    AdminDashboardConsumer,
    AdminFraudAlertConsumer,
    AdminSystemHealthConsumer,
)

admin_websocket_urlpatterns = [
    # Real-time dashboard — KPIs, activity, alerts
    re_path(r'^ws/admin/dashboard/$', AdminDashboardConsumer.as_asgi()),

    # Live fraud alerts feed
    re_path(r'^ws/admin/fraud/alerts/$', AdminFraudAlertConsumer.as_asgi()),

    # System health monitor
    re_path(r'^ws/admin/health/$', AdminSystemHealthConsumer.as_asgi()),
]