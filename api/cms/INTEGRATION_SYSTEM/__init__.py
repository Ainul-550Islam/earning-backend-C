# cms/INTEGRATION_SYSTEM/__init__.py
"""
CMS INTEGRATION_SYSTEM package.

AUDIT RESULT (GAP-06): 7 of 8 files in this package were NOT imported here.
Confirmed floating modules:
  ✗ event_bus            — EventBus class silently dead (no fire/subscribe)
  ✗ health_check         — HealthChecker.get_cached_health() always 404
  ✗ integ_constants      — CMSEvents strings hardcoded everywhere
  ✗ integ_registry       — CMSRegistry was a _Stub() — all .resolve() → None
  ✗ integ_signals        — 22 signals defined but connect_integration_receivers()
                           never called → postback/reward/survey/withdrawal
                           event bridges never fired
  ✗ performance_monitor  — PerformanceMonitor was a stub — no latency recorded
  ✗ webhooks_integration — CPALeadWebhookView v2, GenericWebhookView,
                           WalletCallbackView all unreachable

Business impact of all 7 being floating:
  • EventBus.fire('cms_reward_earned') → no-op → referral bonuses silently skipped
  • HealthChecker → stub → /health/ always returned {'status': 'stub'}
  • CMSRegistry.resolve('withdrawal_service') → None → AttributeError in interactors
  • Signal receivers not connected → postback approval never triggered coin award
  • PerformanceMonitor → stub → /adapters/rate-limiter-stats/ always returned {}
  • WebhookView v2 → 404 → CPAlead postbacks routed to legacy endpoint only

v11c: ALL 7 modules now properly imported and connected.
"""
import logging

logger = logging.getLogger('cms.integration')

# ── 1. Constants — no deps, import first ─────────────────────────────
from .integ_constants import CMSEvents

# ── 2. Registry — lazy import, service locator ───────────────────────
from .integ_registry import CMSRegistry

# ── 3. Event Bus ──────────────────────────────────────────────────────
from .event_bus import EventBus

# ── 4. Performance Monitor ────────────────────────────────────────────
from .performance_monitor import PerformanceMonitor

# ── 5. Health Checker ─────────────────────────────────────────────────
from .health_check import HealthChecker

# ── 6. Signals — import module so Signal objects exist in memory ──────
from . import integ_signals
from .integ_signals import (
    cpalead_postback_approved,
    cpalead_postback_rejected,
    offer_clicked,
    content_unlocked,
    cms_reward_earned,
    cms_reward_approved,
    cms_reward_paid,
    cms_survey_started,
    cms_survey_completed,
    cms_survey_response,
    cms_withdrawal_requested,
    cms_withdrawal_approved,
    cms_withdrawal_rejected,
    cms_user_registered,
    cms_user_level_up,
    cms_user_segment_changed,
    cms_content_unlocked,
    cms_page_viewed,
    cms_blog_post_read,
    cms_quiz_completed,
    cms_referral_bonus,
    cms_streak_milestone,
    cms_health_alert,
    cms_error_occurred,
    connect_integration_receivers,
)

# ── 7. Webhooks ───────────────────────────────────────────────────────
from .webhooks_integration import (
    CPALeadWebhookView,
    GenericWebhookView,
    WalletCallbackView,
)

__all__ = [
    'CMSEvents',
    'CMSRegistry',
    'EventBus',
    'PerformanceMonitor',
    'HealthChecker',
    'integ_signals',
    'cpalead_postback_approved', 'cpalead_postback_rejected',
    'offer_clicked', 'content_unlocked',
    'cms_reward_earned', 'cms_reward_approved', 'cms_reward_paid',
    'cms_survey_started', 'cms_survey_completed', 'cms_survey_response',
    'cms_withdrawal_requested', 'cms_withdrawal_approved', 'cms_withdrawal_rejected',
    'cms_user_registered', 'cms_user_level_up', 'cms_user_segment_changed',
    'cms_content_unlocked', 'cms_page_viewed', 'cms_blog_post_read',
    'cms_quiz_completed', 'cms_referral_bonus', 'cms_streak_milestone',
    'cms_health_alert', 'cms_error_occurred',
    'connect_integration_receivers',
    'CPALeadWebhookView', 'GenericWebhookView', 'WalletCallbackView',
]
