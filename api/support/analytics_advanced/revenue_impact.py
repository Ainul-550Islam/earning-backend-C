"""api/support/analytics_advanced/revenue_impact.py FILE 16"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
logger = logging.getLogger(__name__)

class RevenueImpactAnalyzer:
    def calculate(self, days: int = 30) -> dict:
        since = timezone.now() - timedelta(days=days)
        cost_per = getattr(settings, "SUPPORT_COST_PER_TICKET", 2.5)
        avg_ltv  = getattr(settings, "AVG_USER_LTV", 50)
        try:
            from api.support.models import SupportTicket, TicketRating
            from django.db.models import Avg
            total    = SupportTicket.objects.filter(created_at__gte=since).count()
            resolved = SupportTicket.objects.filter(resolved_at__gte=since).count()
            csat     = TicketRating.objects.filter(created_at__gte=since).aggregate(avg=Avg("rating"))["avg"] or 3
            cost     = total * cost_per
            # Estimate: each resolved ticket prevents 10% churn
            churn_prevented = resolved * 0.1
            revenue_saved   = churn_prevented * avg_ltv
            # CSAT impact: bad CSAT = more churn
            csat_factor = (csat - 3) * 0.05
            return {
                "period_days":       days,
                "total_tickets":     total,
                "resolved":          resolved,
                "support_cost_usd":  round(cost, 2),
                "revenue_saved_usd": round(revenue_saved, 2),
                "net_roi_usd":       round(revenue_saved - cost, 2),
                "roi_pct":           round((revenue_saved - cost) / max(cost,1) * 100, 1),
                "cost_per_ticket":   cost_per,
                "csat_revenue_impact": round(csat_factor * total * avg_ltv, 2),
                "churn_prevented":   round(churn_prevented, 0),
            }
        except Exception as e:
            logger.error(f"Revenue impact: {e}"); return {}

    def get_cost_by_category(self, days: int = 30) -> list:
        try:
            from api.support.models import SupportTicket
            from django.db.models import Count
            cost_per = getattr(settings, "SUPPORT_COST_PER_TICKET", 2.5)
            since    = timezone.now() - timedelta(days=days)
            cats     = SupportTicket.objects.filter(created_at__gte=since).values("category").annotate(count=Count("id")).order_by("-count")
            return [{"category":c["category"],"count":c["count"],"cost_usd":round(c["count"]*cost_per,2)} for c in cats]
        except Exception: return []

revenue_impact_analyzer = RevenueImpactAnalyzer()