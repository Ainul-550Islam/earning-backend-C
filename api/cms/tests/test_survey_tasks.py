# api/cms/tests/test_survey_tasks.py
"""Tests for survey system background tasks."""
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
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from unittest.mock import patch, MagicMock

from api.cms.tasks.survey_tasks import (
    process_survey_rewards,
    update_survey_analytics,
    cleanup_expired_surveys,
    update_user_segments,
    send_survey_recommendations,
    generate_survey_report,
    validate_survey_quality,
    sync_survey_caches
)


class TestSurveyTasks:
    """Test survey background tasks."""
    
    @patch('api.cms.tasks.survey_tasks.ProfileSurveyManager')
    @patch('api.cms.tasks.survey_tasks.SurveyCompletion')
    @patch('api.cms.tasks.survey_tasks.SurveyReward')
    @patch('api.cms.tasks.survey_tasks.RewardTransaction')
    def test_process_survey_rewards_success(self, mock_transaction, mock_reward,
                                             mock_completion_model, mock_manager):
        """Test successful survey reward processing."""
        # Setup mocks
        mock_completion = MagicMock()
        mock_completion.status = 'approved'
        mock_completion.survey.title = 'Test Survey'
        mock_completion.responses.all.return_value = []
        mock_completion_model.objects.get.return_value = mock_completion

        mock_reward.objects.filter.return_value = []

        mock_transaction_instance = MagicMock()
        mock_transaction.objects.create.return_value = mock_transaction_instance

        # Call task
        result = process_survey_rewards('12345678-1234-5678-1234-567812345678')
        
        # Assertions
        assert result['status'] == 'success'
        assert 'transactions_created' in result
        assert 'total_reward' in result
    
    @patch('api.cms.tasks.survey_tasks.SurveyCompletion')
    def test_process_survey_rewards_not_approved(self, mock_completion_model):
        """Test reward processing for non-approved completion."""
        # Setup mock
        mock_completion = MagicMock()
        mock_completion.status = 'completed'
        mock_completion_model.objects.get.return_value = mock_completion
        
        # Call task
        result = process_survey_rewards('12345678-1234-5678-1234-567812345678')
        
        # Assertions
        assert result['status'] == 'skipped'
        assert result['reason'] == 'not_approved'
    
    @patch('api.cms.tasks.survey_tasks.SurveyCompletion')
    def test_process_survey_rewards_not_found(self, mock_completion_model):
        """Test reward processing for non-existent completion."""
        # Use a real exception so side_effect actually raises
        class FakeDoesNotExist(Exception):
            pass
        mock_completion_model.DoesNotExist = FakeDoesNotExist
        mock_completion_model.objects.get.side_effect = FakeDoesNotExist("not found")

        # Call task
        result = process_survey_rewards('nonexistent-uuid')

        # Assertions
        assert result['status'] == 'error'
        assert result['reason'] == 'completion_not_found'
    
    @patch('api.cms.tasks.survey_tasks.SurveyAnalyticsService')
    def test_update_survey_analytics_specific(self, mock_analytics_service):
        """Test updating analytics for specific survey."""
        # Setup mock
        mock_service = MagicMock()
        mock_analytics_service.return_value = mock_service
        
        # Call task
        result = update_survey_analytics('12345678-1234-5678-1234-567812345678')
        
        # Assertions
        assert result['status'] == 'success'
        assert result['survey_uuid'] == '12345678-1234-5678-1234-567812345678'
        mock_service.get_survey_performance_report.assert_called_once_with('12345678-1234-5678-1234-567812345678')
    
    @patch('api.cms.tasks.survey_tasks.SurveyAnalyticsService')
    @patch('api.cms.tasks.survey_tasks.SurveyTemplate')
    def test_update_survey_analytics_all(self, mock_survey_template, mock_analytics_service):
        """Test updating analytics for all surveys."""
        # Setup mocks
        mock_survey = MagicMock()
        mock_survey.uuid = '12345678-1234-5678-1234-567812345678'
        mock_survey_template.objects.filter.return_value = [mock_survey]
        
        mock_service = MagicMock()
        mock_analytics_service.return_value = mock_service
        
        # Call task
        result = update_survey_analytics()
        
        # Assertions
        assert result['status'] == 'success'
        assert 'updated_count' in result
        assert result['updated_count'] >= 0
    
    @patch('api.cms.tasks.survey_tasks.timezone')
    @patch('api.cms.tasks.survey_tasks.SurveyTemplate')
    def test_cleanup_expired_surveys(self, mock_survey_template, mock_timezone):
        """Test cleaning up expired surveys."""
        # Setup mocks
        mock_now = timezone.now()
        mock_timezone.now.return_value = mock_now
        
        mock_queryset = MagicMock()
        mock_queryset.update.return_value = 5
        mock_survey_template.objects.filter.return_value = mock_queryset
        
        # Call task
        result = cleanup_expired_surveys()
        
        # Assertions
        assert result['status'] == 'success'
        assert result['deactivated_count'] == 5
        mock_survey_template.objects.filter.assert_called_once()
    
    @patch('api.cms.tasks.survey_tasks.UserSegmentService')
    @patch('api.cms.tasks.survey_tasks.UserSegment')
    def test_update_user_segments(self, mock_user_segment, mock_segment_service):
        """Test updating user segments."""
        # Setup mocks
        mock_segment = MagicMock()
        mock_segment.update_user_count.return_value = None
        mock_user_segment.objects.filter.return_value = [mock_segment]
        
        # Call task
        result = update_user_segments()
        
        # Assertions
        assert result['status'] == 'success'
        assert 'updated_count' in result
        mock_segment.update_user_count.assert_called_once()
    
    @patch('api.cms.tasks.survey_tasks.ProfileSurveyManager')
    @patch('api.cms.tasks.survey_tasks.NotificationService')
    @patch('api.cms.tasks.survey_tasks.User')
    def test_send_survey_recommendations_all_users(self, mock_user, mock_notification_service, mock_manager):
        """Test sending survey recommendations to all users."""
        # Setup mocks
        mock_user_obj = MagicMock()
        mock_user_obj.id = 1
        mock_user.objects.filter.return_value = [mock_user_obj]
        
        mock_manager_instance = MagicMock()
        mock_manager_instance.get_recommended_surveys.return_value = [
            {'survey': MagicMock()},
            {'survey': MagicMock()}
        ]
        mock_manager.return_value = mock_manager_instance
        
        # Call task
        result = send_survey_recommendations()
        
        # Assertions
        assert result['status'] == 'success'
        assert 'sent_count' in result
        mock_notification_service.notify_user.assert_called()
    
    @patch('api.cms.tasks.survey_tasks.ProfileSurveyManager')
    @patch('api.cms.tasks.survey_tasks.NotificationService')
    @patch('api.cms.tasks.survey_tasks.User')
    def test_send_survey_recommendations_specific_user(self, mock_user, mock_notification_service, mock_manager):
        """Test sending survey recommendations to specific user."""
        # Setup mocks
        mock_user_obj = MagicMock()
        mock_user_obj.id = 1
        mock_user.objects.get.return_value = mock_user_obj
        
        mock_manager_instance = MagicMock()
        mock_manager_instance.get_recommended_surveys.return_value = []
        mock_manager.return_value = mock_manager_instance
        
        # Call task
        result = send_survey_recommendations(user_id=1)
        
        # Assertions
        assert result['status'] == 'success'
        mock_user.objects.get.assert_called_once_with(id=1)
    
    @patch('api.cms.tasks.survey_tasks.SurveyAnalyticsService')
    @patch('api.cms.tasks.survey_tasks.SurveyTemplate')
    def test_generate_survey_report_daily(self, mock_survey_template, mock_analytics_service):
        """Test generating daily survey report."""
        # Setup mocks
        mock_survey = MagicMock()
        mock_survey.uuid = '12345678-1234-5678-1234-567812345678'
        mock_survey_template.objects.get.return_value = mock_survey
        
        mock_service = MagicMock()
        mock_service.get_survey_performance_report.return_value = {'data': 'test'}
        mock_analytics_service.return_value = mock_service
        
        # Call task
        result = generate_survey_report('12345678-1234-5678-1234-567812345678', 'daily')
        
        # Assertions
        assert result['status'] == 'success'
        assert result['survey_uuid'] == '12345678-1234-5678-1234-567812345678'
        assert result['report_type'] == 'daily'
        assert result['period_days'] == 1
        mock_service.get_survey_performance_report.assert_called_once_with('12345678-1234-5678-1234-567812345678', 1)
    
    @patch('api.cms.tasks.survey_tasks.SurveyTemplate')
    def test_generate_survey_report_not_found(self, mock_survey_template):
        """Test generating report for non-existent survey."""
        # Setup mock to raise DoesNotExist
        mock_survey_template.objects.get.side_effect = mock_survey_template.DoesNotExist()
        
        # Call task
        result = generate_survey_report('nonexistent-uuid')
        
        # Assertions
        assert result['status'] == 'error'
        assert result['reason'] == 'survey_not_found'
    
    @patch('api.cms.tasks.survey_tasks.process_survey_rewards')
    @patch('api.cms.tasks.survey_tasks.SurveyResponse')
    @patch('api.cms.tasks.survey_tasks.SurveyCompletion')
    def test_validate_survey_quality_auto_approve(self, mock_completion_model, mock_response, mock_process_rewards):
        """Test quality validation with auto-approval."""
        # Setup mocks
        mock_completion = MagicMock()
        mock_completion.status = 'completed'
        mock_completion.time_spent_seconds = 600  # 10 minutes
        mock_completion.responses.all.return_value = []
        mock_completion.survey.estimated_minutes = 5
        mock_completion_model.objects.get.return_value = mock_completion
        
        mock_response.objects.filter.return_value.count.return_value = 0  # No failed attention checks
        
        # Call task
        result = validate_survey_quality('12345678-1234-5678-1234-567812345678')
        
        # Assertions
        assert result['status'] == 'success'
        assert 'quality_score' in result
        assert 'flags' in result
        assert 'auto_approved' in result
        
        # Check if completion was saved with quality score
        mock_completion.save.assert_called()
        
        # Check if reward processing was triggered for high quality
        if mock_completion.quality_score >= Decimal('0.8'):
            mock_process_rewards.delay.assert_called_once()
    
    @patch('api.cms.tasks.survey_tasks.SurveyCompletion')
    def test_validate_survey_quality_not_completed(self, mock_completion_model):
        """Test quality validation for non-completed survey."""
        # Setup mock
        mock_completion = MagicMock()
        mock_completion.status = 'started'
        mock_completion_model.objects.get.return_value = mock_completion
        
        # Call task
        result = validate_survey_quality('12345678-1234-5678-1234-567812345678')
        
        # Assertions
        assert result['status'] == 'skipped'
        assert result['reason'] == 'not_completed'
    
    @patch('api.cms.tasks.survey_tasks.SurveyCompletion')
    def test_validate_survey_quality_not_found(self, mock_completion_model):
        """Test quality validation for non-existent completion."""
        # Setup mock to raise DoesNotExist — must use a real exception class, not a MagicMock instance
        class FakeDoesNotExist(Exception):
            pass
        mock_completion_model.DoesNotExist = FakeDoesNotExist
        mock_completion_model.objects.get.side_effect = FakeDoesNotExist("Not found")

        # Call task
        result = validate_survey_quality('nonexistent-uuid')

        # Assertions
        assert result['status'] == 'error'
        assert result['reason'] == 'completion_not_found'
    
    @patch('api.cms.tasks.survey_tasks.cache')
    @patch('api.cms.tasks.survey_tasks.SurveyTemplate')
    @patch('api.cms.tasks.survey_tasks.UserProfile')
    def test_sync_survey_caches(self, mock_user_profile, mock_survey_template, mock_cache):
        """Test synchronizing survey caches."""
        # Setup mocks
        mock_profile = MagicMock()
        mock_profile.user.id = 1
        mock_user_profile.objects.all.return_value = [mock_profile]
        
        mock_survey = MagicMock()
        mock_survey.uuid = '12345678-1234-5678-1234-567812345678'
        mock_survey_template.objects.filter.return_value = [mock_survey]
        
        # Call task
        result = sync_survey_caches()
        
        # Assertions
        assert result['status'] == 'success'
        assert 'user_caches_cleared' in result
        assert 'survey_caches_cleared' in result
        
        # Check cache deletion calls
        assert mock_cache.delete.call_count >= 2  # At least user and survey caches
    
    @patch('api.cms.tasks.survey_tasks.cache')
    @patch('api.cms.tasks.survey_tasks.SurveyTemplate')
    @patch('api.cms.tasks.survey_tasks.UserProfile')
    def test_sync_survey_caches_no_surveys(self, mock_user_profile, mock_survey_template, mock_cache):
        """Test cache sync with no active surveys."""
        # Setup mocks
        mock_user_profile.objects.all.return_value = []
        mock_survey_template.objects.filter.return_value = []
        
        # Call task
        result = sync_survey_caches()
        
        # Assertions
        assert result['status'] == 'success'
        assert result['user_caches_cleared'] == 0
        assert result['survey_caches_cleared'] == 0


