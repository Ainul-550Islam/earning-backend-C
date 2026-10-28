"""
Models Tests — Comprehensive model functionality tests.

Tests all new gamification models including Badge, UserBadge, DailyChallenge,
UserDailyChallenge, Streak, StreakReward, and LevelConfig models.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from api.gamification.models import (
    Badge, UserBadge, DailyChallenge, UserDailyChallenge,
    Streak, StreakReward, LevelConfig
)
from api.gamification.choices import (
    BadgeRarity, BadgeCriteriaType, ChallengeAction,
    ChallengeStatus, StreakStatus
)
from api.gamification.tests.factories import UserFactory

User = get_user_model()


class BadgeModelTest(TestCase):
    """Test Badge model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.badge = Badge.objects.create(
            name="Test Badge",
            description="A test badge",
            icon="🎯",
            rarity=BadgeRarity.COMMON,
            criteria_type=BadgeCriteriaType.POINTS_THRESHOLD,
            criteria_value=100,
            points_bonus=10,
            is_active=True,
            sort_order=1,
        )
    
    def test_badge_creation(self):
        """Test successful badge creation."""
        self.assertEqual(self.badge.name, "Test Badge")
        self.assertEqual(self.badge.rarity, BadgeRarity.COMMON)
        self.assertEqual(self.badge.criteria_type, BadgeCriteriaType.POINTS_THRESHOLD)
        self.assertEqual(self.badge.criteria_value, 100)
        self.assertEqual(self.badge.points_bonus, 10)
        self.assertTrue(self.badge.is_active)
        self.assertIsNotNone(self.badge.checksum)
    
    def test_badge_str_representation(self):
        """Test badge string representation."""
        self.assertEqual(str(self.badge), "Test Badge")
    
    def test_badge_is_unlocked_by_user_points_threshold(self):
        """Test badge unlocking logic for points threshold."""
        # User with enough points
        self.assertTrue(self.badge.is_unlocked_by_user(user_points=150, streak_days=0))
        
        # User without enough points
        self.assertFalse(self.badge.is_unlocked_by_user(user_points=50, streak_days=0))
    
    def test_badge_is_unlocked_by_user_streak_days(self):
        """Test badge unlocking logic for streak days."""
        streak_badge = Badge.objects.create(
            name="Streak Badge",
            description="Streak achievement",
            icon="🔥",
            rarity=BadgeRarity.UNCOMMON,
            criteria_type=BadgeCriteriaType.STREAK_DAYS,
            criteria_value=7,
            points_bonus=25,
            is_active=True,
            sort_order=2,
        )
        
        # User with enough streak days
        self.assertTrue(streak_badge.is_unlocked_by_user(user_points=0, streak_days=10))
        
        # User without enough streak days
        self.assertFalse(streak_badge.is_unlocked_by_user(user_points=0, streak_days=5))
    
    def test_badge_is_unlocked_by_user_achievement_count(self):
        """Test badge unlocking logic for achievement count."""
        achievement_badge = Badge.objects.create(
            name="Achievement Badge",
            description="Multiple achievements",
            icon="🏆",
            rarity=BadgeRarity.RARE,
            criteria_type=BadgeCriteriaType.ACHIEVEMENT_COUNT,
            criteria_value=5,
            points_bonus=50,
            is_active=True,
            sort_order=3,
        )
        
        # User with enough achievements
        self.assertTrue(achievement_badge.is_unlocked_by_user(user_points=0, streak_days=0, achievement_count=10))
        
        # User without enough achievements
        self.assertFalse(achievement_badge.is_unlocked_by_user(user_points=0, streak_days=0, achievement_count=3))
    
    def test_badge_is_unlocked_by_user_contest_wins(self):
        """Test badge unlocking logic for contest wins."""
        contest_badge = Badge.objects.create(
            name="Contest Winner",
            description="Contest achievements",
            icon="🥇",
            rarity=BadgeRarity.EPIC,
            criteria_type=BadgeCriteriaType.CONTEST_WINS,
            criteria_value=3,
            points_bonus=100,
            is_active=True,
            sort_order=4,
        )
        
        # User with enough contest wins
        self.assertTrue(contest_badge.is_unlocked_by_user(user_points=0, streak_days=0, contest_wins=5))
        
        # User without enough contest wins
        self.assertFalse(contest_badge.is_unlocked_by_user(user_points=0, streak_days=0, contest_wins=2))
    
    def test_badge_is_unlocked_by_user_referral_count(self):
        """Test badge unlocking logic for referral count."""
        referral_badge = Badge.objects.create(
            name="Referral Master",
            description="Referral achievements",
            icon="👥",
            rarity=BadgeRarity.LEGENDARY,
            criteria_type=BadgeCriteriaType.REFERRAL_COUNT,
            criteria_value=10,
            points_bonus=200,
            is_active=True,
            sort_order=5,
        )
        
        # User with enough referrals
        self.assertTrue(referral_badge.is_unlocked_by_user(user_points=0, streak_days=0, referral_count=15))
        
        # User without enough referrals
        self.assertFalse(referral_badge.is_unlocked_by_user(user_points=0, streak_days=0, referral_count=8))
    
    def test_badge_checksum_generation(self):
        """Test badge checksum generation."""
        original_checksum = self.badge.checksum
        
        # Modify badge
        self.badge.points_bonus = 20
        self.badge.save()
        
        # Checksum should change
        self.assertNotEqual(self.badge.checksum, original_checksum)
    
    def test_badge_ordering(self):
        """Test badge ordering by sort_order and name."""
        # Create badges with different sort orders
        badge_a = Badge.objects.create(
            name="A Badge",
            description="First in alphabet",
            icon="🔤",
            rarity=BadgeRarity.COMMON,
            criteria_type=BadgeCriteriaType.POINTS_THRESHOLD,
            criteria_value=50,
            points_bonus=5,
            is_active=True,
            sort_order=1,
        )
        
        badge_b = Badge.objects.create(
            name="B Badge",
            description="Second in alphabet",
            icon="🔤",
            rarity=BadgeRarity.COMMON,
            criteria_type=BadgeCriteriaType.POINTS_THRESHOLD,
            criteria_value=60,
            points_bonus=6,
            is_active=True,
            sort_order=1,
        )
        
        badge_c = Badge.objects.create(
            name="C Badge",
            description="Third in alphabet",
            icon="🔤",
            rarity=BadgeRarity.COMMON,
            criteria_type=BadgeCriteriaType.POINTS_THRESHOLD,
            criteria_value=70,
            points_bonus=7,
            is_active=True,
            sort_order=2,
        )
        
        # Get all badges ordered
        badges = Badge.objects.all()
        
        # Should be ordered by sort_order first, then name
        self.assertEqual(badges[0].name, "A Badge")
        self.assertEqual(badges[1].name, "B Badge")
        self.assertEqual(badges[2].name, "C Badge")


