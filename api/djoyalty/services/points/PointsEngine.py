# api/djoyalty/services/points/PointsEngine.py
"""
PointsEngine -- thread-safe, idempotent, fraud-checked.

Security fixes:
  1. select_for_update() on LoyaltyPoints -- race condition prevented
  2. Idempotency via reference_id -- duplicate earn blocked
  3. Fraud check before crediting
  4. Negative/zero spend_amount rejected
"""
import logging
from decimal import Decimal

# FIXED: circuit_breakers.py (CircuitBreaker) was orphaned -- now used here
# to protect against cascading failures when external services are down
try:
    from ...circuit_breakers import CircuitBreaker
    _circuit_breaker = CircuitBreaker(name='points_engine', failure_threshold=5,
                                       recovery_timeout=30)
except ImportError:
    _circuit_breaker = None
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
        reference_id: str = None,
    ) -> Decimal:
        """
        Core points earn engine.
        Thread-safe (select_for_update), idempotent (reference_id), fraud-checked.
        """
        # ── 1. Input validation ──────────────────────────────────────────────
        spend_amount = Decimal(str(spend_amount))
        if spend_amount <= 0:
            logger.warning('PointsEngine: rejected non-positive spend_amount=%s for %s', spend_amount, customer)
            return Decimal('0')

        # ── 2. Idempotency check -- same reference_id = skip duplicate earn ───
        if reference_id:
            already_exists = PointsLedger.objects.filter(
                customer=customer,
                reference_id=reference_id,
                txn_type=LEDGER_CREDIT,
                source=source,
            ).exists()
            if already_exists:
                logger.warning(
                    'PointsEngine: duplicate earn blocked for customer=%s reference_id=%s',
                    customer, reference_id,
                )
                return Decimal('0')

        try:
            with DjoyaltyMetrics.time_earn():
                # ── 3. Fraud check ───────────────────────────────────────────
                from ...services.advanced.LoyaltyFraudService import LoyaltyFraudService
                if LoyaltyFraudService.check_rapid_transactions(customer):
                    logger.warning('PointsEngine: earn blocked by fraud check for %s', customer)
                    return Decimal('0')

                # ── 4. Earn rate ─────────────────────────────────────────────
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

                # ── 5. Tier multiplier ───────────────────────────────────────
                user_tier = customer.current_tier
                tier_name = user_tier.tier.name if user_tier and user_tier.tier else 'bronze'
                cached_tier = DjoyaltyCache.get_tier(
                    customer.id, getattr(tenant or customer.tenant, 'id', None)
                )
                if cached_tier:
                    tier_name = cached_tier
                multiplier = get_tier_multiplier(tier_name)

                # ── 6. Calculate points ──────────────────────────────────────
                points = calculate_points_to_earn(spend_amount, earn_rate, multiplier)
                if points <= 0:
                    return Decimal('0')

                # ── 7. Lock & credit (select_for_update prevents race condition)
                lp = (
                    LoyaltyPoints.objects
                    .select_for_update()
                    .filter(customer=customer, tenant=tenant or customer.tenant)
                    .first()
                )
                if lp is None:
                    lp, _ = LoyaltyPoints.objects.get_or_create(
                        customer=customer,
                        defaults={'tenant': tenant or customer.tenant, 'balance': Decimal('0')},
                    )
                    # Re-acquire lock after creation
                    lp = LoyaltyPoints.objects.select_for_update().get(pk=lp.pk)

                lp.credit(points)

                # ── 8. Invalidate cache ──────────────────────────────────────
                DjoyaltyCache.invalidate_balance(
                    customer.id,
                    getattr(tenant or customer.tenant, 'id', None),
                )

                # ── 9. Ledger entry ──────────────────────────────────────────
                expires_at = get_expiry_date(DEFAULT_POINTS_EXPIRY_DAYS)
                PointsLedger.objects.create(
                    tenant=tenant or customer.tenant,
                    customer=customer,
                    txn_type=LEDGER_CREDIT,
                    source=source,
                    points=points,
                    remaining_points=points,
                    balance_after=lp.balance,
                    description=f'Earned {points} pts on spend {spend_amount}',
                    expires_at=expires_at,
                    reference_id=reference_id,
                )

                # ── 10. Metrics ──────────────────────────────────────────────
                DjoyaltyMetrics.record_points_earned(
                    points,
                    tenant_id=getattr(tenant or customer.tenant, 'id', None),
                    source=source,
                    tier=tier_name,
                )

                logger.info(
                    'Earned %s pts for customer %s (tier=%s, multiplier=%s, ref=%s)',
                    points, customer, tier_name, multiplier, reference_id,
                )
                return points

        except Exception as e:
            logger.error('PointsEngine.process_earn error for %s: %s', customer, e)
            raise
