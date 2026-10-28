# engagement/sanctions.py
"""
Sanction system for engagement gamification.
Handles user penalties, suspensions, and rule enforcement.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging

from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SanctionType(Enum):
    """Types of sanctions."""
    WARNING = "warning"
    TEMPORARY_SUSPENSION = "temporary_suspension"
    PERMANENT_SUSPENSION = "permanent_suspension"
    COINS_DEDUCTION = "coins_deduction"
    XP_DEDUCTION = "xp_deduction"
    ACHIEVEMENT_REVOCATION = "achievement_revocation"
    LEADERBOARD_REMOVAL = "leaderboard_removal"
    FEATURE_RESTRICTION = "feature_restriction"
    ACCOUNT_LOCKDOWN = "account_lockdown"


class SanctionSeverity(Enum):
    """Sanction severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SanctionRule:
    """Sanction rule definition."""
    name: str
    description: str
    sanction_type: SanctionType
    severity: SanctionSeverity
    trigger_conditions: Dict[str, Any]
    sanction_parameters: Dict[str, Any]
    is_active: bool = True
    auto_apply: bool = False
    review_required: bool = False


class BaseSanction(ABC):
    """Base sanction class."""
    
    def __init__(self, user, rule: SanctionRule, context: Dict[str, Any] = None):
        self.user = user
        self.rule = rule
        self.context = context or {}
        self.applied_at = timezone.now()
        self.expires_at = None
        self.is_active = True
    
    @abstractmethod
    def apply(self) -> Dict[str, Any]:
        """Apply the sanction."""
        pass
    
    @abstractmethod
    def revoke(self) -> Dict[str, Any]:
        """Revoke the sanction."""
        pass
    
    @abstractmethod
    def is_expired(self) -> bool:
        """Check if sanction is expired."""
        pass


class WarningSanction(BaseSanction):
    """Warning sanction."""
    
    def apply(self) -> Dict[str, Any]:
        """Apply warning sanction."""
        # Send warning notification
        from .services.notification_service import NotificationService
        
        NotificationService.send(
            self.user,
            'warning',
            title='⚠️ Warning',
            body=self.rule.description,
            data={
                'rule_name': self.rule.name,
                'severity': self.rule.severity.value,
                'applied_at': self.applied_at.isoformat()
            }
        )
        
        # Log warning
        logger.warning(f"Warning applied to user {self.user.username}: {self.rule.name}")
        
        return {
            'success': True,
            'message': 'Warning applied successfully',
            'notification_sent': True
        }
    
    def revoke(self) -> Dict[str, Any]:
        """Revoke warning (no action needed for warnings)."""
        return {
            'success': True,
            'message': 'Warning revoked (no action needed)'
        }
    
    def is_expired(self) -> bool:
        """Warnings never expire."""
        return False


