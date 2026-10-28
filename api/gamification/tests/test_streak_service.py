"""
Streak Service Tests — Comprehensive StreakService functionality tests.

Tests all StreakService methods including streak tracking, maintenance,
reward distribution, and statistics.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from api.gamification.models import Streak, StreakReward, UserBadge, Badge
from api.gamification.exceptions import (
    GamificationServiceError,
    UserNotFoundError,
)
from api.gamification.services import StreakService
from api.gamification.tests.factories import UserFactory

User = get_user_model()
logger = logging.getLogger(__name__)


class StreakServiceTest(TestCase):
    """Test StreakService functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.today = date.today()
        
        # Create test streak rewards
        self.reward_3_days = StreakReward.objects.create(
            streak_days=3,
            points_bonus=15,
            title="3 Day Streak",
            description="Maintain streak for 3 days",
            is_active=True,
        )
        
        self.reward_7_days = StreakReward.objects.create(
            streak_days=7,
            points_bonus=50,
            title="Week Warrior",
            description="Maintain streak for 7 days",
            is_active=True,
        )
        
        self.reward_30_days = StreakReward.objects.create(
            streak_days=30,
            points_bonus=200,
            title="Month Master",
            description="Maintain streak for 30 days",
            is_active=True,
        )
        
        # Create badges for rewards
        self.badge_3_days = Badge.objects.create(
            name="3 Day Badge",
            description="3 day streak badge",
            icon="🔥",
            rarity="COMMON",
            criteria_type="STREAK_DAYS",
            criteria_value=3,
            points_bonus=15,
            is_active=True,
        )
        
        self.badge_7_days = Badge.objects.create(
            name="7 Day Badge",
            description="7 day streak badge",
            icon="⭐",
            rarity="RARE",
            criteria_type="STREAK_DAYS",
            criteria_value=7,
            points_bonus=50,
            is_active=True,
        )
        
        # Associate badges with rewards
        self.reward_3_days.badge = self.badge_3_days
        self.reward_3_days.save()
        
        self.reward_7_days.badge = self.badge_7_days
        self.reward_7_days.save()
        
        # Create inactive reward
        self.inactive_reward = StreakReward.objects.create(
            streak_days=14,
            points_bonus=100,
            title="Two Week Streak",
            description="Maintain streak for 14 days",
            is_active=False,
        )
    
    def test_get_or_create_user_streak_new(self):
        """Test creating a new user streak."""
        streak = StreakService.get_or_create_user_streak(self.user.id)
        
        self.assertEqual(streak.user, self.user)
        self.assertEqual(streak.current_days, 0)
        self.assertEqual(streak.longest_days, 0)
        self.assertTrue(streak.is_active)
        self.assertIsNone(streak.last_activity_date)
    
    def test_get_or_create_user_streak_existing(self):
        """Test getting existing user streak."""
        # Create streak first
        original_streak = Streak.objects.create(
            user=self.user,
            current_days=5,
            longest_days=5,
            last_activity_date=self.today,
            is_active=True,
        )
        
        streak = StreakService.get_or_create_user_streak(self.user.id)
        
        self.assertEqual(streak.id, original_streak.id)
        self.assertEqual(streak.current_days, 5)
        self.assertEqual(streak.longest_days, 5)
    
    def test_get_or_create_user_streak_not_found(self):
        """Test getting streak for non-existent user."""
        with self.assertRaises(UserNotFoundError):
            StreakService.get_or_create_user_streak(
                "00000000-0000-0000-0000-000000000000"
            )
    
    def test_update_user_activity_new_streak(self):
        """Test updating activity for new streak."""
        streak, was_extended, days_added = StreakService.update_user_activity(
            user_id=self.user.id,
            activity_date=self.today,
            metadata={"source": "login"}
        )
        
        self.assertEqual(streak.current_days, 1)
        self.assertEqual(streak.longest_days, 1)
        self.assertEqual(streak.last_activity_date, self.today)
        self.assertTrue(was_extended)
        self.assertEqual(days_added, 1)
        self.assertEqual(streak.metadata["last_activity"]["source"], "login")
    
    def test_update_user_activity_consecutive_days(self):
        """Test updating activity for consecutive days."""
        # First day
        streak1, was_extended1, days_added1 = StreakService.update_user_activity(
            self.user.id, self.today - timedelta(days=1)
        )
        
        # Second day (consecutive)
        streak2, was_extended2, days_added2 = StreakService.update_user_activity(
            self.user.id, self.today
        )
        
        self.assertEqual(streak2.current_days, 2)
        self.assertEqual(streak2.longest_days, 2)
        self.assertTrue(was_extended2)
        self.assertEqual(days_added2, 1)
    
    def test_update_user_activity_break_streak(self):
        """Test that missed days break the streak."""
        # Start streak
        StreakService.update_user_activity(self.user.id, self.today - timedelta(days=3))
        
        # Skip a day and update
        streak, was_extended, days_added = StreakService.update_user_activity(
            self.user.id, self.today
        )
        
        self.assertEqual(streak.current_days, 1)  # Reset to 1
        self.assertEqual(streak.longest_days, 1)  # Previous longest was 1
        self.assertFalse(was_extended)  # Streak was reset, not extended
        self.assertEqual(days_added, 1)
    
    def test_update_user_activity_same_day(self):
        """Test updating activity multiple times on same day."""
        # First update
        streak1, was_extended1, days_added1 = StreakService.update_user_activity(
            self.user.id, self.today
        )
        
        # Second update same day
        streak2, was_extended2, days_added2 = StreakService.update_user_activity(
            self.user.id, self.today
        )
        
        self.assertEqual(streak2.current_days, 1)
        self.assertFalse(was_extended2)  # No change
        self.assertEqual(days_added2, 0)
    
    def test_update_user_activity_future_date(self):
        """Test updating activity with future date."""
        future_date = self.today + timedelta(days=1)
        
        with self.assertRaises(GamificationServiceError):
            StreakService.update_user_activity(
                user_id=self.user.id,
                activity_date=future_date
            )
    
    def test_update_user_activity_user_not_found(self):
        """Test updating activity for non-existent user."""
        with self.assertRaises(UserNotFoundError):
            StreakService.update_user_activity(
                "00000000-0000-0000-0000-000000000000"
            )
    
    def test_reset_user_streak(self):
        """Test resetting user streak."""
        # Build up streak first
        streak = StreakService.get_or_create_user_streak(self.user.id)
        streak.current_days = 5
        streak.longest_days = 7
        streak.save()
        
        # Reset streak
        reset_streak = StreakService.reset_user_streak(
            user_id=self.user.id,
            reason="manual_reset"
        )
        
        self.assertEqual(reset_streak.current_days, 0)
        self.assertEqual(reset_streak.longest_days, 7)  # Longest remains
        self.assertEqual(reset_streak.metadata["reset_info"]["reason"], "manual_reset")
    
    def test_reset_user_streak_user_not_found(self):
        """Test resetting streak for non-existent user."""
        with self.assertRaises(UserNotFoundError):
            StreakService.reset_user_streak(
                "00000000-0000-0000-0000-000000000000"
            )
    
    def test_check_streak_rewards_eligible(self):
        """Test checking eligible streak rewards."""
        # Create streak with 5 days
        streak = StreakService.get_or_create_user_streak(self.user.id)
        streak.current_days = 5
        streak.save()
        
        eligible_rewards = StreakService.check_streak_rewards(
            user_id=self.user.id,
            streak_days=5
        )
        
        self.assertEqual(len(eligible_rewards), 1)
        self.assertEqual(eligible_rewards[0].id, self.reward_3_days.id)
    
    def test_check_streak_rewards_already_received(self):
        """Test checking rewards when some already received."""
        # Create streak and award 3-day badge
        streak = StreakService.get_or_create_user_streak(self.user.id)
        streak.current_days = 10
        streak.save()
        
        # Award 3-day badge
        UserBadge.objects.create(
            user=self.user,
            badge=self.badge_3_days,
            metadata={"awarded_via": "streak_milestone"}
        )
        
        eligible_rewards = StreakService.check_streak_rewards(
            user_id=self.user.id,
            streak_days=10
        )
        
        self.assertEqual(len(eligible_rewards), 1)
        self.assertEqual(eligible_rewards[0].id, self.reward_7_days.id)
    
    def test_check_streak_rewards_no_badge(self):
        """Test checking rewards for reward without badge."""
        # Create streak with 15 days
        streak = StreakService.get_or_create_user_streak(self.user.id)
        streak.current_days = 15
        streak.save()
        
        eligible_rewards = StreakService.check_streak_rewards(
            user_id=self.user.id,
            streak_days=15
        )
        
        # Should include 3-day and 7-day rewards, but not inactive 14-day reward
        self.assertEqual(len(eligible_rewards), 2)
        reward_ids = [r.id for r in eligible_rewards]
        self.assertIn(self.reward_3_days.id, reward_ids)
        self.assertIn(self.reward_7_days.id, reward_ids)
        self.assertNotIn(self.inactive_reward.id, reward_ids)
    
    def test_award_streak_rewards_multiple(self):
        """Test awarding multiple streak rewards."""
        # Create streak with 10 days
        streak = StreakService.get_or_create_user_streak(self.user.id)
        streak.current_days = 10
        streak.save()
        
        awarded_badges = StreakService.award_streak_rewards(
            user_id=self.user.id,
            streak_days=10
        )
        
        self.assertEqual(len(awarded_badges), 2)  # 3-day and 7-day badges
        
        # Verify badges were awarded
        badge_ids = [ub.badge.id for ub in awarded_badges]
        self.assertIn(self.badge_3_days.id, badge_ids)
        self.assertIn(self.badge_7_days.id, badge_ids)
        
        # Verify metadata
        for ub in awarded_badges:
            self.assertEqual(ub.metadata["awarded_via"], "streak_milestone")
            self.assertIn("streak_days", ub.metadata)
    
    def test_award_streak_rewards_already_awarded(self):
        """Test awarding rewards when some already awarded."""
        # Award 3-day badge first
        UserBadge.objects.create(
            user=self.user,
            badge=self.badge_3_days,
            metadata={"awarded_via": "streak_milestone"}
        )
        
        # Create streak with 10 days
        streak = StreakService.get_or_create_user_streak(self.user.id)
        streak.current_days = 10
        streak.save()
        
        awarded_badges = StreakService.award_streak_rewards(
            user_id=self.user.id,
            streak_days=10
        )
        
        # Should only award 7-day badge
        self.assertEqual(len(awarded_badges), 1)
        self.assertEqual(awarded_badges[0].badge.id, self.badge_7_days.id)
    
    def test_get_streak_leaderboard(self):
        """Test getting streak leaderboard."""
        # Create multiple users with different streaks
        user2 = UserFactory()
        user3 = UserFactory()
        
        # Set up streaks
        streak1 = StreakService.get_or_create_user_streak(self.user.id)
        streak1.current_days = 5
        streak1.save()
        
        streak2 = StreakService.get_or_create_user_streak(user2.id)
        streak2.current_days = 10
        streak2.save()
        
        streak3 = StreakService.get_or_create_user_streak(user3.id)
        streak3.current_days = 3
        streak3.save()
        
        leaderboard = StreakService.get_streak_leaderboard(limit=5)
        
        self.assertEqual(len(leaderboard), 3)
        self.assertEqual(leaderboard[0]["user_id"], user2.id)
        self.assertEqual(leaderboard[0]["current_days"], 10)
        self.assertEqual(leaderboard[1]["user_id"], self.user.id)
        self.assertEqual(leaderboard[1]["current_days"], 5)
        self.assertEqual(leaderboard[2]["user_id"], user3.id)
        self.assertEqual(leaderboard[2]["current_days"], 3)
    
    def test_get_streak_leaderboard_active_only(self):
        """Test getting streak leaderboard with active only filter."""
        # Create users with active and inactive streaks
        user2 = UserFactory()
        
        # Active streak
        streak1 = StreakService.get_or_create_user_streak(self.user.id)
        streak1.current_days = 5
        streak1.last_activity_date = self.today
        streak1.save()
        
        # Inactive streak (old activity)
        streak2 = StreakService.get_or_create_user_streak(user2.id)
        streak2.current_days = 10
        streak2.last_activity_date = self.today - timedelta(days=3)
        streak2.is_active = False
        streak2.save()
        
        leaderboard_active = StreakService.get_streak_leaderboard(active_only=True)
        leaderboard_all = StreakService.get_streak_leaderboard(active_only=False)
        
        self.assertEqual(len(leaderboard_active), 1)
        self.assertEqual(len(leaderboard_all), 2)
    
    def test_get_streak_statistics(self):
        """Test getting streak statistics."""
        # Create streak with activity
        streak = StreakService.get_or_create_user_streak(self.user.id)
        streak.current_days = 5
        streak.longest_days = 8
        streak.last_activity_date = self.today
        streak.save()
        
        stats = StreakService.get_streak_statistics(self.user.id)
        
        self.assertEqual(stats["current_days"], 5)
        self.assertEqual(stats["longest_days"], 8)
        self.assertTrue(stats["is_active"])
        self.assertEqual(stats["last_activity_date"], self.today)
        self.assertEqual(stats["days_until_reset"], 1)  # Tomorrow
        self.assertFalse(stats["is_expired"])
        self.assertEqual(stats["current_streak_percentage"], 62.5)  # 5/8 * 100
    
    def test_get_streak_statistics_no_activity(self):
        """Test getting streak statistics for user with no activity."""
        stats = StreakService.get_streak_statistics(self.user.id)
        
        self.assertEqual(stats["current_days"], 0)
        self.assertEqual(stats["longest_days"], 0)
        self.assertTrue(stats["is_active"])
        self.assertIsNone(stats["last_activity_date"])
        self.assertEqual(stats["days_until_reset"], 0)
        self.assertTrue(stats["is_expired"])
    
    def test_get_users_with_expiring_streaks(self):
        """Test getting users with expiring streaks."""
        # Create user with expiring streak (activity yesterday)
        expiring_user = UserFactory()
        streak1 = StreakService.get_or_create_user_streak(expiring_user.id)
        streak1.current_days = 5
        streak1.last_activity_date = self.today - timedelta(days=1)
        streak1.save()
        
        # Create user with recent activity
        recent_user = UserFactory()
        streak2 = StreakService.get_or_create_user_streak(recent_user.id)
        streak2.current_days = 3
        streak2.last_activity_date = self.today
        streak2.save()
        
        # Create user with very old activity (should not be included)
        old_user = UserFactory()
        streak3 = StreakService.get_or_create_user_streak(old_user.id)
        streak3.current_days = 2
        streak3.last_activity_date = self.today - timedelta(days=5)
        streak3.save()
        
        expiring_streaks = StreakService.get_users_with_expiring_streaks(grace_period_days=1)
        
        self.assertEqual(len(expiring_streaks), 1)
        self.assertEqual(expiring_streaks[0].user_id, expiring_user.id)
    
    def test_cleanup_expired_streaks(self):
        """Test cleaning up expired streaks."""
        # Create old inactive streak
        old_date = self.today - timedelta(days=40)
        old_streak = Streak.objects.create(
            user=self.user,
            current_days=5,
            last_activity_date=old_date,
            is_active=True,  # Still marked as active
        )
        
        # Clean up expired streaks (older than 30 days)
        cleaned_count = StreakService.cleanup_expired_streaks()
        
        self.assertEqual(cleaned_count, 1)
        old_streak.refresh_from_db()
        self.assertFalse(old_streak.is_active)
    
    def test_get_streak_milestones(self):
        """Test getting streak milestones for user."""
        # Create streak with 5 days
        streak = StreakService.get_or_create_user_streak(self.user.id)
        streak.current_days = 5
        streak.save()
        
        milestones = StreakService.get_streak_milestones(self.user.id)
        
        self.assertEqual(len(milestones), 3)  # All rewards
        
        # Check 3-day milestone (achieved)
        milestone_3 = next(m for m in milestones if m["streak_days"] == 3)
        self.assertTrue(milestone_3["achieved"])
        self.assertEqual(milestone_3["progress_percentage"], 100.0)
        
        # Check 7-day milestone (not achieved)
        milestone_7 = next(m for m in milestones if m["streak_days"] == 7)
        self.assertFalse(milestone_7["achieved"])
        self.assertEqual(milestone_7["progress_percentage"], 71.4)  # 5/7 * 100
    
    def test_get_streak_milestones_with_received_badges(self):
        """Test streak milestones when some badges already received."""
        # Award 3-day badge
        UserBadge.objects.create(
            user=self.user,
            badge=self.badge_3_days,
            metadata={"awarded_via": "streak_milestone"}
        )
        
        # Create streak with 5 days
        streak = StreakService.get_or_create_user_streak(self.user.id)
        streak.current_days = 5
        streak.save()
        
        milestones = StreakService.get_streak_milestones(self.user.id)
        
        milestone_3 = next(m for m in milestones if m["streak_days"] == 3)
        self.assertTrue(milestone_3["received"])
        self.assertTrue(milestone_3["achieved"])
        
        milestone_7 = next(m for m in milestones if m["streak_days"] == 7)
        self.assertFalse(milestone_7["received"])
        self.assertFalse(milestone_7["achieved"])


