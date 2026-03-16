# =============================================================================
# behavior_analytics/tests/factories.py
# =============================================================================
"""
Factory Boy factories for behavior_analytics models.

Usage::

    path    = UserPathFactory()
    clicks  = ClickMetricFactory.create_batch(5, path=path)
    score   = EngagementScoreFactory(user=path.user)

All factories use DjangoModelFactory and set reasonable defaults.
Traits are provided for common states (bounced, high-engagement, etc.).
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone as py_tz

import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from ..choices import (
    ClickCategory,
    DeviceType,
    EngagementTier,
    PathNodeType,
    SessionStatus,
)
from ..models import ClickMetric, EngagementScore, StayTime, UserPath

User = get_user_model()


# ---------------------------------------------------------------------------
# User factory
# ---------------------------------------------------------------------------

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username  = factory.Sequence(lambda n: f"user_{n:04d}")
    email     = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password  = factory.PostGenerationMethodCall("set_password", "password")
    is_active = True


# ---------------------------------------------------------------------------
# UserPath factory
# ---------------------------------------------------------------------------

class UserPathFactory(DjangoModelFactory):
    class Meta:
        model = UserPath

    user        = factory.SubFactory(UserFactory)
    session_id  = factory.LazyFunction(lambda: str(uuid.uuid4()))
    device_type = factory.Iterator(DeviceType.values)
    status      = SessionStatus.ACTIVE
    entry_url   = factory.Faker("url")
    exit_url    = ""
    nodes       = factory.LazyFunction(
        lambda: [
            {
                "url":    f"/page-{i}/",
                "type":   "navigation",
                "ts":     1_700_000_000 + i * 30,
                "status": 200,
            }
            for i in range(random.randint(2, 8))
        ]
    )
    user_agent  = factory.Faker("user_agent")

    class Params:
        # trait: bounced session (single node)
        bounced = factory.Trait(
            status=SessionStatus.BOUNCED,
            nodes=factory.LazyFunction(
                lambda: [{"url": "/home/", "type": "entry", "ts": 1_700_000_000}]
            ),
        )
        # trait: completed long session
        completed = factory.Trait(
            status=SessionStatus.COMPLETED,
            exit_url=factory.Faker("url"),
        )


# ---------------------------------------------------------------------------
# ClickMetric factory
# ---------------------------------------------------------------------------

class ClickMetricFactory(DjangoModelFactory):
    class Meta:
        model = ClickMetric

    path              = factory.SubFactory(UserPathFactory)
    page_url          = factory.Faker("url")
    element_selector  = factory.LazyFunction(
        lambda: random.choice(["#cta-button", ".nav-link", "form > button", "a.hero-link"])
    )
    element_text      = factory.Faker("word")
    category          = factory.Iterator(ClickCategory.values)
    clicked_at        = factory.LazyFunction(lambda: datetime.now(tz=py_tz.utc))
    x_position        = factory.LazyFunction(lambda: random.randint(0, 1920))
    y_position        = factory.LazyFunction(lambda: random.randint(0, 1080))
    viewport_width    = 1920
    viewport_height   = 1080
    metadata          = factory.LazyFunction(dict)


# ---------------------------------------------------------------------------
# StayTime factory
# ---------------------------------------------------------------------------

class StayTimeFactory(DjangoModelFactory):
    class Meta:
        model = StayTime

    path                 = factory.SubFactory(UserPathFactory)
    page_url             = factory.Faker("url")
    duration_seconds     = factory.LazyFunction(lambda: random.randint(5, 600))
    is_active_time       = True
    scroll_depth_percent = factory.LazyFunction(lambda: random.randint(10, 100))

    class Params:
        bounce = factory.Trait(duration_seconds=3)


# ---------------------------------------------------------------------------
# EngagementScore factory
# ---------------------------------------------------------------------------

class EngagementScoreFactory(DjangoModelFactory):
    class Meta:
        model          = EngagementScore
        django_get_or_create = ("user", "date")

    user           = factory.SubFactory(UserFactory)
    date           = factory.LazyFunction(
        lambda: __import__("django.utils.timezone", fromlist=["localdate"]).localdate()
    )
    score          = factory.LazyFunction(
        lambda: round(random.uniform(0, 100), 2)
    )
    tier           = factory.LazyAttribute(
        lambda o: (
            EngagementTier.ELITE  if o.score >= 86 else
            EngagementTier.HIGH   if o.score >= 61 else
            EngagementTier.MEDIUM if o.score >= 31 else
            EngagementTier.LOW
        )
    )
    click_count    = factory.LazyFunction(lambda: random.randint(0, 200))
    total_stay_sec = factory.LazyFunction(lambda: random.randint(0, 7200))
    path_depth     = factory.LazyFunction(lambda: random.randint(0, 30))
    return_visits  = factory.LazyFunction(lambda: random.randint(0, 15))
    breakdown_json = factory.LazyFunction(dict)

    class Params:
        high_engagement = factory.Trait(
            score=92.50,
            tier=EngagementTier.ELITE,
        )
        low_engagement = factory.Trait(
            score=10.00,
            tier=EngagementTier.LOW,
        )
