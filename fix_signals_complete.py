path = r'C:\Users\Ainul Islam\New folder (8)\earning_backend\api\users\signals.py'

content = '''from django.db.models.signals import post_save
from django.dispatch import receiver
from .utils import generate_referral_code
from django.contrib.auth import get_user_model
from api.users.models import UserProfile
from django.conf import settings

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
        if not instance.referral_code:
            instance.referral_code = generate_referral_code(instance.username)
            instance.save()
        try:
            from api.wallet.models import Wallet
            Wallet.objects.get_or_create(user=instance)
        except Exception:
            pass
        try:
            from api.users.models import UserLevel
            UserLevel.objects.get_or_create(user=instance)
        except Exception:
            pass
        try:
            from api.users.models import NotificationSettings
            NotificationSettings.objects.get_or_create(user=instance)
        except Exception:
            pass
        try:
            from api.users.models import SecuritySettings
            SecuritySettings.objects.get_or_create(user=instance)
        except Exception:
            pass
        try:
            from api.users.models import UserStatistics
            UserStatistics.objects.get_or_create(user=instance)
        except Exception:
            pass

@receiver(post_save, sender=User)
def handle_referral_bonus(sender, instance, created, **kwargs):
    if created and instance.referred_by and instance.is_verified:
        referrer = instance.referred_by
        referrer.balance += 10.00
        referrer.save()
'''

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
