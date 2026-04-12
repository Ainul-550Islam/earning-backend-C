# api/offer_inventory/notifications/push_notification_trigger.py
"""
Push Notification Trigger System.
Event-driven push notifications for offer events.
Triggers notifications based on: new offers, cap warnings, fraud alerts, payouts.
"""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class PushNotificationTrigger:
    """Event-driven push notification dispatcher."""

    # ── Offer events ──────────────────────────────────────────────

    @staticmethod
    def notify_new_offer(offer, target_user_ids: list = None):
        """Notify users about a new high-value offer."""
        from api.offer_inventory.marketing.push_notifications import PushNotificationService
        if not target_user_ids:
            from api.offer_inventory.ai_optimization.ai_recommender import AIRecommender
            # Get users likely to convert on this offer
            target_user_ids = PushNotificationTrigger._get_target_users_for_offer(offer)

        if not target_user_ids:
            return {'sent': 0}

        return PushNotificationService.send_to_segment(
            user_ids=target_user_ids,
            title   =f'🎯 নতুন অফার: {offer.title}',
            body    =f'{offer.reward_amount} টাকা পর্যন্ত আয় করুন! সীমিত সময়ের জন্য।',
            url     =f'/offers/{offer.id}',
        )

    @staticmethod
    def notify_offer_expiring(offer, hours_remaining: int = 24):
        """Notify users that an offer is about to expire."""
        from api.offer_inventory.marketing.push_notifications import PushNotificationService
        from api.offer_inventory.models import Click
        from django.db.models import F

        # Users who clicked but didn't convert
        user_ids = list(
            Click.objects.filter(
                offer=offer, converted=False
            ).values_list('user_id', flat=True).distinct()[:5000]
        )

        if not user_ids:
            return {'sent': 0}

        return PushNotificationService.send_to_segment(
            user_ids=user_ids,
            title   =f'⏰ শেষ সুযোগ! অফার {hours_remaining} ঘণ্টায় শেষ',
            body    =f'{offer.title} — এখনই সম্পন্ন করুন!',
            url     =f'/offers/{offer.id}',
        )

    @staticmethod
    def notify_payout_received(user_id, amount):
        """Notify user about received payout."""
        from api.offer_inventory.marketing.push_notifications import PushNotificationService
        return PushNotificationService.send_to_user(
            user   =PushNotificationTrigger._get_user(user_id),
            title  ='💰 পেমেন্ট পেয়েছেন!',
            body   =f'আপনার ওয়ালেটে {amount} টাকা যোগ হয়েছে।',
            url    ='/wallet',
        )

    @staticmethod
    def notify_withdrawal_approved(user_id, amount):
        """Notify user about approved withdrawal."""
        from api.offer_inventory.marketing.push_notifications import PushNotificationService
        return PushNotificationService.send_to_user(
            user  =PushNotificationTrigger._get_user(user_id),
            title ='✅ উইথড্রয়াল অনুমোদিত!',
            body  =f'{amount} টাকা আপনার অ্যাকাউন্টে পাঠানো হচ্ছে।',
            url   ='/wallet/history',
        )

    @staticmethod
    def notify_fraud_alert(user_id):
        """Security alert push notification."""
        from api.offer_inventory.marketing.push_notifications import PushNotificationService
        return PushNotificationService.send_to_user(
            user  =PushNotificationTrigger._get_user(user_id),
            title ='⚠️ নিরাপত্তা সতর্কতা',
            body  ='আপনার অ্যাকাউন্টে অস্বাভাবিক কার্যকলাপ সনাক্ত হয়েছে।',
            url   ='/profile/security',
        )

    @staticmethod
    def _get_target_users_for_offer(offer) -> list:
        """Get user IDs likely interested in this offer."""
        from api.offer_inventory.models import UserInterest
        if not offer.category_id:
            return []
        return list(
            UserInterest.objects.filter(
                category_id=offer.category_id, score__gte=0.5
            ).values_list('user_id', flat=True)[:5000]
        )

    @staticmethod
    def _get_user(user_id):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None


# ─────────────────────────────────────────────────────
# api/offer_inventory/notifications/email_alert_system.py
# ─────────────────────────────────────────────────────

