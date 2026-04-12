# api/promotions/tracking/event_logger.py
# Event Bus — impression, click, conversion, fraud events
# Redis stream → Celery consumer → DB / Analytics
import logging, time, uuid
from dataclasses import dataclass, field
from django.core.cache import cache
logger = logging.getLogger('tracking.events')
STREAM_KEY = 'track:events:stream'

@dataclass
class PlatformEvent:
    event_type:  str
    campaign_id: int
    user_id:     int   = None
    properties:  dict  = field(default_factory=dict)
    event_id:    str   = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp:   float = field(default_factory=time.time)

class EventLogger:
    """Generic event bus. Types: impression, click, conversion, fraud, payout, error."""
    MAX_STREAM = 10000

    def emit(self, event: PlatformEvent) -> str:
        stream = cache.get(STREAM_KEY) or []
        stream.append({'type': event.event_type, 'campaign': event.campaign_id,
                       'user': event.user_id, 'id': event.event_id,
                       'ts': event.timestamp, 'props': event.properties})
        cache.set(STREAM_KEY, stream[-self.MAX_STREAM:], timeout=3600)
        if event.event_type == 'fraud' and event.properties.get('score', 0) > 0.8:
            self._alert_fraud(event)
        logger.debug(f'Event: {event.event_type} camp={event.campaign_id}')
        return event.event_id

    def impression(self, campaign_id, user_id, **p): return self.emit(PlatformEvent('impression', campaign_id, user_id, p))
    def click(self, campaign_id, user_id, **p):      return self.emit(PlatformEvent('click', campaign_id, user_id, p))
    def conversion(self, campaign_id, user_id, value, **p): return self.emit(PlatformEvent('conversion', campaign_id, user_id, {'value': value, **p}))
    def fraud(self, campaign_id, user_id, score, typ): return self.emit(PlatformEvent('fraud', campaign_id, user_id, {'score': score, 'type': typ}))

    def get_stream(self, event_type: str = None, limit: int = 100) -> list:
        s = cache.get(STREAM_KEY) or []
        if event_type: s = [e for e in s if e['type'] == event_type]
        return s[-limit:]

    def stats(self) -> dict:
        s = cache.get(STREAM_KEY) or []
        r = {}
        for e in s: r[e['type']] = r.get(e['type'], 0) + 1
        return r

    def _alert_fraud(self, event):
        try:
            from api.promotions.monitoring.alert_system import AlertSystem
            AlertSystem().send_fraud_alert(event.campaign_id, event.user_id, event.properties)
        except Exception: pass
