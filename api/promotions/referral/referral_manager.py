# =============================================================================
# promotions/referral/referral_manager.py
# Multi-Level Referral Program — CPAlead 5%, MyLead 5% ongoing
# L1=5%, L2=2%, L3=1% of referred publisher's earnings
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import hashlib, logging

logger = logging.getLogger(__name__)

REFERRAL_RATES = {
    1: Decimal('0.05'),   # L1: 5%
    2: Decimal('0.02'),   # L2: 2%
    3: Decimal('0.01'),   # L3: 1%
}


class ReferralManager:
    """Multi-level referral tracking and commission payout."""

    def get_referral_link(self, user_id: int) -> dict:
        from django.conf import settings
        base = getattr(settings, 'SITE_URL', 'https://yourplatform.com')
        ref_code = hashlib.md5(f'ref_{user_id}_salt'.encode()).hexdigest()[:10].upper()
        return {
            'referral_code': ref_code,
            'referral_link': f'{base}/register/?ref={ref_code}',
            'commission_structure': {f'Level {l}': f'{float(r*100):.0f}%' for l, r in REFERRAL_RATES.items()},
            'description': 'Earn commission on your referred publishers\' earnings for life!',
        }

    def register_referral(self, new_user_id: int, referral_code: str) -> bool:
        """Record that new_user was referred by referral_code owner."""
        from api.promotions.models import ReferralCommissionLog
        from django.core.cache import cache
        referrer_id = self._get_user_by_ref_code(referral_code)
        if not referrer_id or referrer_id == new_user_id:
            return False
        cache.set(f'referral_parent:{new_user_id}', referrer_id, timeout=3600 * 24 * 365 * 10)
        logger.info(f'Referral registered: user={new_user_id} referred_by={referrer_id}')
        return True

    def process_referral_commission(self, earner_id: int, earning_amount: Decimal) -> list:
        """When earner gets a payout, give % to their referrers."""
        from django.core.cache import cache
        from api.promotions.models import PromotionTransaction
        awarded = []
        current_user = earner_id
        for level in range(1, 4):
            parent_id = cache.get(f'referral_parent:{current_user}')
            if not parent_id: break
            rate = REFERRAL_RATES[level]
            commission = (earning_amount * rate).quantize(Decimal('0.0001'))
            if commission > Decimal('0'):
                try:
                    PromotionTransaction.objects.create(
                        user_id=parent_id,
                        transaction_type='referral',
                        amount=commission,
                        status='completed',
                        notes=f'Referral L{level} — ${commission} from user #{earner_id}',
                        metadata={'type': 'referral', 'level': level, 'earner_id': earner_id, 'rate': str(rate)},
                    )
                    awarded.append({'level': level, 'referrer': parent_id, 'commission': str(commission)})
                except Exception as e:
                    logger.error(f'Referral commission failed L{level}: {e}')
            current_user = parent_id
        return awarded

    def get_referral_stats(self, user_id: int) -> dict:
        from api.promotions.models import PromotionTransaction
        total = PromotionTransaction.objects.filter(
            user_id=user_id, transaction_type='referral',
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        referral_info = self.get_referral_link(user_id)
        return {
            'user_id': user_id,
            'referral_link': referral_info['referral_link'],
            'referral_code':  referral_info['referral_code'],
            'total_commission': str(total),
            'referred_count': 0,  # Query in production
            'commission_structure': referral_info['commission_structure'],
        }

    def _get_user_by_ref_code(self, ref_code: str) -> int:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        for user in User.objects.filter(is_active=True):
            code = hashlib.md5(f'ref_{user.id}_salt'.encode()).hexdigest()[:10].upper()
            if code == ref_code.upper():
                return user.id
        return None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_referral_view(request):
    mgr = ReferralManager()
    return Response(mgr.get_referral_stats(request.user.id))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_referral_link_view(request):
    mgr = ReferralManager()
    return Response(mgr.get_referral_link(request.user.id))
