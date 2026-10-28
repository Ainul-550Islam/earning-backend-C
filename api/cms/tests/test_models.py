# cms/tests/test_models.py
"""Test cases for CMS models."""
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

User = get_user_model()


class TestUserModels(TestCase):
    """Test user-related models."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_user_creation(self):
        """Test user creation."""
        self.assertEqual(self.user.username, 'testuser')
        self.assertEqual(self.user.email, 'test@example.com')
        self.assertTrue(self.user.check_password('testpass123'))
    
    def test_user_str_representation(self):
        """Test user string representation."""
        self.assertEqual(str(self.user), 'testuser')


class TestSurveyModels(TestCase):
    """Test survey-related models."""
    
    def setUp(self):
        """Set up test data."""
        from api.cms.models_new.survey import Survey
        self.survey = Survey.objects.create(
            title='Test Survey',
            description='Test Description',
            reward_amount=Decimal('10.00'),
            is_active=True
        )
    
    def test_survey_creation(self):
        """Test survey creation."""
        self.assertEqual(self.survey.title, 'Test Survey')
        self.assertEqual(self.survey.reward_amount, Decimal('10.00'))
        self.assertTrue(self.survey.is_active)
    
    def test_survey_str_representation(self):
        """Test survey string representation."""
        # __str__ includes status display: 'Title (Status)'
        self.assertIn('Test Survey', str(self.survey))


class TestRewardModels(TestCase):
    """Test reward-related models."""
    
    def setUp(self):
        """Set up test data."""
        from api.cms.models_new.rewards import RewardTransaction
        self.user = User.objects.create_user(
            username='rewarduser',
            email='reward@example.com',
            password='testpass123'
        )
        self.transaction = RewardTransaction.objects.create(
            user=self.user,
            amount=Decimal('5.00'),
            transaction_type='earned',
            status='completed'
        )
    
    def test_reward_transaction_creation(self):
        """Test reward transaction creation."""
        self.assertEqual(self.transaction.user, self.user)
        self.assertEqual(self.transaction.amount, Decimal('5.00'))
        self.assertEqual(self.transaction.transaction_type, 'earned')
        self.assertEqual(self.transaction.status, 'completed')
    
    def test_reward_transaction_str_representation(self):
        """Test reward transaction string representation."""
        expected = f"{self.user.username} - earned - 5.00"
        self.assertEqual(str(self.transaction), expected)


class TestTaskModels(TestCase):
    """Test task-related models."""
    
    def setUp(self):
        """Set up test data."""
        from api.cms.models_new.tasks import TaskSchedule
        self.task = TaskSchedule.objects.create(
            name='Test Task',
            description='Test task description',
            schedule_type='daily',
            is_active=True
        )
    
    def test_task_creation(self):
        """Test task creation."""
        self.assertEqual(self.task.name, 'Test Task')
        self.assertEqual(self.task.schedule_type, 'daily')
        self.assertTrue(self.task.is_active)
    
    def test_task_str_representation(self):
        """Test task string representation."""
        self.assertEqual(str(self.task), 'Test Task')


@pytest.mark.django_db
class TestModelIntegration:
    """Test model integration and relationships."""
    
    def test_user_survey_completion_relationship(self, db):
        """Test user survey completion relationship."""
        from api.cms.models_new.profile_surveys import SurveyTemplate as Survey, SurveyCompletion
        from api.cms.models_new.profile_surveys import SurveyCategory
        from api.cms.models_new.survey_rewards import RewardTransaction
        from django.contrib.auth import get_user_model
        _User = get_user_model()

        user = _User.objects.create_user(
            username="completionuser3",
            email="completion3@example.com",
            password="testpass123",
            is_active=True,
        )
        cat, _ = SurveyCategory.objects.get_or_create(
            name="IntegrationCat", defaults={"slug": "integration-cat"}
        )
        survey = Survey.objects.create(
            title="Completion Test Survey",
            category=cat,
            status="active",
            base_reward=Decimal("15.00"),
        )
        completion = SurveyCompletion.objects.create(
            user=user,
            survey=survey,
            status="completed",
            completed_at=timezone.now(),
        )
        # Verify the completion exists and is linked
        assert completion.pk is not None
        assert SurveyCompletion.objects.filter(user=user, survey=survey).exists()
    
    def test_cascade_deletion(self, db):
        """Test cascade deletion behavior."""
        import pytest
        from api.cms.models_new.profile_surveys import SurveyTemplate as Survey, SurveyCompletion
        from api.cms.models_new.profile_surveys import SurveyCategory
        
        from django.contrib.auth import get_user_model
        _User = get_user_model()
        user = _User.objects.create_user(
            username="cascadeuser2",
            email="cascade2@example.com",
            password="testpass123",
            is_active=True,
        )
        cat = SurveyCategory.objects.create(name="CascadeCat", slug="cascade-cat")
        survey = Survey.objects.create(
            title="Cascade Test Survey",
            category=cat,
            status="active",
        )
        completion = SurveyCompletion.objects.create(
            user=user,
            survey=survey,
            status="completed",
        )
        survey.delete()
        with pytest.raises(SurveyCompletion.DoesNotExist):
            SurveyCompletion.objects.get(id=completion.id)
