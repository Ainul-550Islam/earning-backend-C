"""
api/support/integrations/telegram_bot.py
FILE 3/70 — Telegram Bot Full Integration

User Telegram-এ message পাঠালে → ticket তৈরি হবে।
Agent Telegram-এ notification পাবে।
Inline keyboard দিয়ে user সহজে category select করতে পারবে।

pip install python-telegram-bot==20.7
Settings:
    TELEGRAM_BOT_TOKEN    = 'your_bot_token'
    TELEGRAM_ADMIN_CHAT   = '-100xxxxxxxxx'  # group chat id
    TELEGRAM_WEBHOOK_URL  = 'https://yoursite.com/api/support/webhooks/telegram/'
"""
import json
import logging
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

BOT_TOKEN  = getattr(settings, 'TELEGRAM_BOT_TOKEN',  '')
ADMIN_CHAT = getattr(settings, 'TELEGRAM_ADMIN_CHAT', '')
BASE_URL   = f'https://api.telegram.org/bot{BOT_TOKEN}'

# User conversation state (Redis-based in production)
USER_STATES = {}  # {chat_id: state_dict}


class TelegramSupportBot:
    """
    Full-featured Telegram support bot.
    State machine for guided ticket creation.
    """

    # Conversation states
    STATE_IDLE        = 'idle'
    STATE_SELECT_CAT  = 'select_category'
    STATE_GET_SUBJECT = 'get_subject'
    STATE_GET_DESC    = 'get_description'

    # Category keyboard
    CATEGORY_KEYBOARD = {
        'inline_keyboard': [
            [{'text': '💰 Payment Issue',    'callback_data': 'cat:payment'}],
            [{'text': '💸 Withdrawal',        'callback_data': 'cat:withdrawal'}],
            [{'text': '🪙 Coins Missing',     'callback_data': 'cat:coins'}],
            [{'text': '👤 Account Problem',   'callback_data': 'cat:account'}],
            [{'text': '🔒 Fraud/Security',    'callback_data': 'cat:fraud'}],
            [{'text': '📋 KYC Verification',  'callback_data': 'cat:kyc'}],
            [{'text': '🔧 Technical Issue',   'callback_data': 'cat:technical'}],
            [{'text': '❓ Other',             'callback_data': 'cat:other'}],
        ]
    }

    MAIN_KEYBOARD = {
        'inline_keyboard': [
            [{'text': '🎫 Create Ticket',  'callback_data': 'action:new_ticket'}],
            [{'text': '📋 My Tickets',     'callback_data': 'action:my_tickets'}],
            [{'text': '📚 Knowledge Base', 'callback_data': 'action:kb'}],
            [{'text': '💬 Live Chat',      'callback_data': 'action:chat'}],
        ]
    }

    # ─────────────────────────────────────
    # WEBHOOK HANDLER
    # ─────────────────────────────────────
    def handle_update(self, update: dict) -> dict:
        """
        Telegram webhook update handle করো।
        Returns: response dict
        """
        try:
            if 'message' in update:
                return self._handle_message(update['message'])
            elif 'callback_query' in update:
                return self._handle_callback(update['callback_query'])
            return {'ok': True}
        except Exception as e:
            logger.error(f'Telegram update error: {e}')
            return {'ok': False, 'error': str(e)}

    def _handle_message(self, message: dict) -> dict:
        chat_id  = str(message['chat']['id'])
        text     = message.get('text', '').strip()
        username = message.get('from', {}).get('username', '')
        name     = message.get('from', {}).get('first_name', 'User')

        # Commands
        if text.startswith('/'):
            return self._handle_command(chat_id, text, name, username)

        # State machine
        state = self._get_state(chat_id)
        if state.get('state') == self.STATE_GET_SUBJECT:
            return self._save_subject(chat_id, text)
        elif state.get('state') == self.STATE_GET_DESC:
            return self._save_description_and_create(chat_id, text, username)

        # Default — show main menu
        return self._show_main_menu(chat_id, name)

    def _handle_command(self, chat_id: str, text: str, name: str, username: str) -> dict:
        """Bot commands handle করো"""
        cmd = text.split()[0].lower()

        if cmd == '/start':
            self.send_message(chat_id,
                f"👋 Welcome to Support, {name}!\n\n"
                f"I can help you:\n"
                f"• Create support tickets\n"
                f"• Check ticket status\n"
                f"• Search knowledge base\n\n"
                f"How can I help you today?",
                reply_markup=self.MAIN_KEYBOARD
            )

        elif cmd == '/ticket':
            self._start_ticket_creation(chat_id)

        elif cmd == '/status':
            parts     = text.split()
            ticket_id = parts[1].upper() if len(parts) > 1 else None
            if ticket_id:
                self._check_ticket_status(chat_id, ticket_id)
            else:
                self._show_my_tickets(chat_id, username)

        elif cmd == '/help':
            self.send_message(chat_id,
                "📖 *Available Commands:*\n\n"
                "/start — Main menu\n"
                "/ticket — Create new ticket\n"
                "/status TKT123456 — Check ticket status\n"
                "/mytickets — List my tickets\n"
                "/kb — Search knowledge base\n"
                "/help — Show this help",
                parse_mode='Markdown'
            )

        elif cmd == '/mytickets':
            self._show_my_tickets(chat_id, username)

        elif cmd == '/kb':
            query = text[3:].strip()
            self._search_kb(chat_id, query)

        elif cmd == '/cancel':
            self._clear_state(chat_id)
            self.send_message(chat_id, '❌ Cancelled. Use /start to begin.')

        return {'ok': True}

    def _handle_callback(self, callback: dict) -> dict:
        """Inline keyboard callback handle করো"""
        chat_id    = str(callback['message']['chat']['id'])
        data       = callback.get('data', '')
        callback_id= callback.get('id')

        # Answer callback to remove loading
        self._answer_callback(callback_id)

        if data.startswith('action:'):
            action = data.split(':')[1]
            if action == 'new_ticket':
                self._start_ticket_creation(chat_id)
            elif action == 'my_tickets':
                username = callback['from'].get('username', '')
                self._show_my_tickets(chat_id, username)
            elif action == 'kb':
                self.send_message(chat_id, '🔍 Send me your question to search the knowledge base:')
            elif action == 'chat':
                self.send_message(chat_id, '💬 To start live chat, please visit:\nyour-site.com/support/chat')

        elif data.startswith('cat:'):
            category = data.split(':')[1]
            self._save_category(chat_id, category)

        elif data.startswith('rate:'):
            parts    = data.split(':')
            ticket_id= parts[1]
            rating   = int(parts[2])
            self._submit_rating(chat_id, ticket_id, rating, callback['from'].get('username',''))

        return {'ok': True}

    # ─────────────────────────────────────
    # TICKET CREATION FLOW
    # ─────────────────────────────────────
    def _start_ticket_creation(self, chat_id: str) -> None:
        self._set_state(chat_id, {'state': self.STATE_SELECT_CAT})
        self.send_message(chat_id,
            '📂 Please select the category for your issue:',
            reply_markup=self.CATEGORY_KEYBOARD
        )

    def _save_category(self, chat_id: str, category: str) -> None:
        state = self._get_state(chat_id)
        state['category'] = category
        state['state']    = self.STATE_GET_SUBJECT
        self._set_state(chat_id, state)

        category_names = {
            'payment': '💰 Payment Issue', 'withdrawal': '💸 Withdrawal',
            'coins': '🪙 Coins Missing', 'account': '👤 Account Problem',
            'fraud': '🔒 Fraud/Security', 'kyc': '📋 KYC Verification',
            'technical': '🔧 Technical', 'other': '❓ Other',
        }
        self.send_message(chat_id,
            f"✅ Category: *{category_names.get(category, category)}*\n\n"
            f"📝 Now please enter a brief subject/title for your issue:",
            parse_mode='Markdown'
        )

    def _save_subject(self, chat_id: str, subject: str) -> dict:
        if len(subject) < 5:
            self.send_message(chat_id, '⚠️ Subject too short. Please be more descriptive:')
            return {'ok': True}

        state = self._get_state(chat_id)
        state['subject'] = subject[:200]
        state['state']   = self.STATE_GET_DESC
        self._set_state(chat_id, state)

        self.send_message(chat_id,
            f"📋 Subject: *{subject[:50]}*\n\n"
            f"💬 Now please describe your issue in detail:\n"
            f"_(Include transaction IDs, error messages, etc.)_",
            parse_mode='Markdown'
        )
        return {'ok': True}

    def _save_description_and_create(self, chat_id: str, description: str, username: str) -> dict:
        if len(description) < 10:
            self.send_message(chat_id, '⚠️ Please provide more details:')
            return {'ok': True}

        state = self._get_state(chat_id)
        if not state.get('category') or not state.get('subject'):
            self.send_message(chat_id, '❌ Something went wrong. Please /start again.')
            self._clear_state(chat_id)
            return {'ok': True}

        # Create ticket
        ticket = self._create_ticket(
            chat_id    = chat_id,
            username   = username,
            category   = state['category'],
            subject    = state['subject'],
            description= description,
        )

        self._clear_state(chat_id)

        if ticket:
            self.send_message(chat_id,
                f"✅ *Ticket Created Successfully!*\n\n"
                f"🎫 Ticket ID: `{ticket.ticket_id}`\n"
                f"📂 Category: {ticket.category}\n"
                f"⚡ Priority: {ticket.priority.upper()}\n\n"
                f"Our team will respond within 24 hours.\n"
                f"Use /status {ticket.ticket_id} to check updates.",
                parse_mode='Markdown'
            )
        else:
            self.send_message(chat_id, '❌ Failed to create ticket. Please try again or visit our website.')

        return {'ok': True}

    def _create_ticket(self, chat_id: str, username: str, category: str, subject: str, description: str):
        try:
            from api.support.models import SupportTicket
            from api.support.choices import CATEGORY_PRIORITY_MAP
            from django.contrib.auth import get_user_model
            User = get_user_model()

            # Telegram username দিয়ে user খুঁজে বের করো
            user = User.objects.filter(
                profile__telegram_username=username
            ).first() if username else None

            if not user:
                tg_username = f'tg_{username or chat_id}'
                user, _ = User.objects.get_or_create(
                    username = tg_username[:150],
                    defaults = {'is_active': True},
                )

            priority = CATEGORY_PRIORITY_MAP.get(category, 'medium')
            ticket   = SupportTicket.objects.create(
                user        = user,
                category    = category,
                subject     = subject,
                description = description,
                priority    = priority,
                status      = 'open',
                channel     = 'telegram',
                tenant      = getattr(user, 'tenant', None),
            )

            # Notify admin group
            self.notify_admin_new_ticket(ticket)
            return ticket

        except Exception as e:
            logger.error(f'Telegram ticket create failed: {e}')
            return None

    # ─────────────────────────────────────
    # TICKET STATUS + MY TICKETS
    # ─────────────────────────────────────
    def _check_ticket_status(self, chat_id: str, ticket_id: str) -> None:
        from api.support.models import SupportTicket
        try:
            ticket = SupportTicket.objects.get(ticket_id=ticket_id.upper())
            status_emoji = {
                'open': '🟡', 'in_progress': '🔵', 'waiting_user': '🟠',
                'resolved': '✅', 'closed': '⛔', 'spam': '🚫'
            }
            emoji = status_emoji.get(ticket.status, '❓')
            msg   = (
                f"🎫 *Ticket: {ticket.ticket_id}*\n\n"
                f"📋 Subject: {ticket.subject}\n"
                f"📂 Category: {ticket.category}\n"
                f"⚡ Priority: {ticket.priority.upper()}\n"
                f"{emoji} Status: {ticket.status.replace('_', ' ').title()}\n"
                f"📅 Created: {ticket.created_at.strftime('%d %b %Y %H:%M')}"
            )
            if ticket.admin_response:
                msg += f"\n\n💬 *Last Response:*\n{ticket.admin_response[:300]}"
            self.send_message(chat_id, msg, parse_mode='Markdown')
        except SupportTicket.DoesNotExist:
            self.send_message(chat_id, f'❌ Ticket {ticket_id} not found.')

    def _show_my_tickets(self, chat_id: str, username: str) -> None:
        from api.support.models import SupportTicket
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user = User.objects.filter(username=f'tg_{username}').first()
        if not user:
            self.send_message(chat_id, '❌ No tickets found. Create one with /ticket')
            return

        tickets = SupportTicket.objects.filter(user=user).order_by('-created_at')[:5]
        if not tickets:
            self.send_message(chat_id, '📭 You have no tickets yet. Use /ticket to create one.')
            return

        msg = '📋 *Your Recent Tickets:*\n\n'
        for t in tickets:
            status_emoji = {'open': '🟡', 'in_progress': '🔵', 'resolved': '✅', 'closed': '⛔'}.get(t.status, '❓')
            msg += f"{status_emoji} `{t.ticket_id}` — {t.subject[:40]}\n"

        msg += '\nUse /status TICKET_ID for details.'
        self.send_message(chat_id, msg, parse_mode='Markdown')

    def _search_kb(self, chat_id: str, query: str) -> None:
        if not query:
            self.send_message(chat_id, '🔍 Please provide a search term after /kb\nExample: /kb how to withdraw')
            return
        try:
            from api.support.services.knowledge_base.KBSearchService import kb_search_service
            results = kb_search_service.search(query, limit=5)
            if not results:
                self.send_message(chat_id, f'❌ No results found for "{query}".\n\nTry /ticket to create a support request.')
                return

            msg = f'📚 *Search Results for "{query}":*\n\n'
            for r in results:
                msg += f"• {r['title']}\n  your-site.com/kb/{r.get('slug','')}\n\n"
            self.send_message(chat_id, msg, parse_mode='Markdown')
        except Exception as e:
            logger.error(f'KB search from Telegram failed: {e}')

    def _submit_rating(self, chat_id: str, ticket_id: str, rating: int, username: str) -> None:
        from api.support.models import SupportTicket, TicketRating
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            ticket = SupportTicket.objects.get(ticket_id=ticket_id)
            user   = User.objects.filter(username=f'tg_{username}').first() or ticket.user
            TicketRating.objects.get_or_create(ticket=ticket, defaults={'user': user, 'rating': rating})
            stars = '⭐' * rating
            self.send_message(chat_id, f'{stars} Thank you for rating {rating}/5!')
        except Exception as e:
            logger.error(f'TG rating failed: {e}')

    # ─────────────────────────────────────
    # ADMIN NOTIFICATIONS
    # ─────────────────────────────────────
    def notify_admin_new_ticket(self, ticket) -> bool:
        if not ADMIN_CHAT:
            return False
        emoji = {'urgent': '🚨', 'high': '⚠️', 'medium': '📢', 'low': 'ℹ️'}.get(ticket.priority, '📢')
        msg   = (
            f"{emoji} *New Support Ticket*\n\n"
            f"🎫 ID: `{ticket.ticket_id}`\n"
            f"👤 User: {ticket.user.username}\n"
            f"📂 Category: {ticket.category}\n"
            f"⚡ Priority: {ticket.priority.upper()}\n"
            f"📝 Subject: {ticket.subject[:100]}\n\n"
            f"🕐 {ticket.created_at.strftime('%d %b %Y %H:%M UTC')}"
        )
        return bool(self.send_message(ADMIN_CHAT, msg, parse_mode='Markdown'))

    def notify_admin_sla_breach(self, ticket, breach_type: str) -> bool:
        if not ADMIN_CHAT:
            return False
        msg = (
            f"🔴 *SLA BREACH ALERT*\n\n"
            f"Ticket: `{ticket.ticket_id}`\n"
            f"Breach: {breach_type}\n"
            f"Priority: {ticket.priority.upper()}\n"
            f"Agent: {ticket.assigned_to.username if ticket.assigned_to else 'Unassigned'}"
        )
        return bool(self.send_message(ADMIN_CHAT, msg, parse_mode='Markdown'))

    def notify_agent_assigned(self, ticket, agent_chat_id: str) -> bool:
        msg = (
            f"📬 *New Ticket Assigned to You*\n\n"
            f"🎫 {ticket.ticket_id}: {ticket.subject[:80]}\n"
            f"⚡ Priority: {ticket.priority.upper()}\n"
            f"📂 Category: {ticket.category}"
        )
        return bool(self.send_message(agent_chat_id, msg, parse_mode='Markdown'))

    # ─────────────────────────────────────
    # SEND MESSAGE
    # ─────────────────────────────────────
    def send_message(self, chat_id: str, text: str, parse_mode: str = None, reply_markup: dict = None) -> dict | None:
        if not BOT_TOKEN:
            logger.warning('Telegram: BOT_TOKEN not configured.')
            return None

        payload = {'chat_id': chat_id, 'text': text[:4096]}
        if parse_mode:
            payload['parse_mode'] = parse_mode
        if reply_markup:
            payload['reply_markup'] = json.dumps(reply_markup)

        try:
            resp = requests.post(f'{BASE_URL}/sendMessage', json=payload, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            logger.error(f'Telegram send failed [{resp.status_code}]: {resp.text[:200]}')
            return None
        except requests.RequestException as e:
            logger.error(f'Telegram request error: {e}')
            return None

    def _answer_callback(self, callback_id: str) -> None:
        if not BOT_TOKEN:
            return
        try:
            requests.post(
                f'{BASE_URL}/answerCallbackQuery',
                json    = {'callback_query_id': callback_id},
                timeout = 10,
            )
        except Exception:
            pass

    def set_webhook(self, webhook_url: str) -> bool:
        if not BOT_TOKEN:
            return False
        try:
            resp = requests.post(
                f'{BASE_URL}/setWebhook',
                json    = {'url': webhook_url, 'max_connections': 40, 'drop_pending_updates': True},
                timeout = 15,
            )
            ok = resp.json().get('ok', False)
            logger.info(f'Telegram webhook set: {ok}')
            return ok
        except Exception as e:
            logger.error(f'Set webhook failed: {e}')
            return False

    # ─────────────────────────────────────
    # STATE MANAGEMENT (Redis in production)
    # ─────────────────────────────────────
    def _get_state(self, chat_id: str) -> dict:
        try:
            from django.core.cache import cache
            state = cache.get(f'tg_state:{chat_id}')
            return state or {'state': self.STATE_IDLE}
        except Exception:
            return USER_STATES.get(chat_id, {'state': self.STATE_IDLE})

    def _set_state(self, chat_id: str, state: dict) -> None:
        try:
            from django.core.cache import cache
            cache.set(f'tg_state:{chat_id}', state, timeout=1800)  # 30 min
        except Exception:
            USER_STATES[chat_id] = state

    def _clear_state(self, chat_id: str) -> None:
        try:
            from django.core.cache import cache
            cache.delete(f'tg_state:{chat_id}')
        except Exception:
            USER_STATES.pop(chat_id, None)

    def _show_main_menu(self, chat_id: str, name: str) -> dict:
        self.send_message(chat_id,
            f"Hi {name}! How can I help you?",
            reply_markup=self.MAIN_KEYBOARD
        )
        return {'ok': True}


# Singleton
telegram_bot = TelegramSupportBot()