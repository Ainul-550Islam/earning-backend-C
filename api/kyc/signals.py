import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _get_kyc_model():
    from .models import KYC
    return KYC


def register_signals():
    KYC = _get_kyc_model()

    @receiver(post_save, sender=KYC)
    def kyc_status_changed(sender, instance, created, **kwargs):
        if not created:
            if instance.status == 'verified':
                logger.info(f"KYC verified for user: {instance.user.username}")
                # এখানে notification পাঠাতে পারো
                try:
                    from api.notifications.models import Notification
                    Notification.objects.create(
                        user=instance.user,
                        title='KYC Verified ✅',
                        message='আপনার KYC সফলভাবে verified হয়েছে।',
                        notification_type='kyc'
                    )
                except Exception:
                    pass

            elif instance.status == 'rejected':
                logger.info(f"KYC rejected for user: {instance.user.username}")
                try:
                    from api.notifications.models import Notification
                    Notification.objects.create(
                        user=instance.user,
                        title='KYC Rejected ❌',
                        message=f'আপনার KYC reject হয়েছে। কারণ: {instance.rejection_reason}',
                        notification_type='kyc'
                    )
                except Exception:
                    pass


register_signals()