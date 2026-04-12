# routing.py — Django Channels WebSocket URL routing
"""
ASGI routing for real-time translation collaboration.

Add to your main routing.py:
  from api.localization.routing import websocket_urlpatterns as loc_ws_patterns
  application = ProtocolTypeRouter({
      'http': get_asgi_application(),
      'websocket': AuthMiddlewareStack(URLRouter(loc_ws_patterns)),
  })

WebSocket URLs:
  ws://host/ws/localization/translations/{language}/  — Translation collaboration
"""
try:
    from django.urls import re_path
    from .consumers.translation_consumer import TranslationCollabConsumer

    websocket_urlpatterns = [
        re_path(
            r'^ws/localization/translations/(?P<language>[a-z]{2,5})/$',
            TranslationCollabConsumer.as_asgi(),
        ),
    ]
except ImportError:
    websocket_urlpatterns = []
