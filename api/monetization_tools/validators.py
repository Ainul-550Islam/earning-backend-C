"""
api/monetization_tools/validators.py
======================================
Reusable field-level and object-level validators.
"""

from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from .constants import (
    MIN_CAMPAIGN_BUDGET_USD, MAX_CAMPAIGN_BUDGET_USD,
    MIN_BID_AMOUNT, MAX_BID_AMOUNT,
    MIN_FLOOR_ECPM, MAX_FLOOR_ECPM,
    MIN_REWARD_AMOUNT, MAX_REWARD_AMOUNT,
    MIN_TRANSACTION_AMOUNT, MAX_TRANSACTION_AMOUNT,
    MAX_TRIAL_DAYS, MIN_AB_TRAFFIC_SPLIT,
)


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------

def validate_positive_decimal(value):
    if value is not None and value < 0:
        raise ValidationError(_("Value must be zero or positive."))


def validate_percentage(value):
    if not (Decimal('0') <= value <= Decimal('100')):
        raise ValidationError(_("Value must be between 0 and 100."))


def validate_future_date(value):
    if value and value <= timezone.now():
        raise ValidationError(_("Date must be in the future."))


def validate_iso_country_code(value):
    if value and len(value) != 2:
        raise ValidationError(_("Country code must be 2 characters (ISO 3166-1 alpha-2)."))


# ---------------------------------------------------------------------------
# Ad Campaign
# ---------------------------------------------------------------------------

def validate_campaign_budget(value):
    if value < MIN_CAMPAIGN_BUDGET_USD:
        raise ValidationError(
            _("Campaign budget must be at least $%(min)s.") % {'min': MIN_CAMPAIGN_BUDGET_USD}
        )
    if value > MAX_CAMPAIGN_BUDGET_USD:
        raise ValidationError(
            _("Campaign budget cannot exceed $%(max)s.") % {'max': MAX_CAMPAIGN_BUDGET_USD}
        )


def validate_bid_amount(value):
    if value < MIN_BID_AMOUNT or value > MAX_BID_AMOUNT:
        raise ValidationError(
            _("Bid amount must be between %(min)s and %(max)s.") % {
                'min': MIN_BID_AMOUNT, 'max': MAX_BID_AMOUNT
            }
        )


# ---------------------------------------------------------------------------
# Offer / Reward
# ---------------------------------------------------------------------------

def validate_reward_amount(value):
    if value < MIN_REWARD_AMOUNT:
        raise ValidationError(
            _("Reward amount must be at least %(min)s.") % {'min': MIN_REWARD_AMOUNT}
        )
    if value > MAX_REWARD_AMOUNT:
        raise ValidationError(
            _("Reward amount cannot exceed %(max)s.") % {'max': MAX_REWARD_AMOUNT}
        )


def validate_offer_age(value):
    if value < 13:
        raise ValidationError(_("Minimum user age must be at least 13."))
    if value > 100:
        raise ValidationError(_("Minimum user age cannot exceed 100."))


# ---------------------------------------------------------------------------
# Floor Price / eCPM
# ---------------------------------------------------------------------------

def validate_floor_ecpm(value):
    if value < MIN_FLOOR_ECPM or value > MAX_FLOOR_ECPM:
        raise ValidationError(
            _("Floor eCPM must be between %(min)s and %(max)s.") % {
                'min': MIN_FLOOR_ECPM, 'max': MAX_FLOOR_ECPM
            }
        )


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------

def validate_payment_amount(value):
    if value < MIN_TRANSACTION_AMOUNT:
        raise ValidationError(
            _("Transaction amount must be at least %(min)s.") % {'min': MIN_TRANSACTION_AMOUNT}
        )
    if value > MAX_TRANSACTION_AMOUNT:
        raise ValidationError(
            _("Transaction amount cannot exceed %(max)s.") % {'max': MAX_TRANSACTION_AMOUNT}
        )


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------

