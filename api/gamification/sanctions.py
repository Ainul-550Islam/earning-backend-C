"""
Gamification Sanctions — Rule enforcement and violation handling.

This module provides sanction classes for enforcing gamification rules,
handling violations, and applying penalties or restrictions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from api.gamification.models import (
    Badge, UserBadge, DailyChallenge, UserDailyChallenge,
    Streak, LevelConfig, ContestCycle, UserAchievement
)
from api.gamification.choices import (
    BadgeRarity, BadgeCriteriaType, ChallengeAction,
    ContestCycleStatus, AchievementType
)
from api.gamification.exceptions import GamificationServiceError
from api.gamification.repositories import (
    BadgeRepository, UserBadgeRepository, StreakRepository,
    UserAchievementRepository
)
from api.gamification.helpers import CacheHelper, ValidationHelper

User = get_user_model()
logger = logging.getLogger(__name__)



class ViolationSeverity:
    """Violation severity levels."""
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"

    CHOICES = [
        (LOW, "Low"),
        (MEDIUM, "Medium"),
        (HIGH, "High"),
        (CRITICAL, "Critical"),
    ]

class ViolationType:
    """Violation types for gamification system."""
    
    POINTS_MANIPULATION = "points_manipulation"
    BADGE_EXPLOITATION = "badge_exploitation"
    CHALLENGE_CHEATING = "challenge_cheating"
    STREAK_MANIPULATION = "streak_manipulation"
    CONTEST_FRAUD = "contest_fraud"
    ACCOUNT_ABUSE = "account_abuse"
    RATE_LIMIT_VIOLATION = "rate_limit_violation"
    DATA_TAMPERING = "data_tampering"
    SYSTEM_ABUSE = "system_abuse"


class SanctionType:
    """Sanction types for rule violations."""
    
    WARNING = "warning"
    POINTS_DEDUCTION = "points_deduction"
    BADGE_REVOCATION = "badge_revocation"
    STREAK_RESET = "streak_reset"
    TEMPORARY_SUSPENSION = "temporary_suspension"
    PERMANENT_BAN = "permanent_ban"
    FEATURE_RESTRICTION = "feature_restriction"
    CONTEST_DISQUALIFICATION = "contest_disqualification"
    LEVEL_DEMOTION = "level_demotion"
    ACHIEVEMENT_REMOVAL = "achievement_removal"


class Violation:
    """Represents a rule violation."""
    
    def __init__(self, user_id: str, violation_type: str, description: str,
                 severity: str = "medium", evidence: Optional[Dict[str, Any]] = None,
                 detected_at: Optional[datetime] = None):
        self.user_id = user_id
        self.violation_type = violation_type
        self.description = description
        self.severity = severity  # low, medium, high, critical
        self.evidence = evidence or {}
        self.detected_at = detected_at or timezone.now()
        self.id = f"{user_id}_{violation_type}_{self.detected_at.timestamp()}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert violation to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'violation_type': self.violation_type,
            'description': self.description,
            'severity': self.severity,
            'evidence': self.evidence,
            'detected_at': self.detected_at.isoformat()
        }


class Sanction:
    """Represents a sanction applied for a violation."""
    
    def __init__(self, violation: Violation, sanction_type: str, description: str,
                 duration: Optional[timedelta] = None, parameters: Optional[Dict[str, Any]] = None,
                 applied_at: Optional[datetime] = None):
        self.violation = violation
        self.sanction_type = sanction_type
        self.description = description
        self.duration = duration
        self.parameters = parameters or {}
        self.applied_at = applied_at or timezone.now()
        self.id = f"{violation.id}_{sanction_type}"
        self.expires_at = self.applied_at + duration if duration else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert sanction to dictionary."""
        return {
            'id': self.id,
            'violation_id': self.violation.id,
            'sanction_type': self.sanction_type,
            'description': self.description,
            'duration_days': self.duration.days if self.duration else None,
            'parameters': self.parameters,
            'applied_at': self.applied_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }


