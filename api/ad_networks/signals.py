from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import OfferConversion
from api.users.models import User


@receiver(post_save, sender=OfferConversion)
def credit_user_on_approval(sender, instance, created, **kwargs):
    """Credit user balance when conversion is approved"""
    if instance.is_verified and instance.engagement.status != 'approved':
        engagement = instance.engagement
        user = engagement.user
        
        # Update engagement
        engagement.status = 'approved'
        engagement.reward_earned = instance.payout
        engagement.rewarded_at = timezone.now()
        engagement.save()
        
        # Credit user
        user.balance += instance.payout
        user.save()