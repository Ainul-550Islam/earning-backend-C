# =============================================================================
# api/promotions/referral/referral_manager.py  ← PATCHED
# Redis cache-based referral tree সম্পূর্ণ সরানো (data loss risk ছিল!)
# সব api.referral.INTEGRATION_SYSTEM.bridge এ delegate।
# "এক মালিক — api.referral"
# =============================================================================
import logging
from decimal import Decimal
logger = logging.getLogger(__name__)


class ReferralManager:
    """
    Deprecated own logic — now delegates to api.referral.
    Cache-based tree removed (was causing data loss on cache flush).
    """

    def get_referral_link(self, user_id: int) -> dict:
        try:
            from django.contrib.auth import get_user_model
            from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge
            User = get_user_model()
            user = User.objects.get(id=user_id)
            bridge = get_bridge()
            code = bridge.get_referral_code(user)
            from django.conf import settings
            base = getattr(settings, 'FRONTEND_URL', 'https://yourplatform.com')
            return {
                'referral_code': code,
                'referral_link': f'{base}/go/{code}/',
                'commission_structure': {
                    'Level 1': '10%', 'Level 2': '5%', 'Level 3': '2%'
                },
                'description': 'Earn commission on your referrals earnings for life!',
            }
        except Exception as e:
            logger.warning(f'[ReferralManager] get_referral_link failed: {e}')
            return {}

    def register_referral(self, new_user_id: int, referral_code: str) -> bool:
        """Register referral via api.referral bridge (replaces cache-based logic)."""
        try:
            from django.contrib.auth import get_user_model
            from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge
            User = get_user_model()
            new_user = User.objects.get(id=new_user_id)
            result = get_bridge().on_signup(
                new_user=new_user, referral_code=referral_code
            )
            return result.get('success', False)
        except Exception as e:
            logger.error(f'[ReferralManager] register_referral failed: {e}')
            return False

    def process_referral_commission(self, earner_id: int, earning_amount: Decimal) -> list:
        """
        Process referral commission via api.referral bridge.
        REPLACES Redis cache-based tree (data loss risk removed).
        """
        try:
            from django.contrib.auth import get_user_model
            from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge
            User = get_user_model()
            earner = User.objects.get(id=earner_id)
            result = get_bridge().on_task_earned(
                user=earner, amount=float(earning_amount)
            )
            return result.get('commissions', [])
        except Exception as e:
            logger.error(f'[ReferralManager] process_referral_commission failed: {e}')
            return []

    def get_referral_stats(self, user_id: int) -> dict:
        try:
            from django.contrib.auth import get_user_model
            from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge
            User = get_user_model()
            user = User.objects.get(id=user_id)
            return get_bridge().get_user_referral_summary(user)
        except Exception as e:
            logger.warning(f'[ReferralManager] get_referral_stats failed: {e}')
            return {}