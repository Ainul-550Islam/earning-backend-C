# api/support/sanctions.py
"""
Sanctions system — actions taken against users who abuse support.
Rate limiting, temporary bans, dispute restrictions.
"""
import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Cache key prefixes
PREFIX_DISPUTE_BAN = 'support:sanction:dispute_ban'
PREFIX_TICKET_BAN  = 'support:sanction:ticket_ban'
PREFIX_CHAT_BAN    = 'support:sanction:chat_ban'
PREFIX_STRIKE      = 'support:sanction:strike'


class SupportSanctionsManager:
    """
    Manages user sanctions for support system abuse.
    Sanctions are stored in cache (Redis) and DB.
    """

    # ── Dispute Sanctions ─────────────────────────────────────

    def can_submit_dispute(self, user) -> tuple:
        """
        Check if user can submit a dispute right now.
        Returns: (can_submit: bool, reason: str, wait_seconds: int)
        """
        from api.support.constants import MAX_OFFER_DISPUTES_PER_WEEK

        # Check Redis ban first (fast)
        ban_key = f'{PREFIX_DISPUTE_BAN}:{user.id}'
        ban     = cache.get(ban_key)
        if ban:
            ttl = cache.ttl(ban_key) if hasattr(cache, 'ttl') else 3600
            return False, ban.get('reason', 'Dispute submission restricted.'), ttl

        # Check weekly limit
        from api.support.repositories import dispute_repo
        count = dispute_repo.count_user_disputes_this_week(user)
        if count >= MAX_OFFER_DISPUTES_PER_WEEK:
            return False, f'Maximum {MAX_OFFER_DISPUTES_PER_WEEK} disputes per week reached.', 0

        # Check fraud risk
        try:
            from api.support.integrations.integ_adapter import fraud_adapter
            risk = fraud_adapter.get_risk_score(user)
            if risk.get('is_critical'):
                return False, 'Account risk level too high for dispute submission.', 0
        except Exception:
            pass

        return True, 'OK', 0

    def ban_dispute_submission(self, user, reason: str, hours: int = 24) -> None:
        """Temporarily ban user from submitting disputes."""
        ban_key = f'{PREFIX_DISPUTE_BAN}:{user.id}'
        cache.set(ban_key, {
            'reason':    reason,
            'banned_at': timezone.now().isoformat(),
            'hours':     hours,
        }, timeout=hours * 3600)
        logger.warning(f'Dispute ban: user={user.id} reason={reason} hours={hours}')

    def lift_dispute_ban(self, user) -> None:
        """Remove dispute ban."""
        cache.delete(f'{PREFIX_DISPUTE_BAN}:{user.id}')

    # ── Strike System ─────────────────────────────────────────

    def add_strike(self, user, reason: str) -> int:
        """Add a strike to user's record. Returns total strikes."""
        strike_key = f'{PREFIX_STRIKE}:{user.id}'
        strikes    = cache.get(strike_key, [])
        strikes.append({
            'reason':    reason,
            'timestamp': timezone.now().isoformat(),
        })
        # Strikes expire after 30 days
        cache.set(strike_key, strikes, timeout=30 * 86400)
        total = len(strikes)
        logger.warning(f'Strike added: user={user.id} total={total} reason={reason}')

        # Auto-ban after 3 strikes
        if total >= 3:
            self.ban_dispute_submission(
                user,
                reason=f'Auto-banned after {total} strikes.',
                hours=72
            )

        return total

    def get_strikes(self, user) -> list:
        """Get user's current strikes."""
        return cache.get(f'{PREFIX_STRIKE}:{user.id}', [])

    def clear_strikes(self, user) -> None:
        """Clear all strikes (after appeal resolved)."""
        cache.delete(f'{PREFIX_STRIKE}:{user.id}')
        self.lift_dispute_ban(user)

    # ── Spam Detection ────────────────────────────────────────

    def check_spam_ticket(self, user, subject: str, description: str) -> dict:
        """
        Quick spam check for new tickets.
        Returns: {is_spam: bool, confidence: float, reason: str}
        """
        # Rate check: too many tickets in 1 hour
        rate_key  = f'support:ticket_rate:{user.id}'
        tick_count = cache.get(rate_key, 0)
        if tick_count >= 5:
            return {'is_spam': True, 'confidence': 0.9, 'reason': 'Rate limit exceeded'}
        cache.set(rate_key, tick_count + 1, timeout=3600)

        # Try AI spam detection
        try:
            from api.support.integrations.project_specific.ai_engine_adapter import ai_engine_adapter
            from api.support.models import SupportTicket
            class FakeTicket:
                def __init__(self, s, d, c):
                    self.subject = s; self.description = d; self.category = c; self.user = user
            fake = FakeTicket(subject, description, 'other')
            result = ai_engine_adapter.is_spam_ticket(fake)
            return result
        except Exception:
            pass

        return {'is_spam': False, 'confidence': 0.0, 'reason': ''}

    # ── Summary ───────────────────────────────────────────────

    def get_user_sanction_status(self, user) -> dict:
        """Get complete sanction status for a user."""
        dispute_ban = cache.get(f'{PREFIX_DISPUTE_BAN}:{user.id}')
        strikes     = self.get_strikes(user)
        return {
            'dispute_banned':   bool(dispute_ban),
            'dispute_ban_info': dispute_ban,
            'strike_count':     len(strikes),
            'strikes':          strikes[-3:],  # Last 3
        }


sanctions_manager = SupportSanctionsManager()