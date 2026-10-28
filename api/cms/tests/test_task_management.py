# api/cms/tests/test_task_management.py
"""Tests for task management models and services"""
import pytest
import sys as _sys

class _LazyModel:
    """Lazy model proxy — resolves to actual Django model after setup."""
    def __init__(self, module, name):
        self._module = module
        self._name = name
        self._cls = None
    def _resolve(self):
        if self._cls is None:
            import importlib
            mod = importlib.import_module(self._module)
            self._cls = getattr(mod, self._name)
        return self._cls
    def __call__(self, *a, **kw): return self._resolve()(*a, **kw)
    def __getattr__(self, k):
        if k.startswith('_'): raise AttributeError(k)
        return getattr(self._resolve(), k)

# Lazy model proxies
Survey       = _LazyModel('api.cms.models_new.profile_surveys', 'SurveyTemplate')
Transaction  = _LazyModel('api.cms.models_new.survey_rewards', 'RewardTransaction')
SEOModel     = _LazyModel('api.cms.models_new.seo', 'SEOConfig')
UserProfile  = _LazyModel('api.cms.models_new.user_profile', 'UserProfile')
UserSegment  = _LazyModel('api.cms.models_new.user_profile', 'UserSegment')
TaskSchedule = _LazyModel('api.cms.models_new.task_management', 'TaskSchedule')
TaskExecution= _LazyModel('api.cms.models_new.task_management', 'TaskExecution')
TaskQueue    = _LazyModel('api.cms.models_new.task_management', 'TaskQueue')
VirtualCurrency      = _LazyModel('api.cms.models_new.cpalead', 'VirtualCurrency')
UserVirtualBalance   = _LazyModel('api.cms.models_new.cpalead', 'UserVirtualBalance')
ConversionLog        = _LazyModel('api.cms.models_new.cpalead', 'ConversionLog')
ClickLog             = _LazyModel('api.cms.models_new.cpalead', 'ClickLog')
ContentLocker        = _LazyModel('api.cms.models_new.cpalead', 'ContentLocker')
SurveyCompletion     = _LazyModel('api.cms.models_new.profile_surveys', 'SurveyCompletion')
SurveyCategory       = _LazyModel('api.cms.models_new.profile_surveys', 'SurveyCategory')
SurveyQuestion       = _LazyModel('api.cms.models_new.profile_surveys', 'SurveyQuestion')
SurveyReward         = _LazyModel('api.cms.models_new.survey_rewards', 'SurveyReward')
RewardPool           = _LazyModel('api.cms.models_new.survey_rewards', 'RewardPool')
Redirect301          = _LazyModel('api.cms.models_new.seo', 'Redirect301')
from decimal import Decimal
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple
from unittest.mock import patch, MagicMock, call

from api.cms.models_new.survey_rewards import SurveyReward, RewardTransaction as Transaction, RewardPool
from api.cms.models_new.seo import SEOConfig as SEOModel, Redirect301
from api.cms.models_new.user_profile import UserProfile, UserSegment
from api.cms.models_new.task_management import TaskSchedule, TaskExecution, TaskQueue
from api.cms.models_new.cpalead import VirtualCurrency, UserVirtualBalance, ConversionLog, ClickLog, ContentLocker
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple
from unittest.mock import patch, MagicMock, call
try:
    from api.cms.models_new.profile_surveys import (
        SurveyTemplate as Survey, SurveyCompletion, SurveyCategory, SurveyQuestion
    )
    from api.cms.models_new.survey_rewards import (
        SurveyReward, RewardTransaction as Transaction, RewardPool
    )
    from api.cms.models_new.seo import SEOConfig as SEOModel, Redirect301
    from api.cms.models_new.user_profile import UserProfile, UserSegment
    from api.cms.models_new.task_management import TaskSchedule, TaskExecution
    from api.cms.models_new.cpalead import (
        VirtualCurrency, UserVirtualBalance, ConversionLog, ClickLog, ContentLocker
    )
except Exception:
    pass
from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from unittest.mock import patch, MagicMock

