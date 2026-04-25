# api/payment_gateways/receivers.py
# Django signal receivers that connect model saves to integration events

import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def connect_all_receivers():
    """Connect all signal receivers. Called from AppConfig.ready()."""
    try:
        from api.payment_gateways.models.deposit import DepositRequest
        from api.payment_gateways.models.core import PayoutRequest, GatewayTransaction

        @receiver(post_save, sender=DepositRequest, weak=False)
        def on_deposit_status_change(sender, instance, created, **kwargs):
            if not created and instance.status == 'completed':
                from api.payment_gateways.events import emit_deposit_completed
                try:
                    emit_deposit_completed(instance.user, instance)
                except Exception as e:
                    logger.error(f'emit_deposit_completed failed: {e}')

        @receiver(post_save, sender=PayoutRequest, weak=False)
        def on_payout_status_change(sender, instance, created, **kwargs):
            if not created and instance.status == 'processing':
                from api.payment_gateways.events import emit_withdrawal_processed
                try:
                    emit_withdrawal_processed(instance.user, instance)
                except Exception as e:
                    logger.error(f'emit_withdrawal_processed failed: {e}')

        logger.debug('payment_gateways receivers connected')
    except Exception as e:
        logger.warning(f'Could not connect payment_gateways receivers: {e}')
