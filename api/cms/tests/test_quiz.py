# api/cms/tests/test_quiz.py
"""Tests for Quiz Builder."""
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


class TestQuizService(TestCase):
    def setUp(self):
        from api.cms.factories import QuizFactory, UserFactory
        from django.core.cache import cache
        cache.clear()
        self.user = UserFactory.create()
        self.quiz = QuizFactory.create(num_questions=3)

    def test_start_attempt(self):
        from api.cms.services_new.QuizService import QuizService
        result = QuizService.start_attempt(self.quiz.id, user=self.user)
        self.assertIn('attempt_id', result)
        self.assertIn('questions', result)
        self.assertEqual(len(result['questions']), 3)

    def test_start_attempt_invalid_quiz(self):
        from api.cms.services_new.QuizService import QuizService
        result = QuizService.start_attempt(99999, user=self.user)
        self.assertIn('error', result)

    def test_submit_answers(self):
        from api.cms.services_new.QuizService import QuizService
        start = QuizService.start_attempt(self.quiz.id, user=self.user)
        attempt_id = start['attempt_id']
        answers = {
            str(q['id']): q['answers'][0]['id']
            for q in start['questions'] if q['answers']
        }
        result = QuizService.submit_answers(attempt_id, answers)
        self.assertTrue(result.get('completed'))
        self.assertIn('total_score', result)

    def test_list_quizzes(self):
        from api.cms.services_new.QuizService import QuizService
        quizzes = QuizService.list_quizzes()
        self.assertIsInstance(quizzes, list)
        self.assertGreater(len(quizzes), 0)

    def test_completion_rate_calculation(self):
        from api.cms.models_new.quiz import QuizTemplate
        quiz = QuizTemplate.objects.create(
            title='Rate Test', slug='rate-test-1', quiz_type='personality',
            is_active=True, total_attempts=10, total_completions=7,
        )
        self.assertEqual(quiz.completion_rate, 70.0)


class TestQuizModel(TestCase):
    def test_quiz_attempt_complete(self):
        from api.cms.factories import QuizFactory, UserFactory
        user = UserFactory.create()
        quiz = QuizFactory.create(num_questions=2)
        from api.cms.models_new.quiz import QuizAttempt
        attempt = QuizAttempt.objects.create(quiz=quiz, user=user)
        result = quiz.results.first()
        attempt.complete(result, total_score=5)
        attempt.refresh_from_db()
        self.assertTrue(attempt.is_completed)
        self.assertEqual(attempt.total_score, 5)