class UserBadgeModelTest(TestCase):
    """Test UserBadge model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.badge = Badge.objects.create(
            name="Test Badge",
            description="A test badge",
            icon="🎯",
            rarity=BadgeRarity.COMMON,
            criteria_type=BadgeCriteriaType.POINTS_THRESHOLD,
            criteria_value=100,
            points_bonus=10,
            is_active=True,
            sort_order=1,
        )
        
        self.user_badge = UserBadge.objects.create(
            user=self.user,
            badge=self.badge,
        )
    
    def test_user_badge_creation(self):
        """Test successful user badge creation."""
        self.assertEqual(self.user_badge.user, self.user)
        self.assertEqual(self.user_badge.badge, self.badge)
        self.assertIsNotNone(self.user_badge.earned_at)
        self.assertFalse(self.user_badge.is_pinned)
        self.assertIsNotNone(self.user_badge.checksum)
    
    def test_user_badge_str_representation(self):
        """Test user badge string representation."""
        expected = f"{self.user.username} - {self.badge.name}"
        self.assertEqual(str(self.user_badge), expected)
    
    def test_user_badge_unique_constraint(self):
        """Test that user cannot earn same badge twice."""
        with self.assertRaises(Exception):  # Should raise IntegrityError
            UserBadge.objects.create(
                user=self.user,
                badge=self.badge,
            )
    
    def test_user_badge_pin_unpin(self):
        """Test pinning and unpinning user badges."""
        # Pin badge
        self.user_badge.is_pinned = True
        self.user_badge.save()
        
        self.assertTrue(self.user_badge.is_pinned)
        
        # Unpin badge
        self.user_badge.is_pinned = False
        self.user_badge.save()
        
        self.assertFalse(self.user_badge.is_pinned)
    
    def test_user_badge_checksum_generation(self):
        """Test user badge checksum generation."""
        original_checksum = self.user_badge.checksum
        
        # Modify user badge
        self.user_badge.is_pinned = True
        self.user_badge.save()
        
        # Checksum should change
        self.assertNotEqual(self.user_badge.checksum, original_checksum)


class DailyChallengeModelTest(TestCase):
    """Test DailyChallenge model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.today = date.today()
        self.challenge = DailyChallenge.objects.create(
            title="Daily Login",
            description="Log in once today",
            target_action=ChallengeAction.LOGIN,
            target_count=1,
            bonus_points=10,
            date=self.today,
            is_active=True,
        )
    
    def test_daily_challenge_creation(self):
        """Test successful daily challenge creation."""
        self.assertEqual(self.challenge.title, "Daily Login")
        self.assertEqual(self.challenge.target_action, ChallengeAction.LOGIN)
        self.assertEqual(self.challenge.target_count, 1)
        self.assertEqual(self.challenge.bonus_points, 10)
        self.assertEqual(self.challenge.date, self.today)
        self.assertTrue(self.challenge.is_active)
        self.assertIsNotNone(self.challenge.checksum)
    
    def test_daily_challenge_str_representation(self):
        """Test daily challenge string representation."""
        expected = f"{self.challenge.title} ({self.challenge.date})"
        self.assertEqual(str(self.challenge), expected)
    
    def test_daily_challenge_unique_constraint(self):
        """Test that challenge must be unique per date and action."""
        with self.assertRaises(Exception):  # Should raise IntegrityError
            DailyChallenge.objects.create(
                title="Duplicate Login",
                description="Another login challenge",
                target_action=ChallengeAction.LOGIN,
                target_count=1,
                bonus_points=5,
                date=self.today,
                is_active=True,
            )
    
    def test_daily_challenge_checksum_generation(self):
        """Test daily challenge checksum generation."""
        original_checksum = self.challenge.checksum
        
        # Modify challenge
        self.challenge.bonus_points = 15
        self.challenge.save()
        
        # Checksum should change
        self.assertNotEqual(self.challenge.checksum, original_checksum)


