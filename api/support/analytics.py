# api/support/analytics.py
"""
Support analytics — tracks events to your analytics app.
Wraps the analytics adapter for support-specific event tracking.
"""
import logging

logger = logging.getLogger(__name__)


class SupportAnalytics:
    """Track support events to analytics system."""

    def _track(self, event: str, user=None, props: dict = None) -> bool:
        """Core tracking — delegates to analytics adapter."""
        try:
            from api.support.integrations.integ_adapter import analytics_adapter
            return analytics_adapter.track(event, user=user, props=props or {})
        except Exception as e:
            logger.debug(f'SupportAnalytics._track [{event}]: {e}')
            return False

    # ── Ticket Events ─────────────────────────────────────────

    def track_ticket_created(self, ticket) -> None:
        self._track('support.ticket.created', user=ticket.user, props={
            'ticket_id': ticket.ticket_id,
            'category':  ticket.category,
            'priority':  ticket.priority,
            'channel':   ticket.channel,
        })

    def track_ticket_resolved(self, ticket, resolution_hours: float = 0) -> None:
        self._track('support.ticket.resolved', user=ticket.user, props={
            'ticket_id':        ticket.ticket_id,
            'category':         ticket.category,
            'priority':         ticket.priority,
            'resolution_hours': resolution_hours,
        })

    def track_ticket_escalated(self, ticket) -> None:
        self._track('support.ticket.escalated', user=ticket.user, props={
            'ticket_id': ticket.ticket_id,
            'priority':  ticket.priority,
        })

    def track_ticket_rated(self, ticket, score: int) -> None:
        self._track('support.ticket.rated', user=ticket.user, props={
            'ticket_id': ticket.ticket_id,
            'score':     score,
            'category':  ticket.category,
        })

    # ── Chat Events ───────────────────────────────────────────

    def track_chat_started(self, session) -> None:
        self._track('support.chat.started', user=session.user, props={
            'session_id': str(session.session_id),
        })

    def track_chat_ended(self, session, duration_seconds: int = 0) -> None:
        self._track('support.chat.ended', user=session.user, props={
            'session_id':       str(session.session_id),
            'duration_seconds': duration_seconds,
            'rated':            session.rating is not None,
        })

    def track_chat_message_sent(self, session, is_agent: bool = False) -> None:
        self._track('support.chat.message_sent', props={
            'session_id': str(session.session_id),
            'is_agent':   is_agent,
        })

    # ── Dispute Events ────────────────────────────────────────

    def track_dispute_submitted(self, dispute) -> None:
        self._track('support.dispute.submitted', user=dispute.user, props={
            'offer_id':  dispute.offer_id,
            'amount':    float(dispute.expected_amount),
        })

    def track_dispute_approved(self, dispute) -> None:
        self._track('support.dispute.approved', user=dispute.user, props={
            'offer_id':   dispute.offer_id,
            'amount':     float(dispute.expected_amount),
            'auto':       'auto' in (dispute.agent_notes or '').lower(),
            'confidence': dispute.confidence_score,
        })

    def track_dispute_rejected(self, dispute) -> None:
        self._track('support.dispute.rejected', user=dispute.user, props={
            'offer_id': dispute.offer_id,
            'amount':   float(dispute.expected_amount),
        })

    # ── KB Events ─────────────────────────────────────────────

    def track_kb_article_viewed(self, article, user=None) -> None:
        self._track('support.kb.article_viewed', user=user, props={
            'article_slug': article.slug,
            'category':     article.category.slug if article.category else '',
        })

    def track_kb_search(self, query: str, results_count: int, user=None) -> None:
        self._track('support.kb.search', user=user, props={
            'query':         query,
            'results_count': results_count,
        })

    # ── FAQ Events ────────────────────────────────────────────

    def track_faq_viewed(self, faq) -> None:
        self._track('support.faq.viewed', props={
            'faq_id':   faq.id,
            'category': faq.category,
        })

    def track_faq_helpful_vote(self, faq, helpful: bool, user=None) -> None:
        self._track('support.faq.helpful_vote', user=user, props={
            'faq_id':   faq.id,
            'helpful':  helpful,
        })

    # ── SLA Events ────────────────────────────────────────────

    def track_sla_breach(self, ticket, breach_type: str) -> None:
        self._track('support.sla.breach', props={
            'ticket_id':   ticket.ticket_id,
            'breach_type': breach_type,
            'priority':    ticket.priority,
            'category':    ticket.category,
        })

    # ── Agent Events ──────────────────────────────────────────

    def track_agent_status_change(self, agent, new_status: str) -> None:
        self._track('support.agent.status_change', user=agent.user, props={
            'new_status': new_status,
        })


support_analytics = SupportAnalytics()