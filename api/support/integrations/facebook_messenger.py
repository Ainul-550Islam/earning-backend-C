import os
"""
api/support/integrations/facebook_messenger.py
FILE 4/70 — Facebook Messenger Integration

User Facebook Page-এ message পাঠালে → ticket তৈরি হবে।
Messenger bot দিয়ে auto response দেবে।

Settings:
    FACEBOOK_PAGE_ACCESS_TOKEN = 'your_token'
    FACEBOOK_VERIFY_TOKEN      = 'your_verify_token'
    FACEBOOK_APP_SECRET        = os.environ.get('FACEBOOK_APP_SECRET', '')
"""
import hashlib
import hmac
import json
import logging
import requests
from django.conf import settings
from django.http import HttpResponse, JsonResponse

logger = logging.getLogger(__name__)

PAGE_TOKEN   = getattr(settings, 'FACEBOOK_PAGE_ACCESS_TOKEN', '')
VERIFY_TOKEN = getattr(settings, 'FACEBOOK_VERIFY_TOKEN',      'support_fb_verify')
APP_SECRET   = getattr(settings, 'FACEBOOK_APP_SECRET',        '')
BASE_URL     = 'https://graph.facebook.com/v18.0/me/messages'


class FacebookMessengerIntegration:
    """
    Facebook Messenger send + receive.
    User message → ticket.
    Agent reply → messenger notification.
    """

    # ─────────────────────────────────────
    # WEBHOOK
    # ─────────────────────────────────────
    def handle_webhook(self, request) -> HttpResponse:
        if request.method == 'GET':
            return self._verify(request)
        if request.method == 'POST':
            return self._process(request)
        return HttpResponse(status=405)

    def _verify(self, request) -> HttpResponse:
        mode      = request.GET.get('hub.mode')
        token     = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            logger.info('Facebook Messenger webhook verified.')
            return HttpResponse(challenge, content_type='text/plain')
        return HttpResponse(status=403)

    def _process(self, request) -> JsonResponse:
        if not self._verify_signature(request):
            return JsonResponse({'error': 'Invalid signature'}, status=403)
        try:
            body = json.loads(request.body)
            for entry in body.get('entry', []):
                for event in entry.get('messaging', []):
                    if 'message' in event:
                        self._handle_message(event)
                    elif 'postback' in event:
                        self._handle_postback(event)
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            logger.error(f'FB Messenger webhook error: {e}')
            return JsonResponse({'error': str(e)}, status=500)

    # ─────────────────────────────────────
    # HANDLE MESSAGES
    # ─────────────────────────────────────
    def _handle_message(self, event: dict) -> None:
        sender_id = event['sender']['id']
        msg       = event.get('message', {})
        text      = msg.get('text', '')
        attachments = msg.get('attachments', [])

        if not text and not attachments:
            return

        content = text or f'[{len(attachments)} attachment(s) received]'

        # Quick reply
        quick_reply = msg.get('quick_reply', {})
        if quick_reply:
            self._handle_quick_reply(sender_id, quick_reply.get('payload', ''))
            return

        # Create or update ticket
        self._process_message(sender_id, content)

    def _handle_postback(self, event: dict) -> None:
        sender_id = event['sender']['id']
        payload   = event.get('postback', {}).get('payload', '')
        if payload == 'GET_STARTED':
            self._send_welcome(sender_id)
        elif payload == 'CREATE_TICKET':
            self._send_category_quick_replies(sender_id)

    def _handle_quick_reply(self, sender_id: str, payload: str) -> None:
        if payload.startswith('CAT:'):
            category = payload.split(':')[1]
            self._send_message(sender_id, f'Please describe your {category} issue:')
            self._set_state(sender_id, {'category': category, 'awaiting': 'description'})

    def _process_message(self, sender_id: str, content: str) -> None:
        state = self._get_state(sender_id)
        if state.get('awaiting') == 'description':
            self._create_ticket(sender_id, state.get('category', 'other'), content)
            self._clear_state(sender_id)
        else:
            # Show welcome + options
            self._send_welcome(sender_id)

    # ─────────────────────────────────────
    # SEND MESSAGES
    # ─────────────────────────────────────
    def _send_welcome(self, sender_id: str) -> None:
        self._send_message(sender_id, 'Welcome to Support! How can I help you?')
        self._send_category_quick_replies(sender_id)

    def _send_category_quick_replies(self, sender_id: str) -> None:
        payload = {
            'recipient': {'id': sender_id},
            'message':   {
                'text':          'Please select your issue category:',
                'quick_replies': [
                    {'content_type': 'text', 'title': '💰 Payment',   'payload': 'CAT:payment'},
                    {'content_type': 'text', 'title': '💸 Withdrawal','payload': 'CAT:withdrawal'},
                    {'content_type': 'text', 'title': '🪙 Coins',     'payload': 'CAT:coins'},
                    {'content_type': 'text', 'title': '👤 Account',   'payload': 'CAT:account'},
                    {'content_type': 'text', 'title': '❓ Other',     'payload': 'CAT:other'},
                ]
            }
        }
        self._post(payload)

    def send_text(self, psid: str, text: str) -> bool:
        return self._send_message(psid, text)

    def send_ticket_update(self, psid: str, ticket, message: str) -> bool:
        text = f'💬 Update on ticket {ticket.ticket_id}:\n\n{message[:300]}'
        return self._send_message(psid, text)

    def _send_message(self, psid: str, text: str) -> bool:
        return self._post({
            'recipient': {'id': psid},
            'message':   {'text': text[:2000]},
        })

    def _post(self, payload: dict) -> bool:
        if not PAGE_TOKEN:
            logger.warning('Facebook: PAGE_TOKEN not configured.')
            return False
        try:
            resp = requests.post(
                BASE_URL,
                params  = {'access_token': PAGE_TOKEN},
                json    = payload,
                timeout = 15,
            )
            if resp.status_code == 200:
                return True
            logger.error(f'FB Messenger send failed: {resp.text[:200]}')
            return False
        except Exception as e:
            logger.error(f'FB Messenger request error: {e}')
            return False

    # ─────────────────────────────────────
    # TICKET CREATION
    # ─────────────────────────────────────
    def _create_ticket(self, psid: str, category: str, description: str) -> None:
        try:
            from api.support.models import SupportTicket
            from api.support.choices import CATEGORY_PRIORITY_MAP
            from django.contrib.auth import get_user_model
            User = get_user_model()

            username = f'fb_{psid}'
            user, _  = User.objects.get_or_create(
                username = username[:150],
                defaults = {'is_active': True},
            )
            priority = CATEGORY_PRIORITY_MAP.get(category, 'medium')
            ticket   = SupportTicket.objects.create(
                user        = user,
                category    = category,
                subject     = description[:100],
                description = description[:2000],
                priority    = priority,
                status      = 'open',
                channel     = 'facebook',
                tenant      = getattr(user, 'tenant', None),
            )
            self._send_message(psid,
                f'✅ Ticket created!\n\nTicket ID: {ticket.ticket_id}\n'
                f'We will respond within 24 hours.'
            )
            logger.info(f'FB Messenger ticket created: {ticket.ticket_id}')
        except Exception as e:
            logger.error(f'FB ticket create failed: {e}')
            self._send_message(psid, '❌ Failed to create ticket. Please visit our website.')

    # ─────────────────────────────────────
    # STATE + HELPERS
    # ─────────────────────────────────────
    def _get_state(self, psid: str) -> dict:
        try:
            from django.core.cache import cache
            return cache.get(f'fb_state:{psid}') or {}
        except Exception:
            return {}

    def _set_state(self, psid: str, state: dict) -> None:
        try:
            from django.core.cache import cache
            cache.set(f'fb_state:{psid}', state, timeout=1800)
        except Exception:
            pass

    def _clear_state(self, psid: str) -> None:
        try:
            from django.core.cache import cache
            cache.delete(f'fb_state:{psid}')
        except Exception:
            pass

    def _verify_signature(self, request) -> bool:
        if not APP_SECRET:
            return True
        signature = request.headers.get('X-Hub-Signature-256', '').replace('sha256=', '')
        expected  = hmac.new(APP_SECRET.encode(), request.body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)


# Singleton
fb_messenger = FacebookMessengerIntegration()