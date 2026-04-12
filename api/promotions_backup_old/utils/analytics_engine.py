# api/promotions/utils/analytics_engine.py
import logging
from django.core.cache import cache
logger = logging.getLogger('utils.analytics')

class AnalyticsEngine:
    """Unified analytics — delegates to reporting/ modules。"""

    def get_dashboard_data(self, user_id: int = None, role: str = 'admin') -> dict:
        ck = f'analytics:dashboard:{role}:{user_id}'
        if cache.get(ck): return cache.get(ck)
        from api.promotions.reporting.revenue_report import RevenueReport
        from api.promotions.reporting.user_growth_stats import UserGrowthStats
        data = {
            'revenue_today': RevenueReport().daily(),
            'user_growth':   UserGrowthStats().overview(days=7),
        }
        if role == 'advertiser' and user_id:
            from api.promotions.reporting.campaign_performance import CampaignPerformanceReport
            from api.promotions.models import Campaign
            camps = list(Campaign.objects.filter(advertiser_id=user_id).values_list('id',flat=True)[:5])
            data['campaigns'] = [CampaignPerformanceReport().for_campaign(cid) for cid in camps]
        cache.set(ck, data, timeout=300)
        return data

    def track_event(self, event_type: str, user_id: int, campaign_id: int = None, **props) -> str:
        from api.promotions.tracking.event_logger import EventLogger, PlatformEvent
        return EventLogger().emit(PlatformEvent(event_type, campaign_id or 0, user_id, props))

    def get_funnel_data(self, campaign_id: int) -> dict:
        from api.promotions.models import TaskSubmission
        from api.promotions.choices import SubmissionStatus
        from django.db.models import Count
        subs = TaskSubmission.objects.filter(campaign_id=campaign_id)
        return {
            'impressions': 0,
            'clicks':      0,
            'started':     subs.count(),
            'submitted':   subs.count(),
            'approved':    subs.filter(status=SubmissionStatus.APPROVED).count(),
        }
