"""
Daily Challenge Service Tests — Comprehensive DailyChallengeService functionality tests.

Tests all DailyChallengeService methods including challenge creation,
progress tracking, completion, and statistics.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from api.gamification.models import DailyChallenge, UserDailyChallenge
from api.gamification.choices import ChallengeAction
from api.gamification.exceptions import (
    GamificationServiceError,
    UserNotFoundError,
    DuplicateAchievementError,
)
from api.gamification.services import DailyChallengeService
from api.gamification.tests.factories import UserFactory

User = get_user_model()
logger = logging.getLogger(__name__)


class DailyChallengeServiceTest(TestCase):
    """Test DailyChallengeService functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.today = date.today()
        
        # Create test challenges
        self.login_challenge = DailyChallenge.objects.create(
            title="Daily Login",
            description="Log in once today",
            target_action=ChallengeAction.LOGIN,
            target_count=1,
            bonus_points=10,
            date=self.today,
            is_active=True,
        )
        
        self.post_challenge = DailyChallenge.objects.create(
            title="Post Creator",
            description="Create 3 posts",
            target_action=ChallengeAction.POST,
            target_count=3,
            bonus_points=25,
            date=self.today,
            is_active=True,
        )
        
        self.yesterday_challenge = DailyChallenge.objects.create(
            title="Yesterday's Challenge",
            description="Old challenge",
            target_action=ChallengeAction.LOGIN,
            target_count=1,
            bonus_points=5,
            date=self.today - timedelta(days=1),
            is_active=True,
        )
        
        self.inactive_challenge = DailyChallenge.objects.create(
            title="Inactive Challenge",
            description="Not active",
            target_action=ChallengeAction.LOGIN,
            target_count=1,
            bonus_points=15,
            date=self.today,
            is_active=False,
        )
    
    def test_create_daily_challenge_success(self):
        """Test successful daily challenge creation."""
        challenge = DailyChallengeService.create_daily_challenge(
            title="Comment Master",
            description="Make 5 comments",
            target_action=ChallengeAction.COMMENT,
            target_count=5,
            bonus_points=20,
            challenge_date=self.today + timedelta(days=1),
            metadata={"difficulty": "medium"},
        )
        
        self.assertEqual(challenge.title, "Comment Master")
        self.assertEqual(challenge.target_action, ChallengeAction.COMMENT)
        self.assertEqual(challenge.target_count, 5)
        self.assertEqual(challenge.bonus_points, 20)
        self.assertEqual(challenge.date, self.today + timedelta(days=1))
        self.assertEqual(challenge.metadata["difficulty"], "medium")
    
    def test_create_daily_challenge_validation_errors(self):
        """Test daily challenge creation validation."""
        # Empty title
        with self.assertRaises(GamificationServiceError):
            DailyChallengeService.create_daily_challenge(
                title="",
                description="Test",
                target_action=ChallengeAction.LOGIN,
                target_count=1,
                bonus_points=10,
            )
        
        # Invalid target action
        with self.assertRaises(GamificationServiceError):
            DailyChallengeService.create_daily_challenge(
                title="Test",
                description="Test",
                target_action="INVALID_ACTION",
                target_count=1,
                bonus_points=10,
            )
        
        # Invalid target count
        with self.assertRaises(GamificationServiceError):
            DailyChallengeService.create_daily_challenge(
                title="Test",
                description="Test",
                target_action=ChallengeAction.LOGIN,
                target_count=0,
                bonus_points=10,
            )
        
        # Invalid bonus points
        with self.assertRaises(GamificationServiceError):
            DailyChallengeService.create_daily_challenge(
                title="Test",
                description="Test",
                target_action=ChallengeAction.LOGIN,
                target_count=1,
                bonus_points=-5,
            )
        
        # Duplicate challenge for same date and action
        with self.assertRaises(GamificationServiceError):
            DailyChallengeService.create_daily_challenge(
                title="Duplicate",
                description="Duplicate challenge",
                target_action=ChallengeAction.LOGIN,
                target_count=1,
                bonus_points=10,
                challenge_date=self.today,
            )
    
    def test_get_active_challenges_today(self):
        """Test getting active challenges for today."""
        challenges = DailyChallengeService.get_active_challenges()
        
        self.assertEqual(len(challenges), 2)  # login and post challenges
        challenge_ids = [c.id for c in challenges]
        self.assertIn(self.login_challenge.id, challenge_ids)
        self.assertIn(self.post_challenge.id, challenge_ids)
        self.assertNotIn(self.yesterday_challenge.id, challenge_ids)
        self.assertNotIn(self.inactive_challenge.id, challenge_ids)
    
    def test_get_active_challenges_specific_date(self):
        """Test getting active challenges for specific date."""
        challenges = DailyChallengeService.get_active_challenges(
            challenge_date=self.yesterday_challenge.date
        )
        
        self.assertEqual(len(challenges), 1)
        self.assertEqual(challenges[0].id, self.yesterday_challenge.id)
    
    def test_get_active_challenges_filtered_by_action(self):
        """Test getting active challenges filtered by action type."""
        challenges = DailyChallengeService.get_active_challenges(
            target_action=ChallengeAction.LOGIN
        )
        
        self.assertEqual(len(challenges), 1)
        self.assertEqual(challenges[0].id, self.login_challenge.id)
    
    def test_get_user_challenge_progress_all(self):
        """Test getting all user challenge progress."""
        # Start some challenges
        DailyChallengeService.start_user_challenge(self.user.id, self.login_challenge.id)
        DailyChallengeService.start_user_challenge(self.user.id, self.post_challenge.id)
        
        progress = DailyChallengeService.get_user_challenge_progress(self.user.id)
        
        self.assertEqual(len(progress), 2)
        challenge_ids = [p.challenge.id for p in progress]
        self.assertIn(self.login_challenge.id, challenge_ids)
        self.assertIn(self.post_challenge.id, challenge_ids)
    
    def test_get_user_challenge_progress_specific_challenge(self):
        """Test getting progress for specific challenge."""
        # Start a challenge
        user_challenge = DailyChallengeService.start_user_challenge(
            self.user.id, self.login_challenge.id
        )
        
        progress = DailyChallengeService.get_user_challenge_progress(
            user_id=self.user.id,
            challenge_id=self.login_challenge.id
        )
        
        self.assertEqual(len(progress), 1)
        self.assertEqual(progress[0].id, user_challenge.id)
    
    def test_get_user_challenge_progress_specific_date(self):
        """Test getting progress for specific date."""
        # Start today's challenge
        DailyChallengeService.start_user_challenge(self.user.id, self.login_challenge.id)
        
        progress = DailyChallengeService.get_user_challenge_progress(
            user_id=self.user.id,
            challenge_date=self.today
        )
        
        self.assertEqual(len(progress), 1)
        self.assertEqual(progress[0].challenge.id, self.login_challenge.id)
    
    def test_get_user_challenge_progress_user_not_found(self):
        """Test getting progress for non-existent user."""
        with self.assertRaises(UserNotFoundError):
            DailyChallengeService.get_user_challenge_progress(
                user_id="00000000-0000-0000-0000-000000000000"
            )
    
    def test_start_user_challenge_success(self):
        """Test successful user challenge start."""
        user_challenge = DailyChallengeService.start_user_challenge(
            user_id=self.user.id,
            challenge_id=self.login_challenge.id
        )
        
        self.assertEqual(user_challenge.user, self.user)
        self.assertEqual(user_challenge.challenge, self.login_challenge)
        self.assertEqual(user_challenge.progress, 0)
        self.assertFalse(user_challenge.is_completed)
        self.assertIsNone(user_challenge.completed_at)
    
    def test_start_user_challenge_already_started(self):
        """Test starting a challenge that's already started."""
        # Start challenge first
        DailyChallengeService.start_user_challenge(self.user.id, self.login_challenge.id)
        
        # Try to start again
        with self.assertRaises(DuplicateAchievementError):
            DailyChallengeService.start_user_challenge(
                user_id=self.user.id,
                challenge_id=self.login_challenge.id
            )
    
    def test_start_user_challenge_not_found(self):
        """Test starting non-existent challenge."""
        with self.assertRaises(GamificationServiceError):
            DailyChallengeService.start_user_challenge(
                user_id=self.user.id,
                challenge_id="00000000-0000-0000-0000-000000000000"
            )
    
    def test_start_user_challenge_inactive(self):
        """Test starting inactive challenge."""
        with self.assertRaises(GamificationServiceError):
            DailyChallengeService.start_user_challenge(
                user_id=self.user.id,
                challenge_id=self.inactive_challenge.id
            )
    
    def test_update_challenge_progress_success(self):
        """Test successful challenge progress update."""
        # Start challenge
        user_challenge = DailyChallengeService.start_user_challenge(
            self.user.id, self.post_challenge.id
        )
        
        # Update progress
        updated_challenge, completed = DailyChallengeService.update_challenge_progress(
            user_id=self.user.id,
            challenge_id=self.post_challenge.id,
            increment_amount=2,
            action_metadata={"source": "api"}
        )
        
        self.assertEqual(updated_challenge.progress, 2)
        self.assertFalse(completed)
        self.assertEqual(updated_challenge.metadata["last_increment"], 2)
        self.assertEqual(updated_challenge.metadata["last_action"]["source"], "api")
    
    def test_update_challenge_progress_completion(self):
        """Test challenge progress completion."""
        # Start challenge
        user_challenge = DailyChallengeService.start_user_challenge(
            self.user.id, self.login_challenge.id
        )
        
        # Complete challenge
        updated_challenge, completed = DailyChallengeService.update_challenge_progress(
            user_id=self.user.id,
            challenge_id=self.login_challenge.id,
            increment_amount=1
        )
        
        self.assertEqual(updated_challenge.progress, 1)
        self.assertTrue(completed)
        self.assertIsNotNone(updated_challenge.completed_at)
        self.assertTrue(updated_challenge.is_completed)
    
    def test_update_challenge_progress_not_started(self):
        """Test updating progress for challenge not started."""
        with self.assertRaises(GamificationServiceError):
            DailyChallengeService.update_challenge_progress(
                user_id=self.user.id,
                challenge_id=self.login_challenge.id,
                increment_amount=1
            )
    
    def test_update_challenge_progress_invalid_increment(self):
        """Test updating progress with invalid increment amount."""
        # Start challenge
        DailyChallengeService.start_user_challenge(self.user.id, self.login_challenge.id)
        
        # Try invalid increment
        with self.assertRaises(GamificationServiceError):
            DailyChallengeService.update_challenge_progress(
                user_id=self.user.id,
                challenge_id=self.login_challenge.id,
                increment_amount=0
            )
    
    def test_auto_start_active_challenges(self):
        """Test auto-starting all active challenges."""
        started_challenges = DailyChallengeService.auto_start_active_challenges(self.user.id)
        
        self.assertEqual(len(started_challenges), 2)  # login and post challenges
        challenge_ids = [uc.challenge.id for uc in started_challenges]
        self.assertIn(self.login_challenge.id, challenge_ids)
        self.assertIn(self.post_challenge.id, challenge_ids)
        
        # Verify challenges are actually started
        for uc in started_challenges:
            self.assertEqual(uc.user, self.user)
            self.assertEqual(uc.progress, 0)
    
    def test_auto_start_active_challenges_already_started(self):
        """Test auto-starting when some challenges already started."""
        # Start one challenge manually
        DailyChallengeService.start_user_challenge(self.user.id, self.login_challenge.id)
        
        # Auto-start all
        started_challenges = DailyChallengeService.auto_start_active_challenges(self.user.id)
        
        # Should only start the new one
        self.assertEqual(len(started_challenges), 1)
        self.assertEqual(started_challenges[0].challenge.id, self.post_challenge.id)
    
    def test_get_challenge_statistics(self):
        """Test getting challenge statistics."""
        # Start and complete some challenges
        uc1 = DailyChallengeService.start_user_challenge(self.user.id, self.login_challenge.id)
        DailyChallengeService.update_challenge_progress(self.user.id, self.login_challenge.id, 1)
        
        uc2 = DailyChallengeService.start_user_challenge(self.user.id, self.post_challenge.id)
        DailyChallengeService.update_challenge_progress(self.user.id, self.post_challenge.id, 2)
        
        stats = DailyChallengeService.get_challenge_statistics(self.user.id, days=30)
        
        self.assertEqual(stats["period_days"], 30)
        self.assertEqual(stats["total_challenges"], 2)
        self.assertEqual(stats["completed_challenges"], 1)
        self.assertEqual(stats["completion_rate"], 50.0)
        self.assertEqual(stats["total_bonus_points"], 10)  # Only completed challenge
        self.assertIn(ChallengeAction.LOGIN, stats["by_action_type"])
        self.assertIn(ChallengeAction.POST, stats["by_action_type"])
    
    def test_get_challenge_statistics_no_challenges(self):
        """Test getting statistics for user with no challenges."""
        stats = DailyChallengeService.get_challenge_statistics(self.user.id)
        
        self.assertEqual(stats["total_challenges"], 0)
        self.assertEqual(stats["completed_challenges"], 0)
        self.assertEqual(stats["completion_rate"], 0)
        self.assertEqual(stats["total_bonus_points"], 0)
    
    def test_get_leaderboard(self):
        """Test getting challenge leaderboard."""
        # Create another user and complete challenges
        user2 = UserFactory()
        
        # Complete challenges for both users
        uc1 = DailyChallengeService.start_user_challenge(self.user.id, self.login_challenge.id)
        DailyChallengeService.update_challenge_progress(self.user.id, self.login_challenge.id, 1)
        
        uc2 = DailyChallengeService.start_user_challenge(user2.id, self.login_challenge.id)
        DailyChallengeService.update_challenge_progress(user2.id, self.login_challenge.id, 1)
        
        uc3 = DailyChallengeService.start_user_challenge(user2.id, self.post_challenge.id)
        DailyChallengeService.update_challenge_progress(user2.id, self.post_challenge.id, 3)
        
        leaderboard = DailyChallengeService.get_leaderboard(limit=10)
        
        self.assertEqual(len(leaderboard), 2)
        self.assertEqual(leaderboard[0]["username"], user2.username)
        self.assertEqual(leaderboard[0]["completed_challenges"], 2)
        self.assertEqual(leaderboard[1]["username"], self.user.username)
        self.assertEqual(leaderboard[1]["completed_challenges"], 1)
    
    def test_deactivate_expired_challenges(self):
        """Test deactivating expired challenges."""
        # Create old challenge
        old_date = self.today - timedelta(days=10)
        old_challenge = DailyChallenge.objects.create(
            title="Old Challenge",
            description="Very old challenge",
            target_action=ChallengeAction.LOGIN,
            target_count=1,
            bonus_points=5,
            date=old_date,
            is_active=True,
        )
        
        # Deactivate expired challenges
        deactivated_count = DailyChallengeService.deactivate_expired_challenges()
        
        self.assertEqual(deactivated_count, 1)
        old_challenge.refresh_from_db()
        self.assertFalse(old_challenge.is_active)
        
        # Recent challenges should remain active
        self.login_challenge.refresh_from_db()
        self.assertTrue(self.login_challenge.is_active)


