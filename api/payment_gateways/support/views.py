# api/payment_gateways/support/views.py
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from core.views import BaseViewSet
from .models import SupportTicket, TicketMessage
from .serializers import (
    SupportTicketListSerializer, SupportTicketDetailSerializer,
    CreateTicketSerializer, ReplyTicketSerializer, TicketMessageSerializer,
)


class SupportTicketViewSet(BaseViewSet):
    """
    Full support ticket system for publishers and advertisers.

    Endpoints:
        POST   /support/tickets/           — Create new ticket
        GET    /support/tickets/           — List user's tickets
        GET    /support/tickets/{id}/      — Ticket detail
        POST   /support/tickets/{id}/reply/ — Reply to ticket
        POST   /support/tickets/{id}/resolve/ — Admin: resolve ticket
        GET    /support/tickets/my_open/   — Open tickets for current user
        GET    /support/tickets/{id}/messages/ — All messages
    """
    queryset           = SupportTicket.objects.all().order_by('-created_at')
    serializer_class   = SupportTicketListSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ('retrieve', 'messages'):
            return SupportTicketDetailSerializer
        if self.action == 'create':
            return CreateTicketSerializer
        return SupportTicketListSerializer

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        """Get full ticket detail including all messages."""
        ticket = self.get_object()
        data   = SupportTicketDetailSerializer(ticket).data
        return self.success_response(data=data)

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """Get all messages for a ticket."""
        ticket = self.get_object()
        msgs   = ticket.messages.all().order_by('created_at')
        return self.success_response(
            data=TicketMessageSerializer(msgs, many=True).data
        )

    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        """
        Add a reply to a support ticket.
        Updates status to 'in_progress' if admin replies to open ticket.
        """
        ticket = self.get_object()

        s = ReplyTicketSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        msg = TicketMessage.objects.create(
            ticket         = ticket,
            sender         = request.user,
            message        = s.validated_data['message'],
            is_staff       = request.user.is_staff,
            attachment_url = s.validated_data.get('attachment_url', ''),
        )

        # Update ticket status
        if ticket.status == 'open' and request.user.is_staff:
            ticket.status     = 'in_progress'
            ticket.assigned_to= request.user
            ticket.save(update_fields=['status', 'assigned_to'])
        elif ticket.status == 'resolved' and not request.user.is_staff:
            # User replied to resolved ticket — reopen
            ticket.status = 'open'
            ticket.save(update_fields=['status'])

        return self.success_response(
            data=TicketMessageSerializer(msg).data,
            message='Reply added successfully.'
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def resolve(self, request, pk=None):
        """Admin: mark ticket as resolved."""
        ticket             = self.get_object()
        ticket.status      = 'resolved'
        ticket.resolved_at = timezone.now()
        ticket.assigned_to = request.user
        ticket.save(update_fields=['status', 'resolved_at', 'assigned_to'])

        # Add a resolution message if provided
        resolution_note = request.data.get('resolution_note', '')
        if resolution_note:
            TicketMessage.objects.create(
                ticket   = ticket,
                sender   = request.user,
                message  = resolution_note,
                is_staff = True,
            )

        return self.success_response(
            message=f'Ticket {ticket.ticket_number} resolved.'
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def assign(self, request, pk=None):
        """Admin: assign ticket to a staff member."""
        from django.contrib.auth import get_user_model
        User        = get_user_model()
        ticket      = self.get_object()
        assignee_id = request.data.get('assignee_id')

        try:
            assignee          = User.objects.get(id=assignee_id, is_staff=True)
            ticket.assigned_to= assignee
            ticket.status     = 'in_progress'
            ticket.save(update_fields=['assigned_to', 'status'])
            return self.success_response(
                message=f'Ticket assigned to {assignee.get_full_name() or assignee.username}'
            )
        except User.DoesNotExist:
            return self.error_response(message='Staff member not found.', status_code=404)

    @action(detail=False, methods=['get'])
    def my_open(self, request):
        """Get current user's open/in-progress tickets."""
        qs = self.get_queryset().filter(status__in=['open', 'in_progress'])
        return self.success_response(
            data=SupportTicketListSerializer(qs, many=True).data
        )

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def pending_queue(self, request):
        """Admin: all unassigned open tickets ordered by priority."""
        PRIORITY_ORDER = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}
        qs = SupportTicket.objects.filter(
            status__in=['open'], assigned_to__isnull=True
        ).order_by('created_at')
        sorted_qs = sorted(qs, key=lambda t: PRIORITY_ORDER.get(t.priority, 99))
        return self.success_response(
            data=SupportTicketListSerializer(sorted_qs, many=True).data
        )

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Ticket statistics — for admin dashboard."""
        from django.db.models import Count
        if not request.user.is_staff:
            total     = self.get_queryset().count()
            open_count= self.get_queryset().filter(status='open').count()
            return self.success_response(data={
                'total': total, 'open': open_count,
            })

        by_status = SupportTicket.objects.values('status').annotate(count=Count('id'))
        by_priority = SupportTicket.objects.filter(
            status__in=['open', 'in_progress']
        ).values('priority').annotate(count=Count('id'))

        return self.success_response(data={
            'by_status':   {s['status']: s['count'] for s in by_status},
            'by_priority': {p['priority']: p['count'] for p in by_priority},
        })
