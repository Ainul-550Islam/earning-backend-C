# =============================================================================
# auto_mod/sanctions.py
# =============================================================================

"""
Sanctions management for auto moderation system.
Provides user sanctions, penalties, and enforcement mechanisms.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models, transaction
from django.core.cache import cache
from django.contrib.auth import get_user_model

from .models import SuspiciousSubmission, ModerationDecision
from .constants import RISK_SCORE_HIGH, RISK_SCORE_MEDIUM
from .exceptions import ModerationError, ValidationError

logger = logging.getLogger(__name__)

User = get_user_model()


class SanctionType:
    """Sanction types."""
    WARNING = "warning"
    TEMPORARY_SUSPENSION = "temporary_suspension"
    PERMANENT_BAN = "permanent_ban"
    CONTENT_RESTRICTION = "content_restriction"
    FEATURE_LIMITATION = "feature_limitation"
    PROBATION = "probation"
    DEMOTION = "demotion"


class SanctionSeverity:
    """Sanction severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class UserSanction:
    """User sanction model representation."""
    
    def __init__(self, user_id: Union[str, int], sanction_type: str, 
                 severity: str, reason: str, duration_days: int = None,
                 metadata: Dict[str, Any] = None):
        self.user_id = user_id
        self.sanction_type = sanction_type
        self.severity = severity
        self.reason = reason
        self.duration_days = duration_days
        self.metadata = metadata or {}
        self.created_at = timezone.now()
        self.expires_at = None
        self.is_active = True
        
        if duration_days:
            self.expires_at = self.created_at + timedelta(days=duration_days)


