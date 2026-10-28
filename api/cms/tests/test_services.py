import unittest
# cms/tests/test_services.py
"""Test cases for CMS services."""
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
from api.cms.models_new.survey_rewards import RewardTransaction as Transaction, RewardPool
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock

User = get_user_model()


class TestUserService(TestCase):
    """Test user service."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_get_user_profile(self):
        """Test getting user profile."""
        from api.cms.services import UserService
        
        profile = UserService.get_user_profile(self.user.id)
        self.assertIsNotNone(profile)
        self.assertEqual(profile.user, self.user)
    
    def test_update_user_profile(self):
        """Test updating user profile."""
        from api.cms.services import UserService
        
        profile_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'bio': 'Updated bio'
        }
        
        updated_profile = UserService.update_user_profile(self.user.id, profile_data)
        self.assertIsNotNone(updated_profile)
        self.assertEqual(updated_profile.first_name, 'John')
        self.assertEqual(updated_profile.last_name, 'Doe')
        self.assertEqual(updated_profile.bio, 'Updated bio')
    
    def test_user_not_found(self):
        """Test user not found scenario."""
        from api.cms.services import UserService
        
        profile = UserService.get_user_profile(99999)
        self.assertIsNone(profile)


class TestSurveyService(TestCase):
    """Test survey service."""
    
    def setUp(self):
        """Set up test data."""
        from api.cms.models_new.survey import Survey
        self.survey = Survey.objects.create(
            title='Test Survey',
            description='Test Description',
            reward_amount=Decimal('10.00'),
            is_active=True
        )
    
    def test_get_available_surveys(self):
        """Test getting available surveys."""
        from api.cms.services import SurveyService
        
        surveys = SurveyService.get_available_surveys()
        self.assertGreaterEqual(len(surveys), 1)
        self.assertIn(self.survey, surveys)
    
    def test_complete_survey(self):
        """Test completing a survey."""
        from api.cms.services import SurveyService
        from api.cms.models_new.survey import SurveyCompletion
        
        completion = SurveyService.complete_survey(
            user_id=self.user.id,
            survey_id=self.survey.id
        )
        
        self.assertIsNotNone(completion)
        self.assertEqual(completion.user, self.user)
        self.assertEqual(completion.survey, self.survey)
        self.assertEqual(completion.status, 'completed')
    
    def test_survey_already_completed(self):
        """Test survey already completed."""
        from api.cms.services import SurveyService
        from api.cms.models_new.survey import SurveyCompletion
        
        # Complete survey first
        SurveyService.complete_survey(
            user_id=self.user.id,
            survey_id=self.survey.id
        )
        
        # Try to complete again
        with self.assertRaises(Exception):
            SurveyService.complete_survey(
                user_id=self.user.id,
                survey_id=self.survey.id
            )


class TestRewardService(TestCase):
    """Test reward service."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='rewarduser',
            email='reward@example.com',
            password='testpass123'
        )
    
    def test_earn_reward(self):
        """Test earning rewards."""
        from api.cms.services import RewardService
        from api.cms.models_new.rewards import RewardTransaction
        
        reward = RewardService.earn_reward(
            user_id=self.user.id,
            amount=Decimal('15.00'),
            source='survey_completion',
            reference_id='test_ref'
        )
        
        self.assertIsNotNone(reward)
        self.assertEqual(reward.user, self.user)
        self.assertEqual(reward.amount, Decimal('15.00'))
        self.assertEqual(reward.transaction_type, 'earned')
        self.assertEqual(reward.status, 'completed')
    
    def test_withdraw_reward(self):
        """Test withdrawing rewards."""
        from api.cms.services import RewardService
        from api.cms.models_new.rewards import RewardTransaction
        
        # First earn some rewards
        RewardService.earn_reward(
            user_id=self.user.id,
            amount=Decimal('50.00'),
            source='survey_completion'
        )
        
        withdrawal = RewardService.withdraw_reward(
            user_id=self.user.id,
            amount=Decimal('25.00'),
            method='paypal',
            withdrawal_address='test@example.com'
        )
        
        self.assertIsNotNone(withdrawal)
        self.assertEqual(withdrawal.user, self.user)
        self.assertEqual(withdrawal.amount, Decimal('25.00'))
        self.assertEqual(withdrawal.transaction_type, 'withdrawal')
        self.assertEqual(withdrawal.status, 'pending')
    
    def test_insufficient_balance(self):
        """Test insufficient balance scenario."""
        from api.cms.services import RewardService
        
        with self.assertRaises(Exception):
            RewardService.withdraw_reward(
                user_id=self.user.id,
                amount=Decimal('100.00'),
                method='paypal',
                withdrawal_address='test@example.com'
            )


