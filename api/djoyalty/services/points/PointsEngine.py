# api/djoyalty/services/points/PointsEngine.py
import logging
from decimal import Decimal
from django.db import transaction
from ...models.points import LoyaltyPoints, PointsLedger
from ...choices import LEDGER_CREDIT, LEDGER_SOURCE_PURCHASE
from ...utils import calculate_points_to_earn, get_tier_multiplier, get_expiry_date
from ...constants import DEFAULT_EARN_RATE, DEFAULT_POINTS_EXPIRY_DAYS
from ...cache_backends import DjoyaltyCache
from ...metrics import DjoyaltyMetrics

logger = logging.getLogger(__name__)


class PointsEngine:
    @staticmethod
    @transaction.atomic
    def process_earn(
        customer,
        spend_amount: Decimal,
        txn=None,
        tenant=None,
        source=LEDGER_SOURCE_PURCHASE,
    ) -> Decimal:
        """
        Core points earn engine।
        Thread-safe (atomic), cached, instrumented।
        """
        try:
            with DjoyaltyMetrics.time_earn():
                # Get earn rate from DB or use default
                earn_rate = DEFAULT_EARN_RATE
                try:
                    from ...models.points import PointsRate
                    rate_obj = PointsRate.objects.filter(
                        tenant=tenant or customer.tenant, is_active=True
                    ).first()
                    if rate_obj:
                        earn_rate = rate_obj.earn_rate
                except Exception:
                    pass

                # Get tier multiplier
                user_tier = customer.current_tier
                tier_name = user_tier.tier.name if user_tier and user_tier.tier else 'bronze'

                # Check cache for tier multiplier
                cached_tier = DjoyaltyCache.get_tier(customer.id, getattr(tenant or customer.tenant, 'id', None))
                if cached_tier:
                    tier_name = cached_tier

                multiplier = get_tier_multiplier(tier_name)

                # Calculate points
                points = calculate_points_to_earn(
                    Decimal(str(spend_amount)), earn_rate, multiplier
                )

                if points <= 0:
                    return Decimal('0')

                # Get or create LoyaltyPoints
                lp, _ = LoyaltyPoints.objects.get_or_create(
                    customer=customer,
                    defaults={'tenant': tenant or customer.tenant, 'balance': Decimal('0')},
                )
                lp.credit(points)

                # Invalidate balance cache
                DjoyaltyCache.invalidate_balance(
                    customer.id,
                    getattr(tenant or customer.tenant, 'id', None),
                )

                # Create ledger entry
                expires_at = get_expiry_date(DEFAULT_POINTS_EXPIRY_DAYS)
                ledger = PointsLedger.objects.create(
                    tenant=tenant or customer.tenant,
                    customer=customer,
                    txn_type=LEDGER_CREDIT,
                    source=source,
                    points=points,
                    remaining_points=points,
                    balance_after=lp.balance,
                    description=f'Earned {points} pts on spend {spend_amount}',
                    expires_at=expires_at,
                )

                # Record metric
                DjoyaltyMetrics.record_points_earned(
                    points,
                    tenant_id=getattr(tenant or customer.tenant, 'id', None),
                    source=source,
                    tier=tier_name,
                )

                logger.info(
                    'Earned %s pts for customer %s (tier=%s, multiplier=%s)',
                    points, customer, tier_name, multiplier,
                )
                return points

        except Exception as e:
            logger.error('PointsEngine.process_earn error for %s: %s', customer, e)
            raise