class BaseSanctionEnforcer:
    """Base class for sanction enforcers."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.badge_repository = BadgeRepository()
        self.user_badge_repository = UserBadgeRepository()
        self.streak_repository = StreakRepository()
        self.achievement_repository = UserAchievementRepository()
    
    def apply_sanction(self, sanction: Sanction) -> Dict[str, Any]:
        """Apply a sanction."""
        raise NotImplementedError("Subclasses must implement apply_sanction method")
    
    def revert_sanction(self, sanction: Sanction) -> Dict[str, Any]:
        """Revert a sanction."""
        raise NotImplementedError("Subclasses must implement revert_sanction method")
    
    def is_sanction_active(self, sanction: Sanction) -> bool:
        """Check if sanction is still active."""
        if sanction.expires_at is None:
            return True  # Permanent sanction
        return timezone.now() < sanction.expires_at


class PointsDeductionEnforcer(BaseSanctionEnforcer):
    """Enforcer for points deduction sanctions."""
    
    def apply_sanction(self, sanction: Sanction) -> Dict[str, Any]:
        """Apply points deduction."""
        try:
            points_to_deduct = sanction.parameters.get('points', 0)
            if points_to_deduct <= 0:
                raise GamificationServiceError("Points to deduct must be positive")
            
            # Get user's current total points
            from api.gamification.helpers import UserHelper
            user_stats = UserHelper.get_user_gamification_stats(sanction.violation.user_id)
            current_points = user_stats['total_points']
            
            # Calculate deduction (can't go below zero)
            actual_deduction = min(points_to_deduct, current_points)
            
            # In a real implementation, you would:
            # 1. Create a negative achievement record
            # 2. Update user's point balance
            # 3. Log the deduction
            
            # For now, we'll simulate the deduction
            deduction_record = {
                'user_id': sanction.violation.user_id,
                'points_deducted': actual_deduction,
                'original_points': current_points,
                'new_points': current_points - actual_deduction,
                'reason': sanction.description,
                'violation_type': sanction.violation.violation_type,
                'applied_at': sanction.applied_at.isoformat()
            }
            
            # Invalidate user cache
            CacheHelper.invalidate_user_cache(sanction.violation.user_id)
            
            self.logger.info(f"Applied points deduction: {actual_deduction} points for user {sanction.violation.user_id}")
            
            return {
                'sanction_applied': True,
                'points_deducted': actual_deduction,
                'deduction_record': deduction_record
            }
            
        except Exception as e:
            self.logger.error(f"Error applying points deduction: {e}")
            raise GamificationServiceError(f"Failed to apply points deduction: {e}")
    
    def revert_sanction(self, sanction: Sanction) -> Dict[str, Any]:
        """Revert points deduction."""
        try:
            points_to_restore = sanction.parameters.get('points', 0)
            if points_to_restore <= 0:
                raise GamificationServiceError("Points to restore must be positive")
            
            # In a real implementation, you would:
            # 1. Remove the negative achievement record
            # 2. Restore user's point balance
            # 3. Log the restoration
            
            restoration_record = {
                'user_id': sanction.violation.user_id,
                'points_restored': points_to_restore,
                'reason': f"Reverted sanction: {sanction.description}",
                'reverted_at': timezone.now().isoformat()
            }
            
            # Invalidate user cache
            CacheHelper.invalidate_user_cache(sanction.violation.user_id)
            
            self.logger.info(f"Reverted points deduction: {points_to_restore} points for user {sanction.violation.user_id}")
            
            return {
                'sanction_reverted': True,
                'points_restored': points_to_restore,
                'restoration_record': restoration_record
            }
            
        except Exception as e:
            self.logger.error(f"Error reverting points deduction: {e}")
            raise GamificationServiceError(f"Failed to revert points deduction: {e}")


class BadgeRevocationEnforcer(BaseSanctionEnforcer):
    """Enforcer for badge revocation sanctions."""
    
    def apply_sanction(self, sanction: Sanction) -> Dict[str, Any]:
        """Apply badge revocation."""
        try:
            badge_ids = sanction.parameters.get('badge_ids', [])
            if not badge_ids:
                raise GamificationServiceError("No badge IDs specified for revocation")
            
            revoked_badges = []
            
            for badge_id in badge_ids:
                # Check if user has the badge
                user_badge = self.user_badge_repository.get_for_user(sanction.violation.user_id).by_badge(badge_id).first()
                
                if user_badge:
                    # Store badge info before deletion
                    badge_info = {
                        'badge_id': str(user_badge.badge.id),
                        'badge_name': user_badge.badge.name,
                        'badge_rarity': user_badge.badge.rarity,
                        'points_bonus': user_badge.badge.points_bonus,
                        'earned_at': user_badge.earned_at.isoformat(),
                        'revoked_at': sanction.applied_at.isoformat(),
                        'revocation_reason': sanction.description
                    }
                    
                    # Delete the user badge
                    self.user_badge_repository.delete(str(user_badge.id))
                    
                    revoked_badges.append(badge_info)
            
            # Invalidate user cache
            CacheHelper.invalidate_user_cache(sanction.violation.user_id)
            
            self.logger.info(f"Revoked {len(revoked_badges)} badges for user {sanction.violation.user_id}")
            
            return {
                'sanction_applied': True,
                'revoked_badges': revoked_badges,
                'total_revoked': len(revoked_badges)
            }
            
        except Exception as e:
            self.logger.error(f"Error applying badge revocation: {e}")
            raise GamificationServiceError(f"Failed to apply badge revocation: {e}")
    
    def revert_sanction(self, sanction: Sanction) -> Dict[str, Any]:
        """Revert badge revocation."""
        try:
            # This would require storing the original badge data
            # For now, we'll just log the revert attempt
            
            self.logger.info(f"Badge revocation revert requested for user {sanction.violation.user_id}")
            
            return {
                'sanction_reverted': True,
                'message': 'Badge revocation reverts require manual restoration',
                'note': 'Original badge data must be restored from backup'
            }
            
        except Exception as e:
            self.logger.error(f"Error reverting badge revocation: {e}")
            raise GamificationServiceError(f"Failed to revert badge revocation: {e}")


class StreakResetEnforcer(BaseSanctionEnforcer):
    """Enforcer for streak reset sanctions."""
    
    def apply_sanction(self, sanction: Sanction) -> Dict[str, Any]:
        """Apply streak reset."""
        try:
            # Get user's current streak
            streak = self.streak_repository.get_for_user(sanction.violation.user_id)
            
            if not streak:
                return {
                    'sanction_applied': True,
                    'message': 'No streak found to reset'
                }
            
            # Store original streak data
            original_streak = {
                'current_days': streak.current_days,
                'longest_days': streak.longest_days,
                'last_activity_date': streak.last_activity_date.isoformat(),
                'is_active': streak.is_active,
                'reset_at': sanction.applied_at.isoformat(),
                'reset_reason': sanction.description
            }
            
            # Reset the streak
            streak.current_days = 0
            streak.is_active = False
            streak.save()
            
            # Invalidate user cache
            CacheHelper.invalidate_user_cache(sanction.violation.user_id)
            
            self.logger.info(f"Reset streak for user {sanction.violation.user_id}")
            
            return {
                'sanction_applied': True,
                'original_streak': original_streak,
                'new_streak_days': 0
            }
            
        except Exception as e:
            self.logger.error(f"Error applying streak reset: {e}")
            raise GamificationServiceError(f"Failed to apply streak reset: {e}")
    
    def revert_sanction(self, sanction: Sanction) -> Dict[str, Any]:
        """Revert streak reset."""
        try:
            # This would require storing the original streak data
            # For now, we'll just reactivate the streak
            
            streak = self.streak_repository.get_for_user(sanction.violation.user_id)
            
            if streak:
                streak.is_active = True
                streak.save()
                
                # Invalidate user cache
                CacheHelper.invalidate_user_cache(sanction.violation.user_id)
            
            self.logger.info(f"Reactivated streak for user {sanction.violation.user_id}")
            
            return {
                'sanction_reverted': True,
                'message': 'Streak reactivated (original days not restored)'
            }
            
        except Exception as e:
            self.logger.error(f"Error reverting streak reset: {e}")
            raise GamificationServiceError(f"Failed to revert streak reset: {e}")


class TemporarySuspensionEnforcer(BaseSanctionEnforcer):
    """Enforcer for temporary suspension sanctions."""
    
    def apply_sanction(self, sanction: Sanction) -> Dict[str, Any]:
        """Apply temporary suspension."""
        try:
            if not sanction.duration:
                raise GamificationServiceError("Duration required for temporary suspension")
            
            # Store suspension record
            suspension_record = {
                'user_id': sanction.violation.user_id,
                'suspension_type': sanction.sanction_type,
                'reason': sanction.description,
                'suspended_at': sanction.applied_at.isoformat(),
                'expires_at': sanction.expires_at.isoformat(),
                'duration_days': sanction.duration.days,
                'violation_type': sanction.violation.violation_type
            }
            
            # Store in cache for quick access
            cache_key = f"suspension:{sanction.violation.user_id}"
            cache.set(cache_key, suspension_record, int(sanction.duration.total_seconds()))
            
            # In a real implementation, you might:
            # 1. Set user account to inactive
            # 2. Block API access
            # 3. Disable gamification features
            
            self.logger.info(f"Applied temporary suspension for user {sanction.violation.user_id} for {sanction.duration.days} days")
            
            return {
                'sanction_applied': True,
                'suspension_record': suspension_record,
                'expires_at': sanction.expires_at.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error applying temporary suspension: {e}")
            raise GamificationServiceError(f"Failed to apply temporary suspension: {e}")
    
    def revert_sanction(self, sanction: Sanction) -> Dict[str, Any]:
        """Revert temporary suspension."""
        try:
            # Remove suspension from cache
            cache_key = f"suspension:{sanction.violation.user_id}"
            cache.delete(cache_key)
            
            # In a real implementation, you would:
            # 1. Reactivate user account
            # 2. Restore API access
            # 3. Re-enable gamification features
            
            self.logger.info(f"Reverted temporary suspension for user {sanction.violation.user_id}")
            
            return {
                'sanction_reverted': True,
                'message': 'Suspension lifted, user access restored'
            }
            
        except Exception as e:
            self.logger.error(f"Error reverting temporary suspension: {e}")
            raise GamificationServiceError(f"Failed to revert temporary suspension: {e}")
    
    def is_sanction_active(self, sanction: Sanction) -> bool:
        """Check if suspension is still active."""
        cache_key = f"suspension:{sanction.violation.user_id}"
        suspension_record = cache.get(cache_key)
        
        if not suspension_record:
            return False
        
        expires_at = datetime.fromisoformat(suspension_record['expires_at'])
        return timezone.now() < expires_at


class AchievementRemovalEnforcer(BaseSanctionEnforcer):
    """Enforcer for achievement removal sanctions."""
    
    def apply_sanction(self, sanction: Sanction) -> Dict[str, Any]:
        """Apply achievement removal."""
        try:
            achievement_ids = sanction.parameters.get('achievement_ids', [])
            if not achievement_ids:
                raise GamificationServiceError("No achievement IDs specified for removal")
            
            removed_achievements = []
            
            for achievement_id in achievement_ids:
                # Check if achievement exists and belongs to user
                achievement = self.achievement_repository.get_for_user(sanction.violation.user_id).get_by_id(achievement_id)
                
                if achievement:
                    # Store achievement info before deletion
                    achievement_info = {
                        'achievement_id': str(achievement.id),
                        'achievement_type': achievement.achievement_type,
                        'points_awarded': achievement.points_awarded,
                        'rank': achievement.rank,
                        'awarded_at': achievement.awarded_at.isoformat(),
                        'removed_at': sanction.applied_at.isoformat(),
                        'removal_reason': sanction.description
                    }
                    
                    # Delete the achievement
                    self.achievement_repository.delete(str(achievement.id))
                    
                    removed_achievements.append(achievement_info)
            
            # Invalidate user cache
            CacheHelper.invalidate_user_cache(sanction.violation.user_id)
            
            self.logger.info(f"Removed {len(removed_achievements)} achievements for user {sanction.violation.user_id}")
            
            return {
                'sanction_applied': True,
                'removed_achievements': removed_achievements,
                'total_removed': len(removed_achievements),
                'total_points_lost': sum(a['points_awarded'] for a in removed_achievements)
            }
            
        except Exception as e:
            self.logger.error(f"Error applying achievement removal: {e}")
            raise GamificationServiceError(f"Failed to apply achievement removal: {e}")
    
    def revert_sanction(self, sanction: Sanction) -> Dict[str, Any]:
        """Revert achievement removal."""
        try:
            # This would require storing the original achievement data
            # For now, we'll just log the revert attempt
            
            self.logger.info(f"Achievement removal revert requested for user {sanction.violation.user_id}")
            
            return {
                'sanction_reverted': True,
                'message': 'Achievement removal reverts require manual restoration',
                'note': 'Original achievement data must be restored from backup'
            }
            
        except Exception as e:
            self.logger.error(f"Error reverting achievement removal: {e}")
            raise GamificationServiceError(f"Failed to revert achievement removal: {e}")


class SanctionManager:
    """Main manager for handling violations and sanctions."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.enforcers = {
            SanctionType.POINTS_DEDUCTION: PointsDeductionEnforcer(),
            SanctionType.BADGE_REVOCATION: BadgeRevocationEnforcer(),
            SanctionType.STREAK_RESET: StreakResetEnforcer(),
            SanctionType.TEMPORARY_SUSPENSION: TemporarySuspensionEnforcer(),
            SanctionType.ACHIEVEMENT_REMOVAL: AchievementRemovalEnforcer(),
        }
        self.active_sanctions_cache_key = "active_sanctions"
        self.cache_timeout = 3600  # 1 hour
    
    def detect_violation(self, user_id: str, violation_type: str, description: str,
                        severity: str = "medium", evidence: Optional[Dict[str, Any]] = None) -> Violation:
        """Detect and create a violation."""
        violation = Violation(
            user_id=user_id,
            violation_type=violation_type,
            description=description,
            severity=severity,
            evidence=evidence
        )
        
        self.logger.warning(f"Violation detected: {violation_type} for user {user_id} - {description}")
        
        return violation
    
    def apply_sanctions(self, violation: Violation, sanction_types: List[str],
                        sanction_params: Optional[List[Dict[str, Any]]] = None) -> List[Sanction]:
        """Apply multiple sanctions for a violation."""
        if sanction_params is None:
            sanction_params = [{} for _ in sanction_types]
        
        if len(sanction_types) != len(sanction_params):
            raise GamificationServiceError("Sanction types and parameters length mismatch")
        
        applied_sanctions = []
        
        for sanction_type, params in zip(sanction_types, sanction_params):
            try:
                # Determine sanction parameters based on violation severity
                final_params = self._determine_sanction_params(violation, sanction_type, params)
                
                # Create sanction
                sanction = Sanction(
                    violation=violation,
                    sanction_type=sanction_type,
                    description=f"Sanction for {violation.violation_type}: {violation.description}",
                    parameters=final_params
                )
                
                # Apply sanction
                enforcer = self.enforcers.get(sanction_type)
                if enforcer:
                    result = enforcer.apply_sanction(sanction)
                    sanction.applied_successfully = True
                    self.logger.info(f"Applied {sanction_type} sanction to user {violation.user_id}")
                else:
                    self.logger.warning(f"No enforcer found for sanction type: {sanction_type}")
                    sanction.applied_successfully = False
                
                applied_sanctions.append(sanction)
                
            except Exception as e:
                self.logger.error(f"Error applying {sanction_type} sanction: {e}")
                # Continue with other sanctions even if one fails
                
        # Store active sanctions
        self._store_active_sanctions(applied_sanctions)
        
        return applied_sanctions
    
    def _determine_sanction_params(self, violation: Violation, sanction_type: str,
                                 base_params: Dict[str, Any]) -> Dict[str, Any]:
        """Determine sanction parameters based on violation severity."""
        params = base_params.copy()
        
        # Severity-based scaling
        severity_multipliers = {
            'low': 0.5,
            'medium': 1.0,
            'high': 2.0,
            'critical': 5.0
        }
        
        multiplier = severity_multipliers.get(violation.severity, 1.0)
        
        # Apply severity-based adjustments
        if sanction_type == SanctionType.POINTS_DEDUCTION:
            if 'points' not in params:
                # Default points based on violation type
                default_points = {
                    ViolationType.POINTS_MANIPULATION: 1000,
                    ViolationType.BADGE_EXPLOITATION: 500,
                    ViolationType.CHALLENGE_CHEATING: 300,
                    ViolationType.STREAK_MANIPULATION: 200,
                    ViolationType.CONTEST_FRAUD: 1500,
                    ViolationType.ACCOUNT_ABUSE: 100,
                    ViolationType.RATE_LIMIT_VIOLATION: 50,
                    ViolationType.DATA_TAMPERING: 2000,
                    ViolationType.SYSTEM_ABUSE: 500
                }
                
                base_points = default_points.get(violation.violation_type, 100)
                params['points'] = int(base_points * multiplier)
        
        elif sanction_type == SanctionType.TEMPORARY_SUSPENSION:
            if 'duration' not in params:
                # Default duration based on violation type and severity
                base_days = {
                    ViolationType.POINTS_MANIPULATION: 7,
                    ViolationType.BADGE_EXPLOITATION: 3,
                    ViolationType.CHALLENGE_CHEATING: 5,
                    ViolationType.STREAK_MANIPULATION: 2,
                    ViolationType.CONTEST_FRAUD: 30,
                    ViolationType.ACCOUNT_ABUSE: 1,
                    ViolationType.RATE_LIMIT_VIOLATION: 1,
                    ViolationType.DATA_TAMPERING: 60,
                    ViolationType.SYSTEM_ABUSE: 14
                }
                
                base_duration_days = base_days.get(violation.violation_type, 1)
                params['duration'] = timedelta(days=int(base_duration_days * multiplier))
        
        return params
    
    def _store_active_sanctions(self, sanctions: List[Sanction]) -> None:
        """Store active sanctions in cache."""
        try:
            # Group sanctions by user
            user_sanctions = {}
            for sanction in sanctions:
                if sanction.applied_successfully:
                    user_id = sanction.violation.user_id
                    if user_id not in user_sanctions:
                        user_sanctions[user_id] = []
                    user_sanctions[user_id].append(sanction.to_dict())
            
            # Store in cache
            current_sanctions = cache.get(self.active_sanctions_cache_key, {})
            current_sanctions.update(user_sanctions)
            cache.set(self.active_sanctions_cache_key, current_sanctions, self.cache_timeout)
            
        except Exception as e:
            self.logger.error(f"Error storing active sanctions: {e}")
    
    def get_active_sanctions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get active sanctions for a user."""
        try:
            all_sanctions = cache.get(self.active_sanctions_cache_key, {})
            return all_sanctions.get(user_id, [])
        except Exception as e:
            self.logger.error(f"Error getting active sanctions: {e}")
            return []
    
    def is_user_suspended(self, user_id: str) -> bool:
        """Check if user is currently suspended."""
        active_sanctions = self.get_active_sanctions(user_id)
        
        for sanction in active_sanctions:
            if sanction['sanction_type'] == SanctionType.TEMPORARY_SUSPENSION:
                expires_at = datetime.fromisoformat(sanction['expires_at'])
                if timezone.now() < expires_at:
                    return True
        
        return False
    
    def clear_expired_sanctions(self) -> Dict[str, Any]:
        """Clear expired sanctions from cache."""
        try:
            all_sanctions = cache.get(self.active_sanctions_cache_key, {})
            cleared_count = 0
            
            now = timezone.now()
            updated_sanctions = {}
            
            for user_id, sanctions in all_sanctions.items():
                active_sanctions = []
                
                for sanction in sanctions:
                    expires_at = datetime.fromisoformat(sanction['expires_at'])
                    if expires_at > now:
                        active_sanctions.append(sanction)
                    else:
                        cleared_count += 1
                
                if active_sanctions:
                    updated_sanctions[user_id] = active_sanctions
            
            cache.set(self.active_sanctions_cache_key, updated_sanctions, self.cache_timeout)
            
            return {
                'cleared_count': cleared_count,
                'remaining_users': len(updated_sanctions),
                'cleared_at': now.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error clearing expired sanctions: {e}")
            return {'error': str(e)}
    
    def get_violation_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get violation statistics."""
        try:
            # This would typically query a violations database table
            # For now, return mock statistics
            
            since = timezone.now() - timedelta(days=days)
            
            mock_stats = {
                'period_days': days,
                'total_violations': 0,
                'violation_types': {},
                'severity_distribution': {
                    'low': 0,
                    'medium': 0,
                    'high': 0,
                    'critical': 0
                },
                'sanctions_applied': {
                    'points_deduction': 0,
                    'badge_revocation': 0,
                    'streak_reset': 0,
                    'temporary_suspension': 0,
                    'achievement_removal': 0
                },
                'most_common_violations': [],
                'generated_at': timezone.now().isoformat()
            }
            
            return mock_stats
            
        except Exception as e:
            self.logger.error(f"Error getting violation statistics: {e}")
            return {'error': str(e)}


