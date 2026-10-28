"""
Badge Service Tests — Comprehensive BadgeService functionality tests.

Tests all BadgeService methods including badge eligibility checking,
awarding, management, and statistics.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from api.gamification.models import Badge, UserBadge, Streak
from api.gamification.choices import BadgeRarity, BadgeCriteriaType
from api.gamification.exceptions import (
    GamificationServiceError,
    UserNotFoundError,
    DuplicateAchievementError,
)
from api.gamification.services import BadgeService
from api.gamification.tests.factories import UserFactory

User = get_user_model()
logger = logging.getLogger(__name__)


class BadgeServiceTest(TestCase):
    """Test BadgeService functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        
        # Create test badges
        self.common_badge = Badge.objects.create(
            name="Beginner",
            description="First steps",
            icon="🎯",
            rarity=BadgeRarity.COMMON,
            criteria_type=BadgeCriteriaType.POINTS_THRESHOLD,
            criteria_value=100,
            points_bonus=10,
            is_active=True,
            sort_order=1,
        )
        
        self.rare_badge = Badge.objects.create(
            name="Expert",
            description="Advanced user",
            icon="⭐",
            rarity=BadgeRarity.RARE,
            criteria_type=BadgeCriteriaType.POINTS_THRESHOLD,
            criteria_value=1000,
            points_bonus=50,
            is_active=True,
            sort_order=2,
        )
        
        self.streak_badge = Badge.objects.create(
            name="Week Warrior",
            description="7-day streak",
            icon="🔥",
            rarity=BadgeRarity.UNCOMMON,
            criteria_type=BadgeCriteriaType.STREAK_DAYS,
            criteria_value=7,
            points_bonus=25,
            is_active=True,
            sort_order=3,
        )
        
        self.inactive_badge = Badge.objects.create(
            name="Legacy",
            description="Old badge",
            icon="📜",
            rarity=BadgeRarity.COMMON,
            criteria_type=BadgeCriteriaType.POINTS_THRESHOLD,
            criteria_value=500,
            points_bonus=20,
            is_active=False,
            sort_order=4,
        )
    
    def test_check_user_badge_eligibility_points_based(self):
        """Test badge eligibility checking based on points."""
        # User with 150 points should be eligible for common badge (100) but not rare (1000)
        eligible_badges = BadgeService.check_user_badge_eligibility(
            user_id=self.user.id,
            user_points=150,
            streak_days=0,
        )
        
        self.assertEqual(len(eligible_badges), 1)
        self.assertEqual(eligible_badges[0].id, self.common_badge.id)
    
    def test_check_user_badge_eligibility_streak_based(self):
        """Test badge eligibility checking based on streak days."""
        # User with 7-day streak should be eligible for streak badge
        eligible_badges = BadgeService.check_user_badge_eligibility(
            user_id=self.user.id,
            user_points=0,
            streak_days=7,
        )
        
        self.assertEqual(len(eligible_badges), 1)
        self.assertEqual(eligible_badges[0].id, self.streak_badge.id)
    
    def test_check_user_badge_eligibility_multiple_criteria(self):
        """Test badge eligibility with multiple criteria met."""
        # User with 1500 points and 10-day streak should be eligible for multiple badges
        eligible_badges = BadgeService.check_user_badge_eligibility(
            user_id=self.user.id,
            user_points=1500,
            streak_days=10,
        )
        
        self.assertEqual(len(eligible_badges), 3)
        badge_ids = [badge.id for badge in eligible_badges]
        self.assertIn(self.common_badge.id, badge_ids)
        self.assertIn(self.rare_badge.id, badge_ids)
        self.assertIn(self.streak_badge.id, badge_ids)
    
    def test_check_user_badge_eligibility_excludes_inactive(self):
        """Test that inactive badges are not included in eligibility."""
        eligible_badges = BadgeService.check_user_badge_eligibility(
            user_id=self.user.id,
            user_points=600,  # Should qualify for inactive badge at 500
            streak_days=0,
        )
        
        # Should not include inactive badge
        badge_ids = [badge.id for badge in eligible_badges]
        self.assertNotIn(self.inactive_badge.id, badge_ids)
    
    def test_check_user_badge_eligibility_excludes_already_earned(self):
        """Test that already earned badges are not included."""
        # Award the common badge first
        UserBadge.objects.create(
            user=self.user,
            badge=self.common_badge,
        )
        
        eligible_badges = BadgeService.check_user_badge_eligibility(
            user_id=self.user.id,
            user_points=150,
            streak_days=0,
        )
        
        # Should not include already earned badge
        badge_ids = [badge.id for badge in eligible_badges]
        self.assertNotIn(self.common_badge.id, badge_ids)
    
    def test_check_user_badge_eligibility_user_not_found(self):
        """Test eligibility checking with non-existent user."""
        with self.assertRaises(UserNotFoundError):
            BadgeService.check_user_badge_eligibility(
                user_id="00000000-0000-0000-0000-000000000000",
                user_points=100,
                streak_days=0,
            )
    
    def test_award_badge_to_user_success(self):
        """Test successful badge awarding."""
        user_badge = BadgeService.award_badge_to_user(
            user_id=self.user.id,
            badge_id=self.common_badge.id,
            metadata={"source": "test"},
        )
        
        self.assertEqual(user_badge.user, self.user)
        self.assertEqual(user_badge.badge, self.common_badge)
        self.assertIsNotNone(user_badge.earned_at)
        self.assertEqual(user_badge.metadata["source"], "test")
    
    def test_award_badge_to_user_already_earned(self):
        """Test awarding a badge that user already has."""
        # Award badge first
        UserBadge.objects.create(user=self.user, badge=self.common_badge)
        
        with self.assertRaises(DuplicateAchievementError):
            BadgeService.award_badge_to_user(
                user_id=self.user.id,
                badge_id=self.common_badge.id,
            )
    
    def test_award_badge_to_user_not_found(self):
        """Test awarding badge to non-existent user."""
        with self.assertRaises(UserNotFoundError):
            BadgeService.award_badge_to_user(
                user_id="00000000-0000-0000-0000-000000000000",
                badge_id=self.common_badge.id,
            )
    
    def test_award_badge_to_user_badge_not_found(self):
        """Test awarding non-existent badge."""
        with self.assertRaises(GamificationServiceError):
            BadgeService.award_badge_to_user(
                user_id=self.user.id,
                badge_id="00000000-0000-0000-0000-000000000000",
            )
    
    def test_award_badge_to_user_inactive_badge(self):
        """Test awarding inactive badge."""
        with self.assertRaises(GamificationServiceError):
            BadgeService.award_badge_to_user(
                user_id=self.user.id,
                badge_id=self.inactive_badge.id,
            )
    
    def test_award_eligible_badges_multiple(self):
        """Test awarding multiple eligible badges."""
        awarded_badges = BadgeService.award_eligible_badges(
            user_id=self.user.id,
            user_points=1500,
            streak_days=10,
        )
        
        self.assertEqual(len(awarded_badges), 3)
        
        # Verify all badges were awarded
        badge_ids = [ub.badge.id for ub in awarded_badges]
        self.assertIn(self.common_badge.id, badge_ids)
        self.assertIn(self.rare_badge.id, badge_ids)
        self.assertIn(self.streak_badge.id, badge_ids)
    
    def test_award_eligible_badges_with_metadata(self):
        """Test awarding eligible badges with metadata."""
        metadata = {"campaign": "test_campaign", "source": "automation"}
        
        awarded_badges = BadgeService.award_eligible_badges(
            user_id=self.user.id,
            user_points=150,
            streak_days=0,
            metadata=metadata,
        )
        
        self.assertEqual(len(awarded_badges), 1)
        self.assertEqual(awarded_badges[0].metadata["campaign"], "test_campaign")
        self.assertEqual(awarded_badges[0].metadata["source"], "automation")
    
    def test_get_user_badges_all(self):
        """Test getting all user badges."""
        # Award some badges
        BadgeService.award_badge_to_user(self.user.id, self.common_badge.id)
        BadgeService.award_badge_to_user(self.user.id, self.rare_badge.id)
        
        user_badges = BadgeService.get_user_badges(user_id=self.user.id)
        
        self.assertEqual(len(user_badges), 2)
        badge_ids = [ub.badge.id for ub in user_badges]
        self.assertIn(self.common_badge.id, badge_ids)
        self.assertIn(self.rare_badge.id, badge_ids)
    
    def test_get_user_badges_filtered_by_pinned(self):
        """Test getting user badges filtered by pinned status."""
        # Award badges and pin one
        ub1 = BadgeService.award_badge_to_user(self.user.id, self.common_badge.id)
        ub2 = BadgeService.award_badge_to_user(self.user.id, self.rare_badge.id)
        
        # Pin one badge
        BadgeService.pin_user_badge(self.user.id, ub1.id)
        
        # Get only pinned badges
        pinned_badges = BadgeService.get_user_badges(
            user_id=self.user.id,
            is_pinned=True,
        )
        
        self.assertEqual(len(pinned_badges), 1)
        self.assertEqual(pinned_badges[0].id, ub1.id)
        self.assertTrue(pinned_badges[0].is_pinned)
    
    def test_get_user_badges_filtered_by_rarity(self):
        """Test getting user badges filtered by rarity."""
        # Award badges with different rarities
        BadgeService.award_badge_to_user(self.user.id, self.common_badge.id)
        BadgeService.award_badge_to_user(self.user.id, self.rare_badge.id)
        
        # Get only rare badges
        rare_badges = BadgeService.get_user_badges(
            user_id=self.user.id,
            rarity=BadgeRarity.RARE,
        )
        
        self.assertEqual(len(rare_badges), 1)
        self.assertEqual(rare_badges[0].badge.rarity, BadgeRarity.RARE)
    
    def test_get_user_badges_with_limit(self):
        """Test getting user badges with limit."""
        # Award multiple badges
        BadgeService.award_badge_to_user(self.user.id, self.common_badge.id)
        BadgeService.award_badge_to_user(self.user.id, self.rare_badge.id)
        BadgeService.award_badge_to_user(self.user.id, self.streak_badge.id)
        
        # Get only 2 badges
        limited_badges = BadgeService.get_user_badges(
            user_id=self.user.id,
            limit=2,
        )
        
        self.assertEqual(len(limited_badges), 2)
    
    def test_get_user_badges_user_not_found(self):
        """Test getting badges for non-existent user."""
        with self.assertRaises(UserNotFoundError):
            BadgeService.get_user_badges(
                user_id="00000000-0000-0000-0000-000000000000"
            )
    
    def test_pin_user_badge_success(self):
        """Test successful badge pinning."""
        user_badge = BadgeService.award_badge_to_user(self.user.id, self.common_badge.id)
        
        pinned_badge = BadgeService.pin_user_badge(self.user.id, user_badge.id)
        
        self.assertTrue(pinned_badge.is_pinned)
        self.assertEqual(pinned_badge.id, user_badge.id)
    
    def test_pin_user_badge_not_found(self):
        """Test pinning non-existent user badge."""
        with self.assertRaises(GamificationServiceError):
            BadgeService.pin_user_badge(
                user_id=self.user.id,
                user_badge_id="00000000-0000-0000-0000-000000000000"
            )
    
    def test_unpin_user_badge_success(self):
        """Test successful badge unpinning."""
        user_badge = BadgeService.award_badge_to_user(self.user.id, self.common_badge.id)
        BadgeService.pin_user_badge(self.user.id, user_badge.id)
        
        unpinned_badge = BadgeService.unpin_user_badge(self.user.id, user_badge.id)
        
        self.assertFalse(unpinned_badge.is_pinned)
        self.assertEqual(unpinned_badge.id, user_badge.id)
    
    def test_get_badge_statistics(self):
        """Test getting badge statistics."""
        # Award some badges
        BadgeService.award_badge_to_user(self.user.id, self.common_badge.id)
        BadgeService.award_badge_to_user(self.user.id, self.rare_badge.id)
        BadgeService.pin_user_badge(self.user.id, UserBadge.objects.first().id)
        
        stats = BadgeService.get_badge_statistics(user_id=self.user.id)
        
        self.assertEqual(stats["total_badges"], 2)
        self.assertEqual(stats["pinned_badges"], 1)
        self.assertIn(BadgeRarity.COMMON, stats["by_rarity"])
        self.assertIn(BadgeRarity.RARE, stats["by_rarity"])
        self.assertEqual(stats["by_rarity"][BadgeRarity.COMMON], 1)
        self.assertEqual(stats["by_rarity"][BadgeRarity.RARE], 1)
        self.assertEqual(stats["points_from_badges"], 60)  # 10 + 50
    
    def test_get_badge_statistics_no_badges(self):
        """Test getting badge statistics for user with no badges."""
        stats = BadgeService.get_badge_statistics(user_id=self.user.id)
        
        self.assertEqual(stats["total_badges"], 0)
        self.assertEqual(stats["pinned_badges"], 0)
        self.assertEqual(stats["by_rarity"], {})
        self.assertEqual(stats["points_from_badges"], 0)
    
    def test_get_available_badges_all(self):
        """Test getting all available badges."""
        badges = BadgeService.get_available_badges()
        
        self.assertEqual(len(badges), 3)  # Excludes inactive badge
        badge_ids = [badge.id for badge in badges]
        self.assertIn(self.common_badge.id, badge_ids)
        self.assertIn(self.rare_badge.id, badge_ids)
        self.assertIn(self.streak_badge.id, badge_ids)
        self.assertNotIn(self.inactive_badge.id, badge_ids)
    
    def test_get_available_badges_active_only(self):
        """Test getting only active badges."""
        badges = BadgeService.get_available_badges(is_active=True)
        
        self.assertEqual(len(badges), 3)
        
        badges = BadgeService.get_available_badges(is_active=False)
        
        self.assertEqual(len(badges), 1)
        self.assertEqual(badges[0].id, self.inactive_badge.id)
    
    def test_get_available_badges_filtered_by_rarity(self):
        """Test getting available badges filtered by rarity."""
        badges = BadgeService.get_available_badges(rarity=BadgeRarity.RARE)
        
        self.assertEqual(len(badges), 1)
        self.assertEqual(badges[0].rarity, BadgeRarity.RARE)
    
    def test_get_available_badges_filtered_by_criteria_type(self):
        """Test getting available badges filtered by criteria type."""
        badges = BadgeService.get_available_badges(
            criteria_type=BadgeCriteriaType.STREAK_DAYS
        )
        
        self.assertEqual(len(badges), 1)
        self.assertEqual(badges[0].criteria_type, BadgeCriteriaType.STREAK_DAYS)


