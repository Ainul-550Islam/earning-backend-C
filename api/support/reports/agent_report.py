"""
api/support/reports/agent_report.py
FILE 49/70 — Per-Agent Performance Report
"""
import logging
from datetime import timedelta
from django.utils import timezone
logger = logging.getLogger(__name__)

class AgentReport:
    def generate(self, days: int = 30) -> list:
        from api.support.models import SupportAgent, SupportTicket, TicketRating
        from django.db.models import Avg, Count
        since  = timezone.now() - timedelta(days=days)
        agents = SupportAgent.objects.filter(is_active=True).select_related('user','department')
        report = []
        for agent in agents:
            tickets   = SupportTicket.objects.filter(assigned_to=agent.user, created_at__gte=since)
            resolved  = tickets.filter(status='resolved').count()
            total     = tickets.count()
            responded = tickets.filter(admin_responded_at__isnull=False)
            avg_resp  = 0
            if responded.exists():
                times    = [(t.admin_responded_at - t.created_at).total_seconds()/60 for t in responded]
                avg_resp = round(sum(times)/len(times), 1)
            csat = TicketRating.objects.filter(ticket__assigned_to=agent.user, created_at__gte=since).aggregate(avg=Avg('rating'))['avg'] or 0
            sla_breached = tickets.filter(escalated=True).count()
            report.append({
                'username':        agent.user.username,
                'email':           agent.user.email,
                'role':            agent.role,
                'department':      agent.department.name if agent.department else '',
                'period_days':     days,
                'total_assigned':  total,
                'resolved':        resolved,
                'resolution_rate': round(resolved/total*100,1) if total else 0,
                'avg_response_min':avg_resp,
                'csat_score':      round(csat, 2),
                'sla_breached':    sla_breached,
                'active_now':      tickets.filter(status__in=['open','in_progress','waiting_user']).count(),
            })
        return sorted(report, key=lambda x: x['resolved'], reverse=True)

    def export_csv(self, days: int = 30) -> tuple:
        import csv
        from io import StringIO
        data   = self.generate(days)
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys() if data else [])
        writer.writeheader()
        writer.writerows(data)
        filename = f'agent_report_{timezone.now().strftime("%Y%m%d")}.csv'
        return filename, output.getvalue().encode('utf-8-sig')

agent_report = AgentReport()