class UserDailyChallengeModelTest(TestCase):
    """Test UserDailyChallenge model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.today = date.today()
        
        self.challenge = DailyChallenge.objects.create(
            title="Daily Login",
            description="Log in once today",
            target_action=ChallengeAction.LOGIN,
            target_count=1,
            bonus_points=10,
            date=self.today,
            is_active=True,
        )
        
        self.user_challenge = UserDailyChallenge.objects.create(
            user=self.user,
            challenge=self.challenge,
        )
    
    def test_user_daily_challenge_creation(self):
        """Test successful user daily challenge creation."""
        self.assertEqual(self.user_challenge.user, self.user)
        self.assertEqual(self.user_challenge.challenge, self.challenge)
        self.assertEqual(self.user_challenge.progress, 0)
        self.assertFalse(self.user_challenge.is_completed)
        self.assertIsNone(self.user_challenge.completed_at)
        self.assertIsNotNone(self.user_challenge.checksum)
    
    def test_user_daily_challenge_str_representation(self):
        """Test user daily challenge string representation."""
        expected = f"{self.user.username} - {self.challenge.title}"
        self.assertEqual(str(self.user_challenge), expected)
    
    def test_increment_progress(self):
        """Test incrementing challenge progress."""
        # Increment progress
        was_completed = self.user_challenge.increment_progress(1)
        
        self.assertEqual(self.user_challenge.progress, 1)
        self.assertTrue(was_completed)
        self.assertTrue(self.user_challenge.is_completed)
        self.assertIsNotNone(self.user_challenge.completed_at)
    
    def test_increment_progress_partial(self):
        """Test incrementing progress partially."""
        # Create challenge with higher target
        multi_challenge = DailyChallenge.objects.create(
            title="Multi Challenge",
            description="Multiple actions required",
            target_action=ChallengeAction.POST,
            target_count=3,
            bonus_points=20,
            date=self.today,
            is_active=True,
        )
        
        user_challenge = UserDailyChallenge.objects.create(
            user=self.user,
            challenge=multi_challenge,
        )
        
        # Increment partially
        was_completed = user_challenge.increment_progress(1)
        
        self.assertEqual(user_challenge.progress, 1)
        self.assertFalse(was_completed)
        self.assertFalse(user_challenge.is_completed)
        self.assertIsNone(user_challenge.completed_at)
    
    def test_increment_progress_completion(self):
        """Test completing challenge with progress increment."""
        # Create challenge with target > 1
        multi_challenge = DailyChallenge.objects.create(
            title="Multi Challenge",
            description="Multiple actions required",
            target_action=ChallengeAction.POST,
            target_count=3,
            bonus_points=20,
            date=self.today,
            is_active=True,
        )
        
        user_challenge = UserDailyChallenge.objects.create(
            user=self.user,
            challenge=multi_challenge,
        )
        
        # Complete challenge
        was_completed = user_challenge.increment_progress(3)
        
        self.assertEqual(user_challenge.progress, 3)
        self.assertTrue(was_completed)
        self.assertTrue(user_challenge.is_completed)
        self.assertIsNotNone(user_challenge.completed_at)
    
    def test_increment_progress_over_completion(self):
        """Test incrementing progress beyond completion."""
        # Complete challenge first
        self.user_challenge.increment_progress(1)
        
        # Try to increment again
        was_completed = self.user_challenge.increment_progress(1)
        
        self.assertEqual(self.user_challenge.progress, 1)  # Should not exceed target
        self.assertTrue(was_completed)  # Still completed
    
    def test_progress_percentage(self):
        """Test progress percentage calculation."""
        # Create challenge with target > 1
        multi_challenge = DailyChallenge.objects.create(
            title="Multi Challenge",
            description="Multiple actions required",
            target_action=ChallengeAction.POST,
            target_count=4,
            bonus_points=20,
            date=self.today,
            is_active=True,
        )
        
        user_challenge = UserDailyChallenge.objects.create(
            user=self.user,
            challenge=multi_challenge,
        )
        
        # Check initial percentage
        self.assertEqual(user_challenge.progress_percentage, 0.0)
        
        # Increment progress
        user_challenge.increment_progress(1)
        self.assertEqual(user_challenge.progress_percentage, 25.0)
        
        # Complete challenge
        user_challenge.increment_progress(3)
        self.assertEqual(user_challenge.progress_percentage, 100.0)
    
    def test_user_daily_challenge_unique_constraint(self):
        """Test that user cannot start same challenge twice."""
        with self.assertRaises(Exception):  # Should raise IntegrityError
            UserDailyChallenge.objects.create(
                user=self.user,
                challenge=self.challenge,
            )
    
    def test_user_daily_challenge_checksum_generation(self):
        """Test user daily challenge checksum generation."""
        original_checksum = self.user_challenge.checksum
        
        # Modify user challenge
        self.user_challenge.increment_progress(1)
        
        # Checksum should change
        self.assertNotEqual(self.user_challenge.checksum, original_checksum)


class StreakModelTest(TestCase):
    """Test Streak model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.today = date.today()
        
        self.streak = Streak.objects.create(
            user=self.user,
            current_days=5,
            longest_days=7,
            last_activity_date=self.today,
            is_active=True,
        )
    
    def test_streak_creation(self):
        """Test successful streak creation."""
        self.assertEqual(self.streak.user, self.user)
        self.assertEqual(self.streak.current_days, 5)
        self.assertEqual(self.streak.longest_days, 7)
        self.assertEqual(self.streak.last_activity_date, self.today)
        self.assertTrue(self.streak.is_active)
        self.assertIsNotNone(self.streak.checksum)
    
    def test_streak_str_representation(self):
        """Test streak string representation."""
        expected = f"{self.user.username} - {self.streak.current_days} days"
        self.assertEqual(str(self.streak), expected)
    
    def test_update_activity_consecutive(self):
        """Test updating streak activity for consecutive days."""
        # Update activity for next day
        tomorrow = self.today + timedelta(days=1)
        was_extended, days_added = self.streak.update_activity(tomorrow)
        
        self.assertEqual(self.streak.current_days, 6)
        self.assertEqual(self.streak.longest_days, 7)  # Still 7
        self.assertEqual(self.streak.last_activity_date, tomorrow)
        self.assertTrue(was_extended)
        self.assertEqual(days_added, 1)
    
    def test_update_activity_break_streak(self):
        """Test updating streak activity that breaks the streak."""
        # Update activity with gap (skip a day)
        future_date = self.today + timedelta(days=2)
        was_extended, days_added = self.streak.update_activity(future_date)
        
        self.assertEqual(self.streak.current_days, 1)  # Reset to 1
        self.assertEqual(self.streak.longest_days, 7)  # Preserved
        self.assertEqual(self.streak.last_activity_date, future_date)
        self.assertFalse(was_extended)  # Streak was reset
        self.assertEqual(days_added, 1)
    
    def test_update_activity_same_day(self):
        """Test updating streak activity for same day."""
        # Update activity for same day
        was_extended, days_added = self.streak.update_activity(self.today)
        
        self.assertEqual(self.streak.current_days, 5)  # No change
        self.assertEqual(self.streak.longest_days, 7)
        self.assertEqual(self.streak.last_activity_date, self.today)
        self.assertFalse(was_extended)
        self.assertEqual(days_added, 0)
    
    def test_reset_streak(self):
        """Test resetting streak."""
        self.streak.reset_streak()
        
        self.assertEqual(self.streak.current_days, 0)
        self.assertEqual(self.streak.longest_days, 7)  # Preserved
        self.assertIsNone(self.streak.last_activity_date)
        self.assertFalse(self.streak.is_active)
    
    def test_days_until_reset(self):
        """Test calculating days until streak reset."""
        # Activity today, should reset tomorrow
        days_until = self.streak.days_until_reset
        self.assertEqual(days_until, 1)
        
        # Activity was yesterday, should reset today
        yesterday = self.today - timedelta(days=1)
        self.streak.last_activity_date = yesterday
        self.streak.save()
        
        days_until = self.streak.days_until_reset
        self.assertEqual(days_until, 0)
    
    def test_is_expired(self):
        """Test checking if streak is expired."""
        # Activity today, not expired
        self.assertFalse(self.streak.is_expired)
        
        # Activity was yesterday, expired
        yesterday = self.today - timedelta(days=1)
        self.streak.last_activity_date = yesterday
        self.streak.save()
        
        self.assertTrue(self.streak.is_expired)
    
    def test_streak_checksum_generation(self):
        """Test streak checksum generation."""
        original_checksum = self.streak.checksum
        
        # Modify streak
        self.streak.current_days = 6
        self.streak.save()
        
        # Checksum should change
        self.assertNotEqual(self.streak.checksum, original_checksum)