class SanctionEngine:
    """
    Engine for applying and managing user sanctions.
    """
    
    def __init__(self):
        self.active_sanctions = {}
        self.sanction_rules = self._initialize_rules()
        self._load_active_sanctions()
    
    def _initialize_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize sanction rules."""
        return {
            'high_risk_submissions': {
                'threshold': 3,  # Number of high-risk submissions
                'sanction_type': SanctionType.WARNING,
                'severity': SanctionSeverity.MEDIUM,
                'duration_days': 7,
            },
            'repeated_violations': {
                'threshold': 5,  # Number of violations
                'sanction_type': SanctionType.TEMPORARY_SUSPENSION,
                'severity': SanctionSeverity.HIGH,
                'duration_days': 30,
            },
            'severe_content': {
                'risk_threshold': RISK_SCORE_HIGH,
                'sanction_type': SanctionType.CONTENT_RESTRICTION,
                'severity': SanctionSeverity.HIGH,
                'duration_days': 14,
            },
            'critical_violation': {
                'risk_threshold': 0.9,
                'sanction_type': SanctionType.PERMANENT_BAN,
                'severity': SanctionSeverity.CRITICAL,
                'duration_days': None,  # Permanent
            }
        }
    
    def _load_active_sanctions(self) -> None:
        """Load active sanctions from cache/database."""
        # This would load from database in production
        # For now, use empty cache
        self.active_sanctions = {}
    
    def evaluate_submission_for_sanction(self, submission: SuspiciousSubmission) -> List[UserSanction]:
        """
        Evaluate a submission for potential sanctions.
        
        Args:
            submission: Submission to evaluate
            
        Returns:
            List of recommended sanctions
        """
        sanctions = []
        
        try:
            # Check high-risk submissions
            if submission.risk_score >= RISK_SCORE_HIGH:
                sanction = self._create_risk_based_sanction(submission)
                if sanction:
                    sanctions.append(sanction)
            
            # Check repeated violations
            violation_count = self._count_user_violations(submission.user_id)
            if violation_count >= self.sanction_rules['repeated_violations']['threshold']:
                sanction = self._create_repeated_violation_sanction(submission.user_id, violation_count)
                if sanction:
                    sanctions.append(sanction)
            
            # Check severe content
            if submission.risk_score >= self.sanction_rules['severe_content']['risk_threshold']:
                sanction = self._create_severe_content_sanction(submission)
                if sanction:
                    sanctions.append(sanction)
            
            # Check critical violations
            if submission.risk_score >= self.sanction_rules['critical_violation']['risk_threshold']:
                sanction = self._create_critical_sanction(submission)
                if sanction:
                    sanctions.append(sanction)
            
            return sanctions
            
        except Exception as exc:
            logger.error(f"Sanction evaluation failed: {exc}")
            return []
    
    def _create_risk_based_sanction(self, submission: SuspiciousSubmission) -> Optional[UserSanction]:
        """Create risk-based sanction."""
        rule = self.sanction_rules['high_risk_submissions']
        
        return UserSanction(
            user_id=submission.user_id,
            sanction_type=rule['sanction_type'],
            severity=rule['severity'],
            reason=f"High-risk submission detected (score: {submission.risk_score})",
            duration_days=rule['duration_days'],
            metadata={
                'submission_id': str(submission.id),
                'risk_score': submission.risk_score,
                'flag_reason': submission.flag_reason
            }
        )
    
    def _create_repeated_violation_sanction(self, user_id: Union[str, int], 
                                          violation_count: int) -> Optional[UserSanction]:
        """Create repeated violation sanction."""
        rule = self.sanction_rules['repeated_violations']
        
        return UserSanction(
            user_id=user_id,
            sanction_type=rule['sanction_type'],
            severity=rule['severity'],
            reason=f"Repeated violations detected ({violation_count} violations)",
            duration_days=rule['duration_days'],
            metadata={
                'violation_count': violation_count,
                'sanction_rule': 'repeated_violations'
            }
        )
    
    def _create_severe_content_sanction(self, submission: SuspiciousSubmission) -> Optional[UserSanction]:
        """Create severe content sanction."""
        rule = self.sanction_rules['severe_content']
        
        return UserSanction(
            user_id=submission.user_id,
            sanction_type=rule['sanction_type'],
            severity=rule['severity'],
            reason=f"Severe content violation detected (score: {submission.risk_score})",
            duration_days=rule['duration_days'],
            metadata={
                'submission_id': str(submission.id),
                'risk_score': submission.risk_score,
                'sanction_rule': 'severe_content'
            }
        )
    
    def _create_critical_sanction(self, submission: SuspiciousSubmission) -> Optional[UserSanction]:
        """Create critical violation sanction."""
        rule = self.sanction_rules['critical_violation']
        
        return UserSanction(
            user_id=submission.user_id,
            sanction_type=rule['sanction_type'],
            severity=rule['severity'],
            reason=f"Critical violation detected (score: {submission.risk_score})",
            duration_days=rule['duration_days'],
            metadata={
                'submission_id': str(submission.id),
                'risk_score': submission.risk_score,
                'sanction_rule': 'critical_violation'
            }
        )
    
    def _count_user_violations(self, user_id: Union[str, int], days: int = 30) -> int:
        """Count user violations in the last N days."""
        try:
            start_date = timezone.now() - timedelta(days=days)
            
            # Count rejected submissions
            rejected_count = SuspiciousSubmission.objects.filter(
                user_id=user_id,
                status='rejected',
                created_at__gte=start_date
            ).count()
            
            # Count escalated submissions
            escalated_count = SuspiciousSubmission.objects.filter(
                user_id=user_id,
                status='escalated',
                created_at__gte=start_date
            ).count()
            
            return rejected_count + escalated_count
            
        except Exception as exc:
            logger.error(f"Count violations failed: {exc}")
            return 0
    
    def apply_sanction(self, sanction: UserSanction) -> bool:
        """
        Apply a sanction to a user.
        
        Args:
            sanction: Sanction to apply
            
        Returns:
            True if successful
        """
        try:
            # Store sanction
            self._store_sanction(sanction)
            
            # Apply sanction effects
            self._apply_sanction_effects(sanction)
            
            # Log sanction
            self._log_sanction(sanction)
            
            logger.info(f"Applied sanction {sanction.sanction_type} to user {sanction.user_id}")
            return True
            
        except Exception as exc:
            logger.error(f"Apply sanction failed: {exc}")
            return False
    
    def _store_sanction(self, sanction: UserSanction) -> None:
        """Store sanction in cache/database."""
        # Add to active sanctions
        user_id = str(sanction.user_id)
        if user_id not in self.active_sanctions:
            self.active_sanctions[user_id] = []
        
        self.active_sanctions[user_id].append(sanction)
        
        # Cache for 1 hour
        cache_key = f"user_sanctions:{user_id}"
        cache.set(cache_key, self.active_sanctions[user_id], timeout=3600)
    
    def _apply_sanction_effects(self, sanction: UserSanction) -> None:
        """Apply the effects of a sanction."""
        try:
            user = User.objects.get(id=sanction.user_id)
            
            if sanction.sanction_type == SanctionType.WARNING:
                # Add warning flag to user profile
                if not hasattr(user, 'sanction_warnings'):
                    user.sanction_warnings = 0
                user.sanction_warnings += 1
                user.save(update_fields=['sanction_warnings'])
            
            elif sanction.sanction_type == SanctionType.TEMPORARY_SUSPENSION:
                # Suspend user account
                user.is_active = False
                user.suspended_until = sanction.expires_at
                user.save(update_fields=['is_active', 'suspended_until'])
            
            elif sanction.sanction_type == SanctionType.PERMANENT_BAN:
                # Permanently ban user
                user.is_active = False
                user.is_banned = True
                user.banned_at = timezone.now()
                user.save(update_fields=['is_active', 'is_banned', 'banned_at'])
            
            elif sanction.sanction_type == SanctionType.CONTENT_RESTRICTION:
                # Restrict content posting
                if not hasattr(user, 'content_restricted'):
                    user.content_restricted = False
                user.content_restricted = True
                user.content_restricted_until = sanction.expires_at
                user.save(update_fields=['content_restricted', 'content_restricted_until'])
            
            elif sanction.sanction_type == SanctionType.FEATURE_LIMITATION:
                # Limit user features
                if not hasattr(user, 'features_limited'):
                    user.features_limited = False
                user.features_limited = True
                user.features_limited_until = sanction.expires_at
                user.save(update_fields=['features_limited', 'features_limited_until'])
            
        except User.DoesNotExist:
            logger.warning(f"User {sanction.user_id} not found for sanction application")
        except Exception as exc:
            logger.error(f"Apply sanction effects failed: {exc}")
    
    def _log_sanction(self, sanction: UserSanction) -> None:
        """Log sanction application."""
        log_data = {
            'user_id': sanction.user_id,
            'sanction_type': sanction.sanction_type,
            'severity': sanction.severity,
            'reason': sanction.reason,
            'created_at': sanction.created_at.isoformat(),
            'expires_at': sanction.expires_at.isoformat() if sanction.expires_at else None,
            'metadata': sanction.metadata
        }
        
        logger.info(f"Sanction applied: {log_data}")
        
        # This would be stored in audit logs in production
        # audit_logs.log_event('sanction_applied', log_data)
    
    def check_user_sanctions(self, user_id: Union[str, int]) -> List[UserSanction]:
        """
        Check active sanctions for a user.
        
        Args:
            user_id: User ID to check
            
        Returns:
            List of active sanctions
        """
        user_id = str(user_id)
        
        # Check cache first
        cache_key = f"user_sanctions:{user_id}"
        cached_sanctions = cache.get(cache_key)
        if cached_sanctions:
            return cached_sanctions
        
        # Load from active sanctions
        sanctions = self.active_sanctions.get(user_id, [])
        
        # Filter expired sanctions
        active_sanctions = []
        for sanction in sanctions:
            if sanction.is_active and (not sanction.expires_at or sanction.expires_at > timezone.now()):
                active_sanctions.append(sanction)
        
        # Update cache
        cache.set(cache_key, active_sanctions, timeout=3600)
        
        return active_sanctions
    
    def remove_expired_sanctions(self) -> int:
        """
        Remove expired sanctions.
        
        Returns:
            Number of sanctions removed
        """
        removed_count = 0
        now = timezone.now()
        
        for user_id, sanctions in list(self.active_sanctions.items()):
            active_sanctions = []
            
            for sanction in sanctions:
                if sanction.expires_at and sanction.expires_at <= now:
                    # Remove expired sanction
                    self._remove_sanction_effects(sanction)
                    removed_count += 1
                else:
                    active_sanctions.append(sanction)
            
            if active_sanctions:
                self.active_sanctions[user_id] = active_sanctions
            else:
                del self.active_sanctions[user_id]
            
            # Update cache
            cache_key = f"user_sanctions:{user_id}"
            cache.set(cache_key, active_sanctions, timeout=3600)
        
        if removed_count > 0:
            logger.info(f"Removed {removed_count} expired sanctions")
        
        return removed_count
    
    def _remove_sanction_effects(self, sanction: UserSanction) -> None:
        """Remove the effects of an expired sanction."""
        try:
            user = User.objects.get(id=sanction.user_id)
            
            if sanction.sanction_type == SanctionType.TEMPORARY_SUSPENSION:
                # Reactivate user
                user.is_active = True
                user.suspended_until = None
                user.save(update_fields=['is_active', 'suspended_until'])
            
            elif sanction.sanction_type == SanctionType.CONTENT_RESTRICTION:
                # Remove content restriction
                user.content_restricted = False
                user.content_restricted_until = None
                user.save(update_fields=['content_restricted', 'content_restricted_until'])
            
            elif sanction.sanction_type == SanctionType.FEATURE_LIMITATION:
                # Remove feature limitation
                user.features_limited = False
                user.features_limited_until = None
                user.save(update_fields=['features_limited', 'features_limited_until'])
            
        except User.DoesNotExist:
            logger.warning(f"User {sanction.user_id} not found for sanction removal")
        except Exception as exc:
            logger.error(f"Remove sanction effects failed: {exc}")
    
    def get_sanction_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get sanction statistics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Sanction statistics
        """
        try:
            stats = {
                'total_sanctions': 0,
                'by_type': {},
                'by_severity': {},
                'active_sanctions': 0,
                'expired_sanctions': 0,
                'period_days': days
            }
            
            # Count active sanctions
            for user_id, sanctions in self.active_sanctions.items():
                for sanction in sanctions:
                    if sanction.is_active:
                        stats['active_sanctions'] += 1
                        stats['total_sanctions'] += 1
                        
                        # Count by type
                        sanction_type = sanction.sanction_type
                        stats['by_type'][sanction_type] = stats['by_type'].get(sanction_type, 0) + 1
                        
                        # Count by severity
                        severity = sanction.severity
                        stats['by_severity'][severity] = stats['by_severity'].get(severity, 0) + 1
            
            return stats
            
        except Exception as exc:
            logger.error(f"Get sanction statistics failed: {exc}")
            return {'error': str(exc)}


