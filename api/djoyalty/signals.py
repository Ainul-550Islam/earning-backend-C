from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Customer, Txn, Event 

@receiver(post_save, sender=Customer) 
def log_customer_created(sender, instance, created, **kwargs):
    """নতুন Customer তৈরি হলে Event log করো"""
    if created:
        try:
            Event.objects.create(
                customer=instance,
                action='register',
                description=f'New customer registered with code: {instance.code}'
            )
        except Exception:
            pass  


@receiver(post_save, sender=Txn) 
def log_transaction(sender, instance, created, **kwargs):
    """Transaction তৈরি হলে Event log করো"""
    if created:
        try:
            
            label = 'discount_purchase' if instance.is_discount else 'purchase'
            Event.objects.create(
                customer=instance.customer,
                action=label,
                description=f'Transaction of {instance.value} recorded'
            )
        except Exception:
            pass