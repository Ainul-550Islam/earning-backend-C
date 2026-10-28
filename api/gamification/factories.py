"""
Gamification Factories — Test data generation for gamification models.

This module provides factory classes for generating test data for all
gamification models with realistic and varied data for comprehensive testing.
"""

from __future__ import annotations

import factory
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.utils import timezone

from api.gamification.models import (
    Badge, UserBadge, DailyChallenge, UserDailyChallenge,
    Streak, StreakReward, LevelConfig, ContestCycle, LeaderboardSnapshot,
    ContestReward, UserAchievement, WebhookEndpoint, WebhookEvent, WebhookDelivery
)
from api.gamification.choices import (
    BadgeRarity, BadgeCriteriaType, ChallengeAction, ChallengeStatus,
    StreakStatus, ContestCycleStatus, LeaderboardScope, SnapshotStatus,
    RewardType, AchievementType, WebhookStatus, WebhookEventType
)

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for User model."""
    
    class Meta:
        model = User
        skip_postgeneration_save = True
    
    username = factory.Sequence(lambda n: f"user_{n:04d}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    is_staff = False
    is_premium = factory.Faker('boolean', chance_of_getting_true=20)  # 20% chance of being premium
    
    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        """Set password for user."""
        password = extracted or 'testpass123'
        self.set_password(password)
        self.save()
    
    @factory.post_generation
    def achievements(self, create, extracted, **kwargs):
        """Create achievements for user."""
        if extracted:
            for achievement_data in extracted:
                UserAchievementFactory(user=self, **achievement_data)


class BadgeFactory(factory.django.DjangoModelFactory):
    """Factory for Badge model."""
    
    class Meta:
        model = Badge
    
    name = factory.Faker('word')
    description = factory.Faker('text', max_nb_chars=200)
    icon = factory.Faker('random_element', elements=['🎯', '⭐', '🏆', '🔥', '💎', '🎨', '🚀', '🌟'])
    rarity = factory.Faker('random_element', elements=[choice.value for choice in BadgeRarity])
    criteria_type = factory.Faker('random_element', elements=[choice.value for choice in BadgeCriteriaType])
    criteria_value = factory.Faker('random_int', min=1, max=1000)
    points_bonus = factory.Faker('random_int', min=10, max=500)
    is_active = True
    sort_order = factory.Sequence(lambda n: n)
    metadata = factory.LazyAttribute(lambda obj: {
        'difficulty': factory.Faker('random_element', elements=['easy', 'medium', 'hard']),
        'category': factory.Faker('word'),
        'created_by': 'system'
    })


class UserBadgeFactory(factory.django.DjangoModelFactory):
    """Factory for UserBadge model."""
    
    class Meta:
        model = UserBadge
    
    user = factory.SubFactory(UserFactory)
    badge = factory.SubFactory(BadgeFactory)
    is_pinned = factory.Faker('boolean', chance_of_getting_true=10)  # 10% chance of being pinned
    metadata = factory.LazyAttribute(lambda obj: {
        'awarded_via': factory.Faker('random_element', elements=['automatic', 'manual', 'event']),
        'source': factory.Faker('word'),
        'context': factory.Faker('sentence')
    })


class DailyChallengeFactory(factory.django.DjangoModelFactory):
    """Factory for DailyChallenge model."""
    
    class Meta:
        model = DailyChallenge
    
    title = factory.Faker('sentence', nb_words=4)
    description = factory.Faker('text', max_nb_chars=300)
    target_action = factory.Faker('random_element', elements=[choice.value for choice in ChallengeAction])
    target_count = factory.Faker('random_int', min=1, max=10)
    bonus_points = factory.Faker('random_int', min=5, max=50)
    date = factory.LazyAttribute(lambda obj: timezone.now().date())
    is_active = True
    metadata = factory.LazyAttribute(lambda obj: {
        'difficulty': factory.Faker('random_element', elements=['easy', 'medium', 'hard']),
        'category': factory.Faker('word'),
        'estimated_time': factory.Faker('random_int', min=5, max=60)
    })


class UserDailyChallengeFactory(factory.django.DjangoModelFactory):
    """Factory for UserDailyChallenge model."""
    
    class Meta:
        model = UserDailyChallenge
    
    user = factory.SubFactory(UserFactory)
    challenge = factory.SubFactory(DailyChallengeFactory)
    progress = factory.Faker('random_int', min=0, max=10)
    is_completed = factory.Faker('boolean', chance_of_getting_true=30)  # 30% chance of being completed
    completed_at = factory.LazyAttribute(lambda obj: timezone.now() - timedelta(hours=1) if obj.is_completed else None)
    metadata = factory.LazyAttribute(lambda obj: {
        'last_action': factory.Faker('word'),
        'completion_time': factory.Faker('random_int', min=1, max=120) if obj.is_completed else None,
        'attempts': factory.Faker('random_int', min=1, max=5)
    })
    
    @classmethod
    def create_completed(cls, **kwargs):
        """Create a completed challenge."""
        challenge = cls(**kwargs)
        challenge.is_completed = True
        challenge.completed_at = timezone.now() - timedelta(hours=1)
        challenge.progress = challenge.challenge.target_count
        challenge.save()
        return challenge


class StreakFactory(factory.django.DjangoModelFactory):
    """Factory for Streak model."""
    
    class Meta:
        model = Streak
    
    user = factory.SubFactory(UserFactory)
    current_days = factory.Faker('random_int', min=0, max=365)
    longest_days = factory.LazyAttribute(lambda obj: max(obj.current_days, factory.Faker('random_int', min=obj.current_days, max=365)))
    last_activity_date = factory.LazyAttribute(lambda obj: timezone.now().date() - timedelta(days=obj.current_days))
    is_active = factory.Faker('boolean', chance_of_getting_true=80)  # 80% chance of being active
    metadata = factory.LazyAttribute(lambda obj: {
        'last_action': factory.Faker('word'),
        'activity_source': factory.Faker('random_element', elements=['web', 'mobile', 'api']),
        'timezone': factory.Faker('timezone')
    })


class StreakRewardFactory(factory.django.DjangoModelFactory):
    """Factory for StreakReward model."""
    
    class Meta:
        model = StreakReward
    
    streak_days = factory.Faker('random_int', min=1, max=100)
    points_bonus = factory.Faker('random_int', min=10, max=500)
    title = factory.Faker('sentence', nb_words=3)
    description = factory.Faker('text', max_nb_chars=200)
    is_active = True
    badge = factory.SubFactory(BadgeFactory)
    metadata = factory.LazyAttribute(lambda obj: {
        'rarity': factory.Faker('random_element', elements=['common', 'rare', 'epic']),
        'category': factory.Faker('word')
    })


class LevelConfigFactory(factory.django.DjangoModelFactory):
    """Factory for LevelConfig model."""
    
    class Meta:
        model = LevelConfig
    
    level_number = factory.Sequence(lambda n: n + 1)
    points_required = factory.LazyAttribute(lambda obj: (obj.level_number - 1) * 100)
    title = factory.Faker('word')
    description = factory.Faker('text', max_nb_chars=200)
    points_multiplier = factory.Faker('random_float', min=1.0, max=3.0, digits=2)
    is_active = True
    badge = factory.SubFactory(BadgeFactory)
    perks = factory.LazyAttribute(lambda obj: {
        'bonus_access': factory.Faker('boolean'),
        'special_features': factory.Faker('random_elements', elements=['feature1', 'feature2', 'feature3'], unique=True, length=factory.Faker('random_int', min=1, max=3)),
        'discount_percentage': factory.Faker('random_int', min=0, max=20)
    })
    metadata = factory.LazyAttribute(lambda obj: {
        'difficulty': factory.Faker('random_element', elements=['beginner', 'intermediate', 'advanced']),
        'color_theme': factory.Faker('color_name')
    })


class ContestCycleFactory(factory.django.DjangoModelFactory):
    """Factory for ContestCycle model."""
    
    class Meta:
        model = ContestCycle
    
    name = factory.Faker('sentence', nb_words=4)
    description = factory.Faker('text', max_nb_chars=500)
    status = factory.Faker('random_element', elements=[choice.value for choice in ContestCycleStatus])
    start_time = factory.LazyAttribute(lambda obj: timezone.now() - timedelta(days=7))
    end_time = factory.LazyAttribute(lambda obj: obj.start_time + timedelta(days=14))
    points_multiplier = factory.Faker('random_float', min=1.0, max=2.0, digits=2)
    metadata = factory.LazyAttribute(lambda obj: {
        'category': factory.Faker('word'),
        'prize_pool': factory.Faker('random_int', min=1000, max=10000),
        'sponsored_by': factory.Faker('company')
    })


class LeaderboardSnapshotFactory(factory.django.DjangoModelFactory):
    """Factory for LeaderboardSnapshot model."""
    
    class Meta:
        model = LeaderboardSnapshot
    
    contest_cycle = factory.SubFactory(ContestCycleFactory)
    scope = factory.Faker('random_element', elements=[choice.value for choice in LeaderboardScope])
    status = factory.Faker('random_element', elements=[choice.value for choice in SnapshotStatus])
    snapshot_data = factory.LazyAttribute(lambda obj: [
        {
            'user_id': str(factory.Faker('uuid4')),
            'username': factory.Faker('user_name'),
            'total_points': factory.Faker('random_int', min=0, max=10000),
            'rank': factory.Sequence(lambda n: n + 1),
            'achievement_count': factory.Faker('random_int', min=0, max=50),
            'last_updated': factory.Faker('date_time_this_year').isoformat()
        }
        for _ in range(factory.Faker('random_int', min=10, max=100))
    ])
    created_at = factory.LazyAttribute(lambda obj: timezone.now() - timedelta(hours=1))
    finalized_at = factory.LazyAttribute(lambda obj: timezone.now() if obj.status == SnapshotStatus.FINALIZED else None)
    metadata = factory.LazyAttribute(lambda obj: {
        'total_users': len(obj.snapshot_data),
        'calculation_time': factory.Faker('random_float', min=0.1, max=5.0, digits=2),
        'algorithm_version': '1.0'
    })


class ContestRewardFactory(factory.django.DjangoModelFactory):
    """Factory for ContestReward model."""
    
    class Meta:
        model = ContestReward
    
    contest_cycle = factory.SubFactory(ContestCycleFactory)
    title = factory.Faker('sentence', nb_words=3)
    description = factory.Faker('text', max_nb_chars=200)
    rank_from = factory.Faker('random_int', min=1, max=10)
    rank_to = factory.LazyAttribute(lambda obj: obj.rank_from + factory.Faker('random_int', min=0, max=20))
    reward_type = factory.Faker('random_element', elements=[choice.value for choice in RewardType])
    points_bonus = factory.Faker('random_int', min=10, max=1000)
    total_budget = factory.Faker('random_int', min=100, max=10000)
    issued_count = factory.Faker('random_int', min=0, max=100)
    is_active = True
    badge = factory.SubFactory(BadgeFactory)
    metadata = factory.LazyAttribute(lambda obj: {
        'rarity': 'common',
        'category': 'badge',
        'estimated_value': 100,
    })


class UserAchievementFactory(factory.django.DjangoModelFactory):
    """Factory for UserAchievement model."""
    
    class Meta:
        model = UserAchievement
    
    user = factory.SubFactory(UserFactory)
    contest_cycle = factory.SubFactory(ContestCycleFactory)
    achievement_type = factory.Faker('random_element', elements=[choice.value for choice in AchievementType])
    points_awarded = factory.Faker('random_int', min=10, max=500)
    rank = factory.Faker('random_int', min=1, max=1000)
    is_awarded = factory.Faker('boolean', chance_of_getting_true=80)  # 80% chance of being awarded
    awarded_at = factory.LazyAttribute(lambda obj: timezone.now() - timedelta(hours=1) if obj.is_awarded else None)
    metadata = factory.LazyAttribute(lambda obj: {
        'source': factory.Faker('word'),
        'context': factory.Faker('sentence'),
        'verification_required': factory.Faker('boolean')
    })


class WebhookEndpointFactory(factory.django.DjangoModelFactory):
    """Factory for WebhookEndpoint model."""
    
    class Meta:
        model = WebhookEndpoint
    
    url = factory.Faker('url')
    secret = factory.Faker('password', length=32)
    description = factory.Faker('text', max_nb_chars=200)
    event_types = factory.LazyAttribute(lambda obj: factory.Faker('random_elements', elements=[choice.value for choice in WebhookEventType], unique=True, length=factory.Faker('random_int', min=1, max=3)))
    is_active = factory.Faker('boolean', chance_of_getting_true=80)  # 80% chance of being active
    headers = factory.LazyAttribute(lambda obj: {
        'Authorization': f'Bearer {factory.Faker("password", length=20)}',
        'User-Agent': 'Gamification-Webhooks/1.0'
    })
    metadata = factory.LazyAttribute(lambda obj: {
        'created_by': factory.Faker('user_name'),
        'purpose': factory.Faker('random_element', elements=['notifications', 'analytics', 'integration']),
        'retry_count': factory.Faker('random_int', min=0, max=5)
    })


class WebhookEventFactory(factory.django.DjangoModelFactory):
    """Factory for WebhookEvent model."""
    
    class Meta:
        model = WebhookEvent
    
    event_type = factory.Faker('random_element', elements=[choice.value for choice in WebhookEventType])
    data = factory.LazyAttribute(lambda obj: {
        'user_id': str(factory.Faker('uuid4')),
        'badge_id': str(factory.Faker('uuid4')),
        'points_awarded': factory.Faker('random_int', min=10, max=500),
        'timestamp': factory.Faker('date_time_this_year').isoformat()
    })
    user_id = factory.Faker('uuid4')
    metadata = factory.LazyAttribute(lambda obj: {
        'source': factory.Faker('word'),
        'context': factory.Faker('sentence'),
        'priority': factory.Faker('random_element', elements=['low', 'medium', 'high'])
    })


class WebhookDeliveryFactory(factory.django.DjangoModelFactory):
    """Factory for WebhookDelivery model."""
    
    class Meta:
        model = WebhookDelivery
    
    webhook = factory.SubFactory(WebhookEndpointFactory)
    event = factory.SubFactory(WebhookEventFactory)
    status = factory.Faker('random_element', elements=[choice.value for choice in WebhookStatus])
    attempts = factory.Faker('random_int', min=0, max=5)
    delivered_at = factory.LazyAttribute(lambda obj: timezone.now() - timedelta(minutes=15) if obj.status == WebhookStatus.SUCCESS else None)
    response_status = factory.LazyAttribute(lambda obj: factory.Faker('random_int', min=200, max=500) if obj.status in [WebhookStatus.SUCCESS, WebhookStatus.FAILED] else None)
    response_body = factory.LazyAttribute(lambda obj: factory.Faker('text', max_nb_chars=500) if obj.status in [WebhookStatus.SUCCESS, WebhookStatus.FAILED] else None)
    scheduled_at = factory.LazyAttribute(lambda obj: timezone.now() + timedelta(minutes=5) if obj.status == WebhookStatus.RETRY else timezone.now())
    metadata = factory.LazyAttribute(lambda obj: {
        'delivery_time': factory.Faker('random_float', min=0.1, max=2.0, digits=2),
        'retry_reason': factory.Faker('sentence') if obj.status == WebhookStatus.RETRY else None,
        'error_code': factory.Faker('random_int', min=400, max=599) if obj.status == WebhookStatus.FAILED else None
    })


# Specialized factory methods for creating test scenarios
class GamificationTestDataFactory:
    """Factory for creating comprehensive test data scenarios."""
    
    @staticmethod
    def create_user_with_progress(user_data: Optional[Dict[str, Any]] = None) -> User:
        """Create a user with comprehensive gamification progress."""
        user = UserFactory(**(user_data or {}))
        
        # Create badges
        badges = BadgeFactory.create_batch(5)
        for badge in badges:
            UserBadgeFactory(user=user, badge=badge)
        
        # Create streak
        StreakFactory(user=user, current_days=7, longest_days=15)
        
        # Create achievements
        UserAchievementFactory.create_batch(
            3,
            user=user,
            points_awarded=factory.Faker('random_int', min=50, max=200)
        )
        
        return user
    
    @staticmethod
    def create_contest_with_participants(participant_count: int = 10) -> ContestCycle:
        """Create a contest with participants and leaderboard."""
        contest = ContestCycleFactory(
            status=ContestCycleStatus.COMPLETED,
            start_time=timezone.now() - timedelta(days=14),
            end_time=timezone.now() - timedelta(days=1)
        )
        
        # Create participants with achievements
        users = UserFactory.create_batch(participant_count)
        for i, user in enumerate(users):
            UserAchievementFactory(
                user=user,
                contest_cycle=contest,
                points_awarded=1000 - (i * 50),  # Decreasing points
                rank=i + 1,
                is_awarded=True
            )
        
        # Create leaderboard snapshot
        LeaderboardSnapshotFactory(
            contest_cycle=contest,
            status=SnapshotStatus.FINALIZED,
            snapshot_data=[
                {
                    'user_id': str(user.id),
                    'username': user.username,
                    'total_points': 1000 - (i * 50),
                    'rank': i + 1,
                    'achievement_count': factory.Faker('random_int', min=1, max=10)
                }
                for i, user in enumerate(users)
            ]
        )
        
        # Create rewards
        ContestRewardFactory.create_batch(
            3,
            contest_cycle=contest,
            rank_from=1,
            rank_to=3
        )
        
        return contest
    
    @staticmethod
    def create_daily_challenges_scenario(days: int = 7) -> List[DailyChallenge]:
        """Create a week of daily challenges."""
        challenges = []
        
        for i in range(days):
            challenge_date = timezone.now().date() - timedelta(days=i)
            challenge = DailyChallengeFactory(
                date=challenge_date,
                is_active=(i == 0)  # Only today's challenge is active
            )
            challenges.append(challenge)
        
        return challenges
    
    @staticmethod
    def create_user_challenges_progress(user: User, days: int = 7) -> List[UserDailyChallenge]:
        """Create user challenge progress for multiple days."""
        user_challenges = []
        
        for i in range(days):
            challenge_date = timezone.now().date() - timedelta(days=i)
            challenge = DailyChallengeFactory(date=challenge_date)
            
            # Create user challenge with varying progress
            progress = min(challenge.target_count, max(0, challenge.target_count - i))
            user_challenge = UserDailyChallengeFactory(
                user=user,
                challenge=challenge,
                progress=progress,
                is_completed=(progress >= challenge.target_count)
            )
            user_challenges.append(user_challenge)
        
        return user_challenges
    
    @staticmethod
    def create_level_progression_scenario(max_level: int = 10) -> List[LevelConfig]:
        """Create a complete level progression scenario."""
        levels = []
        
        for i in range(1, max_level + 1):
            level = LevelConfigFactory(
                level_number=i,
                points_required=(i - 1) * 100,
                points_multiplier=1.0 + (i * 0.1)
            )
            levels.append(level)
        
        return levels
    
    @staticmethod
    def create_streak_rewards_scenario(max_days: int = 30) -> List[StreakReward]:
        """Create streak rewards for various milestones."""
        rewards = []
        
        # Common milestones
        milestone_days = [3, 7, 14, 21, 30]
        
        for days in milestone_days:
            if days <= max_days:
                reward = StreakRewardFactory(
                    streak_days=days,
                    points_bonus=days * 10
                )
                rewards.append(reward)
        
        return rewards
    
    @staticmethod
    def create_webhook_scenario(event_count: int = 5) -> tuple[WebhookEndpoint, List[WebhookDelivery]]:
        """Create webhook endpoint with delivery history."""
        webhook = WebhookEndpointFactory()
        deliveries = []
        
        for i in range(event_count):
            event = WebhookEventFactory()
            delivery = WebhookDeliveryFactory(
                webhook=webhook,
                event=event,
                status=factory.Faker('random_element', elements=[choice.value for choice in WebhookStatus])
            )
            deliveries.append(delivery)
        
        return webhook, deliveries


# Factory for creating bulk test data
class BulkGamificationFactory:
    """Factory for creating large amounts of test data."""
    
    @staticmethod
    def create_users_with_badges(user_count: int, badges_per_user: int = 3) -> List[User]:
        """Create multiple users with badges."""
        users = UserFactory.create_batch(user_count)
        badges = BadgeFactory.create_batch(badges_per_user * user_count)
        
        badge_index = 0
        for user in users:
            for _ in range(badges_per_user):
                UserBadgeFactory(user=user, badge=badges[badge_index])
                badge_index += 1
        
        return users
    
    @staticmethod
    def create_contest_history(months: int = 6) -> List[ContestCycle]:
        """Create historical contest data."""
        contests = []
        
        for i in range(months):
            start_time = timezone.now() - timedelta(days=(i + 1) * 30)
            end_time = start_time + timedelta(days=14)
            
            contest = ContestCycleFactory(
                start_time=start_time,
                end_time=end_time,
                status=ContestCycleStatus.COMPLETED
            )
            contests.append(contest)
        
        return contests
    
    @staticmethod
    def create_leaderboard_history(contest: ContestClass, snapshot_count: int = 5) -> List[LeaderboardSnapshot]:
        """Create historical leaderboard snapshots."""
        snapshots = []
        
        for i in range(snapshot_count):
            created_at = contest.start_time + timedelta(
                hours=i * (contest.end_time - contest.start_time).total_seconds() / 3600 / snapshot_count
            )
            
            snapshot = LeaderboardSnapshotFactory(
                contest_cycle=contest,
                created_at=created_at,
                status=SnapshotStatus.FINALIZED if i == snapshot_count - 1 else SnapshotStatus.PENDING
            )
            snapshots.append(snapshot)
        
        return snapshots
