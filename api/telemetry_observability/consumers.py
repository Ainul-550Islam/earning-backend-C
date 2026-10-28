"""
WebSocket consumers for Telemetry Observability.

WIRING — asgi.py:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from .routing import websocket_urlpatterns

    application = ProtocolTypeRouter({
        'http': get_asgi_application(),
        'websocket': AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    })

WebSocket endpoints exposed:
    ws://<host>/ws/telemetry/metrics/      → live metric stream
    ws://<host>/ws/telemetry/logs/         → live log stream
    ws://<host>/ws/telemetry/alerts/       → live alert stream
    ws://<host>/ws/telemetry/health/       → live health stream

Each consumer subscribes to the EventBus and pushes JSON frames to
the connected browser. DRY: no polling — one EventBus subscription per connection.
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from channels.generic.websocket import AsyncWebsocketConsumer
    CHANNELS_AVAILABLE = True
except ImportError:
    CHANNELS_AVAILABLE = False
    # Stub so the file imports cleanly without django-channels installed.
    class AsyncWebsocketConsumer:  # type: ignore[no-redef]
        pass


if CHANNELS_AVAILABLE:
    from .events import event_bus, EventType, Event

    # ------------------------------------------------------------------
    # Base consumer — shared connect/disconnect + send logic
    # ------------------------------------------------------------------

    class BaseTelemetryConsumer(AsyncWebsocketConsumer):
        """
        Abstract base consumer.
        Subclasses declare `subscribed_events: list[EventType]`.
        """

        subscribed_events: list = []
        _group_name: Optional[str] = None

        async def connect(self) -> None:
            if not self.scope.get('user') or not self.scope['user'].is_authenticated:
                await self.close(code=4001)
                return

            await self.accept()
            self._group_name = f'telemetry_{self.__class__.__name__}'

            for event_type in self.subscribed_events:
                event_bus.subscribe(event_type, self._sync_dispatch)

            logger.debug(
                'WS connected: %s (user=%s)',
                self.__class__.__name__,
                self.scope['user'],
            )

        async def disconnect(self, close_code: int) -> None:
            for event_type in self.subscribed_events:
                event_bus.unsubscribe(event_type, self._sync_dispatch)
            logger.debug('WS disconnected: %s (code=%s)', self.__class__.__name__, close_code)

        async def receive(self, text_data: str = '', bytes_data: bytes = b'') -> None:
            """Ignore client messages — this is a server-push only stream."""
            pass

        def _sync_dispatch(self, event: Event) -> None:
            """
            Called synchronously by EventBus. Schedules async_send via the
            event loop that owns this consumer.
            """
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._async_send(event))
            except RuntimeError:
                pass

        async def _async_send(self, event: Event) -> None:
            """Send event as a JSON frame to the WebSocket client."""
            try:
                await self.send(text_data=json.dumps(event.to_dict()))
            except Exception as exc:
                logger.warning('WS send failed (%s): %s', self.__class__.__name__, exc)

    # ------------------------------------------------------------------
    # Domain consumers
    # ------------------------------------------------------------------

    class MetricStreamConsumer(BaseTelemetryConsumer):
        """
        ws://<host>/ws/telemetry/metrics/
        Streams every METRIC_RECORDED event to the client.
        """
        subscribed_events = [EventType.METRIC_RECORDED]

    class LogStreamConsumer(BaseTelemetryConsumer):
        """
        ws://<host>/ws/telemetry/logs/
        Streams every LOG_RECORDED event to the client.
        """
        subscribed_events = [EventType.LOG_RECORDED]

    class AlertStreamConsumer(BaseTelemetryConsumer):
        """
        ws://<host>/ws/telemetry/alerts/
        Streams all alert lifecycle events to the client.
        """
        subscribed_events = [
            EventType.ALERT_TRIGGERED,
            EventType.ALERT_ACKNOWLEDGED,
            EventType.ALERT_RESOLVED,
        ]

    class HealthStreamConsumer(BaseTelemetryConsumer):
        """
        ws://<host>/ws/telemetry/health/
        Streams every HEALTH_STATUS_CHANGED event to the client.
        """
        subscribed_events = [EventType.HEALTH_STATUS_CHANGED]

    class TraceStreamConsumer(BaseTelemetryConsumer):
        """
        ws://<host>/ws/telemetry/traces/
        Streams every TRACE_STARTED and TRACE_FINISHED event.
        """
        subscribed_events = [EventType.TRACE_STARTED, EventType.TRACE_FINISHED]

else:
    # ------------------------------------------------------------------
    # Stub consumers when django-channels is not installed
    # ------------------------------------------------------------------

    class MetricStreamConsumer:  # type: ignore[no-redef]
        pass

    class LogStreamConsumer:  # type: ignore[no-redef]
        pass

    class AlertStreamConsumer:  # type: ignore[no-redef]
        pass

    class HealthStreamConsumer:  # type: ignore[no-redef]
        pass

    class TraceStreamConsumer:  # type: ignore[no-redef]
        pass
