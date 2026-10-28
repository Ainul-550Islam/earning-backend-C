# =============================================================================
# api/users/referral/referral_tracker.py  ← PATCHED
# নিজস্ব referral query সম্পূর্ণ সরানো।
# শুধু api.referral.INTEGRATION_SYSTEM.bridge কে call করে।
# "এক মালিক — api.referral"
# =============================================================================
import logging
logger = logging.getLogger(__name__)


class ReferralTracker:
    """
    users app-এর referral bridge.
    কোনো নিজস্ব DB query নেই — সব api.referral থেকে।
    """

    def get_user_summary(self, user) -> dict:
        """User referral summary — api.referral থেকে আনা হয়।"""
        try:
            from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge
            return get_bridge().get_user_referral_summary(user)
        except Exception as e:
            logger.warning(f'[ReferralTracker] get_user_summary failed: {e}')
            return self._empty_summary(user)

    def get_referral_list(self, user, limit: int = 10) -> list:
        """Referred users list."""
        try:
            from api.referral.models import Referral
            return list(
                Referral.objects.filter(referrer=user)
                .select_related('referred_user')
                .order_by('-created_at')
                .values(
                    'referred_user__username',
                    'referred_user__date_joined',
                    'total_commission_earned',
                    'created_at',
                )[:limit]
            )
        except Exception as e:
            logger.warning(f'[ReferralTracker] get_referral_list failed: {e}')
            return []

    def get_referral_stats_for_dashboard(self, user) -> dict:
        """Dashboard widget stats."""
        summary = self.get_user_summary(user)
        return {
            'count':  summary.get('total_referrals', 0),
            'earned': summary.get('total_commission', 0.0),
            'code':   summary.get('referral_code', ''),
            'link':   f"/ref/{summary.get('referral_code', '')}",
        }

    def get_referral_code(self, user) -> str:
        """Get user's referral code."""
        try:
            from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge
            return get_bridge().get_referral_code(user)
        except Exception:
            return getattr(user, 'referral_code', '') or ''

    def process_signup_referral(self, new_user, referral_code: str = '', ip: str = '') -> dict:
        """Called from registration view."""
        try:
            from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge
            return get_bridge().on_signup(
                new_user=new_user, referral_code=referral_code, ip=ip
            )
        except Exception as e:
            logger.error(f'[ReferralTracker] process_signup_referral failed: {e}')
            return {'success': False, 'error': str(e)}

    @staticmethod
    def _empty_summary(user) -> dict:
        return {
            'referral_code': getattr(user, 'referral_code', ''),
            'total_referrals': 0, 'active_referrals': 0,
            'total_commission': 0, 'this_month_commission': 0,
        }