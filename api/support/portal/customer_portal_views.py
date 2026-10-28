"""
api/support/portal/customer_portal_views.py
FILE 36/70 — Customer Self-Service Portal

User নিজেই সব support history দেখতে পারবে।
Ticket create, track, reply, rate — সব এক জায়গায়।
KB search before ticket creation।

Endpoints:
    GET  /support/portal/                    — Portal home
    GET  /support/portal/tickets/            — My tickets
    GET  /support/portal/tickets/{id}/       — Ticket detail + thread
    POST /support/portal/tickets/            — Create ticket
    POST /support/portal/tickets/{id}/reply/ — Reply
    POST /support/portal/tickets/{id}/rate/  — Rate
    GET  /support/portal/kb/                 — Knowledge base
    GET  /support/portal/kb/search/          — KB search
    GET  /support/portal/profile/            — User support profile
    GET  /support/portal/stats/              — My stats
"""
import logging
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
# PORTAL HOME
# ══════════════════════════════════════════════════════

@api_view(['GET'])
@api_view(['POST'])
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def portal_home(request):
    """
    GET /support/portal/
    User portal home — summary of everything
    """
    user = request.user

    # Open tickets
    from api.support.models import SupportTicket
    open_tickets = SupportTicket.objects.filter(
        user   = user,
        status__in = ['open', 'in_progress', 'waiting_user'],
    ).count()

    # Recent tickets
    recent = list(
        SupportTicket.objects.filter(user=user)
        .order_by('-created_at')
        .values('ticket_id', 'subject', 'status', 'priority', 'created_at', 'updated_at')[:5]
    )

    # Waiting for user reply
    waiting = SupportTicket.objects.filter(user=user, status='waiting_user').count()

    # Suggested KB articles
    kb_suggestions = []
    if open_tickets > 0:
        last_ticket = SupportTicket.objects.filter(user=user).order_by('-created_at').first()
        if last_ticket:
            try:
                from api.support.services.knowledge_base.KBRecommendService import kb_recommend_service
                kb_suggestions = kb_recommend_service.suggest_for_ticket(
                    last_ticket.subject, last_ticket.category, limit=3
                )
            except Exception:
                pass

    # Support status
    from api.support.models import SupportSettings, SupportAgent
    support_online = SupportAgent.objects.filter(is_active=True, is_available=True).exists()

    return Response({
        'success':        True,
        'user':           request.user.username,
        'open_tickets':   open_tickets,
        'waiting_reply':  waiting,
        'recent_tickets': recent,
        'kb_suggestions': kb_suggestions,
        'support_online': support_online,
        'welcome_msg':    f'Welcome back, {user.username}! How can we help you today?',
    })


# ══════════════════════════════════════════════════════
# MY TICKETS
# ══════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def portal_tickets(request):
    """
    GET  /support/portal/tickets/ — list my tickets
    POST /support/portal/tickets/ — create new ticket
    """
    if request.method == 'GET':
        return _list_my_tickets(request)
    return _create_ticket(request)


def _list_my_tickets(request):
    from api.support.models import SupportTicket
    from api.support.serializers.ticket_serializers import SupportTicketListSerializer

    filters = {}
    if request.query_params.get('status'):
        filters['status'] = request.query_params.get('status')
    if request.query_params.get('category'):
        filters['category'] = request.query_params.get('category')

    qs = SupportTicket.objects.filter(user=request.user)
    if filters:
        qs = qs.filter(**filters)
    qs = qs.order_by('-created_at')

    # Pagination
    page     = int(request.query_params.get('page', 1))
    per_page = int(request.query_params.get('per_page', 10))
    start    = (page - 1) * per_page
    end      = start + per_page
    total    = qs.count()

    tickets = SupportTicketListSerializer(qs[start:end], many=True).data

    return Response({
        'success':    True,
        'tickets':    tickets,
        'total':      total,
        'page':       page,
        'per_page':   per_page,
        'has_next':   end < total,
        'has_prev':   page > 1,
        'stats': {
            'open':     qs.filter(status__in=['open','in_progress','waiting_user']).count(),
            'resolved': qs.filter(status='resolved').count(),
            'closed':   qs.filter(status='closed').count(),
        }
    })


