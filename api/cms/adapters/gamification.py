# api/cms/adapters/gamification.py
"""
Adapters for api.gamification, api.djoyalty, api.engagement, api.referral

  GamificationAdapter — XP, badges, levels
  LoyaltyAdapter      — loyalty points (djoyalty)
  EngagementAdapter   — engagement events, streaks
  ReferralAdapter     — referral tracking, bonus awards
"""
import logging
from decimal import Decimal
from typing import Optional, Dict, Any, List

from .base import BaseAdapter

logger = logging.getLogger('api.cms.adapters')


class GamificationAdapter(BaseAdapter):
    """CMS → api.gamification interface."""

    _system_name = 'api.gamification'

    @classmethod
    def _check_available(cls):
        import api.gamification  # noqa

    @classmethod
    def award_xp(cls, user, amount: int, source: str = 'cms', ref_id: str = '') -> bool:
        """Award XP points to a user."""
        try:
            from api.gamification.services import GamificationService
            GamificationService.award_xp(user=user, amount=amount, source=source, ref_id=ref_id)
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.warning("[CMS→Gamification] award_xp failed: %s", e)
            return False

    @classmethod
    def award_badge(cls, user, badge_slug: str) -> bool:
        """Award a badge to a user."""
        try:
            from api.gamification.services import GamificationService
            GamificationService.award_badge(user=user, badge_slug=badge_slug)
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.warning("[CMS→Gamification] award_badge(%s) failed: %s", badge_slug, e)
            return False

    @classmethod
    def get_user_level(cls, user) -> Dict:
        """Return {'level': int, 'xp': int, 'next_level_xp': int}."""
        try:
            from api.gamification.services import GamificationService
            return GamificationService.get_level(user=user) or {'level': 1, 'xp': 0}
        except (ImportError, Exception):
            return {'level': 1, 'xp': 0, 'next_level_xp': 100}

    # CMS-specific award triggers
    @classmethod
    def on_survey_completed(cls, user, survey_id: str) -> bool:
        cls.award_xp(user, 50, source='survey_completed', ref_id=survey_id)
        cls.award_badge(user, 'survey_completer')
        return True

    @classmethod
    def on_content_published(cls, user) -> bool:
        cls.award_xp(user, 20, source='content_published')
        return True

    @classmethod
    def on_offer_converted(cls, user, offer_id: str) -> bool:
        cls.award_xp(user, 100, source='offer_converted', ref_id=offer_id)
        return True

    @classmethod
    def on_streak_milestone(cls, user, streak_days: int) -> bool:
        xp = streak_days * 10
        cls.award_xp(user, xp, source=f'streak_{streak_days}')
        if streak_days >= 7:
            cls.award_badge(user, f'streak_{streak_days}d')
        return True


class LoyaltyAdapter(BaseAdapter):
    """CMS → api.djoyalty (loyalty points) interface."""

    _system_name = 'api.djoyalty'

    @classmethod
    def _check_available(cls):
        import api.djoyalty  # noqa

    @classmethod
    def credit_points(cls, user, points: int, reason: str = '', ref_id: str = '') -> bool:
        """Credit loyalty points to a user."""
        try:
            from api.djoyalty.services import LoyaltyService
            LoyaltyService.credit(user=user, points=points, reason=reason, ref_id=ref_id)
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.warning("[CMS→Loyalty] credit_points failed: %s", e)
            return False

    @classmethod
    def get_points(cls, user) -> int:
        """Return the user's current loyalty point balance."""
        try:
            from api.djoyalty.models import LoyaltyBalance
            bal = LoyaltyBalance.objects.filter(user=user).first()
            return getattr(bal, 'balance', 0) if bal else 0
        except (ImportError, Exception):
            return 0

    @classmethod
    def on_offer_converted(cls, user, payout_usd: float) -> bool:
        points = int(payout_usd * 100)  # 100 pts per $1 — platform-configurable
        return cls.credit_points(user, points, reason='offer_converted')

    @classmethod
    def on_survey_completed(cls, user) -> bool:
        return cls.credit_points(user, 25, reason='survey_completed')


class EngagementAdapter(BaseAdapter):
    """CMS → api.engagement interface."""

    _system_name = 'api.engagement'

    @classmethod
    def _check_available(cls):
        import api.engagement  # noqa

    @classmethod
    def record_action(cls, user, action: str, data: Optional[Dict] = None) -> bool:
        try:
            from api.engagement.services import EngagementService
            EngagementService.record(user=user, action=action, data=data or {})
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.debug("[CMS→Engagement] record_action(%s) failed: %s", action, e)
            return False

    @classmethod
    def daily_login(cls, user) -> bool:
        return cls.record_action(user, 'daily_login')

    @classmethod
    def content_viewed(cls, user, content_type: str, content_id: str) -> bool:
        return cls.record_action(user, 'content_viewed', {
            'content_type': content_type, 'content_id': content_id
        })

    @classmethod
    def offer_viewed(cls, user, offer_id: str) -> bool:
        return cls.record_action(user, 'offer_viewed', {'offer_id': offer_id})

    @classmethod
    def get_engagement_score(cls, user) -> float:
        try:
            from api.engagement.services import EngagementService
            return EngagementService.get_score(user=user) or 0.0
        except (ImportError, Exception):
            return 0.0


class ReferralAdapter(BaseAdapter):
    """CMS → api.referral interface."""

    _system_name = 'api.referral'

    @classmethod
    def _check_available(cls):
        import api.referral  # noqa

    @classmethod
    def credit_referrer(
        cls,
        referred_user,
        event: str,
        amount_usd: float = 0,
        ref_id: str = '',
    ) -> bool:
        """
        Credit the referrer of `referred_user` for completing `event`.
        CMS calls this; api.referral figures out who the referrer is.
        """
        try:
            from api.referral.services import ReferralService
            ReferralService.credit_referrer(
                referred=referred_user, event=event, amount_usd=amount_usd, ref_id=ref_id
            )
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.warning("[CMS→Referral] credit_referrer failed: %s", e)
            return False

    @classmethod
    def on_offer_converted(cls, user, offer_id: str, payout_usd: float) -> bool:
        return cls.credit_referrer(user, 'offer_converted', payout_usd, offer_id)

    @classmethod
    def on_survey_completed(cls, user, survey_id: str) -> bool:
        return cls.credit_referrer(user, 'survey_completed', ref_id=survey_id)

    @classmethod
    def get_referral_code(cls, user) -> str:
        """Fetch user's referral code from api.referral."""
        try:
            from api.referral.models import ReferralCode
            code = ReferralCode.objects.filter(user=user, is_active=True).first()
            return code.code if code else ''
        except (ImportError, Exception):
            return ''