class TestTaskService(TestCase):
    """Test task service."""
    
    def setUp(self):
        """Set up test data."""
        from api.cms.models_new.tasks import TaskSchedule
        self.task = TaskSchedule.objects.create(
            name='Test Task',
            description='Test task description',
            schedule_type='daily',
            is_active=True
        )
    
    def test_create_task(self):
        """Test creating a task."""
        from api.cms.services import TaskService
        
        task_data = {
            'name': 'New Task',
            'description': 'New task description',
            'schedule_type': 'weekly',
            'is_active': True
        }
        
        new_task = TaskService.create_task(task_data)
        self.assertIsNotNone(new_task)
        self.assertEqual(new_task.name, 'New Task')
        self.assertEqual(new_task.schedule_type, 'weekly')
        self.assertTrue(new_task.is_active)
    
    def test_execute_task(self):
        """Test executing a task."""
        from api.cms.services import TaskService
        from api.cms.models_new.tasks import TaskExecution
        
        execution = TaskService.execute_task(self.task.id)
        self.assertIsNotNone(execution)
        self.assertEqual(execution.task, self.task)
        self.assertEqual(execution.status, 'running')
    
    def test_task_not_found(self):
        """Test task not found scenario."""
        from api.cms.services import TaskService
        
        with self.assertRaises(Exception):
            TaskService.execute_task(99999)


@pytest.mark.django_db
class TestServiceIntegration(unittest.TestCase):
    """Test service integration."""
    
    def test_survey_completion_reward_flow(self):
        """Test complete survey -> reward flow via SurveyService."""
        from api.cms.services import SurveyService
        from api.cms.models_new.profile_surveys import SurveyTemplate, SurveyCompletion, SurveyCategory
        from django.contrib.auth import get_user_model
        _User = get_user_model()

        user = _User.objects.create_user(
            username='integrationuser2',
            email='integration2@example.com',
            password='testpass123',
            is_active=True,
        )
        cat, _ = SurveyCategory.objects.get_or_create(
            name='IntSvcCat', defaults={'slug': 'intsvccat'}
        )
        survey = SurveyTemplate.objects.create(
            title='Integration Test Survey', category=cat, status='active',
            base_reward=Decimal('20.00'),
        )

        # complete_survey accepts user object
        completion = SurveyService.complete_survey(user, survey.id)
        self.assertIsNotNone(completion)
        self.assertEqual(completion.status, 'completed')
    
    @patch('cms.monitoring.CMSMetrics.increment')
    def test_service_metrics_recording(self, mock_increment):
        """Test service metrics recording."""
        from api.cms.services import SurveyService
        
        # Call a service method
        SurveyService.get_available_surveys()
        
        # Check if metrics were recorded
        mock_increment.assert_called()
    
    def test_service_error_handling(self):
        """Test service error handling."""
        from api.cms.services import UserService
        
        # Test with invalid user ID
        with self.assertRaises(Exception):
            UserService.get_user_profile(-1)
    
    def test_service_transaction_rollback(self):
        """Test service transaction rollback on error."""
        from api.cms.services import RewardService
        
        user = User.objects.create_user(
            username='transactionuser',
            email='transaction@example.com',
            password='testpass123'
        )
        
        # Attempt to earn reward with invalid amount
        with self.assertRaises(Exception):
            RewardService.earn_reward(
                user_id=user.id,
                amount=Decimal('-10.00'),  # Negative amount
                source='test'
            )
        
        # Verify no reward was created
        from api.cms.models_new.rewards import RewardTransaction
        rewards = RewardTransaction.objects.filter(user=user)
        self.assertEqual(len(rewards), 0)


class TestServicePerformance(TestCase):
    """Test service performance."""
    
    def test_large_dataset_handling(self):
        """Test handling large datasets."""
        from api.cms.services import SurveyService
        from api.cms.models_new.survey import Survey
        
        # Create multiple surveys
        for i in range(100):
            Survey.objects.create(
                title=f'Performance Test Survey {i}',
                description=f'Performance test description {i}',
                reward_amount=Decimal('5.00'),
                is_active=True
            )
        
        # Test getting all surveys
        surveys = SurveyService.get_available_surveys()
        self.assertEqual(len(surveys), 100)
    
    def test_concurrent_operations(self):
        """Test concurrent operations."""
        import threading
        from api.cms.services import UserService
        
        user = User.objects.create_user(
            username='concurrentuser',
            email='concurrent@example.com',
            password='testpass123'
        )
        
        def update_profile():
            from api.cms.services import UserService
            UserService.update_user_profile(user.id, {'bio': f'Updated at {timezone.now()}'})
        
        # Create multiple threads updating the same profile
        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_profile)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify profile was updated (last update wins)
        profile = UserService.get_user_profile(user.id)
        self.assertIsNotNone(profile)
        self.assertIsNotNone(profile.bio)
