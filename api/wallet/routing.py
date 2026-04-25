# api/wallet/routing.py
"""
WebSocket URL routing for wallet app.
Included in the main asgi.py application.

asgi.py:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from api.wallet.routing import websocket_urlpatterns

    application = ProtocolTypeRouter({
        "http": get_asgi_application(),
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    })
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # User wallet real-time updates
    # Connect: ws://host/ws/wallet/
    re_path(r"^ws/wallet/$", consumers.WalletConsumer.as_asgi()),

    # Admin dashboard live stats
    # Connect: ws://host/ws/admin/dashboard/
    re_path(r"^ws/admin/dashboard/$", consumers.AdminDashboardConsumer.as_asgi()),
]