class BadgeServiceTransactionTest(TransactionTestCase):
    """Test BadgeService with transactions."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.badge = Badge.objects.create(
            name="Test Badge",
            description="Test description",
            icon="🎯",
            rarity=BadgeRarity.COMMON,
            criteria_type=BadgeCriteriaType.POINTS_THRESHOLD,
            criteria_value=100,
            points_bonus=10,
            is_active=True,
            sort_order=1,
        )
    
    @patch('api.gamification.services.BadgeService.badge_earned')
    def test_award_badge_sends_signal(self, mock_signal):
        """Test that awarding a badge sends the appropriate signal."""
        mock_signal.send = MagicMock()
        
        user_badge = BadgeService.award_badge_to_user(self.user.id, self.badge.id)
        
        # Verify signal was sent
        mock_signal.send.assert_called_once()
        call_args = mock_signal.send.call_args
        self.assertEqual(call_args[1]['user_id'], self.user.id)
        self.assertEqual(call_args[1]['badge_id'], self.badge.id)
        self.assertEqual(call_args[1]['user_badge_id'], user_badge.id)
    
    def test_award_eligible_badges_atomic(self):
        """Test that awarding eligible badges is atomic."""
        # Create a badge that will fail validation
        invalid_badge = Badge.objects.create(
            name="Invalid",
            description="Invalid badge",
            icon="❌",
            rarity=BadgeRarity.COMMON,
            criteria_type=BadgeCriteriaType.POINTS_THRESHOLD,
            criteria_value=100,
            points_bonus=10,
            is_active=True,
            sort_order=2,
        )
        
        # Make user eligible for both badges
        eligible_badges = BadgeService.check_user_badge_eligibility(
            user_id=self.user.id,
            user_points=200,
            streak_days=0,
        )
        self.assertEqual(len(eligible_badges), 2)
        
        # Award the first badge
        BadgeService.award_badge_to_user(self.user.id, self.badge.id)
        
        # Try to award eligible badges - should skip already awarded badge
        awarded_badges = BadgeService.award_eligible_badges(
            user_id=self.user.id,
            user_points=200,
            streak_days=0,
        )
        
        # Should only award the second badge
        self.assertEqual(len(awarded_badges), 1)
        self.assertEqual(awarded_badges[0].badge.id, invalid_badge.id)