# Rule definitions for different violation types
class RuleDefinitions:
    """Definitions of rules and their corresponding sanctions."""
    
    @staticmethod
    def get_rules() -> Dict[str, Dict[str, Any]]:
        """Get all rule definitions."""
        return {
            ViolationType.POINTS_MANIPULATION: {
                'description': 'Manipulating or exploiting point systems',
                'default_severity': 'high',
                'default_sanctions': [
                    SanctionType.POINTS_DEDUCTION,
                    SanctionType.ACHIEVEMENT_REMOVAL
                ],
                'auto_detect': True,
                'evidence_required': ['ip_address', 'user_agent', 'timestamp', 'action_details']
            },
            
            ViolationType.BADGE_EXPLOITATION: {
                'description': 'Exploiting badge system for unfair advantages',
                'default_severity': 'medium',
                'default_sanctions': [
                    SanctionType.BADGE_REVOCATION,
                    SanctionType.POINTS_DEDUCTION
                ],
                'auto_detect': True,
                'evidence_required': ['badge_id', 'earned_at', 'suspicious_activity']
            },
            
            ViolationType.CHALLENGE_CHEATING: {
                'description': 'Cheating in challenges or using exploits',
                'default_severity': 'medium',
                'default_sanctions': [
                    SanctionType.POINTS_DEDUCTION,
                    SanctionType.STREAK_RESET
                ],
                'auto_detect': True,
                'evidence_required': ['challenge_id', 'suspicious_patterns', 'completion_time']
            },
            
            ViolationType.STREAK_MANIPULATION: {
                'description': 'Manipulating streak tracking mechanisms',
                'default_severity': 'medium',
                'default_sanctions': [
                    SanctionType.STREAK_RESET,
                    SanctionType.POINTS_DEDUCTION
                ],
                'auto_detect': True,
                'evidence_required': ['streak_data', 'activity_patterns', 'timezone_anomalies']
            },
            
            ViolationType.CONTEST_FRAUD: {
                'description': 'Fraudulent activity in contests',
                'default_severity': 'high',
                'default_sanctions': [
                    SanctionType.CONTEST_DISQUALIFICATION,
                    SanctionType.ACHIEVEMENT_REMOVAL,
                    SanctionType.TEMPORARY_SUSPENSION
                ],
                'auto_detect': True,
                'evidence_required': ['contest_id', 'fraud_patterns', 'ip_analysis']
            },
            
            ViolationType.ACCOUNT_ABUSE: {
                'description': 'Creating or using multiple accounts for advantages',
                'default_severity': 'high',
                'default_sanctions': [
                    SanctionType.TEMPORARY_SUSPENSION,
                    SanctionType.POINTS_DEDUCTION
                ],
                'auto_detect': True,
                'evidence_required': ['account_relationships', 'ip_patterns', 'behavior_analysis']
            },
            
            ViolationType.RATE_LIMIT_VIOLATION: {
                'description': 'Exceeding rate limits or automated abuse',
                'default_severity': 'low',
                'default_sanctions': [
                    SanctionType.TEMPORARY_SUSPENSION,
                    SanctionType.POINTS_DEDUCTION
                ],
                'auto_detect': True,
                'evidence_required': ['request_patterns', 'rate_analysis', 'automation_detection']
            },
            
            ViolationType.DATA_TAMPERING: {
                'description': 'Tampering with gamification data or systems',
                'default_severity': 'critical',
                'default_sanctions': [
                    SanctionType.PERMANENT_BAN,
                    SanctionType.ACHIEVEMENT_REMOVAL,
                    SanctionType.BADGE_REVOCATION
                ],
                'auto_detect': True,
                'evidence_required': ['data_integrity_violations', 'system_logs', 'access_patterns']
            },
            
            ViolationType.SYSTEM_ABUSE: {
                'description': 'General abuse of gamification systems',
                'default_severity': 'medium',
                'default_sanctions': [
                    SanctionType.TEMPORARY_SUSPENSION,
                    SanctionType.POINTS_DEDUCTION
                ],
                'auto_detect': True,
                'evidence_required': ['abuse_patterns', 'system_impact']
            }
        }


