# api/support/reports.py
"""
Support analytics and reporting.
Generate stats, trends, and export reports.
"""
import logging
from datetime import timedelta
from typing import Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


class SupportReports:
    """Generate support analytics reports."""

    def get_overview(self, days: int = 30, tenant=None) -> dict:
        """Overall support performance for the period."""
        from api.support.models import SupportTicket, TicketRating
        from django.db.models import Avg, Count, Q
        since = timezone.now() - timedelta(days=days)
        qs    = SupportTicket.objects.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)

        total        = qs.count()
        resolved     = qs.filter(status__in=['resolved','closed'])
        resolution_r = round(resolved.count() / total * 100, 1) if total else 0

        # Average resolution time (hours)
        avg_resolution = 0.0
        resolved_with_time = resolved.filter(resolved_at__isnull=False)
        if resolved_with_time.exists():
            times = [
                (t.resolved_at - t.created_at).total_seconds() / 3600
                for t in resolved_with_time.select_related()
                if t.resolved_at and t.created_at
            ]
            avg_resolution = round(sum(times) / len(times), 1) if times else 0.0

        # CSAT
        ratings      = TicketRating.objects.filter(rated_at__gte=since)
        if tenant:
            ratings = ratings.filter(ticket__tenant=tenant)
        avg_csat     = ratings.aggregate(a=Avg('score'))['a'] or 0
        csat_count   = ratings.count()

        # SLA compliance
        from api.support.models import TicketSLA
        sla_qs       = TicketSLA.objects.filter(ticket__in=qs)
        sla_total    = sla_qs.count()
        sla_breached = sla_qs.filter(
            Q(first_response_breached=True)|Q(resolution_breached=True)
        ).count()
        sla_rate = round((sla_total - sla_breached) / sla_total * 100, 1) if sla_total else 100.0

        return {
            'period_days':       days,
            'total_tickets':     total,
            'open_tickets':      qs.filter(status__in=['open','in_progress','waiting_user']).count(),
            'resolved_tickets':  resolved.count(),
            'resolution_rate':   resolution_r,
            'avg_resolution_hours': avg_resolution,
            'avg_csat':          round(avg_csat, 2),
            'csat_responses':    csat_count,
            'sla_compliance':    sla_rate,
            'sla_breaches':      sla_breached,
            'escalated':         qs.filter(escalated=True).count(),
        }

    def get_category_breakdown(self, days: int = 30, tenant=None) -> list:
        """Ticket count and resolution rate by category."""
        from api.support.models import SupportTicket
        from django.db.models import Count, Q
        since = timezone.now() - timedelta(days=days)
        qs    = SupportTicket.objects.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        rows  = qs.values('category').annotate(
            total    = Count('id'),
            resolved = Count('id', filter=Q(status__in=['resolved','closed'])),
        ).order_by('-total')
        return [
            {
                'category':       r['category'],
                'total':          r['total'],
                'resolved':       r['resolved'],
                'resolution_rate':round(r['resolved']/r['total']*100, 1) if r['total'] else 0,
            }
            for r in rows
        ]

    def get_agent_performance(self, days: int = 30, tenant=None) -> list:
        """Per-agent ticket stats and CSAT."""
        from api.support.models import SupportTicket, TicketRating
        from django.db.models import Count, Avg
        from django.contrib.auth import get_user_model
        User  = get_user_model()
        since = timezone.now() - timedelta(days=days)
        qs    = SupportTicket.objects.filter(
            assigned_to__isnull=False, created_at__gte=since
        )
        if tenant:
            qs = qs.filter(tenant=tenant)
        rows  = qs.values('assigned_to', 'assigned_to__username').annotate(
            total    = Count('id'),
            resolved = Count('id', filter=Count('id')),  # placeholder
            avg_csat = Avg('ticket_rating__score'),
        ).order_by('-total')
        return list(rows[:50])

    def get_volume_trend(self, days: int = 30, granularity: str = 'day', tenant=None) -> list:
        """Ticket volume over time."""
        from api.support.models import SupportTicket
        from django.db.models import Count
        from django.db.models.functions import TruncDay, TruncHour, TruncWeek
        since = timezone.now() - timedelta(days=days)
        qs    = SupportTicket.objects.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        trunc_fn = {'day': TruncDay, 'hour': TruncHour, 'week': TruncWeek}.get(granularity, TruncDay)
        rows = qs.annotate(period=trunc_fn('created_at')).values('period').annotate(
            count=Count('id')
        ).order_by('period')
        return [{'date': r['period'].isoformat() if r['period'] else '', 'count': r['count']} for r in rows]

    def get_sla_report(self, days: int = 30, tenant=None) -> dict:
        """SLA performance breakdown by priority."""
        from api.support.models import TicketSLA, SupportTicket
        from django.db.models import Count, Q
        since = timezone.now() - timedelta(days=days)
        sla   = TicketSLA.objects.filter(ticket__created_at__gte=since)
        if tenant:
            sla = sla.filter(ticket__tenant=tenant)

        result = {}
        for priority in ('urgent', 'high', 'medium', 'low'):
            p_sla    = sla.filter(ticket__priority=priority)
            total    = p_sla.count()
            breached = p_sla.filter(
                Q(first_response_breached=True)|Q(resolution_breached=True)
            ).count()
            result[priority] = {
                'total':       total,
                'compliant':   total - breached,
                'breached':    breached,
                'sla_rate':    round((total-breached)/total*100, 1) if total else 100.0,
            }

        result['overall'] = self.get_overview(days=days, tenant=tenant)
        return result

    def get_csat_report(self, days: int = 30, tenant=None) -> dict:
        """CSAT and NPS metrics."""
        from api.support.models import TicketRating
        from django.db.models import Avg, Count
        since = timezone.now() - timedelta(days=days)
        qs    = TicketRating.objects.filter(rated_at__gte=since)
        if tenant:
            qs = qs.filter(ticket__tenant=tenant)

        total      = qs.count()
        if not total:
            return {'total': 0, 'avg_score': 0, 'nps': 0, 'distribution': {}}

        avg        = qs.aggregate(a=Avg('score'))['a'] or 0
        promoters  = qs.filter(score=5).count()
        passives   = qs.filter(score__in=[3,4]).count()
        detractors = qs.filter(score__in=[1,2]).count()
        nps        = round((promoters - detractors) / total * 100, 1)

        dist = {}
        for score in range(1, 6):
            count    = qs.filter(score=score).count()
            dist[score] = {'count': count, 'pct': round(count/total*100, 1)}

        return {
            'total':        total,
            'avg_score':    round(avg, 2),
            'promoters':    promoters,
            'passives':     passives,
            'detractors':   detractors,
            'nps':          nps,
            'distribution': dist,
        }

    def get_dispute_report(self, days: int = 30, tenant=None) -> dict:
        """Offer dispute statistics."""
        from api.support.models import OfferDispute
        from django.db.models import Count, Avg, Sum
        since = timezone.now() - timedelta(days=days)
        qs    = OfferDispute.objects.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)

        total    = qs.count()
        approved = qs.filter(status='approved')
        rejected = qs.filter(status='rejected')
        return {
            'total':         total,
            'approved':      approved.count(),
            'rejected':      rejected.count(),
            'pending':       qs.filter(status__in=['pending','investigating']).count(),
            'auto_approved': qs.filter(status='approved', agent_notes__icontains='auto').count(),
            'approval_rate': round(approved.count()/total*100, 1) if total else 0,
            'avg_confidence':round(qs.aggregate(a=Avg('confidence_score'))['a'] or 0, 2),
            'total_credited':str(approved.aggregate(s=Sum('expected_amount'))['s'] or 0),
        }


reports_service = SupportReports()