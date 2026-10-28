# api/support/use_cases.py
"""
Use Cases — application-level business operations (Clean Architecture).
Each class = one atomic operation.
Use cases call services, selectors, and integrations.
Controllers (views) call use cases, not services directly.
"""
import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


class CreateTicketUseCase:
    """
    UC-001: Create a support ticket.
    Input:  user, subject, description, category, priority, channel, screenshot
    Output: SupportTicket | None + error_message
    """
    def execute(self, user, data: dict, request=None) -> dict:
        from api.support.logic import determine_ticket_priority
        from api.support.validator import validate_ticket_subject, validate_ticket_description
        from api.support.services import ticket_service
        from api.support.hooks import ticket_hooks

        # Validate
        try:
            data['subject']     = validate_ticket_subject(data.get('subject', ''))
            data['description'] = validate_ticket_description(data.get('description', ''))
        except Exception as e:
            return {'success': False, 'error': str(e), 'ticket': None}

        # Apply pre-create hooks
        data = ticket_hooks.pre_create(data, user)

        # Auto-set priority from category if not given
        if not data.get('priority') and data.get('category'):
            data['priority'] = determine_ticket_priority(data['category'], user=user)

        # Create
        try:
            ticket = ticket_service.create(user, data, request=request)
            ticket_hooks.post_create(ticket)
            return {'success': True, 'ticket': ticket, 'error': None}
        except Exception as e:
            logger.error(f'CreateTicketUseCase: {e}')
            return {'success': False, 'error': 'Failed to create ticket.', 'ticket': None}


class ReplyToTicketUseCase:
    """
    UC-002: Reply to a ticket (user or agent).
    Input:  ticket_id, sender, content, is_agent, is_internal
    Output: TicketMessage | None + error
    """
    def execute(self, ticket_id: str, sender, content: str,
                is_agent: bool = False, is_internal: bool = False) -> dict:
        from api.support.selectors import get_ticket_for_user
        from api.support.services import ticket_service
        from api.support.exceptions import TicketNotFound, TicketClosed

        if not content or len(content.strip()) < 1:
            return {'success': False, 'error': 'Content cannot be empty.', 'message': None}

        ticket = get_ticket_for_user(ticket_id, sender)
        if not ticket:
            return {'success': False, 'error': 'Ticket not found.', 'message': None}

        if ticket.status in ('closed', 'spam'):
            return {'success': False, 'error': 'Ticket is closed.', 'message': None}

        try:
            msg = ticket_service.add_message(
                ticket.ticket_id, sender, content.strip(),
                is_agent=is_agent, is_internal=is_internal
            )
            return {'success': True, 'message': msg, 'error': None}
        except Exception as e:
            logger.error(f'ReplyToTicketUseCase: {e}')
            return {'success': False, 'error': 'Failed to send reply.', 'message': None}


class ResolveTicketUseCase:
    """
    UC-003: Resolve a ticket (agent/admin only).
    Input:  ticket_id, agent, resolution_message
    Output: success, ticket | error
    """
    def execute(self, ticket_id: str, agent, resolution: str = '') -> dict:
        from api.support.services import ticket_service
        from api.support.hooks import ticket_hooks

        try:
            ticket = ticket_service.resolve(ticket_id, agent, resolution)
            ticket_hooks.post_resolve(ticket)
            return {'success': True, 'ticket': ticket, 'error': None}
        except Exception as e:
            logger.error(f'ResolveTicketUseCase: {e}')
            return {'success': False, 'error': str(e), 'ticket': None}


class RateTicketUseCase:
    """
    UC-004: Submit CSAT rating for a resolved ticket.
    Input:  ticket_id, user, score (1-5), comment
    Output: success | error
    """
    def execute(self, ticket_id: str, user, score: int, comment: str = '') -> dict:
        from api.support.validator import validate_csat_rating
        from api.support.selectors import get_ticket_for_user
        from django.utils import timezone
        from api.support.models import TicketRating

        try:
            score = validate_csat_rating(score)
        except Exception as e:
            return {'success': False, 'error': str(e)}

        ticket = get_ticket_for_user(ticket_id, user)
        if not ticket:
            return {'success': False, 'error': 'Ticket not found.'}
        if ticket.user != user:
            return {'success': False, 'error': 'Not your ticket.'}

        ticket.satisfaction_rating = score
        ticket.rating_comment      = comment or ''
        ticket.rated_at            = timezone.now()
        ticket.save(update_fields=['satisfaction_rating', 'rating_comment', 'rated_at'])

        TicketRating.objects.update_or_create(
            ticket=ticket,
            defaults={'user': user, 'score': score, 'review_text': comment or ''},
        )

        # Award gamification points
        try:
            from api.support.integrations.project_specific.gamification_bridge import gamification_bridge
            gamification_bridge.award_rating_points(ticket, score)
        except Exception:
            pass

        return {'success': True}


