"""
Level Up Service Tests — Comprehensive LevelUpService functionality tests.

Tests all LevelUpService methods including level progression, checking,
management, and statistics.
"""

from __future__ import annotations

import logging
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from api.gamification.models import LevelConfig, UserBadge, Badge, UserAchievement as Achievement
from api.gamification.exceptions import (
    GamificationServiceError,
    UserNotFoundError,
)
from api.gamification.services import LevelUpService
from api.gamification.tests.factories import UserFactory
from api.gamification.models import UserAchievement

User = get_user_model()
logger = logging.getLogger(__name__)


class LevelUpServiceTest(TestCase):
    """Test LevelUpService functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        
        # Create test levels
        self.level_1 = LevelConfig.objects.create(
            level_number=1,
            points_required=0,
            title="Beginner",
            description="Starting level",
            points_multiplier=1.0,
            is_active=True,
        )
        
        self.level_2 = LevelConfig.objects.create(
            level_number=2,
            points_required=100,
            title="Novice",
            description="Getting started",
            points_multiplier=1.1,
            is_active=True,
        )
        
        self.level_3 = LevelConfig.objects.create(
            level_number=3,
            points_required=250,
            title="Intermediate",
            description="Making progress",
            points_multiplier=1.2,
            is_active=True,
        )
        
        self.level_5 = LevelConfig.objects.create(
            level_number=5,
            points_required=500,
            title="Expert",
            description="Skilled user",
            points_multiplier=1.5,
            is_active=True,
        )
        
        # Create inactive level
        self.inactive_level = LevelConfig.objects.create(
            level_number=10,
            points_required=2000,
            title="Master",
            description="Advanced level",
            points_multiplier=2.0,
            is_active=False,
        )
        
        # Create badges for levels
        self.level_2_badge = Badge.objects.create(
            name="Novice Badge",
            description="Level 2 achievement",
            icon="🌟",
            rarity="COMMON",
            criteria_type="POINTS_THRESHOLD",
            criteria_value=100,
            points_bonus=25,
            is_active=True,
        )
        
        self.level_3_badge = Badge.objects.create(
            name="Intermediate Badge",
            description="Level 3 achievement",
            icon="⭐",
            rarity="UNCOMMON",
            criteria_type="POINTS_THRESHOLD",
            criteria_value=250,
            points_bonus=50,
            is_active=True,
        )
        
        # Associate badges with levels
        self.level_2.badge = self.level_2_badge
        self.level_2.save()
        
        self.level_3.badge = self.level_3_badge
        self.level_3.save()
    
    def test_get_user_level_no_points(self):
        """Test getting level for user with no points."""
        level = LevelUpService.get_user_level(0)
        
        self.assertEqual(level.level_number, 1)
        self.assertEqual(level.title, "Beginner")
    
    def test_get_user_level_partial_progress(self):
        """Test getting level for user with partial progress."""
        level = LevelUpService.get_user_level(150)
        
        self.assertEqual(level.level_number, 2)
        self.assertEqual(level.title, "Novice")
    
    def test_get_user_level_exact_match(self):
        """Test getting level for user with exact points match."""
        level = LevelUpService.get_user_level(250)
        
        self.assertEqual(level.level_number, 3)
        self.assertEqual(level.title, "Intermediate")
    
    def test_get_user_level_high_points(self):
        """Test getting level for user with high points."""
        level = LevelUpService.get_user_level(600)
        
        self.assertEqual(level.level_number, 5)
        self.assertEqual(level.title, "Expert")
    
    def test_get_user_level_no_levels_available(self):
        """Test getting level when no levels match points."""
        # Delete all levels
        LevelConfig.objects.all().delete()
        
        level = LevelUpService.get_user_level(100)
        
        self.assertIsNone(level)
    
    def test_get_level_progress_current_level(self):
        """Test getting level progress for current level."""
        progress = LevelUpService.get_level_progress(150)
        
        self.assertEqual(progress["current_level"], 2)
        self.assertEqual(progress["current_level_title"], "Novice")
        self.assertEqual(progress["next_level"], 3)
        self.assertEqual(progress["next_level_title"], "Intermediate")
        self.assertEqual(progress["points_needed_for_next"], 250)
        self.assertEqual(progress["points_already_have"], 150)
        self.assertEqual(progress["points_needed"], 100)
        self.assertEqual(progress["progress_percentage"], 50.0)
        self.assertFalse(progress["is_max_level"])
    
    def test_get_level_progress_max_level(self):
        """Test getting level progress for max level."""
        progress = LevelUpService.get_level_progress(600)
        
        self.assertEqual(progress["current_level"], 5)
        self.assertEqual(progress["current_level_title"], "Expert")
        self.assertIsNone(progress["next_level"])
        self.assertIsNone(progress["next_level_title"])
        self.assertEqual(progress["points_needed_for_next"], 0)
        self.assertEqual(progress["points_already_have"], 600)
        self.assertEqual(progress["points_needed"], 0)
        self.assertEqual(progress["progress_percentage"], 100.0)
        self.assertTrue(progress["is_max_level"])
    
    def test_get_level_progress_no_levels(self):
        """Test getting level progress when no levels exist."""
        LevelConfig.objects.all().delete()
        
        progress = LevelUpService.get_level_progress(100)
        
        self.assertIsNone(progress["current_level"])
        self.assertIsNone(progress["current_level_title"])
        self.assertIsNone(progress["next_level"])
        self.assertEqual(progress["points_needed_for_next"], 0)
        self.assertEqual(progress["points_already_have"], 100)
        self.assertEqual(progress["points_needed"], 0)
        self.assertEqual(progress["progress_percentage"], 0.0)
        self.assertTrue(progress["is_max_level"])
    
    def test_check_level_up_no_change(self):
        """Test level up check with no level change."""
        old_level, new_level, did_level_up = LevelUpService.check_level_up(
            self.user.id, old_points=50, new_points=80
        )
        
        self.assertEqual(old_level.level_number, 1)
        self.assertEqual(new_level.level_number, 1)
        self.assertFalse(did_level_up)
    
    def test_check_level_up_single_level(self):
        """Test level up check with single level increase."""
        old_level, new_level, did_level_up = LevelUpService.check_level_up(
            self.user.id, old_points=50, new_points=150
        )
        
        self.assertEqual(old_level.level_number, 1)
        self.assertEqual(new_level.level_number, 2)
        self.assertTrue(did_level_up)
    
    def test_check_level_up_multiple_levels(self):
        """Test level up check with multiple level increase."""
        old_level, new_level, did_level_up = LevelUpService.check_level_up(
            self.user.id, old_points=50, new_points=300
        )
        
        self.assertEqual(old_level.level_number, 1)
        self.assertEqual(new_level.level_number, 3)
        self.assertTrue(did_level_up)
    
    def test_check_level_up_user_not_found(self):
        """Test level up check for non-existent user."""
        with self.assertRaises(UserNotFoundError):
            LevelUpService.check_level_up(
                "00000000-0000-0000-0000-000000000000",
                old_points=50,
                new_points=150
            )
    
    def test_get_user_level_history_no_badges(self):
        """Test getting level history for user with no level badges."""
        history = LevelUpService.get_user_level_history(self.user.id)
        
        self.assertIsNone(history["current_level"])
        self.assertEqual(history["total_levels_achieved"], 0)
        self.assertIsNone(history["highest_level_badge"])
    
    def test_get_user_level_history_with_badges(self):
        """Test getting level history for user with level badges."""
        # Award level 2 badge
        UserBadge.objects.create(
            user=self.user,
            badge=self.level_2_badge,
            metadata={"awarded_via": "level_up"}
        )
        
        history = LevelUpService.get_user_level_history(self.user.id)
        
        self.assertIsNotNone(history["current_level"])
        self.assertEqual(history["current_level"].level_number, 2)
        self.assertEqual(history["total_levels_achieved"], 1)
        self.assertIsNotNone(history["highest_level_badge"])
    
    def test_calculate_points_to_next_level(self):
        """Test calculating points needed for next level."""
        points_needed = LevelUpService.calculate_points_to_next_level(150)
        
        self.assertEqual(points_needed, 100)  # 250 - 150
    
    def test_calculate_points_to_next_level_max_level(self):
        """Test calculating points needed at max level."""
        points_needed = LevelUpService.calculate_points_to_next_level(600)
        
        self.assertEqual(points_needed, 0)
    
    def test_calculate_level_progress_percentage(self):
        """Test calculating level progress percentage."""
        progress = LevelUpService.calculate_level_progress_percentage(150)
        
        self.assertEqual(progress, 50.0)  # (150-100)/(250-100) * 100
    
    def test_calculate_level_progress_percentage_max_level(self):
        """Test calculating level progress percentage at max level."""
        progress = LevelUpService.calculate_level_progress_percentage(600)
        
        self.assertEqual(progress, 100.0)
    
    def test_get_level_leaderboard(self):
        """Test getting level leaderboard."""
        # Create users with different point totals
        user2 = UserFactory()
        user3 = UserFactory()
        
        # Create achievements for users
        UserAchievement.objects.create(
            user=self.user,
            points_awarded=150,
            is_awarded=True
        )
        
        UserAchievement.objects.create(
            user=user2,
            points_awarded=300,
            is_awarded=True
        )
        
        UserAchievement.objects.create(
            user=user3,
            points_awarded=80,
            is_awarded=True
        )
        
        leaderboard = LevelUpService.get_level_leaderboard(limit=5)
        
        self.assertEqual(len(leaderboard), 3)
        self.assertEqual(leaderboard[0]["username"], user2.username)
        self.assertEqual(leaderboard[0]["current_level"], 3)
        self.assertEqual(leaderboard[1]["username"], self.user.username)
        self.assertEqual(leaderboard[1]["current_level"], 2)
        self.assertEqual(leaderboard[2]["username"], user3.username)
        self.assertEqual(leaderboard[2]["current_level"], 1)
    
    def test_get_level_statistics(self):
        """Test getting level statistics for user."""
        # Create achievements for user
        UserAchievement.objects.create(
            user=self.user,
            points_awarded=150,
            is_awarded=True
        )
        
        stats = LevelUpService.get_level_statistics(self.user.id)
        
        self.assertEqual(stats["total_points"], 150)
        self.assertEqual(stats["current_level"], 2)
        self.assertEqual(stats["current_level_title"], "Novice")
        self.assertEqual(stats["points_to_next_level"], 100)
        self.assertEqual(stats["progress_percentage"], 50.0)
        self.assertFalse(stats["is_max_level"])
        self.assertEqual(stats["points_multiplier"], 1.1)
    
    def test_get_level_statistics_no_achievements(self):
        """Test getting level statistics for user with no achievements."""
        stats = LevelUpService.get_level_statistics(self.user.id)
        
        self.assertEqual(stats["total_points"], 0)
        self.assertEqual(stats["current_level"], 1)
        self.assertEqual(stats["current_level_title"], "Beginner")
        self.assertEqual(stats["points_to_next_level"], 100)
        self.assertEqual(stats["progress_percentage"], 0.0)
        self.assertFalse(stats["is_max_level"])
        self.assertEqual(stats["points_multiplier"], 1.0)
    
    def test_get_available_levels_all(self):
        """Test getting all available levels."""
        levels = LevelUpService.get_available_levels()
        
        self.assertEqual(len(levels), 4)  # Excludes inactive level
        level_numbers = [level.level_number for level in levels]
        self.assertIn(1, level_numbers)
        self.assertIn(2, level_numbers)
        self.assertIn(3, level_numbers)
        self.assertIn(5, level_numbers)
        self.assertNotIn(10, level_numbers)
    
    def test_get_available_levels_active_only(self):
        """Test getting only active levels."""
        levels = LevelUpService.get_available_levels(is_active=True)
        
        self.assertEqual(len(levels), 4)
        
        levels = LevelUpService.get_available_levels(is_active=False)
        
        self.assertEqual(len(levels), 1)
        self.assertEqual(levels[0].level_number, 10)
    
    def test_create_level_config_success(self):
        """Test successful level configuration creation."""
        level_config = LevelUpService.create_level_config(
            level_number=4,
            points_required=400,
            title="Advanced",
            description="Advanced user level",
            perks={"bonus_access": True},
            points_multiplier=1.3,
            badge_id=None,
            metadata={"difficulty": "hard"}
        )
        
        self.assertEqual(level_config.level_number, 4)
        self.assertEqual(level_config.points_required, 400)
        self.assertEqual(level_config.title, "Advanced")
        self.assertEqual(level_config.description, "Advanced user level")
        self.assertEqual(level_config.perks["bonus_access"], True)
        self.assertEqual(level_config.points_multiplier, 1.3)
        self.assertEqual(level_config.metadata["difficulty"], "hard")
    
    def test_create_level_config_validation_errors(self):
        """Test level configuration creation validation."""
        # Empty title
        with self.assertRaises(GamificationServiceError):
            LevelUpService.create_level_config(
                level_number=6,
                points_required=600,
                title="",
                description="Test"
            )
        
        # Invalid level number
        with self.assertRaises(GamificationServiceError):
            LevelUpService.create_level_config(
                level_number=0,
                points_required=100,
                title="Test",
                description="Test"
            )
        
        # Negative points required
        with self.assertRaises(GamificationServiceError):
            LevelUpService.create_level_config(
                level_number=6,
                points_required=-50,
                title="Test",
                description="Test"
            )
        
        # Invalid points multiplier
        with self.assertRaises(GamificationServiceError):
            LevelUpService.create_level_config(
                level_number=6,
                points_required=600,
                title="Test",
                description="Test",
                points_multiplier=0.0
            )
        
        # Duplicate level number
        with self.assertRaises(GamificationServiceError):
            LevelUpService.create_level_config(
                level_number=2,  # Already exists
                points_required=150,
                title="Duplicate",
                description="Duplicate level"
            )
        
        # Invalid progression (points less than previous level)
        with self.assertRaises(GamificationServiceError):
            LevelUpService.create_level_config(
                level_number=4,
                points_required=50,  # Less than level 3's 250
                title="Invalid",
                description="Invalid progression"
            )
    
    def test_update_level_config_success(self):
        """Test successful level configuration update."""
        updated_config = LevelUpService.update_level_config(
            level_id=self.level_3.id,
            title="Updated Intermediate",
            description="Updated description",
            perks={"new_perk": True},
            points_multiplier=1.25
        )
        
        self.assertEqual(updated_config.title, "Updated Intermediate")
        self.assertEqual(updated_config.description, "Updated description")
        self.assertEqual(updated_config.perks["new_perk"], True)
        self.assertEqual(updated_config.points_multiplier, 1.25)
    
    def test_update_level_config_validation_errors(self):
        """Test level configuration update validation."""
        # Non-existent level
        with self.assertRaises(GamificationServiceError):
            LevelUpService.update_level_config(
                level_id="00000000-0000-0000-0000-000000000000",
                title="Updated"
            )
        
        # Empty title
        with self.assertRaises(GamificationServiceError):
            LevelUpService.update_level_config(
                level_id=self.level_3.id,
                title=""
            )
        
        # Invalid points progression
        with self.assertRaises(GamificationServiceError):
            LevelUpService.update_level_config(
                level_id=self.level_3.id,
                points_required=50  # Less than level 2's 100
            )
    
    def test_get_level_requirements_summary(self):
        """Test getting level requirements summary."""
        summary = LevelUpService.get_level_requirements_summary()
        
        self.assertEqual(summary["total_levels"], 4)
        self.assertEqual(summary["min_points"], 0)
        self.assertEqual(summary["max_points"], 500)
        self.assertEqual(len(summary["levels"]), 4)
        
        # Check first level
        level_1_info = summary["levels"][0]
        self.assertEqual(level_1_info["level_number"], 1)
        self.assertEqual(level_1_info["points_required"], 0)
        self.assertEqual(level_1_info["title"], "Beginner")
        self.assertEqual(level_1_info["points_multiplier"], 1.0)
        self.assertFalse(level_1_info["has_badge"])
    
    def test_get_level_requirements_summary_no_levels(self):
        """Test getting level requirements summary with no levels."""
        LevelConfig.objects.all().delete()
        
        summary = LevelUpService.get_level_requirements_summary()
        
        self.assertEqual(summary["total_levels"], 0)
        self.assertEqual(summary["min_points"], 0)
        self.assertEqual(summary["max_points"], 0)
        self.assertEqual(summary["levels"], [])


class LevelUpServiceTransactionTest(TransactionTestCase):
    """Test LevelUpService with transactions."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        
        self.level_1 = LevelConfig.objects.create(
            level_number=1,
            points_required=0,
            title="Beginner",
            description="Starting level",
            points_multiplier=1.0,
            is_active=True,
        )
        
        self.level_2 = LevelConfig.objects.create(
            level_number=2,
            points_required=100,
            title="Novice",
            description="Getting started",
            points_multiplier=1.1,
            is_active=True,
        )
        
        self.badge = Badge.objects.create(
            name="Novice Badge",
            description="Level 2 achievement",
            icon="🌟",
            rarity="COMMON",
            criteria_type="POINTS_THRESHOLD",
            criteria_value=100,
            points_bonus=25,
            is_active=True,
        )
        
        self.level_2.badge = self.badge
        self.level_2.save()
    
    @patch('api.gamification.services.LevelUpService.user_leveled_up')
    def test_check_level_up_sends_signal(self, mock_signal):
        """Test that leveling up sends the appropriate signal."""
        mock_signal.send = MagicMock()
        
        old_level, new_level, did_level_up = LevelUpService.check_level_up(
            self.user.id, old_points=50, new_points=150
        )
        
        # Verify signal was sent
        mock_signal.send.assert_called_once()
        call_args = mock_signal.send.call_args
        self.assertEqual(call_args[1]['user_id'], self.user.id)
        self.assertEqual(call_args[1]['old_level'], 1)
        self.assertEqual(call_args[1]['new_level'], 2)
        self.assertEqual(call_args[1]['level_config_id'], self.level_2.id)
    
    @patch('api.gamification.services.LevelUpService.badge_earned')
    def test_check_level_up_awards_badge(self, mock_signal):
        """Test that leveling up awards badge and sends signal."""
        mock_signal.send = MagicMock()
        
        old_level, new_level, did_level_up = LevelUpService.check_level_up(
            self.user.id, old_points=50, new_points=150
        )
        
        # Verify badge was awarded
        self.assertTrue(UserBadge.objects.filter(
            user=self.user,
            badge=self.badge
        ).exists())
        
        # Verify badge earned signal was sent
        mock_signal.send.assert_called_once()
        call_args = mock_signal.send.call_args
        self.assertEqual(call_args[1]['user_id'], self.user.id)
        self.assertEqual(call_args[1]['badge_id'], self.badge.id)
    
    def test_check_level_up_no_signal_no_level_up(self):
        """Test that no signal is sent when no level up occurs."""
        with patch('api.gamification.services.LevelUpService.user_leveled_up') as mock_signal:
            old_level, new_level, did_level_up = LevelUpService.check_level_up(
                self.user.id, old_points=50, new_points=80
            )
            
            # Should not send signal
            mock_signal.send.assert_not_called()
            self.assertFalse(did_level_up)
    
    def test_award_level_badge_no_badge_configured(self):
        """Test awarding level badge when no badge is configured."""
        # Remove badge from level
        self.level_2.badge = None
        self.level_2.save()
        
        # Try to award badge
        badge = LevelUpService._award_level_badge(self.user.id, self.level_2.id)
        
        # Should return None
        self.assertIsNone(badge)
    
    def test_award_level_badge_already_awarded(self):
        """Test awarding level badge when already awarded."""
        # Award badge first
        UserBadge.objects.create(user=self.user, badge=self.badge)
        
        # Try to award again
        badge = LevelUpService._award_level_badge(self.user.id, self.level_2.id)
        
        # Should return None
        self.assertIsNone(badge)