class TemporarySuspensionSanction(BaseSanction):
    """Temporary suspension sanction."""
    
    def __init__(self, user, rule: SanctionRule, context: Dict[str, Any] = None):
        super().__init__(user, rule, context)
        suspension_hours = self.rule.sanction_parameters.get('hours', 24)
        self.expires_at = self.applied_at + timedelta(hours=suspension_hours)
    
    def apply(self) -> Dict[str, Any]:
        """Apply temporary suspension."""
        # Update user status
        self.user.status = 'suspended'
        self.user.save()
        
        # Revoke all active sessions
        self._revoke_sessions()
        
        # Send notification
        from .services.notification_service import NotificationService
        
        NotificationService.send(
            self.user,
            'suspension',
            title='🚫 Account Suspended',
            body=f'Your account has been temporarily suspended until {self.expires_at.strftime("%Y-%m-%d %H:%M")}',
            data={
                'suspension_type': 'temporary',
                'expires_at': self.expires_at.isoformat(),
                'reason': self.rule.description
            }
        )
        
        # Log suspension
        logger.warning(f"Temporary suspension applied to user {self.user.username}: {self.rule.name}")
        
        return {
            'success': True,
            'message': 'Temporary suspension applied',
            'expires_at': self.expires_at.isoformat(),
            'sessions_revoked': True
        }
    
    def revoke(self) -> Dict[str, Any]:
        """Revoke temporary suspension."""
        # Update user status
        self.user.status = 'active'
        self.user.save()
        
        # Send notification
        from .services.notification_service import NotificationService
        
        NotificationService.send(
            self.user,
            'suspension_lifted',
            title='✅ Suspension Lifted',
            body='Your account suspension has been lifted. Welcome back!',
            data={
                'suspension_lifted_at': timezone.now().isoformat(),
                'previous_suspension': self.rule.name
            }
        )
        
        # Log revocation
        logger.info(f"Suspension revoked for user {self.user.username}: {self.rule.name}")
        
        return {
            'success': True,
            'message': 'Suspension revoked successfully',
            'status_restored': 'active'
        }
    
    def is_expired(self) -> bool:
        """Check if suspension is expired."""
        return timezone.now() >= self.expires_at
    
    def _revoke_sessions(self):
        """Revoke all user sessions."""
        try:
            from django.contrib.sessions.models import Session
            
            # Remove all user sessions
            Session.objects.filter(
                session_data__contains=f'"user_id":{self.user.id}'
            ).delete()
            
        except Exception as exc:
            logger.error(f"Failed to revoke sessions for {self.user.username}: {exc}")


class PermanentSuspensionSanction(BaseSanction):
    """Permanent suspension sanction."""
    
    def apply(self) -> Dict[str, Any]:
        """Apply permanent suspension."""
        # Update user status
        self.user.status = 'banned'
        self.user.save()
        
        # Revoke all active sessions
        self._revoke_sessions()
        
        # Send notification
        from .services.notification_service import NotificationService
        
        NotificationService.send(
            self.user,
            'permanent_suspension',
            title='🚫 Account Permanently Suspended',
            body='Your account has been permanently suspended due to violations.',
            data={
                'suspension_type': 'permanent',
                'reason': self.rule.description,
                'applied_at': self.applied_at.isoformat()
            }
        )
        
        # Log permanent suspension
        logger.error(f"Permanent suspension applied to user {self.user.username}: {self.rule.name}")
        
        return {
            'success': True,
            'message': 'Permanent suspension applied',
            'status_changed': 'banned',
            'sessions_revoked': True
        }
    
    def revoke(self) -> Dict[str, Any]:
        """Revoke permanent suspension (requires admin override)."""
        # This should only be allowed by administrators
        return {
            'success': False,
            'message': 'Permanent suspensions cannot be revoked automatically'
        }
    
    def is_expired(self) -> bool:
        """Permanent suspensions never expire."""
        return False
    
    def _revoke_sessions(self):
        """Revoke all user sessions."""
        try:
            from django.contrib.sessions.models import Session
            
            # Remove all user sessions
            Session.objects.filter(
                session_data__contains=f'"user_id":{self.user.id}'
            ).delete()
            
        except Exception as exc:
            logger.error(f"Failed to revoke sessions for {self.user.username}: {exc}")


