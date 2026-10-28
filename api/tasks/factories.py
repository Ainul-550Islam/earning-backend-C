"""
api/tasks/factories.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Factory Boy model factories for the task system.
Used in tests to create test data easily.

Usage:
    from api.tasks.factories import MasterTaskFactory, UserTaskCompletionFactory

    task       = MasterTaskFactory()
    completion = UserTaskCompletionFactory(user=user, task=task)
    admin_ledger = AdminLedgerFactory(completion=completion)
"""

import factory
import factory.fuzzy
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for creating test User instances."""

    class Meta:
        model       = get_user_model()
        skip_postgeneration_save = True

    username   = factory.Sequence(lambda n: f'user_{n:04d}')
    email      = factory.LazyAttribute(lambda o: f'{o.username}@example.com')
    first_name = factory.Faker('first_name')
    last_name  = factory.Faker('last_name')
    is_active  = True
    is_staff   = False

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        password = extracted or 'testpass123!'
        self.set_password(password)
        if create:
            self.save()


class StaffUserFactory(UserFactory):
    """Factory for staff/admin users."""
    is_staff     = True
    is_superuser = False


class MasterTaskFactory(factory.django.DjangoModelFactory):
    """Factory for creating MasterTask instances."""

    class Meta:
        try:
            from api.tasks.models import MasterTask
            model = MasterTask
        except ImportError:
            model = None

    task_id     = factory.Sequence(lambda n: f'TASK_{n:06d}')
    name        = factory.Faker('sentence', nb_words=4)
    category    = factory.fuzzy.FuzzyChoice([
        'daily_retention', 'monetization', 'social', 'gaming', 'survey'
    ])
    system_type = factory.fuzzy.FuzzyChoice([
        'click_visit', 'social_follow', 'video_watch', 'app_install', 'survey'
    ])
    is_active   = True
    is_featured = False
    sort_order  = factory.Sequence(lambda n: n)
    rewards     = factory.LazyFunction(lambda: {'type': 'fixed', 'amount': '0.25'})


class UserTaskCompletionFactory(factory.django.DjangoModelFactory):
    """Factory for creating UserTaskCompletion instances."""

    class Meta:
        try:
            from api.tasks.models import UserTaskCompletion
            model = UserTaskCompletion
        except ImportError:
            model = None

    user          = factory.SubFactory(UserFactory)
    task          = factory.SubFactory(MasterTaskFactory)
    status        = 'completed'
    reward_amount = factory.fuzzy.FuzzyDecimal(0.01, 2.00, precision=4)
    ip_address    = factory.Faker('ipv4')
    user_agent    = factory.Faker('user_agent')
    completed_at  = factory.LazyFunction(timezone.now)


class AdminLedgerFactory(factory.django.DjangoModelFactory):
    """Factory for creating AdminLedger entries."""

    class Meta:
        try:
            from api.tasks.models import AdminLedger
            model = AdminLedger
        except ImportError:
            model = None

    completion    = factory.SubFactory(UserTaskCompletionFactory)
    amount        = factory.fuzzy.FuzzyDecimal(0.001, 0.10, precision=4)
    source        = 'task_completion'
    created_at    = factory.LazyFunction(timezone.now)


# ── Monitoring Factories ───────────────────────────────────────────────────

class TaskMonitorFactory(factory.django.DjangoModelFactory):

    class Meta:
        try:
            from api.tasks.models.monitoring import TaskMonitor
            model = TaskMonitor
        except ImportError:
            model = None

    task_name   = factory.Sequence(lambda n: f'tasks.test_task_{n}')
    status      = 'healthy'
    success_rate = factory.fuzzy.FuzzyFloat(85.0, 100.0)
    avg_duration = factory.fuzzy.FuzzyFloat(0.1, 5.0)


class WorkerHealthFactory(factory.django.DjangoModelFactory):

    class Meta:
        try:
            from api.tasks.models.monitoring import WorkerHealth
            model = WorkerHealth
        except ImportError:
            model = None

    worker_id       = factory.Sequence(lambda n: f'worker-{n}@localhost')
    hostname        = factory.Faker('hostname')
    status          = 'online'
    active_tasks    = factory.fuzzy.FuzzyInteger(0, 10)
    concurrency     = 4
    last_heartbeat  = factory.LazyFunction(timezone.now)


class TaskDeadLetterQueueFactory(factory.django.DjangoModelFactory):

    class Meta:
        try:
            from api.tasks.models.queue import TaskDeadLetterQueue
            model = TaskDeadLetterQueue
        except ImportError:
            model = None

    task_name       = factory.Sequence(lambda n: f'tasks.failing_task_{n}')
    task_id         = factory.Faker('uuid4')
    failure_reason  = 'exception'
    exception       = 'RuntimeError: test error'
    payload         = factory.LazyFunction(dict)
    retry_count     = 0
    reprocess_status = 'pending'
    failed_at       = factory.LazyFunction(timezone.now)


__all__ = [
    'UserFactory', 'StaffUserFactory', 'MasterTaskFactory',
    'UserTaskCompletionFactory', 'AdminLedgerFactory',
    'TaskMonitorFactory', 'WorkerHealthFactory',
    'TaskDeadLetterQueueFactory',
]
