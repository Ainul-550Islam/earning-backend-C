# api/cms/tests/test_survey_models.py
"""Tests for survey system models."""
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
from datetime import datetime, timedelta, date
from django.utils import timezone

from api.cms.models_new.profile_surveys import (
    SurveyCategory, SurveyTemplate, SurveyQuestion, SurveyCompletion, SurveyResponse
)
from api.cms.models_new.user_profile import UserProfile, UserSegment
from api.cms.models_new.survey_rewards import SurveyReward, RewardTransaction, RewardPool


@pytest.fixture
def survey_category(db):
    """Create a survey category for testing."""
    return SurveyCategory.objects.create(
        name="Test Category",
        slug="test-category",
        description="Test category description",
        icon="test-icon",
        order=1
    )


@pytest.fixture
def survey_template(db, survey_category):
    """Create a survey template for testing."""
    return SurveyTemplate.objects.create(
        title="Test Survey",
        description="Test survey description",
        category=survey_category,
        survey_type="profile",
        status="active",
        estimated_minutes=10,
        base_reward=Decimal("5.00"),
        bonus_reward=Decimal("2.00"),
        min_age=18,
        max_age=65,
        target_countries=["US", "CA"],
        target_genders=["male", "female"],
        target_interests=["technology", "gaming"]
    )


@pytest.fixture
def survey_question(db, survey_template):
    """Create a survey question for testing."""
    return SurveyQuestion.objects.create(
        survey=survey_template,
        question_text="What is your favorite color?",
        question_type="single_choice",
        is_required=True,
        order=1,
        choices=["Red", "Blue", "Green", "Yellow"]
    )


@pytest.fixture
def user_profile(db, user):
    """Create or update a user profile for testing."""
    obj, _ = UserProfile.objects.update_or_create(
        user=user,
        defaults={
            'date_of_birth': date(1990, 1, 1),
            'gender': 'male',
            'education': 'bachelor',
            'income_level': '50k_75k',
            'interests': ['technology', 'gaming'],
            'primary_language': 'en',
            'country': 'US',
        }
    )
    return obj

@pytest.fixture
def user_segment(db):
    """Create a user segment for testing."""
    seg, _ = UserSegment.objects.get_or_create(
        name="Test Segment",
        defaults={
            "description": "Test segment description",
            "min_age": 18,
            "max_age": 65,
            "countries": ["US", "CA"],
            "interests": ["technology"],
        }
    )
    return seg


@pytest.fixture
def survey_reward(db, survey_template, virtual_currency):
    """Create a survey reward for testing."""
    return SurveyReward.objects.create(
        survey=survey_template,
        name="Standard Reward",
        description="Standard reward for completion",
        reward_type="tiered",
        base_amount=Decimal("5.00"),
        currency=virtual_currency,
        min_quality_for_bonus=Decimal("0.8"),
        bonus_amount=Decimal("2.00")
    )


@pytest.fixture
def reward_pool(db, virtual_currency):
    """Create a reward pool for testing."""
    return RewardPool.objects.create(
        name="Test Pool",
        description="Test reward pool",
        total_budget=Decimal("1000.00"),
        currency=virtual_currency,
        auto_refill=True,
        refill_amount=Decimal("500.00"),
        refill_threshold=Decimal("100.00")
    )


class TestSurveyCategory:
    """Test SurveyCategory model."""
    
    def test_category_creation(self, survey_category):
        """Test creating a survey category."""
        assert survey_category.name == "Test Category"
        assert survey_category.slug == "test-category"
        assert survey_category.is_active is True
        assert survey_category.order == 1
    
    def test_category_str(self, survey_category):
        """Test category string representation."""
        assert str(survey_category) == "Test Category"
    
    def test_category_ordering(self, db):
        """Test categories are ordered correctly."""
        cat1 = SurveyCategory.objects.create(name="C", slug="c", order=3)
        cat2 = SurveyCategory.objects.create(name="A", slug="a", order=1)
        cat3 = SurveyCategory.objects.create(name="B", slug="b", order=2)
        
        categories = list(SurveyCategory.objects.all())
        assert categories[0].name == "A"
        assert categories[1].name == "B"
        assert categories[2].name == "C"


