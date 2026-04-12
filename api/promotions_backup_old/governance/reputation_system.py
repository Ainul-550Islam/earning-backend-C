# api/promotions/governance/reputation_system.py
# Reputation System — Level progression, badges, rewards
import logging
from django.core.cache import cache
logger = logging.getLogger('governance.reputation')

LEVELS = [
    {'level': 1, 'name': 'Newcomer',    'min_score': 0,   'max_tasks': 10,   'max_reward': 0.10},
    {'level': 2, 'name': 'Beginner',    'min_score': 20,  'max_tasks': 25,   'max_reward': 0.25},
    {'level': 3, 'name': 'Member',      'min_score': 40,  'max_tasks': 50,   'max_reward': 0.50},
    {'level': 4, 'name': 'Trusted',     'min_score': 60,  'max_tasks': 100,  'max_reward': 1.00},
    {'level': 5, 'name': 'Senior',      'min_score': 75,  'max_tasks': 200,  'max_reward': 2.00},
    {'level': 6, 'name': 'Expert',      'min_score': 85,  'max_tasks': 500,  'max_reward': 5.00},
    {'level': 7, 'name': 'Elite',       'min_score': 95,  'max_tasks': 1000, 'max_reward': 10.00},
]

BADGES = {
    'first_task':         {'name': 'First Step',    'condition': 'complete_1_task'},
    'century':            {'name': 'Century',        'condition': 'complete_100_tasks'},
    'perfect_week':       {'name': 'Perfect Week',   'condition': '7_day_streak_approved'},
    'fraud_free_90days':  {'name': 'Clean Record',   'condition': 'no_fraud_90_days'},
    'top_earner':         {'name': 'Top Earner',     'condition': 'top_10_percent_earnings'},
    'verified':           {'name': 'Verified',       'condition': 'kyc_verified'},
}

class ReputationSystem:
    """User level ও badge management।"""

    def get_level(self, trust_score: float) -> dict:
        level = LEVELS[0]
        for l in LEVELS:
            if trust_score >= l['min_score']:
                level = l
        return level

    def check_level_up(self, user_id: int, trust_score: float) -> dict:
        """Level up হয়েছে কিনা check করে।"""
        new_level = self.get_level(trust_score)
        cache_key = f'gov:level:{user_id}'
        old_level = cache.get(cache_key) or 1
        leveled_up = new_level['level'] > old_level
        if leveled_up:
            cache.set(cache_key, new_level['level'], timeout=86400*30)
            self._save_level(user_id, new_level['level'])
        return {'level': new_level, 'leveled_up': leveled_up, 'previous_level': old_level}

    def award_badge(self, user_id: int, badge_id: str) -> bool:
        """Badge award করে।"""
        if badge_id not in BADGES:
            return False
        try:
            from api.promotions.models import UserBadge
            _, created = UserBadge.objects.get_or_create(user_id=user_id, badge_id=badge_id)
            if created:
                logger.info(f'Badge awarded: user={user_id} badge={badge_id}')
            return created
        except Exception:
            return False

    def check_badges(self, user_id: int) -> list:
        """User এর earned badges।"""
        try:
            from api.promotions.models import UserBadge
            return list(UserBadge.objects.filter(user_id=user_id).values_list('badge_id', flat=True))
        except Exception:
            return []

    def _save_level(self, user_id: int, level: int):
        try:
            from api.promotions.models import UserReputation
            UserReputation.objects.filter(user_id=user_id).update(level=level)
        except Exception:
            pass
