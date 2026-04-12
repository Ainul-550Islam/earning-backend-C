# =============================================================================
# promotions/subid_tracking/subid_manager.py
# 🟠 HIGH — SubID Tracking System
# Every top network has this. Publisher appends subid to track traffic sources.
# Example: ?pub=123&s1=tiktok&s2=video456&s3=us_male_18_24
# Lets publisher know which traffic source converts best.
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import logging

logger = logging.getLogger(__name__)

MAX_SUBID_LENGTH = 64
SUBID_SLOTS = ['s1', 's2', 's3', 's4', 's5']  # Up to 5 SubID slots


class SubIDManager:
    """
    Track conversions by SubID.
    Publisher can split traffic by source, placement, ad ID, etc.
    Reports show which SubIDs are most profitable.
    """

    def record_click(self, publisher_id: int, campaign_id: int, click_id: str,
                     subids: dict, country: str = '', device: str = '') -> dict:
        """Record a click with SubID data."""
        # Validate subids
        clean_subids = {}
        for slot in SUBID_SLOTS:
            val = str(subids.get(slot, ''))[:MAX_SUBID_LENGTH]
            if val:
                clean_subids[slot] = val

        click_data = {
            'click_id': click_id,
            'publisher_id': publisher_id,
            'campaign_id': campaign_id,
            'subids': clean_subids,
            'country': country,
            'device': device,
            'clicked_at': timezone.now().isoformat(),
            'converted': False,
        }
        cache.set(f'subid_click:{click_id}', click_data, timeout=3600 * 24 * 30)

        # Aggregate subid stats
        for slot, val in clean_subids.items():
            stat_key = f'subid_stat:{publisher_id}:{campaign_id}:{slot}:{val}:{timezone.now().date()}'
            current = cache.get(stat_key, {'clicks': 0, 'conversions': 0, 'earnings': '0'})
            current['clicks'] += 1
            cache.set(stat_key, current, timeout=3600 * 48)

        return {'click_id': click_id, 'subids_recorded': clean_subids}

    def record_conversion(self, click_id: str, payout: Decimal) -> dict:
        """Mark a click as converted and update SubID stats."""
        click_data = cache.get(f'subid_click:{click_id}')
        if not click_data:
            return {'error': 'Click not found'}

        click_data['converted'] = True
        click_data['payout'] = str(payout)
        click_data['converted_at'] = timezone.now().isoformat()
        cache.set(f'subid_click:{click_id}', click_data, timeout=3600 * 24 * 30)

        for slot, val in click_data.get('subids', {}).items():
            stat_key = f'subid_stat:{click_data["publisher_id"]}:{click_data["campaign_id"]}:{slot}:{val}:{timezone.now().date()}'
            current = cache.get(stat_key, {'clicks': 0, 'conversions': 0, 'earnings': '0'})
            current['conversions'] += 1
            current['earnings'] = str(Decimal(current['earnings']) + payout)
            cache.set(stat_key, current, timeout=3600 * 48)

        return {'success': True, 'click_id': click_id, 'subids': click_data.get('subids', {})}

    def get_subid_report(self, publisher_id: int, campaign_id: int = None,
                          slot: str = 's1', days: int = 7) -> list:
        """Get SubID performance report."""
        from api.promotions.models import TaskSubmission, PromotionTransaction
        from django.db.models import Q
        cutoff = timezone.now() - timezone.timedelta(days=days)

        # In production: query SubID tracking model in DB
        # For now: return structured sample
        return [
            {
                'subid_slot': slot,
                'subid_value': f'source_{i}',
                'clicks': 100 - (i * 10),
                'conversions': 20 - (i * 2),
                'cvr_pct': round((20 - (i * 2)) / (100 - (i * 10)) * 100, 1) if (100 - i*10) > 0 else 0,
                'earnings': str(Decimal(str((20 - i * 2) * 1.0))),
                'epc': str(Decimal('0.20').quantize(Decimal('0.0001'))),
            }
            for i in range(5)
        ]

    def get_top_performing_subids(self, publisher_id: int, days: int = 30, limit: int = 20) -> dict:
        """Get publisher's best SubID sources."""
        result = {}
        for slot in SUBID_SLOTS:
            result[slot] = self.get_subid_report(publisher_id, slot=slot, days=days)[:limit]
        return {
            'publisher_id': publisher_id,
            'period_days': days,
            'by_slot': result,
            'tip': f'Use ?s1=source&s2=ad_id&s3=placement in your tracking URLs',
        }

    def generate_tracking_url_with_subids(self, publisher_id: int, campaign_id: int,
                                           subids: dict = None) -> str:
        """Generate tracking URL with SubID parameters."""
        from django.conf import settings
        base = getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        params = f'pub={publisher_id}&cid={campaign_id}'
        for slot in SUBID_SLOTS:
            val = (subids or {}).get(slot, '')
            if val:
                params += f'&{slot}={val}'
        return f'{base}/api/promotions/go/{campaign_id}/?{params}'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def subid_report_view(request):
    """GET /api/promotions/subid/report/?slot=s1&days=7&campaign=1"""
    manager = SubIDManager()
    data = manager.get_top_performing_subids(
        publisher_id=request.user.id,
        days=int(request.query_params.get('days', 7)),
    )
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generate_subid_url_view(request):
    """GET /api/promotions/subid/generate/?campaign=1&s1=tiktok&s2=video123"""
    manager = SubIDManager()
    campaign_id = int(request.query_params.get('campaign', 0))
    subids = {s: request.query_params.get(s, '') for s in SUBID_SLOTS}
    url = manager.generate_tracking_url_with_subids(
        publisher_id=request.user.id,
        campaign_id=campaign_id,
        subids=subids,
    )
    return Response({'tracking_url': url, 'subids': {k: v for k, v in subids.items() if v}})
