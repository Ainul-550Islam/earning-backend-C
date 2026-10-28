"""
api/support/portal/ticket_history_view.py
FILE 39/70 — Full Ticket History Timeline

Ticket-এর complete audit trail — visual timeline।
User দেখবে: created → assigned → replied → resolved।
Agent দেখবে: সব status change, internal notes বাদে।
"""
import logging
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ticket_timeline(request, ticket_id):
    """
    GET /support/portal/tickets/{ticket_id}/timeline/
    Complete ticket history as timeline events
    """
    from api.support.models import SupportTicket, TicketMessage, TicketAttachment
    from api.support.permissions import IsSupportAgent

    is_agent = IsSupportAgent().has_permission(request, None) or request.user.is_staff

    try:
        if is_agent:
            ticket = SupportTicket.objects.get(ticket_id=ticket_id)
        else:
            ticket = SupportTicket.objects.get(ticket_id=ticket_id, user=request.user)
    except SupportTicket.DoesNotExist:
        return Response({'error': 'Ticket not found.'}, status=404)

    events = []

    # 1. Ticket Created
    events.append({
        'type':      'created',
        'icon':      '🎫',
        'title':     'Ticket Created',
        'detail':    f'Ticket #{ticket.ticket_id} created with {ticket.priority} priority.',
        'actor':     ticket.user.username,
        'actor_type':'user',
        'timestamp': ticket.created_at.isoformat(),
        'color':     '#6366f1',
    })

    # 2. Assignment
    if ticket.assigned_to:
        events.append({
            'type':      'assigned',
            'icon':      '👤',
            'title':     'Agent Assigned',
            'detail':    f'Assigned to {ticket.assigned_to.username}.',
            'actor':     'System',
            'actor_type':'system',
            'timestamp': ticket.created_at.isoformat(),
            'color':     '#0ea5e9',
        })

    # 3. Messages
    msg_qs = TicketMessage.objects.filter(ticket=ticket).order_by('created_at')
    if not is_agent:
        msg_qs = msg_qs.filter(is_internal=False)

    for msg in msg_qs:
        event_type = 'agent_reply' if msg.is_agent else 'user_reply'
        if msg.is_internal:
            event_type = 'internal_note'

        events.append({
            'type':      event_type,
            'icon':      '💬' if not msg.is_internal else '📝',
            'title':     'Support Team Replied' if msg.is_agent else 'You Replied',
            'detail':    msg.content[:200] + ('...' if len(msg.content) > 200 else ''),
            'actor':     msg.sender.username if msg.sender else 'Unknown',
            'actor_type':'agent' if msg.is_agent else 'user',
            'is_internal':msg.is_internal,
            'timestamp': msg.created_at.isoformat(),
            'color':     '#16a34a' if msg.is_agent else '#6366f1',
        })

    # 4. Attachments
    for att in TicketAttachment.objects.filter(ticket=ticket).order_by('created_at'):
        events.append({
            'type':      'attachment',
            'icon':      '📎',
            'title':     'File Attached',
            'detail':    f'{att.filename} ({att.size_mb}MB)',
            'actor':     att.uploaded_by.username,
            'actor_type':'user',
            'timestamp': att.created_at.isoformat(),
            'color':     '#ca8a04',
        })

    # 5. Resolution
    if ticket.resolved_at:
        events.append({
            'type':      'resolved',
            'icon':      '✅',
            'title':     'Ticket Resolved',
            'detail':    ticket.admin_response[:200] if ticket.admin_response else 'Issue resolved.',
            'actor':     ticket.assigned_to.username if ticket.assigned_to else 'Support Team',
            'actor_type':'agent',
            'timestamp': ticket.resolved_at.isoformat(),
            'color':     '#16a34a',
        })

    # 6. Rating
    if ticket.rated_at:
        stars = '⭐' * (ticket.satisfaction_rating or 0)
        events.append({
            'type':      'rated',
            'icon':      '⭐',
            'title':     'Experience Rated',
            'detail':    f'{stars} {ticket.rating_comment[:100] if ticket.rating_comment else ""}',
            'actor':     ticket.user.username,
            'actor_type':'user',
            'timestamp': ticket.rated_at.isoformat(),
            'color':     '#f59e0b',
        })

    # 7. Escalation
    if ticket.escalated_at:
        events.append({
            'type':      'escalated',
            'icon':      '🚨',
            'title':     'Ticket Escalated',
            'detail':    'This ticket was escalated for priority handling.',
            'actor':     'System',
            'actor_type':'system',
            'timestamp': ticket.escalated_at.isoformat(),
            'color':     '#dc2626',
        })

    # Sort by timestamp
    events.sort(key=lambda x: x['timestamp'])

    # Timeline summary
    total_time = None
    if ticket.resolved_at:
        diff       = (ticket.resolved_at - ticket.created_at).total_seconds() / 3600
        total_time = f'{round(diff, 1)} hours'

    return Response({
        'success':      True,
        'ticket_id':    ticket_id,
        'timeline':     events,
        'event_count':  len(events),
        'total_time':   total_time,
        'status':       ticket.status,
    })
@permission_classes([IsAuthenticated])
def user_full_history(request):
    """
    GET /support/portal/history/
    User-এর complete support history
    """
    from api.support.models import SupportTicket, TicketRating
    from django.db.models import Avg, Count

    user    = request.user
    tickets = SupportTicket.objects.filter(user=user).order_by('-created_at')

    # Stats
    stats = {
        'total':    tickets.count(),
        'resolved': tickets.filter(status='resolved').count(),
        'closed':   tickets.filter(status='closed').count(),
        'open':     tickets.filter(status__in=['open','in_progress','waiting_user']).count(),
    }

    # Rating history
    ratings = list(
        TicketRating.objects.filter(user=user)
        .order_by('-created_at')
        .values('ticket__ticket_id', 'rating', 'comment', 'created_at')[:20]
    )

    avg_rating = TicketRating.objects.filter(user=user).aggregate(avg=Avg('rating'))['avg'] or 0

    return Response({
        'success':      True,
        'stats':        stats,
        'avg_csat':     round(avg_rating, 1),
        'ratings':      ratings,
        'recent':       list(tickets.values(
            'ticket_id', 'subject', 'status', 'priority', 'created_at', 'resolved_at'
        )[:20]),
    })