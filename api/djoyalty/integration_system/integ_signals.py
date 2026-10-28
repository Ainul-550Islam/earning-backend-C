# api/djoyalty/integration_system/integ_signals.py
"""
Integration Signals -- Django signals -> integration events।
Bridges Django ORM signals to the integration event bus।
Every loyalty model change triggers appropriate integrations।
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver, Signal

logger = logging.getLogger(__name__)

# ─── Custom Integration Signals ──────────────────────────────────────────────

# Fired when any loyalty event needs external notification
loyalty_event_fired = Signal()

# Fired when integration status changes
integration_status_changed = Signal()

# Fired when webhook needs to be sent
webhook_trigger = Signal()

# Fired when data sync is needed
data_sync_required = Signal()


# ─── Auto-connect to loyalty models ──────────────────────────────────────────

def connect_integration_signals():
    """
    Connect all Django model signals to integration handlers।
    Call this in AppConfig.ready()।
    """
    try:
        from ..models.points import PointsLedger
        from ..models.tiers import UserTier
        from ..models.engagement import UserBadge, DailyStreak
        from ..models.redemption import Voucher, RedemptionRequest
        from ..models.cashout import CashoutRequest
        from ..models.advanced import ChurnAlert as _CA
        from ..models.gamification import SpinWheelResult

        post_save.connect(_on_points_ledger_save, sender=PointsLedger, dispatch_uid='integ_points_ledger')
        post_save.connect(_on_usertier_save, sender=UserTier, dispatch_uid='integ_usertier')
        post_save.connect(_on_badge_earned, sender=UserBadge, dispatch_uid='integ_badge')
        post_save.connect(_on_voucher_created, sender=Voucher, dispatch_uid='integ_voucher')
        post_save.connect(_on_cashout_status_change, sender=CashoutRequest, dispatch_uid='integ_cashout')
        post_save.connect(_on_spin_result, sender=SpinWheelResult, dispatch_uid='integ_spin')

        logger.info('IntegrationSignals: connected %d signal handlers', 6)
    except ImportError as e:
        logger.debug('IntegrationSignals: could not connect some signals: %s', e)


# ─── Signal Handlers ─────────────────────────────────────────────────────────

def _on_points_ledger_save(sender, instance, created, **kwargs):
    """PointsLedger saved -> fire points event।"""
    if not created:
        return
    try:
        from .event_bus import EventBus
        from .integ_constants import EventType
        customer = instance.customer
        EventBus.publish(
            EventType.POINTS_EARNED if instance.txn_type == 'credit' else EventType.POINTS_REDEEMED,
            customer=customer,
            data={
                'points': str(instance.points),
                'balance': str(instance.balance_after),
                'source': instance.source,
                'reference': instance.reference_id or '',
            },
        )
    except Exception as e:
        logger.debug('_on_points_ledger_save error: %s', e)


def _on_usertier_save(sender, instance, created, **kwargs):
    """UserTier updated -> fire tier event।"""
    if not instance.is_current:
        return
    try:
        from .event_bus import EventBus
        from .integ_constants import EventType
        EventBus.publish(
            EventType.TIER_UPGRADED,
            customer=instance.customer,
            data={
                'new_tier': instance.tier.name,
                'old_tier': '',
            },
        )
    except Exception as e:
        logger.debug('_on_usertier_save error: %s', e)


def _on_badge_earned(sender, instance, created, **kwargs):
    """Badge earned -> push notification।"""
    if not created:
        return
    try:
        from .event_bus import EventBus
        from .integ_constants import EventType
        EventBus.publish(
            EventType.BADGE_UNLOCKED,
            customer=instance.customer,
            data={'badge_name': instance.badge.name, 'badge_icon': instance.badge.icon},
        )
    except Exception as e:
        logger.debug('_on_badge_earned error: %s', e)


def _on_voucher_created(sender, instance, created, **kwargs):
    """Voucher created -> notify customer।"""
    if not created:
        return
    try:
        from .event_bus import EventBus
        from .integ_constants import EventType
        EventBus.publish(
            EventType.VOUCHER_GENERATED,
            customer=instance.customer,
            data={
                'code': instance.code,
                'discount': f'{instance.discount_value}%' if instance.voucher_type == 'percent'
                            else f'{instance.discount_value} BDT',
                'expires_at': instance.expires_at,
            },
        )
    except Exception as e:
        logger.debug('_on_voucher_created error: %s', e)


def _on_cashout_status_change(sender, instance, created, **kwargs):
    """Cashout status changed -> notify customer + process payment।"""
    if created:
        return
    try:
        from .event_bus import EventBus
        from .integ_constants import EventType
        if instance.status == 'completed':
            EventBus.publish(
                EventType.CASHOUT_COMPLETED,
                customer=instance.customer,
                data={
                    'amount': str(instance.cash_amount),
                    'method': instance.cashout_method,
                    'ref': instance.reference or str(instance.id),
                },
            )
    except Exception as e:
        logger.debug('_on_cashout_status_change error: %s', e)


def _on_spin_result(sender, instance, created, **kwargs):
    """Spin wheel result -> notify customer।"""
    if not created:
        return
    try:
        if instance.points_awarded > 0:
            from .event_bus import EventBus
            from .integ_constants import EventType
            EventBus.publish(
                EventType.POINTS_EARNED,
                customer=instance.customer,
                data={
                    'points': str(instance.points_awarded),
                    'source': 'spin_wheel',
                    'prize': instance.slice_won.label if instance.slice_won else '',
                },
            )
    except Exception as e:
        logger.debug('_on_spin_result error: %s', e)
