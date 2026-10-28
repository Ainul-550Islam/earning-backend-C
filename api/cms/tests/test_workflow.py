# api/cms/tests/test_workflow.py
"""Tests for Content Approval Workflow."""
from django.test import TestCase
from decimal import Decimal
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


class TestWorkflowService(TestCase):
    def setUp(self):
        from api.cms.factories import UserFactory
        self.author = UserFactory.create(username='author')
        self.reviewer = UserFactory.create(username='reviewer', is_staff=True)
        self.admin = UserFactory.create(username='admin', is_staff=True)
        # Create a mock blog post
        from api.cms.models_new.blog import BlogPost
        self.post = BlogPost.objects.create(
            title='Test Post', slug='test-post-wf',
            content='Test content', author=self.author, status='draft',
        )

    def test_get_or_create_workflow_state(self):
        from api.cms.services_new.WorkflowService import WorkflowService
        state = WorkflowService.get_or_create_state(self.post)
        self.assertIsNotNone(state)
        self.assertEqual(state.state, 'draft')

    def test_submit_for_review(self):
        from api.cms.services_new.WorkflowService import WorkflowService
        result = WorkflowService.submit_for_review(self.post, self.author)
        self.assertTrue(result['success'])
        self.assertEqual(result['state'], 'review')

    def test_cannot_submit_non_draft(self):
        from api.cms.services_new.WorkflowService import WorkflowService
        WorkflowService.submit_for_review(self.post, self.author)
        result = WorkflowService.submit_for_review(self.post, self.author)
        self.assertFalse(result['success'])

    def test_approve_from_review(self):
        from api.cms.services_new.WorkflowService import WorkflowService
        WorkflowService.submit_for_review(self.post, self.author)
        result = WorkflowService.approve(self.post, self.reviewer)
        self.assertTrue(result['success'])
        self.assertEqual(result['state'], 'approved')

    def test_reject_from_review(self):
        from api.cms.services_new.WorkflowService import WorkflowService
        WorkflowService.submit_for_review(self.post, self.author)
        result = WorkflowService.reject(self.post, self.reviewer, reason='Needs revision')
        self.assertTrue(result['success'])
        self.assertEqual(result['state'], 'rejected')

    def test_publish_approved(self):
        from api.cms.services_new.WorkflowService import WorkflowService
        WorkflowService.submit_for_review(self.post, self.author)
        WorkflowService.approve(self.post, self.reviewer)
        result = WorkflowService.publish(self.post, self.admin)
        self.assertTrue(result['success'])
        self.assertEqual(result['state'], 'published')

    def test_workflow_history(self):
        from api.cms.services_new.WorkflowService import WorkflowService
        WorkflowService.submit_for_review(self.post, self.author)
        WorkflowService.approve(self.post, self.reviewer)
        history = WorkflowService.get_history(self.post)
        self.assertGreater(len(history), 0)
        self.assertIn('from_state', history[0])
        self.assertIn('to_state', history[0])

    def test_get_pending_reviews(self):
        from api.cms.services_new.WorkflowService import WorkflowService
        WorkflowService.submit_for_review(self.post, self.author)
        pending = WorkflowService.get_pending_reviews()
        self.assertGreater(len(pending), 0)