def _create_ticket(request):
    from api.support.services.ticket.TicketService import ticket_service  # noqa
    from api.support.services.knowledge_base.KBRecommendService import kb_recommend_service

    subject     = request.data.get('subject', '').strip()
    description = request.data.get('description', '').strip()
    category    = request.data.get('category', 'other')

    if not subject or len(subject) < 5:
        return Response({'error': 'Subject must be at least 5 characters.'}, status=400)
    if not description or len(description) < 10:
        return Response({'error': 'Description must be at least 10 characters.'}, status=400)

    # Suggest KB before creating
    suggestions = kb_recommend_service.suggest_for_ticket(subject, category, limit=3)
    if suggestions and request.data.get('check_kb_first'):
        return Response({
            'success':           False,
            'kb_suggestions':    suggestions,
            'message':           'These articles might help. Create ticket anyway?',
            'require_confirm':   True,
        })

    try:
        ticket = ticket_service.create(request.user, {
            'category':    category,
            'subject':     subject,
            'description': description,
            'priority':    request.data.get('priority', ''),
            'channel':     'web',
        })

        # AI classify
        try:
            from api.support.ai.ai_ticket_classifier import ai_classifier
            ai_classifier.classify(ticket)
        except Exception:
            pass

        return Response({
            'success':           True,
            'ticket_id':         ticket.ticket_id,
            'priority':          ticket.priority,
            'message':           f'Ticket #{ticket.ticket_id} created. We\'ll respond soon!',
            'kb_suggestions':    suggestions,
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f'Portal ticket create failed: {e}')
        return Response({'error': str(e)}, status=500)


# ══════════════════════════════════════════════════════
# TICKET DETAIL
# ══════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def portal_ticket_detail(request, ticket_id):
    """GET /support/portal/tickets/{ticket_id}/"""
    from api.support.services.ticket.TicketService import ticket_service  # noqa
    from api.support.serializers.ticket_serializers import SupportTicketSerializer
    from api.support.exceptions import TicketNotFoundException, UnauthorizedTicketAccessException  # noqa

    try:
        ticket = ticket_service.get(ticket_id, user=request.user)
    except TicketNotFoundException:
        return Response({'error': 'Ticket not found.'}, status=404)
    except UnauthorizedTicketAccessException:
        return Response({'error': 'Access denied.'}, status=403)

    # Get messages (exclude internal notes)
    from api.support.models import TicketMessage
    messages = list(
        TicketMessage.objects.filter(
            ticket      = ticket,
            is_internal = False,
        ).select_related('sender').order_by('created_at').values(
            'id', 'content', 'is_agent', 'created_at', 'sender__username', 'is_edited'
        )
    )

    # SLA info
    sla_info = {}
    try:
        from api.support.sla.advanced_sla_engine import advanced_sla_engine
        sla_info = advanced_sla_engine.get_sla_status(ticket)
    except Exception:
        pass

    # Attachments
    from api.support.models import TicketAttachment
    attachments = list(
        TicketAttachment.objects.filter(ticket=ticket)
        .values('id', 'filename', 'file_size', 'file_type', 'created_at')
    )

    return Response({
        'success':    True,
        'ticket':     SupportTicketSerializer(ticket).data,
        'messages':   messages,
        'sla':        sla_info,
        'attachments':attachments,
        'can_reply':  ticket.status not in ['closed', 'spam'],
        'can_rate':   ticket.status in ['resolved', 'closed'] and not ticket.satisfaction_rating,
        'can_reopen': ticket.status in ['resolved', 'closed'],
    })
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def portal_ticket_reply(request, ticket_id):
    """POST /support/portal/tickets/{ticket_id}/reply/"""
    content = request.data.get('content', '').strip()
    if not content or len(content) < 2:
        return Response({'error': 'Reply content required.'}, status=400)

    try:
        from api.support.services.ticket.TicketService import ticket_service  # noqa
        message = ticket_service.add_message(
            ticket_id   = ticket_id,
            user        = request.user,
            content     = content,
            is_agent    = False,
            is_internal = False,
        )
        return Response({
            'success': True,
            'message': {
                'id':         str(message.id),
                'content':    message.content,
                'is_agent':   False,
                'created_at': message.created_at.isoformat(),
            },
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=400)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def portal_ticket_rate(request, ticket_id):
    """POST /support/portal/tickets/{ticket_id}/rate/"""
    rating  = request.data.get('rating')
    comment = request.data.get('comment', '')

    if not rating or not 1 <= int(rating) <= 5:
        return Response({'error': 'Rating 1-5 required.'}, status=400)

    try:
        from api.support.models import SupportTicket, TicketRating
        ticket = SupportTicket.objects.get(ticket_id=ticket_id, user=request.user)

        if ticket.status not in ['resolved', 'closed']:
            return Response({'error': 'Can only rate resolved or closed tickets.'}, status=400)

        TicketRating.objects.update_or_create(
            ticket   = ticket,
            defaults = {
                'user':    request.user,
                'rating':  int(rating),
                'comment': comment,
            }
        )
        ticket.satisfaction_rating = int(rating)
        ticket.rating_comment      = comment
        ticket.rated_at            = timezone.now()
        ticket.save(update_fields=['satisfaction_rating', 'rating_comment', 'rated_at'])

        return Response({'success': True, 'message': 'Thank you for your feedback! ⭐'})
    except SupportTicket.DoesNotExist:
        return Response({'error': 'Ticket not found.'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=400)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def portal_ticket_reopen(request, ticket_id):
    """POST /support/portal/tickets/{ticket_id}/reopen/"""
    try:
        from api.support.services.ticket.TicketService import ticket_service  # noqa
        ticket_service.reopen(ticket_id, request.user)
        return Response({'success': True, 'message': 'Ticket reopened.'})
    except Exception as e:
        return Response({'error': str(e)}, status=400)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def portal_ticket_close(request, ticket_id):
    """POST /support/portal/tickets/{ticket_id}/close/"""
    try:
        from api.support.services.ticket.TicketService import ticket_service  # noqa
        ticket_service.close(ticket_id, request.user)
        return Response({'success': True, 'message': 'Ticket closed.'})
    except Exception as e:
        return Response({'error': str(e)}, status=400)


# ══════════════════════════════════════════════════════
# KNOWLEDGE BASE
# ══════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def portal_kb(request):
    """GET /support/portal/kb/"""
    from api.support.services.knowledge_base.KBService import kb_service
    from api.support.serializers.kb_serializers import KBArticleListSerializer, KBCategorySerializer

    filters = {}
    if request.query_params.get('category'):
        filters['category_slug'] = request.query_params.get('category')

    articles   = kb_service.list_articles(filters, public_only=True)
    popular    = kb_service.get_popular(limit=5)

    from api.support.models import KBCategory
    categories = KBCategory.objects.filter(is_active=True, parent=None)

    return Response({
        'success':    True,
        'articles':   KBArticleListSerializer(articles[:20], many=True).data,
        'popular':    popular,
        'categories': KBCategorySerializer(categories, many=True).data,
    })
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def portal_kb_search(request):
    """GET /support/portal/kb/search/?q=..."""
    query = request.query_params.get('q', '').strip()
    if len(query) < 2:
        return Response({'error': 'Query too short.'}, status=400)

    from api.support.services.knowledge_base.KBSearchService import kb_search_service
    results = kb_search_service.search(query, user=request.user)

    return Response({
        'success': True,
        'query':   query,
        'count':   len(results),
        'results': results,
    })
@permission_classes([IsAuthenticated])
def portal_kb_article(request, slug):
    """GET /support/portal/kb/{slug}/"""
    from api.support.services.knowledge_base.KBService import kb_service
    from api.support.serializers.kb_serializers import KBArticleSerializer
    from api.support.exceptions import KBArticleNotFoundException  # noqa

    try:
        article = kb_service.get_article(slug, increment_view=True)
    except KBArticleNotFoundException:
        return Response({'error': 'Article not found.'}, status=404)

    related = []
    try:
        from api.support.services.knowledge_base.KBRecommendService import kb_recommend_service
        related = kb_recommend_service.suggest_related(str(article.id))
    except Exception:
        pass

    return Response({
        'success': True,
        'article': KBArticleSerializer(article).data,
        'related': related,
    })


# ══════════════════════════════════════════════════════
# USER SUPPORT PROFILE
# ══════════════════════════════════════════════════════

@permission_classes([IsAuthenticated])
def portal_profile(request):
    """GET /support/portal/profile/"""
    from api.support.notifications.notification_prefs import prefs_manager
    prefs = prefs_manager.get_prefs_for_api(request.user)

    return Response({
        'success':              True,
        'username':             request.user.username,
        'email':                request.user.email,
        'notification_prefs':   prefs,
        'member_since':         request.user.date_joined.strftime('%B %Y') if hasattr(request.user, 'date_joined') else '',
    })
@permission_classes([IsAuthenticated])
def portal_update_prefs(request):
    """POST /support/portal/profile/prefs/"""
    from api.support.notifications.notification_prefs import prefs_manager
    prefs = prefs_manager.update_prefs(request.user, request.data)
    return Response({'success': True, 'prefs': prefs_manager.get_prefs_for_api(request.user)})


# ══════════════════════════════════════════════════════
# USER STATS
# ══════════════════════════════════════════════════════

@permission_classes([IsAuthenticated])
def portal_stats(request):
    """GET /support/portal/stats/ — My support statistics"""
    from api.support.models import SupportTicket, TicketRating
    from django.db.models import Avg, Count

    user    = request.user
    tickets = SupportTicket.objects.filter(user=user)

    # Ticket stats
    total    = tickets.count()
    by_status= {}
    for s in ['open','in_progress','waiting_user','resolved','closed']:
        by_status[s] = tickets.filter(status=s).count()

    # Avg resolution time
    resolved_tickets = tickets.filter(resolved_at__isnull=False)
    avg_res = 0
    if resolved_tickets.exists():
        times   = [(t.resolved_at - t.created_at).total_seconds() / 3600 for t in resolved_tickets]
        avg_res = round(sum(times) / len(times), 1)

    # My ratings
    ratings = TicketRating.objects.filter(user=user)
    avg_rat = ratings.aggregate(avg=Avg('rating'))['avg'] or 0

    # Category breakdown
    by_cat = list(tickets.values('category').annotate(count=Count('id')).order_by('-count'))

    return Response({
        'success':          True,
        'total_tickets':    total,
        'by_status':        by_status,
        'by_category':      by_cat,
        'avg_resolution_hrs':avg_res,
        'avg_rating_given': round(avg_rat, 1),
        'tickets_rated':    ratings.count(),
    })