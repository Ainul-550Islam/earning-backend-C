# api/offer_inventory/marketing/push_notifications.py
"""
Push Notification Service.
Web Push, FCM (Firebase), and in-app notification routing.
"""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class PushNotificationService:
    """Multi-channel push notification sender."""

    @staticmethod
    def send_to_user(user, title: str, body: str,
                      icon: str = '', url: str = '',
                      data: dict = None) -> dict:
        """Send push notification to a user via all their active subscriptions."""
        from api.offer_inventory.models import PushSubscription

        subs   = PushSubscription.objects.filter(user=user, is_active=True)
        sent   = 0
        failed = 0

        for sub in subs:
            ok = PushNotificationService._send_web_push(
                endpoint =sub.endpoint,
                p256dh   =sub.p256dh_key,
                auth     =sub.auth_key,
                title    =title,
                body     =body,
                icon     =icon,
                url      =url,
                data     =data or {},
            )
            if ok:
                sent += 1
                from django.utils import timezone
                PushSubscription.objects.filter(id=sub.id).update(last_used=timezone.now())
            else:
                failed += 1

        return {'sent': sent, 'failed': failed}

    @staticmethod
    def send_to_segment(user_ids: list, title: str, body: str,
                         url: str = '') -> dict:
        """Send push to a list of users."""
        from api.offer_inventory.models import PushSubscription

        subs = PushSubscription.objects.filter(
            user_id__in=user_ids, is_active=True
        )
        sent = failed = 0

        for sub in subs:
            ok = PushNotificationService._send_web_push(
                endpoint=sub.endpoint, p256dh=sub.p256dh_key,
                auth=sub.auth_key, title=title, body=body, url=url,
            )
            if ok: sent  += 1
            else:  failed += 1

        return {'sent': sent, 'failed': failed, 'total': subs.count()}

    @staticmethod
    def _send_web_push(endpoint: str, p256dh: str, auth: str,
                        title: str, body: str, icon: str = '',
                        url: str = '', data: dict = None) -> bool:
        try:
            import json
            from pywebpush import webpush, WebPushException
            from django.conf import settings

            payload = json.dumps({
                'title': title, 'body': body,
                'icon' : icon or '', 'url': url,
                'data' : data or {},
            })
            webpush(
                subscription_info={
                    'endpoint': endpoint,
                    'keys'    : {'p256dh': p256dh, 'auth': auth}
                },
                data             =payload,
                vapid_private_key=getattr(settings, 'VAPID_PRIVATE_KEY', ''),
                vapid_claims     ={
                    'sub': f'mailto:{getattr(settings, "VAPID_EMAIL", "admin@platform.com")}'
                },
            )
            return True
        except Exception as e:
            if 'expired' in str(e).lower() or '410' in str(e):
                # Subscription expired — mark inactive
                from api.offer_inventory.models import PushSubscription
                PushSubscription.objects.filter(endpoint=endpoint).update(is_active=False)
            logger.debug(f'Web push error: {e}')
            return False

    @staticmethod
    def subscribe(user, endpoint: str, p256dh: str, auth: str,
                   user_agent: str = '') -> object:
        """Register a new push subscription."""
        from api.offer_inventory.models import PushSubscription
        obj, created = PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                'user'      : user,
                'p256dh_key': p256dh,
                'auth_key'  : auth,
                'user_agent': user_agent[:500],
                'is_active' : True,
            }
        )
        return obj

    @staticmethod
    def unsubscribe(endpoint: str) -> bool:
        """Mark a subscription as inactive."""
        from api.offer_inventory.models import PushSubscription
        updated = PushSubscription.objects.filter(endpoint=endpoint).update(is_active=False)
        return updated > 0

    @staticmethod
    def get_subscription_count(user) -> int:
        from api.offer_inventory.models import PushSubscription
        return PushSubscription.objects.filter(user=user, is_active=True).count()
