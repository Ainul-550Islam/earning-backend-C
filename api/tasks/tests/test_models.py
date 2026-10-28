"""api/tasks/tests/test_models.py — MasterTask, Completion, AdminLedger tests."""
import pytest
from decimal import Decimal
from django.utils import timezone


@pytest.mark.django_db
class TestMasterTask:
    def test_create_task(self, master_task):
        assert master_task.task_id == 'TEST_TASK_001'
        assert master_task.is_active is True

    def test_str_representation(self, master_task):
        assert 'TEST_TASK_001' in str(master_task) or 'Test Click Task' in str(master_task)

    def test_active_manager(self, db, master_task, inactive_task):
        from api.tasks.models import MasterTask
        active = MasterTask.objects.filter(is_active=True)
        assert master_task in active
        assert inactive_task not in active

    def test_task_ordering(self, db, master_task, featured_task):
        from api.tasks.models import MasterTask
        tasks = list(MasterTask.objects.filter(is_active=True).order_by('-is_featured', 'sort_order'))
        assert tasks[0] == featured_task   # Featured first


@pytest.mark.django_db
class TestUserTaskCompletion:
    def test_create_completion(self, completion):
        assert completion.status == 'completed'
        assert completion.reward_amount == Decimal('0.25')

    def test_admin_revenue_set(self, completion):
        assert completion.admin_revenue_received == Decimal('0.075')

    def test_completion_for_user(self, db, completion, user):
        from api.tasks.models import UserTaskCompletion
        user_completions = UserTaskCompletion.objects.filter(user=user, status='completed')
        assert completion in user_completions

    def test_total_earned(self, db, user, master_task):
        from api.tasks.models import UserTaskCompletion
        UserTaskCompletion.objects.create(
            user=user, task=master_task, status='completed',
            reward_amount=Decimal('0.50'), completed_at=timezone.now(),
        )
        UserTaskCompletion.objects.create(
            user=user, task=master_task, status='completed',
            reward_amount=Decimal('0.25'), completed_at=timezone.now(),
        )
        from api.tasks.managers import UserTaskCompletionManager
        total = UserTaskCompletion.objects.filter(user=user).completed().total_earned()
        assert total == Decimal('0.75')


@pytest.mark.django_db
class TestAdminLedger:
    def test_create_ledger_entry(self, db, completion):
        from api.tasks.models import AdminLedger
        entry = AdminLedger.objects.create(
            completion=completion,
            amount=Decimal('0.075'),
            source='task_completion',
        )
        assert entry.amount == Decimal('0.075')

    def test_admin_profit(self, db, completion):
        from api.tasks.models import AdminLedger
        AdminLedger.objects.create(
            completion=completion, amount=Decimal('0.10'), source='task_completion'
        )
        total = AdminLedger.objects.total_profit()
        assert total >= Decimal('0.10')