class TestSurveyTemplate:
    """Test SurveyTemplate model."""
    
    def test_template_creation(self, survey_template):
        """Test creating a survey template."""
        assert survey_template.title == "Test Survey"
        assert survey_template.survey_type == "profile"
        assert survey_template.status == "active"
        assert survey_template.estimated_minutes == 10
        assert survey_template.base_reward == Decimal("5.00")
    
    def test_template_str(self, survey_template):
        """Test template string representation."""
        assert str(survey_template) == "Test Survey (Active)"
    
    def test_is_active_for_user(self, survey_template, user_profile):
        """Test checking if survey is active for user."""
        assert survey_template.is_active_for_user(user_profile.user) is True
    
    def test_matches_user_profile(self, survey_template, user_profile):
        """Test user profile matching."""
        assert survey_template.matches_user_profile(user_profile.user) is True
    
    def test_age_matching(self, survey_template, user, db):
        """Test age-based matching."""
        # User within age range
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={'date_of_birth': date(1990, 1, 1), 'country': 'US'}
        )
        
        # User too young
        profile.date_of_birth = date(2010, 1, 1)  # 13 years old
        profile.save()
        assert survey_template.matches_user_profile(profile.user) is False
        
        # User too old
        profile.date_of_birth = date(1950, 1, 1)  # 73 years old
        profile.save()
        assert survey_template.matches_user_profile(profile.user) is False
    
    def test_country_matching(self, survey_template, user, db):
        """Test country-based matching."""
        # Ensure profile with country in target list
        profile, _ = UserProfile.objects.update_or_create(
            user=user, defaults={'country': 'US', 'date_of_birth': __import__('datetime').date(1990,1,1)}
        )
        profile.refresh_from_db()
        assert profile.country == 'US', f"Country should be US but is '{profile.country}'"
        assert survey_template.matches_user_profile(profile.user) is True,             f"Should match user with country=US; target_countries={survey_template.target_countries}"

        # User not in target country
        profile.country = 'UK'
        profile.save(update_fields=['country'])
        profile.refresh_from_db()
        assert survey_template.matches_user_profile(profile.user) is False
    
    def test_get_completion_rate(self, survey_template, user, db):
        """Test completion rate calculation."""
        # Create some completions
        from api.cms.factories import UserFactory
        user2 = UserFactory.create()
        
        SurveyCompletion.objects.create(survey=survey_template, user=user, status='approved')
        SurveyCompletion.objects.create(survey=survey_template, user=user2, status='rejected')
        SurveyCompletion.objects.create(survey=survey_template, user=user2, status='completed')
        
        completion_rate = survey_template.get_completion_rate()
        assert completion_rate == Decimal('33.33')  # 1 approved out of 3 total
    
    def test_get_daily_completions(self, survey_template, user, db):
        """Test daily completion count."""
        SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            status='approved',
            completed_at=timezone.now()
        )
        
        daily_count = survey_template.get_daily_completions()
        assert daily_count == 1


class TestSurveyQuestion:
    """Test SurveyQuestion model."""
    
    def test_question_creation(self, survey_question):
        """Test creating a survey question."""
        assert survey_question.question_text == "What is your favorite color?"
        assert survey_question.question_type == "single_choice"
        assert survey_question.is_required is True
        assert survey_question.order == 1
        assert "Red" in survey_question.choices
    
    def test_question_str(self, survey_question):
        """Test question string representation."""
        expected = f"{survey_question.survey.title} - Q{survey_question.order + 1}"
        assert str(survey_question) == expected


class TestSurveyCompletion:
    """Test SurveyCompletion model."""
    
    def test_completion_creation(self, survey_template, user):
        """Test creating a survey completion."""
        completion = SurveyCompletion.objects.create(
            survey=survey_template,
            user=user
        )
        
        assert completion.survey == survey_template
        assert completion.user == user
        assert completion.status == 'started'
        assert completion.started_at is not None
    
    def test_completion_str(self, survey_template, user):
        """Test completion string representation."""
        completion = SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            status='approved'
        )
        expected = f"{user.username} - {survey_template.title} (Approved)"
        assert str(completion) == expected
    
    def test_calculate_reward(self, survey_template, user):
        """Test reward calculation."""
        completion = SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            quality_score=Decimal("0.9")
        )
        
        reward = completion.calculate_reward()
        expected = survey_template.base_reward + survey_template.bonus_reward  # 5.00 + 2.00 = 7.00
        assert reward == expected
    
    def test_calculate_reward_with_penalties(self, survey_template, user):
        """Test reward calculation with quality penalties."""
        completion = SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            quality_score=Decimal("0.6"),
            flagged_for_speeding=True,
            failed_attention_checks=2
        )
        
        reward = completion.calculate_reward()
        # Base reward (5.00) * 0.5 (speeding penalty) * 0.8 (attention check penalty) = 2.00
        expected = Decimal("2.00")
        assert reward == expected
    
    def test_complete_survey(self, survey_template, survey_question, user):
        """Test completing a survey with responses."""
        completion = SurveyCompletion.objects.create(
            survey=survey_template,
            user=user
        )
        
        responses = {
            str(survey_question.uuid): "Red"
        }
        
        completion.complete_survey(responses, Decimal("0.9"))
        
        completion.refresh_from_db()
        assert completion.status == 'completed'
        assert completion.completed_at is not None
        assert completion.quality_score == Decimal("0.9")
        assert completion.total_reward_earned > 0
        
        # Check response was created
        assert SurveyResponse.objects.filter(
            completion=completion,
            question=survey_question
        ).exists()


