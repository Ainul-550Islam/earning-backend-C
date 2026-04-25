# api/payment_gateways/routing.py
# Django Channels WebSocket URL routing for real-time payment events

from django.urls import re_path
from .consumers import PaymentEventConsumer, GatewayHealthConsumer

# ── WebSocket URL patterns ─────────────────────────────────────────────────────
websocket_urlpatterns = [
    re_path(r'^ws/payment/events/$',  PaymentEventConsumer.as_asgi()),
    re_path(r'^ws/payment/health/$',  GatewayHealthConsumer.as_asgi()),
]


def get_pg_ws_patterns():
    """Return payment_gateways WebSocket patterns for merging into your ASGI router.

    Usage in your project/asgi.py:
        from api.payment_gateways.routing import get_pg_ws_patterns
        from your_project.routing import websocket_urlpatterns

        application = ProtocolTypeRouter({
            "http": get_asgi_application(),
            "websocket": AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns + get_pg_ws_patterns())
            ),
        })
    """
    return websocket_urlpatterns


def get_channel_layers_config():
    """Return channel layers Redis config for settings.py.

    Add to settings.py:
        from api.payment_gateways.routing import get_channel_layers_config
        CHANNEL_LAYERS = get_channel_layers_config()
    """
    import os
    return {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379')],
                'prefix': 'pg_ws',
                'capacity': 1500,
                'expiry': 60,
            },
        }
    }


def broadcast_payment_event(user_id: int, event_type: str, data: dict):
    """
    Broadcast a real-time payment event to a specific user's WebSocket.

    Call this after deposit/withdrawal/conversion events:
        broadcast_payment_event(user.id, 'deposit_completed', {
            'amount': '500.00', 'currency': 'BDT', 'gateway': 'bkash',
            'reference_id': 'DEP-BKAS-...',
        })

    Frontend JavaScript:
        const ws = new WebSocket('wss://yourdomain.com/ws/payment/events/');
        ws.onmessage = (e) => {
            const msg = JSON.parse(e.data);
            if (msg.type === 'deposit_completed') {
                updateBalance(msg.data.amount);
            }
        };
    """
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    group_name    = f'pg_payment_user_{user_id}'

    try:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type':       'payment_event',
                'event_type': event_type,
                'data':       data,
            }
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f'WS broadcast failed for user {user_id}: {e} — '
            f'Is channels_redis installed? pip install channels channels-redis'
        )


def broadcast_gateway_health(gateway: str, status: str, details: dict = None):
    """
    Broadcast gateway health status change to admin WebSocket.

    Used by GatewayHealthService after each health check.
        broadcast_gateway_health('bkash', 'down', {'error': 'Connection timeout'})
    """
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    try:
        async_to_sync(get_channel_layer().group_send)(
            'pg_gateway_health',
            {
                'type': 'gateway_health_update',
                'data': {
                    'gateway': gateway,
                    'status':  status,
                    **(details or {}),
                },
            }
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug(f'Gateway health broadcast failed: {e}')


def broadcast_conversion(publisher_id: int, conversion_data: dict):
    """
    Broadcast new conversion to publisher's WebSocket.
    Shows real-time earnings notification.
    """
    broadcast_payment_event(publisher_id, 'new_conversion', {
        'payout':      conversion_data.get('payout', 0),
        'offer':       conversion_data.get('offer_name', ''),
        'currency':    conversion_data.get('currency', 'USD'),
        'conversion_id': conversion_data.get('conversion_id', ''),
    })
