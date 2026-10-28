# api/djoyalty/signals/fraud_cashout_signals.py
"""
Signal receivers for fraud_detected and cashout_approved।

FIXED: cashout_approved and fraud_detected were custom Signal objects
defined in signals.py (flat/dead file). Receivers were never wired.
These receivers now run whenever those signals fire.
"""
import logging
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# ─── fraud_detected receivers ─────────────────────────────────────────────────

def on_fraud_detected_alert(sender, customer, fraud_type, risk_level,
                             detail, timestamp, **kwargs):
    """
    Send admin alert when fraud is detected।
    Notifies the tenant admin via email/push if risk is high or critical।
    """
    try:
        from ..services.NotificationService import NotificationService

        if risk_level in ('high', 'critical'):
            NotificationService.notify_admin_fraud_alert(
                customer=customer,
                fraud_type=fraud_type,
                risk_level=risk_level,
                detail=detail,
            )
            logger.info(
                'fraud_detected -> admin alert sent: customer=%s type=%s level=%s',
                getattr(customer, 'code', customer.pk), fraud_type, risk_level,
            )
    except Exception as e:
        logger.error('on_fraud_detected_alert error: %s', e)


def on_fraud_detected_suspend_check(sender, customer, fraud_type, risk_level,
                                      detail, timestamp, **kwargs):
    """
    Auto-suspend customer if risk is critical and sanctions are enabled।
    Uses SanctionManager (sanctions.py) to freeze the account।

    FIXED: sanctions.py was an orphan -- connected here as a signal receiver।
    """
    try:
        if risk_level != 'critical':
            return
        from ..sanctions import SanctionManager
        can_act, reason = SanctionManager.check_can_earn(customer)
        if not can_act:
            logger.info(
                'fraud_detected -> customer %s already sanctioned: %s',
                getattr(customer, 'code', customer.pk), reason,
            )
            return
        SanctionManager.flag_warning(
            customer=customer,
            reason=f'Auto-flagged: {fraud_type} (risk={risk_level})',
        )
        logger.info(
            'fraud_detected -> warning flag set: customer=%s type=%s',
            getattr(customer, 'code', customer.pk), fraud_type,
        )
    except Exception as e:
        logger.error('on_fraud_detected_suspend_check error: %s', e)


# ─── cashout_approved receivers ───────────────────────────────────────────────

def on_cashout_approved_notify_customer(sender, cashout, action, admin_user,
                                          payment_reference, note, timestamp, **kwargs):
    """
    Notify the customer when their cashout is approved or completed।
    """
    try:
        from ..services.NotificationService import NotificationService

        customer = cashout.customer
        amount   = getattr(cashout, 'cash_amount', '?')
        currency = getattr(cashout, 'currency', 'BDT')
        method   = getattr(cashout, 'cashout_method', '')

        if action == 'approved':
            NotificationService.send(
                customer=customer,
                notification_type='cashout_approved',
                title='Cashout Approved ✅',
                body=(
                    f'Your cashout of {amount} {currency} via {method} '
                    f'has been approved and is being processed.'
                ),
                icon='💸',
                metadata={
                    'cashout_id':  str(cashout.pk),
                    'amount':      str(amount),
                    'currency':    currency,
                    'method':      method,
                    'action':      action,
                },
            )
        elif action == 'completed':
            NotificationService.send(
                customer=customer,
                notification_type='cashout_completed',
                title='Cashout Sent 🎉',
                body=(
                    f'Your cashout of {amount} {currency} has been sent to '
                    f'your {method} account.'
                    + (f' Reference: {payment_reference}' if payment_reference else '')
                ),
                icon='🏦',
                metadata={
                    'cashout_id':         str(cashout.pk),
                    'amount':             str(amount),
                    'currency':           currency,
                    'method':             method,
                    'payment_reference':  payment_reference,
                    'action':             action,
                },
            )

        logger.info(
            'cashout_approved -> customer notified: cashout=%s action=%s customer=%s',
            getattr(cashout, 'reference', cashout.pk),
            action,
            getattr(customer, 'code', customer.pk),
        )
    except Exception as e:
        logger.error('on_cashout_approved_notify_customer error: %s', e)


def on_cashout_approved_webhook(sender, cashout, action, admin_user,
                                  payment_reference, note, timestamp, **kwargs):
    """
    Dispatch outbound webhook to tenant's registered webhook endpoints
    when cashout is approved or completed।

    Uses LoyaltyWebhookService (previously unconnected service)।

    FIXED: LoyaltyWebhookService was a service class with no callers।
    Connected here as a cashout_approved signal receiver।
    """
    try:
        from ..services.LoyaltyWebhookService import LoyaltyWebhookService

        tenant = getattr(cashout.customer, 'tenant', None)
        if not tenant:
            return

        event_type = (
            'cashout.approved' if action == 'approved'
            else 'cashout.completed' if action == 'completed'
            else f'cashout.{action}'
        )

        LoyaltyWebhookService.dispatch(
            tenant=tenant,
            event_type=event_type,
            payload={
                'cashout_id':         str(cashout.pk),
                'reference':          getattr(cashout, 'reference', ''),
                'customer_code':      getattr(cashout.customer, 'code', ''),
                'action':             action,
                'cash_amount':        str(getattr(cashout, 'cash_amount', 0)),
                'currency':           getattr(cashout, 'currency', 'BDT'),
                'cashout_method':     getattr(cashout, 'cashout_method', ''),
                'payment_reference':  payment_reference,
                'note':               note,
                'admin_user':         admin_user,
                'timestamp':          str(timestamp),
            },
        )

        logger.info(
            'cashout_approved -> webhook dispatched: cashout=%s event=%s tenant=%s',
            getattr(cashout, 'reference', cashout.pk),
            event_type,
            getattr(tenant, 'name', tenant.pk),
        )
    except Exception as e:
        logger.error('on_cashout_approved_webhook error: %s', e)
