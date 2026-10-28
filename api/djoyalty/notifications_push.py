# api/djoyalty/notifications_push.py
"""
notifications_push -- PushNotificationService wrapper module.
OmnichannelViewSet imports PushNotificationService from here.
Delegates to integrations/push_notification.py FCMPushService
and CustomerDevice model for token management.
"""
import logging
from django.db import transaction

logger = logging.getLogger(__name__)


class PushNotificationService:
    """
    Push notification service -- device token management + FCM delivery.
    Used by OmnichannelViewSet for register/unregister/send operations.
    """

    @staticmethod
    def register_token(customer, token: str, platform: str = 'android',
                       device_name: str = '', tenant=None) -> dict:
        """Register a device FCM token for push notifications."""
        try:
            from .models.core import CustomerDevice
            device, created = CustomerDevice.objects.update_or_create(
                customer=customer,
                token=token,
                defaults={
                    'platform': platform,
                    'device_name': device_name or f'{platform} device',
                    'is_active': True,
                    'tenant': tenant or getattr(customer, 'tenant', None),
                }
            )
            logger.info('PushNotificationService.register_token: %s %s token',
                        customer.code, 'registered' if created else 'updated')
            return {
                'success': True,
                'device_id': device.id,
                'registered': created,
                'platform': platform,
            }
        except Exception as e:
            logger.error('PushNotificationService.register_token error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def unregister_token(customer, token: str) -> dict:
        """Unregister / deactivate a device FCM token."""
        try:
            from .models.core import CustomerDevice
            updated = CustomerDevice.objects.filter(
                customer=customer, token=token,
            ).update(is_active=False)
            logger.info('PushNotificationService.unregister_token: %s token(s) deactivated', updated)
            return {'success': True, 'deactivated': updated}
        except Exception as e:
            logger.error('PushNotificationService.unregister_token error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def send(customer, title: str, body: str, data: dict = None,
             notification_type: str = 'general') -> dict:
        """Send push notification to all active devices of a customer."""
        try:
            from .models.core import CustomerDevice
            from .integrations.push_notification import FCMPushService

            tokens = list(
                CustomerDevice.objects.filter(
                    customer=customer, is_active=True,
                ).values_list('token', flat=True)
            )
            if not tokens:
                return {'success': True, 'sent': 0, 'reason': 'No active device tokens'}

            results = []
            for token in tokens:
                r = FCMPushService.send_to_token(
                    token=token, title=title, body=body, data=data or {},
                )
                results.append(r)

            sent = sum(1 for r in results if r.get('success'))
            return {'success': True, 'sent': sent, 'total_devices': len(tokens)}
        except Exception as e:
            logger.error('PushNotificationService.send error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def send_batch(payloads: list) -> dict:
        """
        Send push to multiple customers.
        payloads = [{'customer': obj, 'title': str, 'body': str, 'data': dict}, ...]
        """
        sent = 0; failed = 0
        for payload in payloads:
            try:
                result = PushNotificationService.send(
                    customer=payload['customer'],
                    title=payload.get('title', ''),
                    body=payload.get('body', ''),
                    data=payload.get('data', {}),
                )
                if result.get('success'):
                    sent += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                logger.warning('PushNotificationService.send_batch item error: %s', e)
        return {'sent': sent, 'failed': failed, 'total': len(payloads)}

    @staticmethod
    def get_delivery_stats(tenant=None, days: int = 30) -> dict:
        """Delivery stats for push notifications over last N days."""
        try:
            from .services.NotificationService import NotificationService
            return NotificationService.get_delivery_stats(tenant=tenant, days=days)
        except Exception as e:
            logger.error('PushNotificationService.get_delivery_stats error: %s', e)
            return {'total_sent': 0, 'push_sent': 0, 'read_rate_pct': 0}