class DailyChallengeServiceTransactionTest(TransactionTestCase):
    """Test DailyChallengeService with transactions."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.challenge = DailyChallenge.objects.create(
            title="Test Challenge",
            description="Test description",
            target_action=ChallengeAction.LOGIN,
            target_count=1,
            bonus_points=10,
            date=date.today(),
            is_active=True,
        )
    
    @patch('api.gamification.services.DailyChallengeService.daily_challenge_completed')
    def test_update_progress_sends_signal(self, mock_signal):
        """Test that completing a challenge sends the appropriate signal."""
        mock_signal.send = MagicMock()
        
        # Start and complete challenge
        DailyChallengeService.start_user_challenge(self.user.id, self.challenge.id)
        updated_challenge, completed = DailyChallengeService.update_challenge_progress(
            self.user.id, self.challenge.id, 1
        )
        
        # Verify signal was sent only on completion
        mock_signal.send.assert_called_once()
        call_args = mock_signal.send.call_args
        self.assertEqual(call_args[1]['user_id'], self.user.id)
        self.assertEqual(call_args[1]['challenge_id'], self.challenge.id)
        self.assertEqual(call_args[1]['user_challenge_id'], updated_challenge.id)
    
    def test_update_progress_no_signal_on_partial_progress(self):
        """Test that partial progress doesn't send completion signal."""
        with patch('api.gamification.services.DailyChallengeService.daily_challenge_completed') as mock_signal:
            # Start challenge with target > 1
            multi_challenge = DailyChallenge.objects.create(
                title="Multi Challenge",
                description="Multiple actions required",
                target_action=ChallengeAction.POST,
                target_count=3,
                bonus_points=20,
                date=date.today(),
                is_active=True,
            )
            
            DailyChallengeService.start_user_challenge(self.user.id, multi_challenge.id)
            DailyChallengeService.update_challenge_progress(self.user.id, multi_challenge.id, 1)
            
            # Should not send signal for partial progress
            mock_signal.send.assert_not_called()
    
    def test_auto_start_atomic(self):
        """Test that auto-starting challenges is atomic."""
        # Create a challenge that will fail
        failing_challenge = DailyChallenge.objects.create(
            title="Failing Challenge",
            description="This will fail",
            target_action=ChallengeAction.LOGIN,
            target_count=1,
            bonus_points=10,
            date=date.today(),
            is_active=True,
        )
        
        # Start one challenge manually
        DailyChallengeService.start_user_challenge(self.user.id, self.challenge.id)
        
        # Auto-start should work despite one already being started
        started_challenges = DailyChallengeService.auto_start_active_challenges(self.user.id)
        
        # Should start the new challenge
        self.assertEqual(len(started_challenges), 1)
        self.assertEqual(started_challenges[0].challenge.id, failing_challenge.id)
