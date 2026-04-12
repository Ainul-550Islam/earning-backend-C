# api/promotions/services/referral_service.py
import logging
from decimal import Decimal
logger = logging.getLogger('services.referral')

REFERRAL_COMMISSION_RATE = Decimal('0.05')   # 5% of referee's earnings

class ReferralService:
    def generate_code(self, user_id: int) -> str:
        import hashlib
        return hashlib.md5(f'ref:{user_id}'.encode()).hexdigest()[:8].upper()

    def register_referral(self, referral_code: str, new_user_id: int) -> bool:
        try:
            from api.promotions.models import UserReferral
            from django.contrib.auth import get_user_model
            User = get_user_model()
            referrer = User.objects.filter(referral_code=referral_code).first()
            if not referrer or referrer.id == new_user_id: return False
            UserReferral.objects.get_or_create(referrer_id=referrer.id, referee_id=new_user_id)
            logger.info(f'Referral: {referrer.id} → {new_user_id}')
            return True
        except Exception as e:
            logger.error(f'Referral register failed: {e}'); return False

    def credit_commission(self, referee_id: int, earned_usd: Decimal) -> Decimal:
        """Referee earning থেকে referrer commission pay করে।"""
        commission = (earned_usd * REFERRAL_COMMISSION_RATE).quantize(Decimal('0.0001'))
        if commission <= Decimal('0'):
            return Decimal('0')
        try:
            from api.promotions.models import UserReferral, Wallet
            ref = UserReferral.objects.filter(referee_id=referee_id, is_active=True).first()
            if not ref: return Decimal('0')
            Wallet.objects.filter(user_id=ref.referrer_id).update(balance_usd=models.F('balance_usd') + commission)
            logger.debug(f'Referral commission: referrer={ref.referrer_id} ${commission}')
            return commission
        except Exception as e:
            logger.error(f'Commission credit failed: {e}'); return Decimal('0')

    def get_stats(self, user_id: int) -> dict:
        try:
            from api.promotions.models import UserReferral, PromotionTransaction
            from django.db.models import Count, Sum
            referrals = UserReferral.objects.filter(referrer_id=user_id)
            return {
                'total_referrals': referrals.count(),
                'active':          referrals.filter(is_active=True).count(),
                'total_earned_usd': float(PromotionTransaction.objects.filter(user_id=user_id, transaction_type='referral_commission').aggregate(t=Sum('amount_usd'))['t'] or 0),
                'referral_code':   self.generate_code(user_id),
            }
        except Exception: return {}
