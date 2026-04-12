"""
api/monetization_tools/config.py
===================================
Runtime configuration for the monetization_tools app.
Reads from Django settings with safe defaults.
"""

from django.conf import settings


def _mt(key: str, default=None):
    """Read from settings.MONETIZATION_TOOLS dict."""
    return getattr(settings, 'MONETIZATION_TOOLS', {}).get(key, default)


# ---------------------------------------------------------------------------
# Coin / Currency
# ---------------------------------------------------------------------------

# How many coins equal 1 USD
COINS_PER_USD: float = _mt('COINS_PER_USD', 100.0)

# Minimum withdrawal in USD
MIN_WITHDRAWAL_USD: float = _mt('MIN_WITHDRAWAL_USD', 1.0)

# Maximum withdrawal per transaction in USD
MAX_WITHDRAWAL_USD: float = _mt('MAX_WITHDRAWAL_USD', 500.0)

# Default currency for subscriptions / payments
DEFAULT_CURRENCY: str = _mt('DEFAULT_CURRENCY', 'BDT')

# ---------------------------------------------------------------------------
# Offerwall
# ---------------------------------------------------------------------------

# Global on/off switch
OFFERWALL_ENABLED: bool = _mt('OFFERWALL_ENABLED', True)

# Maximum pending completions per user at a time
MAX_PENDING_COMPLETIONS: int = _mt('MAX_PENDING_COMPLETIONS', 10)

# Postback shared secret (fallback; individual networks should override)
POSTBACK_SECRET: str = _mt('POSTBACK_SECRET', getattr(settings, 'SECRET_KEY', 'change-me')[:32])

# ---------------------------------------------------------------------------
# Fraud Detection
# ---------------------------------------------------------------------------

# Auto-reject completions with fraud_score >= this
FRAUD_AUTO_REJECT_THRESHOLD: int = _mt('FRAUD_AUTO_REJECT_THRESHOLD', 70)

# Flag (but don't auto-reject) completions with fraud_score >= this
FRAUD_FLAG_THRESHOLD: int = _mt('FRAUD_FLAG_THRESHOLD', 50)

# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------

SUBSCRIPTION_ENABLED: bool      = _mt('SUBSCRIPTION_ENABLED', True)
DEFAULT_TRIAL_DAYS: int          = _mt('DEFAULT_TRIAL_DAYS', 7)
GRACE_PERIOD_DAYS: int           = _mt('GRACE_PERIOD_DAYS', 3)

# ---------------------------------------------------------------------------
# Payment Gateways enabled
# ---------------------------------------------------------------------------

ENABLED_GATEWAYS: list = _mt('ENABLED_GATEWAYS', ['bkash', 'nagad', 'stripe'])

# ---------------------------------------------------------------------------
# Gamification
# ---------------------------------------------------------------------------

SPIN_WHEEL_ENABLED: bool         = _mt('SPIN_WHEEL_ENABLED', True)
SPIN_WHEEL_DAILY_LIMIT: int      = _mt('SPIN_WHEEL_DAILY_LIMIT', 3)
SCRATCH_CARD_ENABLED: bool       = _mt('SCRATCH_CARD_ENABLED', True)
SCRATCH_CARD_DAILY_LIMIT: int    = _mt('SCRATCH_CARD_DAILY_LIMIT', 5)
LEADERBOARD_TOP_N: int           = _mt('LEADERBOARD_TOP_N', 100)

# ---------------------------------------------------------------------------
# A/B Testing
# ---------------------------------------------------------------------------

AB_TESTING_ENABLED: bool         = _mt('AB_TESTING_ENABLED', True)

# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

# Keep raw impression/click logs for this many days before archiving
LOG_RETENTION_DAYS: int          = _mt('LOG_RETENTION_DAYS', 90)

# ---------------------------------------------------------------------------
# Feature flags (convenience dict)
# ---------------------------------------------------------------------------

FEATURE_FLAGS: dict = {
    'offerwall':        OFFERWALL_ENABLED,
    'subscription':     SUBSCRIPTION_ENABLED,
    'spin_wheel':       SPIN_WHEEL_ENABLED,
    'scratch_card':     SCRATCH_CARD_ENABLED,
    'ab_testing':       AB_TESTING_ENABLED,
}


def is_feature_enabled(feature: str) -> bool:
    """Check if a monetization feature flag is enabled."""
    return FEATURE_FLAGS.get(feature, False)
