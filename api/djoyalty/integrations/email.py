# api/djoyalty/integrations/email.py
"""
Email Integrations -- Django SMTP + SendGrid + Mailgun।
Loyalty notifications, vouchers, receipts email পাঠানো।

Settings:
    DJOYALTY_EMAIL_PROVIDER = 'smtp'  # 'smtp' | 'sendgrid' | 'mailgun'

    # SendGrid:
    DJOYALTY_SENDGRID_API_KEY = 'SG.xxx'
    DJOYALTY_EMAIL_FROM = 'loyalty@yourbrand.com'

    # Mailgun:
    DJOYALTY_MAILGUN_API_KEY = 'xxx'
    DJOYALTY_MAILGUN_DOMAIN = 'mg.yourdomain.com'
"""
import logging
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class DjangoSMTPEmail:
    """Django built-in SMTP email।"""

    def send(self, to: str, subject: str, html_body: str, text_body: str = '') -> bool:
        try:
            from_email = getattr(settings, 'DJOYALTY_EMAIL_FROM',
                                  getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@djoyalty.com'))
            msg = EmailMultiAlternatives(subject, text_body or '', from_email, [to])
            msg.attach_alternative(html_body, 'text/html')
            msg.send()
            logger.info('DjangoSMTPEmail: sent to %s -- %s', to, subject)
            return True
        except Exception as e:
            logger.error('DjangoSMTPEmail.send error: %s', e)
            return False

    @staticmethod
    def is_configured() -> bool:
        return bool(getattr(settings, 'EMAIL_HOST', None))


class SendGridIntegration:
    """
    SendGrid transactional email।
    pip install sendgrid

    Settings:
        DJOYALTY_SENDGRID_API_KEY
        DJOYALTY_EMAIL_FROM
    """

    def __init__(self):
        self.api_key = getattr(settings, 'DJOYALTY_SENDGRID_API_KEY', '')
        self.from_email = getattr(settings, 'DJOYALTY_EMAIL_FROM', 'noreply@djoyalty.com')

    def send(self, to: str, subject: str, html_body: str, text_body: str = '') -> bool:
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content

            sg = sendgrid.SendGridAPIClient(api_key=self.api_key)
            mail = Mail(
                from_email=Email(self.from_email),
                to_emails=To(to),
                subject=subject,
                html_content=Content('text/html', html_body),
            )
            response = sg.client.mail.send.post(request_body=mail.get())
            success = response.status_code in (200, 202)
            if success:
                logger.info('SendGridIntegration: email sent to %s', to)
            return success
        except ImportError:
            logger.error('SendGrid: sendgrid package not installed. pip install sendgrid')
            return False
        except Exception as e:
            logger.error('SendGridIntegration.send error: %s', e)
            return False

    def send_template(self, to: str, template_id: str, template_data: dict) -> bool:
        """SendGrid dynamic template ব্যবহার করো।"""
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, DynamicTemplateData

            sg = sendgrid.SendGridAPIClient(api_key=self.api_key)
            mail = Mail(from_email=self.from_email, to_emails=to)
            mail.template_id = template_id
            mail.dynamic_template_data = DynamicTemplateData(template_data)
            response = sg.client.mail.send.post(request_body=mail.get())
            return response.status_code in (200, 202)
        except Exception as e:
            logger.error('SendGridIntegration.send_template error: %s', e)
            return False

    @staticmethod
    def is_configured() -> bool:
        return bool(getattr(settings, 'DJOYALTY_SENDGRID_API_KEY', ''))


class MailgunIntegration:
    """
    Mailgun transactional email।
    pip install requests (already installed)

    Settings:
        DJOYALTY_MAILGUN_API_KEY
        DJOYALTY_MAILGUN_DOMAIN
        DJOYALTY_EMAIL_FROM
    """

    def __init__(self):
        self.api_key    = getattr(settings, 'DJOYALTY_MAILGUN_API_KEY', '')
        self.domain     = getattr(settings, 'DJOYALTY_MAILGUN_DOMAIN', '')
        self.from_email = getattr(settings, 'DJOYALTY_EMAIL_FROM', f'loyalty@{self.domain}')

    def send(self, to: str, subject: str, html_body: str, text_body: str = '') -> bool:
        try:
            import requests as req
            response = req.post(
                f'https://api.mailgun.net/v3/{self.domain}/messages',
                auth=('api', self.api_key),
                data={
                    'from': self.from_email,
                    'to': to,
                    'subject': subject,
                    'text': text_body or '',
                    'html': html_body,
                },
                timeout=10,
            )
            success = response.status_code == 200
            if success:
                logger.info('MailgunIntegration: email sent to %s', to)
            return success
        except Exception as e:
            logger.error('MailgunIntegration.send error: %s', e)
            return False

    @staticmethod
    def is_configured() -> bool:
        return bool(
            getattr(settings, 'DJOYALTY_MAILGUN_API_KEY', '') and
            getattr(settings, 'DJOYALTY_MAILGUN_DOMAIN', '')
        )


# ─── Unified Email Service ─────────────────────────────────────────────────────

class EmailService:
    """
    Unified email service -- auto-select provider from settings।

    settings.py:
        DJOYALTY_EMAIL_PROVIDER = 'smtp'  # or 'sendgrid' or 'mailgun'

    Usage:
        EmailService.send('user@example.com', 'Subject', '<h1>Hello</h1>')
    """

    @staticmethod
    def get_provider():
        name = getattr(settings, 'DJOYALTY_EMAIL_PROVIDER', 'smtp')
        providers = {
            'smtp':      DjangoSMTPEmail,
            'sendgrid':  SendGridIntegration,
            'mailgun':   MailgunIntegration,
        }
        return providers.get(name, DjangoSMTPEmail)()

    @classmethod
    def send(cls, to: str, subject: str, html_body: str, text_body: str = '') -> bool:
        if not to:
            return False
        provider = cls.get_provider()
        return provider.send(to, subject, html_body, text_body)

    # ─── Loyalty Email Templates ──────────────────────────────────

    @classmethod
    def send_welcome(cls, customer):
        if not customer.email or not customer.newsletter:
            return
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
          <h2 style="color:#3b82f6">স্বাগতম, {customer.firstname or customer.code}! 🎉</h2>
          <p>আপনি আমাদের Loyalty Program এ যোগ দিয়েছেন।</p>
          <p>আপনার Loyalty Number: <strong>{customer.loyalty_number or customer.code}</strong></p>
          <p>এখনই পয়েন্ট অর্জন শুরু করুন!</p>
          <a href="#" style="background:#3b82f6;color:white;padding:10px 20px;text-decoration:none;border-radius:5px">App ডাউনলোড করুন</a>
        </div>
        """
        cls.send(customer.email, '🎉 Loyalty Program এ স্বাগতম!', html)

    @classmethod
    def send_points_statement(cls, customer, points_earned: float,
                               current_balance: float, transaction_ref: str):
        if not customer.email or not customer.newsletter:
            return
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
          <h2 style="color:#3b82f6">Points Statement 💰</h2>
          <p>প্রিয় {customer.firstname or customer.code},</p>
          <table style="width:100%;border-collapse:collapse">
            <tr><td style="padding:8px;border:1px solid #ddd">অর্জিত পয়েন্ট</td>
                <td style="padding:8px;border:1px solid #ddd;color:green"><strong>+{points_earned}</strong></td></tr>
            <tr><td style="padding:8px;border:1px solid #ddd">বর্তমান Balance</td>
                <td style="padding:8px;border:1px solid #ddd"><strong>{current_balance}</strong></td></tr>
            <tr><td style="padding:8px;border:1px solid #ddd">Reference</td>
                <td style="padding:8px;border:1px solid #ddd">{transaction_ref}</td></tr>
          </table>
        </div>
        """
        cls.send(customer.email, f'💰 +{points_earned} Points অর্জিত!', html)

    @classmethod
    def send_tier_upgrade(cls, customer, old_tier: str, new_tier: str, benefits: list = None):
        if not customer.email or not customer.newsletter:
            return
        benefits_html = ''.join(f'<li>✅ {b}</li>' for b in (benefits or []))
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
          <h2 style="color:#FFD700">🎊 Tier Upgrade!</h2>
          <p>অভিনন্দন {customer.firstname or customer.code}!</p>
          <p><s>{old_tier.title()}</s> -> <strong style="color:#FFD700">{new_tier.title()}</strong></p>
          {f'<ul>{benefits_html}</ul>' if benefits_html else ''}
        </div>
        """
        cls.send(customer.email, f'🏆 {new_tier.title()} Tier Upgrade!', html)

    @classmethod
    def send_voucher(cls, customer, code: str, discount: str, expires_at=None):
        if not customer.email or not customer.newsletter:
            return
        expiry = f'<p>মেয়াদ: {expires_at.strftime("%d %b %Y")}</p>' if expires_at else ''
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
          <h2 style="color:#3b82f6">🎟️ আপনার Voucher</h2>
          <p>প্রিয় {customer.firstname or customer.code},</p>
          <div style="background:#f3f4f6;padding:20px;text-align:center;border-radius:8px">
            <h1 style="letter-spacing:4px;color:#3b82f6">{code}</h1>
            <p><strong>{discount}</strong> Discount</p>
          </div>
          {expiry}
        </div>
        """
        cls.send(customer.email, f'🎟️ Voucher Code: {code}', html)

    @classmethod
    def send_cashout_confirmation(cls, customer, amount: float,
                                   method: str, ref: str):
        if not customer.email or not customer.newsletter:
            return
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
          <h2 style="color:#22c55e">✅ Cashout Successful!</h2>
          <p>প্রিয় {customer.firstname or customer.code},</p>
          <table style="width:100%;border-collapse:collapse">
            <tr><td style="padding:8px;border:1px solid #ddd">Amount</td>
                <td style="padding:8px;border:1px solid #ddd"><strong>{amount} BDT</strong></td></tr>
            <tr><td style="padding:8px;border:1px solid #ddd">Method</td>
                <td style="padding:8px;border:1px solid #ddd">{method}</td></tr>
            <tr><td style="padding:8px;border:1px solid #ddd">Reference</td>
                <td style="padding:8px;border:1px solid #ddd">{ref}</td></tr>
          </table>
        </div>
        """
        cls.send(customer.email, f'✅ {amount} BDT Cashout সফল!', html)