class SanctionManager:
    """
    High-level manager for sanctions.
    """
    
    def __init__(self):
        self.engine = SanctionEngine()
    
    def process_submission_sanctions(self, submission: SuspiciousSubmission) -> Dict[str, Any]:
        """
        Process sanctions for a submission.
        
        Args:
            submission: Submission to process
            
        Returns:
            Processing result
        """
        try:
            # Evaluate for sanctions
            recommended_sanctions = self.engine.evaluate_submission_for_sanction(submission)
            
            applied_sanctions = []
            
            # Apply recommended sanctions
            for sanction in recommended_sanctions:
                if self.engine.apply_sanction(sanction):
                    applied_sanctions.append({
                        'type': sanction.sanction_type,
                        'severity': sanction.severity,
                        'duration_days': sanction.duration_days,
                        'reason': sanction.reason
                    })
            
            return {
                'submission_id': str(submission.id),
                'user_id': str(submission.user_id),
                'recommended_sanctions': len(recommended_sanctions),
                'applied_sanctions': len(applied_sanctions),
                'sanctions': applied_sanctions,
                'processed_at': timezone.now().isoformat()
            }
            
        except Exception as exc:
            logger.error(f"Process submission sanctions failed: {exc}")
            raise ModerationError(f"Failed to process sanctions: {exc}")
    
    def check_user_status(self, user_id: Union[str, int]) -> Dict[str, Any]:
        """
        Check user's sanction status.
        
        Args:
            user_id: User ID to check
            
        Returns:
            User status information
        """
        try:
            sanctions = self.engine.check_user_sanctions(user_id)
            
            # Determine user status
            is_suspended = any(s.sanction_type == SanctionType.TEMPORARY_SUSPENSION for s in sanctions)
            is_banned = any(s.sanction_type == SanctionType.PERMANENT_BAN for s in sanctions)
            content_restricted = any(s.sanction_type == SanctionType.CONTENT_RESTRICTION for s in sanctions)
            features_limited = any(s.sanction_type == SanctionType.FEATURE_LIMITATION for s in sanctions)
            
            return {
                'user_id': str(user_id),
                'active_sanctions': len(sanctions),
                'is_suspended': is_suspended,
                'is_banned': is_banned,
                'content_restricted': content_restricted,
                'features_limited': features_limited,
                'sanctions': [
                    {
                        'type': s.sanction_type,
                        'severity': s.severity,
                        'reason': s.reason,
                        'created_at': s.created_at.isoformat(),
                        'expires_at': s.expires_at.isoformat() if s.expires_at else None,
                    }
                    for s in sanctions
                ],
                'checked_at': timezone.now().isoformat()
            }
            
        except Exception as exc:
            logger.error(f"Check user status failed: {exc}")
            raise ModerationError(f"Failed to check user status: {exc}")
    
    def lift_sanction(self, user_id: Union[str, int], sanction_type: str = None) -> bool:
        """
        Lift sanctions for a user.
        
        Args:
            user_id: User ID
            sanction_type: Specific sanction type to lift (None for all)
            
        Returns:
            True if successful
        """
        try:
            user_id = str(user_id)
            sanctions = self.engine.check_user_sanctions(user_id)
            
            lifted_count = 0
            
            for sanction in sanctions:
                if sanction_type is None or sanction.sanction_type == sanction_type:
                    # Remove sanction effects
                    self.engine._remove_sanction_effects(sanction)
                    sanction.is_active = False
                    lifted_count += 1
            
            # Update active sanctions
            active_sanctions = [s for s in sanctions if s.is_active]
            self.engine.active_sanctions[user_id] = active_sanctions
            
            # Update cache
            cache_key = f"user_sanctions:{user_id}"
            cache.set(cache_key, active_sanctions, timeout=3600)
            
            logger.info(f"Lifted {lifted_count} sanctions for user {user_id}")
            return lifted_count > 0
            
        except Exception as exc:
            logger.error(f"Lift sanction failed: {exc}")
            return False
    
    def get_sanction_report(self, days: int = 30) -> Dict[str, Any]:
        """
        Get sanction report.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Sanction report
        """
        try:
            stats = self.engine.get_sanction_statistics(days)
            
            # Remove expired sanctions
            expired_count = self.engine.remove_expired_sanctions()
            
            return {
                **stats,
                'expired_sanctions_removed': expired_count,
                'report_generated_at': timezone.now().isoformat()
            }
            
        except Exception as exc:
            logger.error(f"Get sanction report failed: {exc}")
            raise ModerationError(f"Failed to get sanction report: {exc}")


# Global sanction manager instance
sanction_manager = SanctionManager()


# Utility functions
def process_submission_sanctions(submission_id: str) -> Dict[str, Any]:
    """Process sanctions for a submission."""
    try:
        from .models import SuspiciousSubmission
        submission = SuspiciousSubmission.objects.get(id=submission_id)
        return sanction_manager.process_submission_sanctions(submission)
    except Exception as exc:
        logger.error(f"Process submission sanctions failed: {exc}")
        raise ModerationError(f"Failed to process sanctions: {exc}")


def check_user_sanction_status(user_id: Union[str, int]) -> Dict[str, Any]:
    """Check user's sanction status."""
    return sanction_manager.check_user_status(user_id)


def lift_user_sanctions(user_id: Union[str, int], sanction_type: str = None) -> bool:
    """Lift sanctions for a user."""
    return sanction_manager.lift_sanction(user_id, sanction_type)


# Initialize logging
logger.info("Sanctions module initialized with user sanction management")
