# api/cms/tests/test_survey_services.py
"""Tests for survey system services."""
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

from api.cms.services_new.ProfileSurveyService import ProfileSurveyManager
from api.cms.services_new.SurveyAnalyticsService import SurveyAnalyticsService
from api.cms.services_new.UserSegmentService import UserSegmentService


class TestProfileSurveyManager:
    """Test ProfileSurveyManager service."""
    
    def test_get_recommended_surveys(self, db, user, survey_template, user_profile):
        """Test getting personalized survey recommendations."""
        manager = ProfileSurveyManager()
        
        # Create a matching survey
        survey_template.status = 'active'
        survey_template.save()
        
        recommendations = manager.get_recommended_surveys(user, limit=5)
        
        assert len(recommendations) >= 1
        assert all('survey' in rec for rec in recommendations)
        assert all('match_score' in rec for rec in recommendations)
        assert all('estimated_reward' in rec for rec in recommendations)
    
    def test_calculate_match_score(self, db, user, survey_template, user_profile):
        """Test calculating survey-user match score."""
        manager = ProfileSurveyManager()
        
        score = manager._calculate_match_score(survey_template, user)
        
        assert 0 <= score <= 100
        assert isinstance(score, float)
    
    def test_start_survey(self, db, user, survey_template, user_profile):
        """Test starting a survey."""
        manager = ProfileSurveyManager()
        
        survey_template.status = 'active'
        survey_template.save()
        
        result = manager.start_survey(user, str(survey_template.uuid))
        
        assert 'completion_uuid' in result
        assert 'survey' in result
        assert result['survey']['title'] == survey_template.title
    
    def test_start_survey_already_started(self, db, user, survey_template, user_profile):
        """Test starting a survey that's already started."""
        manager = ProfileSurveyManager()
        
        survey_template.status = 'active'
        survey_template.save()
        
        # Start it once
        manager.start_survey(user, str(survey_template.uuid))
        
        # Try to start again
        with pytest.raises(ValueError, match="User already started this survey"):
            manager.start_survey(user, str(survey_template.uuid))
    
    def test_submit_survey(self, db, user, survey_template, survey_question, user_profile):
        """Test submitting a completed survey."""
        manager = ProfileSurveyManager()
        
        survey_template.status = 'active'
        survey_template.save()
        
        # Start survey
        start_result = manager.start_survey(user, str(survey_template.uuid))
        completion_uuid = start_result['completion_uuid']
        
        # Submit responses
        responses = {
            str(survey_question.uuid): "Red"
        }
        
        completion = manager.submit_survey(user, completion_uuid, responses)
        
        assert completion.status == 'completed'
        assert completion.completed_at is not None
        assert completion.responses.count() == 1
    
    def test_validate_responses(self, db, survey_template, survey_question):
        """Test response validation."""
        manager = ProfileSurveyManager()
        
        # Valid single choice response
        responses = {
            str(survey_question.uuid): "Red"
        }
        
        # Should not raise exception
        manager._validate_responses(survey_template, responses)
        
        # Invalid choice
        invalid_responses = {
            str(survey_question.uuid): "Purple"  # Not in choices
        }
        
        with pytest.raises(ValueError, match="Invalid choice"):
            manager._validate_responses(survey_template, invalid_responses)
        
        # Missing required question
        empty_responses = {}
        
        with pytest.raises(ValueError, match="Required question"):
            manager._validate_responses(survey_template, empty_responses)
    
    def test_analyze_response_quality(self, db, survey_template):
        """Test response quality analysis."""
        manager = ProfileSurveyManager()
        
        # Good responses
        good_responses = {
            "q1": "A",
            "q2": "B",
            "q3": "C",
            "q4": "D",
            "q5": "E"
        }
        
        quality = manager._analyze_response_quality(good_responses, survey_template)
        assert quality == Decimal('1.0')
        
        # Straight-lined responses
        straight_responses = {
            "q1": "A",
            "q2": "A",
            "q3": "A",
            "q4": "A",
            "q5": "A"
        }
        
        quality = manager._analyze_response_quality(straight_responses, survey_template)
        assert quality < Decimal('1.0')
    
    def test_get_survey_analytics(self, db, user, survey_template, user_profile):
        """Test getting survey analytics."""
        manager = ProfileSurveyManager()
        
        # Create some completions
        from api.cms.models_new.profile_surveys import SurveyCompletion
        SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            status='approved',
            quality_score=Decimal('0.9')
        )
        
        analytics = manager.get_survey_analytics(str(survey_template.uuid))
        
        assert 'survey_uuid' in analytics
        assert 'total_started' in analytics
        assert 'total_completed' in analytics
        assert 'total_approved' in analytics
        assert 'completion_rate' in analytics
        assert 'approval_rate' in analytics
    
    def test_get_user_survey_history(self, db, user, survey_template, user_profile):
        """Test getting user's survey history."""
        manager = ProfileSurveyManager()
        
        # Create some completions
        from api.cms.models_new.profile_surveys import SurveyCompletion
        SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            status='approved'
        )
        
        history = manager.get_user_survey_history(user, limit=10)
        
        assert len(history) >= 1
        assert all('uuid' in item for item in history)
        assert all('survey_title' in item for item in history)
        assert all('status' in item for item in history)


