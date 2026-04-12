"""
api/users/profile/achievement_manager.py
Achievement tracking — api.gamification-কে signal দেয়, নিজে store করে না।
"""
import logging
from ..constants import UserEvent

logger = logging.getLogger(__name__)


class AchievementManager:
    """
    users app শুধু achievement check করে এবং
    api.gamification-কে signal দেয়।
    Badge store, display — api.gamification-এর কাজ।
    """

    # Milestone definitions
    MILESTONES = {
        'first_login':        {'event': UserEvent.LOGGED_IN,       'once': True},
        'profile_complete':   {'event': UserEvent.PROFILE_UPDATED, 'once': True},
        'kyc_verified':       {'event': UserEvent.KYC_APPROVED,    'once': True},
        'first_withdrawal':   {'event': UserEvent.WITHDRAWAL_REQ,  'once': True},
        'referral_first':     {'event': UserEvent.REFERRAL_JOINED, 'once': True},
        'tier_bronze':        {'tier': 'BRONZE'},
        'tier_silver':        {'tier': 'SILVER'},
        'tier_gold':          {'tier': 'GOLD'},
        'tier_platinum':      {'tier': 'PLATINUM'},
        'tier_diamond':       {'tier': 'DIAMOND'},
        'earned_10':          {'total_earned_gte': 10},
        'earned_100':         {'total_earned_gte': 100},
        'earned_1000':        {'total_earned_gte': 1000},
    }

    def check_and_award(self, user, event: str, context: dict = None) -> list[str]:
        """
        Event হলে achievement check করো।
        api.gamification-কে signal দাও।
        Returns: list of newly earned achievement keys
        """
        earned = []

        for key, conditions in self.MILESTONES.items():
            if self._should_award(user, key, event, conditions, context):
                self._notify_gamification(user, key)
                earned.append(key)

        return earned

    def check_tier_achievement(self, user, new_tier: str) -> None:
        """Tier upgrade হলে call করো"""
        key = f'tier_{new_tier.lower()}'
        if key in self.MILESTONES:
            self._notify_gamification(user, key)

    def check_earning_milestone(self, user, total_earned: float) -> None:
        """Earning milestone চেক করো"""
        milestones = [10, 100, 1000]
        for amount in milestones:
            if total_earned >= amount:
                key = f'earned_{amount}'
                self._notify_gamification(user, key)

    # ─────────────────────────────────────
    # PRIVATE
    # ─────────────────────────────────────
    def _should_award(self, user, key, event, conditions, context) -> bool:
        # Event match
        if 'event' in conditions and conditions['event'] != event:
            return False

        # Already earned check (api.gamification-এ)
        if conditions.get('once') and self._already_earned(user, key):
            return False

        return True

    def _already_earned(self, user, achievement_key: str) -> bool:
        """api.gamification-এ check করো"""
        try:
            from django.apps import apps
            Achievement = apps.get_model('gamification', 'UserAchievement')
            return Achievement.objects.filter(
                user=user, key=achievement_key
            ).exists()
        except Exception:
            return False

    def _notify_gamification(self, user, achievement_key: str) -> None:
        """
        api.gamification-কে signal দাও।
        gamification নিজে store করবে।
        """
        try:
            from django.dispatch import Signal
            logger.info(f'Achievement signal: {achievement_key} for user {user.id}')
            # api.gamification.signals.achievement_earned.send(...)
        except Exception as e:
            logger.warning(f'Achievement signal failed: {e}')


# Singleton
achievement_manager = AchievementManager()