# Convenience functions for common sanction operations
def detect_and_apply_sanctions(user_id: str, violation_type: str, description: str,
                              severity: str = "medium", evidence: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Detect violation and apply appropriate sanctions."""
    manager = SanctionManager()
    
    # Detect violation
    violation = manager.detect_violation(
        user_id=user_id,
        violation_type=violation_type,
        description=description,
        severity=severity,
        evidence=evidence
    )
    
    # Get rule-based sanctions
    rules = RuleDefinitions.get_rules()
    rule = rules.get(violation_type, {})
    sanction_types = rule.get('default_sanctions', [SanctionType.WARNING])
    
    # Apply sanctions
    applied_sanctions = manager.apply_sanctions(violation, sanction_types)
    
    return {
        'violation': violation.to_dict(),
        'applied_sanctions': [s.to_dict() for s in applied_sanctions],
        'total_sanctions': len(applied_sanctions)
    }


def check_user_suspension(user_id: str) -> Dict[str, Any]:
    """Check if user is suspended and return suspension details."""
    manager = SanctionManager()
    
    if manager.is_user_suspended(user_id):
        active_sanctions = manager.get_active_sanctions(user_id)
        
        for sanction in active_sanctions:
            if sanction['sanction_type'] == SanctionType.TEMPORARY_SUSPENSION:
                return {
                    'is_suspended': True,
                    'suspension_details': sanction,
                    'expires_at': sanction['expires_at']
                }
    
    return {'is_suspended': False}


def get_user_sanction_history(user_id: str) -> List[Dict[str, Any]]:
    """Get user's sanction history."""
    manager = SanctionManager()
    return manager.get_active_sanctions(user_id)


def clear_expired_sanctions() -> Dict[str, Any]:
    """Clear expired sanctions."""
    manager = SanctionManager()
    return manager.clear_expired_sanctions()