class CoinsDeductionSanction(BaseSanction):
    """Coins deduction sanction."""
    
    def apply(self) -> Dict[str, Any]:
        """Apply coins deduction."""
        deduction_amount = self.rule.sanction_parameters.get('amount', 100)
        
        # Get user's current coins (mock implementation)
        current_coins = self._get_user_coins()
        
        if current_coins < deduction_amount:
            return {
                'success': False,
                'message': 'Insufficient coins for deduction',
                'current_coins': current_coins,
                'deduction_amount': deduction_amount
            }
        
        # Deduct coins
        self._deduct_coins(deduction_amount)
        
        # Send notification
        from .services.notification_service import NotificationService
        
        NotificationService.send(
            self.user,
            'coins_deduction',
            title='💰 Coins Deducted',
            body=f'{deduction_amount} coins have been deducted from your account.',
            data={
                'deduction_amount': deduction_amount,
                'remaining_coins': current_coins - deduction_amount,
                'reason': self.rule.description
            }
        )
        
        # Log deduction
        logger.warning(f"Coins deduction applied to user {self.user.username}: {deduction_amount} coins")
        
        return {
            'success': True,
            'message': 'Coins deducted successfully',
            'deduction_amount': deduction_amount,
            'remaining_coins': current_coins - deduction_amount
        }
    
    def revoke(self) -> Dict[str, Any]:
        """Revoke coins deduction (restore coins)."""
        deduction_amount = self.rule.sanction_parameters.get('amount', 100)
        
        # Restore coins
        self._add_coins(deduction_amount)
        
        # Send notification
        from .services.notification_service import NotificationService
        
        NotificationService.send(
            self.user,
            'coins_restored',
            title='💰 Coins Restored',
            body=f'{deduction_amount} coins have been restored to your account.',
            data={
                'restoration_amount': deduction_amount,
                'reason': 'Sanction revoked'
            }
        )
        
        # Log restoration
        logger.info(f"Coins restored for user {self.user.username}: {deduction_amount} coins")
        
        return {
            'success': True,
            'message': 'Coins restored successfully',
            'restoration_amount': deduction_amount
        }
    
    def is_expired(self) -> bool:
        """Coins deductions never expire."""
        return False
    
    def _get_user_coins(self) -> int:
        """Get user's current coins (mock implementation)."""
        # In real implementation, this would query user's coin balance
        return 1000  # Mock value
    
    def _deduct_coins(self, amount: int):
        """Deduct coins from user account."""
        # In real implementation, this would update user's coin balance
        pass
    
    def _add_coins(self, amount: int):
        """Add coins to user account."""
        # In real implementation, this would update user's coin balance
        pass


class XPDeductionSanction(BaseSanction):
    """XP deduction sanction."""
    
    def apply(self) -> Dict[str, Any]:
        """Apply XP deduction."""
        deduction_amount = self.rule.sanction_parameters.get('amount', 50)
        
        # Get user's current XP (mock implementation)
        current_xp = self._get_user_xp()
        
        if current_xp < deduction_amount:
            return {
                'success': False,
                'message': 'Insufficient XP for deduction',
                'current_xp': current_xp,
                'deduction_amount': deduction_amount
            }
        
        # Deduct XP
        self._deduct_xp(deduction_amount)
        
        # Send notification
        from .services.notification_service import NotificationService
        
        NotificationService.send(
            self.user,
            'xp_deduction',
            title='⭐ XP Deducted',
            body=f'{deduction_amount} XP have been deducted from your account.',
            data={
                'deduction_amount': deduction_amount,
                'remaining_xp': current_xp - deduction_amount,
                'reason': self.rule.description
            }
        )
        
        # Log deduction
        logger.warning(f"XP deduction applied to user {self.user.username}: {deduction_amount} XP")
        
        return {
            'success': True,
            'message': 'XP deducted successfully',
            'deduction_amount': deduction_amount,
            'remaining_xp': current_xp - deduction_amount
        }
    
    def revoke(self) -> Dict[str, Any]:
        """Revoke XP deduction (restore XP)."""
        deduction_amount = self.rule.sanction_parameters.get('amount', 50)
        
        # Restore XP
        self._add_xp(deduction_amount)
        
        # Send notification
        from .services.notification_service import NotificationService
        
        NotificationService.send(
            self.user,
            'xp_restored',
            title='⭐ XP Restored',
            body=f'{deduction_amount} XP have been restored to your account.',
            data={
                'restoration_amount': deduction_amount,
                'reason': 'Sanction revoked'
            }
        )
        
        # Log restoration
        logger.info(f"XP restored for user {self.user.username}: {deduction_amount} XP")
        
        return {
            'success': True,
            'message': 'XP restored successfully',
            'restoration_amount': deduction_amount
        }
    
    def is_expired(self) -> bool:
        """XP deductions never expire."""
        return False
    
    def _get_user_xp(self) -> int:
        """Get user's current XP (mock implementation)."""
        # In real implementation, this would query user's XP
        return 500  # Mock value
    
    def _deduct_xp(self, amount: int):
        """Deduct XP from user account."""
        # In real implementation, this would update user's XP
        pass
    
    def _add_xp(self, amount: int):
        """Add XP to user account."""
        # In real implementation, this would update user's XP
        pass