class TestSurveyResponse:
    """Test SurveyResponse model."""
    
    def test_response_creation(self, survey_completion, survey_question):
        """Test creating a survey response."""
        response = SurveyResponse.objects.create(
            completion=survey_completion,
            question=survey_question,
            answer="Red",
            answer_text="Red"
        )
        
        assert response.completion == survey_completion
        assert response.question == survey_question
        assert response.answer == "Red"
        assert response.answer_text == "Red"
    
    def test_response_str(self, survey_completion, survey_question):
        """Test response string representation."""
        response = SurveyResponse.objects.create(
            completion=survey_completion,
            question=survey_question,
            answer="Red"
        )
        
        expected = f"{survey_completion.user.username} - {survey_question.question_text[:50]}"
        assert str(response) == expected


class TestUserProfile:
    """Test UserProfile model."""
    
    def test_profile_creation(self, user_profile):
        """Test creating a user profile."""
        assert user_profile.user is not None
        assert user_profile.gender == "male"
        assert user_profile.country == "US"
        assert user_profile.education == "bachelor"
        assert "technology" in user_profile.interests
    
    def test_profile_str(self, user_profile):
        """Test profile string representation."""
        assert str(user_profile) == f"{user_profile.user.username} Profile"
    
    def test_age_calculation(self, user_profile):
        """Test age calculation from date of birth."""
        # This will depend on current date, so we check it's reasonable
        age = user_profile.age
        assert age is not None
        assert 30 <= age <= 40  # Reasonable range for someone born in 1990
    
    def test_profile_completeness(self, user_profile):
        """Test profile completeness calculation."""
        completeness = user_profile.calculate_profile_completeness()
        assert completeness > 0
        assert completeness <= 100
    
    def test_get_survey_preferences(self, user_profile):
        """Test getting survey preferences."""
        preferences = user_profile.get_survey_preferences()
        
        assert 'age' in preferences
        assert 'gender' in preferences
        assert 'country' in preferences
        assert 'interests' in preferences
        assert 'languages' in preferences
    
    def test_update_survey_stats(self, user_profile):
        """Test updating survey statistics."""
        initial_score = user_profile.survey_participation_score
        initial_quality = user_profile.quality_score
        
        user_profile.update_survey_stats(
            completion_time=300,
            quality_score=Decimal("0.9")
        )
        
        user_profile.refresh_from_db()
        assert user_profile.survey_participation_score > initial_score
        assert user_profile.quality_score >= initial_quality


class TestUserSegment:
    """Test UserSegment model."""
    
    def test_segment_creation(self, user_segment):
        """Test creating a user segment."""
        assert user_segment.name == "Test Segment"
        assert user_segment.min_age == 18
        assert user_segment.max_age == 65
        assert "US" in user_segment.countries
        assert "technology" in user_segment.interests
    
    def test_segment_str(self, user_segment):
        """Test segment string representation."""
        assert str(user_segment) == "Test Segment"
    
    def test_get_matching_users(self, user_segment, user, db):
        """Test getting matching users for a segment."""
        # Ensure user is active
        user.is_active = True
        user.save(update_fields=['is_active'])
        # Create a matching profile
        profile, _ = UserProfile.objects.update_or_create(
            user=user,
            defaults={'date_of_birth': date(1990, 1, 1), 'country': 'US', 'interests': ['technology', 'gaming']}
        )
        
        matching_users = user_segment.get_matching_users()
        assert profile in matching_users
        
        # Update user count
        user_segment.update_user_count()
        user_segment.refresh_from_db()
        assert user_segment.user_count >= 1


class TestSurveyReward:
    """Test SurveyReward model."""
    
    def test_reward_creation(self, survey_reward):
        """Test creating a survey reward."""
        assert survey_reward.survey is not None
        assert survey_reward.name == "Standard Reward"
        assert survey_reward.reward_type == "tiered"
        assert survey_reward.base_amount == Decimal("5.00")
        assert survey_reward.bonus_amount == Decimal("2.00")
    
    def test_reward_str(self, survey_reward):
        """Test reward string representation."""
        expected = f"{survey_reward.survey.title} - {survey_reward.name}"
        assert str(survey_reward) == expected
    
    def test_is_active(self, survey_reward):
        """Test checking if reward is active."""
        assert survey_reward.is_active() is True
        
        # Deactivate it
        survey_reward.status = 'inactive'
        survey_reward.save()
        assert survey_reward.is_active() is False
    
    def test_calculate_reward(self, survey_reward, survey_template, user):
        """Test reward calculation for a completion."""
        completion = SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            quality_score=Decimal("0.9")
        )
        
        reward_amount = survey_reward.calculate_reward(completion)
        expected = survey_reward.base_amount + survey_reward.bonus_amount
        assert reward_amount == expected
    
    def test_calculate_reward_no_bonus(self, survey_reward, survey_template, user):
        """Test reward calculation without bonus."""
        completion = SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            quality_score=Decimal("0.7")  # Below bonus threshold
        )
        
        reward_amount = survey_reward.calculate_reward(completion)
        expected = survey_reward.base_amount
        assert reward_amount == expected


