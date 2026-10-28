# api/referral/validator.py
# Standalone validators — not tied to any specific serializer
# ============================================================

import re
import logging
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


def validate_referral_code(value: str) -> str:
    """
    Validate referral code format.
    Must be 4-30 uppercase alphanumeric + optional dash/underscore.
    """
    if not value:
        raise ValidationError(_('Referral code cannot be empty.'))
    value = value.strip().upper()
    if len(value) < 4:
        raise ValidationError(_('Referral code must be at least 4 characters.'))
    if len(value) > 30:
        raise ValidationError(_('Referral code cannot exceed 30 characters.'))
    if not re.match(r'^[A-Z0-9_-]+$', value):
        raise ValidationError(
            _('Referral code can only contain letters, numbers, hyphens, and underscores.')
        )
    return value


def validate_commission_amount(value) -> Decimal:
    """Validate commission amount — must be positive decimal."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(_('Invalid commission amount.'))
    if amount <= 0:
        raise ValidationError(_('Commission amount must be positive.'))
    if amount > Decimal('999999.99'):
        raise ValidationError(_('Commission amount exceeds maximum allowed.'))
    return amount


def validate_commission_rate(value) -> Decimal:
    """Validate commission rate — must be 0-100."""
    try:
        rate = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValidationError(_('Invalid commission rate.'))
    if rate < 0:
        raise ValidationError(_('Commission rate cannot be negative.'))
    if rate > 100:
        raise ValidationError(_('Commission rate cannot exceed 100%.'))
    return rate


def validate_referral_level(value: int) -> int:
    """Validate referral level (1, 2, or 3)."""
    try:
        level = int(value)
    except (TypeError, ValueError):
        raise ValidationError(_('Referral level must be a number.'))
    if level not in (1, 2, 3):
        raise ValidationError(_('Referral level must be 1, 2, or 3.'))
    return level


def validate_no_self_referral(referrer, referred_user):
    """Raise if referrer and referred_user are the same person."""
    if referrer and referred_user and referrer.pk == referred_user.pk:
        raise ValidationError(_('A user cannot refer themselves.'))


def validate_not_already_referred(referred_user):
    """Raise if user already has a referrer."""
    try:
        from api.referral.models import Referral
        if Referral.objects.filter(referred_user=referred_user).exists():
            raise ValidationError(_('This user already has a referrer.'))
    except ImportError:
        pass


def validate_ip_address(ip: str) -> bool:
    """Check if string is a valid IPv4 or IPv6 address."""
    if not ip:
        return True
    ipv4 = re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip)
    if ipv4:
        parts = ip.split('.')
        return all(0 <= int(p) <= 255 for p in parts)
    ipv6 = re.match(r'^[0-9a-fA-F:]+$', ip)
    return bool(ipv6)


def validate_payout_amount(amount, min_threshold: Decimal = None) -> Decimal:
    """Validate payout amount meets minimum threshold."""
    amount = validate_commission_amount(amount)
    if min_threshold is None:
        try:
            from api.referral.models import ReferralSettings
            settings = ReferralSettings.objects.first()
            min_threshold = settings.min_payout_threshold if settings else Decimal('50')
        except Exception:
            min_threshold = Decimal('50')
    if amount < min_threshold:
        raise ValidationError(
            _(f'Payout amount must be at least {min_threshold}.')
        )
    return amount


def validate_email_invitation(email: str, referrer) -> str:
    """Validate email invitation — check format and daily limit."""
    import re as _re
    email = email.lower().strip()
    if not _re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
        raise ValidationError(_('Invalid email address.'))
    # Check if user already invited this email today
    try:
        from api.referral.models import ReferralEmailInvitation
        from django.utils import timezone
        today_count = ReferralEmailInvitation.objects.filter(
            referrer=referrer,
            created_at__date=timezone.now().date(),
        ).count()
        if today_count >= 20:
            raise ValidationError(_('Daily invitation limit of 20 reached.'))
    except (ImportError, ValidationError):
        raise
    except Exception:
        pass
    return email


def validate_campaign_dates(start_date, end_date):
    """Validate campaign date range."""
    from django.utils import timezone
    if start_date and end_date and start_date >= end_date:
        raise ValidationError(_('End date must be after start date.'))
    if end_date and end_date < timezone.now():
        raise ValidationError(_('End date cannot be in the past.'))


def validate_fraud_score(value: int) -> int:
    """Validate fraud score (0-100)."""
    try:
        score = int(value)
    except (TypeError, ValueError):
        raise ValidationError(_('Fraud score must be an integer.'))
    if not 0 <= score <= 100:
        raise ValidationError(_('Fraud score must be between 0 and 100.'))
    return score