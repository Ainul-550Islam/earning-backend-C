# api/djoyalty/signals/core_signals.py
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from ..models.core import Customer, Txn, Event

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Customer)
def log_customer_created(sender, instance, created, **kwargs):
    if created:
        try:
            Event.objects.create(
                customer=instance,
                action='register',
                description=f'New customer registered: {instance.code}',
                tenant=instance.tenant,
            )
        except Exception as e:
            logger.warning('log_customer_created error: %s', e)

@receiver(post_save, sender=Txn)
def log_transaction(sender, instance, created, **kwargs):
    if created:
        try:
            label = 'discount_purchase' if instance.is_discount else 'purchase'
            Event.objects.create(
                customer=instance.customer,
                action=label,
                description=f'Transaction of {instance.value} recorded',
                tenant=instance.tenant,
            )
        except Exception as e:
            logger.warning('log_transaction error: %s', e)