class EmailAlertSystem:
    """
    System-level email alerts for admins and operations.
    Sends alerts for: fraud spikes, revenue drops, system errors, cap hits.
    """

    ADMIN_EMAIL_KEY = 'system.admin_email'

    @classmethod
    def _get_admin_emails(cls) -> list:
        from api.offer_inventory.models import SystemSetting
        try:
            setting = SystemSetting.objects.get(key=cls.ADMIN_EMAIL_KEY)
            import json
            return json.loads(setting.value) if setting.value.startswith('[') else [setting.value]
        except Exception:
            from django.conf import settings
            return [getattr(settings, 'ADMIN_EMAIL', 'admin@platform.com')]

    @classmethod
    def send_fraud_spike_alert(cls, stats: dict):
        """Alert admins about fraud rate spike."""
        admins = cls._get_admin_emails()
        subject = f'🚨 Fraud Spike Alert — {stats.get("fraud_rate", 0):.1f}% fraud rate'
        body    = (
            f'Fraud rate has exceeded threshold.\n\n'
            f'Fraud clicks: {stats.get("fraud_clicks", 0)}\n'
            f'Total clicks: {stats.get("total_clicks", 0)}\n'
            f'Fraud rate: {stats.get("fraud_rate", 0):.1f}%\n'
            f'Time: {__import__("django.utils.timezone", fromlist=["timezone"]).timezone.now()}'
        )
        cls._send_to_admins(admins, subject, body)

    @classmethod
    def send_revenue_alert(cls, expected: float, actual: float):
        """Alert if daily revenue drops significantly."""
        drop_pct = ((expected - actual) / max(expected, 1)) * 100
        if drop_pct < 20:
            return
        admins  = cls._get_admin_emails()
        subject = f'📉 Revenue Alert — {drop_pct:.0f}% below expected'
        body    = f'Expected: {expected:.2f}\nActual: {actual:.2f}\nDrop: {drop_pct:.1f}%'
        cls._send_to_admins(admins, subject, body)

    @classmethod
    def send_system_error_alert(cls, error: str, context: str = ''):
        """Alert for critical system errors."""
        admins  = cls._get_admin_emails()
        subject = '🔴 Critical System Error — Offer Inventory'
        body    = f'Error: {error}\nContext: {context}'
        cls._send_to_admins(admins, subject, body)

    @classmethod
    def send_offer_cap_hit_alert(cls, offer):
        """Alert when an offer hits its conversion cap."""
        admins  = cls._get_admin_emails()
        subject = f'⚠️ Offer Cap Hit: {offer.title}'
        body    = f'Offer "{offer.title}" has reached its conversion cap and has been paused.'
        cls._send_to_admins(admins, subject, body)

    @staticmethod
    def _send_to_admins(emails: list, subject: str, body: str):
        from django.core.mail import send_mail
        from django.conf import settings
        try:
            send_mail(
                subject     =f'[Platform Alert] {subject}',
                message     =body,
                from_email  =getattr(settings, 'DEFAULT_FROM_EMAIL', 'alerts@platform.com'),
                recipient_list=emails,
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f'Admin email alert error: {e}')


# ─────────────────────────────────────────────────────
# api/offer_inventory/notifications/slack_webhook.py
# ─────────────────────────────────────────────────────

class SlackNotifier:
    """
    Slack Webhook integration for operational alerts.
    Sends formatted messages to Slack channels.
    """

    def __init__(self, webhook_url: str = None):
        from django.conf import settings
        self.webhook_url = webhook_url or getattr(settings, 'SLACK_WEBHOOK_URL', '')

    def send(self, message: str, channel: str = None,
              color: str = 'good', fields: list = None) -> bool:
        """Send a Slack message."""
        if not self.webhook_url:
            logger.debug('Slack webhook not configured')
            return False

        payload = {
            'attachments': [{
                'color'   : color,
                'text'    : message,
                'fields'  : fields or [],
                'footer'  : 'Offer Inventory System',
                'ts'      : int(__import__('time').time()),
            }]
        }
        if channel:
            payload['channel'] = channel

        try:
            import requests
            resp = requests.post(self.webhook_url, json=payload, timeout=5)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f'Slack notification error: {e}')
            return False

    def alert_fraud(self, stats: dict) -> bool:
        return self.send(
            message=f'🚨 *Fraud Spike Detected*\nFraud Rate: {stats.get("fraud_rate", 0):.1f}%',
            color='danger',
            fields=[
                {'title': 'Fraud Clicks', 'value': str(stats.get('fraud_clicks', 0)), 'short': True},
                {'title': 'Total Clicks', 'value': str(stats.get('total_clicks', 0)), 'short': True},
            ]
        )

    def alert_new_conversion(self, conversion) -> bool:
        return self.send(
            message=f'✅ New Conversion: {conversion.offer.title if conversion.offer else "?"}',
            color='good',
            fields=[
                {'title': 'Amount',  'value': str(conversion.payout_amount), 'short': True},
                {'title': 'Country', 'value': conversion.country_code, 'short': True},
            ]
        )

    def alert_system_error(self, error: str) -> bool:
        return self.send(
            message=f'🔴 *System Error*\n{error[:500]}',
            color='danger',
        )

    def daily_summary(self, stats: dict) -> bool:
        return self.send(
            message='📊 *Daily Summary — Offer Inventory*',
            color='#36a64f',
            fields=[
                {'title': 'Revenue',     'value': f"৳{stats.get('gross_revenue', 0):.2f}", 'short': True},
                {'title': 'Conversions', 'value': str(stats.get('total_conversions', 0)), 'short': True},
                {'title': 'Clicks',      'value': str(stats.get('total_clicks', 0)), 'short': True},
                {'title': 'CVR',         'value': f"{stats.get('cvr_pct', 0):.1f}%", 'short': True},
            ]
        )