class AchievementRevocationSanction(BaseSanction):
    """Achievement revocation sanction."""
    
    def apply(self) -> Dict[str, Any]:
        """Apply achievement revocation."""
        achievement_ids = self.rule.sanction_parameters.get('achievement_ids', [])
        revoke_all = self.rule.sanction_parameters.get('revoke_all', False)
        
        revoked_achievements = []
        
        if revoke_all:
            # Revoke all achievements
            from .models.achievement import UserAchievement
            
            user_achievements = UserAchievement.objects.filter(
                user=self.user,
                unlocked_at__isnull=False
            )
            
            for ua in user_achievements:
                ua.unlocked_at = None
                ua.save()
                revoked_achievements.append({
                    'id': ua.achievement.id,
                    'name': ua.achievement.name
                })
        else:
            # Revoke specific achievements
            from .models.achievement import UserAchievement
            
            for achievement_id in achievement_ids:
                try:
                    ua = UserAchievement.objects.get(
                        user=self.user,
                        achievement_id=achievement_id,
                        unlocked_at__isnull=False
                    )
                    ua.unlocked_at = None
                    ua.save()
                    revoked_achievements.append({
                        'id': ua.achievement.id,
                        'name': ua.achievement.name
                    })
                except UserAchievement.DoesNotExist:
                    continue
        
        # Send notification
        from .services.notification_service import NotificationService
        
        NotificationService.send(
            self.user,
            'achievement_revoked',
            title='🏆 Achievements Revoked',
            body=f'{len(revoked_achievements)} achievement(s) have been revoked.',
            data={
                'revoked_achievements': revoked_achievements,
                'reason': self.rule.description
            }
        )
        
        # Log revocation
        logger.warning(f"Achievement revocation applied to user {self.user.username}: {len(revoked_achievements)} achievements")
        
        return {
            'success': True,
            'message': 'Achievements revoked successfully',
            'revoked_count': len(revoked_achievements),
            'revoked_achievements': revoked_achievements
        }
    
    def revoke(self) -> Dict[str, Any]:
        """Revoke achievement revocation (restore achievements)."""
        achievement_ids = self.rule.sanction_parameters.get('achievement_ids', [])
        restore_all = self.rule.sanction_parameters.get('revoke_all', False)
        
        restored_achievements = []
        
        if restore_all:
            # Restore all previously revoked achievements
            # This would require tracking which achievements were revoked
            pass  # Complex logic for restoration
        else:
            # Restore specific achievements
            from .models.achievement import UserAchievement
            
            for achievement_id in achievement_ids:
                try:
                    ua = UserAchievement.objects.get(
                        user=self.user,
                        achievement_id=achievement_id,
                        unlocked_at__isnull=True
                    )
                    ua.unlocked_at = timezone.now()
                    ua.save()
                    restored_achievements.append({
                        'id': ua.achievement.id,
                        'name': ua.achievement.name
                    })
                except UserAchievement.DoesNotExist:
                    continue
        
        # Send notification
        from .services.notification_service import NotificationService
        
        NotificationService.send(
            self.user,
            'achievement_restored',
            title='🏆 Achievements Restored',
            body=f'{len(restored_achievements)} achievement(s) have been restored.',
            data={
                'restored_achievements': restored_achievements,
                'reason': 'Sanction revoked'
            }
        )
        
        # Log restoration
        logger.info(f"Achievement restoration applied to user {self.user.username}: {len(restored_achievements)} achievements")
        
        return {
            'success': True,
            'message': 'Achievements restored successfully',
            'restored_count': len(restored_achievements),
            'restored_achievements': restored_achievements
        }
    
    def is_expired(self) -> bool:
        """Achievement revocations never expire."""
        return False