def validate_trial_days(value):
    if value < 0:
        raise ValidationError(_("Trial days cannot be negative."))
    if value > MAX_TRIAL_DAYS:
        raise ValidationError(
            _("Trial period cannot exceed %(max)s days.") % {'max': MAX_TRIAL_DAYS}
        )


def validate_subscription_price(value):
    if value < Decimal('0.00'):
        raise ValidationError(_("Subscription price cannot be negative."))


# ---------------------------------------------------------------------------
# A/B Testing
# ---------------------------------------------------------------------------

def validate_ab_traffic_split(value):
    if value < MIN_AB_TRAFFIC_SPLIT or value > 100:
        raise ValidationError(
            _("Traffic split must be between %(min)s%% and 100%%.") % {
                'min': MIN_AB_TRAFFIC_SPLIT
            }
        )


def validate_ab_variants(value):
    """Validate A/B test variants JSON structure."""
    if not isinstance(value, list):
        raise ValidationError(_("Variants must be a list."))
    if len(value) < 2:
        raise ValidationError(_("At least 2 variants are required for an A/B test."))
    total_weight = sum(v.get('weight', 0) for v in value)
    if total_weight != 100:
        raise ValidationError(_("Variant weights must sum to 100."))
    for v in value:
        if 'name' not in v:
            raise ValidationError(_("Each variant must have a 'name' field."))


# ---------------------------------------------------------------------------
# JSON field validators
# ---------------------------------------------------------------------------

def validate_country_code_list(value):
    """Validate a list of ISO country codes."""
    if not isinstance(value, list):
        raise ValidationError(_("Must be a list of country codes."))
    for code in value:
        if not isinstance(code, str) or len(code) != 2:
            raise ValidationError(
                _("'%(code)s' is not a valid 2-letter country code.") % {'code': code}
            )


def validate_device_list(value):
    allowed = {'mobile', 'tablet', 'desktop', 'tv', 'other'}
    if not isinstance(value, list):
        raise ValidationError(_("Must be a list of device types."))
    for d in value:
        if d not in allowed:
            raise ValidationError(
                _("'%(d)s' is not a valid device type. Allowed: %(allowed)s") % {
                    'd': d, 'allowed': ', '.join(allowed)
                }
            )


# ---------------------------------------------------------------------------
# Coupon
# ---------------------------------------------------------------------------

def validate_coupon_code(value: str):
    """Coupon codes: uppercase alphanumeric, 4–30 chars."""
    import re
    if not re.match(r'^[A-Z0-9_\-]{4,30}$', value.upper()):
        raise ValidationError(
            _("Coupon code must be 4–30 alphanumeric characters (A-Z, 0-9, -, _).")
        )


def validate_coupon_discount_pct(value):
    if not (0 <= value <= 100):
        raise ValidationError(_("Discount percentage must be between 0 and 100."))


def validate_coupon_multiplier(value):
    if value < 1:
        raise ValidationError(_("Coupon multiplier must be at least 1.0 (no negative boost)."))
    if value > 10:
        raise ValidationError(_("Coupon multiplier cannot exceed 10x."))


# ---------------------------------------------------------------------------
# Referral
# ---------------------------------------------------------------------------

def validate_referral_commission_pct(value):
    if not (0 <= value <= 100):
        raise ValidationError(_("Commission percentage must be between 0 and 100."))


def validate_referral_levels(value: int):
    if not (1 <= value <= 5):
        raise ValidationError(_("Referral levels must be between 1 and 5."))


def validate_referral_code(value: str):
    import re
    if not re.match(r'^[A-Z0-9]{6,20}$', value.upper()):
        raise ValidationError(_("Referral code must be 6–20 alphanumeric characters."))


# ---------------------------------------------------------------------------
# Flash Sale
# ---------------------------------------------------------------------------

def validate_flash_sale_multiplier(value):
    if value < 1:
        raise ValidationError(_("Flash sale multiplier must be at least 1.0."))
    if value > 100:
        raise ValidationError(_("Flash sale multiplier cannot exceed 100x."))


