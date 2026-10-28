# api/support/feature_flags.py
"""
Feature flags for support system.
Enable/disable features without deployment.
Flags stored in: settings.py → DB → cache (in order of priority).
"""
import logging
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

# Flag cache TTL (2 minutes)
FLAG_CACHE_TTL = 120

# ── Default flag values (can be overridden in settings.py) ───
DEFAULTS = {
    'SUPPORT_CHAT_ENABLED':           True,
    'SUPPORT_AI_AUTO_RESPONSE':       False,
    'SUPPORT_OFFER_DISPUTES':         True,
    'SUPPORT_WITHDRAWAL_DISPUTES':    True,
    'SUPPORT_KB_ENABLED':             True,
    'SUPPORT_CSAT_ENABLED':           True,
    'SUPPORT_WEBSOCKET_ENABLED':      True,
    'SUPPORT_COLLISION_DETECTION':    True,
    'SUPPORT_VPN_CHECK':              True,
    'SUPPORT_GAMIFICATION':           True,
    'SUPPORT_CHURN_PREDICTION':       False,
    'SUPPORT_VOICE_TICKETS':          False,
    'SUPPORT_PROACTIVE_CHAT':         False,
    'SUPPORT_SENTIMENT_ESCALATION':   True,
    'SUPPORT_AUTO_KB_SUGGEST':        True,
    'SUPPORT_AGENT_ROUTING':          True,
    'SUPPORT_SLA_ENFORCEMENT':        True,
    'SUPPORT_ANALYTICS_TRACKING':     True,
    'SUPPORT_AUDIT_LOGGING':          True,
    'SUPPORT_TELEGRAM_INTEGRATION':   False,
    'SUPPORT_WHATSAPP_INTEGRATION':   False,
    'SUPPORT_EMAIL_TO_TICKET':        False,
    'SUPPORT_FACEBOOK_INTEGRATION':   False,
    'SUPPORT_SLACK_ALERTS':           False,
}


def is_enabled(flag_name: str, default: bool = None) -> bool:
    """
    Check if a feature flag is enabled.
    Priority: settings.py → DB SupportSettings → DEFAULTS
    """
    # 1. Check settings.py override
    override = getattr(settings, flag_name, None)
    if override is not None:
        return bool(override)

    # 2. Check cache
    cache_key = f'support:flag:{flag_name}'
    cached    = cache.get(cache_key)
    if cached is not None:
        return bool(cached)

    # 3. Check DB (SupportSettings JSON field if available)
    try:
        from api.support.models import SupportSettings
        obj, _ = SupportSettings.objects.get_or_create(id=1)
        flags  = getattr(obj, 'feature_flags', None) or {}
        if flag_name in flags:
            val = bool(flags[flag_name])
            cache.set(cache_key, val, timeout=FLAG_CACHE_TTL)
            return val
    except Exception:
        pass

    # 4. Default
    val = DEFAULTS.get(flag_name, default if default is not None else False)
    cache.set(cache_key, val, timeout=FLAG_CACHE_TTL)
    return val


def enable(flag_name: str) -> None:
    """Enable a feature flag."""
    cache.set(f'support:flag:{flag_name}', True, timeout=FLAG_CACHE_TTL)
    logger.info(f'Feature flag enabled: {flag_name}')


def disable(flag_name: str) -> None:
    """Disable a feature flag."""
    cache.set(f'support:flag:{flag_name}', False, timeout=FLAG_CACHE_TTL)
    logger.info(f'Feature flag disabled: {flag_name}')


def reset(flag_name: str) -> None:
    """Reset flag to default."""
    cache.delete(f'support:flag:{flag_name}')


def get_all() -> dict:
    """Get all flag states."""
    return {flag: is_enabled(flag) for flag in DEFAULTS}


# ── Convenience helpers ───────────────────────────────────────
def chat_enabled() -> bool:
    return is_enabled('SUPPORT_CHAT_ENABLED')

def ai_auto_response_enabled() -> bool:
    return is_enabled('SUPPORT_AI_AUTO_RESPONSE')

def disputes_enabled() -> bool:
    return is_enabled('SUPPORT_OFFER_DISPUTES')

def sla_enabled() -> bool:
    return is_enabled('SUPPORT_SLA_ENFORCEMENT')

def sentiment_escalation_enabled() -> bool:
    return is_enabled('SUPPORT_SENTIMENT_ESCALATION')

def audit_logging_enabled() -> bool:
    return is_enabled('SUPPORT_AUDIT_LOGGING')