class LeaderboardRemovalSanction(BaseSanction):
    """Leaderboard removal sanction."""
    
    def apply(self) -> Dict[str, Any]:
        """Apply leaderboard removal."""
        removal_days = self.rule.sanction_parameters.get('days', 7)
        
        # Remove user from leaderboard for specified period
        from .models.leaderboard import Leaderboard
        
        # Remove existing leaderboard entries
        removed_entries = []
        
        # Get current date
        current_date = timezone.now().date()
        
        # Remove entries for the specified period
        for i in range(removal_days):
            target_date = current_date + timedelta(days=i)
            
            try:
                entry = Leaderboard.objects.get(user=self.user, date=target_date)
                entry.delete()
                removed_entries.append(target_date.isoformat())
            except Leaderboard.DoesNotExist:
                continue
        
        # Send notification
        from .services.notification_service import NotificationService
        
        NotificationService.send(
            self.user,
            'leaderboard_removal',
            title='📊 Leaderboard Removal',
            body=f'You have been removed from the leaderboard for {removal_days} days.',
            data={
                'removal_days': removal_days,
                'removed_entries': removed_entries,
                'reason': self.rule.description
            }
        )
        
        # Log removal
        logger.warning(f"Leaderboard removal applied to user {self.user.username}: {removal_days} days")
        
        return {
            'success': True,
            'message': 'Leaderboard removal applied successfully',
            'removal_days': removal_days,
            'removed_entries': removed_entries
        }
    
    def revoke(self) -> Dict[str, Any]:
        """Revoke leaderboard removal."""
        # This would restore user to leaderboard
        # Complex logic for restoration
        return {
            'success': True,
            'message': 'Leaderboard removal revoked',
            'status_restored': 'active'
        }
    
    def is_expired(self) -> bool:
        """Check if leaderboard removal is expired."""
        removal_days = self.rule.sanction_parameters.get('days', 7)
        expiry_date = self.applied_at + timedelta(days=removal_days)
        return timezone.now() >= expiry_date


class FeatureRestrictionSanction(BaseSanction):
    """Feature restriction sanction."""
    
    def apply(self) -> Dict[str, Any]:
        """Apply feature restriction."""
        restricted_features = self.rule.sanction_parameters.get('features', [])
        restriction_hours = self.rule.sanction_parameters.get('hours', 24)
        
        self.expires_at = self.applied_at + timedelta(hours=restriction_hours)
        
        # Store restricted features in user profile or separate model
        # In real implementation, this would update user's restricted features
        
        # Send notification
        from .services.notification_service import NotificationService
        
        NotificationService.send(
            self.user,
            'feature_restriction',
            title='🚫 Feature Access Restricted',
            body=f'Access to certain features has been restricted for {restriction_hours} hours.',
            data={
                'restricted_features': restricted_features,
                'restriction_hours': restriction_hours,
                'expires_at': self.expires_at.isoformat(),
                'reason': self.rule.description
            }
        )
        
        # Log restriction
        logger.warning(f"Feature restriction applied to user {self.user.username}: {restricted_features}")
        
        return {
            'success': True,
            'message': 'Feature restriction applied successfully',
            'restricted_features': restricted_features,
            'restriction_hours': restriction_hours,
            'expires_at': self.expires_at.isoformat()
        }
    
    def revoke(self) -> Dict[str, Any]:
        """Revoke feature restriction."""
        # Remove restricted features from user profile
        # In real implementation, this would update user's restricted features
        
        # Send notification
        from .services.notification_service import NotificationService
        
        NotificationService.send(
            self.user,
            'feature_restriction_lifted',
            title='✅ Feature Access Restored',
            body='Your feature access has been fully restored.',
            data={
                'restriction_lifted_at': timezone.now().isoformat(),
                'reason': 'Sanction revoked'
            }
        )
        
        # Log revocation
        logger.info(f"Feature restriction revoked for user {self.user.username}")
        
        return {
            'success': True,
            'message': 'Feature restriction revoked successfully',
            'status_restored': 'full_access'
        }
    
    def is_expired(self) -> bool:
        """Check if feature restriction is expired."""
        return timezone.now() >= self.expires_at