def validate_flash_sale_dates(start, end):
    if end <= start:
        raise ValidationError(_("Flash sale end date must be after start date."))
    from datetime import timedelta
    if (end - start).total_seconds() < 3600:
        raise ValidationError(_("Flash sale must last at least 1 hour."))


# ---------------------------------------------------------------------------
# Payout
# ---------------------------------------------------------------------------

def validate_payout_account_number(value: str):
    if not value or len(value.strip()) < 5:
        raise ValidationError(_("Account number must be at least 5 characters."))
    if len(value) > 50:
        raise ValidationError(_("Account number cannot exceed 50 characters."))


def validate_payout_amount(value):
    from .constants import MIN_TRANSACTION_AMOUNT, MAX_TRANSACTION_AMOUNT
    if value < MIN_TRANSACTION_AMOUNT:
        raise ValidationError(
            _("Payout amount must be at least %(min)s.") % {'min': MIN_TRANSACTION_AMOUNT}
        )
    if value > MAX_TRANSACTION_AMOUNT:
        raise ValidationError(
            _("Payout amount cannot exceed %(max)s.") % {'max': MAX_TRANSACTION_AMOUNT}
        )


# ---------------------------------------------------------------------------
# Publisher Account
# ---------------------------------------------------------------------------

def validate_publisher_revenue_share(value):
    if value is not None and not (0 <= value <= 1):
        raise ValidationError(_("Revenue share must be between 0 and 1 (e.g. 0.70 = 70%)."))


def validate_credit_limit(value):
    if value < 0:
        raise ValidationError(_("Credit limit cannot be negative."))


# ---------------------------------------------------------------------------
# Ad Creative
# ---------------------------------------------------------------------------

def validate_creative_dimensions(width, height):
    if width is not None and height is not None:
        if width <= 0 or height <= 0:
            raise ValidationError(_("Creative dimensions must be positive."))
        if width > 5000 or height > 5000:
            raise ValidationError(_("Creative dimensions cannot exceed 5000px."))


def validate_creative_file_size(size_kb: int):
    from .constants import MAX_CREATIVE_FILE_SIZE_MB
    if size_kb > MAX_CREATIVE_FILE_SIZE_MB * 1024:
        raise ValidationError(
            _("Creative file size cannot exceed %(max)sMB.") % {'max': MAX_CREATIVE_FILE_SIZE_MB}
        )


def validate_vast_tag_url(value: str):
    if value and not (value.startswith('http://') or value.startswith('https://')):
        raise ValidationError(_("VAST tag URL must start with http:// or https://."))


# ---------------------------------------------------------------------------
# Revenue Goal
# ---------------------------------------------------------------------------

def validate_goal_target(value):
    if value <= 0:
        raise ValidationError(_("Revenue goal target must be greater than zero."))


def validate_goal_dates(start, end):
    if end <= start:
        raise ValidationError(_("Goal end date must be after start date."))


# ---------------------------------------------------------------------------
# User Segment
# ---------------------------------------------------------------------------

def validate_segment_rules(value: dict):
    if not isinstance(value, dict):
        raise ValidationError(_("Segment rules must be a JSON object."))


# ---------------------------------------------------------------------------
# Spin Wheel
# ---------------------------------------------------------------------------

def validate_prize_weight(value: int):
    if value < 1:
        raise ValidationError(_("Prize weight must be at least 1."))
    if value > 10000:
        raise ValidationError(_("Prize weight cannot exceed 10000."))


def validate_spin_cost(value):
    if value < 0:
        raise ValidationError(_("Spin cost cannot be negative."))


# ---------------------------------------------------------------------------
# Postback
# ---------------------------------------------------------------------------

def validate_postback_signature(signature: str, payload: str, secret: str) -> bool:
    """Helper to validate HMAC-SHA256 postback signature. Returns bool."""
    from .utils import verify_hmac_signature
    return verify_hmac_signature(payload, signature, secret)
