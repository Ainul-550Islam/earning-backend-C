# =============================================================================
# version_control/tests/factories.py
# =============================================================================
"""
Factory Boy factories for version_control models.

Usage::

    policy   = AppUpdatePolicyFactory(platform="ios", status="active")
    schedule = MaintenanceScheduleFactory.build()  # no DB
    redirect = PlatformRedirectFactory(platform="android")
"""

from __future__ import annotations

import random
from datetime import timedelta

import factory
from django.contrib.auth import get_user_model
from django.utils import timezone
from factory.django import DjangoModelFactory

from ..choices import (
    MaintenanceStatus,
    Platform,
    PolicyStatus,
    RedirectType,
    UpdateType,
)
from ..models import AppUpdatePolicy, MaintenanceSchedule, PlatformRedirect

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username  = factory.Sequence(lambda n: f"vc_user_{n:04d}")
    email     = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password  = factory.PostGenerationMethodCall("set_password", "password")
    is_active = True
    is_staff  = False


class StaffUserFactory(UserFactory):
    is_staff = True


class AppUpdatePolicyFactory(DjangoModelFactory):
    class Meta:
        model = AppUpdatePolicy

    platform       = factory.Iterator(Platform.values)
    min_version    = "1.0.0"
    max_version    = ""
    target_version = "2.0.0"
    update_type    = UpdateType.OPTIONAL
    release_notes  = factory.Faker("paragraph")
    release_notes_url = factory.Faker("url")
    force_update_after = None
    status         = PolicyStatus.DRAFT
    created_by     = factory.SubFactory(StaffUserFactory)
    metadata       = factory.LazyFunction(dict)

    class Params:
        active = factory.Trait(status=PolicyStatus.ACTIVE)
        critical = factory.Trait(update_type=UpdateType.CRITICAL)
        required = factory.Trait(update_type=UpdateType.REQUIRED)


class MaintenanceScheduleFactory(DjangoModelFactory):
    class Meta:
        model = MaintenanceSchedule

    title           = factory.Faker("sentence", nb_words=4)
    description     = factory.Faker("paragraph")
    platforms       = factory.LazyFunction(list)   # empty = all platforms
    status          = MaintenanceStatus.SCHEDULED
    scheduled_start = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=1))
    scheduled_end   = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=2))
    actual_start    = None
    actual_end      = None
    bypass_token    = ""
    notify_users    = True

    class Params:
        active = factory.Trait(
            status=MaintenanceStatus.ACTIVE,
            scheduled_start=factory.LazyFunction(
                lambda: timezone.now() - timedelta(minutes=5)
            ),
            actual_start=factory.LazyFunction(timezone.now),
        )
        ios_only = factory.Trait(platforms=["ios"])
        short = factory.Trait(
            scheduled_end=factory.LazyFunction(
                lambda: timezone.now() + timedelta(minutes=10)
            )
        )


class PlatformRedirectFactory(DjangoModelFactory):
    class Meta:
        model = PlatformRedirect
        django_get_or_create = ("platform",)

    platform      = factory.Iterator(Platform.values)
    redirect_type = RedirectType.STORE
    url           = factory.LazyAttribute(
        lambda o: (
            "https://apps.apple.com/app/id1234567890"
            if o.platform == "ios"
            else "https://play.google.com/store/apps/details?id=com.example.app"
        )
    )
    is_active     = True
    notes         = ""