class AccountLockdownSanction(BaseSanction):
    """Account lockdown sanction."""
    
    def apply(self) -> Dict[str, Any]:
        """Apply account lockdown."""
        lockdown_hours = self.rule.sanction_parameters.get('hours', 48)
        
        self.expires_at = self.applied_at + timedelta(hours=lockdown_hours)
        
        # Update user status
        self.user.status = 'locked'
        self.user.save()
        
        # Revoke all active sessions
        self._revoke_sessions()
        
        # Send notification
        from .services.notification_service import NotificationService
        
        NotificationService.send(
            self.user,
            'account_lockdown',
            title='🔒 Account Locked',
            body=f'Your account has been locked for {lockdown_hours} hours due to security concerns.',
            data={
                'lockdown_hours': lockdown_hours,
                'expires_at': self.expires_at.isoformat(),
                'reason': self.rule.description
            }
        )
        
        # Log lockdown
        logger.error(f"Account lockdown applied to user {self.user.username}: {lockdown_hours} hours")
        
        return {
            'success': True,
            'message': 'Account lockdown applied successfully',
            'lockdown_hours': lockdown_hours,
            'expires_at': self.expires_at.isoformat(),
            'sessions_revoked': True
        }
    
    def revoke(self) -> Dict[str, Any]:
        """Revoke account lockdown."""
        # Update user status
        self.user.status = 'active'
        self.user.save()
        
        # Send notification
        from .services.notification_service import NotificationService
        
        NotificationService.send(
            self.user,
            'account_unlocked',
            title='🔓 Account Unlocked',
            body='Your account has been unlocked. Welcome back!',
            data={
                'unlocked_at': timezone.now().isoformat(),
                'reason': 'Sanction revoked'
            }
        )
        
        # Log revocation
        logger.info(f"Account lockdown revoked for user {self.user.username}")
        
        return {
            'success': True,
            'message': 'Account lockdown revoked successfully',
            'status_restored': 'active'
        }
    
    def is_expired(self) -> bool:
        """Check if account lockdown is expired."""
        return timezone.now() >= self.expires_at
    
    def _revoke_sessions(self):
        """Revoke all user sessions."""
        try:
            from django.contrib.sessions.models import Session
            
            # Remove all user sessions
            Session.objects.filter(
                session_data__contains=f'"user_id":{self.user.id}'
            ).delete()
            
        except Exception as exc:
            logger.error(f"Failed to revoke sessions for {self.user.username}: {exc}")


# ── Sanction Factory ─────────────────────────────────────────────────────

