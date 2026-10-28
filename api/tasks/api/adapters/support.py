"""
api/adapters/support.py
Support adapter for earning backend platform
"""
from django.db.models import Q
import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, fields
from decimal import Decimal
from datetime import timedelta

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_support_tickets(request):
    """Get user's support tickets."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        status_filter = request.GET.get('status')  # 'all', 'open', 'closed', 'resolved'
        priority = request.GET.get('priority')  # 'all', 'low', 'medium', 'high', 'urgent'
        category = request.GET.get('category')
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get support tickets
        from support.models import SupportTicket
        queryset = SupportTicket.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).order_by('-created_at')
        
        # Apply filters
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)
        if priority and priority != 'all':
            queryset = queryset.filter(priority=priority)
        if category:
            queryset = queryset.filter(category=category)
        
        # Paginate
        tickets = queryset[offset:offset+limit]
        
        # Serialize tickets
        ticket_data = []
        for ticket in tickets:
            ticket_data.append({
                'id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'subject': ticket.subject,
                'description': ticket.description,
                'status': ticket.status,
                'priority': ticket.priority,
                'category': ticket.category,
                'created_at': ticket.created_at.isoformat(),
                'updated_at': ticket.updated_at.isoformat(),
                'assigned_to': {
                    'id': ticket.assigned_to.id,
                    'username': ticket.assigned_to.username,
                    'first_name': ticket.assigned_to.first_name,
                    'last_name': ticket.assigned_to.last_name,
                } if ticket.assigned_to else None,
                'last_reply_at': ticket.last_reply_at.isoformat() if ticket.last_reply_at else None,
                'response_time_hours': _calculate_response_time(ticket),
                'attachment_count': ticket.attachments.count(),
                'rating': ticket.rating,
                'feedback': ticket.feedback,
                'metadata': ticket.metadata
            })
        
        return Response({
            'success': True,
            'data': {
                'tickets': ticket_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(ticket_data) == limit
                },
                'filters': {
                    'status': status_filter,
                    'priority': priority,
                    'category': category
                },
                'summary': _get_ticket_summary(queryset)
            },
            'message': 'Support tickets retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[SupportAdapter] Error getting support tickets: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve support tickets',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_support_ticket(request):
    """Create a new support ticket."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        required_fields = ['subject', 'description', 'category']
        for field in required_fields:
            if field not in data:
                return Response({
                    'success': False,
                    'error': 'Missing required field',
                    'details': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create support ticket
        from support.models import SupportTicket
        ticket = SupportTicket.objects.create(
            user=user,
            ticket_number=_generate_ticket_number(tenant_id),
            subject=data['subject'],
            description=data['description'],
            category=data['category'],
            priority=data.get('priority', 'medium'),
            status='open',
            metadata=data.get('metadata', {}),
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Handle attachments if provided
        if 'attachments' in data:
            _handle_ticket_attachments(ticket, data['attachments'])
        
        # Emit ticket created event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('support.ticket_created', {
            'user_id': user.id,
            'ticket_id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'category': data['category'],
            'priority': data.get('priority', 'medium'),
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'ticket_id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'subject': ticket.subject,
                'status': ticket.status,
                'created_at': ticket.created_at.isoformat(),
                'estimated_response_time': _get_estimated_response_time(data.get('priority', 'medium'))
            },
            'message': 'Support ticket created successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[SupportAdapter] Error creating support ticket: {e}")
        return Response({
            'success': False,
            'error': 'Failed to create support ticket',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_ticket_details(request, ticket_id):
    """Get detailed support ticket information."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get ticket
        from support.models import SupportTicket
        try:
            ticket = SupportTicket.objects.get(
                id=ticket_id,
                user=user,
                tenant_id=tenant_id
            )
        except SupportTicket.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Ticket not found',
                'details': f'Support ticket with ID {ticket_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get ticket replies
        from support.models import TicketReply
        replies = TicketReply.objects.filter(
            ticket=ticket
        ).order_by('created_at')
        
        # Build detailed ticket data
        ticket_data = {
            'id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'subject': ticket.subject,
            'description': ticket.description,
            'status': ticket.status,
            'priority': ticket.priority,
            'category': ticket.category,
            'created_at': ticket.created_at.isoformat(),
            'updated_at': ticket.updated_at.isoformat(),
            'assigned_to': {
                'id': ticket.assigned_to.id,
                'username': ticket.assigned_to.username,
                'first_name': ticket.assigned_to.first_name,
                'last_name': ticket.assigned_to.last_name,
                'avatar': getattr(ticket.assigned_to, 'avatar', None),
            } if ticket.assigned_to else None,
            'last_reply_at': ticket.last_reply_at.isoformat() if ticket.last_reply_at else None,
            'response_time_hours': _calculate_response_time(ticket),
            'resolution_time_hours': _calculate_resolution_time(ticket),
            'attachments': [
                {
                    'id': attachment.id,
                    'filename': attachment.filename,
                    'file_url': attachment.file_url,
                    'file_size': attachment.file_size,
                    'mime_type': attachment.mime_type,
                    'uploaded_at': attachment.uploaded_at.isoformat(),
                }
                for attachment in ticket.attachments.all()
            ],
            'replies': [
                {
                    'id': reply.id,
                    'author': {
                        'id': reply.author.id,
                        'username': reply.author.username,
                        'first_name': reply.author.first_name,
                        'last_name': reply.author.last_name,
                        'is_staff': reply.author.is_staff,
                        'avatar': getattr(reply.author, 'avatar', None),
                    },
                    'message': reply.message,
                    'is_internal': reply.is_internal,
                    'created_at': reply.created_at.isoformat(),
                    'attachments': [
                        {
                            'id': attachment.id,
                            'filename': attachment.filename,
                            'file_url': attachment.file_url,
                            'file_size': attachment.file_size,
                            'mime_type': attachment.mime_type,
                            'uploaded_at': attachment.uploaded_at.isoformat(),
                        }
                        for attachment in reply.attachments.all()
                    ]
                }
                for reply in replies
            ],
            'rating': ticket.rating,
            'feedback': ticket.feedback,
            'metadata': ticket.metadata,
            'user_actions': _get_user_ticket_actions(user, ticket),
            'tenant_id': tenant_id
        }
        
        return Response({
            'success': True,
            'data': ticket_data,
            'message': 'Ticket details retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[SupportAdapter] Error getting ticket details: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve ticket details',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_ticket_reply(request, ticket_id):
    """Add reply to support ticket."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        if 'message' not in data:
            return Response({
                'success': False,
                'error': 'Message required',
                'details': 'Please provide a message for the reply'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get ticket
        from support.models import SupportTicket
        try:
            ticket = SupportTicket.objects.get(
                id=ticket_id,
                user=user,
                tenant_id=tenant_id
            )
        except SupportTicket.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Ticket not found',
                'details': f'Support ticket with ID {ticket_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if ticket is open
        if ticket.status in ['closed', 'resolved']:
            return Response({
                'success': False,
                'error': 'Ticket is closed',
                'details': 'Cannot add reply to closed ticket'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create reply
        from support.models import TicketReply
        reply = TicketReply.objects.create(
            ticket=ticket,
            author=user,
            message=data['message'],
            is_internal=data.get('is_internal', False),
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Handle attachments if provided
        if 'attachments' in data:
            _handle_reply_attachments(reply, data['attachments'])
        
        # Update ticket
        ticket.last_reply_at = timezone.now()
        ticket.updated_at = timezone.now()
        ticket.save()
        
        # Emit reply added event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('support.reply_added', {
            'user_id': user.id,
            'ticket_id': ticket_id,
            'reply_id': reply.id,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'reply_id': reply.id,
                'ticket_id': ticket_id,
                'message': data['message'],
                'created_at': reply.created_at.isoformat(),
                'is_internal': reply.is_internal
            },
            'message': 'Reply added successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[SupportAdapter] Error adding ticket reply: {e}")
        return Response({
            'success': False,
            'error': 'Failed to add ticket reply',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rate_ticket(request, ticket_id):
    """Rate support ticket."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        rating = data.get('rating')
        feedback = data.get('feedback', '')
        
        if not rating or rating not in [1, 2, 3, 4, 5]:
            return Response({
                'success': False,
                'error': 'Valid rating required',
                'details': 'Please provide a rating between 1 and 5'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get ticket
        from support.models import SupportTicket
        try:
            ticket = SupportTicket.objects.get(
                id=ticket_id,
                user=user,
                tenant_id=tenant_id
            )
        except SupportTicket.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Ticket not found',
                'details': f'Support ticket with ID {ticket_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user can rate this ticket
        if not _can_rate_ticket(user, ticket):
            return Response({
                'success': False,
                'error': 'Cannot rate this ticket',
                'details': 'You can only rate tickets you created'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update ticket rating
        ticket.rating = rating
        ticket.feedback = feedback
        ticket.save()
        
        # Emit ticket rated event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('support.ticket_rated', {
            'user_id': user.id,
            'ticket_id': ticket_id,
            'rating': rating,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'ticket_id': ticket_id,
                'rating': rating,
                'feedback': feedback,
                'rated_at': timezone.now().isoformat()
            },
            'message': 'Ticket rated successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[SupportAdapter] Error rating ticket: {e}")
        return Response({
            'success': False,
            'error': 'Failed to rate ticket',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_support_analytics(request):
    """Get support analytics for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get support analytics
        from support.models import SupportTicket
        tickets = SupportTicket.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        )
        
        # Calculate analytics
        analytics_data = {
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'ticket_metrics': {
                'total_tickets': tickets.count(),
                'open_tickets': tickets.filter(status='open').count(),
                'closed_tickets': tickets.filter(status='closed').count(),
                'resolved_tickets': tickets.filter(status='resolved').count(),
                'average_resolution_time': tickets.filter(
                    status='resolved'
                ).aggregate(
                    avg_time=Avg(F('resolved_at') - F('created_at'))
                )['avg_time'].total_seconds() / 3600 if tickets.filter(status='resolved').exists() else 0,
                'average_response_time': tickets.aggregate(
                    avg_response=Avg(F('last_reply_at') - F('created_at'))
                )['avg_response'].total_seconds() / 3600 if tickets.exists() else 0,
                'satisfaction_rating': tickets.filter(
                    rating__isnull=False
                ).aggregate(
                    avg_rating=Avg('rating')
                )['avg_rating'] or 0,
            },
            'category_breakdown': list(tickets.values('category').annotate(
                count=Count('id'),
                avg_resolution_time=Avg(F('resolved_at') - F('created_at'))
            ).order_by('-count')),
            'priority_breakdown': list(tickets.values('priority').annotate(
                count=Count('id'),
                avg_resolution_time=Avg(F('resolved_at') - F('created_at'))
            ).order_by('-count')),
            'daily_trends': _get_daily_ticket_trends(tickets, days),
            'top_agents': _get_top_agents(tickets, days),
            'user_satisfaction': _get_user_satisfaction(tickets, days)
        }
        
        return Response({
            'success': True,
            'data': analytics_data,
            'message': 'Support analytics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[SupportAdapter] Error getting support analytics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve support analytics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper functions
def _generate_ticket_number(tenant_id) -> str:
    """Generate unique ticket number."""
    try:
        # Get last ticket number
        from support.models import SupportTicket
        last_ticket = SupportTicket.objects.filter(
            tenant_id=tenant_id
        ).order_by('-ticket_number').first()
        
        # Generate next number
        if last_ticket and last_ticket.ticket_number:
            last_number = int(last_ticket.ticket_number.split('-')[-1])
            next_number = last_number + 1
        else:
            next_number = 1
        
        return f"TK-{tenant_id}-{next_number:06d}"
    except Exception:
        return f"TK-{tenant_id}-000001"


def _calculate_response_time(ticket) -> float:
    """Calculate response time in hours."""
    try:
        if ticket.last_reply_at:
            return (ticket.last_reply_at - ticket.created_at).total_seconds() / 3600
        return 0.0
    except Exception:
        return 0.0


def _calculate_resolution_time(ticket) -> float:
    """Calculate resolution time in hours."""
    try:
        if ticket.status == 'resolved' and ticket.resolved_at:
            return (ticket.resolved_at - ticket.created_at).total_seconds() / 3600
        return 0.0
    except Exception:
        return 0.0


def _get_ticket_summary(queryset) -> Dict:
    """Get ticket summary statistics."""
    try:
        total_tickets = queryset.count()
        open_tickets = queryset.filter(status='open').count()
        closed_tickets = queryset.filter(status='closed').count()
        resolved_tickets = queryset.filter(status='resolved').count()
        
        return {
            'total_tickets': total_tickets,
            'open_tickets': open_tickets,
            'closed_tickets': closed_tickets,
            'resolved_tickets': resolved_tickets,
            'resolution_rate': round((resolved_tickets / max(total_tickets, 1)) * 100, 2),
            'open_percentage': round((open_tickets / max(total_tickets, 1)) * 100, 2),
            'urgent_tickets': queryset.filter(priority='urgent').count(),
            'high_priority_tickets': queryset.filter(priority='high').count()
        }
    except Exception:
        return {}


def _get_user_ticket_actions(user, ticket) -> List[str]:
    """Get available actions for user on ticket."""
    actions = []
    
    if ticket.user.id == user.id:
        actions.extend(['view', 'reply', 'rate', 'close'])
    
    if user.is_staff:
        actions.extend(['assign', 'reassign', 'escalate', 'mark_internal'])
    
    return actions


def _can_rate_ticket(user, ticket) -> bool:
    """Check if user can rate ticket."""
    return ticket.user.id == user.id and ticket.status in ['closed', 'resolved']


def _handle_ticket_attachments(ticket, attachments):
    """Handle ticket attachments."""
    try:
        from support.models import TicketAttachment
        for attachment_data in attachments:
            TicketAttachment.objects.create(
                ticket=ticket,
                filename=attachment_data.get('filename', ''),
                file_url=attachment_data.get('file_url', ''),
                file_size=attachment_data.get('file_size', 0),
                mime_type=attachment_data.get('mime_type', 'application/octet-stream'),
                uploaded_at=timezone.now()
            )
    except Exception:
        pass


def _handle_reply_attachments(reply, attachments):
    """Handle reply attachments."""
    try:
        from support.models import ReplyAttachment
        for attachment_data in attachments:
            ReplyAttachment.objects.create(
                reply=reply,
                filename=attachment_data.get('filename', ''),
                file_url=attachment_data.get('file_url', ''),
                file_size=attachment_data.get('file_size', 0),
                mime_type=attachment_data.get('mime_type', 'application/octet-stream'),
                uploaded_at=timezone.now()
            )
    except Exception:
        pass


def _get_estimated_response_time(priority) -> str:
    """Get estimated response time based on priority."""
    response_times = {
        'urgent': '1-2 hours',
        'high': '4-8 hours',
        'medium': '12-24 hours',
        'low': '24-48 hours'
    }
    return response_times.get(priority, '24-48 hours')


def _get_daily_ticket_trends(tickets, days) -> List[Dict]:
    """Get daily ticket trends."""
    try:
        from django.db.models import TruncDay
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_trends = tickets.filter(
            created_at__gte=start_date
        ).extra({
            'day': 'date(created_at)'
        }).values('day').annotate(
            new_tickets=Count('id', filter=Q(status='open')),
            resolved_tickets=Count('id', filter=Q(status='resolved'))
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'new_tickets': trend['new_tickets'],
                'resolved_tickets': trend['resolved_tickets']
            }
            for trend in daily_trends
        ]
    except Exception:
        return []


def _get_top_agents(tickets, days) -> List[Dict]:
    """Get top performing support agents."""
    try:
        from django.utils import timezone
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        # Get agents with ticket counts
        from support.models import SupportTicket
        agents = tickets.filter(
            created_at__gte=start_date,
            assigned_to__isnull=False,
            status='resolved'
        ).values('assigned_to__username', 'assigned_to__first_name', 'assigned_to__last_name').annotate(
            resolved_tickets=Count('id'),
            avg_resolution_time=Avg(F('resolved_at') - F('created_at'))
        ).order_by('-resolved_tickets')[:10]
        
        return [
            {
                'username': agent['assigned_to__username'],
                'name': f"{agent['assigned_to__first_name']} {agent['assigned_to__last_name']}",
                'resolved_tickets': agent['resolved_tickets'],
                'avg_resolution_time_hours': agent['avg_resolution_time'].total_seconds() / 3600 if agent['avg_resolution_time'] else 0
            }
            for agent in agents
        ]
    except Exception:
        return []


def _get_user_satisfaction(tickets, days) -> Dict:
    """Get user satisfaction metrics."""
    try:
        from django.utils import timezone
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        # Get rated tickets
        rated_tickets = tickets.filter(
            created_at__gte=start_date,
            rating__isnull=False
        )
        
        if not rated_tickets.exists():
            return {
                'average_rating': 0,
                'total_rated_tickets': 0,
                'rating_distribution': {}
            }
        
        # Calculate satisfaction metrics
        total_rated = rated_tickets.count()
        avg_rating = rated_tickets.aggregate(
            avg_rating=Avg('rating')
        )['avg_rating'] or 0
        
        # Rating distribution
        rating_dist = rated_tickets.values('rating').annotate(
            count=Count('id')
        ).order_by('rating')
        
        return {
            'average_rating': round(avg_rating, 2),
            'total_rated_tickets': total_rated,
            'rating_distribution': {
                str(rating['rating']): rating['count']
                for rating in rating_dist
            }
        }
    except Exception:
        return {
            'average_rating': 0,
            'total_rated_tickets': 0,
            'rating_distribution': {}
        }