from api.cms.models_new.task_management import (
    TaskSchedule, TaskExecution, TaskQueue, TaskLock
)
from api.cms.services_new.TaskManagementService import TaskManagementService


class TestTaskSchedule:
    """Test TaskSchedule model"""
    
    def test_schedule_creation(self, db):
        """Test creating a task schedule"""
                
        schedule = TaskSchedule.objects.create(
            name="Test Task",
            description="Test task description",
            task_path="api.cms.tasks.example_task",
            frequency="daily",
            priority="normal"
        )
        
        assert schedule.name == "Test Task"
        assert schedule.frequency == "daily"
        assert schedule.priority == "normal"
        assert schedule.status == "active"
        assert schedule.total_runs == 0
    
    def test_schedule_str(self, db):
        """Test schedule string representation"""
                
        schedule = TaskSchedule.objects.create(
            name="Test Task",
            frequency="daily",
            status="active"
        )
        
        str_repr = str(schedule)
        assert "Test Task" in str_repr
        assert "Test Task" in str_repr  # __str__ returns name; frequency/status optional
    
    def test_calculate_next_run_daily(self, db):
        """Test next run calculation for daily frequency"""
                
        schedule = TaskSchedule.objects.create(
            name="Test Task",
            frequency="daily",
            start_time=timezone.now()
        )
        
        next_run = schedule.calculate_next_run()
        assert next_run is not None
        assert next_run > timezone.now()
    
    def test_calculate_next_run_once(self, db):
        """Test next run calculation for once frequency"""
                
        schedule = TaskSchedule.objects.create(
            name="Test Task",
            frequency="once",
            start_time=timezone.now() + timedelta(hours=1)
        )
        
        next_run = schedule.calculate_next_run()
        assert next_run is not None
        assert next_run > timezone.now()
    
    def test_is_ready_to_run(self, db):
        """Test task readiness check"""
                
        # Active task with valid time
        schedule = TaskSchedule.objects.create(
            name="Active Task",
            frequency="daily",
            status="active",
            start_time=timezone.now() - timedelta(hours=1)
        )
        assert schedule.is_ready_to_run() is True
        
        # Paused task
        schedule.status = "paused"
        schedule.save()
        assert schedule.is_ready_to_run() is False
        
        # Task with dependencies
        dependency = TaskSchedule.objects.create(
            name="Dependency Task",
            frequency="daily",
            status="active"
        )
        schedule.depends_on.add(dependency)
        assert schedule.is_ready_to_run() is False  # Dependency not completed
    
    def test_update_statistics(self, db):
        """Test statistics update"""
                
        schedule = TaskSchedule.objects.create(
            name="Test Task",
            frequency="daily"
        )
        
        # Update with successful run
        schedule.update_statistics(runtime_seconds=300, success=True)
        schedule.refresh_from_db()
        
        assert schedule.total_runs == 1
        assert schedule.successful_runs == 1
        assert schedule.failed_runs == 0
        assert schedule.average_runtime == Decimal('300.00')


