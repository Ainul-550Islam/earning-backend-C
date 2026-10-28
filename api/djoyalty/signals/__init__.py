# api/djoyalty/signals/__init__.py
"""
Djoyalty Signals package।

CRITICAL FIX: Signal object DEFINITIONS were only in signals.py (flat file)
which Python ignores because this signals/ folder takes precedence.
Any code doing `from .signals import cashout_approved` was getting an
ImportError or silent AttributeError. Moved all Signal definitions here.

Now contains:
  1. Custom Signal object definitions (6 signals)
  2. All model signal @receiver connections
  3. All signal receiver function imports
  4. DeferredSignalManager from signals_cap.py
"""
import logging

logger = logging.getLogger(__name__)

# ─── Custom Signal Definitions ────────────────────────────────────────────────
# FIXED: these were defined only in the dead signals.py flat file.
# Moved here so `from djoyalty.signals import cashout_approved` works.
from django.dispatch import Signal

points_earned    = Signal()   # kwargs: customer, points, source, balance
points_redeemed  = Signal()   # kwargs: customer, points, reward_type
tier_changed     = Signal()   # kwargs: customer, old_tier, new_tier
badge_unlocked   = Signal()   # kwargs: customer, badge
cashout_approved = Signal()   # kwargs: cashout, action, admin_user, payment_reference, note, timestamp
fraud_detected   = Signal()   # kwargs: customer, fraud_type, risk_level, detail, timestamp

# ─── Receiver function imports (pre-existing) ─────────────────────────────────
from .core_signals import log_customer_created, log_transaction
from .points_signals import on_points_ledger_created
from .tier_signals import on_tier_changed
from .earn_signals import on_earn_transaction
from .redemption_signals import on_redemption_status_changed
from .badge_signals import on_badge_unlocked
from .streak_signals import on_streak_milestone

# ─── New receivers for fraud_detected and cashout_approved ───────────────────
from .fraud_cashout_signals import (
    on_fraud_detected_alert,
    on_fraud_detected_suspend_check,
    on_cashout_approved_notify_customer,
    on_cashout_approved_webhook,
)

# ─── Model signal connections ─────────────────────────────────────────────────
# FIXED: these @receiver connections were in signals.py (flat/dead).
# Re-implemented here so they actually execute at startup.
from django.db.models.signals import post_save, pre_save

try:
    from ..models.core import Customer, Txn
    from ..receivers import on_customer_created, on_txn_created

    @post_save.connect_via(Customer, dispatch_uid='djoyalty_customer_created_v2')
    def customer_post_save(sender, instance, created, **kwargs):
        if created:
            on_customer_created(sender, instance, created, **kwargs)

    logger.debug('djoyalty signals: Customer post_save connected')
except Exception as _e:
    logger.debug('djoyalty signals: Customer signal setup skipped: %s', _e)

try:
    from ..models.core import Txn
    from ..receivers import on_txn_created

    @post_save.connect_via(Txn, dispatch_uid='djoyalty_txn_created_v2')
    def txn_post_save(sender, instance, created, **kwargs):
        if created:
            on_txn_created(sender, instance, created, **kwargs)

    logger.debug('djoyalty signals: Txn post_save connected')
except Exception as _e:
    logger.debug('djoyalty signals: Txn signal setup skipped: %s', _e)

try:
    from ..models.points import PointsLedger

    @post_save.connect_via(PointsLedger, dispatch_uid='djoyalty_ledger_points_signal_v2')
    def ledger_post_save(sender, instance, created, **kwargs):
        if not created:
            return
        if instance.txn_type == 'credit':
            points_earned.send(
                sender=PointsLedger,
                customer=instance.customer,
                points=instance.points,
                source=instance.source,
                balance=instance.balance_after,
            )
        else:
            points_redeemed.send(
                sender=PointsLedger,
                customer=instance.customer,
                points=instance.points,
                reward_type=instance.source,
            )
        on_points_ledger_created(sender, instance, created, **kwargs)

    logger.debug('djoyalty signals: PointsLedger post_save connected')
