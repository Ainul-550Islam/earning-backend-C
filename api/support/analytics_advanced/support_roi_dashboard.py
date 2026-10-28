"""api/support/analytics_advanced/support_roi_dashboard.py FILE 17"""
import logging
from datetime import timedelta
from django.utils import timezone
logger = logging.getLogger(__name__)

class SupportROIDashboard:
    def get_full_roi_data(self, days: int = 30) -> dict:
        from api.support.analytics_advanced.revenue_impact import revenue_impact_analyzer
        from api.support.reports.ticket_report import ticket_report
        from api.support.reports.csat_report import csat_report
        from api.support.reports.agent_report import agent_report
        return {
            "revenue_impact": revenue_impact_analyzer.calculate(days),
            "cost_by_category": revenue_impact_analyzer.get_cost_by_category(days),
            "ticket_summary": ticket_report.generate(days).get("summary", {}),
            "csat_summary": {"avg": csat_report.generate(days).get("avg_score", 0), "nps": csat_report.generate(days).get("nps_score", 0)},
            "period_days": days,
            "generated_at": timezone.now().isoformat(),
        }

roi_dashboard = SupportROIDashboard()