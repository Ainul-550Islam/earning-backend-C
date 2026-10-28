# api/support/viewsets/TicketViewSet.py  — WORLD #1
import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger(__name__)


class TicketViewSet(viewsets.ModelViewSet):
    """
    Full ticket CRUD + thread + attachments + rating + merge actions.
    GET    /api/support/tickets/             — list
    POST   /api/support/tickets/             — create
    GET    /api/support/tickets/{id}/        — detail with thread
    PATCH  /api/support/tickets/{id}/        — update
    DELETE /api/support/tickets/{id}/        — delete
    POST   /api/support/tickets/{id}/reply/       — add message
    POST   /api/support/tickets/{id}/resolve/     — resolve
    POST   /api/support/tickets/{id}/close/       — close
    POST   /api/support/tickets/{id}/rate/        — CSAT rating
    POST   /api/support/tickets/{id}/assign/      — assign agent
    POST   /api/support/tickets/{id}/escalate/    — escalate
    POST   /api/support/tickets/{id}/merge/       — merge into another
    GET    /api/support/tickets/{id}/sla/         — SLA status
    GET    /api/support/tickets/stats/             — dashboard stats
    GET    /api/support/tickets/export/            — CSV export
    """
    permission_classes  = [IsAuthenticated]
    parser_classes      = [MultiPartParser, FormParser, JSONParser]
    filter_backends     = [filters.OrderingFilter]
    ordering_fields     = ['created_at', 'updated_at', 'priority']
    ordering            = ['-created_at']

    def get_queryset(self):
        from api.support.models import SupportTicket
        from api.support.filters import TicketFilter
        if self.request.user.is_staff:
            qs = SupportTicket.objects.select_related('user', 'assigned_to').prefetch_related('ticket_tags__tag', 'sla')
        else:
            qs = SupportTicket.objects.filter(user=self.request.user)
        # Assigned to me
        if self.request.query_params.get('assigned_to') == 'me':
            qs = qs.filter(assigned_to=self.request.user)
        return TicketFilter.apply(qs, self.request.query_params)

    def get_serializer_class(self):
        from api.support.serializers import SupportTicketSerializer, SupportTicketListSerializer, SupportTicketCreateSerializer
        if self.action == 'list':
            return SupportTicketListSerializer
        if self.action == 'create':
            return SupportTicketCreateSerializer
        return SupportTicketSerializer

    def perform_create(self, serializer):
        from api.support.services import ticket_service
        ticket = ticket_service.create(
            user=self.request.user,
            data={**serializer.validated_data, 'channel': self.request.data.get('channel','web')},
        )
        serializer.instance = ticket

    def create(self, request, *args, **kwargs):
        from api.support.services import ticket_service
        from api.support.serializers import SupportTicketSerializer
        from api.support.validators import validate_ticket_subject, validate_ticket_description
        subject = request.data.get('subject','')
        description = request.data.get('description','')
        try:
            validate_ticket_subject(subject)
            validate_ticket_description(description)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
        ticket = ticket_service.create(user=request.user, data=dict(request.data))
        return Response(SupportTicketSerializer(ticket, context={'request':request}).data, status=201)

    def retrieve(self, request, *args, **kwargs):
        from api.support.serializers import SupportTicketSerializer
        ticket = self.get_object()
        return Response(SupportTicketSerializer(ticket, context={'request':request}).data)

    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        from api.support.services import ticket_service
        from api.support.serializers import TicketMessageSerializer
        ticket = self.get_object()
        content = request.data.get('content','').strip()
        if not content:
            return Response({'error': 'content required.'}, status=400)
        is_agent = request.user.is_staff
        msg = ticket_service.add_message(str(ticket.ticket_id), request.user, content, is_agent)
        return Response(TicketMessageSerializer(msg).data, status=201)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def resolve(self, request, pk=None):
        from api.support.services import ticket_service
        ticket = ticket_service.resolve(pk, request.user, request.data.get('resolution',''))
        return Response({'success': True, 'ticket_id': ticket.ticket_id})

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        from api.support.services import ticket_service
        ticket = ticket_service.close(pk, request.user)
        return Response({'success': True, 'ticket_id': ticket.ticket_id})

    @action(detail=True, methods=['post'])
    def rate(self, request, pk=None):
        ticket = self.get_object()
        if ticket.user != request.user:
            return Response({'detail': 'Not your ticket.'}, status=403)
        score = request.data.get('score') or request.data.get('rating')
        if not score or not 1 <= int(score) <= 5:
            return Response({'error': 'score 1-5 required.'}, status=400)
        ticket.satisfaction_rating = int(score)
        ticket.rating_comment = request.data.get('comment','')
        ticket.rated_at = timezone.now()
        ticket.save(update_fields=['satisfaction_rating','rating_comment','rated_at'])
        # Create TicketRating record
        try:
            from api.support.models import TicketRating
            TicketRating.objects.update_or_create(
                ticket=ticket, defaults={'user':request.user,'score':int(score),'review_text':ticket.rating_comment}
            )
        except Exception:
            pass
        return Response({'success': True, 'message': '⭐ Thank you for your feedback!'})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def assign(self, request, pk=None):
        from api.support.services.ticket.TicketAssignmentService import ticket_assignment_service
        ticket = self.get_object()
        agent_id = request.data.get('agent_id')
        result = ticket_assignment_service.assign(ticket, agent_id, assigned_by=request.user)
        return Response(result)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def escalate(self, request, pk=None):
        ticket = self.get_object()
        if ticket.escalated:
            return Response({'detail': 'Already escalated.'}, status=400)
        ticket.escalated = True
        ticket.escalated_at = timezone.now()
        ticket.priority = 'urgent'
        ticket.save(update_fields=['escalated','escalated_at','priority'])
        logger.info(f'Ticket {ticket.ticket_id} escalated by {request.user.username}')
        return Response({'success': True, 'ticket_id': ticket.ticket_id})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def merge(self, request, pk=None):
        from api.support.services.ticket.TicketMergeService import ticket_merge_service
        ticket = self.get_object()
        target_id = request.data.get('target_ticket_id')
        if not target_id:
            return Response({'error': 'target_ticket_id required.'}, status=400)
        result = ticket_merge_service.merge(ticket, target_id, merged_by=request.user, reason=request.data.get('reason',''))
        return Response(result)

    @action(detail=True, methods=['get'])
    def sla(self, request, pk=None):
        from api.support.serializers import TicketSLASerializer
        ticket = self.get_object()
        try:
            return Response(TicketSLASerializer(ticket.sla).data)
        except Exception:
            return Response({'detail': 'No SLA record found.'}, status=404)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsAdminUser])
    def stats(self, request):
        from api.support.services import ticket_service
        return Response(ticket_service.get_stats())

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsAdminUser])
    def export(self, request):
        from api.support.services.ticket.TicketExportService import ticket_export_service
        fmt = request.query_params.get('format','csv')
        days = int(request.query_params.get('days', 30))
        return ticket_export_service.export_response(days=days, fmt=fmt, request=request)