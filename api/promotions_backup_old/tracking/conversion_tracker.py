# =============================================================================
# api/promotions/tracking/conversion_tracker.py
# Conversion Tracker — Task completion attribution (last click / first click / linear)
# =============================================================================
import logging, time, uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional
from django.core.cache import cache

logger = logging.getLogger('tracking.conversion')
CACHE_PREFIX_CONV = 'track:conv:{}'


class AttributionModel(str, Enum):
    LAST_CLICK  = 'last_click'
    FIRST_CLICK = 'first_click'
    LINEAR      = 'linear'


@dataclass
class ConversionEvent:
    campaign_id:     int
    user_id:         int
    conversion_type: str           # 'task_complete', 'app_install', 'signup'
    value_usd:       Decimal
    click_id:        Optional[str] = None
    attribution:     str           = AttributionModel.LAST_CLICK
    metadata:        dict          = field(default_factory=dict)
    event_id:        str           = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp:       float         = field(default_factory=time.time)


class ConversionTracker:
    """
    Conversion attribution tracking.
    Attribution window: 30 days.
    Models: last_click (default), first_click, linear.
    """
    ATTRIBUTION_WINDOW = 86400 * 30

    def track(self, event: ConversionEvent) -> dict:
        touchpoints = self._get_touchpoints(event.user_id, event.campaign_id)
        result      = self._apply_attribution(event, touchpoints)
        self._save(event, result)
        logger.info(f'Conversion: camp={event.campaign_id} user={event.user_id} type={event.conversion_type} ${event.value_usd}')
        return result

    def record_touchpoint(self, user_id: int, campaign_id: int, click_id: str) -> None:
        key = CACHE_PREFIX_CONV.format(f'touch:{user_id}:{campaign_id}')
        pts = cache.get(key) or []
        pts.append({'click_id': click_id, 'ts': time.time()})
        cache.set(key, pts[-10:], timeout=self.ATTRIBUTION_WINDOW)

    def get_stats(self, campaign_id: int, days: int = 7) -> dict:
        try:
            from api.promotions.models import ConversionLog
            from django.utils import timezone
            from datetime import timedelta
            from django.db.models import Count, Sum
            since = timezone.now() - timedelta(days=days)
            r = ConversionLog.objects.filter(campaign_id=campaign_id, created_at__gte=since).aggregate(
                count=Count('id'), total=Sum('value_usd'))
            return {'conversions': r['count'] or 0, 'value_usd': float(r['total'] or 0)}
        except Exception:
            return {'conversions': 0, 'value_usd': 0.0}

    def _get_touchpoints(self, user_id, campaign_id):
        return cache.get(CACHE_PREFIX_CONV.format(f'touch:{user_id}:{campaign_id}')) or []

    def _apply_attribution(self, event, touchpoints):
        if not touchpoints:
            return {'click_id': event.click_id, 'model': event.attribution, 'credit': 1.0}
        if event.attribution == AttributionModel.FIRST_CLICK:
            return {'click_id': touchpoints[0]['click_id'], 'model': 'first_click', 'credit': 1.0}
        if event.attribution == AttributionModel.LINEAR:
            n = len(touchpoints)
            return {'click_ids': [t['click_id'] for t in touchpoints], 'model': 'linear', 'credit': round(1/n,4)}
        return {'click_id': touchpoints[-1]['click_id'], 'model': 'last_click', 'credit': 1.0}

    def _save(self, event, attribution):
        try:
            from api.promotions.models import ConversionLog
            ConversionLog.objects.create(
                campaign_id=event.campaign_id, user_id=event.user_id,
                conversion_type=event.conversion_type, value_usd=event.value_usd,
                event_id=event.event_id, attribution_model=attribution.get('model',''),
                attributed_click_id=attribution.get('click_id',''),
            )
        except Exception as e:
            logger.error(f'Conversion save failed: {e}')
