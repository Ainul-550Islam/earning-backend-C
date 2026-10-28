"""
api/support/livechat/chat_widget_api.py
FILE 25/70 — Chat Widget Embed API

Website-এ embed করার JS widget-এর backend API।
Frontend JS widget এই endpoints call করবে।

Widget JS embed code:
<script>
  window.SupportConfig = {
    apiUrl: 'https://yoursite.com/api/support',
    userId: '{{user.id}}',
    token: '{{user.auth_token}}',
    theme: {primary: '#6366f1'},
  };
</script>
<script src="https://yoursite.com/static/support/widget.js"></script>

Endpoints:
    POST /support/widget/init/          — Widget initialize
    POST /support/widget/track/         — Track visitor event
    POST /support/widget/proactive/     — Check proactive trigger
    POST /support/widget/bot/message/   — Bot message
    POST /support/widget/chat/start/    — Start live chat
    GET  /support/widget/config/        — Widget config
"""
import logging
from django.utils import timezone
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)

WIDGET_VERSION = '2.0.0'


# ══════════════════════════════════════════════════════
# WIDGET CONFIG
# ══════════════════════════════════════════════════════

@api_view(['GET'])
@api_view(['POST'])
@permission_classes([AllowAny])
def widget_config(request):
    """
    GET /support/widget/config/
    Widget settings — no auth required।
    """
    from api.support.models import SupportSettings, SupportAgent
    from django.db.models import Count

    try:
        settings_obj = SupportSettings.objects.filter(id=1).first()
        online_count = SupportAgent.objects.filter(is_active=True, is_available=True).count()

        # Business hours check
        now       = timezone.localtime().time()
        in_hours  = True
        if settings_obj:
            in_hours = (
                settings_obj.support_hours_start <= now <= settings_obj.support_hours_end
                and settings_obj.is_support_online
                and not settings_obj.maintenance_mode
            )

        return Response({
            'success':          True,
            'version':          WIDGET_VERSION,
            'is_online':        in_hours and online_count > 0,
            'agents_online':    online_count,
            'maintenance':      settings_obj.maintenance_mode if settings_obj else False,
            'maintenance_msg':  settings_obj.maintenance_message if settings_obj else '',
            'business_hours': {
                'start': str(settings_obj.support_hours_start) if settings_obj else '09:00',
                'end':   str(settings_obj.support_hours_end)   if settings_obj else '18:00',
            },
            'features': {
                'live_chat':       True,
                'chatbot':         True,
                'tickets':         True,
                'kb':              True,
                'proactive_chat':  getattr(settings, 'PROACTIVE_CHAT_ENABLED', True),
            },
            'theme': {
                'primary_color':  getattr(settings, 'WIDGET_PRIMARY_COLOR', '#6366f1'),
                'secondary_color':getattr(settings, 'WIDGET_SECONDARY_COLOR', '#f1f5f9'),
                'font_family':    'Inter, sans-serif',
            },
            'text': {
                'greeting':       'How can we help you?',
                'placeholder':    'Type your message...',
                'offline_msg':    'We\'re offline right now. Leave us a message!',
                'bot_name':       'Support Bot',
            },
        })
    except Exception as e:
        logger.error(f'Widget config failed: {e}')
        return Response({'success': False, 'error': str(e)}, status=500)


# ══════════════════════════════════════════════════════
# WIDGET INITIALIZE
# ══════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([AllowAny])
def widget_init(request):
    """
    POST /support/widget/init/
    Widget first load — session create করো।
    """
    from api.support.livechat.visitor_tracking import visitor_tracker

    user_id    = request.data.get('user_id') or (str(request.user.id) if request.user.is_authenticated else None)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    ip         = _get_client_ip(request)

    # Create visitor session
    session_id = visitor_tracker.create_session(
        user_id    = user_id,
        ip         = ip,
        user_agent = user_agent,
    )

    # Check for open tickets
    open_tickets = _get_open_tickets(user_id)

    # Check proactive trigger
    page_url = request.data.get('page_url', '/')
    visitor_tracker.track_event('session_start', session_id, user_id or '', page_url, {
        'user_agent': user_agent,
        'referrer':   request.data.get('referrer', ''),
    })

    return Response({
        'success':    True,
        'session_id': session_id,
        'user_id':    user_id,
        'open_tickets':open_tickets,
        'show_notification': len(open_tickets) > 0,
    })


