"""
Gamification Test Factories — factory_boy factories for all gamification models.
"""

from __future__ import annotations

import factory
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from ..choices import (
    ContestCycleStatus,
    RewardType,
    AchievementType,
    SnapshotStatus,
    LeaderboardScope,
)
from ..models import ContestCycle, LeaderboardSnapshot, ContestReward, UserAchievement

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user_{n:04d}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "test-password-!@#")
        obj = super()._create(model_class, *args, **kwargs)
        obj.set_password(password)
        obj.save()
        return obj


class ContestCycleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ContestCycle

    name = factory.Sequence(lambda n: f"Test Contest Cycle {n:04d}")
    slug = factory.Sequence(lambda n: f"test-contest-cycle-{n:04d}")
    description = factory.Faker("sentence")
    status = ContestCycleStatus.DRAFT
    start_date = factory.LazyFunction(lambda: timezone.now() - timedelta(hours=1))
    end_date = factory.LazyFunction(lambda: timezone.now() + timedelta(days=7))
    points_multiplier = Decimal("1.00")
    is_featured = False
    max_participants = None
    metadata = factory.LazyFunction(dict)
    created_by = None


class LeaderboardSnapshotFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LeaderboardSnapshot

    contest_cycle = factory.SubFactory(ContestCycleFactory)
    scope = LeaderboardScope.GLOBAL
    scope_ref = ""
    snapshot_data = factory.LazyFunction(list)
    top_n = 100
    status = SnapshotStatus.PENDING
    generated_at = None
    error_message = ""
    checksum = ""


class ContestRewardFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ContestReward

    contest_cycle = factory.SubFactory(ContestCycleFactory)
    title = factory.Sequence(lambda n: f"Reward {n:04d}")
    description = factory.Faker("sentence")
    reward_type = RewardType.POINTS
    reward_value = Decimal("100.00")
    rank_from = 1
    rank_to = 10
    total_budget = None
    issued_count = 0
    is_active = True
    image_url = ""
    metadata = factory.LazyFunction(dict)


class UserAchievementFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserAchievement

    user = factory.SubFactory(UserFactory)
    contest_cycle = factory.SubFactory(ContestCycleFactory)
    contest_reward = None
    achievement_type = AchievementType.BADGE
    title = factory.Sequence(lambda n: f"Achievement {n:04d}")
    description = factory.Faker("sentence")
    points_awarded = 0
    rank_at_award = None
    is_awarded = False
    awarded_at = None
    is_notified = False
    notified_at = None
    metadata = factory.LazyFunction(dict)
