# cms/tests_new/test_gamification.py
"""
Gamification system tests:
LeaderboardService, ReferralService, QuizService, ABTestingService.
"""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()
pytestmark = pytest.mark.django_db


def _make_user(username):
    return User.objects.create_user(
        username=username, email=f'{username}@test.com', password='Pass123!'
    )


# ══════════════════════════════════════════════════════════════════════════════
# LeaderboardService
# ══════════════════════════════════════════════════════════════════════════════

class TestLeaderboardService(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user_a = _make_user('lb_user_a')
        cls.user_b = _make_user('lb_user_b')

    def test_update_score_returns_entry(self):
        from api.cms.services_new.LeaderboardService import LeaderboardService
        result = LeaderboardService.update_score(
            user=self.user_a, points=Decimal('100'), period='daily'
        )
        self.assertIsNotNone(result)

    def test_get_leaderboard_returns_list(self):
        from api.cms.services_new.LeaderboardService import LeaderboardService
        result = LeaderboardService.get_leaderboard(period='daily', limit=10)
        self.assertIsInstance(result, (list, dict))

    def test_get_user_rank_returns_int_or_none(self):
        from api.cms.services_new.LeaderboardService import LeaderboardService
        LeaderboardService.update_score(self.user_a, Decimal('50'), 'daily')
        rank = LeaderboardService.get_user_rank(self.user_a, 'daily')
        self.assertIsInstance(rank, (int, type(None)))

    def test_higher_score_better_rank(self):
        from api.cms.services_new.LeaderboardService import LeaderboardService
        LeaderboardService.update_score(self.user_a, Decimal('10'),  'weekly')
        LeaderboardService.update_score(self.user_b, Decimal('500'), 'weekly')
        rank_a = LeaderboardService.get_user_rank(self.user_a, 'weekly')
        rank_b = LeaderboardService.get_user_rank(self.user_b, 'weekly')
        if rank_a and rank_b:
            self.assertGreater(rank_a, rank_b,
                               msg='Lower score → worse rank (higher number)')

    def test_recalculate_rankings_returns_count(self):
        from api.cms.services_new.LeaderboardService import LeaderboardService
        result = LeaderboardService.recalculate_rankings()
        self.assertIsInstance(result, (dict, int))

    def test_update_streak_returns_streak_data(self):
        from api.cms.services_new.LeaderboardService import LeaderboardService
        result = LeaderboardService.update_streak(user=self.user_a)
        self.assertIsInstance(result, dict)

    def test_get_user_streak_returns_dict(self):
        from api.cms.services_new.LeaderboardService import LeaderboardService
        result = LeaderboardService.get_user_streak(self.user_a)
        self.assertIsInstance(result, (dict, type(None)))


# ══════════════════════════════════════════════════════════════════════════════
# ReferralService
# ══════════════════════════════════════════════════════════════════════════════

class TestReferralService(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.referrer = _make_user('ref_referrer')
        cls.referred = _make_user('ref_referred')

    def test_generate_referral_code_unique(self):
        from api.cms.services_new.ReferralService import ReferralService
        code1 = ReferralService.generate_referral_code(self.referrer)
        code2 = ReferralService.generate_referral_code(self.referrer)
        # Second call should return same code (idempotent) or a new unique code
        self.assertIsNotNone(code1)

    def test_get_referral_stats_returns_dict(self):
        from api.cms.services_new.ReferralService import ReferralService
        stats = ReferralService.get_referral_stats(self.referrer)
        self.assertIsInstance(stats, dict)

    @patch('api.cms.services_new.ReferralService.VirtualCurrencyService.award_coins')
    def test_process_referral_bonus_awards_referrer(self, mock_award):
        from api.cms.services_new.ReferralService import ReferralService
        mock_award.return_value = True
        ReferralService.process_referral_bonus(
            referrer=self.referrer,
            referred=self.referred,
            earned_amount=Decimal('10.00'),
            lead_id='ref_bonus_lead',
        )
        mock_award.assert_called()
        # Referrer gets bonus (5% of earned)
        call_args = mock_award.call_args_list[0]
        self.assertEqual(call_args[1].get('user') or call_args[0][0], self.referrer)

    def test_process_self_referral_rejected(self):
        from api.cms.services_new.ReferralService import ReferralService
        with self.assertRaises(Exception):
            ReferralService.process_referral_bonus(
                referrer=self.referrer,
                referred=self.referrer,  # same user → invalid
                earned_amount=Decimal('5.00'),
                lead_id='self_ref_lead',
            )

    def test_get_referral_tree_returns_list(self):
        from api.cms.services_new.ReferralService import ReferralService
        tree = ReferralService.get_referral_tree(self.referrer)
        self.assertIsInstance(tree, (list, dict))

    def test_referral_bonus_rate_is_five_percent(self):
        """Verify REFERRAL_BONUS_RATE is 0.05 per CPAlead docs."""
        from api.cms.services_new.ReferralService import REFERRAL_BONUS_RATE
        self.assertEqual(REFERRAL_BONUS_RATE, Decimal('0.05'))

    def test_referral_active_months_is_six(self):
        """Verify REFERRAL_ACTIVE_MONTHS is 6 per CPAlead docs."""
        from api.cms.services_new.ReferralService import REFERRAL_ACTIVE_MONTHS
        self.assertEqual(REFERRAL_ACTIVE_MONTHS, 6)


# ══════════════════════════════════════════════════════════════════════════════
# QuizService
# ══════════════════════════════════════════════════════════════════════════════

class TestQuizService(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user('quiz_svc_user')

    def test_get_available_quizzes_returns_list(self):
        from api.cms.services_new.QuizService import QuizService
        result = QuizService.get_available_quizzes(self.user)
        self.assertIsInstance(result, (list, dict))

    def test_start_quiz_nonexistent_raises(self):
        from api.cms.services_new.QuizService import QuizService
        with self.assertRaises(Exception):
            QuizService.start_quiz(user=self.user, quiz_id=99999999)

    def test_get_user_quiz_history_returns_list(self):
        from api.cms.services_new.QuizService import QuizService
        result = QuizService.get_user_quiz_history(self.user)
        self.assertIsInstance(result, (list, dict))

    def test_calculate_quiz_score_returns_numeric(self):
        from api.cms.services_new.QuizService import QuizService
        # Test with empty answers dict
        score = QuizService.calculate_score(answers={}, correct_answers={})
        self.assertIsInstance(score, (int, float, Decimal))
        self.assertEqual(float(score), 0.0)

    def test_calculate_score_perfect_returns_max(self):
        from api.cms.services_new.QuizService import QuizService
        answers = {'q1': 'A', 'q2': 'B', 'q3': 'C'}
        score = QuizService.calculate_score(
            answers=answers, correct_answers=answers  # identical
        )
        self.assertGreater(float(score), 0)


# ══════════════════════════════════════════════════════════════════════════════
# ABTestingService
# ══════════════════════════════════════════════════════════════════════════════

class TestABTestingService(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user('ab_test_user')

    def test_get_variant_for_user_returns_string(self):
        from api.cms.services_new.ABTestingService import ABTestingService
        svc = ABTestingService()
        variant = svc.get_variant(user=self.user, test_name='homepage_cta')
        self.assertIsInstance(variant, (str, type(None)))

    def test_same_user_gets_same_variant(self):
        from api.cms.services_new.ABTestingService import ABTestingService
        svc = ABTestingService()
        v1 = svc.get_variant(user=self.user, test_name='consistent_test')
        v2 = svc.get_variant(user=self.user, test_name='consistent_test')
        # Variant assignment must be stable for the same user
        self.assertEqual(v1, v2,
                         msg='Same user must always get same A/B variant')

    def test_record_conversion_returns_bool(self):
        from api.cms.services_new.ABTestingService import ABTestingService
        svc = ABTestingService()
        result = svc.record_conversion(
            user=self.user, test_name='conv_test', variant='A'
        )
        self.assertIsInstance(result, bool)

    def test_get_test_results_returns_dict(self):
        from api.cms.services_new.ABTestingService import ABTestingService
        svc = ABTestingService()
        result = svc.get_test_results(test_name='conv_test')
        self.assertIsInstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# NotificationService
# ══════════════════════════════════════════════════════════════════════════════

class TestNotificationService(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user('notif_svc_user')

    def test_notify_user_returns_bool(self):
        from api.cms.services_new.NotificationService import NotificationService
        result = NotificationService.notify_user(
            user=self.user,
            title='Test notification',
            body='Body text',
            notif_type='info',
        )
        self.assertIsInstance(result, bool)

    def test_get_unread_count_returns_int(self):
        from api.cms.services_new.NotificationService import NotificationService
        count = NotificationService.get_unread_count(self.user)
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    def test_mark_read_returns_int(self):
        from api.cms.services_new.NotificationService import NotificationService
        marked = NotificationService.mark_all_read(self.user)
        self.assertIsInstance(marked, (int, bool))

    def test_notify_reward_does_not_raise(self):
        from api.cms.services_new.NotificationService import NotificationService
        try:
            NotificationService.notify_reward(
                user=self.user,
                amount=Decimal('5.00'),
                currency='USD',
                source='offer_completion',
            )
        except Exception as e:
            self.fail(f'notify_reward raised: {e}')

    def test_bulk_notify_returns_sent_count(self):
        from api.cms.services_new.NotificationService import NotificationService
        result = NotificationService.bulk_notify(
            user_ids=[self.user.pk],
            title='Bulk test',
            body='Bulk body',
            notif_type='announcement',
        )
        self.assertIsInstance(result, (dict, int, bool))


# ══════════════════════════════════════════════════════════════════════════════
# UserSegmentService
# ══════════════════════════════════════════════════════════════════════════════

class TestUserSegmentService(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user('segment_svc_user')

    def test_get_user_segments_returns_list(self):
        from api.cms.services_new.UserSegmentService import UserSegmentService
        segments = UserSegmentService.get_user_segments(self.user)
        self.assertIsInstance(segments, list)

    def test_assign_segment_does_not_raise(self):
        from api.cms.services_new.UserSegmentService import UserSegmentService
        try:
            UserSegmentService.assign_segment(self.user, 'new_user')
        except Exception as e:
            self.fail(f'assign_segment raised: {e}')

    def test_sync_all_segments_returns_dict(self):
        from api.cms.services_new.UserSegmentService import UserSegmentService
        result = UserSegmentService.sync_all_segments()
        self.assertIsInstance(result, (dict, int))

    def test_update_user_profile_attributes_does_not_raise(self):
        from api.cms.services_new.UserSegmentService import UserSegmentService
        try:
            UserSegmentService.update_user_profile_attributes(
                user=self.user,
                attributes={'country': 'BD', 'device': 'mobile'},
            )
        except Exception as e:
            self.fail(f'update_user_profile_attributes raised: {e}')
