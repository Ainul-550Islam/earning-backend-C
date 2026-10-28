# =============================================================================
# api/promotions/services/referral_service.py  ← PATCHED
# এই ফাইলের নিজস্ব referral logic সম্পূর্ণ সরানো হয়েছে।
# সব call এখন api.referral মডিউলে যায়।
# "এক কাজের জন্য একটাই মালিক — api.referral"
# =============================================================================
import logging
logger = logging.getLogger('services.referral')


class ReferralService:
    """
    DEPRECATED own logic.
    এখন শুধু api.referral.INTEGRATION_SYSTEM.bridge এ delegate করে।
    """

    def generate_code(self, user_id: int) -> str:
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge
            return get_bridge().get_referral_code(user)
        except Exception as e:
            logger.warning(f'generate_code fallback: {e}')
            return ''

    def register_referral(self, referral_code: str, new_user_id: int) -> bool:
        try:
            from django.contrib.auth import get_user_model
            from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge
            User = get_user_model()
            new_user = User.objects.get(id=new_user_id)
            result = get_bridge().on_signup(new_user=new_user, referral_code=referral_code)
            return result.get('success', False)
        except Exception as e:
            logger.error(f'register_referral failed: {e}')
            return False

    def credit_commission(self, referee_id: int, earned_usd, **kwargs):
        """Deprecated — commissions handled by api.referral automatically via signals."""
        logger.debug('credit_commission: handled by api.referral signal system')
        return 0

    def get_stats(self, user_id: int) -> dict:
        try:
            from django.contrib.auth import get_user_model
            from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge
            User = get_user_model()
            user = User.objects.get(id=user_id)
            return get_bridge().get_user_referral_summary(user)
        except Exception as e:
            logger.warning(f'get_stats failed: {e}')
            return {}