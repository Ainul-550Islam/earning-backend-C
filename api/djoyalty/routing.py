# api/djoyalty/routing.py
"""
Djoyalty ASGI WebSocket Routing।
Add to your project's routing.py:
    from djoyalty.routing import djoyalty_websocket_urlpatterns
    application = ProtocolTypeRouter({
        'websocket': AuthMiddlewareStack(
            URLRouter(djoyalty_websocket_urlpatterns)
        ),
    })
"""
try:
    from django.urls import re_path
    from .consumers import LoyaltyConsumer

    djoyalty_websocket_urlpatterns = [
        re_path(
            r'ws/loyalty/(?P<customer_code>[A-Z0-9]+)/$',
            LoyaltyConsumer.as_asgi(),
            name='loyalty_ws',
        ),
    ]
except Exception:
    djoyalty_websocket_urlpatterns = []