class TestSurveyAnalyticsService:
    """Test SurveyAnalyticsService service."""
    
    def test_get_dashboard_overview(self, db, user, survey_template, user_profile):
        """Test getting dashboard overview."""
        service = SurveyAnalyticsService()
        
        # Create some data
        from api.cms.models_new.profile_surveys import SurveyCompletion
        SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            status='approved'
        )
        
        overview = service.get_dashboard_overview(days=30)
        
        assert 'total_surveys' in overview
        assert 'total_completions' in overview
        assert 'total_approved' in overview
        assert 'active_users' in overview
        assert 'total_payout' in overview
        assert 'avg_quality_score' in overview
        assert 'completion_rate' in overview
    
    def test_get_survey_performance_report(self, db, user, survey_template, user_profile):
        """Test getting detailed survey performance report."""
        service = SurveyAnalyticsService()
        
        # Create some completions
        from api.cms.models_new.profile_surveys import SurveyCompletion
        SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            status='approved',
            quality_score=Decimal('0.9'),
            time_spent_seconds=300
        )
        
        report = service.get_survey_performance_report(str(survey_template.uuid), days=30)
        
        assert 'basic_stats' in report
        assert 'time_analytics' in report
        assert 'quality_analytics' in report
        assert 'drop_off_analysis' in report
        assert 'response_analysis' in report
        assert 'demographic_analysis' in report
        assert 'financial_analysis' in report
    
    def test_get_user_analytics(self, db, user, survey_template, user_profile):
        """Test getting user analytics."""
        service = SurveyAnalyticsService()
        
        # Create some completions
        from api.cms.models_new.profile_surveys import SurveyCompletion
        SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            status='approved',
            total_reward_earned=Decimal('5.00')
        )
        
        analytics = service.get_user_analytics(user.id, days=30)
        
        assert 'participation_stats' in analytics
        assert 'earnings' in analytics
        assert 'performance_metrics' in analytics
        assert 'category_preferences' in analytics
        assert 'activity_series' in analytics
    
    def test_get_real_time_metrics(self, db, user, survey_template, user_profile):
        """Test getting real-time metrics."""
        service = SurveyAnalyticsService()
        
        # Create some recent activity
        from api.cms.models_new.profile_surveys import SurveyCompletion
        SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            status='in_progress'
        )
        
        metrics = service.get_real_time_metrics()
        
        assert 'active_surveys' in metrics
        assert 'completions_last_hour' in metrics
        assert 'completions_last_24h' in metrics
        assert 'active_users' in metrics
        assert 'recent_avg_quality' in metrics
    
    def test_analyze_drop_off_points(self, db, survey_template, survey_question, user):
        """Test analyzing drop-off points."""
        service = SurveyAnalyticsService()
        
        # Create another question
        from api.cms.models_new.profile_surveys import SurveyQuestion
        q2 = SurveyQuestion.objects.create(
            survey=survey_template,
            question_text="Second question",
            question_type="single_choice",
            order=2,
            choices=["A", "B", "C"]
        )
        
        # Create some responses only for first question
        from api.cms.models_new.profile_surveys import SurveyCompletion, SurveyResponse
        completion = SurveyCompletion.objects.create(survey=survey_template, user=user)
        SurveyResponse.objects.create(
            completion=completion,
            question=survey_question,
            answer="A"
        )
        
        drop_off = service._analyze_drop_off_points(survey_template)
        
        assert len(drop_off) == 2
        assert all('question_order' in point for point in drop_off)
        assert all('drop_off_rate' in point for point in drop_off)
    
    def test_analyze_question_responses(self, db, survey_template, survey_question, user):
        """Test analyzing question responses."""
        service = SurveyAnalyticsService()
        
        # Create some responses
        from api.cms.models_new.profile_surveys import SurveyCompletion, SurveyResponse
        completion1 = SurveyCompletion.objects.create(survey=survey_template, user=user, status='approved')
        completion2 = SurveyCompletion.objects.create(survey=survey_template, user=user, status='approved')
        
        SurveyResponse.objects.create(completion=completion1, question=survey_question, answer="Red")
        SurveyResponse.objects.create(completion=completion2, question=survey_question, answer="Blue")
        SurveyResponse.objects.create(completion=completion2, question=survey_question, answer="Red")
        
        analysis = service._analyze_question_responses(survey_template)
        
        assert len(analysis) == 1
        question_analysis = analysis[0]
        assert 'question_uuid' in question_analysis
        assert 'response_patterns' in question_analysis
        assert 'choice_distribution' in question_analysis['response_patterns']
        assert question_analysis['response_patterns']['choice_distribution']['Red'] == 2
        assert question_analysis['response_patterns']['choice_distribution']['Blue'] == 1