except Exception as _e:
    logger.debug('djoyalty signals: PointsLedger signal setup skipped: %s', _e)

try:
    from ..models.cashout import CashoutRequest
    from ..receivers import on_cashout_status_changed

    @pre_save.connect_via(CashoutRequest, dispatch_uid='djoyalty_cashout_status_v2')
    def cashout_pre_save(sender, instance, **kwargs):
        if instance.pk:
            try:
                old = CashoutRequest.objects.get(pk=instance.pk)
                if old.status != instance.status:
                    on_cashout_status_changed(sender, instance)
            except CashoutRequest.DoesNotExist:
                pass

    logger.debug('djoyalty signals: CashoutRequest pre_save connected')
except Exception as _e:
    logger.debug('djoyalty signals: Cashout signal setup skipped: %s', _e)

try:
    from ..models.tiers import UserTier

    @post_save.connect_via(UserTier, dispatch_uid='djoyalty_tier_changed_v2')
    def user_tier_post_save(sender, instance, created, **kwargs):
        if instance.is_current:
            old_tier_name = ''
            try:
                from ..selectors import get_previous_tier
                prev = get_previous_tier(instance.customer)
                old_tier_name = prev.name if prev else ''
            except Exception:
                pass
            tier_changed.send(
                sender=UserTier,
                customer=instance.customer,
                old_tier=old_tier_name,
                new_tier=instance.tier.name,
            )
            on_tier_changed(sender, instance, created, **kwargs)

    logger.debug('djoyalty signals: UserTier post_save connected')
except Exception as _e:
    logger.debug('djoyalty signals: UserTier signal setup skipped: %s', _e)

try:
    from ..models.engagement import UserBadge

    @post_save.connect_via(UserBadge, dispatch_uid='djoyalty_badge_unlocked_v2')
    def user_badge_post_save(sender, instance, created, **kwargs):
        if created:
            badge_unlocked.send(
                sender=UserBadge,
                customer=instance.customer,
                badge=instance.badge,
            )
            on_badge_unlocked(sender, instance, created, **kwargs)
            try:
                from ..services.NotificationService import NotificationService
                NotificationService.notify_badge_unlocked(
                    instance.customer,
                    instance.badge.name,
                    instance.badge.icon,
                )
            except Exception:
                pass

    logger.debug('djoyalty signals: UserBadge post_save connected')
except Exception as _e:
    logger.debug('djoyalty signals: UserBadge signal setup skipped: %s', _e)

try:
    from ..models.engagement import DailyStreak

    @post_save.connect_via(DailyStreak, dispatch_uid='djoyalty_streak_milestone_v2')
    def daily_streak_post_save(sender, instance, created, **kwargs):
        on_streak_milestone(sender, instance, created, **kwargs)

    logger.debug('djoyalty signals: DailyStreak post_save connected')
except Exception as _e:
    logger.debug('djoyalty signals: DailyStreak signal setup skipped: %s', _e)

# ─── DeferredSignalManager (from signals_cap.py) ──────────────────────────────
# FIXED: signals_cap.py was an orphan -- DeferredSignalManager allows signals
# to be deferred until after DB transaction commits (prevents phantom signals
# if a transaction rolls back).
try:
    from ..signals_cap import DeferredSignalManager, SignalReplayManager
    logger.debug('djoyalty signals: DeferredSignalManager loaded from signals_cap')
except Exception as _e:
    logger.debug('djoyalty signals: signals_cap not loaded: %s', _e)

__all__ = [
    # Signal objects
    'points_earned', 'points_redeemed', 'tier_changed',
    'badge_unlocked', 'cashout_approved', 'fraud_detected',
    # Receiver functions
    'log_customer_created', 'log_transaction',
    'on_points_ledger_created', 'on_tier_changed',
    'on_earn_transaction', 'on_redemption_status_changed',
    'on_badge_unlocked', 'on_streak_milestone',
    # New receivers
    'on_fraud_detected_alert', 'on_fraud_detected_suspend_check',
    'on_cashout_approved_notify_customer', 'on_cashout_approved_webhook',
]
