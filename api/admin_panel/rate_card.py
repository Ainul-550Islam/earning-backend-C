# api/admin_panel/rate_card.py
"""Publisher rate cards and payout tier management."""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.core.cache import cache

logger = logging.getLogger(__name__)


class RateCardManager:
    """Manage publisher payout rates and tiers."""

    DEFAULT_TIERS = {
        'bronze':   {'min_monthly': 0,     'max_monthly': 999,   'rate_multiplier': 1.0, 'min_payout': 10},
        'silver':   {'min_monthly': 1000,  'max_monthly': 4999,  'rate_multiplier': 1.1, 'min_payout': 5},
        'gold':     {'min_monthly': 5000,  'max_monthly': 19999, 'rate_multiplier': 1.25, 'min_payout': 1},
        'platinum': {'min_monthly': 20000, 'max_monthly': None,  'rate_multiplier': 1.5, 'min_payout': 1},
    }

    @classmethod
    def get_tiers(cls) -> Dict:
        cached = cache.get('admin_panel:rate_tiers')
        if cached:
            return cached
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            obj = SystemConfig.objects.get(key='publisher_rate_tiers')
            tiers = json.loads(obj.value)
            cache.set('admin_panel:rate_tiers', tiers, 300)
            return tiers
        except Exception:
            return cls.DEFAULT_TIERS

    @classmethod
    def get_publisher_tier(cls, publisher_id: Any, monthly_earnings: float = None) -> Dict:
        if monthly_earnings is None:
            # Calculate from wallet
            try:
                from api.wallet.models import WalletTransaction
                from django.db.models import Sum
                from datetime import timedelta
                from django.utils import timezone
                cutoff = timezone.now() - timedelta(days=30)
                monthly_earnings = float(WalletTransaction.objects.filter(
                    wallet__user_id=publisher_id,
                    transaction_type='earning',
                    created_at__gte=cutoff
                ).aggregate(t=Sum('amount'))['t'] or 0)
            except Exception:
                monthly_earnings = 0

        tiers = cls.get_tiers()
        publisher_tier = 'bronze'
        for tier_name, tier_config in tiers.items():
            min_m = tier_config.get('min_monthly', 0)
            max_m = tier_config.get('max_monthly')
            if monthly_earnings >= min_m and (max_m is None or monthly_earnings <= max_m):
                publisher_tier = tier_name

        tier_config = tiers.get(publisher_tier, cls.DEFAULT_TIERS['bronze'])
        return {
            'publisher_id': publisher_id,
            'tier': publisher_tier,
            'monthly_earnings': monthly_earnings,
            'rate_multiplier': tier_config.get('rate_multiplier', 1.0),
            'min_payout': tier_config.get('min_payout', 10),
        }

    @classmethod
    def update_tier(cls, tier_name: str, config: Dict, actor=None) -> bool:
        tiers = cls.get_tiers()
        tiers[tier_name] = config
        try:
            from api.admin_panel.models.config import SystemConfig
            import json
            SystemConfig.objects.update_or_create(
                key='publisher_rate_tiers',
                defaults={'value': json.dumps(tiers), 'group': 'finance', 'value_type': 'json'}
            )
            cache.delete('admin_panel:rate_tiers')
            return True
        except Exception:
            return False

    @classmethod
    def get_rate_card_for_offer(cls, offer_id: Any, publisher_tier: str = 'bronze') -> Dict:
        """Get adjusted payout rate for a publisher tier."""
        try:
            from api.offer_inventory.models import Offer
            offer = Offer.objects.get(pk=offer_id)
            base_payout = float(offer.payout)
            multiplier = cls.DEFAULT_TIERS.get(publisher_tier, {}).get('rate_multiplier', 1.0)
            return {
                'offer_id': offer_id, 'base_payout': base_payout,
                'tier': publisher_tier, 'multiplier': multiplier,
                'adjusted_payout': round(base_payout * multiplier, 4),
            }
        except Exception as e:
            return {'offer_id': offer_id, 'error': str(e)}

rate_card_manager = RateCardManager()