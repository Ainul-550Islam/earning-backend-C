# FILE 95 of 257 — notifications/EmailNotifier.py
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
import logging
logger = logging.getLogger(__name__)

TEMPLATES = {
    'deposit_completed':    'payment_gateways/email/deposit_completed.html',
    'deposit_failed':       'payment_gateways/email/deposit_failed.html',
    'withdrawal_submitted': 'payment_gateways/email/withdrawal_submitted.html',
    'withdrawal_completed': 'payment_gateways/email/withdrawal_completed.html',
    'withdrawal_rejected':  'payment_gateways/email/withdrawal_rejected.html',
    'refund_completed':     'payment_gateways/email/refund_completed.html',
    'refund_failed':        'payment_gateways/email/refund_failed.html',
    'payout_approved':      'payment_gateways/email/payout_approved.html',
}

SUBJECTS = {
    'deposit_completed':    '✅ Deposit Successful',
    'deposit_failed':       '❌ Deposit Failed',
    'withdrawal_submitted': '📤 Withdrawal Request Submitted',
    'withdrawal_completed': '✅ Withdrawal Completed',
    'withdrawal_rejected':  '❌ Withdrawal Rejected',
    'refund_completed':     '✅ Refund Processed',
    'refund_failed':        '❌ Refund Failed',
    'payout_approved':      '✅ Payout Approved',
}

class EmailNotifier:
    def send(self, recipient: str, notification_type: str, context: dict = None):
        template = TEMPLATES.get(notification_type)
        subject  = SUBJECTS.get(notification_type, 'Payment Notification')
        if not template:
            logger.warning(f'EmailNotifier: no template for {notification_type}')
            return False
        try:
            ctx      = context or {}
            html_msg = render_to_string(template, ctx)
            text_msg = f"Payment Notification: {subject}"
            msg = EmailMultiAlternatives(
                subject=subject, body=text_msg,
                from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient]
            )
            msg.attach_alternative(html_msg, "text/html")
            msg.send()
            logger.info(f'Email sent: {notification_type} → {recipient}')
            return True
        except Exception as e:
            logger.error(f'EmailNotifier.send error: {e}')
            return False

    def send_raw(self, recipient: str, subject: str, body: str):
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient])
            return True
        except Exception as e:
            logger.error(f'EmailNotifier.send_raw error: {e}')
            return False

    def send_daily_report(self, recipients: list, report_date):
        from django.db.models import Sum, Count
        from payment_gateways.models import GatewayTransaction
        summary = GatewayTransaction.objects.filter(
            created_at__date=report_date, status='completed', transaction_type='deposit'
        ).aggregate(count=Count('id'), total=Sum('amount'))
        body = f"Daily Report {report_date}\nTotal Deposits: {summary['count']}\nTotal Amount: {summary['total'] or 0}"
        for email in recipients:
            self.send_raw(email, f'Daily Payment Report - {report_date}', body)
