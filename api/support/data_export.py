# api/support/data_export.py
"""
Data export module for support system.
Exports: tickets, disputes, CSAT reports, agent performance.
Formats: CSV, JSON, Excel-compatible CSV.
"""
import csv
import io
import json
import logging
from datetime import timedelta

from django.http import HttpResponse, JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


def export_tickets_csv(queryset, include_messages: bool = False) -> bytes:
    """Export tickets to CSV bytes (UTF-8 BOM for Excel)."""
    buf     = io.StringIO()
    writer  = csv.writer(buf)
    headers = [
        'ticket_id', 'user_username', 'user_email', 'category',
        'subject', 'priority', 'status', 'channel',
        'assigned_to', 'escalated', 'satisfaction_rating',
        'message_count', 'created_at', 'first_response_at',
        'resolved_at', 'resolution_hours',
        'sla_fr_breached', 'sla_res_breached',
    ]
    if include_messages:
        headers.append('first_message')

    writer.writerow(headers)

    for t in queryset.select_related('user', 'assigned_to').prefetch_related('sla'):
        resolution_hours = ''
        if t.resolved_at and t.created_at:
            resolution_hours = round(
                (t.resolved_at - t.created_at).total_seconds() / 3600, 1
            )
        try:
            sla_fr = t.sla.first_response_breached
            sla_rs = t.sla.resolution_breached
        except Exception:
            sla_fr = sla_rs = False

        row = [
            t.ticket_id,
            t.user.username if t.user else '',
            t.user.email    if t.user else '',
            t.category      or '',
            t.subject       or '',
            t.priority      or '',
            t.status        or '',
            t.channel       or '',
            t.assigned_to.username if t.assigned_to else '',
            t.escalated,
            t.satisfaction_rating or '',
            t.message_count,
            t.created_at.strftime('%Y-%m-%d %H:%M') if t.created_at else '',
            t.first_response_at.strftime('%Y-%m-%d %H:%M') if t.first_response_at else '',
            t.resolved_at.strftime('%Y-%m-%d %H:%M')   if t.resolved_at else '',
            resolution_hours,
            sla_fr,
            sla_rs,
        ]
        if include_messages:
            try:
                first_msg = t.messages.filter(is_agent=False).order_by('created_at').first()
                row.append(first_msg.content[:200] if first_msg else '')
            except Exception:
                row.append('')
        writer.writerow(row)

    return buf.getvalue().encode('utf-8-sig')


def export_disputes_csv(queryset) -> bytes:
    """Export offer disputes to CSV."""
    buf    = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'dispute_id', 'user_username', 'user_email',
        'offer_id', 'offer_name', 'expected_amount', 'click_id',
        'status', 'verification_status', 'confidence_score',
        'ticket_id', 'created_at', 'resolved_at', 'agent_notes',
    ])
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
            (d.agent_notes or '')[:200],
        ])
    return buf.getvalue().encode('utf-8-sig')


def export_csat_json(days: int = 30, tenant=None) -> dict:
    """Export CSAT report as JSON dict."""
    from api.support.reports import reports_service
    return reports_service.get_csat_report(days=days, tenant=tenant)


def export_agent_performance_csv(days: int = 30, tenant=None) -> bytes:
    """Export agent performance report."""
    from api.support.reports import reports_service
    performance = reports_service.get_agent_performance(days=days, tenant=tenant)
    buf     = io.StringIO()
    writer  = csv.writer(buf)
    writer.writerow(['agent_id', 'username', 'total_tickets', 'avg_csat'])
    for row in performance:
        writer.writerow([
            row.get('assigned_to', ''),
            row.get('assigned_to__username', ''),
            row.get('total', 0),
            round(row.get('avg_csat') or 0, 2),
        ])
    return buf.getvalue().encode('utf-8-sig')


def get_export_response(data: bytes, filename: str, content_type: str = 'text/csv') -> HttpResponse:
    """Create Django HttpResponse for file download."""
    response = HttpResponse(data, content_type=f'{content_type}; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response