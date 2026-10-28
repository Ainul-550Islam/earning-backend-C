"""
api/support/cpa/fraud_detector.py
FILE 8 — AI Fraud Pattern Detection in Support Tickets

Support ticket-এ fraud pattern detect করো।
Auto-flag suspicious tickets।
Security team-কে alert করো।
"""
import re, logging
from django.core.cache import cache
logger = logging.getLogger(__name__)

class SupportFraudDetector:
    """Detects fraudulent support claims in tickets"""

    # Fraud indicators in ticket content
    FRAUD_PATTERNS = {
        'fake_offer_claim': {
            'patterns': [r'i did\s+\d+\s+offers?', r'completed\s+\d{3,}\s+offers?', r'all\s+\d+\s+offers?'],
            'weight': 0.4,
        },
        'impossible_amount': {
            'patterns': [r'missing\s+\$\d{4,}', r'not\s+received\s+\$\d{3,}'],
            'weight': 0.5,
        },
        'multiple_accounts': {
            'patterns': [r'my (other|another|second|multiple) account', r'account\s+\d+\s+and\s+account'],
            'weight': 0.6,
        },
        'coordinated_fraud': {
            'patterns': [r'my (friends?|team|group|members?)', r'we all (completed|did|finished)'],
            'weight': 0.5,
        },
        'vpn_proxy': {
            'patterns': [r'vpn', r'proxy', r'different (country|location|ip)'],
            'weight': 0.3,
        },
        'threatening': {
            'patterns': [r'chargeback', r'paypal dispute', r'credit card dispute'],
            'weight': 0.7,
        },
    }

    def analyze_ticket(self, ticket) -> dict:
        text    = f"{ticket.subject} {ticket.description}".lower()
        score   = 0.0
        flags   = []

        for pattern_name, config in self.FRAUD_PATTERNS.items():
            for pattern in config['patterns']:
                if re.search(pattern, text, re.IGNORECASE):
                    score += config['weight']
                    flags.append(pattern_name)
                    break

        # Check user history
        history_score = self._check_user_history(ticket.user)
        score        += history_score['score']
        if history_score['flags']:
            flags.extend(history_score['flags'])

        score = min(score, 1.0)
        risk  = 'critical' if score >= 0.8 else 'high' if score >= 0.6 else 'medium' if score >= 0.4 else 'low'

        result = {
            'fraud_score':  round(score, 3),
            'risk_level':   risk,
            'flags':        list(set(flags)),
            'should_review':score >= 0.5,
            'auto_flag':    score >= 0.8,
        }

        if result['auto_flag']:
            self._auto_flag_ticket(ticket, result)

        return result

    def _check_user_history(self, user) -> dict:
        score = 0.0
        flags = []
        try:
            from api.support.models import SupportTicket
            from api.support.cpa.models import OfferDispute
            dispute_count = OfferDispute.objects.filter(user=user).count()
            rejected      = OfferDispute.objects.filter(user=user, status='rejected').count()
            if dispute_count > 5:
                score += 0.2
                flags.append('high_dispute_count')
            if rejected > 2:
                score += 0.3
                flags.append('multiple_rejected_disputes')
        except Exception:
            pass
        return {'score': score, 'flags': flags}

    def _auto_flag_ticket(self, ticket, result: dict) -> None:
        try:
            from api.support.models import TicketTag, TicketTagging
            tag, _ = TicketTag.objects.get_or_create(name='fraud-suspected')
            TicketTagging.objects.get_or_create(ticket=ticket, tag=tag)
            ticket.priority = 'urgent'
            ticket.escalated = True
            from django.utils import timezone
            ticket.escalated_at = timezone.now()
            ticket.save(update_fields=['priority','escalated','escalated_at'])
            # Alert security team
            try:
                from api.support.integrations.slack_integration import slack_integration
                slack_integration.notify_new_ticket(ticket)
            except Exception:
                pass
            logger.warning(f'FRAUD FLAGGED: {ticket.ticket_id} score={result["fraud_score"]}')
        except Exception as e:
            logger.error(f'Auto-flag failed: {e}')

support_fraud_detector = SupportFraudDetector()