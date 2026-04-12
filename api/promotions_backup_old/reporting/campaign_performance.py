# api/promotions/reporting/campaign_performance.py
import logging
from django.core.cache import cache
logger = logging.getLogger('reporting.campaign')

class CampaignPerformanceReport:
    def for_campaign(self, campaign_id: int, days: int = 7) -> dict:
        ck = f'report:camp:{campaign_id}:{days}'
        if cache.get(ck): return cache.get(ck)
        try:
            from api.promotions.models import TaskSubmission, Campaign
            from api.promotions.choices import SubmissionStatus
            from django.utils import timezone
            from datetime import timedelta
            from django.db.models import Count, Sum, Avg

            camp  = Campaign.objects.select_related('platform','category').get(pk=campaign_id)
            since = timezone.now() - timedelta(days=days)
            subs  = TaskSubmission.objects.filter(campaign_id=campaign_id, submitted_at__gte=since)
            total  = subs.count()
            approv = subs.filter(status=SubmissionStatus.APPROVED).count()
            r = {
                'campaign_id': campaign_id, 'title': camp.title,
                'platform': camp.platform.name if camp.platform else '',
                'days': days,
                'total_submissions':    total,
                'approved':             approv,
                'rejected':             subs.filter(status=SubmissionStatus.REJECTED).count(),
                'pending':              subs.filter(status=SubmissionStatus.PENDING).count(),
                'approval_rate':        round(approv/max(total,1)*100, 2),
                'total_spent_usd':      float(camp.spent_usd),
                'budget_utilization':   round(float(camp.spent_usd)/float(max(camp.total_budget_usd,1))*100, 2),
                'cost_per_approval':    round(float(camp.spent_usd)/max(approv,1), 4),
                'fill_rate':            round(camp.filled_slots/max(camp.total_slots,1)*100, 2),
            }
            cache.set(ck, r, timeout=600)
            return r
        except Exception as e:
            return {'campaign_id': campaign_id, 'error': str(e)}

    def top_campaigns(self, limit: int = 10, days: int = 7) -> list:
        from django.db.models import Count, Sum
        from django.utils import timezone
        from datetime import timedelta
        from api.promotions.models import AdminCommissionLog
        since = timezone.now() - timedelta(days=days)
        return list(
            AdminCommissionLog.objects.filter(created_at__gte=since)
            .values('campaign__id','campaign__title')
            .annotate(revenue=Sum('total_amount_usd'), count=Count('id'))
            .order_by('-revenue')[:limit]
        )
