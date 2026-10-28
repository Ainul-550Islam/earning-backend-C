# api/djoyalty/integrations/push_notification.py
"""
Firebase FCM Push Notification Integration।
Android + iOS + Web push notifications।

docs: https://firebase.google.com/docs/cloud-messaging
package: firebase-admin (pip install firebase-admin)

Settings required:
    GOOGLE_APPLICATION_CREDENTIALS = '/path/to/firebase-credentials.json'
    OR
    DJOYALTY_FIREBASE_CREDENTIALS = {...}  # dict form

Usage:
    from djoyalty.integrations.push_notification import FCMPushService
    FCMPushService.send_to_customer(customer, title='🎁 Bonus!', body='You earned 100 points!')
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class FCMPushService:
    """
    Firebase FCM push notification service।
    Customer device tokens manage করে এবং push পাঠায়।

    Device Token save করতে হবে CustomerDevice model এ।
    """

    _app = None

    @classmethod
    def _get_app(cls):
        """Firebase app initialize করো (singleton)।"""
        if cls._app:
            return cls._app
        try:
            import firebase_admin
            from firebase_admin import credentials

            cred_dict = getattr(settings, 'DJOYALTY_FIREBASE_CREDENTIALS', None)
            if cred_dict:
                cred = credentials.Certificate(cred_dict)
            else:
                # GOOGLE_APPLICATION_CREDENTIALS env var ব্যবহার করে
                cred = credentials.ApplicationDefault()

            try:
                cls._app = firebase_admin.get_app()
            except ValueError:
                cls._app = firebase_admin.initialize_app(cred)

            return cls._app
        except ImportError:
            logger.error('FCMPushService: firebase-admin not installed. Run: pip install firebase-admin')
            return None
        except Exception as e:
            logger.error('FCMPushService: Firebase init error: %s', e)
            return None

    @classmethod
    def send_to_token(cls, device_token: str, title: str, body: str,
                       data: dict = None, image_url: str = None) -> bool:
        """Single device token এ push পাঠাও।"""
        app = cls._get_app()
        if not app:
            return False

        try:
            from firebase_admin import messaging

            notification = messaging.Notification(title=title, body=body, image=image_url)
            message = messaging.Message(
                notification=notification,
                data={str(k): str(v) for k, v in (data or {}).items()},
                token=device_token,
                android=messaging.AndroidConfig(
                    notification=messaging.AndroidNotification(
                        icon='loyalty_icon',
                        color='#3b82f6',
                        sound='default',
                    ),
                    priority='high',
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(sound='default', badge=1),
                    ),
                ),
            )
            response = messaging.send(message)
            logger.info('FCMPushService: push sent -- %s', response)
            return True
        except Exception as e:
            logger.error('FCMPushService.send_to_token error: %s', e)
            return False

    @classmethod
    def send_to_multiple(cls, tokens: list, title: str, body: str,
                          data: dict = None) -> dict:
        """Multiple device tokens এ push পাঠাও (max 500)।"""
        app = cls._get_app()
        if not app or not tokens:
            return {'success_count': 0, 'failure_count': len(tokens)}

        try:
            from firebase_admin import messaging

            messages = [
                messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    data={str(k): str(v) for k, v in (data or {}).items()},
                    token=token,
                )
                for token in tokens[:500]
            ]

            response = messaging.send_each(messages)
            logger.info('FCMPushService: batch push -- success=%d, failed=%d',
                        response.success_count, response.failure_count)
            return {
                'success_count': response.success_count,
                'failure_count': response.failure_count,
            }
        except Exception as e:
            logger.error('FCMPushService.send_to_multiple error: %s', e)
            return {'success_count': 0, 'failure_count': len(tokens), 'error': str(e)}

    @classmethod
    def send_to_customer(cls, customer, title: str, body: str,
                          data: dict = None, notification_type: str = 'general') -> bool:
        """Customer এর সব registered devices এ push পাঠাও।"""
        try:
            devices = CustomerDevice.objects.filter(
                customer=customer, is_active=True
            ).values_list('fcm_token', flat=True)

            tokens = [t for t in devices if t]
            if not tokens:
                return False

            data = data or {}
            data['notification_type'] = notification_type

            result = cls.send_to_multiple(list(tokens), title=title, body=body, data=data)
            return result.get('success_count', 0) > 0
        except Exception as e:
            logger.error('FCMPushService.send_to_customer error: %s', e)
            return False

    @classmethod
    def send_to_topic(cls, topic: str, title: str, body: str, data: dict = None) -> bool:
        """Topic subscriber সবাইকে push পাঠাও।"""
        app = cls._get_app()
        if not app:
            return False
        try:
            from firebase_admin import messaging
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data={str(k): str(v) for k, v in (data or {}).items()},
                topic=topic,
            )
            response = messaging.send(message)
            logger.info('FCMPushService: topic push sent -- %s -> %s', topic, response)
            return True
        except Exception as e:
            logger.error('FCMPushService.send_to_topic error: %s', e)
            return False

    # ─── Pre-built loyalty push templates ────────────────────────

    @classmethod
    def notify_points_earned(cls, customer, points: float):
        cls.send_to_customer(
            customer,
            title='💰 পয়েন্ট অর্জন!',
            body=f'আপনি {points} পয়েন্ট অর্জন করেছেন।',
            data={'type': 'points_earned', 'points': str(points)},
            notification_type='points_earned',
        )

    @classmethod
    def notify_tier_upgrade(cls, customer, new_tier: str):
        cls.send_to_customer(
            customer,
            title=f'🎉 {new_tier.title()} Tier!',
            body=f'অভিনন্দন! আপনি {new_tier.title()} Tier এ upgrade হয়েছেন।',
            data={'type': 'tier_upgrade', 'tier': new_tier},
            notification_type='tier_upgrade',
        )

    @classmethod
    def notify_badge_unlocked(cls, customer, badge_name: str):
        cls.send_to_customer(
            customer,
            title='🏅 নতুন Badge!',
            body=f'আপনি "{badge_name}" badge অর্জন করেছেন!',
            data={'type': 'badge_unlocked', 'badge': badge_name},
            notification_type='badge_unlocked',
        )

    @classmethod
    def notify_voucher_generated(cls, customer, code: str):
        cls.send_to_customer(
            customer,
            title='🎟️ Voucher পেয়েছেন!',
            body=f'আপনার Voucher: {code}',
            data={'type': 'voucher', 'code': code},
            notification_type='voucher',
        )

    @classmethod
    def notify_personalized_offer(cls, customer, offer_title: str):
        cls.send_to_customer(
            customer,
            title='🎁 বিশেষ অফার!',
            body=offer_title,
            data={'type': 'personalized_offer'},
            notification_type='offer',
        )

    @classmethod
    def notify_points_expiring(cls, customer, points: float, days: int):
        cls.send_to_customer(
            customer,
            title='⚠️ পয়েন্ট মেয়াদ শেষ হচ্ছে!',
            body=f'{days} দিনে {points} পয়েন্ট মেয়াদ শেষ হবে।',
            data={'type': 'expiry_warning', 'points': str(points), 'days': str(days)},
            notification_type='expiry_warning',
        )

    @staticmethod
    def is_configured() -> bool:
        import os
        return bool(
            getattr(settings, 'DJOYALTY_FIREBASE_CREDENTIALS', None) or
            os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        )


# ─── CustomerDevice Model (for FCM token storage) ─────────────────────────────

from django.db import models


class CustomerDevice(models.Model):
    """
    Customer device FCM token storage।
    Push notification পাঠাতে এই model ব্যবহার হয়।

    Note: This model needs to be added to INSTALLED_APPS
    and migrated separately, or use fcm-django package.
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='devices',
    )
    fcm_token = models.CharField(max_length=500, unique=True, verbose_name='FCM Token')
    device_type = models.CharField(
        max_length=10,
        choices=[('android', 'Android'), ('ios', 'iOS'), ('web', 'Web')],
        default='android',
    )
    device_name = models.CharField(max_length=200, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Customer Device'
        verbose_name_plural = 'Customer Devices'
        indexes = [
            models.Index(fields=['customer', 'is_active']),
        ]

    def __str__(self):
        return f'Device({self.customer.code}: {self.device_type})'
