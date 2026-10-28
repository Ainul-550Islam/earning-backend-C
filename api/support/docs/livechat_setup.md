# Live Chat Setup (Django Channels)

## Install
```bash
pip install channels channels-redis daphne
```

## settings.py
```python
INSTALLED_APPS += ["channels"]
ASGI_APPLICATION = "yourproject.asgi.application"
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [("127.0.0.1", 6379)]}
    }
}
```

## asgi.py
```python
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from api.support.consumers.routing import support_websocket_patterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(URLRouter(support_websocket_patterns)),
})
```

## WebSocket URLs
- `ws/support/chat/<session_id>/`  — User↔Agent chat
- `ws/support/agent/`              — Agent dashboard alerts
- `ws/support/notifications/`      — User ticket updates
- `ws/support/typing/<session_id>/`— Typing indicators