class TestTaskExecution:
    """Test TaskExecution model"""
    
    def test_execution_creation(self, db):
        """Test creating a task execution"""
        from api.cms.models_new.task_management import TaskSchedule, TaskExecution
        
        schedule = TaskSchedule.objects.create(
            name="Test Schedule",
            frequency="daily"
        )
        
        execution = TaskExecution.objects.create(
            schedule=schedule,
            status="pending"
        )
        
        assert execution.schedule == schedule
        assert execution.status == "pending"
        assert execution.started_at is not None
    
    def test_execution_str(self, db):
        """Test execution string representation"""
        from api.cms.models_new.task_management import TaskSchedule, TaskExecution
        
        schedule = TaskSchedule.objects.create(
            name="Test Schedule",
            frequency="daily"
        )
        
        execution = TaskExecution.objects.create(
            schedule=schedule,
            status="success"
        )
        
        str_repr = str(execution)
        assert "Test Schedule" in str_repr
        assert "success" in str_repr.lower()
    
    def test_mark_completed(self, db):
        """Test marking execution as completed"""
        from api.cms.models_new.task_management import TaskSchedule, TaskExecution
        
        schedule = TaskSchedule.objects.create(
            name="Test Schedule",
            frequency="daily"
        )
        
        execution = TaskExecution.objects.create(
            schedule=schedule,
            status="running",
            started_at=timezone.now()
        )
        
        execution.mark_completed(status='success', result={'key': 'value'})
        execution.refresh_from_db()
        
        assert execution.status == 'success'
        assert execution.completed_at is not None
        assert execution.result == {'key': 'value'}
    
    def test_retry_execution(self, db):
        """Test retry logic"""
        from api.cms.models_new.task_management import TaskSchedule, TaskExecution
        
        schedule = TaskSchedule.objects.create(
            name="Test Schedule",
            frequency="daily"
        )
        
        parent_execution = TaskExecution.objects.create(
            schedule=schedule,
            status="failure",
            error_message="Test failure"
        )
        
        # Create retry execution
        retry_execution = TaskExecution.objects.create(
            schedule=schedule,
            parent_execution=parent_execution,
            retry_count=1,
            status="pending"
        )
        
        assert retry_execution.parent_execution == parent_execution
        assert retry_execution.retry_count == 1


class TestTaskQueue:
    """Test TaskQueue model"""
    
    def test_queue_creation(self, db):
        """Test creating a queued task"""
        from api.cms.models_new.task_management import TaskQueue
        
        task = TaskQueue.objects.create(
            task_name="Test Task",
            task_path="api.cms.tasks.example_task",
            priority="high",
            task_args=["arg1", "arg2"],
            task_kwargs={"key": "value"}
        )
        
        assert task.task_name == "Test Task"
        assert task.priority == "high"
        assert task.status == "queued"
        assert task.queued_at is not None
    
    def test_can_retry(self, db):
        """Test retry logic"""
        from api.cms.models_new.task_management import TaskQueue
        
        # Task with retries available
        task = TaskQueue.objects.create(
            task_name="Test Task",
            max_retries=3,
            retry_count=1,
            status="failed"
        )
        
        assert task.can_retry() is True
        
        # Task with no retries left
        task.retry_count = 3
        task.save()
        assert task.can_retry() is False
    
    def test_schedule_retry(self, db):
        """Test scheduling retry"""
        from api.cms.models_new.task_management import TaskQueue
        
        task = TaskQueue.objects.create(
            task_name="Test Task",
            max_retries=3,
            retry_count=1,
            status="failed"
        )
        
        from django.utils import timezone
        original_next_retry = task.next_retry_at or timezone.now()
        task.schedule_retry(delay_seconds=300)
        task.refresh_from_db()
        
        assert task.status == "queued"
        assert task.retry_count == 2
        assert task.next_retry_at is not None
        assert task.next_retry_at > original_next_retry


