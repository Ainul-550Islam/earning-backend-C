# api/admin_panel/commission_engine.py
"""Advertiser commission and revenue share calculation engine."""
from __future__ import annotations
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Platform commission rates
DEFAULT_PUBLISHER_SHARE = Decimal('0.70')   # 70% to publisher
PLATFORM_FEE            = Decimal('0.30')   # 30% platform fee
ADVERTISER_MARKUP       = Decimal('1.20')   # Advertiser pays 120% of publisher payout


class CommissionEngine:
    """Calculate advertiser/publisher revenue split."""

    @classmethod
    def calculate_advertiser_cost(cls, publisher_payout: Decimal) -> Dict:
        """What advertiser is charged for a conversion."""
        advertiser_cost = (publisher_payout * ADVERTISER_MARKUP).quantize(Decimal('0.0001'))
        platform_fee    = (advertiser_cost - publisher_payout).quantize(Decimal('0.0001'))
        return {
            'publisher_payout': float(publisher_payout),
            'platform_fee':     float(platform_fee),
            'advertiser_cost':  float(advertiser_cost),
            'platform_fee_pct': float(PLATFORM_FEE * 100),
        }

    @classmethod
    def calculate_publisher_payout(cls, advertiser_cpa: Decimal) -> Decimal:
        """What publisher earns from advertiser CPA."""
        return (advertiser_cpa * DEFAULT_PUBLISHER_SHARE).quantize(Decimal('0.0001'), ROUND_HALF_UP)

    @classmethod
    def get_revenue_split(cls, conversion_id: Any) -> Dict:
        """Get revenue split for a completed conversion."""
        try:
            from api.promotions.models import TaskSubmission
            sub = TaskSubmission.objects.get(pk=conversion_id)
            pub_payout = Decimal(str(sub.reward_usd or 0))
            return cls.calculate_advertiser_cost(pub_payout)
        except Exception as e:
            return {'error': str(e)}

    @classmethod
    def get_platform_revenue(cls, days: int = 30) -> Dict:
        """Calculate total platform revenue for period."""
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Sum
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.promotions.models import TaskSubmission
            total_publisher = float(
                TaskSubmission.objects.filter(
                    created_at__gte=cutoff, status='approved'
                ).aggregate(t=Sum('reward_usd'))['t'] or 0
            )
            return {
                'period_days':       days,
                'total_publisher_payout': total_publisher,
                'platform_revenue':  round(total_publisher * float(PLATFORM_FEE / DEFAULT_PUBLISHER_SHARE), 4),
                'total_advertiser_charged': round(total_publisher / float(DEFAULT_PUBLISHER_SHARE), 4),
            }
        except Exception as e:
            return {'error': str(e)}


commission_engine = CommissionEngine()