class SanctionFactory:
    """Factory for creating sanction instances."""
    
    @staticmethod
    def create_sanction(user, rule: SanctionRule, context: Dict[str, Any] = None) -> BaseSanction:
        """Create sanction instance based on rule type."""
        sanction_map = {
            SanctionType.WARNING: WarningSanction,
            SanctionType.TEMPORARY_SUSPENSION: TemporarySuspensionSanction,
            SanctionType.PERMANENT_SUSPENSION: PermanentSuspensionSanction,
            SanctionType.COINS_DEDUCTION: CoinsDeductionSanction,
            SanctionType.XP_DEDUCTION: XPDeductionSanction,
            SanctionType.ACHIEVEMENT_REVOCATION: AchievementRevocationSanction,
            SanctionType.LEADERBOARD_REMOVAL: LeaderboardRemovalSanction,
            SanctionType.FEATURE_RESTRICTION: FeatureRestrictionSanction,
            SanctionType.ACCOUNT_LOCKDOWN: AccountLockdownSanction,
        }
        
        sanction_class = sanction_map.get(rule.sanction_type)
        if sanction_class:
            return sanction_class(user, rule, context)
        
        raise ValueError(f"Unknown sanction type: {rule.sanction_type}")


# ── Sanction Manager ─────────────────────────────────────────────────────

