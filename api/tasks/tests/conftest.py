"""
api/tasks/tests/conftest.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Shared pytest fixtures for the task system test suite.
Run: pytest api/tasks/tests/ -v --tb=short
"""

import pytest
import django
from django.conf import settings

# Configure Django before importing models
if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'tasks',
        ],
        SECRET_KEY='test-secret-key',
        USE_TZ=True,
    )
    django.setup()

from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


# ══════════════════════════════════════════════════════════════════════════════
# USERS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def user(db):
    """Standard authenticated user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123!',
        is_active=True,
    )


@pytest.fixture
def staff_user(db):
    """Staff/admin user."""
    return User.objects.create_user(
        username='staffuser',
        email='staff@example.com',
        password='staffpass123!',
        is_active=True,
        is_staff=True,
    )


@pytest.fixture
def second_user(db):
    """Second user for referral/multi-user tests."""
    return User.objects.create_user(
        username='seconduser',
        email='second@example.com',
        password='testpass123!',
        is_active=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# TASKS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def master_task(db):
    """A standard active MasterTask."""
    from api.tasks.models import MasterTask
    return MasterTask.objects.create(
        task_id='TEST_TASK_001',
        name='Test Click Task',
        category='daily_retention',
        system_type='click_visit',
        is_active=True,
        is_featured=False,
        rewards={'type': 'fixed', 'amount': '0.25'},
        sort_order=1,
    )


@pytest.fixture
def featured_task(db):
    """A featured active MasterTask."""
    from api.tasks.models import MasterTask
    return MasterTask.objects.create(
        task_id='TEST_TASK_FEATURED',
        name='Featured Video Task',
        category='monetization',
        system_type='video_watch',
        is_active=True,
        is_featured=True,
        rewards={'type': 'fixed', 'amount': '0.50'},
        sort_order=0,
    )


@pytest.fixture
def inactive_task(db):
    """An inactive MasterTask."""
    from api.tasks.models import MasterTask
    return MasterTask.objects.create(
        task_id='TEST_TASK_INACTIVE',
        name='Inactive Task',
        category='daily_retention',
        system_type='click_visit',
        is_active=False,
        rewards={'type': 'fixed', 'amount': '0.10'},
        sort_order=99,
    )


# ══════════════════════════════════════════════════════════════════════════════
# COMPLETIONS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def completion(db, user, master_task):
    """A completed UserTaskCompletion."""
    from api.tasks.models import UserTaskCompletion
    return UserTaskCompletion.objects.create(
        user=user,
        task=master_task,
        status='completed',
        reward_amount=Decimal('0.25'),
        admin_revenue_received=Decimal('0.075'),
        ip_address='192.168.1.1',
        user_agent='TestAgent/1.0',
        completed_at=timezone.now(),
    )


@pytest.fixture
def pending_completion(db, user, master_task):
    """A pending UserTaskCompletion."""
    from api.tasks.models import UserTaskCompletion
    return UserTaskCompletion.objects.create(
        user=user,
        task=master_task,
        status='pending',
        reward_amount=Decimal('0.25'),
        ip_address='192.168.1.1',
    )


# ══════════════════════════════════════════════════════════════════════════════
# API CLIENT
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def api_client():
    """DRF test client."""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    """Authenticated DRF test client."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def staff_client(api_client, staff_user):
    """Staff-authenticated DRF test client."""
    api_client.force_authenticate(user=staff_user)
    return api_client


