# api/cms/tests/test_reward_management.py
"""Tests for survey reward management models and services"""
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
from api.cms.models_new.survey_rewards import RewardTransaction as Transaction, RewardPool
from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from unittest.mock import patch, MagicMock

from api.cms.models_new.survey_rewards import SurveyReward, RewardTransaction, RewardPool
from api.cms.models_new.profile_surveys import SurveyCompletion, SurveyTemplate
from api.cms.services_new.SurveyRewardService import SurveyRewardService


class TestSurveyReward:
    """Test SurveyReward model"""
    
    def test_reward_creation(self, db, survey_template, virtual_currency):
        """Test creating a survey reward"""
        reward = SurveyReward.objects.create(
            survey=survey_template,
            name="Standard Reward",
            description="Standard reward for completion",
            reward_type="tiered",
            base_amount=Decimal("5.00"),
            currency=virtual_currency,
            min_quality_for_bonus=Decimal("0.8"),
            bonus_amount=Decimal("2.00")
        )
        
        assert reward.survey == survey_template
        assert reward.name == "Standard Reward"
        assert reward.reward_type == "tiered"
        assert reward.base_amount == Decimal("5.00")
        assert reward.bonus_amount == Decimal("2.00")
    
    def test_reward_str(self, db, survey_template, virtual_currency):
        """Test reward string representation"""
        reward = SurveyReward.objects.create(
            survey=survey_template,
            name="Test Reward",
            reward_type="fixed"
        )
        
        str_repr = str(reward)
        assert "Test Reward" in str_repr
        assert survey_template.title in str_repr
    
    def test_is_active(self, db, survey_template, virtual_currency):
        """Test checking if reward is active"""
        # Active reward
        reward = SurveyReward.objects.create(
            survey=survey_template,
            name="Active Reward",
            status="active"
        )
        assert reward.is_active() is True
        
        # Inactive reward
        reward.status = "inactive"
        reward.save()
        assert reward.is_active() is False
    
    def test_calculate_reward_tiered(self, db, survey_template, virtual_currency, user):
        """Test reward calculation for tiered rewards"""
        # Create completion with high quality
        completion = SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            quality_score=Decimal("0.9")
        )
        
        reward = SurveyReward.objects.create(
            survey=survey_template,
            reward_type="tiered",
            base_amount=Decimal("5.00"),
            min_quality_for_bonus=Decimal("0.8"),
            bonus_amount=Decimal("2.00")
        )
        
        calculated_reward = reward.calculate_reward(completion)
        expected = Decimal("7.00")  # 5.00 + 2.00 bonus
        assert calculated_reward == expected
    
    def test_calculate_reward_no_bonus(self, db, survey_template, virtual_currency, user):
        """Test reward calculation without bonus"""
        # Create completion with low quality
        completion = SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            quality_score=Decimal("0.7")
        )
        
        reward = SurveyReward.objects.create(
            survey=survey_template,
            reward_type="tiered",
            base_amount=Decimal("5.00"),
            min_quality_for_bonus=Decimal("0.8"),
            bonus_amount=Decimal("2.00")
        )
        
        calculated_reward = reward.calculate_reward(completion)
        expected = Decimal("5.00")  # Base amount only
        assert calculated_reward == expected
    
    def test_calculate_reward_with_penalties(self, db, survey_template, virtual_currency, user):
        """Test reward calculation with penalties"""
        completion = SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            quality_score=Decimal("0.8"),
            flagged_for_speeding=True,
            failed_attention_checks=2
        )
        
        reward = SurveyReward.objects.create(
            survey=survey_template,
            reward_type="tiered",
            base_amount=Decimal("10.00"),
            min_quality_for_bonus=Decimal("0.8"),
            bonus_amount=Decimal("2.00")
        )
        
        calculated_reward = reward.calculate_reward(completion)
        # 10.00 base + 2.00 bonus = 12.00
        # 50% penalty for speeding = 6.00
        # 20% penalty for 2 failed checks = 9.60
        expected = Decimal("9.60")
        assert calculated_reward == expected


