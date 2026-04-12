# api/offer_inventory/marketing/email_marketing.py
"""
Email Marketing System.
Transactional and bulk email management with tracking.
Templates, unsubscribe management, bounce handling.
"""
import logging
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

DEFAULT_FROM = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@platform.com')


class EmailMarketingService:
    """Full email marketing lifecycle."""

    # ── Transactional emails ───────────────────────────────────────

    @staticmethod
    def send_welcome(user) -> bool:
        """Welcome email for new users."""
        return EmailMarketingService._send(
            to      =user.email,
            subject ='🎉 স্বাগতম! আপনার Earning যাত্রা শুরু হল',
            template='emails/welcome.html',
            context ={
                'user'    : user,
                'platform': getattr(settings, 'PLATFORM_NAME', 'Earning Platform'),
            }
        )

    @staticmethod
    def send_withdrawal_approved(user, amount, reference) -> bool:
        """Withdrawal approved notification."""
        return EmailMarketingService._send(
            to      =user.email,
            subject =f'✅ আপনার {amount} টাকা উইথড্রয়াল অনুমোদিত হয়েছে',
            template='emails/withdrawal_approved.html',
            context ={'user': user, 'amount': amount, 'reference': reference},
        )

    @staticmethod
    def send_fraud_alert(user, reason: str) -> bool:
        """Security alert email."""
        return EmailMarketingService._send(
            to      =user.email,
            subject ='⚠️ নিরাপত্তা সতর্কতা - আপনার অ্যাকাউন্ট',
            template='emails/fraud_alert.html',
            context ={'user': user, 'reason': reason},
        )

    @staticmethod
    def send_kyc_approved(user) -> bool:
        """KYC approval notification."""
        return EmailMarketingService._send(
            to      =user.email,
            subject ='✅ আপনার KYC যাচাই সম্পন্ন হয়েছে',
            template='emails/kyc_approved.html',
            context ={'user': user},
        )

    @staticmethod
    def send_new_offers(user, offers: list) -> bool:
        """New offers digest email."""
        return EmailMarketingService._send(
            to      =user.email,
            subject =f'🎯 {len(offers)}টি নতুন অফার আপনার জন্য!',
            template='emails/new_offers.html',
            context ={'user': user, 'offers': offers},
        )

    # ── Bulk email ─────────────────────────────────────────────────

    @classmethod
    def send_bulk(cls, subject: str, html_body: str,
                   recipients: list, text_body: str = '') -> dict:
        """
        Send bulk email campaign.
        Logs each email to EmailLog for tracking.
        """
        from api.offer_inventory.models import EmailLog
        import time

        sent = 0
        failed = 0

        for email in recipients:
            if not email or '@' not in email:
                continue

            # Check unsubscribe
            if cls._is_unsubscribed(email):
                continue

            try:
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body   =text_body or 'HTML email - please enable HTML',
                    from_email=DEFAULT_FROM,
                    to     =[email],
                )
                msg.attach_alternative(html_body, 'text/html')
                msg.send()

                EmailLog.objects.create(
                    recipient=email, subject=subject, status='sent',
                    sent_at=timezone.now(),
                )
                sent += 1
            except Exception as e:
                logger.error(f'Bulk email error to {email}: {e}')
                EmailLog.objects.create(
                    recipient=email, subject=subject, status='failed',
                    error=str(e)[:500],
                )
                failed += 1

            # Rate limit: 50 emails/sec
            if sent % 50 == 0:
                time.sleep(1)

        logger.info(f'Bulk email: sent={sent} failed={failed} subject="{subject}"')
        return {'sent': sent, 'failed': failed, 'total': sent + failed}

    # ── Unsubscribe management ─────────────────────────────────────

    @staticmethod
    def unsubscribe(email: str) -> bool:
        """Unsubscribe an email from marketing."""
        cache.set(f'email_unsub:{email}', '1', 86400 * 365)
        from api.offer_inventory.models import SystemSetting
        try:
            SystemSetting.objects.get_or_create(
                key=f'email_unsub:{email}',
                defaults={'value': '1', 'value_type': 'string',
                          'description': f'Unsubscribed: {email}'}
            )
        except Exception:
            pass
        logger.info(f'Email unsubscribed: {email}')
        return True

    @staticmethod
    def _is_unsubscribed(email: str) -> bool:
        if cache.get(f'email_unsub:{email}'):
            return True
        from api.offer_inventory.models import SystemSetting
        return SystemSetting.objects.filter(key=f'email_unsub:{email}').exists()

    # ── Core sender ────────────────────────────────────────────────

    @staticmethod
    def _send(to: str, subject: str, template: str,
               context: dict = None, text_template: str = None) -> bool:
        """Send a single email using a template."""
        from api.offer_inventory.models import EmailLog

        if not to:
            return False

        try:
            html = render_to_string(template, context or {})
            text = render_to_string(text_template, context or {}) if text_template else ''

            msg = EmailMultiAlternatives(
                subject=subject, body=text or subject,
                from_email=DEFAULT_FROM, to=[to]
            )
            msg.attach_alternative(html, 'text/html')
            msg.send()

            EmailLog.objects.create(
                recipient=to, subject=subject,
                template=template, status='sent', sent_at=timezone.now()
            )
            return True
        except Exception as e:
            logger.error(f'Email send error to {to}: {e}')
            EmailLog.objects.create(
                recipient=to, subject=subject, template=template,
                status='failed', error=str(e)[:500]
            )
            return False
