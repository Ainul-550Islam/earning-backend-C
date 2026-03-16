from django.db.models.signals import post_save
from django.dispatch import receiver
from .utils import generate_referral_code
from django.contrib.auth import get_user_model 
from api.users.models import UserProfile
from django.conf import settings
# বর্তমান প্রজেক্টের ইউজার মডেলকে চিনে নেওয়া
User = get_user_model()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create user profile when user is created"""
    if created:
        UserProfile.objects.create(user=instance)
        
        # Generate referral code
        if not instance.referral_code:
            instance.referral_code = generate_referral_code(instance.username)
            instance.save()


@receiver(post_save, sender=User)
def handle_referral_bonus(sender, instance, created, **kwargs):
    """Give bonus to referrer when new user registers"""
    if created and instance.referred_by and instance.is_verified:
        referrer = instance.referred_by
        referrer.balance += 10.00  # Bonus amount
        referrer.save()