class StreakRewardModelTest(TestCase):
    """Test StreakReward model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.reward = StreakReward.objects.create(
            streak_days=7,
            points_bonus=50,
            title="Week Warrior",
            description="Maintain streak for 7 days",
            is_active=True,
        )
    
    def test_streak_reward_creation(self):
        """Test successful streak reward creation."""
        self.assertEqual(self.reward.streak_days, 7)
        self.assertEqual(self.reward.points_bonus, 50)
        self.assertEqual(self.reward.title, "Week Warrior")
        self.assertEqual(self.reward.description, "Maintain streak for 7 days")
        self.assertTrue(self.reward.is_active)
        self.assertIsNotNone(self.reward.checksum)
    
    def test_streak_reward_str_representation(self):
        """Test streak reward string representation."""
        expected = f"{self.reward.title} ({self.reward.streak_days} days)"
        self.assertEqual(str(self.reward), expected)
    
    def test_streak_reward_with_badge(self):
        """Test streak reward with associated badge."""
        badge = Badge.objects.create(
            name="7 Day Badge",
            description="7 day streak badge",
            icon="🔥",
            rarity="UNCOMMON",
            criteria_type="STREAK_DAYS",
            criteria_value=7,
            points_bonus=50,
            is_active=True,
        )
        
        self.reward.badge = badge
        self.reward.save()
        
        self.assertEqual(self.reward.badge, badge)
    
    def test_streak_reward_checksum_generation(self):
        """Test streak reward checksum generation."""
        original_checksum = self.reward.checksum
        
        # Modify reward
        self.reward.points_bonus = 75
        self.reward.save()
        
        # Checksum should change
        self.assertNotEqual(self.reward.checksum, original_checksum)


class LevelConfigModelTest(TestCase):
    """Test LevelConfig model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.level = LevelConfig.objects.create(
            level_number=5,
            points_required=500,
            title="Expert",
            description="Expert level user",
            perks={"bonus_access": True, "special_features": ["feature1", "feature2"]},
            points_multiplier=1.5,
            is_active=True,
        )
    
    def test_level_config_creation(self):
        """Test successful level config creation."""
        self.assertEqual(self.level.level_number, 5)
        self.assertEqual(self.level.points_required, 500)
        self.assertEqual(self.level.title, "Expert")
        self.assertEqual(self.level.description, "Expert level user")
        self.assertEqual(self.level.points_multiplier, 1.5)
        self.assertTrue(self.level.is_active)
        self.assertIsNotNone(self.level.checksum)
    
    def test_level_config_str_representation(self):
        """Test level config string representation."""
        expected = f"Level {self.level.level_number}: {self.level.title}"
        self.assertEqual(str(self.level), expected)
    
    def test_level_config_perks_json(self):
        """Test level perks JSON field."""
        perks = self.level.perks
        self.assertTrue(perks["bonus_access"])
        self.assertEqual(len(perks["special_features"]), 2)
        self.assertIn("feature1", perks["special_features"])
    
    def test_level_config_with_badge(self):
        """Test level config with associated badge."""
        badge = Badge.objects.create(
            name="Expert Badge",
            description="Expert level badge",
            icon="⭐",
            rarity="RARE",
            criteria_type="POINTS_THRESHOLD",
            criteria_value=500,
            points_bonus=100,
            is_active=True,
        )
        
        self.level.badge = badge
        self.level.save()
        
        self.assertEqual(self.level.badge, badge)
    
    def test_get_level_for_points(self):
        """Test getting level for point total."""
        # Create multiple levels
        level1 = LevelConfig.objects.create(
            level_number=1,
            points_required=0,
            title="Beginner",
            description="Starting level",
            points_multiplier=1.0,
            is_active=True,
        )
        
        level2 = LevelConfig.objects.create(
            level_number=2,
            points_required=100,
            title="Novice",
            description="Getting started",
            points_multiplier=1.1,
            is_active=True,
        )
        
        level3 = LevelConfig.objects.create(
            level_number=3,
            points_required=250,
            title="Intermediate",
            description="Making progress",
            points_multiplier=1.2,
            is_active=True,
        )
        
        # Test various point totals
        self.assertEqual(LevelConfig.get_level_for_points(0).level_number, 1)
        self.assertEqual(LevelConfig.get_level_for_points(50).level_number, 1)
        self.assertEqual(LevelConfig.get_level_for_points(100).level_number, 2)
        self.assertEqual(LevelConfig.get_level_for_points(150).level_number, 2)
        self.assertEqual(LevelConfig.get_level_for_points(250).level_number, 3)
        self.assertEqual(LevelConfig.get_level_for_points(300).level_number, 3)
        self.assertEqual(LevelConfig.get_level_for_points(600).level_number, 5)  # Our test level
    
    def test_get_level_for_points_no_levels(self):
        """Test getting level when no levels exist."""
        LevelConfig.objects.all().delete()
        
        level = LevelConfig.get_level_for_points(100)
        self.assertIsNone(level)
    
    def test_get_progress_to_next_level(self):
        """Test getting progress to next level."""
        # Create multiple levels
        level1 = LevelConfig.objects.create(
            level_number=1,
            points_required=0,
            title="Beginner",
            description="Starting level",
            points_multiplier=1.0,
            is_active=True,
        )
        
        level2 = LevelConfig.objects.create(
            level_number=2,
            points_required=100,
            title="Novice",
            description="Getting started",
            points_multiplier=1.1,
            is_active=True,
        )
        
        # Test progress calculation
        progress = LevelConfig.get_progress_to_next_level(50)
        self.assertEqual(progress["current_level"], 1)
        self.assertEqual(progress["next_level"], 2)
        self.assertEqual(progress["points_needed_for_next"], 100)
        self.assertEqual(progress["points_already_have"], 50)
        self.assertEqual(progress["points_needed"], 50)
        self.assertEqual(progress["progress_percentage"], 50.0)
        self.assertFalse(progress["is_max_level"])
        
        # Test at max level
        progress = LevelConfig.get_progress_to_next_level(600)
        self.assertEqual(progress["current_level"], 5)  # Our test level
        self.assertIsNone(progress["next_level"])
        self.assertTrue(progress["is_max_level"])
    
    def test_level_config_checksum_generation(self):
        """Test level config checksum generation."""
        original_checksum = self.level.checksum
        
        # Modify level
        self.level.points_multiplier = 1.6
        self.level.save()
        
        # Checksum should change
        self.assertNotEqual(self.level.checksum, original_checksum)
