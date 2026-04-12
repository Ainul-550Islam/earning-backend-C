# api/offer_inventory/notifications/email_alert_system.py
"""
Email Alert System — System-level email alerts for admins and ops.
Sends alerts for: fraud spikes, revenue drops, errors, cap hits.
"""
import logging
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

ADMIN_EMAIL_SETTING = 'system.admin_email'


class EmailAlertSystem:
    """System email alerts for platform administrators."""

    @classmethod
    def _get_admin_emails(cls) -> list:
        """Load admin emails from SystemSetting or Django settings."""
        from api.offer_inventory.models import SystemSetting
        try:
            setting = SystemSetting.objects.get(key=ADMIN_EMAIL_SETTING)
            import json
            val = setting.value
            return json.loads(val) if val.startswith('[') else [val]
        except Exception:
            return [getattr(settings, 'ADMIN_EMAIL', 'admin@platform.com')]

    @classmethod
    def send_fraud_spike_alert(cls, stats: dict):
        """Alert admins about fraud rate spike."""
        admins  = cls._get_admin_emails()
        subject = f'🚨 Fraud Spike Alert — {stats.get("fraud_rate", 0):.1f}% fraud rate'
        body    = (
            f'Fraud rate has exceeded threshold.\n\n'
            f'Fraud clicks  : {stats.get("fraud_clicks", 0)}\n'
            f'Total clicks  : {stats.get("total_clicks", 0)}\n'
            f'Fraud rate    : {stats.get("fraud_rate", 0):.1f}%\n'
            f'Threshold     : 15%\n'
            f'Time          : {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n'
            f'Action: Check the fraud dashboard immediately.'
        )
        cls._send(admins, subject, body)

    @classmethod
    def send_revenue_alert(cls, expected: float, actual: float):
        """Alert if daily revenue drops significantly."""
        if expected <= 0:
            return
        drop_pct = ((expected - actual) / expected) * 100
        if drop_pct < 20:
            return
        admins  = cls._get_admin_emails()
        subject = f'📉 Revenue Alert — {drop_pct:.0f}% below expected'
        body    = (
            f'Revenue is significantly below expected.\n\n'
            f'Expected : ৳{expected:.2f}\n'
            f'Actual   : ৳{actual:.2f}\n'
            f'Drop     : {drop_pct:.1f}%\n'
            f'Time     : {timezone.now().strftime("%Y-%m-%d %H:%M")}\n'
        )
        cls._send(admins, subject, body)

    @classmethod
    def send_system_error_alert(cls, error: str, context: str = ''):
        """Alert for critical system errors."""
        admins  = cls._get_admin_emails()
        subject = '🔴 Critical System Error — Offer Inventory'
        body    = (
            f'A critical error occurred.\n\n'
            f'Error   : {error}\n'
            f'Context : {context}\n'
            f'Time    : {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
        )
        cls._send(admins, subject, body)

    @classmethod
    def send_offer_cap_hit_alert(cls, offer):
        """Alert when an offer hits its conversion cap."""
        admins  = cls._get_admin_emails()
        subject = f'⚠️ Offer Cap Hit: {offer.title}'
        body    = (
            f'An offer has reached its conversion cap.\n\n'
            f'Offer ID : {offer.id}\n'
            f'Title    : {offer.title}\n'
            f'Status   : Paused\n'
            f'Time     : {timezone.now().strftime("%Y-%m-%d %H:%M")}\n\n'
            f'SmartLink will automatically rotate to the next best offer.'
        )
        cls._send(admins, subject, body)

    @classmethod
    def send_withdrawal_summary(cls, stats: dict):
        """Daily withdrawal summary for finance team."""
        admins  = cls._get_admin_emails()
        subject = f'💰 Daily Withdrawal Summary — {timezone.now().strftime("%Y-%m-%d")}'
        body    = (
            f'Daily withdrawal summary:\n\n'
            f'Pending      : {stats.get("pending", 0)} (৳{stats.get("pending_amount", 0):.2f})\n'
            f'Approved     : {stats.get("approved", 0)} (৳{stats.get("approved_amount", 0):.2f})\n'
            f'Completed    : {stats.get("completed", 0)} (৳{stats.get("completed_amount", 0):.2f})\n'
            f'Rejected     : {stats.get("rejected", 0)}\n'
        )
        cls._send(admins, subject, body)

    @classmethod
    def send_kyc_pending_alert(cls, count: int):
        """Alert when KYC queue gets large."""
        if count < 10:
            return
        admins  = cls._get_admin_emails()
        subject = f'📋 {count} KYC Submissions Pending Review'
        body    = f'{count} KYC submissions are waiting for review. Please log in to the admin panel.'
        cls._send(admins, subject, body)

    @staticmethod
    def _send(emails: list, subject: str, body: str):
        """Send email to admins."""
        try:
            send_mail(
                subject       =f'[Platform Alert] {subject}',
                message       =body,
                from_email    =getattr(settings, 'DEFAULT_FROM_EMAIL', 'alerts@platform.com'),
                recipient_list=emails,
                fail_silently =True,
            )
            logger.info(f'Admin alert sent: {subject[:60]}')
        except Exception as e:
            logger.error(f'Admin email send error: {e}')