class StreakServiceTransactionTest(TransactionTestCase):
    """Test StreakService with transactions."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.reward = StreakReward.objects.create(
            streak_days=3,
            points_bonus=15,
            title="3 Day Streak",
            description="Maintain streak for 3 days",
            is_active=True,
        )
        
        self.badge = Badge.objects.create(
            name="3 Day Badge",
            description="3 day streak badge",
            icon="🔥",
            rarity="COMMON",
            criteria_type="STREAK_DAYS",
            criteria_value=3,
            points_bonus=15,
            is_active=True,
        )
        
        self.reward.badge = self.badge
        self.reward.save()
    
    @patch('api.gamification.services.StreakService.streak_updated')
    def test_update_activity_sends_signal(self, mock_signal):
        """Test that updating streak activity sends the appropriate signal."""
        mock_signal.send = MagicMock()
        
        streak, was_extended, days_added = StreakService.update_user_activity(self.user.id)
        
        # Verify signal was sent
        mock_signal.send.assert_called_once()
        call_args = mock_signal.send.call_args
        self.assertEqual(call_args[1]['user_id'], self.user.id)
        self.assertEqual(call_args[1]['streak_days'], 1)
        self.assertEqual(call_args[1]['was_extended'], True)
    
    @patch('api.gamification.services.StreakService.badge_earned')
    def test_award_streak_rewards_sends_signal(self, mock_signal):
        """Test that awarding streak rewards sends badge earned signal."""
        mock_signal.send = MagicMock()
        
        # Create streak with 5 days
        streak = StreakService.get_or_create_user_streak(self.user.id)
        streak.current_days = 5
        streak.save()
        
        # Award rewards
        awarded_badges = StreakService.award_streak_rewards(self.user.id, 5)
        
        # Verify signal was sent for each badge
        self.assertEqual(mock_signal.send.call_count, 1)
        call_args = mock_signal.send.call_args
        self.assertEqual(call_args[1]['user_id'], self.user.id)
        self.assertEqual(call_args[1]['badge_id'], self.badge.id)
        self.assertEqual(call_args[1]['user_badge_id'], awarded_badges[0].id)
    
    def test_award_streak_rewards_atomic(self):
        """Test that awarding streak rewards is atomic."""
        # Create streak with 10 days
        streak = StreakService.get_or_create_user_streak(self.user.id)
        streak.current_days = 10
        streak.save()
        
        # Award rewards
        awarded_badges = StreakService.award_streak_rewards(self.user.id, 10)
        
        # Verify all badges were created in the same transaction
        self.assertEqual(len(awarded_badges), 1)
        self.assertEqual(awarded_badges[0].user, self.user)
        self.assertEqual(awarded_badges[0].badge, self.badge)
