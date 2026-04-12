# =============================================================================
# promotions/account_manager/am_communication.py
# AM Communication — Ticket system between publisher and their AM
# =============================================================================
import uuid
from django.utils import timezone
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


class AMTicketSystem:
    """Simple ticket/message system between publisher and their AM."""
    TICKET_PREFIX = 'am_ticket:'
    INBOX_PREFIX = 'am_inbox:'

    def create_ticket(self, publisher_id: int, subject: str, message: str, priority: str = 'normal') -> dict:
        ticket_id = str(uuid.uuid4())[:8].upper()
        ticket = {
            'ticket_id': ticket_id,
            'publisher_id': publisher_id,
            'subject': subject,
            'messages': [
                {
                    'sender': 'publisher',
                    'message': message,
                    'sent_at': timezone.now().isoformat(),
                }
            ],
            'status': 'open',
            'priority': priority,
            'created_at': timezone.now().isoformat(),
        }
        cache.set(f'{self.TICKET_PREFIX}{ticket_id}', ticket, timeout=3600 * 24 * 90)
        # Add to publisher's inbox
        inbox = cache.get(f'{self.INBOX_PREFIX}{publisher_id}', [])
        inbox.insert(0, ticket_id)
        cache.set(f'{self.INBOX_PREFIX}{publisher_id}', inbox[:50], timeout=3600 * 24 * 90)
        return {
            'ticket_id': ticket_id,
            'status': 'open',
            'message': 'Ticket created. Your AM will respond within the SLA timeframe.',
            'estimated_response': '24 hours',
        }

    def reply_to_ticket(self, ticket_id: str, sender: str, message: str) -> dict:
        key = f'{self.TICKET_PREFIX}{ticket_id}'
        ticket = cache.get(key)
        if not ticket:
            return {'error': 'Ticket not found'}
        ticket['messages'].append({
            'sender': sender,
            'message': message,
            'sent_at': timezone.now().isoformat(),
        })
        if sender == 'am':
            ticket['status'] = 'replied'
        cache.set(key, ticket, timeout=3600 * 24 * 90)
        return {'success': True, 'ticket_id': ticket_id, 'status': ticket['status']}

    def get_publisher_tickets(self, publisher_id: int) -> list:
        inbox = cache.get(f'{self.INBOX_PREFIX}{publisher_id}', [])
        tickets = []
        for tid in inbox:
            t = cache.get(f'{self.TICKET_PREFIX}{tid}')
            if t:
                tickets.append({
                    'ticket_id': t['ticket_id'],
                    'subject': t['subject'],
                    'status': t['status'],
                    'created_at': t['created_at'],
                    'message_count': len(t.get('messages', [])),
                })
        return tickets

    def get_ticket_detail(self, ticket_id: str, publisher_id: int) -> dict:
        ticket = cache.get(f'{self.TICKET_PREFIX}{ticket_id}')
        if not ticket or ticket.get('publisher_id') != publisher_id:
            return {'error': 'Ticket not found'}
        return ticket


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_ticket_view(request):
    system = AMTicketSystem()
    result = system.create_ticket(
        publisher_id=request.user.id,
        subject=request.data.get('subject', ''),
        message=request.data.get('message', ''),
        priority=request.data.get('priority', 'normal'),
    )
    return Response(result, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_tickets_view(request):
    system = AMTicketSystem()
    tickets = system.get_publisher_tickets(request.user.id)
    return Response({'tickets': tickets})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reply_ticket_view(request, ticket_id):
    system = AMTicketSystem()
    result = system.reply_to_ticket(
        ticket_id=ticket_id,
        sender='publisher' if not request.user.is_staff else 'am',
        message=request.data.get('message', ''),
    )
    return Response(result)