class SubmitOfferDisputeUseCase:
    """
    UC-005: Submit an offer dispute.
    Input:  user, offer_id, expected_amount, click_id, offer_name, description
    Output: success, dispute, ticket | error
    """
    def execute(self, user, data: dict) -> dict:
        from api.support.logic import can_submit_offer_dispute
        from api.support.validator import validate_dispute_amount, validate_offer_id
        from api.support.services import offer_dispute_service

        # Check limits
        can_submit, reason = can_submit_offer_dispute(user)
        if not can_submit:
            return {'success': False, 'error': reason, 'dispute': None, 'ticket': None}

        # Validate
        try:
            data['offer_id']        = validate_offer_id(data.get('offer_id', ''))
            data['expected_amount'] = validate_dispute_amount(data.get('expected_amount', 0))
        except Exception as e:
            return {'success': False, 'error': str(e), 'dispute': None, 'ticket': None}

        # Create dispute + ticket
        result = offer_dispute_service.create(user, data)
        return result


class StartChatSessionUseCase:
    """
    UC-006: Start a live chat session.
    Input:  user
    Output: ChatSession | error
    """
    def execute(self, user) -> dict:
        from api.support.selectors import get_support_settings
        from api.support.services import livechat_service

        settings_obj = get_support_settings()
        if settings_obj and not settings_obj.chat_widget_enabled:
            return {'success': False, 'error': 'Live chat is currently disabled.', 'session': None}
        if settings_obj and settings_obj.maintenance_mode:
            return {'success': False, 'error': 'Support in maintenance mode.', 'session': None}

        try:
            session = livechat_service.start(user)
            return {'success': True, 'session': session, 'error': None}
        except Exception as e:
            logger.error(f'StartChatSessionUseCase: {e}')
            return {'success': False, 'error': 'Failed to start chat.', 'session': None}


class EscalateTicketUseCase:
    """
    UC-007: Escalate a ticket (agent/admin).
    Input:  ticket_id, agent, reason
    Output: success | error
    """
    def execute(self, ticket_id: str, agent, reason: str = '') -> dict:
        from api.support.selectors import get_ticket_by_id
        from api.support.services import ticket_service
        from django.utils import timezone

        ticket = get_ticket_by_id(ticket_id)
        if not ticket:
            return {'success': False, 'error': 'Ticket not found.'}
        if ticket.escalated:
            return {'success': False, 'error': 'Already escalated.'}

        ticket.escalated    = True
        ticket.escalated_at = timezone.now()
        ticket.priority     = 'urgent'
        ticket.save(update_fields=['escalated', 'escalated_at', 'priority'])

        try:
            from api.support.integrations.integ_handler import integ_handler
            integ_handler.on_ticket_escalated(ticket, reason=reason)
        except Exception:
            pass

        return {'success': True, 'ticket': ticket}


class MarkFAQHelpfulUseCase:
    """
    UC-008: Mark a FAQ as helpful or not.
    Input:  faq_id, helpful (bool)
    Output: success, new ratio
    """
    def execute(self, faq_id: int, helpful: bool) -> dict:
        from api.support.selectors import get_faq_by_id

        faq = get_faq_by_id(faq_id)
        if not faq:
            return {'success': False, 'error': 'FAQ not found.'}

        if helpful:
            faq.helpful_yes += 1
        else:
            faq.helpful_no += 1
        faq.save(update_fields=['helpful_yes', 'helpful_no'])

        return {
            'success': True,
            'helpful_yes': faq.helpful_yes,
            'helpful_no':  faq.helpful_no,
            'ratio':       faq.helpful_ratio,
        }