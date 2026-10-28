# api/cms/adapters/analytics.py
"""
Adapters for api.analytics and api.behavior_analytics

  AnalyticsAdapter — track events, page views, conversions
  BehaviorAdapter  — user behavior events, session tracking
"""
import logging
from typing import Optional, Dict, Any

from .base import BaseAdapter

logger = logging.getLogger('api.cms.adapters')


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class AnalyticsAdapter(BaseAdapter):
    """CMS → api.analytics interface."""

    _system_name = 'api.analytics'

    @classmethod
    def _check_available(cls):
        import api.analytics  # noqa

    @classmethod
    def track(cls, event: str, user=None, data: Optional[Dict] = None) -> bool:
        """Track an analytics event."""
        try:
            from api.analytics.services import AnalyticsService
            AnalyticsService.track(event=event, user=user, data=data or {})
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.debug("[CMS→Analytics] track(%s) failed: %s", event, e)
            return False

    @classmethod
    def page_view(cls, user, path: str, content_id: str = '', content_type: str = '') -> bool:
        return cls.track('cms_page_view', user, {
            'path': path, 'content_id': content_id, 'content_type': content_type
        })

    @classmethod
    def banner_impression(cls, user, banner_id: int, placement: str = '') -> bool:
        return cls.track('banner_impression', user, {
            'banner_id': banner_id, 'placement': placement
        })

    @classmethod
    def banner_click(cls, user, banner_id: int) -> bool:
        return cls.track('banner_click', user, {'banner_id': banner_id})

    @classmethod
    def survey_started(cls, user, survey_id: str) -> bool:
        return cls.track('survey_started', user, {'survey_id': survey_id})

    @classmethod
    def survey_completed(cls, user, survey_id: str, time_spent: int = 0) -> bool:
        return cls.track('survey_completed', user, {
            'survey_id': survey_id, 'time_spent_seconds': time_spent
        })

    @classmethod
    def offer_clicked(cls, user, offer_id: str, payout_usd: float = 0) -> bool:
        return cls.track('offer_clicked', user, {
            'offer_id': offer_id, 'payout_usd': payout_usd
        })

    @classmethod
    def offer_converted(cls, user, offer_id: str, campaign_id: str, payout_usd: float = 0) -> bool:
        return cls.track('offer_converted', user, {
            'offer_id': offer_id, 'campaign_id': campaign_id, 'payout_usd': payout_usd
        })

    @classmethod
    def content_published(cls, user, content_type: str, content_id: str) -> bool:
        return cls.track('cms_content_published', user, {
            'content_type': content_type, 'content_id': content_id
        })

    @classmethod
    def form_submission(cls, user, form_id: str) -> bool:
        return cls.track('form_submission', user, {'form_id': form_id})

    @classmethod
    def quiz_attempt(cls, user, quiz_id: str, completed: bool = False) -> bool:
        return cls.track('quiz_attempt', user, {
            'quiz_id': quiz_id, 'completed': completed
        })

    @classmethod
    def ab_test_exposure(cls, user, test_id: str, variant_id: str) -> bool:
        return cls.track('ab_test_exposure', user, {
            'test_id': test_id, 'variant_id': variant_id
        })

    @classmethod
    def ab_test_conversion(cls, user, test_id: str, variant_id: str) -> bool:
        return cls.track('ab_test_conversion', user, {
            'test_id': test_id, 'variant_id': variant_id
        })


# ══════════════════════════════════════════════════════════════════════════════
# BEHAVIOR ANALYTICS ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class BehaviorAdapter(BaseAdapter):
    """CMS → api.behavior_analytics interface."""

    _system_name = 'api.behavior_analytics'

    @classmethod
    def _check_available(cls):
        import api.behavior_analytics  # noqa

    @classmethod
    def record(cls, user, action: str, context: Optional[Dict] = None) -> bool:
        """Record a user behavior event."""
        try:
            from api.behavior_analytics.services import BehaviorService
            BehaviorService.record(user=user, action=action, context=context or {})
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.debug("[CMS→Behavior] record(%s) failed: %s", action, e)
            return False

    @classmethod
    def content_scroll_depth(cls, user, content_id: str, depth_pct: int) -> bool:
        return cls.record(user, 'scroll_depth', {
            'content_id': content_id, 'depth_pct': depth_pct
        })

    @classmethod
    def time_on_page(cls, user, content_id: str, seconds: int) -> bool:
        return cls.record(user, 'time_on_page', {
            'content_id': content_id, 'seconds': seconds
        })

    @classmethod
    def get_user_preferences(cls, user) -> Dict:
        """Fetch learned preferences for personalization."""
        try:
            from api.behavior_analytics.services import BehaviorService
            return BehaviorService.get_preferences(user=user) or {}
        except (ImportError, Exception):
            return {}