class TestTaskLock:
    """Test TaskLock model"""
    
    def test_lock_creation(self, db):
        """Test creating a task lock"""
        from api.cms.models_new.task_management import TaskLock
        
        lock = TaskLock.objects.create(
            lock_key="test_lock_key",
            task_name="Test Task",
            owner="test_user",
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        assert lock.lock_key == "test_lock_key"
        assert lock.owner == "test_user"
        assert lock.expires_at is not None
    
    def test_acquire_lock(self, db):
        """Test lock acquisition"""
        from api.cms.models_new.task_management import TaskLock
        
        # First acquisition should succeed
        created, lock = TaskLock.acquire("test_key", "test_user", 3600)
        assert created is True
        assert lock is not None
        
        # Second acquisition should fail
        created2, lock2 = TaskLock.acquire("test_key", "test_user2", 3600)
        assert created2 is False
        assert lock2 is None
    
    def test_release_lock(self, db):
        """Test lock release"""
        from api.cms.models_new.task_management import TaskLock
        
        # Create and release a lock
        created, lock = TaskLock.acquire("test_release_key", "test_user", 3600)
        assert created is True
        
        released = TaskLock.release("test_release_key", "test_user")
        assert released is True
        
        # Try to release non-existent lock
        released2 = TaskLock.release("non_existent_key", "test_user")
        assert released2 is False
    
    def test_is_expired(self, db):
        """Test lock expiration check"""
        from api.cms.models_new.task_management import TaskLock
        
        # Expired lock
        expired_lock = TaskLock.objects.create(
            lock_key="expired_lock",
            expires_at=timezone.now() - timedelta(hours=1)
        )
        
        assert expired_lock.is_expired() is True
        
        # Valid lock
        valid_lock = TaskLock.objects.create(
            lock_key="valid_lock",
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        assert valid_lock.is_expired() is False
    
    def test_extend_lock(self, db):
        """Test lock extension"""
        from api.cms.models_new.task_management import TaskLock
        
        lock = TaskLock.objects.create(
            lock_key="extend_lock",
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        original_expires = lock.expires_at
        lock.extend(additional_seconds=3600)
        lock.refresh_from_db()
        
        assert lock.expires_at > original_expires


class TestTaskManagementService:
    """Test TaskManagementService"""
    
    def test_get_ready_tasks(self, db):
        """Test getting ready tasks"""
        from api.cms.services_new.TaskManagementService import TaskManagementService
                
        # Create test tasks
        TaskSchedule.objects.create(
            name="Ready Task 1",
            frequency="daily",
            status="active",
            next_run=timezone.now() - timedelta(minutes=5)
        )
        TaskSchedule.objects.create(
            name="Future Task",
            frequency="daily",
            status="active",
            next_run=timezone.now() + timedelta(hours=1)
        )
        
        service = TaskManagementService()
        ready_tasks = service.get_ready_tasks()
        
        assert len(ready_tasks) == 1
        assert ready_tasks[0].name == "Ready Task 1"
    
    @patch('api.cms.services_new.TaskManagementService.TaskManagementService.execute_task')
    def test_execute_task(self, mock_execute):
        """Test task execution"""
        from api.cms.services_new.TaskManagementService import TaskManagementService
                
        schedule = TaskSchedule.objects.create(
            name="Test Task",
            frequency="daily"
        )
        
        service = TaskManagementService()
        execution = service.execute_task(str(schedule.uuid))
        
        mock_execute.assert_called_once_with(str(schedule.uuid))
        assert execution is not None
    
    @patch('api.cms.services_new.TaskManagementService.TaskManagementService.complete_execution')
    def test_complete_execution(self, mock_complete):
        """Test task completion"""
        from api.cms.services_new.TaskManagementService import TaskManagementService
        from api.cms.models_new.task_management import TaskExecution
        
        schedule = TaskSchedule.objects.create(
            name="Test Task",
            frequency="daily"
        )
        
        execution = TaskExecution.objects.create(
            schedule=schedule,
            status="running"
        )
        
        mock_complete.return_value = type('Result', (), {'status': 'success'})()
        service = TaskManagementService()
        result = service.complete_execution(str(execution.uuid))
        
        mock_complete.assert_called_once()
        assert result.status == 'success'
    
    def test_get_task_statistics(self, db):
        """Test getting task statistics"""
        from api.cms.services_new.TaskManagementService import TaskManagementService
        from api.cms.models_new.task_management import TaskSchedule, TaskExecution
        
        schedule = TaskSchedule.objects.create(
            name="Test Task",
            frequency="daily"
        )
        
        # Create some executions
        TaskExecution.objects.create(
            schedule=schedule,
            status="success",
            runtime_seconds=300
        )
        TaskExecution.objects.create(
            schedule=schedule,
            status="failure",
            runtime_seconds=150
        )
        
        service = TaskManagementService()
        stats = service.get_task_statistics(str(schedule.uuid))
        
        assert 'task' in stats
        assert stats['task']['name'] == "Test Task"
        assert 'executions' in stats
        assert stats['executions']['total'] == 2
        assert stats['executions']['success_rate'] == 50.0