# ══════════════════════════════════════════════════════
# VISITOR TRACKING
# ══════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([AllowAny])
def widget_track(request):
    """
    POST /support/widget/track/
    Track visitor events।
    """
    from api.support.livechat.visitor_tracking import visitor_tracker

    event_type = request.data.get('event', 'page_view')
    session_id = request.data.get('session_id', '')
    user_id    = request.data.get('user_id', '') or (str(request.user.id) if request.user.is_authenticated else '')
    page_url   = request.data.get('page_url', '/')
    event_data = request.data.get('data', {})

    result = visitor_tracker.track_event(event_type, session_id, user_id, page_url, event_data)

    return Response({
        'success':              True,
        'should_trigger_chat':  result.get('should_trigger_chat', False),
        'trigger_data':         result.get('trigger_data'),
    })


# ══════════════════════════════════════════════════════
# PROACTIVE CHAT
# ══════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([AllowAny])
def widget_proactive_check(request):
    """
    POST /support/widget/proactive/
    Proactive trigger check করো।
    """
    from api.support.livechat.proactive_triggers import proactive_trigger_engine

    user_id      = request.data.get('user_id', '')
    page_url     = request.data.get('page_url', '/')
    session_data = request.data.get('session_data', {})

    trigger = proactive_trigger_engine.evaluate(user_id, page_url, session_data)

    return Response({
        'success':     True,
        'should_show': trigger is not None,
        'trigger':     trigger,
    })


# ══════════════════════════════════════════════════════
# CHATBOT
# ══════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([AllowAny])
def widget_bot_message(request):
    """
    POST /support/widget/bot/message/
    Bot message process করো।
    """
    from api.support.livechat.chatbot_runner import chatbot_runner

    session_id  = request.data.get('session_id', '')
    message     = request.data.get('message', '').strip()
    user        = request.user if request.user.is_authenticated else None

    if not session_id:
        return Response({'error': 'session_id required.'}, status=400)

    if not message:
        # Start new flow
        result = chatbot_runner.start_flow(session_id, user=user)
    else:
        result = chatbot_runner.process_message(session_id, message, user)

    return Response({
        'success':       True,
        'messages':      result.get('messages', []),
        'options':       result.get('options', []),
        'is_handoff':    result.get('is_handoff', False),
        'is_end':        result.get('is_end', False),
        'ticket_created':result.get('ticket_created'),
        'variables':     result.get('variables', {}),
    })


