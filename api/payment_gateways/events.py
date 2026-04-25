# api/payment_gateways/events.py
# High-level event publisher for payment_gateways

from .integration_system.event_bus import event_bus
from .integration_system.integ_constants import IntegEvent


def emit_deposit_completed(user, deposit):
    event_bus.publish(IntegEvent.DEPOSIT_COMPLETED, {
        'user_id': user.id, 'amount': str(deposit.net_amount),
        'gateway': deposit.gateway, 'reference_id': deposit.reference_id,
    }, priority=0)


def emit_withdrawal_processed(user, payout):
    event_bus.publish(IntegEvent.WITHDRAWAL_PROCESSED, {
        'user_id': user.id, 'amount': str(payout.net_amount),
        'gateway': payout.payout_method, 'reference_id': payout.reference_id,
    }, priority=0)


def emit_conversion_approved(conversion):
    event_bus.publish(IntegEvent.CONVERSION_APPROVED, {
        'publisher_id':  conversion.publisher_id,
        'offer_id':      conversion.offer_id,
        'payout':        str(conversion.payout),
        'conversion_id': conversion.conversion_id,
    }, priority=1)


def emit_fraud_detected(user, risk_score, reasons):
    event_bus.publish(IntegEvent.FRAUD_DETECTED, {
        'user_id': user.id, 'risk_score': risk_score, 'reasons': reasons,
    }, priority=0)


def emit_gateway_down(gateway_name, error=''):
    event_bus.publish(IntegEvent.GATEWAY_DOWN, {
        'gateway': gateway_name, 'error': error,
    }, priority=0)