class TestRewardTransaction:
    """Test RewardTransaction model."""
    
    def test_transaction_creation(self, survey_completion, survey_reward):
        """Test creating a reward transaction."""
        transaction = RewardTransaction.objects.create(
            user=survey_completion.user,
            survey_completion=survey_completion,
            reward_config=survey_reward,
            transaction_type='earned',
            amount=Decimal("5.00"),
            description="Test reward"
        )
        
        assert transaction.user == survey_completion.user
        assert transaction.survey_completion == survey_completion
        assert transaction.reward_config == survey_reward
        assert transaction.transaction_type == 'earned'
        assert transaction.amount == Decimal("5.00")
    
    def test_transaction_str(self, survey_completion, survey_reward):
        """Test transaction string representation."""
        transaction = RewardTransaction.objects.create(
            user=survey_completion.user,
            survey_completion=survey_completion,
            reward_config=survey_reward,
            transaction_type='earned',
            amount=Decimal("5.00")
        )
        
        expected = f"{survey_completion.user.username} - earned - 5.00"
        assert str(transaction) == expected
    
    def test_approve_transaction(self, survey_completion, survey_reward):
        """Test approving a transaction."""
        transaction = RewardTransaction.objects.create(
            user=survey_completion.user,
            survey_completion=survey_completion,
            reward_config=survey_reward,
            transaction_type='earned',
            amount=Decimal("5.00")
        )
        
        assert transaction.status == 'pending'
        
        transaction.approve()
        transaction.refresh_from_db()
        
        assert transaction.status == 'approved'
        assert transaction.processed_at is not None


class TestRewardPool:
    """Test RewardPool model."""
    
    def test_pool_creation(self, reward_pool):
        """Test creating a reward pool."""
        assert reward_pool.name == "Test Pool"
        assert reward_pool.total_budget == Decimal("1000.00")
        assert reward_pool.auto_refill is True
        assert reward_pool.refill_amount == Decimal("500.00")
    
    def test_pool_str(self, reward_pool):
        """Test pool string representation."""
        expected = f"Test Pool ({reward_pool.currency})"
        assert str(reward_pool) == expected
    
    def test_remaining_budget(self, reward_pool):
        """Test remaining budget calculation."""
        remaining = reward_pool.remaining_budget
        expected = reward_pool.total_budget - reward_pool.allocated_amount
        assert remaining == expected
    
    def test_allocate_funds(self, reward_pool):
        """Test allocating funds from pool."""
        success = reward_pool.allocate_funds(Decimal("100.00"))
        assert success is True
        
        reward_pool.refresh_from_db()
        assert reward_pool.allocated_amount == Decimal("100.00")
    
    def test_allocate_insufficient_funds(self, reward_pool):
        """Test allocating more funds than available."""
        success = reward_pool.allocate_funds(Decimal("2000.00"))
        assert success is False
        
        reward_pool.refresh_from_db()
        assert reward_pool.allocated_amount == Decimal("0.00")
    
    def test_release_funds(self, reward_pool):
        """Test releasing allocated funds."""
        # First allocate some funds
        reward_pool.allocate_funds(Decimal("100.00"))
        reward_pool.refresh_from_db()
        
        # Then release them
        reward_pool.release_funds(Decimal("50.00"))
        reward_pool.refresh_from_db()
        
        assert reward_pool.allocated_amount == Decimal("50.00")
    
    def test_mark_paid(self, reward_pool):
        """Test marking funds as paid."""
        # First allocate funds
        reward_pool.allocate_funds(Decimal("100.00"))
        reward_pool.refresh_from_db()
        
        # Then mark as paid
        reward_pool.mark_paid(Decimal("30.00"))
        reward_pool.refresh_from_db()
        
        assert reward_pool.paid_amount == Decimal("30.00")
        assert reward_pool.allocated_amount == Decimal("70.00")
    
    def test_auto_refill(self, reward_pool):
        """Test automatic refill functionality."""
        # Set up for refill
        reward_pool.allocated_amount = Decimal("950.00")  # Above threshold
        reward_pool.save()
        
        # Trigger refill check
        reward_pool.mark_paid(Decimal("100.00"))  # This should trigger refill
        
        reward_pool.refresh_from_db()
        assert reward_pool.total_budget == Decimal("1500.00")  # 1000 + 500 refill
