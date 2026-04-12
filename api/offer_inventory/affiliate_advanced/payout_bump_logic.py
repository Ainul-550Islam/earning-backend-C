# api/offer_inventory/affiliate_advanced/payout_bump_logic.py
"""Payout Bump Logic — Temporarily increase offer payouts to boost conversions."""
import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class PayoutBumpManager:
    """Apply and manage temporary payout increases."""

    @staticmethod
    def apply_bump(offer_id: str, bump_pct: Decimal = Decimal('10'),
                    duration_hours: int = 24, reason: str = '') -> dict:
        """Apply a payout bump to an offer for N hours."""
        from api.offer_inventory.models import Offer
        offer      = Offer.objects.get(id=offer_id)
        factor     = Decimal('1') + bump_pct / Decimal('100')
        new_payout = (offer.payout_amount * factor).quantize(Decimal('0.0001'))
        new_reward = (offer.reward_amount * factor).quantize(Decimal('0.0001'))

        Offer.objects.filter(id=offer_id).update(
            payout_amount=new_payout, reward_amount=new_reward
        )
        expires_at = timezone.now() + timedelta(hours=duration_hours)
        cache.set(f'payout_bump:{offer_id}', {
            'original_payout': str(offer.payout_amount),
            'original_reward': str(offer.reward_amount),
            'expires_at'     : expires_at.isoformat(),
            'reason'         : reason,
        }, duration_hours * 3600)

        logger.info(f'Payout bump: offer={offer_id} +{bump_pct}% for {duration_hours}h')
        return {
            'offer_id'      : offer_id,
            'original_payout': float(offer.payout_amount),
            'new_payout'    : float(new_payout),
            'bump_pct'      : float(bump_pct),
            'expires_at'    : expires_at.isoformat(),
        }

    @staticmethod
    def rollback_bump(offer_id: str) -> bool:
        """Rollback a payout bump."""
        data = cache.get(f'payout_bump:{offer_id}')
        if not data:
            return False
        from api.offer_inventory.models import Offer
        Offer.objects.filter(id=offer_id).update(
            payout_amount=Decimal(data['original_payout']),
            reward_amount=Decimal(data['original_reward']),
        )
        cache.delete(f'payout_bump:{offer_id}')
        logger.info(f'Payout bump rolled back: offer={offer_id}')
        return True

    @staticmethod
    def rollback_all_expired() -> int:
        """Auto-rollback all expired bumps."""
        from api.offer_inventory.models import Offer
        from django.utils.dateparse import parse_datetime
        rolled_back = 0
        for offer in Offer.objects.filter(status='active'):
            data = cache.get(f'payout_bump:{offer.id}')
            if data:
                expires = parse_datetime(data.get('expires_at', ''))
                if expires and timezone.now() > expires:
                    PayoutBumpManager.rollback_bump(str(offer.id))
                    rolled_back += 1
        return rolled_back

    @staticmethod
    def get_active_bumps() -> list:
        """List all currently active payout bumps."""
        from api.offer_inventory.models import Offer
        bumps = []
        for offer in Offer.objects.filter(status='active')[:500]:
            data = cache.get(f'payout_bump:{offer.id}')
            if data:
                bumps.append({'offer_id': str(offer.id), 'offer_title': offer.title, **data})
        return bumps
