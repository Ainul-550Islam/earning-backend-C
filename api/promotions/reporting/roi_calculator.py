# api/promotions/reporting/roi_calculator.py
import logging
from decimal import Decimal
logger = logging.getLogger('reporting.roi')

class ROICalculator:
    """Campaign and platform-level ROI calculations。"""

    def campaign_roi(self, campaign_id: int) -> dict:
        try:
            from api.promotions.models import Campaign, TaskSubmission, AdminCommissionLog
            from api.promotions.choices import SubmissionStatus
            from django.db.models import Sum, Count
            camp    = Campaign.objects.get(pk=campaign_id)
            spend   = float(camp.spent_usd)
            approved = TaskSubmission.objects.filter(campaign_id=campaign_id, status=SubmissionStatus.APPROVED).count()
            cost_per = round(spend/max(approved,1), 4)
            revenue  = float(AdminCommissionLog.objects.filter(campaign_id=campaign_id).aggregate(t=Sum('total_amount_usd'))['t'] or 0)
            profit   = revenue - spend
            roi_pct  = round(profit/max(spend,0.01)*100, 2)
            return {
                'campaign_id': campaign_id, 'total_spend': spend,
                'approved_tasks': approved, 'cost_per_task': cost_per,
                'revenue': revenue, 'profit': profit,
                'roi_percent': roi_pct, 'fill_rate': round(camp.filled_slots/max(camp.total_slots,1)*100,2),
            }
        except Exception as e:
            return {'campaign_id': campaign_id, 'error': str(e)}

    def platform_roi(self, platform_name: str, days: int = 30) -> dict:
        from django.db.models import Sum, Count, Avg
        from django.utils import timezone
        from datetime import timedelta
        from api.promotions.models import AdminCommissionLog
        since = timezone.now() - timedelta(days=days)
        qs    = AdminCommissionLog.objects.filter(created_at__gte=since, campaign__platform__name__iexact=platform_name)
        return {
            'platform': platform_name, 'days': days,
            'revenue':     float(qs.aggregate(t=Sum('total_amount_usd'))['t'] or 0),
            'commission':  float(qs.aggregate(t=Sum('commission_usd'))['t'] or 0),
            'transactions': qs.count(),
        }
