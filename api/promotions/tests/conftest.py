# =============================================================================
# promotions/tests/conftest.py
# 🔴 CRITICAL — Pytest configuration & shared fixtures
# =============================================================================
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture(scope='session')
def django_db_setup():
    pass


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username='admin_test',
        email='admin@test.com',
        password='AdminPass123!'
    )


@pytest.fixture
def publisher_user(db):
    return User.objects.create_user(
        username='publisher_test',
        email='publisher@test.com',
        password='PubPass123!'
    )


@pytest.fixture
def advertiser_user(db):
    return User.objects.create_user(
        username='advertiser_test',
        email='advertiser@test.com',
        password='AdvPass123!'
    )


@pytest.fixture
def base_category(db):
    from api.promotions.models import PromotionCategory
    return PromotionCategory.objects.create(name='social', sort_order=1)


@pytest.fixture
def base_reward_policy(db):
    from api.promotions.models import RewardPolicy
    return RewardPolicy.objects.create(
        name='Test Policy',
        base_reward=Decimal('1.00'),
        min_reward=Decimal('0.50'),
        max_reward=Decimal('10.00'),
        platform_commission_rate=Decimal('0.20'),
    )


@pytest.fixture
def active_campaign(db, advertiser_user, base_category, base_reward_policy):
    from api.promotions.models import Campaign
    return Campaign.objects.create(
        title='Test Active Campaign',
        description='A test campaign for automated testing',
        advertiser=advertiser_user,
        category=base_category,
        reward_policy=base_reward_policy,
        total_budget=Decimal('500.00'),
        per_task_reward=Decimal('1.00'),
        max_tasks_per_user=5,
        status='active',
    )


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def auth_client(publisher_user):
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=publisher_user)
    return client


@pytest.fixture
def admin_client(admin_user):
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client