# ══════════════════════════════════════════════════════════════════════════════
# CACHE & REDIS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def clear_cache():
    """Clear Django cache before each test."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def mock_cache(mocker):
    """Mock cache for tests that need controlled cache behavior."""
    mock = mocker.MagicMock()
    mocker.patch('django.core.cache.cache', mock)
    return mock


# ══════════════════════════════════════════════════════════════════════════════
# CELERY
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope='session')
def celery_config():
    """Celery configuration for testing (synchronous execution)."""
    return {
        'task_always_eager':       True,
        'task_eager_propagates':   True,
        'broker_url':              'memory://',
        'result_backend':          'cache+memory://',
    }


@pytest.fixture
def celery_app(celery_config):
    """Celery app configured for synchronous test execution."""
    from celery import current_app
    current_app.config_from_object(celery_config)
    return current_app


# ══════════════════════════════════════════════════════════════════════════════
# MONITORING FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def task_monitor(db):
    """A healthy TaskMonitor."""
    from api.tasks.models.monitoring import TaskMonitor
    return TaskMonitor.objects.create(
        task_name='tasks.test_task.test_func',
        status='healthy',
        success_rate=99.5,
        avg_duration=0.5,
        run_count=100,
        success_count=99,
        failure_count=1,
    )


@pytest.fixture
def dlq_entry(db):
    """A DLQ entry for testing."""
    from api.tasks.models.queue import TaskDeadLetterQueue
    return TaskDeadLetterQueue.objects.create(
        task_name='tasks.test_task.failing_task',
        task_id='test-task-id-001',
        failure_reason='exception',
        exception='RuntimeError: test exception',
        payload={'user_id': 1},
        retry_count=3,
        reprocess_status='pending',
        failed_at=timezone.now(),
    )


@pytest.fixture
def worker_health(db):
    """A healthy worker health record."""
    from api.tasks.models.monitoring import WorkerHealth
    return WorkerHealth.objects.create(
        worker_id='celery@worker-001',
        hostname='worker-001',
        status='online',
        active_tasks=2,
        concurrency=4,
        load_avg='0.5,0.4,0.3',
        last_heartbeat=timezone.now(),
    )


# ══════════════════════════════════════════════════════════════════════════════
# DATA FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_postback_data():
    """Sample S2S postback data dict."""
    return {
        'click_id':       'click_abc123',
        'offer_id':       'OFFER_001',
        'transaction_id': 'txn_xyz789',
        'payout':         '1.50',
        'status':         'approved',
        'pub_id':         '42',
        'country':        'US',
        'device':         'mobile',
        'ip':             '1.2.3.4',
    }


@pytest.fixture
def sample_cpi_data():
    """Sample CPI install event data."""
    return {
        'click_id':     'click_cpi_001',
        'app_id':       'com.example.app',
        'bundle_id':    'com.example.app',
        'platform':     'android',
        'device_id':    'device_abc123',
        'install_time': timezone.now().isoformat(),
        'publisher_id': 1,
        'mmp_name':     'appsflyer',
        'event_type':   'install',
    }


@pytest.fixture
def sample_quiz_session():
    """Sample quiz session context."""
    return {
        'quiz_id':      'personality_001',
        'user_id':      1,
        'publisher_id': 1,
        'click_id':     'click_quiz_001',
        'country':      'US',
        'device':       'mobile',
        'answers':      [
            {'question_id': 'q1', 'answer': 'A', 'answer_index': 0, 'time_taken_seconds': 5},
            {'question_id': 'q2', 'answer': 'B', 'answer_index': 1, 'time_taken_seconds': 8},
            {'question_id': 'q3', 'answer': 'C', 'answer_index': 2, 'time_taken_seconds': 6},
        ],
    }


@pytest.fixture
def fraud_context_clean():
    """Clean user fraud context."""
    return {
        'user_id':           1,
        'ip_address':        '8.8.8.8',
        'velocity_1h':       3,
        'ip_diversity':      3,
        'account_age_hours': 720,
        'reward_vs_avg':     1.1,
        'new_account':       False,
        'ip_blocked':        False,
    }


@pytest.fixture
def fraud_context_suspicious():
    """Suspicious fraud context."""
    return {
        'user_id':           99,
        'ip_address':        '1.2.3.4',
        'velocity_1h':       80,
        'ip_diversity':      1,
        'account_age_hours': 2,
        'reward_vs_avg':     8.0,
        'new_account':       True,
        'ip_blocked':        False,
    }