# ══════════════════════════════════════════════════════
# LIVE CHAT
# ══════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def widget_start_chat(request):
    """
    POST /support/widget/chat/start/
    Live chat session শুরু করো।
    """
    from api.support.services.livechat.ChatService import chat_service

    department = request.data.get('department')
    try:
        session = chat_service.start_session(request.user, department)
        return Response({
            'success':     True,
            'session_id':  str(session.session_id),
            'status':      session.status,
            'queue_pos':   session.queue_position,
            'message':     'Connected!' if session.status == 'active' else 'Waiting for agent...',
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error(f'Widget start chat failed: {e}')
        return Response({'error': str(e)}, status=500)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def widget_send_message(request):
    """
    POST /support/widget/chat/message/
    Chat message পাঠাও।
    """
    from api.support.services.livechat.ChatService import chat_service

    session_id = request.data.get('session_id', '')
    content    = request.data.get('content', '').strip()
    msg_type   = request.data.get('type', 'text')

    if not session_id or not content:
        return Response({'error': 'session_id and content required.'}, status=400)

    try:
        message = chat_service.send_message(session_id, request.user, content, False, msg_type)
        return Response({
            'success':  True,
            'message':  {
                'id':         str(message.id),
                'content':    message.content,
                'is_agent':   message.is_agent,
                'created_at': message.created_at.isoformat(),
            }
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error(f'Widget send message failed: {e}')
        return Response({'error': str(e)}, status=500)
@permission_classes([IsAuthenticated])
def widget_get_messages(request, session_id):
    """
    GET /support/widget/chat/{session_id}/messages/
    Chat messages fetch করো।
    """
    from api.support.services.livechat.ChatService import chat_service

    messages = chat_service.get_messages(session_id)
    return Response({'success': True, 'messages': messages})

@permission_classes([IsAuthenticated])
def widget_end_chat(request):
    """
    POST /support/widget/chat/end/
    Chat session end করো।
    """
    from api.support.services.livechat.ChatService import chat_service

    session_id = request.data.get('session_id', '')
    chat_service.end_session(session_id)
    return Response({'success': True, 'message': 'Chat ended.'})
@permission_classes([IsAuthenticated])
def widget_rate_chat(request):
    """
    POST /support/widget/chat/rate/
    Chat rate করো।
    """
    from api.support.models import ChatSession  # ChatRating is handled via ChatSession.rating field

    session_id = request.data.get('session_id', '')
    rating     = request.data.get('rating')
    comment    = request.data.get('comment', '')

    if not rating or not 1 <= int(rating) <= 5:
        return Response({'error': 'Rating 1-5 required.'}, status=400)

    try:
        session = ChatSession.objects.get(session_id=session_id, user=request.user)
        # Update rating directly on ChatSession
        session.rating = int(rating)
        session.rating_comment = comment
        session.save(update_fields=['rating', 'rating_comment'])
        return Response({'success': True, 'message': 'Rating submitted!'})
    except Exception as e:
        return Response({'error': str(e)}, status=400)


# ══════════════════════════════════════════════════════
# TICKET CREATION FROM WIDGET
# ══════════════════════════════════════════════════════

@permission_classes([IsAuthenticated])
def widget_create_ticket(request):
    """
    POST /support/widget/ticket/
    Widget থেকে ticket create করো।
    """
    from api.support.services.ticket.TicketService import ticket_service
    from api.support.services.knowledge_base.KBRecommendService import kb_recommend_service

    data = {
        'category':    request.data.get('category', 'other'),
        'subject':     request.data.get('subject', ''),
        'description': request.data.get('description', ''),
        'channel':     'chat',
    }

    if not data['subject'] or not data['description']:
        return Response({'error': 'subject and description required.'}, status=400)

    # Suggest KB first
    suggestions = kb_recommend_service.suggest_for_ticket(data['subject'], data['category'])

    try:
        ticket = ticket_service.create(request.user, data)
        return Response({
            'success':           True,
            'ticket_id':         ticket.ticket_id,
            'priority':          ticket.priority,
            'suggested_articles':suggestions,
            'message':           f'Ticket #{ticket.ticket_id} created. We\'ll respond within 24 hours.',
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error(f'Widget ticket create failed: {e}')
        return Response({'error': str(e)}, status=500)


# ══════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════

def _get_client_ip(request) -> str:
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _get_open_tickets(user_id: str) -> list:
    if not user_id:
        return []
    try:
        from api.support.models import SupportTicket
        from django.contrib.auth import get_user_model
        User   = get_user_model()
        user   = User.objects.filter(id=user_id).first()
        if not user:
            return []
        return list(
            SupportTicket.objects.filter(
                user=user, status__in=['open','in_progress','waiting_user']
            ).values('ticket_id', 'subject', 'status', 'priority')[:3]
        )
    except Exception:
        return []