class TestUserSegmentService:
    """Test UserSegmentService service."""
    
    def test_create_segment(self, db):
        """Test creating a new user segment."""
        service = UserSegmentService()
        
        segment_data = {
            'name': 'Test Segment',
            'description': 'Test description',
            'min_age': 18,
            'max_age': 65,
            'countries': ['US', 'CA'],
            'interests': ['technology']
        }
        
        segment = service.create_segment(segment_data)
        
        assert segment.name == 'Test Segment'
        assert segment.min_age == 18
        assert 'US' in segment.countries
        assert 'technology' in segment.interests
    
    def test_update_segment(self, db, user_segment):
        """Test updating an existing segment."""
        service = UserSegmentService()
        
        update_data = {
            'name': 'Updated Segment',
            'min_age': 21
        }
        
        segment = service.update_segment(str(user_segment.uuid), update_data)
        
        assert segment.name == 'Updated Segment'
        assert segment.min_age == 21
    
    def test_get_segment_users(self, db, user_segment, user, user_profile):
        """Test getting users in a segment."""
        service = UserSegmentService()
        
        # Create matching profile
        user_profile.date_of_birth = timezone.now().date() - timezone.timedelta(days=25*365)
        user_profile.country = 'US'
        user_profile.interests = ['technology']
        user_profile.save()
        
        users = service.get_segment_users(str(user_segment.uuid))
        
        assert len(users) >= 1
        assert user in users
    
    def test_get_user_segments(self, db, user, user_profile, user_segment):
        """Test getting segments a user belongs to."""
        service = UserSegmentService()
        
        # Create matching profile
        user_profile.date_of_birth = timezone.now().date() - timezone.timedelta(days=25*365)
        user_profile.country = 'US'
        user_profile.interests = ['technology']
        user_profile.save()
        
        segments = service.get_user_segments(user.id)
        
        assert len(segments) >= 1
        assert any(seg['name'] == user_segment.name for seg in segments)
    
    def test_get_segment_analytics(self, db, user, survey_template, user_profile, user_segment):
        """Test getting segment analytics."""
        service = UserSegmentService()
        
        # Create matching profile and completion
        user_profile.date_of_birth = timezone.now().date() - timezone.timedelta(days=25*365)
        user_profile.country = 'US'
        user_profile.interests = ['technology']
        user_profile.save()
        
        from api.cms.models_new.profile_surveys import SurveyCompletion
        SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            status='approved',
            total_reward_earned=Decimal('5.00')
        )
        
        analytics = service.get_segment_analytics(str(user_segment.uuid), days=30)
        
        assert 'survey_activity' in analytics
        assert 'earnings' in analytics
        assert 'quality_metrics' in analytics
        assert 'demographics' in analytics
    
    def test_get_recommended_surveys_for_segment(self, db, survey_template, user_segment):
        """Test getting recommended surveys for a segment."""
        service = UserSegmentService()
        
        survey_template.status = 'active'
        survey_template.save()
        
        recommendations = service.get_recommended_surveys_for_segment(str(user_segment.uuid), limit=5)
        
        assert len(recommendations) >= 1
        assert all('survey' in rec for rec in recommendations)
        assert all('match_score' in rec for rec in recommendations)
        assert all('segment_completion_rate' in rec for rec in recommendations)
    
    def test_auto_create_segments(self, db, user, user_profile):
        """Test automatic segment creation."""
        service = UserSegmentService()
        
        # Set up user profile for high-value segment
        user_profile.survey_participation_score = Decimal('90.00')
        user_profile.quality_score = Decimal('0.9')
        user_profile.save()
        
        segments = service.auto_create_segments()
        
        assert len(segments) >= 1
        assert any(seg.name == 'High Value Users' for seg in segments)
    
    def test_get_segment_overlap_analysis(self, db, user_segment):
        """Test segment overlap analysis."""
        service = UserSegmentService()
        
        # Create another segment
        from api.cms.models_new.user_profile import UserSegment
        seg2 = UserSegment.objects.create(
            name='Segment 2',
            countries=['US', 'UK'],
            interests=['technology', 'gaming']
        )
        
        overlap = service.get_segment_overlap_analysis([str(user_segment.uuid), str(seg2.uuid)])
        
        assert 'segments' in overlap
        assert 'pairwise_overlaps' in overlap
        assert 'unique_users' in overlap
    
    def test_calculate_segment_match_score(self, db, survey_template, user_segment):
        """Test calculating segment-survey match score."""
        service = UserSegmentService()
        
        score = service._calculate_segment_match_score(survey_template, user_segment)
        
        assert 0 <= score <= 100
        assert isinstance(score, float)
    
    def test_get_survey_segment_stats(self, db, user, survey_template, user_profile, user_segment):
        """Test getting survey statistics for a segment."""
        service = UserSegmentService()
        
        # Create matching profile and completion
        user_profile.date_of_birth = timezone.now().date() - timezone.timedelta(days=25*365)
        user_profile.country = 'US'
        user_profile.interests = ['technology']
        user_profile.save()
        
        from api.cms.models_new.profile_surveys import SurveyCompletion
        SurveyCompletion.objects.create(
            survey=survey_template,
            user=user,
            status='approved'
        )
        
        segment_users = user_segment.get_matching_users().values_list('user', flat=True)
        stats = service._get_survey_segment_stats(survey_template, segment_users)
        
        assert 'completion_rate' in stats
        assert 'avg_quality' in stats
