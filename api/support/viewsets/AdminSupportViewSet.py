# api/support/viewsets/AdminSupportViewSet.py  — WORLD #1
"""Superadmin overview, bulk ops, system health."""
import logging
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class AdminSupportViewSet(ViewSet):
    """
    GET  /api/support/admin/overview/      — full system overview
    POST /api/support/admin/bulk-assign/   — bulk assign tickets
    POST /api/support/admin/bulk-close/    — bulk close resolved tickets
    POST /api/support/admin/run-sla-check/ — manual SLA check
    GET  /api/support/admin/health/        — system health
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        from api.support.models import SupportTicket, SupportAgent, LiveChatSession
        from api.support.services import ticket_service
        stats = ticket_service.get_stats()
        stats['agents_available'] = SupportAgent.objects.filter(is_active=True, is_available=True).count()
        stats['agents_total']     = SupportAgent.objects.filter(is_active=True).count()
        stats['active_chats']     = LiveChatSession.objects.filter(status='active').count() if hasattr(LiveChatSession, 'status') else 0
        return Response(stats)

    @action(detail=False, methods=['post'], url_path='bulk-assign')
    def bulk_assign(self, request):
        from api.support.models import SupportTicket
        ticket_ids = request.data.get('ticket_ids', [])
        agent_id   = request.data.get('agent_id')
        if not ticket_ids or not agent_id:
            return Response({'error': 'ticket_ids and agent_id required.'}, status=400)
        updated = SupportTicket.objects.filter(id__in=ticket_ids).update(assigned_to_id=agent_id)
        return Response({'success': True, 'updated': updated})

    @action(detail=False, methods=['post'], url_path='bulk-close')
    def bulk_close(self, request):
        from api.support.models import SupportTicket
        cutoff = timezone.now() - timedelta(days=int(request.data.get('older_than_days', 30)))
        tickets = SupportTicket.objects.filter(status='resolved', resolved_at__lte=cutoff)
        count = tickets.count()
        tickets.update(status='closed')
        return Response({'success': True, 'closed': count})

    @action(detail=False, methods=['post'], url_path='run-sla-check')
    def run_sla_check(self, request):
        from api.support.services import sla_service
        result = sla_service.check_breaches()
        return Response({'success': True, 'result': result})

    @action(detail=False, methods=['get'])
    def health(self, request):
        from api.support.models import SupportSettings, SupportAgent
        obj, _ = SupportSettings.objects.get_or_create(id=1)
        return Response({
            'support_online':  obj.is_support_online,
            'maintenance':     obj.maintenance_mode,
            'agents_online':   SupportAgent.objects.filter(is_active=True, is_available=True).count(),
            'timestamp':       timezone.now().isoformat(),
        })