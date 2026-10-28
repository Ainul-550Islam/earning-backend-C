# api/admin_panel/email_gateway.py
"""
Admin Panel Email Gateway.
Sends admin emails via SMTP/AWS SES/SendGrid.
Used for: admin digest, alerts, report delivery, KYC notifications,
withdrawal confirmations, broadcast emails.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from django.conf import settings
from django.core.mail import send_mail, send_mass_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


class EmailGateway:
    """Central email sending gateway for admin_panel."""

    DEFAULT_FROM = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
    ADMIN_FROM   = getattr(settings, 'ADMIN_EMAIL_FROM', 'admin@example.com')

    @classmethod
    def send_simple(cls, to: str, subject: str, body: str,
                    html_body: str = '', from_email: str = None) -> bool:
        """Send a simple email."""
        try:
            from_email = from_email or cls.DEFAULT_FROM
            if html_body:
                msg = EmailMultiAlternatives(subject=subject, body=body,
                                             from_email=from_email, to=[to])
                msg.attach_alternative(html_body, 'text/html')
                msg.send()
            else:
                send_mail(subject=subject, message=body,
                          from_email=from_email, recipient_list=[to], fail_silently=False)
            logger.info(f"[EmailGateway] Sent to {to}: {subject}")
            return True
        except Exception as e:
            logger.error(f"[EmailGateway.send_simple] {to}: {e}")
            return False

    @classmethod
    def send_admin_alert(cls, subject: str, body: str, severity: str = 'medium') -> int:
        """Send alert to all admin users who have alerts enabled."""
        sent = 0
        try:
            from api.admin_panel.models.core import AdminProfile
            emails = list(AdminProfile.objects.filter(
                receive_alerts=True,
                user__is_active=True,
                user__email__isnull=False,
            ).values_list('user__email', flat=True))

            prefix = {'critical': '🚨 CRITICAL', 'high': '⚠️ HIGH', 'medium': 'ℹ️ ALERT'}.get(severity, 'ALERT')
            full_subject = f"[{prefix}] {subject}"

            for email in emails:
                if cls.send_simple(email, full_subject, body):
                    sent += 1
        except Exception as e:
            logger.error(f"[EmailGateway.send_admin_alert] {e}")
        return sent

    @classmethod
    def send_withdrawal_notification(cls, user_email: str, username: str,
                                     amount: float, gateway: str,
                                     status: str, reference: str = '') -> bool:
        """Send withdrawal status email to user."""
        status_text = {'SUCCESS': 'Approved & Processing', 'FAILED': 'Rejected'}.get(status, status)
        emoji = '✅' if status == 'SUCCESS' else '❌'
        subject = f"{emoji} Withdrawal {status_text} — ৳{amount:,.2f}"
        body = (
            f"Dear {username},\n\n"
            f"Your withdrawal request has been {status_text}.\n\n"
            f"Amount:   ৳{amount:,.2f}\n"
            f"Gateway:  {gateway}\n"
            f"Status:   {status_text}\n"
            f"Reference: {reference or 'Pending'}\n\n"
            f"Time: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"If you have questions, contact support.\n"
        )
        return cls.send_simple(user_email, subject, body)

    @classmethod
    def send_admin_digest(cls, stats: Dict, recipient_emails: List[str]) -> int:
        """Send daily admin digest email."""
        sent = 0
        subject = f"📊 Admin Digest — {timezone.now().strftime('%Y-%m-%d')}"
        body = (
            f"Daily Platform Summary\n{'='*40}\n\n"
            f"Users:        {stats.get('users', {}).get('new_today', 0)} new today\n"
            f"Revenue:      ৳{stats.get('revenue', {}).get('total_earned', 0):,.2f}\n"
            f"Withdrawals:  {stats.get('pending_payouts', {}).get('count', 0)} pending\n"
            f"Fraud Alerts: {stats.get('fraud', {}).get('total', 0)} (24h)\n"
            f"System:       {stats.get('system', {}).get('overall_health', 'unknown')}\n\n"
            f"Generated: {timezone.now().isoformat()}\n"
        )
        for email in recipient_emails:
            if cls.send_simple(email, subject, body, from_email=cls.ADMIN_FROM):
                sent += 1
        return sent

    @classmethod
    def send_maintenance_notice(cls, message: str, duration: int, all_users: bool = False) -> int:
        """Send maintenance notice email."""
        subject = "⚠️ Scheduled Maintenance Notice"
        body = (
            f"Dear User,\n\n"
            f"We have scheduled maintenance for our platform.\n\n"
            f"Message:  {message}\n"
            f"Duration: Approximately {duration} minutes\n\n"
            f"We apologize for any inconvenience.\n"
        )
        if all_users:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            emails = list(User.objects.filter(
                is_active=True, email__isnull=False
            ).values_list('email', flat=True)[:10000])
            # Use bulk send
            messages = [(subject, body, cls.DEFAULT_FROM, [e]) for e in emails if e]
            try:
                send_mass_mail(messages, fail_silently=True)
                return len(messages)
            except Exception:
                return 0
        return 0

    @classmethod
    def send_kyc_result(cls, user_email: str, username: str, result: str, reason: str = '') -> bool:
        """Send KYC approval/rejection email."""
        if result == 'approved':
            subject = "✅ Identity Verification Approved"
            body = f"Dear {username},\n\nYour identity has been verified. You can now access all features.\n"
        else:
            subject = "❌ Identity Verification Rejected"
            body = f"Dear {username},\n\nYour KYC was rejected.\nReason: {reason}\nPlease resubmit.\n"
        return cls.send_simple(user_email, subject, body)


email_gateway = EmailGateway()