class TestSurveyTaskErrorHandling:
    """Test error handling in survey tasks."""
    
    @patch('api.cms.tasks.survey_tasks.SurveyCompletion')
    def test_process_survey_rewards_retry(self, mock_completion_model):
        """Test that reward processing task retries on exception."""
        # Setup mock to raise exception
        mock_completion_model.objects.get.side_effect = Exception("Test error")
        
        # Create task instance with retry capability
        task = process_survey_rewards
        task.request.retries = 0
        task.retry = MagicMock()
        
        # Call task and expect retry
        with pytest.raises(Exception):
            task('12345678-1234-5678-1234-567812345678')
        
        # Verify retry was called
        task.retry.assert_called_once()
    
    @patch('api.cms.tasks.survey_tasks.SurveyAnalyticsService')
    def test_update_survey_analytics_retry(self, mock_analytics_service):
        """Test that analytics update task retries on exception."""
        # Setup mock to raise exception
        mock_analytics_service.side_effect = Exception("Test error")
        
        # Create task instance with retry capability
        task = update_survey_analytics
        task.request.retries = 0
        task.retry = MagicMock()
        
        # Call task and expect retry
        with pytest.raises(Exception):
            task('12345678-1234-5678-1234-567812345678')
        
        # Verify retry was called
        task.retry.assert_called_once()
    
    @patch('api.cms.tasks.survey_tasks.timezone')
    @patch('api.cms.tasks.survey_tasks.SurveyTemplate')
    def test_cleanup_expired_surveys_no_retry(self, mock_survey_template, mock_timezone):
        """Test that cleanup task doesn't retry on certain exceptions."""
        # Setup mocks
        mock_timezone.now.return_value = timezone.now()
        mock_queryset = MagicMock()
        mock_queryset.update.side_effect = ValueError("Database error")
        mock_survey_template.objects.filter.return_value = mock_queryset
        
        # Call task
        result = cleanup_expired_surveys()
        
        # Should not raise exception, but return error status
        assert result['status'] == 'error' or 'exception' in str(result).lower()