class TestRewardTransaction:
    """Test RewardTransaction model"""
    
    def test_transaction_creation(self, db, survey_completion, survey_reward, virtual_currency):
        """Test creating a reward transaction"""
        transaction = RewardTransaction.objects.create(
            user=survey_completion.user,
            survey_completion=survey_completion,
            reward_config=survey_reward,
            transaction_type='earned',
            amount=Decimal("5.00"),
            currency=virtual_currency,
            description="Test reward"
        )
        
        assert transaction.user == survey_completion.user
        assert transaction.survey_completion == survey_completion
        assert transaction.reward_config == survey_reward
        assert transaction.transaction_type == 'earned'
        assert transaction.amount == Decimal("5.00")
    
    def test_transaction_str(self, db, survey_completion, survey_reward):
        """Test transaction string representation"""
        transaction = RewardTransaction.objects.create(
            user=survey_completion.user,
            survey_completion=survey_completion,
            reward_config=survey_reward,
            transaction_type='earned',
            amount=Decimal("5.00")
        )
        
        str_repr = str(transaction)
        assert survey_completion.user.username in str_repr
        assert "earned" in str_repr
        assert "5.00" in str_repr
    
    def test_approve_transaction(self, db, survey_completion, survey_reward, virtual_currency):
        """Test approving a transaction"""
        transaction = RewardTransaction.objects.create(
            user=survey_completion.user,
            survey_completion=survey_completion,
            reward_config=survey_reward,
            transaction_type='earned',
            amount=Decimal("5.00"),
            status='pending'
        )
        
        assert transaction.status == 'pending'
        assert transaction.processed_at is None
        
        transaction.approve()
        transaction.refresh_from_db()
        
        assert transaction.status == 'approved'
        assert transaction.processed_at is not None
    
    def test_mark_paid(self, db, survey_completion, survey_reward, virtual_currency):
        """Test marking transaction as paid"""
        transaction = RewardTransaction.objects.create(
            user=survey_completion.user,
            survey_completion=survey_completion,
            reward_config=survey_reward,
            transaction_type='earned',
            amount=Decimal("5.00"),
            status='approved'
        )
        
        assert transaction.paid_at is None
        
        transaction.mark_paid()
        transaction.refresh_from_db()
        
        assert transaction.status == 'paid'
        assert transaction.paid_at is not None


