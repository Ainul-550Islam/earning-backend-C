# api/support/resources.py
"""
Data export/import resources for support system.
Uses Django Import-Export or raw CSV/Excel.
Full code — no summarizing.
"""
import csv
import io
import logging
from datetime import timedelta
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


class TicketExportResource:
    """Export support tickets to CSV or Excel."""

    HEADERS = [
        'ticket_id', 'user_username', 'user_email', 'category', 'subject',
        'priority', 'status', 'channel', 'assigned_to', 'created_at',
        'first_response_at', 'resolved_at', 'resolution_hours',
        'satisfaction_rating', 'message_count', 'escalated',
        'sla_fr_breached', 'sla_res_breached',
    ]

    def export_csv(self, queryset) -> bytes:
        """Export queryset to CSV bytes."""
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(self.HEADERS)

        for ticket in queryset.select_related('user', 'assigned_to').prefetch_related('sla'):
            resolution_hours = ''
            if ticket.resolved_at and ticket.created_at:
                resolution_hours = round(
                    (ticket.resolved_at - ticket.created_at).total_seconds() / 3600, 1
                )
            try:
                sla = ticket.sla
                fr_breach  = sla.first_response_breached
                res_breach = sla.resolution_breached
            except Exception:
                fr_breach = res_breach = False

            writer.writerow([
                ticket.ticket_id,
                ticket.user.username if ticket.user else '',
                ticket.user.email    if ticket.user else '',
                ticket.category      or '',
                ticket.subject       or '',
                ticket.priority      or '',
                ticket.status        or '',
                ticket.channel       or '',
                ticket.assigned_to.username if ticket.assigned_to else '',
                ticket.created_at.strftime('%Y-%m-%d %H:%M') if ticket.created_at else '',
                ticket.first_response_at.strftime('%Y-%m-%d %H:%M') if ticket.first_response_at else '',
                ticket.resolved_at.strftime('%Y-%m-%d %H:%M')   if ticket.resolved_at else '',
                resolution_hours,
                ticket.satisfaction_rating or '',
                ticket.message_count,
                ticket.escalated,
                fr_breach,
                res_breach,
            ])

        return buf.getvalue().encode('utf-8-sig')  # BOM for Excel

    def export_csv_response(self, queryset, filename: str = None) -> HttpResponse:
        """Return CSV as Django HttpResponse."""
        if not filename:
            filename = f'tickets_{timezone.now().strftime("%Y%m%d_%H%M")}.csv'
        data     = self.export_csv(queryset)
        response = HttpResponse(data, content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    def export_recent(self, days: int = 30, tenant=None) -> bytes:
        """Export tickets from the last N days."""
        from api.support.models import SupportTicket
        since = timezone.now() - timedelta(days=days)
        qs    = SupportTicket.objects.filter(created_at__gte=since)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return self.export_csv(qs)


class DisputeExportResource:
    """Export offer disputes to CSV."""

    HEADERS = [
        'dispute_id', 'user_username', 'user_email', 'offer_id', 'offer_name',
        'expected_amount', 'click_id', 'status', 'verification_status',
        'confidence_score', 'ticket_id', 'created_at', 'resolved_at',
    ]

    def export_csv(self, queryset) -> bytes:
        buf    = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(self.HEADERS)
        for d in queryset.select_related('user', 'ticket'):
            writer.writerow([
                d.id,
                d.user.username if d.user else '',
                d.user.email    if d.user else '',
                d.offer_id,
                d.offer_name,
                d.expected_amount,
                d.click_id,
                d.status,
                d.verification_status,
                d.confidence_score,
                d.ticket.ticket_id if d.ticket else '',
                d.created_at.strftime('%Y-%m-%d %H:%M') if d.created_at else '',
                d.resolved_at.strftime('%Y-%m-%d %H:%M') if d.resolved_at else '',
            ])
        return buf.getvalue().encode('utf-8-sig')


class CSATReportResource:
    """Generate CSAT/NPS reports."""

    def generate_report(self, days: int = 30, tenant=None) -> dict:
        """Generate CSAT statistics for the given period."""
        from api.support.models import TicketRating
        from django.db.models import Avg, Count
        since = timezone.now() - timedelta(days=days)
        qs    = TicketRating.objects.filter(rated_at__gte=since)
        if tenant:
            qs = qs.filter(ticket__tenant=tenant)

        if not qs.exists():
            return {'period_days': days, 'total': 0, 'avg_score': 0, 'nps': 0}

        total      = qs.count()
        avg        = qs.aggregate(a=Avg('score'))['a'] or 0
        promoters  = qs.filter(score=5).count()
        detractors = qs.filter(score__in=[1, 2]).count()
        nps        = round((promoters - detractors) / total * 100, 1) if total else 0

        # Category breakdown
        from django.db.models import Count as DCount
        by_category = list(
            qs.values('ticket__category')
            .annotate(count=DCount('id'), avg=Avg('score'))
            .order_by('-avg')
        )

        return {
            'period_days':   days,
            'total':         total,
            'avg_score':     round(avg, 2),
            'promoters':     promoters,
            'detractors':    detractors,
            'nps':           nps,
            'by_category':   by_category,
        }


# Singletons
ticket_export   = TicketExportResource()
dispute_export  = DisputeExportResource()
csat_report     = CSATReportResource()