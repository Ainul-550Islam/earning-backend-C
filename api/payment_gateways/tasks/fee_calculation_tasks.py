# tasks/fee_calculation_tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

@shared_task
def recalculate_gateway_fees():
    """
    Recalculate fee totals for recent transactions.
    Useful when fee rules change and need retroactive recalculation.
    """
    from api.payment_gateways.models.core import GatewayTransaction
    from api.payment_gateways.models.gateway_config import GatewayFeeRule
    from django.utils import timezone
    from datetime import timedelta

    since = timezone.now() - timedelta(days=7)
    count = 0
    for txn in GatewayTransaction.objects.filter(created_at__gte=since, status='pending'):
        try:
            rule = GatewayFeeRule.objects.filter(
                gateway__name=txn.gateway, transaction_type=txn.transaction_type,
                is_active=True
            ).first()
            if rule:
                new_fee = rule.calculate(txn.amount)
                if new_fee != txn.fee:
                    txn.fee       = new_fee
                    txn.net_amount= txn.amount - new_fee
                    txn.save(update_fields=['fee', 'net_amount'])
                    count += 1
        except Exception as e:
            logger.warning(f'Fee recalc failed for txn {txn.id}: {e}')
    logger.info(f'Recalculated fees for {count} transactions')
    return {'recalculated': count}

@shared_task
def sync_gateway_fee_rules():
    """Sync fee rules from gateway API if available."""
    from api.payment_gateways.constants import GATEWAY_FEES
    from api.payment_gateways.models.core import PaymentGateway
    from api.payment_gateways.models.gateway_config import GatewayFeeRule
    from decimal import Decimal

    updated = 0
    for gw_name, fee_rate in GATEWAY_FEES.items():
        try:
            gw = PaymentGateway.objects.get(name=gw_name)
            GatewayFeeRule.objects.update_or_create(
                gateway=gw, transaction_type='deposit', is_active=True,
                defaults={
                    'fee_type':  'percentage',
                    'fee_value': Decimal(str(fee_rate * 100)),
                    'min_fee':   Decimal('0'),
                }
            )
            updated += 1
        except Exception as e:
            logger.warning(f'Fee rule sync failed for {gw_name}: {e}')
    logger.info(f'Fee rules synced for {updated} gateways')
    return {'updated': updated}
