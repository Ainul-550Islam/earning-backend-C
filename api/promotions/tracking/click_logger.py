# =============================================================================
# api/promotions/tracking/click_logger.py
# Click Logger — Campaign click events (Redis buffer → async DB flush)
# Deduplication, real-time stats, device detection
# =============================================================================
import hashlib, hmac, logging, time, uuid
from dataclasses import dataclass, field
from typing import Optional
from django.core.cache import cache

logger = logging.getLogger('tracking.click')
CACHE_PREFIX = 'track:click:{}'


@dataclass
class ClickEvent:
    campaign_id:  int
    user_id:      Optional[int]
    ip_address:   str
    user_agent:   str
    referrer:     str   = ''
    country:      str   = ''
    device_type:  str   = 'unknown'    # mobile, desktop, tablet
    click_id:     str   = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp:    float = field(default_factory=time.time)
    is_duplicate: bool  = False


class ClickLogger:
    """
    High-performance click logging.
    Buffer clicks in Redis → async flush to DB via Celery.

    Features:
    - Deduplication (same user + campaign within 5 min = duplicate)
    - Device type detection
    - Country tracking
    - Real-time buffer with auto-flush at 100 clicks
    """
    DEDUP_WINDOW = 300   # 5 minutes

    def log_click(self, event: ClickEvent) -> ClickEvent:
        """Click event log করে।"""
        # Deduplication check
        dedup_key = CACHE_PREFIX.format(f'dedup:{event.user_id}:{event.campaign_id}')
        if cache.get(dedup_key):
            event.is_duplicate = True
            logger.debug(f'Duplicate click: campaign={event.campaign_id} user={event.user_id}')
            return event
        cache.set(dedup_key, True, timeout=self.DEDUP_WINDOW)

        # Auto-detect device type
        if not event.device_type or event.device_type == 'unknown':
            event.device_type = self._detect_device(event.user_agent)

        # Buffer in Redis
        buffer_key = CACHE_PREFIX.format('buffer')
        buffer     = cache.get(buffer_key) or []
        buffer.append({
            'campaign_id': event.campaign_id,
            'user_id':     event.user_id,
            'ip':          event.ip_address,
            'country':     event.country,
            'device':      event.device_type,
            'referrer':    event.referrer[:200] if event.referrer else '',
            'click_id':    event.click_id,
            'timestamp':   event.timestamp,
        })
        cache.set(buffer_key, buffer[-500:], timeout=3600)

        # Auto-flush if buffer >= 100
        if len(buffer) >= 100:
            self._flush_async()

        # Update realtime counter
        count_key = CACHE_PREFIX.format(f'count:{event.campaign_id}')
        try:
            cache.incr(count_key)
        except Exception:
            cache.set(count_key, 1, timeout=86400)

        logger.debug(f'Click logged: campaign={event.campaign_id} user={event.user_id} id={event.click_id}')
        return event

    def flush_buffer(self) -> int:
        """Buffer → DB flush (Celery task থেকে call করো)।"""
        buffer_key = CACHE_PREFIX.format('buffer')
        buffer     = cache.get(buffer_key) or []
        if not buffer:
            return 0

        cache.delete(buffer_key)
        try:
            from api.promotions.models import ClickLog
            from django.utils import timezone
            import datetime

            objs = [
                ClickLog(
                    campaign_id = c['campaign_id'],
                    user_id     = c['user_id'],
                    ip_address  = c['ip'],
                    country     = c.get('country', ''),
                    device_type = c.get('device', ''),
                    referrer    = c.get('referrer', ''),
                    click_id    = c['click_id'],
                    created_at  = datetime.datetime.fromtimestamp(c['timestamp'], tz=timezone.utc),
                )
                for c in buffer
            ]
            ClickLog.objects.bulk_create(objs, ignore_conflicts=True)
            logger.info(f'Click buffer flushed: {len(objs)} clicks saved')
            return len(objs)
        except Exception as e:
            # Restore buffer on failure
            cache.set(buffer_key, buffer, timeout=3600)
            logger.error(f'Click buffer flush failed: {e}')
            return 0

    def get_campaign_stats(self, campaign_id: int, hours: int = 24) -> dict:
        """Campaign click stats।"""
        try:
            from api.promotions.models import ClickLog
            from django.utils import timezone
            from datetime import timedelta
            from django.db.models import Count

            since  = timezone.now() - timedelta(hours=hours)
            qs     = ClickLog.objects.filter(campaign_id=campaign_id, created_at__gte=since)
            total  = qs.count()
            unique = qs.values('user_id').distinct().count()
            by_device = dict(qs.values('device_type').annotate(c=Count('id')).values_list('device_type','c'))

            return {'total': total, 'unique': unique, 'by_device': by_device, 'hours': hours}
        except Exception:
            return {'total': 0, 'unique': 0, 'by_device': {}}

    def get_realtime_count(self, campaign_id: int) -> int:
        """Today's realtime click count (Redis)।"""
        return cache.get(CACHE_PREFIX.format(f'count:{campaign_id}')) or 0

    @staticmethod
    def _detect_device(user_agent: str) -> str:
        ua = (user_agent or '').lower()
        if any(k in ua for k in ['mobile', 'android', 'iphone', 'ipod']):
            return 'mobile'
        if any(k in ua for k in ['tablet', 'ipad']):
            return 'tablet'
        return 'desktop'

    def _flush_async(self):
        try:
            from api.promotions.tasks import flush_click_buffer
            flush_click_buffer.delay()
        except Exception:
            pass
