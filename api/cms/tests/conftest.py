import pytest

# ── Model imports (loaded after Django setup) ─────────────────────────────────
Survey = Transaction = SEOModel = UserProfile = UserSegment = None
Decimal = None
try:
    from decimal import Decimal
    from api.cms.models_new.profile_surveys import SurveyTemplate as Survey, SurveyCompletion, SurveyCategory
    from api.cms.models_new.survey_rewards import RewardTransaction as Transaction, RewardPool, SurveyReward
    from api.cms.models_new.seo import SEOConfig as SEOModel, Redirect301
    from api.cms.models_new.user_profile import UserProfile, UserSegment
    from api.cms.models_new.task_management import TaskSchedule, TaskExecution
    from api.cms.models_new.cpalead import VirtualCurrency, UserVirtualBalance, ConversionLog
except Exception as _e:
    import logging
    logging.getLogger('cms.tests').warning(f"conftest model import failed: {_e}")
# ──────────────────────────────────────────────────────────────────────────────

# api/cms/tests/conftest.py
"""Pytest fixtures shared across all CMS tests."""


from datetime import datetime, timedelta, date
from api.cms.models_new.survey_rewards import RewardTransaction as Transaction, RewardPool
from decimal import Decimal




@pytest.fixture(autouse=True)
def _no_fk(db):
    """Disable SQLite FK enforcement for every test."""
    from django.db import connections
    for alias in connections:
        conn = connections[alias]
        if conn.vendor == 'sqlite':
            # Must use ensure_connection first
            conn.ensure_connection()
            conn.connection.execute('PRAGMA foreign_keys = OFF')

@pytest.fixture
def user(db):
    from api.cms.factories import UserFactory
    return UserFactory.create()


@pytest.fixture
def admin_user(db):
    from api.cms.factories import UserFactory
    return UserFactory.create_admin()


@pytest.fixture
def virtual_currency(db):
    from api.cms.models_new.cpalead import VirtualCurrency
    vc, _ = VirtualCurrency.objects.get_or_create(
        name='Test Coins',
        defaults={'symbol': 'TC', 'usd_ratio': 100, 'daily_earn_cap': 5000, 'is_active': True}
    )
    return vc


@pytest.fixture
def user_with_balance(db, user, virtual_currency):
    from api.cms.models_new.cpalead import UserVirtualBalance
    UserVirtualBalance.objects.get_or_create(
        user=user, currency=virtual_currency,
        defaults={'balance': 1000, 'total_earned': 1000}
    )
    return user


@pytest.fixture
def quiz(db):
    from api.cms.factories import QuizFactory
    return QuizFactory.create(num_questions=3)


@pytest.fixture
def smartlink(db):
    from api.cms.factories import SmartLinkFactory
    return SmartLinkFactory.create()


@pytest.fixture
def content_locker(db):
    from api.cms.factories import ContentLockerFactory
    return ContentLockerFactory.create()


@pytest.fixture
def dynamic_form(db):
    from api.cms.factories import DynamicFormFactory
    return DynamicFormFactory.create(num_fields=3)


@pytest.fixture
def site_config(db):
    from api.cms.factories import SiteConfigFactory
    return SiteConfigFactory.create()


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


# ── Additional fixtures for survey, segment, workflow tests ──────────────────

@pytest.fixture
def survey_category(db):
    from api.cms.models_new.profile_surveys import SurveyCategory
    return SurveyCategory.objects.create(
        uuid=__import__('uuid').uuid4(),
        name='Test Category',
        slug='test-category',
    )


@pytest.fixture
def survey_template(db, survey_category):
    from api.cms.models_new.profile_surveys import SurveyTemplate
    return SurveyTemplate.objects.create(
        uuid=__import__('uuid').uuid4(),
        title='Test Survey',
        description='A test survey',
        category=survey_category,
        survey_type='profile',
        status='active',
    )


@pytest.fixture
def survey_completion(db, user, survey_template):
    from api.cms.models_new.profile_surveys import SurveyCompletion
    from django.utils import timezone
    obj, _ = SurveyCompletion.objects.get_or_create(
        survey=survey_template,
        user=user,
        defaults={
            'uuid': __import__('uuid').uuid4(),
            'status': 'completed',
            'started_at': timezone.now(),
            'completed_at': timezone.now(),
        }
    )
    return obj


@pytest.fixture
def user_segment(db):
    from api.cms.models_new.user_profile import UserSegment
    return UserSegment.objects.create(
        name='Test Segment',
        description='Test segment for testing',
        criteria={},
        is_active=True,
    )


@pytest.fixture
def reward_pool(db):
    from api.cms.models_new.survey_rewards import RewardPool
    from decimal import Decimal
    pool, _ = RewardPool.objects.get_or_create(
        name='Test Pool',
        defaults={
            'total_budget': Decimal('10000.00'),
            'allocated_amount': Decimal('0'),
            'paid_amount': Decimal('0'),
        }
    )
    return pool


@pytest.fixture
def workflow_state(db, admin_user):
    from api.cms.models_new.workflow import WorkflowState
    from django.contrib.contenttypes.models import ContentType
    return WorkflowState.objects.create(
        uuid=__import__('uuid').uuid4(),
        content_type='blogpost',
        object_id=1,
        state='draft',
        created_by=admin_user,
    )


@pytest.fixture
def leaderboard_period(db):
    from api.cms.models_new.leaderboard import LeaderboardPeriod
    from django.utils import timezone
    return LeaderboardPeriod.objects.create(
        period_type='weekly',
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timezone.timedelta(days=7)).date(),
        is_active=True,
    )


@pytest.fixture
def survey_question(db, survey_template):
    from api.cms.models_new.profile_surveys import SurveyQuestion
    return SurveyQuestion.objects.create(
        uuid=__import__('uuid').uuid4(),
        survey=survey_template,
        question_text='What is your favourite colour?',
        question_type='single_choice',
        is_required=True,
        order=1,
        choices=['Red','Blue','Green'],
    )


@pytest.fixture
def survey_response(db, survey_completion, survey_question):
    from api.cms.models_new.profile_surveys import SurveyResponse
    return SurveyResponse.objects.create(
        uuid=__import__('uuid').uuid4(),
        completion=survey_completion,
        question=survey_question,
        answer='Blue',
    )


@pytest.fixture
def reward_transaction(db, user, reward_pool):
    from api.cms.models_new.survey_rewards import RewardTransaction
    return RewardTransaction.objects.create(
        user=user,
        tx_type='earn',
        amount='5.00',
    )


@pytest.fixture
def user_profile(db, user):
    from api.cms.models_new.user_profile import UserProfile
    obj, _ = UserProfile.objects.get_or_create(user=user)
    return obj


@pytest.fixture
def survey_reward(db, user, survey_template):
    from api.cms.models_new.survey_rewards import SurveyReward
    from decimal import Decimal
    sr, _ = SurveyReward.objects.get_or_create(
        survey=survey_template,
        defaults={
            'name': 'Test Reward',
            'reward_type': 'fixed',
            'base_amount': Decimal('2.50'),
            'bonus_amount': Decimal('0.50'),
        }
    )
    return sr


@pytest.fixture
def task_schedule(db):
    from api.cms.models_new.task_management import TaskSchedule
    return TaskSchedule.objects.create(
        uuid=__import__('uuid').uuid4(),
        name='Test Task',
        task_path='api.cms.tasks.test_task',
        frequency='daily',
        schedule_type='interval',
        is_active=True,
    )