class SanctionManager:
    """Manager for applying and managing sanctions."""
    
    def __init__(self):
        self.rules = []
        self.active_sanctions = {}
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """Setup default sanction rules."""
        self.rules = [
            # Warning rules
            SanctionRule(
                name="minor_violation_warning",
                description="Warning for minor policy violations",
                sanction_type=SanctionType.WARNING,
                severity=SanctionSeverity.LOW,
                trigger_conditions={"violation_count": 1, "severity": "low"},
                sanction_parameters={},
                auto_apply=True,
                review_required=False
            ),
            
            # Temporary suspension rules
            SanctionRule(
                name="spam_behavior_suspension",
                description="Temporary suspension for spam behavior",
                sanction_type=SanctionType.TEMPORARY_SUSPENSION,
                severity=SanctionSeverity.MEDIUM,
                trigger_conditions={"violation_type": "spam", "count": 3},
                sanction_parameters={"hours": 24},
                auto_apply=False,
                review_required=True
            ),
            
            # Coins deduction rules
            SanctionRule(
                name="cheating_coins_deduction",
                description="Coins deduction for cheating behavior",
                sanction_type=SanctionType.COINS_DEDUCTION,
                severity=SanctionSeverity.HIGH,
                trigger_conditions={"violation_type": "cheating"},
                sanction_parameters={"amount": 500},
                auto_apply=True,
                review_required=True
            ),
            
            # Achievement revocation rules
            SanctionRule(
                name="exploitation_achievement_revocation",
                description="Achievement revocation for exploitation",
                sanction_type=SanctionType.ACHIEVEMENT_REVOCATION,
                severity=SanctionSeverity.HIGH,
                trigger_conditions={"violation_type": "exploitation"},
                sanction_parameters={"revoke_all": True},
                auto_apply=False,
                review_required=True
            ),
            
            # Permanent suspension rules
            SanctionRule(
                name="severe_violation_ban",
                description="Permanent ban for severe violations",
                sanction_type=SanctionType.PERMANENT_SUSPENSION,
                severity=SanctionSeverity.CRITICAL,
                trigger_conditions={"violation_type": "severe", "count": 1},
                sanction_parameters={},
                auto_apply=False,
                review_required=True
            ),
        ]
    
    def check_violations(self, user, violation_data: Dict[str, Any]) -> List[SanctionRule]:
        """Check if violations trigger any sanction rules."""
        triggered_rules = []
        
        for rule in self.rules:
            if not rule.is_active:
                continue
            
            if self._evaluate_conditions(rule.trigger_conditions, violation_data):
                triggered_rules.append(rule)
        
        return triggered_rules
    
    def _evaluate_conditions(self, conditions: Dict[str, Any], violation_data: Dict[str, Any]) -> bool:
        """Evaluate if conditions are met."""
        for key, expected_value in conditions.items():
            if key not in violation_data:
                return False
            
            actual_value = violation_data[key]
            
            if isinstance(expected_value, (list, tuple)):
                if actual_value not in expected_value:
                    return False
            elif actual_value != expected_value:
                return False
        
        return True
    
    def apply_sanctions(self, user, violation_data: Dict[str, Any], 
                       auto_apply: bool = False, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Apply sanctions for violations."""
        triggered_rules = self.check_violations(user, violation_data)
        applied_sanctions = []
        
        for rule in triggered_rules:
            # Check if sanction should be auto-applied
            if rule.auto_apply or auto_apply:
                # Check if review is required
                if rule.review_required and not auto_apply:
                    applied_sanctions.append({
                        'rule': rule,
                        'status': 'pending_review',
                        'message': 'Sanction requires review before application'
                    })
                    continue
                
                # Apply sanction
                try:
                    sanction = SanctionFactory.create_sanction(user, rule, context)
                    result = sanction.apply()
                    
                    # Store active sanction
                    self.active_sanctions[user.id] = sanction
                    
                    applied_sanctions.append({
                        'rule': rule,
                        'status': 'applied',
                        'result': result,
                        'sanction': sanction
                    })
                    
                except Exception as exc:
                    logger.error(f"Failed to apply sanction {rule.name}: {exc}")
                    applied_sanctions.append({
                        'rule': rule,
                        'status': 'failed',
                        'error': str(exc)
                    })
            else:
                applied_sanctions.append({
                    'rule': rule,
                    'status': 'manual_review_required',
                    'message': 'Sanction requires manual application'
                })
        
        return applied_sanctions
    
    def revoke_sanction(self, user, rule_name: str) -> Dict[str, Any]:
        """Revoke a specific sanction."""
        if user.id not in self.active_sanctions:
            return {
                'success': False,
                'message': 'No active sanctions found for user'
            }
        
        sanction = self.active_sanctions[user.id]
        
        if sanction.rule.name != rule_name:
            return {
                'success': False,
                'message': f'Sanction {rule_name} not found for user'
            }
        
        try:
            result = sanction.revoke()
            del self.active_sanctions[user.id]
            
            return {
                'success': True,
                'message': 'Sanction revoked successfully',
                'result': result
            }
            
        except Exception as exc:
            logger.error(f"Failed to revoke sanction {rule_name}: {exc}")
            return {
                'success': False,
                'error': str(exc)
            }
    
    def get_active_sanctions(self, user) -> List[BaseSanction]:
        """Get all active sanctions for user."""
        sanctions = []
        
        if user.id in self.active_sanctions:
            sanction = self.active_sanctions[user.id]
            
            # Check if sanction is expired
            if sanction.is_expired():
                # Auto-revoke expired sanctions
                sanction.revoke()
                del self.active_sanctions[user.id]
            else:
                sanctions.append(sanction)
        
        return sanctions
    
    def check_expired_sanctions(self) -> int:
        """Check and revoke expired sanctions."""
        expired_count = 0
        expired_user_ids = []
        
        for user_id, sanction in self.active_sanctions.items():
            if sanction.is_expired():
                try:
                    sanction.revoke()
                    expired_user_ids.append(user_id)
                    expired_count += 1
                except Exception as exc:
                    logger.error(f"Failed to revoke expired sanction for user {user_id}: {exc}")
        
        # Remove expired sanctions from active list
        for user_id in expired_user_ids:
            del self.active_sanctions[user_id]
        
        return expired_count
    
    def add_rule(self, rule: SanctionRule):
        """Add a new sanction rule."""
        self.rules.append(rule)
    
    def remove_rule(self, rule_name: str) -> bool:
        """Remove a sanction rule."""
        for i, rule in enumerate(self.rules):
            if rule.name == rule_name:
                del self.rules[i]
                return True
        return False
    
    def get_rule(self, rule_name: str) -> Optional[SanctionRule]:
        """Get a specific sanction rule."""
        for rule in self.rules:
            if rule.name == rule_name:
                return rule
        return None
    
    def list_rules(self) -> List[SanctionRule]:
        """List all sanction rules."""
        return self.rules.copy()


# Global sanction manager instance
sanction_manager = SanctionManager()
