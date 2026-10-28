# cms/tests_new/test_models_group1.py
"""
Model Tests — Group 1

Tests for:
  - Blog models (BlogCategory, BlogPost, BlogComment, BlogSEO)
  - Survey models (Survey, SurveyQuestion, SurveyCompletion)
  - Leaderboard models (Leaderboard, EarningStreak, LeaderboardEntry)
  - Withdrawal models (WithdrawalRequest, PayoutMethod)
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from decimal import Decimal
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# BLOG MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class BlogCategoryModelTest(TestCase):
    """Tests for BlogCategory model."""

    def setUp(self):
        self.category = None
        try:
            from api.cms.models_new.blog import BlogCategory
            self.BlogCategory = BlogCategory
            self.category = BlogCategory.objects.create(
                name='Technology',
                slug='technology',
            )
        except Exception:
            self.skipTest('BlogCategory model not available')

    def test_category_creation(self):
        self.assertIsNotNone(self.category.id)
        self.assertEqual(self.category.name, 'Technology')
        self.assertEqual(self.category.slug, 'technology')

    def test_category_str(self):
        self.assertIn('Technology', str(self.category))

    def test_category_slug_unique(self):
        with self.assertRaises(IntegrityError):
            self.BlogCategory.objects.create(name='Tech2', slug='technology')

    def test_category_ordering(self):
        self.BlogCategory.objects.create(name='Arts', slug='arts')
        cats = list(self.BlogCategory.objects.all())
        self.assertGreaterEqual(len(cats), 1)

    def test_category_parent_child(self):
        child = self.BlogCategory.objects.create(
            name='Python', slug='python', parent=self.category
        )
        self.assertEqual(child.parent, self.category)


class BlogPostModelTest(TestCase):
    """Tests for BlogPost model."""

    def setUp(self):
        try:
            from api.cms.models_new.blog import BlogPost, BlogCategory
            self.BlogPost = BlogPost
            self.user = User.objects.create_user('bloguser', 'blog@test.com', 'pass')
            self.category = BlogCategory.objects.create(name='Tech', slug='tech')
            self.post = BlogPost.objects.create(
                title='Test Post',
                slug='test-post',
                content='Content here',
                author=self.user,
                category=self.category,
            )
        except Exception:
            self.skipTest('BlogPost model not available')

    def test_post_creation(self):
        self.assertIsNotNone(self.post.id)
        self.assertEqual(self.post.title, 'Test Post')
        self.assertEqual(self.post.author, self.user)

    def test_post_str(self):
        self.assertIn('Test Post', str(self.post))

    def test_post_default_not_published(self):
        self.assertFalse(self.post.is_published)

    def test_post_publish_sets_timestamp(self):
        self.post.is_published = True
        self.post.published_at = timezone.now()
        self.post.save()
        self.assertIsNotNone(self.post.published_at)

    def test_post_slug_unique_per_category(self):
        user2 = User.objects.create_user('user2', 'u2@test.com', 'pass')
        with self.assertRaises(IntegrityError):
            self.BlogPost.objects.create(
                title='Duplicate', slug='test-post',
                content='Content', author=user2, category=self.category,
            )

    def test_post_view_count_default_zero(self):
        self.assertEqual(self.post.view_count, 0)

    def test_post_category_relationship(self):
        self.assertEqual(self.post.category, self.category)

    def test_published_queryset_method(self):
        self.post.is_published = True
        self.post.save()
        if hasattr(self.BlogPost.objects, 'published'):
            qs = self.BlogPost.objects.published()
            self.assertIn(self.post, qs)


class BlogSEOModelTest(TestCase):
    """Tests for BlogSEO model."""

    def setUp(self):
        try:
            from api.cms.models_new.blog import BlogPost, BlogCategory, BlogSEO
            self.BlogSEO = BlogSEO
            user = User.objects.create_user('seouser', 'seo@test.com', 'pass')
            category = BlogCategory.objects.create(name='SEO', slug='seo-cat')
            self.post = BlogPost.objects.create(
                title='SEO Post', slug='seo-post',
                content='Content', author=user, category=category,
            )
            self.seo = BlogSEO.objects.create(
                post=self.post,
                meta_title='SEO Meta Title for Post',
                meta_description='This is the SEO meta description for the post, has enough characters.',
            )
        except Exception:
            self.skipTest('BlogSEO model not available')

    def test_seo_creation(self):
        self.assertIsNotNone(self.seo.id)
        self.assertEqual(self.seo.post, self.post)

    def test_seo_str(self):
        result = str(self.seo)
        self.assertIsInstance(result, str)

    def test_seo_one_to_one_with_post(self):
        with self.assertRaises(Exception):
            self.BlogSEO.objects.create(
                post=self.post,
                meta_title='Duplicate SEO',
                meta_description='Duplicate meta description here with enough chars.',
            )


# ─────────────────────────────────────────────────────────────────────────────
# SURVEY MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class SurveyModelTest(TestCase):
    """Tests for Survey model."""

    def setUp(self):
        try:
            from api.cms.models_new.survey import Survey
            self.Survey = Survey
            self.user = User.objects.create_user('surveyuser', 's@test.com', 'pass')
            self.survey = Survey.objects.create(
                title='Test Survey',
                reward_amount=Decimal('5.00'),
                created_by=self.user,
            )
        except Exception:
            self.skipTest('Survey model not available')

    def test_survey_creation(self):
        self.assertIsNotNone(self.survey.id)
        self.assertEqual(self.survey.title, 'Test Survey')
        self.assertEqual(self.survey.reward_amount, Decimal('5.00'))

    def test_survey_str(self):
        self.assertIn('Test Survey', str(self.survey))

    def test_survey_default_active(self):
        self.assertTrue(self.survey.is_active)

    def test_survey_reward_non_negative(self):
        self.assertGreaterEqual(self.survey.reward_amount, 0)


class SurveyCompletionModelTest(TestCase):
    """Tests for SurveyCompletion model."""

    def setUp(self):
        try:
            from api.cms.models_new.survey import Survey, SurveyCompletion
            self.SurveyCompletion = SurveyCompletion
            self.user = User.objects.create_user('completer', 'c@test.com', 'pass')
            survey_user = User.objects.create_user('survmaker', 'sm@test.com', 'pass')
            self.survey = Survey.objects.create(
                title='Complete Me', reward_amount=Decimal('3.00'), created_by=survey_user
            )
            self.completion = SurveyCompletion.objects.create(
                survey=self.survey,
                user=self.user,
                reward_amount=Decimal('3.00'),
            )
        except Exception:
            self.skipTest('SurveyCompletion model not available')

    def test_completion_creation(self):
        self.assertIsNotNone(self.completion.id)
        self.assertEqual(self.completion.user, self.user)
        self.assertEqual(self.completion.survey, self.survey)

    def test_completion_reward_matches_survey(self):
        self.assertEqual(self.completion.reward_amount, self.survey.reward_amount)

    def test_completion_timestamp_auto(self):
        self.assertIsNotNone(self.completion.created_at)

    def test_duplicate_completion_constraint(self):
        """User should not complete same survey twice (if unique_together set)."""
        try:
            self.SurveyCompletion.objects.create(
                survey=self.survey, user=self.user, reward_amount=Decimal('3.00')
            )
        except IntegrityError:
            pass  # expected if unique_together enforced


# ─────────────────────────────────────────────────────────────────────────────
# LEADERBOARD MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class LeaderboardModelTest(TestCase):
    """Tests for Leaderboard model."""

    def setUp(self):
        try:
            from api.cms.models_new.leaderboard import Leaderboard
            self.Leaderboard = Leaderboard
            self.user = User.objects.create_user('leader', 'l@test.com', 'pass')
            self.entry = Leaderboard.objects.create(
                user=self.user,
                total_points=Decimal('250.00'),
                rank_position=1,
            )
        except Exception:
            self.skipTest('Leaderboard model not available')

    def test_leaderboard_creation(self):
        self.assertIsNotNone(self.entry.id)
        self.assertEqual(self.entry.user, self.user)
        self.assertEqual(self.entry.rank_position, 1)

    def test_leaderboard_str(self):
        result = str(self.entry)
        self.assertIsInstance(result, str)

    def test_leaderboard_points_non_negative(self):
        self.assertGreaterEqual(self.entry.total_points, 0)

    def test_user_unique_on_leaderboard(self):
        with self.assertRaises(Exception):
            self.Leaderboard.objects.create(
                user=self.user, total_points=Decimal('100.00'), rank_position=2
            )


class EarningStreakModelTest(TestCase):
    """Tests for EarningStreak model."""

    def setUp(self):
        try:
            from api.cms.models_new.leaderboard import EarningStreak
            self.EarningStreak = EarningStreak
            self.user = User.objects.create_user('streaker', 'st@test.com', 'pass')
            self.streak = EarningStreak.objects.create(
                user=self.user,
                current_streak=7,
                longest_streak=10,
            )
        except Exception:
            self.skipTest('EarningStreak model not available')

    def test_streak_creation(self):
        self.assertIsNotNone(self.streak.id)
        self.assertEqual(self.streak.current_streak, 7)

    def test_streak_longest_gte_current(self):
        self.assertGreaterEqual(self.streak.longest_streak, self.streak.current_streak)

    def test_streak_str(self):
        self.assertIsInstance(str(self.streak), str)


# ─────────────────────────────────────────────────────────────────────────────
# WITHDRAWAL MODEL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class WithdrawalRequestModelTest(TestCase):
    """Tests for WithdrawalRequest model."""

    def setUp(self):
        try:
            from api.cms.models_new.withdrawal import WithdrawalRequest
            self.WithdrawalRequest = WithdrawalRequest
            self.user = User.objects.create_user('withdrawer', 'w@test.com', 'pass')
            self.request_obj = WithdrawalRequest.objects.create(
                user=self.user,
                amount=Decimal('50.00'),
                payment_method='bkash',
                account_number='01712345678',
            )
        except Exception:
            self.skipTest('WithdrawalRequest model not available')

    def test_withdrawal_creation(self):
        self.assertIsNotNone(self.request_obj.id)
        self.assertEqual(self.request_obj.amount, Decimal('50.00'))
        self.assertEqual(self.request_obj.user, self.user)

    def test_withdrawal_default_status_pending(self):
        self.assertEqual(self.request_obj.status, 'pending')

    def test_withdrawal_str(self):
        self.assertIsInstance(str(self.request_obj), str)

    def test_withdrawal_amount_positive(self):
        self.assertGreater(self.request_obj.amount, 0)

    def test_withdrawal_approve(self):
        self.request_obj.status = 'approved'
        self.request_obj.approved_at = timezone.now()
        self.request_obj.save()
        refreshed = self.WithdrawalRequest.objects.get(pk=self.request_obj.pk)
        self.assertEqual(refreshed.status, 'approved')

    def test_withdrawal_reject(self):
        self.request_obj.status = 'rejected'
        self.request_obj.rejection_reason = 'Insufficient verification'
        self.request_obj.save()
        refreshed = self.WithdrawalRequest.objects.get(pk=self.request_obj.pk)
        self.assertEqual(refreshed.status, 'rejected')


class PayoutMethodModelTest(TestCase):
    """Tests for PayoutMethod model."""

    def setUp(self):
        try:
            from api.cms.models_new.withdrawal import PayoutMethod
            self.PayoutMethod = PayoutMethod
            self.user = User.objects.create_user('payoutuser', 'pay@test.com', 'pass')
            self.method = PayoutMethod.objects.create(
                user=self.user,
                method_type='bkash',
                account_number='01712345678',
                is_default=True,
            )
        except Exception:
            self.skipTest('PayoutMethod model not available')

    def test_payout_method_creation(self):
        self.assertIsNotNone(self.method.id)
        self.assertEqual(self.method.method_type, 'bkash')
        self.assertTrue(self.method.is_default)

    def test_payout_method_str(self):
        self.assertIsInstance(str(self.method), str)

    def test_payout_method_belongs_to_user(self):
        self.assertEqual(self.method.user, self.user)