class TestRewardPool:
    """Test RewardPool model"""
    
    def test_pool_creation(self, db, virtual_currency):
        """Test creating a reward pool"""
        pool = RewardPool.objects.create(
            name="Test Pool",
            description="Test reward pool",
            total_budget=Decimal("1000.00"),
            currency=virtual_currency,
            auto_refill=True,
            refill_amount=Decimal("500.00"),
            refill_threshold=Decimal("100.00")
        )
        
        assert pool.name == "Test Pool"
        assert pool.total_budget == Decimal("1000.00")
        assert pool.auto_refill is True
        assert pool.refill_amount == Decimal("500.00")
    
    def test_pool_str(self, db, virtual_currency):
        """Test pool string representation"""
        pool = RewardPool.objects.create(
            name="Test Pool",
            currency=virtual_currency
        )
        
        str_repr = str(pool)
        assert "Test Pool" in str_repr
        assert virtual_currency.symbol in str_repr
    
    def test_remaining_budget(self, db, virtual_currency):
        """Test remaining budget calculation"""
        pool = RewardPool.objects.create(
            name="Test Pool",
            total_budget=Decimal("1000.00"),
            currency=virtual_currency,
            allocated_amount=Decimal("300.00"),
            paid_amount=Decimal("200.00")
        )
        
        remaining = pool.remaining_budget
        expected = Decimal("700.00")  # 1000 - 300
        assert remaining == expected
    
    def test_available_budget(self, db, virtual_currency):
        """Test available budget calculation"""
        pool = RewardPool.objects.create(
            name="Test Pool",
            total_budget=Decimal("1000.00"),
            currency=virtual_currency,
            allocated_amount=Decimal("300.00"),
            paid_amount=Decimal("200.00")
        )
        
        available = pool.available_budget
        expected = Decimal("500.00")  # 1000 - 300 - 200
        assert available == expected
    
    def test_allocate_funds(self, db, virtual_currency):
        """Test allocating funds from pool"""
        pool = RewardPool.objects.create(
            name="Test Pool",
            total_budget=Decimal("1000.00"),
            currency=virtual_currency
        )
        
        success = pool.allocate_funds(Decimal("200.00"))
        assert success is True
        
        pool.refresh_from_db()
        assert pool.allocated_amount == Decimal("200.00")
    
    def test_allocate_insufficient_funds(self, db, virtual_currency):
        """Test allocating more funds than available"""
        pool = RewardPool.objects.create(
            name="Test Pool",
            total_budget=Decimal("1000.00"),
            currency=virtual_currency,
            allocated_amount=Decimal("900.00"),
            paid_amount=Decimal("200.00")
        )
        
        success = pool.allocate_funds(Decimal("200.00"))
        assert success is False  # Only 100.00 available
    
    def test_mark_paid(self, db, virtual_currency):
        """Test marking funds as paid"""
        pool = RewardPool.objects.create(
            name="Test Pool",
            total_budget=Decimal("1000.00"),
            currency=virtual_currency,
            allocated_amount=Decimal("300.00"),
            paid_amount=Decimal("200.00")
        )
        
        pool.mark_paid(Decimal("100.00"))
        pool.refresh_from_db()
        
        assert pool.paid_amount == Decimal("300.00")  # 200 + 100
        assert pool.allocated_amount == Decimal("200.00")  # 300 - 100


