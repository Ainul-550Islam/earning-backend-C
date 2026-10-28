# api/djoyalty/services/NotificationService.py
"""
Notification Service -- Unified notification sender।
Creates in-app notification + sends via SMS/Push/Email based on preferences।
"এক কাজের জন্য একটাই মালিক" -- all notification logic here।
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Unified notification service for all loyalty events।
    Checks customer preferences, creates in-app record,
    routes to SMS/Push/Email accordingly।

    Usage:
        NotificationService.notify_points_earned(customer, points=100, balance=500)
        NotificationService.notify_tier_upgrade(customer, new_tier='gold')
        NotificationService.send(customer, 'points_earned', title='...', body='...')
    """

    @staticmethod
    def send(customer, notification_type: str, title: str, body: str,
              icon: str = '🔔', action_url: str = '', metadata: dict = None,
              linked_object_type: str = '', linked_object_id: str = '',
              priority: str = 'normal') -> bool:
        """
        Send notification to customer via all enabled channels।
        Creates in-app record + routes to push/sms/email।
        """
        try:
            from ..models.notifications import NotificationCenter, NotificationPreference

            # 1. Get customer preferences
            pref = NotificationPreference.objects.filter(
                customer=customer
            ).first()

            # 2. Daily limit check
            if pref and pref.max_per_day:
                today_count = NotificationCenter.objects.filter(
                    customer=customer,
                    created_at__date=timezone.now().date(),
                ).count()
                if today_count >= pref.max_per_day:
                    logger.debug('NotificationService: daily limit reached for %s', customer.code)
                    return False

            # 3. Type preference check
            type_map = {
                'points_earned':    'points_notifications',
                'points_expiring':  'expiry_notifications',
                'tier_upgrade':     'tier_notifications',
                'tier_downgrade':   'tier_notifications',
                'badge_unlocked':   'badge_notifications',
                'voucher_issued':   'campaign_notifications',
                'challenge_completed': 'campaign_notifications',
                'cashout_complete': 'cashout_notifications',
                'offer_available':  'offer_notifications',
                'campaign_active':  'campaign_notifications',
                'marketing':        'marketing_notifications',
            }
            type_pref = type_map.get(notification_type, 'campaign_notifications')
            if pref and not getattr(pref, type_pref, True):
                return False

            # 4. Create in-app notification
            if not pref or pref.in_app_enabled:
                NotificationCenter.objects.create(
                    customer=customer,
                    tenant=customer.tenant,
                    title=title,
                    body=body,
                    icon=icon,
                    action_url=action_url,
                    notification_type=notification_type,
                    channel='in_app',
                    priority=priority,
                    linked_object_type=linked_object_type,
                    linked_object_id=str(linked_object_id) if linked_object_id else '',
                    metadata=metadata or {},
                    is_sent=True,
                    sent_at=timezone.now(),
                )

            # 5. Push notification
            if not pref or pref.push_enabled:
                NotificationService._send_push(customer, title, body, notification_type, metadata)

            # 6. SMS (only for high-priority)
            if pref and pref.sms_enabled and priority in ('high', 'critical'):
                NotificationService._send_sms(customer, body)

            return True

        except Exception as e:
            logger.error('NotificationService.send error for %s: %s', customer.code, e)
            return False

    @staticmethod
    def _send_push(customer, title: str, body: str, notif_type: str, data: dict = None):
        try:
            from ..integrations.push_notification import FCMPushService
            if FCMPushService.is_configured():
                FCMPushService.send_to_customer(
                    customer, title=title, body=body,
                    data=data, notification_type=notif_type,
                )
        except Exception as e:
            logger.debug('NotificationService._send_push error: %s', e)

    @staticmethod
    def _send_sms(customer, message: str):
        try:
            if not customer.phone or not getattr(customer, 'sms_opt_in', False):
                return
            from ..integrations.sms import SMSService
            SMSService.send(customer.phone, message[:160])
        except Exception as e:
            logger.debug('NotificationService._send_sms error: %s', e)

    # ─── Pre-built notification helpers ──────────────────────────

    @classmethod
    def notify_points_earned(cls, customer, points, balance):
        cls.send(
            customer, 'points_earned',
            title=f'💰 +{points} পয়েন্ট অর্জিত!',
            body=f'আপনার {points} পয়েন্ট যোগ হয়েছে। মোট: {balance} পয়েন্ট।',
            icon='💰',
            metadata={'points': str(points), 'balance': str(balance)},
        )

    @classmethod
    def notify_tier_upgrade(cls, customer, new_tier: str, old_tier: str = ''):
        cls.send(
            customer, 'tier_upgrade',
            title=f'🏆 {new_tier.title()} Tier!',
            body=f'অভিনন্দন! আপনি {new_tier.title()} Tier এ upgrade হয়েছেন।',
            icon='🏆',
            metadata={'new_tier': new_tier, 'old_tier': old_tier},
            priority='high',
        )

    @classmethod
    def notify_badge_unlocked(cls, customer, badge_name: str, badge_icon: str = '🏅'):
        cls.send(
            customer, 'badge_unlocked',
            title=f'{badge_icon} নতুন Badge!',
            body=f'"{badge_name}" badge অর্জন করেছেন!',
            icon=badge_icon,
            metadata={'badge_name': badge_name},
        )

    @classmethod
    def notify_voucher_issued(cls, customer, code: str, discount: str):
        cls.send(
            customer, 'voucher_issued',
            title='🎟️ Voucher পেয়েছেন!',
            body=f'আপনার Voucher: {code} -- {discount} Discount',
            icon='🎟️',
            metadata={'code': code, 'discount': discount},
            priority='high',
        )

    @classmethod
    def notify_points_expiring(cls, customer, points, days: int):
        cls.send(
            customer, 'points_expiring',
            title='⚠️ পয়েন্ট মেয়াদ শেষ হচ্ছে!',
            body=f'{days} দিনে {points} পয়েন্ট মেয়াদ শেষ হবে।',
            icon='⚠️',
            metadata={'points': str(points), 'days': days},
            priority='high',
        )

    @classmethod
    def notify_cashout_complete(cls, customer, amount, method: str):
        cls.send(
            customer, 'cashout_complete',
            title='✅ Cashout সম্পন্ন!',
            body=f'{amount} টাকা {method} এ পাঠানো হয়েছে।',
            icon='✅',
            metadata={'amount': str(amount), 'method': method},
            priority='high',
        )

    @classmethod
    def notify_challenge_completed(cls, customer, challenge_name: str, points_reward):
        cls.send(
            customer, 'challenge_completed',
            title='✅ Challenge শেষ!',
            body=f'"{challenge_name}" সম্পন্ন! +{points_reward} পয়েন্ট।',
            icon='✅',
            metadata={'challenge': challenge_name, 'points': str(points_reward)},
        )

    @classmethod
    def notify_spin_result(cls, customer, prize: str, points_won):
        icon = '🎉' if points_won > 0 else '😔'
        cls.send(
            customer, 'offer_available',
            title=f'{icon} Spin Result!',
            body=f'আপনি জিতেছেন: {prize}' if points_won > 0 else 'আজ ভাগ্য সহায় ছিল না।',
            icon=icon,
            metadata={'prize': prize, 'points_won': str(points_won)},
        )

    @classmethod
    def mark_all_read(cls, customer) -> int:
        """Mark all unread notifications as read।"""
        from ..models.notifications import NotificationCenter
        updated = NotificationCenter.objects.filter(
            customer=customer, is_read=False,
        ).update(is_read=True, read_at=timezone.now())
        return updated

    @classmethod
    def get_unread_count(cls, customer) -> int:
        """Get unread notification count।"""
        from ..models.notifications import NotificationCenter
        return NotificationCenter.objects.filter(customer=customer, is_read=False).count()

    @classmethod
    def send_bulk(cls, customers: list, notification_type: str,
                  title: str, body: str, data: dict = None, tenant=None) -> dict:
        """
        Bulk send notifications to a list of customers.
        Returns: {'sent': N, 'failed': N, 'results': [...]}
        """
        sent = 0; failed = 0; results = []
        for customer in customers:
            try:
                cls.send(customer, notification_type, title=title, body=body,
                         icon='🔔', metadata=data or {})
                sent += 1
                results.append({'customer_id': customer.id, 'success': True})
            except Exception as e:
                failed += 1
                results.append({'customer_id': getattr(customer, 'id', None), 'success': False, 'error': str(e)})
        logger.info('NotificationService.send_bulk: sent=%d failed=%d', sent, failed)
        return {'sent': sent, 'failed': failed, 'results': results}

    @classmethod
    def send_batch(cls, payloads: list, tenant=None) -> dict:
        """
        Send a batch of heterogeneous notifications.
        payloads = [{'customer': obj, 'type': str, 'title': str, 'body': str}, ...]
        """
        sent = 0; failed = 0
        for payload in payloads:
            try:
                cls.send(
                    payload['customer'],
                    payload.get('type', 'batch'),
                    title=payload.get('title', ''),
                    body=payload.get('body', ''),
                    icon=payload.get('icon', '🔔'),
                    metadata=payload.get('data', {}),
                )
                sent += 1
            except Exception as e:
                failed += 1
                logger.warning('NotificationService.send_batch item error: %s', e)
        return {'sent': sent, 'failed': failed, 'total': len(payloads)}

    @classmethod
    def get_delivery_stats(cls, tenant=None, days: int = 30) -> dict:
        """
        Delivery stats for the last N days.
        Returns: {'total_sent': N, 'push_sent': N, 'sms_sent': N, 'read_rate': pct}
        """
        try:
            from ..models.notifications import LoyaltyNotification
            from django.utils import timezone
            from datetime import timedelta
            from django.db.models import Count, Q

            since = timezone.now() - timedelta(days=days)
            qs = LoyaltyNotification.objects.filter(created_at__gte=since)
            if tenant:
                qs = qs.filter(customer__tenant=tenant)

            total = qs.count()
            read = qs.filter(is_read=True).count()
            push = qs.filter(channel='push').count()
            sms = qs.filter(channel='sms').count()

            return {
                'period_days': days,
                'total_sent': total,
                'push_sent': push,
                'sms_sent': sms,
                'read_count': read,
                'read_rate_pct': round((read / total * 100), 1) if total > 0 else 0,
            }
        except Exception as e:
            logger.error('NotificationService.get_delivery_stats error: %s', e)
            return {'total_sent': 0, 'push_sent': 0, 'sms_sent': 0, 'read_rate_pct': 0}

    @classmethod
    def register_token(cls, customer, token: str, platform: str = 'android',
                       device_name: str = '', tenant=None) -> dict:
        """Register a device push token for a customer. Delegates to PushNotificationService."""
        try:
            from ..notifications_push import PushNotificationService
            return PushNotificationService.register_token(
                customer=customer, token=token,
                platform=platform, device_name=device_name, tenant=tenant,
            )
        except Exception as e:
            logger.error('NotificationService.register_token error: %s', e)
            return {'success': False, 'error': str(e)}

    @classmethod
    def unregister_token(cls, customer, token: str) -> dict:
        """Unregister a device push token. Delegates to PushNotificationService."""
        try:
            from ..notifications_push import PushNotificationService
            return PushNotificationService.unregister_token(customer=customer, token=token)
        except Exception as e:
            logger.error('NotificationService.unregister_token error: %s', e)
            return {'success': False, 'error': str(e)}
