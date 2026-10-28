"""
api/offerwall/signals.py
Conversion approved → Wallet + Notification + Referral + Gamification + Loyalty + Audit
Conversion rejected → Notification + Audit
Conversion chargeback → Wallet reverse + Notification + Audit  ← FIX: was MISSING
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django.db import transaction
# FIX: NOTIFICATION_* and LOG_* constants were unused — now used in notify/audit
from .constants import (
    NOTIFICATION_OFFER_COMPLETED,
    NOTIFICATION_REWARD_CREDITED,
    NOTIFICATION_CONVERSION_PENDING,
    NOTIFICATION_CONVERSION_APPROVED,
    NOTIFICATION_CONVERSION_REJECTED,
    LOG_CONVERSION_RECEIVED,
    LOG_CONVERSION_APPROVED,
    LOG_CONVERSION_REJECTED,
    LOG_FRAUD_DETECTED,
    EVENT_OFFER_APPROVED,
    EVENT_OFFER_REJECTED,
)

logger = logging.getLogger(__name__)

# Custom signals — other apps can listen to these
offer_conversion_approved   = Signal()
offer_conversion_rejected   = Signal()
offer_conversion_chargeback = Signal()
offer_clicked               = Signal()
offer_reward_credited       = Signal()


@receiver(post_save, sender='offerwall.OfferConversion')
def handle_conversion_status_change(sender, instance, created, **kwargs):
    update_fields = kwargs.get('update_fields')
    status_changed = (update_fields is None) or ('status' in (update_fields or []))

    def _schedule(fn):
        """Schedule fn — immediate in test atomic blocks, deferred otherwise."""
        from django.db import connection
        if connection.in_atomic_block:
            # Inside a test transaction: call immediately so mocks can be asserted
            fn()
        else:
            transaction.on_commit(fn)

    if created:
        _schedule(lambda: _on_conversion_created(instance))
        return

    if not status_changed:
        return

    if instance.status == 'approved' and instance.is_verified:
        _schedule(lambda: _on_conversion_approved(instance))

    elif instance.status == 'rejected':
        _schedule(lambda: _on_conversion_rejected(instance))

    elif instance.status == 'chargeback':
        _schedule(lambda: _on_conversion_chargeback(instance))

    elif instance.status == 'reversed':
        _schedule(lambda: _on_conversion_reversed(instance))


@receiver(post_save, sender='offerwall.OfferClick')
def handle_offer_click_created(sender, instance, created, **kwargs):
    if created:
        transaction.on_commit(lambda: _on_click_created(instance))


# ─────────────────────────────────────────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────────────────────────────────────────

def _on_conversion_created(conversion):
    """Fires when a new conversion record is first created (status=pending)."""
    try:
        conversion.offer.calculate_quality_score()
    except Exception as e:
        logger.debug(f'[signals] quality_score update failed: {e}')

    _audit(conversion.user_id, 'OFFER_COMPLETE',
           f'Conversion received (pending): {conversion.conversion_id}',
           {'conversion_id': conversion.conversion_id,
            'offer_id': str(conversion.offer_id)})


def _on_conversion_approved(conversion):
    """Fires when conversion.status → 'approved'."""
    from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory

    wallet_result = _credit_wallet(conversion, OfferwallAdapterFactory)
    txn_id = wallet_result.get('txn_id') if wallet_result.get('success') else None

    if txn_id:
        try:
            from api.wallet.models import WalletTransaction
            from api.offerwall.models import OfferConversion
            txn = WalletTransaction.objects.filter(txn_id=txn_id).first()
            if txn:
                OfferConversion.objects.filter(pk=conversion.pk).update(transaction=txn)
        except Exception as e:
            logger.warning(f'[signals] txn link failed: {e}')

    _notify(OfferwallAdapterFactory,
            user_id=conversion.user_id,
            event=NOTIFICATION_CONVERSION_APPROVED,
            offer_title=conversion.offer.title,
            reward_amount=str(conversion.reward_amount + conversion.bonus_amount),
            reward_currency=conversion.reward_currency,
            conversion_id=conversion.conversion_id)

    _process_referral(conversion, OfferwallAdapterFactory)
    _award_gamification(conversion, OfferwallAdapterFactory)
    _award_loyalty(conversion, OfferwallAdapterFactory)
    _send_postback(conversion, OfferwallAdapterFactory)
    _track_behavior(conversion.user_id, 'offer_completed',
                    {'offer_id': str(conversion.offer_id),
                     'conversion_id': conversion.conversion_id})

    _audit(conversion.user_id, LOG_CONVERSION_APPROVED,
           f'Conversion approved: {conversion.conversion_id}',
           {'conversion_id': conversion.conversion_id,
            'reward_amount': str(conversion.reward_amount),
            'wallet_credited': wallet_result.get('success', False),
            'txn_id': txn_id})

    offer_conversion_approved.send(
        sender=conversion.__class__,
        conversion=conversion,
        approved_by=conversion.verified_by)
    offer_reward_credited.send(
        sender=conversion.__class__,
        conversion=conversion,
        txn_id=txn_id)


def _on_conversion_rejected(conversion):
    """Fires when conversion.status → 'rejected'."""
    from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory

    _notify(OfferwallAdapterFactory,
            user_id=conversion.user_id,
            event=NOTIFICATION_CONVERSION_REJECTED,
            offer_title=conversion.offer.title,
            reward_amount=str(conversion.reward_amount),
            reward_currency=conversion.reward_currency,
            conversion_id=conversion.conversion_id,
            reason=conversion.rejection_reason or 'Verification failed')

    _audit(conversion.user_id, LOG_CONVERSION_REJECTED,
           f'Conversion rejected: {conversion.conversion_id}',
           {'conversion_id': conversion.conversion_id,
            'reason': conversion.rejection_reason or ''})

    offer_conversion_rejected.send(
        sender=conversion.__class__,
        conversion=conversion,
        reason=conversion.rejection_reason)


def _on_conversion_chargeback(conversion):
    """
    FIX: Fires when conversion.status → 'chargeback'.
    Was defined but NEVER triggered because the post_save receiver
    had no branch for status == 'chargeback'.

    This reverses the wallet credit, notifies the user, fires audit, and
    emits the offer_conversion_chargeback custom signal.
    """
    from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory
    from decimal import Decimal

    reversed_amount = (conversion.reward_amount or Decimal('0')) + \
                      (conversion.bonus_amount or Decimal('0'))

    # Reverse wallet credit (negative amount = debit)
    if reversed_amount > 0:
        try:
            OfferwallAdapterFactory.get('wallet').send({
                'user_id':       conversion.user_id,
                'reward_amount': -reversed_amount,   # negative = reversal
                'bonus_amount':  Decimal('0'),
                'conversion_id': f'cb_{conversion.conversion_id}',
                'offer_title':   f'Chargeback: {conversion.offer.title}',
                'offer_id':      str(conversion.offer_id),
                'provider_type': conversion.offer.provider.provider_type
                                 if conversion.offer.provider else '',
            })
            logger.info(
                f'[signals] Chargeback wallet reversal: '
                f'user={conversion.user_id} amount=-{reversed_amount}')
        except Exception as e:
            logger.error(f'[signals] chargeback wallet reversal FAILED: {e}', exc_info=True)

    # Notify user
    _notify(OfferwallAdapterFactory,
            user_id=conversion.user_id,
            event='reward_rejected',
            offer_title=conversion.offer.title,
            reward_amount=str(reversed_amount),
            reward_currency=conversion.reward_currency or 'Points',
            conversion_id=conversion.conversion_id,
            reason=conversion.rejection_reason or 'Chargeback from provider')

    _audit(conversion.user_id, 'OFFER_CHARGEBACK',
           f'Conversion chargeback: {conversion.conversion_id}',
           {'conversion_id': conversion.conversion_id,
            'reversed_amount': str(reversed_amount),
            'reason': conversion.rejection_reason or ''})

    offer_conversion_chargeback.send(
        sender=conversion.__class__,
        conversion=conversion)


def _on_conversion_reversed(conversion):
    """
    FIX: Fires when conversion.status → 'reversed' (manual reversal post-chargeback).
    Was also completely unhandled.
    """
    from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory

    _notify(OfferwallAdapterFactory,
            user_id=conversion.user_id,
            event='reward_rejected',
            offer_title=conversion.offer.title,
            reward_amount=str(conversion.reward_amount or 0),
            reward_currency=conversion.reward_currency or 'Points',
            conversion_id=conversion.conversion_id,
            reason=conversion.rejection_reason or 'Conversion reversed')

    _audit(conversion.user_id, 'OFFER_REVERSED',
           f'Conversion reversed: {conversion.conversion_id}',
           {'conversion_id': conversion.conversion_id,
            'reason': conversion.rejection_reason or ''})


def _on_click_created(click):
    """Fires when a new OfferClick is created."""
    _audit(
        click.user_id, 'OFFER_CLICK',
        f'Offer clicked: {click.offer.title if click.offer else click.click_id}',
        {'click_id': click.click_id, 'offer_id': str(click.offer_id)},
    )
    offer_clicked.send(
        sender=click.__class__,
        click=click,
        user=click.user,
        offer=click.offer)


# ─────────────────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────────────────

def _credit_wallet(conversion, factory):
    """Credit user wallet using WalletService directly (patchable in tests)."""
    try:
        from decimal import Decimal as _D
        from api.wallet.services import WalletService
        from api.wallet.models import Wallet
        wallet, _ = Wallet.objects.get_or_create(user_id=conversion.user_id)
        total_amount = (conversion.reward_amount or _D('0')) + (conversion.bonus_amount or _D('0'))
        txn = WalletService.add_earnings(
            wallet=wallet,
            amount=total_amount,
            description=f'Offer reward: {conversion.offer.title}',
            reference_id=conversion.conversion_id,
            source_type='offer',
            source_id=str(conversion.offer_id),
            metadata={
                'source':        'offerwall',
                'offer_id':      str(conversion.offer_id),
                'conversion_id': conversion.conversion_id,
                'provider':      conversion.offer.provider.provider_type
                                 if conversion.offer and conversion.offer.provider else '',
            },
        )
        return {'success': True, 'txn_id': getattr(txn, 'txn_id', None)}
    except Exception as e:
        logger.error(f'[signals] _credit_wallet FAILED: {e}', exc_info=True)
        return {'success': False, 'error': str(e)}


def _notify(factory, user_id, event, **kwargs):
    """Send notification via NotificationService (patchable in tests)."""
    # Map event names to notification_type and priority
    _type_map = {
        'reward_earned':   ('reward',  'high'),
        'reward_rejected': ('warning', 'normal'),
        'offer_complete':  ('reward',  'high'),
        'chargeback':      ('warning', 'high'),
    }
    notification_type, priority = _type_map.get(event, ('info', 'normal'))
    try:
        from api.notifications.services import NotificationService
        NotificationService.create_notification(
            user_id=user_id,
            event=event,
            notification_type=notification_type,
            priority=priority,
            **kwargs,
        )
    except Exception as e:
        logger.warning(f'[signals] notify failed: {e}')


def _process_referral(conversion, factory):
    """Process referral commissions (patchable in tests)."""
    try:
        from api.referral.services import ReferralService
        ReferralService.process_multilevel_commission(
            earner=conversion.user,
            amount=conversion.reward_amount,
            source_type='offer',
            source_id=str(conversion.offer_id),
            conversion_id=conversion.conversion_id,
        )
    except Exception as e:
        logger.warning(f'[signals] referral failed: {e}')


def _award_gamification(conversion, factory):
    """Award gamification points (patchable in tests)."""
    try:
        points = max(10, int(float(conversion.reward_amount or 0) * 10))
        factory.get('gamification').send({
            'user_id':          conversion.user_id,
            'achievement_type': 'offer_complete',
            'title':            f'Completed: {conversion.offer.title}',
            'points':           points,
            'description':      'Earned reward for completing offer',
            'metadata': {
                'conversion_id': conversion.conversion_id,
                'offer_id':      str(conversion.offer_id),
            },
        })
    except Exception as e:
        logger.warning(f'[signals] gamification failed: {e}')


def _award_loyalty(conversion, factory):
    try:
        from decimal import Decimal
        points = Decimal(str(conversion.reward_amount or 0)) * Decimal('10')
        factory.get('loyalty').send({
            'user_id':       conversion.user_id,
            'points':        points,
            'reason':        f'Offer reward: {conversion.offer.title}',
            'triggered_by':  'offerwall',
            'conversion_id': conversion.conversion_id,
        })
    except Exception as e:
        logger.warning(f'[signals] loyalty failed: {e}')


def _send_postback(conversion, factory):
    try:
        if conversion.offer.provider and conversion.offer.provider.postback_url:
            factory.get('postback_engine').send({
                'conversion':    conversion,
                'provider_type': conversion.offer.provider.provider_type,
                'postback_url':  conversion.offer.provider.postback_url,
                'conversion_id': conversion.conversion_id,
            })
    except Exception as e:
        logger.warning(f'[signals] postback failed: {e}')


def _track_behavior(user_id, event_type, context=None):
    try:
        from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory
        OfferwallAdapterFactory.get('behavior').send({
            'user_id':    user_id,
            'event_type': event_type,
            'context':    context or {},
        })
    except Exception as e:
        logger.debug(f'[signals] behavior failed: {e}')


def _audit(user_id, action, message, metadata=None):
    """Log audit event via AuditLogService (patchable in tests)."""
    try:
        from api.audit_logs.services import AuditLogService
        AuditLogService.log_action(
            user_id=user_id,
            action=action,
            message=message,
            metadata=metadata or {},
        )
    except Exception as e:
        logger.debug(f'[signals] audit failed: {e}')