class TestSurveyRewardService:
    """Test SurveyRewardService"""
    
    def test_calculate_reward_tiered_with_bonus(self, db, survey_template, virtual_currency, user):
        """Test reward calculation with tiered bonus"""
        service = SurveyRewardService()
        
        completion = SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            quality_score=Decimal("0.9")
        )
        
        reward_config = SurveyReward.objects.create(
            survey=survey_template,
            reward_type="tiered",
            base_amount=Decimal("5.00"),
            min_quality_for_bonus=Decimal("0.8"),
            bonus_amount=Decimal("2.00")
        )
        
        calculated = service.calculate_reward(completion, reward_config)
        expected = Decimal("7.00")  # 5.00 + 2.00 bonus
        assert calculated == expected
    
    def test_calculate_reward_with_penalties(self, db, survey_template, virtual_currency, user):
        """Test reward calculation with penalties"""
        service = SurveyRewardService()
        
        completion = SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            quality_score=Decimal("0.8"),
            flagged_for_speeding=True,
            failed_attention_checks=1
        )
        
        reward_config = SurveyReward.objects.create(
            survey=survey_template,
            reward_type="tiered",
            base_amount=Decimal("10.00"),
            min_quality_for_bonus=Decimal("0.8"),
            bonus_amount=Decimal("2.00")
        )
        
        calculated = service.calculate_reward(completion, reward_config)
        # 10.00 base + 2.00 bonus = 12.00
        # 50% penalty for speeding = 6.00
        # 10% penalty for 1 failed check = 10.80
        expected = Decimal("10.80")
        assert calculated == expected
    
    def test_create_reward_transaction(self, db, survey_template, virtual_currency, user):
        """Test creating reward transaction"""
        service = SurveyRewardService()
        
        completion = SurveyCompletion.objects.create(
            survey=survey_template,
            user=user
        )
        
        reward_config = SurveyReward.objects.create(
            survey=survey_template,
            reward_type="fixed",
            base_amount=Decimal("5.00")
        )
        
        transaction = service.create_reward_transaction(
            completion, reward_config, Decimal("7.00")
        )
        
        assert transaction.user == user
        assert transaction.survey_completion == completion
        assert transaction.reward_config == reward_config
        assert transaction.amount == Decimal("7.00")
    
    def test_approve_transaction(self, db, survey_completion, survey_reward):
        """Test approving a transaction"""
        service = SurveyRewardService()
        
        transaction = RewardTransaction.objects.create(
            user=survey_completion.user,
            survey_completion=survey_completion,
            reward_config=survey_reward,
            transaction_type='earned',
            amount=Decimal("5.00"),
            status='pending'
        )
        
        approved = service.approve_transaction(str(transaction.uuid))
        assert approved.status == 'approved'
        assert approved.processed_at is not None
    
    def test_get_user_reward_summary(self, db, survey_template, virtual_currency, user):
        """Test getting user reward summary"""
        service = SurveyRewardService()
        
        # Create some transactions
        completion = SurveyCompletion.objects.create(
            survey=survey_template,
            user=user
        )
        
        RewardTransaction.objects.create(
            user=user,
            survey_completion=completion,
            transaction_type='earned',
            amount=Decimal("5.00"),
            status='paid',
            currency=virtual_currency
        )
        
        RewardTransaction.objects.create(
            user=user,
            transaction_type='bonus',
            amount=Decimal("2.00"),
            status='paid',
            currency=virtual_currency
        )
        
        summary = service.get_user_reward_summary(user.id, 30)
        
        assert summary['period_days'] == 30
        assert summary['total_transactions'] == 2
        assert summary['total_amount'] == 7.0
        assert 'by_currency' in summary
        assert 'recent_transactions' in summary
    
    def test_get_reward_pool_utilization(self, db, virtual_currency):
        """Test getting reward pool utilization"""
        service = SurveyRewardService()
        
        pool = RewardPool.objects.create(
            name="Test Pool",
            total_budget=Decimal("1000.00"),
            currency=virtual_currency,
            allocated_amount=Decimal("600.00"),
            paid_amount=Decimal("400.00")
        )
        
        utilization = service.get_reward_pool_utilization(str(pool.uuid))
        
        assert 'pool_info' in utilization
        assert utilization['pool_info']['total_budget'] == 1000.0
        assert utilization['pool_info']['remaining_budget'] == 400.0
        assert utilization['utilization_rate'] == 60.0  # 600/1000 * 100
    
    def test_get_survey_reward_analytics(self, db, survey_template, virtual_currency, user):
        """Test getting survey reward analytics"""
        service = SurveyRewardService()
        
        # Create some transactions
        completion = SurveyCompletion.objects.create(
            survey=survey_template,
            user=user
        )
        
        RewardTransaction.objects.create(
            user=user,
            survey_completion=completion,
            transaction_type='earned',
            amount=Decimal("5.00"),
            status='paid',
            currency=virtual_currency
        )
        
        analytics = service.get_survey_reward_analytics(str(survey_template.uuid), 30)
        
        assert 'survey_info' in analytics
        assert analytics['survey_info']['title'] == survey_template.title
        assert 'reward_summary' in analytics
        assert analytics['reward_summary']['total_transactions'] == 1
        assert 'reward_types' in analytics
        assert 'top_earners' in analytics
    
    def test_get_system_reward_overview(self, db, virtual_currency):
        """Test getting system-wide reward overview"""
        service = SurveyRewardService()
        
        # Create some pools and transactions
        pool1 = RewardPool.objects.create(
            name="Pool 1",
            total_budget=Decimal("1000.00"),
            currency=virtual_currency,
            is_active=True
        )
        
        pool2 = RewardPool.objects.create(
            name="Pool 2",
            total_budget=Decimal("2000.00"),
            currency=virtual_currency,
            is_active=True
        )
        
        overview = service.get_system_reward_overview()
        
        assert 'pools' in overview
        assert overview['pools']['total_pools'] == 2
        assert overview['pools']['total_budget'] == 3000.0
        assert 'transactions' in overview
        assert 'generated_at' in overview
