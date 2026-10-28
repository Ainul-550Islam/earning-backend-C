"""
api/support/integrations/whatsapp_integration.py
FILE 2/70 — WhatsApp Business API Integration

User WhatsApp-এ message পাঠালে → auto ticket তৈরি হবে।
Agent WhatsApp-এ reply পাঠাতে পারবে।

Requirements:
    pip install requests
    Settings:
        WHATSAPP_API_TOKEN      = 'your_token'
        WHATSAPP_PHONE_NUMBER_ID = 'your_phone_id'
        WHATSAPP_VERIFY_TOKEN   = 'your_webhook_verify_token'
        WHATSAPP_BUSINESS_ID    = 'your_business_id'

Meta Business API docs: https://developers.facebook.com/docs/whatsapp
"""
import re
import logging
import json
import hashlib
import hmac
import requests
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse

logger = logging.getLogger(__name__)


class WhatsAppBusinessAPI:
    """
    WhatsApp Business API wrapper.
    Send messages + handle incoming webhooks.
    """

    BASE_URL        = 'https://graph.facebook.com/v18.0'
    API_TOKEN       = getattr(settings, 'WHATSAPP_API_TOKEN',       '')
    PHONE_NUMBER_ID = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '')
    VERIFY_TOKEN    = getattr(settings, 'WHATSAPP_VERIFY_TOKEN',    'support_verify_2024')
    APP_SECRET      = getattr(settings, 'WHATSAPP_APP_SECRET',      '')

    # ─────────────────────────────────────
    # SEND MESSAGES
    # ─────────────────────────────────────
    def send_text(self, to: str, message: str) -> bool:
        """Plain text message পাঠাও"""
        return self._send({
            'messaging_product': 'whatsapp',
            'recipient_type':    'individual',
            'to':                self._format_phone(to),
            'type':              'text',
            'text':              {'preview_url': False, 'body': message},
        })

    def send_template(self, to: str, template_name: str, language: str = 'en', components: list = None) -> bool:
        """Template message পাঠাও (pre-approved templates)"""
        payload = {
            'messaging_product': 'whatsapp',
            'to':                self._format_phone(to),
            'type':              'template',
            'template': {
                'name':     template_name,
                'language': {'code': language},
            }
        }
        if components:
            payload['template']['components'] = components

        return self._send(payload)

    def send_ticket_confirmation(self, to: str, ticket) -> bool:
        """Ticket created — user-কে WA notification পাঠাও"""
        message = (
            f"✅ *Support Ticket Created*\n\n"
            f"Ticket ID: *{ticket.ticket_id}*\n"
            f"Subject: {ticket.subject}\n"
            f"Priority: {ticket.priority.upper()}\n\n"
            f"Our team will respond within 24 hours.\n"
            f"Reply here to update your ticket."
        )
        return self.send_text(to, message)

    def send_ticket_reply(self, to: str, ticket, reply_content: str) -> bool:
        """Agent reply → user-কে WA notification"""
        message = (
            f"💬 *New Reply on Ticket {ticket.ticket_id}*\n\n"
            f"{reply_content[:800]}\n\n"
            f"Reply here to respond."
        )
        return self.send_text(to, message)

    def send_ticket_resolved(self, to: str, ticket) -> bool:
        """Ticket resolved → user-কে notify"""
        message = (
            f"✅ *Ticket Resolved: {ticket.ticket_id}*\n\n"
            f"Your issue has been resolved.\n"
            f"Please rate your experience: 1-5\n\n"
            f"Reply with a number (1=Poor, 5=Excellent)"
        )
        return self.send_text(to, message)

    def send_agent_alert(self, agent_phone: str, ticket) -> bool:
        """New ticket → agent-কে WA alert"""
        message = (
            f"🎫 *New Ticket Assigned*\n\n"
            f"ID: {ticket.ticket_id}\n"
            f"Priority: {ticket.priority.upper()}\n"
            f"Category: {ticket.category}\n"
            f"User: {ticket.user.username}\n"
            f"Subject: {ticket.subject[:100]}"
        )
        return self.send_text(agent_phone, message)

    def send_sla_breach_alert(self, agent_phone: str, ticket, breach_type: str) -> bool:
        """SLA breach → agent-কে urgent alert"""
        message = (
            f"🚨 *SLA BREACH ALERT*\n\n"
            f"Ticket: {ticket.ticket_id}\n"
            f"Breach Type: {breach_type}\n"
            f"Priority: {ticket.priority.upper()}\n"
            f"Please respond immediately!"
        )
        return self.send_text(agent_phone, message)

    # ─────────────────────────────────────
    # WEBHOOK HANDLER
    # ─────────────────────────────────────
    def handle_webhook(self, request) -> HttpResponse:
        """
        WhatsApp webhook handler।
        GET = verification
        POST = incoming messages
        """
        if request.method == 'GET':
            return self._verify_webhook(request)
        if request.method == 'POST':
            return self._process_webhook(request)
        return HttpResponse(status=405)

    def _verify_webhook(self, request) -> HttpResponse:
        """Meta webhook verification"""
        mode      = request.GET.get('hub.mode')
        token     = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode == 'subscribe' and token == self.VERIFY_TOKEN:
            logger.info('WhatsApp webhook verified.')
            return HttpResponse(challenge, content_type='text/plain')

        return HttpResponse(status=403)

    def _process_webhook(self, request) -> JsonResponse:
        """Incoming WhatsApp message process করো"""
        try:
            # Signature verification
            if not self._verify_signature(request):
                return JsonResponse({'error': 'Invalid signature'}, status=403)

            body = json.loads(request.body)
            entries = body.get('entry', [])

            for entry in entries:
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    messages = value.get('messages', [])

                    for msg in messages:
                        self._handle_incoming_message(msg, value)

            return JsonResponse({'status': 'ok'})

        except Exception as e:
            logger.error(f'WhatsApp webhook error: {e}')
            return JsonResponse({'error': str(e)}, status=500)

    def _handle_incoming_message(self, msg: dict, context: dict) -> None:
        """Single incoming WA message process করো"""
        from_phone  = msg.get('from', '')
        msg_type    = msg.get('type', 'text')
        timestamp   = msg.get('timestamp')

        if msg_type == 'text':
            content = msg.get('text', {}).get('body', '')
        elif msg_type == 'image':
            content = f'[Image received via WhatsApp]'
        elif msg_type == 'document':
            content = f'[Document received via WhatsApp]'
        elif msg_type == 'voice':
            content = f'[Voice message received via WhatsApp]'
        else:
            content = f'[{msg_type} received via WhatsApp]'

        if not content:
            return

        logger.info(f'WhatsApp message from {from_phone}: {content[:50]}')

        # Check if reply to existing ticket
        ticket_id = self._extract_ticket_id(content)
        if ticket_id:
            self._add_reply_to_ticket(ticket_id, from_phone, content)
        elif self._is_rating_response(content):
            self._process_rating(from_phone, content)
        else:
            self._create_ticket_from_wa(from_phone, content)

    def _create_ticket_from_wa(self, phone: str, content: str) -> None:
        """WhatsApp message থেকে ticket তৈরি করো"""
        try:
            from api.support.models import SupportTicket
            from api.support.choices import CATEGORY_PRIORITY_MAP

            user     = self._get_user_by_phone(phone)
            category = self._detect_category(content)
            priority = CATEGORY_PRIORITY_MAP.get(category, 'medium')

            ticket = SupportTicket.objects.create(
                user        = user,
                category    = category,
                subject     = content[:100],
                description = content[:2000],
                priority    = priority,
                status      = 'open',
                channel     = 'whatsapp',
                tenant      = getattr(user, 'tenant', None),
            )

            # Confirmation
            self.send_ticket_confirmation(phone, ticket)
            logger.info(f'WhatsApp ticket created: {ticket.ticket_id}')

        except Exception as e:
            logger.error(f'WA ticket create failed: {e}')

    def _add_reply_to_ticket(self, ticket_id: str, phone: str, content: str) -> None:
        from api.support.models import SupportTicket, TicketMessage
        try:
            ticket = SupportTicket.objects.filter(
                ticket_id=ticket_id
            ).exclude(status__in=['closed', 'spam']).first()

            if not ticket:
                self.send_text(phone, f'Ticket {ticket_id} not found or closed.')
                return

            TicketMessage.objects.create(
                ticket   = ticket,
                sender   = ticket.user,
                content  = f'[Via WhatsApp]\n\n{content}',
                is_agent = False,
            )
            ticket.status = 'in_progress'
            ticket.save(update_fields=['status'])

            self.send_text(phone, f'✅ Your message has been added to ticket {ticket_id}. We will respond soon.')
        except Exception as e:
            logger.error(f'WA reply to ticket failed: {e}')

    def _process_rating(self, phone: str, content: str) -> None:
        """User যদি 1-5 rating দেয়"""
        try:
            rating = int(content.strip()[0])
            if 1 <= rating <= 5:
                from api.support.models import SupportTicket, TicketRating
                # Latest resolved ticket
                user   = self._get_user_by_phone(phone)
                ticket = SupportTicket.objects.filter(
                    user   = user,
                    status = 'resolved',
                    satisfaction_rating__isnull = True,
                ).order_by('-resolved_at').first()

                if ticket:
                    TicketRating.objects.get_or_create(
                        ticket   = ticket,
                        defaults = {'user': user, 'rating': rating}
                    )
                    self.send_text(phone, f'⭐ Thank you for rating {rating}/5! We appreciate your feedback.')
        except (ValueError, IndexError):
            pass

    # ─────────────────────────────────────
    # PRIVATE HELPERS
    # ─────────────────────────────────────
    def _send(self, payload: dict) -> bool:
        if not self.API_TOKEN or not self.PHONE_NUMBER_ID:
            logger.warning('WhatsApp: API credentials not configured.')
            return False

        url = f'{self.BASE_URL}/{self.PHONE_NUMBER_ID}/messages'
        try:
            resp = requests.post(
                url,
                headers = {
                    'Authorization': f'Bearer {self.API_TOKEN}',
                    'Content-Type':  'application/json',
                },
                json    = payload,
                timeout = 15,
            )
            if resp.status_code == 200:
                return True
            logger.error(f'WhatsApp send failed [{resp.status_code}]: {resp.text}')
            return False
        except requests.RequestException as e:
            logger.error(f'WhatsApp request failed: {e}')
            return False

    def _verify_signature(self, request) -> bool:
        if not self.APP_SECRET:
            return True  # Skip in dev
        signature = request.headers.get('X-Hub-Signature-256', '').replace('sha256=', '')
        expected  = hmac.new(self.APP_SECRET.encode(), request.body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)

    def _format_phone(self, phone: str) -> str:
        phone = re.sub(r'[^\d+]', '', phone)
        if not phone.startswith('+'):
            phone = '+' + phone
        return phone

    def _extract_ticket_id(self, text: str) -> str | None:
        import re
        match = re.search(r'\b(TKT\d{6})\b', text, re.IGNORECASE)
        return match.group(1) if match else None

    def _is_rating_response(self, text: str) -> bool:
        return text.strip() in ['1', '2', '3', '4', '5']

    def _detect_category(self, text: str) -> str:
        text = text.lower()
        if any(w in text for w in ['payment', 'paid', 'bkash', 'nagad', 'টাকা']):
            return 'payment'
        if any(w in text for w in ['withdraw', 'withdrawal', 'উইথড্র']):
            return 'withdrawal'
        if any(w in text for w in ['coin', 'balance', 'কয়েন']):
            return 'coins'
        if any(w in text for w in ['fraud', 'hack', 'scam', 'ফ্রড']):
            return 'fraud'
        if any(w in text for w in ['account', 'login', 'password', 'একাউন্ট']):
            return 'account'
        return 'other'

    def _get_user_by_phone(self, phone: str):
        """Phone number দিয়ে user খুঁজে বের করো"""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # profile-এ phone number matching
        user = User.objects.filter(
            profile__phone_number=phone
        ).first() if hasattr(User, 'profile') else None

        if not user:
            username = f'wa_{phone.replace("+", "").replace(" ", "")}'
            user, _  = User.objects.get_or_create(
                username = username[:150],
                defaults = {'is_active': True},
            )
        return user

    def get_message_status(self, message_id: str) -> dict:
        """Message delivery status check"""
        try:
            url  = f'{self.BASE_URL}/{message_id}'
            resp = requests.get(
                url,
                headers = {'Authorization': f'Bearer {self.API_TOKEN}'},
                timeout = 10,
            )
            return resp.json() if resp.status_code == 200 else {}
        except Exception:
            return {}



# Singleton
whatsapp_api = WhatsAppBusinessAPI()