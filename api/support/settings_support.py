# api/support/settings_support.py
"""
Django settings for support system.
Add to your main settings.py:
    from api.support.settings_support import *

Or import selectively:
    from api.support.settings_support import SUPPORT_REST_FRAMEWORK, SUPPORT_CELERY_BEAT
"""
import os
from django.conf import settings


# ── Support system settings ───────────────────────────────────
SUPPORT_AI_ENABLED               = os.environ.get('SUPPORT_AI_ENABLED', 'false').lower() == 'true'
SUPPORT_ANTHROPIC_API_KEY        = os.environ.get('ANTHROPIC_API_KEY', '')
SUPPORT_OPENAI_API_KEY           = os.environ.get('OPENAI_API_KEY', '')
SUPPORT_ADMIN_EMAIL              = os.environ.get('SUPPORT_ADMIN_EMAIL', '')
SUPPORT_ENCRYPTION_KEY           = os.environ.get('SUPPORT_ENCRYPTION_KEY', '')
SUPPORT_SLACK_WEBHOOK_URL        = os.environ.get('SUPPORT_SLACK_WEBHOOK_URL', '')

# ── Ticket limits ─────────────────────────────────────────────
SUPPORT_MAX_ATTACHMENT_MB        = int(os.environ.get('SUPPORT_MAX_ATTACHMENT_MB', '10'))
SUPPORT_MAX_DISPUTES_PER_WEEK    = int(os.environ.get('SUPPORT_MAX_DISPUTES_PER_WEEK', '5'))
SUPPORT_AUTO_CLOSE_WAITING_DAYS  = int(os.environ.get('SUPPORT_AUTO_CLOSE_WAITING_DAYS', '7'))
SUPPORT_AUTO_CLOSE_RESOLVED_DAYS = int(os.environ.get('SUPPORT_AUTO_CLOSE_RESOLVED_DAYS', '30'))

# ── SLA defaults (hours) ─────────────────────────────────────
SUPPORT_SLA_URGENT_FR    = int(os.environ.get('SUPPORT_SLA_URGENT_FR', '1'))
SUPPORT_SLA_HIGH_FR      = int(os.environ.get('SUPPORT_SLA_HIGH_FR', '4'))
SUPPORT_SLA_MEDIUM_FR    = int(os.environ.get('SUPPORT_SLA_MEDIUM_FR', '8'))
SUPPORT_SLA_LOW_FR       = int(os.environ.get('SUPPORT_SLA_LOW_FR', '24'))

# ── DRF throttle rates ────────────────────────────────────────
SUPPORT_THROTTLE_RATES = {
    'ticket_create':  os.environ.get('SUPPORT_THROTTLE_TICKET_CREATE', '10/hour'),
    'dispute_submit': os.environ.get('SUPPORT_THROTTLE_DISPUTE_SUBMIT', '5/day'),
    'chat_start':     os.environ.get('SUPPORT_THROTTLE_CHAT_START', '10/hour'),
    'rating_submit':  os.environ.get('SUPPORT_THROTTLE_RATING_SUBMIT', '20/hour'),
    'support_public': os.environ.get('SUPPORT_THROTTLE_PUBLIC', '60/minute'),
    'agent_action':   os.environ.get('SUPPORT_THROTTLE_AGENT', '100/minute'),
}

# ── DRF settings additions ────────────────────────────────────
SUPPORT_REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_RATES': SUPPORT_THROTTLE_RATES,
}

# ── Celery beat schedule ──────────────────────────────────────
from api.support.celery_beat_config import SUPPORT_BEAT_SCHEDULE

# ── Channel layers ────────────────────────────────────────────
SUPPORT_CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG':  {
            'hosts': [os.environ.get('REDIS_URL', 'redis://localhost:6379/0')],
        },
    },
}

# ── Email settings ────────────────────────────────────────────
SUPPORT_EMAIL_HOST     = os.environ.get('SUPPORT_EMAIL_HOST', '')
SUPPORT_EMAIL_PORT     = int(os.environ.get('SUPPORT_EMAIL_PORT', '587'))
SUPPORT_EMAIL_USER     = os.environ.get('SUPPORT_EMAIL_USER', '')
SUPPORT_EMAIL_PASSWORD = os.environ.get('SUPPORT_EMAIL_PASSWORD', '')
SUPPORT_EMAIL_TLS      = os.environ.get('SUPPORT_EMAIL_TLS', 'true').lower() == 'true'

# ── Feature flags defaults ────────────────────────────────────
SUPPORT_CHAT_ENABLED          = os.environ.get('SUPPORT_CHAT_ENABLED', 'true').lower() == 'true'
SUPPORT_AI_AUTO_RESPONSE      = os.environ.get('SUPPORT_AI_AUTO_RESPONSE', 'false').lower() == 'true'
SUPPORT_OFFER_DISPUTES        = os.environ.get('SUPPORT_OFFER_DISPUTES', 'true').lower() == 'true'
SUPPORT_SLA_ENFORCEMENT       = os.environ.get('SUPPORT_SLA_ENFORCEMENT', 'true').lower() == 'true'
SUPPORT_WEBSOCKET_ENABLED     = os.environ.get('SUPPORT_WEBSOCKET_ENABLED', 'true').lower() == 'true'
SUPPORT_AUDIT_LOGGING         = os.environ.get('SUPPORT_AUDIT_LOGGING', 'true').lower() == 'true'