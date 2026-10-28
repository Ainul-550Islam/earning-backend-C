"""
api/support/ai/ai_auto_responder.py
FILE 6/70 — AI Auto-Response System (Claude API)

Ticket create হলে AI auto-draft response তৈরি করবে।
Agent এটা review করে পাঠাবে অথবা auto-send হবে।

Settings:
    ANTHROPIC_API_KEY = 'sk-ant-...'
    AI_AUTO_SEND      = False   # True হলে agent review ছাড়াই পাঠাবে
    AI_AUTO_SEND_CATEGORIES = ['coins', 'referral', 'other']  # শুধু এগুলোতে auto-send
"""
import logging
import requests
import json
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY       = getattr(settings, 'ANTHROPIC_API_KEY', '')
AI_AUTO_SEND            = getattr(settings, 'AI_AUTO_SEND', False)
AI_AUTO_SEND_CATEGORIES = getattr(settings, 'AI_AUTO_SEND_CATEGORIES', ['coins', 'referral'])
ANTHROPIC_API_URL       = 'https://api.anthropic.com/v1/messages'
MODEL                   = 'claude-sonnet-4-20250514'


class AIAutoResponder:
    """
    Claude API দিয়ে ticket-এর auto-response draft করো।
    KB articles + ticket history context ব্যবহার করে।
    """

    SYSTEM_PROMPT = """You are a professional customer support agent for a CPA/earning platform.
Your job is to write helpful, empathetic, and accurate responses to support tickets.

Rules:
1. Always be polite and professional
2. Address the user by name if available
3. Provide specific actionable steps
4. Reference the ticket ID
5. Keep response under 300 words
6. If it's a payment/fraud issue, always escalate and don't make promises about refunds
7. End with an offer to help further
8. Write in the same language as the user's message (Bengali/English/Hindi)

Platform context:
- Users earn coins/rewards by completing tasks and offers
- Withdrawals are processed via bKash, Nagad, PayPal, Payoneer, USDT
- KYC is required for withdrawal
- Payment processing takes 1-3 business days
- Fraud team handles security issues with highest priority"""

    # ─────────────────────────────────────
    # MAIN: DRAFT RESPONSE FOR TICKET
    # ─────────────────────────────────────
    def draft_response(self, ticket) -> dict:
        """
        Ticket-এর জন্য AI response draft করো।
        Returns: {'draft': str, 'confidence': float, 'should_auto_send': bool}
        """
        if not ANTHROPIC_API_KEY:
            return {'draft': '', 'confidence': 0, 'should_auto_send': False, 'error': 'API key not configured'}

        try:
            context = self._build_context(ticket)
            prompt  = self._build_prompt(ticket, context)
            draft   = self._call_claude(prompt)

            if not draft:
                return {'draft': '', 'confidence': 0, 'should_auto_send': False}

            confidence       = self._calculate_confidence(ticket, draft)
            should_auto_send = self._should_auto_send(ticket, confidence)

            result = {
                'draft':           draft,
                'confidence':      confidence,
                'should_auto_send':should_auto_send,
                'generated_at':    timezone.now().isoformat(),
            }

            # Save draft to DB
            self._save_draft(ticket, draft, confidence)

            # Auto-send if configured
            if should_auto_send:
                self._auto_send(ticket, draft)

            logger.info(f'AI draft for {ticket.ticket_id}: confidence={confidence:.2f}, auto_send={should_auto_send}')
            return result

        except Exception as e:
            logger.error(f'AI auto-responder failed for {ticket.ticket_id}: {e}')
            return {'draft': '', 'confidence': 0, 'should_auto_send': False, 'error': str(e)}

    def draft_response_async(self, ticket_id: str) -> str:
        """Celery task-এ call করো"""
        try:
            from api.support.models import SupportTicket
            ticket = SupportTicket.objects.get(ticket_id=ticket_id)
            result = self.draft_response(ticket)
            return result.get('draft', '')
        except Exception as e:
            logger.error(f'Async draft failed: {e}')
            return ''

    # ─────────────────────────────────────
    # CONTEXT BUILDER
    # ─────────────────────────────────────
    def _build_context(self, ticket) -> dict:
        """Ticket context collect করো"""
        context = {
            'kb_articles':    [],
            'similar_tickets':[],
            'user_history':   {},
        }

        # KB articles suggest করো
        try:
            from api.support.services.knowledge_base.KBRecommendService import kb_recommend_service
            context['kb_articles'] = kb_recommend_service.suggest_for_ticket(
                ticket.subject, ticket.category, limit=3
            )
        except Exception:
            pass

        # Similar resolved tickets
        try:
            from api.support.models import SupportTicket
            from django.db.models import Q
            similar = SupportTicket.objects.filter(
                category   = ticket.category,
                status     = 'resolved',
                admin_response__isnull = False,
            ).exclude(admin_response='').order_by('-resolved_at')[:3]

            context['similar_tickets'] = [
                {'subject': t.subject[:80], 'response': t.admin_response[:200]}
                for t in similar
            ]
        except Exception:
            pass

        # User history
        try:
            from api.support.models import SupportTicket
            prev = SupportTicket.objects.filter(
                user     = ticket.user,
                status__in = ['resolved', 'closed'],
            ).count()
            context['user_history'] = {
                'previous_tickets': prev,
                'username':         ticket.user.username,
                'email':            ticket.user.email,
            }
        except Exception:
            pass

        return context

    # ─────────────────────────────────────
    # PROMPT BUILDER
    # ─────────────────────────────────────
    def _build_prompt(self, ticket, context: dict) -> str:
        prompt_parts = [
            f"Write a support response for the following ticket:\n\n",
            f"TICKET DETAILS:\n",
            f"- Ticket ID: {ticket.ticket_id}\n",
            f"- Category: {ticket.category}\n",
            f"- Priority: {ticket.priority}\n",
            f"- Subject: {ticket.subject}\n",
            f"- User: {ticket.user.username}\n",
            f"- Description:\n{ticket.description[:1000]}\n\n",
        ]

        # KB context
        if context['kb_articles']:
            prompt_parts.append("RELEVANT KNOWLEDGE BASE ARTICLES:\n")
            for art in context['kb_articles']:
                prompt_parts.append(f"- {art.get('title', '')}: {art.get('summary', '')[:100]}\n")
            prompt_parts.append("\n")

        # Similar resolved tickets
        if context['similar_tickets']:
            prompt_parts.append("SIMILAR RESOLVED TICKETS (for reference):\n")
            for t in context['similar_tickets']:
                prompt_parts.append(f"- Subject: {t['subject']}\n  Response: {t['response']}\n")
            prompt_parts.append("\n")

        # Special instructions by category
        category_instructions = {
            'payment':    "\nIMPORTANT: This is a payment issue. Express urgency, ask for transaction ID, do NOT promise refunds.",
            'fraud':      "\nIMPORTANT: FRAUD ALERT — Escalate immediately, ask for details carefully, notify security team.",
            'withdrawal': "\nIMPORTANT: Ask for payment method details and transaction ID. Mention 1-3 business day processing.",
            'kyc':        "\nIMPORTANT: Guide user through KYC steps. Be clear about required documents.",
            'coins':      "\nIMPORTANT: Ask for offer name/ID and screenshot. Will investigate within 24 hours.",
        }
        if ticket.category in category_instructions:
            prompt_parts.append(category_instructions[ticket.category])

        prompt_parts.append("\n\nWrite a helpful, professional response:")
        return ''.join(prompt_parts)

    # ─────────────────────────────────────
    # CLAUDE API CALL
    # ─────────────────────────────────────
    def _call_claude(self, prompt: str) -> str:
        try:
            response = requests.post(
                ANTHROPIC_API_URL,
                headers = {
                    'x-api-key':         ANTHROPIC_API_KEY,
                    'anthropic-version': '2023-06-01',
                    'content-type':      'application/json',
                },
                json    = {
                    'model':      MODEL,
                    'max_tokens': 600,
                    'system':     self.SYSTEM_PROMPT,
                    'messages':   [{'role': 'user', 'content': prompt}],
                },
                timeout = 30,
            )

            if response.status_code != 200:
                logger.error(f'Claude API error [{response.status_code}]: {response.text[:200]}')
                return ''

            data    = response.json()
            content = data.get('content', [])
            if content and content[0].get('type') == 'text':
                return content[0]['text'].strip()
            return ''

        except requests.Timeout:
            logger.error('Claude API timeout')
            return ''
        except Exception as e:
            logger.error(f'Claude API call failed: {e}')
            return ''

    # ─────────────────────────────────────
    # CONFIDENCE + AUTO-SEND
    # ─────────────────────────────────────
    def _calculate_confidence(self, ticket, draft: str) -> float:
        """
        Response quality score 0.0-1.0.
        Low confidence = agent review করবে।
        High confidence = auto-send করতে পারে।
        """
        score = 0.5  # Base score

        # Ticket ID mentioned
        if ticket.ticket_id in draft:
            score += 0.1

        # Appropriate length
        word_count = len(draft.split())
        if 50 <= word_count <= 300:
            score += 0.1
        elif word_count < 20:
            score -= 0.2

        # Category-specific keywords present
        category_keywords = {
            'payment':    ['transaction', 'payment', 'investigate', '24 hours'],
            'withdrawal': ['processed', 'business days', 'method'],
            'coins':      ['offer', 'investigate', 'screenshot', '24 hours'],
            'account':    ['account', 'verify', 'secure'],
            'kyc':        ['kyc', 'document', 'verification'],
        }
        keywords = category_keywords.get(ticket.category, [])
        if keywords:
            found = sum(1 for kw in keywords if kw.lower() in draft.lower())
            score += (found / len(keywords)) * 0.2

        # Fraud/payment always lower confidence (needs human review)
        if ticket.category in ['fraud', 'payment']:
            score = min(score, 0.5)

        # Urgent tickets always need human review
        if ticket.priority == 'urgent':
            score = min(score, 0.4)

        return min(max(score, 0.0), 1.0)

    def _should_auto_send(self, ticket, confidence: float) -> bool:
        if not AI_AUTO_SEND:
            return False
        if ticket.category not in AI_AUTO_SEND_CATEGORIES:
            return False
        if ticket.priority in ['urgent', 'high']:
            return False
        return confidence >= 0.75

    # ─────────────────────────────────────
    # SAVE + SEND
    # ─────────────────────────────────────
    def _save_draft(self, ticket, draft: str, confidence: float) -> None:
        """AI draft DB-তে save করো যাতে agent দেখতে পারে"""
        try:
            from api.support.models import TicketMessage
            from django.contrib.auth import get_user_model
            User = get_user_model()

            # System user
            system = User.objects.filter(is_superuser=True).first()
            if not system:
                return

            TicketMessage.objects.create(
                ticket      = ticket,
                sender      = system,
                content     = f'🤖 [AI Draft - Confidence: {confidence:.0%}]\n\n{draft}',
                is_agent    = True,
                is_internal = True,  # Only agents see this
            )
        except Exception as e:
            logger.warning(f'Save AI draft failed: {e}')

    def _auto_send(self, ticket, draft: str) -> None:
        """High confidence → auto-send response"""
        try:
            from api.support.services.ticket.TicketService import ticket_service
            from django.contrib.auth import get_user_model
            User = get_user_model()

            system = User.objects.filter(is_superuser=True).first()
            if not system:
                return

            ticket_service.add_message(
                ticket_id   = ticket.ticket_id,
                user        = system,
                content     = draft,
                is_agent    = True,
                is_internal = False,
            )
            logger.info(f'AI auto-sent response for {ticket.ticket_id}')
        except Exception as e:
            logger.error(f'Auto-send failed: {e}')

    # ─────────────────────────────────────
    # BATCH PROCESSING
    # ─────────────────────────────────────
    def process_pending_tickets(self, limit: int = 20) -> dict:
        """Unresponded open tickets-এ AI draft করো"""
        from api.support.models import SupportTicket
        tickets = SupportTicket.objects.filter(
            status          = 'open',
            admin_response  = '',
            assigned_to__isnull = False,
        ).order_by('-priority', 'created_at')[:limit]

        stats = {'processed': 0, 'drafted': 0, 'auto_sent': 0, 'errors': 0}
        for ticket in tickets:
            result = self.draft_response(ticket)
            stats['processed'] += 1
            if result.get('draft'):
                stats['drafted'] += 1
            if result.get('should_auto_send'):
                stats['auto_sent'] += 1
            if result.get('error'):
                stats['errors'] += 1

        return stats


# Singleton
ai_auto_responder = AIAutoResponder()