"""
api/support/reports/sla_report.py
FILE 51/70 — SLA Compliance Report
"""
import logging
from datetime import timedelta
from django.utils import timezone
logger = logging.getLogger(__name__)

class SLAReport:
    def generate(self, days: int = 30) -> dict:
        from api.support.models import TicketSLA, SLABreach
        since   = timezone.now() - timedelta(days=days)
        slas    = TicketSLA.objects.filter(created_at__gte=since)
        total   = slas.count()
        if not total:
            return {'total': 0, 'compliance_rate': 100}

        fr_breach  = slas.filter(first_response_breached=True).count()
        res_breach = slas.filter(resolution_breached=True).count()
        any_breach = slas.filter(first_response_breached=True).union(slas.filter(resolution_breached=True)).count()

        by_priority = {}
        for p in ['urgent','high','medium','low']:
            p_slas  = slas.filter(ticket__priority=p)
            p_total = p_slas.count()
            if p_total:
                p_breach = p_slas.filter(first_response_breached=True).count()
                by_priority[p] = {
                    'total':       p_total,
                    'breached':    p_breach,
                    'compliance':  round((p_total - p_breach) / p_total * 100, 1),
                }

        breaches = list(SLABreach.objects.filter(breached_at__gte=since).values(
            'ticket__ticket_id','ticket__priority','breach_type','overdue_hours','breached_at'
        ).order_by('-overdue_hours')[:20])

        from django.db.models import Avg
        avg_overdue = SLABreach.objects.filter(breached_at__gte=since).aggregate(avg=Avg('overdue_hours'))['avg'] or 0

        return {
            'period_days':          days,
            'total':                total,
            'first_response_breached': fr_breach,
            'resolution_breached':  res_breach,
            'any_breached':         any_breach,
            'compliance_rate':      round((total - any_breach) / total * 100, 1),
            'by_priority':          by_priority,
            'worst_breaches':       breaches,
            'avg_overdue_hrs':      round(avg_overdue, 1),
        }

sla_report = SLAReport()