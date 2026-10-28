# cms/email_service.py
"""
CMS Transactional Email Service.
Sends HTML emails for: welcome, reward, withdrawal, streak, referral.
Uses Django Anymail (Mailgun/SendGrid/SES) — falls back to console backend.
"""
import logging
from datetime import datetime
from typing import Optional
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _base_ctx(user=None) -> dict:
    """Base context for all emails."""
    site_url  = getattr(settings, 'SITE_URL', 'https://yoursite.com')
    site_name = getattr(settings, 'SITE_NAME', 'Earning Site')
    return {
        'site_url':       site_url,
        'site_name':      site_name,
        'year':           datetime.now().year,
        'username':       getattr(user, 'username', '') if user else '',
        'unsubscribe_url': f"{site_url}/unsubscribe/",
    }


def _send(to_email: str, subject: str, template: str, ctx: dict) -> bool:
    """Render and send an HTML email. Returns True on success."""
    try:
        html  = render_to_string(f"cms/email/{template}.html", ctx)
        plain = render_to_string(f"cms/email/{template}.txt",  ctx) if _template_exists(f"cms/email/{template}.txt") else _html_to_plain(html)
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=False)
        logger.info(f"[Email] Sent '{subject}' to {to_email}")
        return True
    except Exception as e:
        logger.error(f"[Email] Failed to send '{subject}' to {to_email}: {e}")
        return False


def _template_exists(name: str) -> bool:
    from django.template.loader import get_template
    from django.template.exceptions import TemplateDoesNotExist
    try:
        get_template(name)
        return True
    except TemplateDoesNotExist:
        return False


def _html_to_plain(html: str) -> str:
    """Strip HTML tags to make plain-text fallback."""
    import re
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


class CMSEmailService:
    """High-level email sending for all CMS events."""

    @classmethod
    def send_welcome(cls, user, referral_bonus: float = 0) -> bool:
        ctx = {**_base_ctx(user), 'referral_bonus': referral_bonus or ''}
        return _send(
            to_email=user.email,
            subject=f"Welcome to {ctx['site_name']}!",
            template='welcome',
            ctx=ctx,
        )

    @classmethod
    def send_reward_earned(cls, user, coins: float, usd_value: float,
                            source: str = 'Offer') -> bool:
        ctx = {
            **_base_ctx(user),
            'coins':     f"{coins:.0f}",
            'usd_value': f"{usd_value:.2f}",
            'source':    source,
        }
        return _send(
            to_email=user.email,
            subject=f"You earned {coins:.0f} coins!",
            template='reward_earned',
            ctx=ctx,
        )

    @classmethod
    def send_withdrawal_update(cls, user, amount: float, method: str,
                                status: str, reference: str = '') -> bool:
        ctx = {
            **_base_ctx(user),
            'amount':    f"{amount:.2f}",
            'method':    method,
            'status':    status,
            'reference': reference,
        }
        subjects = {
            'approved':   f"Withdrawal Approved: ${amount:.2f}",
            'paid':       f"Payment Sent: ${amount:.2f} via {method.upper()}",
            'rejected':   f"Withdrawal Update: Action Required",
            'processing': f"Withdrawal Processing: ${amount:.2f}",
        }
        return _send(
            to_email=user.email,
            subject=subjects.get(status, f"Withdrawal {status.title()}: ${amount:.2f}"),
            template='withdrawal_update',
            ctx=ctx,
        )

    @classmethod
    def send_streak_milestone(cls, user, days: int,
                               bonus_coins: float) -> bool:
        ctx = {
            **_base_ctx(user),
            'streak_days': days,
            'bonus_coins': f"{bonus_coins:.0f}",
        }
        return _send(
            to_email=user.email,
            subject=f"🔥 {days}-Day Streak! Bonus earned",
            template='streak_milestone',
            ctx=ctx,
        )

    @classmethod
    def send_referral_bonus(cls, referrer, referred_username: str,
                             bonus_coins: float) -> bool:
        ctx = {
            **_base_ctx(referrer),
            'referred_username': referred_username,
            'bonus_coins':       f"{bonus_coins:.0f}",
        }
        return _send(
            to_email=referrer.email,
            subject=f"Referral Bonus: {referred_username} earned you {bonus_coins:.0f} coins!",
            template='referral_bonus',
            ctx=ctx,
        )