class TestSurveyTaskPerformance:
    """Test performance characteristics of survey tasks."""
    
    @patch('api.cms.tasks.survey_tasks.ProfileSurveyManager')
    @patch('api.cms.tasks.survey_tasks.SurveyCompletion')
    @patch('api.cms.tasks.survey_tasks.SurveyReward')
    @patch('api.cms.tasks.survey_tasks.RewardTransaction')
    def test_process_survey_rewards_performance(self, mock_transaction, mock_reward, mock_completion_model, mock_manager):
        """Test reward processing performance with multiple rewards."""
        # Setup mocks for multiple reward configurations
        mock_completion = MagicMock()
        mock_completion.status = 'approved'
        mock_completion_model.objects.get.return_value = mock_completion
        mock_completion.survey.title = 'Test Survey'
        mock_completion.responses.all.return_value = []
        
        mock_reward_config = MagicMock()
        mock_reward_config.calculate_reward.return_value = Decimal('5.00')
        mock_reward_config.update_statistics.return_value = None
        mock_reward.objects.filter.return_value = [mock_reward_config] * 3  # 3 reward configs
        
        mock_transaction_instance = MagicMock()
        mock_transaction_instance.approve.return_value = None
        mock_transaction.objects.create.return_value = mock_transaction_instance
        
        # Call task
        result = process_survey_rewards('12345678-1234-5678-1234-567812345678')
        
        # Assertions
        assert result['status'] == 'success'
        assert result['transactions_created'] == 3
        assert result['total_reward'] == 15.0  # 3 * 5.00
    
    @patch('api.cms.tasks.survey_tasks.SurveyAnalyticsService')
    @patch('api.cms.tasks.survey_tasks.SurveyTemplate')
    def test_update_survey_analytics_batch_performance(self, mock_survey_template, mock_analytics_service):
        """Test analytics update performance with multiple surveys."""
        # Setup mocks for multiple surveys
        mock_surveys = [MagicMock(uuid=f'test-uuid-{i}') for i in range(10)]
        mock_survey_template.objects.filter.return_value = mock_surveys
        
        mock_service = MagicMock()
        mock_analytics_service.return_value = mock_service
        
        # Call task
        result = update_survey_analytics()
        
        # Assertions
        assert result['status'] == 'success'
        assert result['updated_count'] == 10
        assert mock_service.get_survey_performance_report.call_count == 10
