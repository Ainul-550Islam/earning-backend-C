# api/support/services/ticket/TicketExportService.py  — WORLD #1
import csv, io, logging
from datetime import timedelta
from django.utils import timezone
from django.http import HttpResponse
logger = logging.getLogger(__name__)

class TicketExportService:
    HEADERS = ['ticket_id','user','category','subject','priority','status','channel','created_at','resolved_at','first_response_at','admin_response','satisfaction_rating','message_count']

    def export_csv_bytes(self, days: int = 30, filters: dict = None) -> bytes:
        from api.support.models import SupportTicket
        since = timezone.now() - timedelta(days=days)
        qs = SupportTicket.objects.filter(created_at__gte=since).select_related('user')
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(self.HEADERS)
        for t in qs:
            writer.writerow([
                t.ticket_id, t.user.username if t.user else '', t.category, t.subject,
                t.priority, t.status, t.channel,
                t.created_at.strftime('%Y-%m-%d %H:%M') if t.created_at else '',
                t.resolved_at.strftime('%Y-%m-%d %H:%M') if t.resolved_at else '',
                t.first_response_at.strftime('%Y-%m-%d %H:%M') if t.first_response_at else '',
                (t.admin_response or '')[:200], t.satisfaction_rating or '', t.message_count,
            ])
        return buf.getvalue().encode('utf-8-sig')

    def export_response(self, days: int = 30, fmt: str = 'csv', request=None) -> HttpResponse:
        data = self.export_csv_bytes(days=days)
        fname = f'tickets_{timezone.now().strftime("%Y%m%d")}.csv'
        response = HttpResponse(data, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{fname}"'
        return response

ticket_export_service = TicketExportService()