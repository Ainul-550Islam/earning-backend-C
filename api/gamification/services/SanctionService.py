"""
Sanction Service - Comprehensive sanction management for gamification system.

Handles applying, managing, and resolving gamification sanctions.
Wraps the sanctions.py module with service layer functionality.
"""

from __future__ import annotations
from django.db.models import Count
from django.db.models import Sum

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from api.gamification.sanctions import (
    ViolationType, Violation, Sanction, ViolationSeverity,
    PointsDeductionEnforcer, BadgeRevocationEnforcer, StreakResetEnforcer,
    TemporarySuspensionEnforcer, SanctionManager
)
from api.gamification.signals import sanction_applied
from api.gamification.models import UserPoints, UserAchievement, Streak
from api.gamification.models import PointsTransaction

logger = logging.getLogger(__name__)
User = get_user_model()


class SanctionService:
    """
    Service for managing gamification sanctions.
    
    Provides methods for applying sanctions, tracking violations,
    and enforcing penalties based on gamification rules.
    """

    def __init__(self):
        self.logger = logger
        self.sanction_manager = SanctionManager()

    def apply_sanction(
        self,
        user,
        violation_type: str,
        severity: str = "medium",
        reason: str = "",
        evidence: Optional[Dict[str, Any]] = None,
        applied_by=None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Sanction:
        """
        Apply a sanction to a user for a gamification violation.
        
        Args:
            user: User instance or ID
            violation_type: Type of violation (points_manipulation, badge_exploitation, etc.)
            severity: Severity level (low, medium, high, critical)
            reason: Human-readable reason for the sanction
            evidence: Evidence supporting the violation
            applied_by: User who applied the sanction
            metadata: Additional metadata
            
        Returns:
            Sanction: Applied sanction record
            
        Raises:
            ValidationError: If violation type or severity is invalid
        """
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                raise ValueError(f"User with ID {user} does not exist")
        
        # Validate violation type
        valid_violation_types = [vt.value for vt in ViolationType]
        if violation_type not in valid_violation_types:
            raise ValidationError(f"Invalid violation type. Must be one of: {', '.join(valid_violation_types)}")
        
        # Validate severity
        valid_severities = [vs.value for vs in ViolationSeverity]
        if severity not in valid_severities:
            raise ValidationError(f"Invalid severity. Must be one of: {', '.join(valid_severities)}")
        
        with transaction.atomic():
            # Create violation record
            violation = Violation.objects.create(
                user=user,
                violation_type=ViolationType(violation_type),
                severity=ViolationSeverity(severity),
                reason=reason,
                evidence=evidence or {},
                detected_by=applied_by
            )
            
            # Apply appropriate sanction based on violation type and severity
            sanction = self.sanction_manager.apply_sanction(
                violation=violation,
                auto_apply=True
            )
            
            # Add metadata if provided
            if metadata:
                sanction.metadata.update(metadata)
                sanction.save(update_fields=['metadata'])
            
            # Send signal
            sanction_applied.send(
                sender=self.__class__,
                user=user,
                violation=violation,
                sanction=sanction,
                applied_by=applied_by
            )
            
            self.logger.info(
                "Applied %s sanction to user %s for %s violation (severity: %s)",
                sanction.sanction_type, user.id, violation_type, severity
            )
            
            return sanction

    def resolve_sanction(self, sanction_id: str, resolved_by=None, resolution_notes: str = "") -> bool:
        """
        Resolve an active sanction.
        
        Args:
            sanction_id: Sanction ID
            resolved_by: User resolving the sanction
            resolution_notes: Notes about the resolution
            
        Returns:
            bool: True if sanction was resolved successfully
        """
        try:
            sanction = Sanction.objects.get(id=sanction_id)
        except Sanction.DoesNotExist:
            raise ValueError(f"Sanction with ID {sanction_id} does not exist")
        
        if sanction.is_resolved:
            self.logger.warning("Sanction %s is already resolved", sanction_id)
            return True
        
        # Use sanction manager to resolve
        success = self.sanction_manager.resolve_sanction(
            sanction=sanction,
            resolved_by=resolved_by,
            resolution_notes=resolution_notes
        )
        
        if success:
            self.logger.info(
                "Resolved sanction %s for user %s",
                sanction_id, sanction.user.id
            )
        
        return success

    def get_active_sanctions(self, user) -> List[Sanction]:
        """
        Get all active sanctions for a user.
        
        Args:
            user: User instance or ID
            
        Returns:
            List of active sanctions
        """
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                return []
        
        return Sanction.objects.filter(
            user=user,
            is_resolved=False,
            expires_at__gt=timezone.now()
        ).order_by('-created_at')

    def check_can_participate(self, user) -> bool:
        """
        Check if a user can participate in gamification activities.
        
        Args:
            user: User instance or ID
            
        Returns:
            bool: True if user can participate
        """
        active_sanctions = self.get_active_sanctions(user)
        
        # Check for suspension sanctions
        for sanction in active_sanctions:
            if sanction.sanction_type == "temporary_suspension":
                return False
        
        # Check for other restrictions
        for sanction in active_sanctions:
            if sanction.sanction_type in ["points_deduction", "streak_reset"]:
                # These don't prevent participation but may affect it
                continue
        
        return True

    def get_sanction_history(self, user, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get sanction history for a user.
        
        Args:
            user: User instance or ID
            limit: Maximum number of sanctions to return
            
        Returns:
            List of sanction records
        """
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                return []
        
        sanctions = Sanction.objects.filter(
            user=user
        ).select_related('violation').order_by('-created_at')[:limit]
        
        history = []
        for sanction in sanctions:
            history.append({
                'sanction_id': str(sanction.id),
                'sanction_type': sanction.sanction_type,
                'violation_type': sanction.violation.violation_type.value if sanction.violation else None,
                'severity': sanction.violation.severity.value if sanction.violation else None,
                'reason': sanction.violation.reason if sanction.violation else "",
                'is_resolved': sanction.is_resolved,
                'created_at': sanction.created_at.isoformat(),
                'expires_at': sanction.expires_at.isoformat() if sanction.expires_at else None,
                'resolved_at': sanction.resolved_at.isoformat() if sanction.resolved_at else None,
                'sanction_data': sanction.sanction_data,
            })
        
        return history

    def apply_points_deduction(
        self,
        user,
        amount: int,
        reason: str = "Gamification violation",
        applied_by=None
    ) -> Dict[str, Any]:
        """
        Apply points deduction as a sanction.
        
        Args:
            user: User instance or ID
            amount: Points to deduct
            reason: Reason for deduction
            applied_by: User applying the deduction
            
        Returns:
            Dict with deduction details
        """
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                raise ValueError(f"User with ID {user} does not exist")
        
        # Use points deduction enforcer
        enforcer = PointsDeductionEnforcer()
        
        # Create violation first
        violation = Violation.objects.create(
            user=user,
            violation_type=ViolationType.POINTS_MANIPULATION,
            severity=ViolationSeverity.MEDIUM,
            reason=reason,
            detected_by=applied_by
        )
        
        # Apply deduction
        result = enforcer.enforce(violation, amount)
        
        self.logger.info(
            "Applied %d point deduction to user %s for: %s",
            amount, user.id, reason
        )
        
        return result

    def revoke_badges(
        self,
        user,
        badge_ids: Optional[List[str]] = None,
        reason: str = "Gamification violation",
        applied_by=None
    ) -> Dict[str, Any]:
        """
        Revoke badges as a sanction.
        
        Args:
            user: User instance or ID
            badge_ids: Specific badge IDs to revoke (None for all recent badges)
            reason: Reason for revocation
            applied_by: User applying the revocation
            
        Returns:
            Dict with revocation details
        """
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                raise ValueError(f"User with ID {user} does not exist")
        
        # Use badge revocation enforcer
        enforcer = BadgeRevocationEnforcer()
        
        # Create violation first
        violation = Violation.objects.create(
            user=user,
            violation_type=ViolationType.BADGE_EXPLOITATION,
            severity=ViolationSeverity.HIGH,
            reason=reason,
            detected_by=applied_by
        )
        
        # Apply revocation
        result = enforcer.enforce(violation, badge_ids)
        
        self.logger.info(
            "Revoked %d badges from user %s for: %s",
            result.get('revoked_count', 0), user.id, reason
        )
        
        return result

    def reset_streak(
        self,
        user,
        reason: str = "Gamification violation",
        applied_by=None
    ) -> Dict[str, Any]:
        """
        Reset user's streak as a sanction.
        
        Args:
            user: User instance or ID
            reason: Reason for streak reset
            applied_by: User applying the reset
            
        Returns:
            Dict with reset details
        """
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                raise ValueError(f"User with ID {user} does not exist")
        
        # Use streak reset enforcer
        enforcer = StreakResetEnforcer()
        
        # Create violation first
        violation = Violation.objects.create(
            user=user,
            violation_type=ViolationType.CHALLENGE_CHEATING,
            severity=ViolationSeverity.HIGH,
            reason=reason,
            detected_by=applied_by
        )
        
        # Apply reset
        result = enforcer.enforce(violation)
        
        self.logger.info(
            "Reset streak for user %s for: %s",
            user.id, reason
        )
        
        return result

    def apply_temporary_suspension(
        self,
        user,
        duration_hours: int,
        reason: str = "Gamification violation",
        applied_by=None
    ) -> Dict[str, Any]:
        """
        Apply temporary suspension as a sanction.
        
        Args:
            user: User instance or ID
            duration_hours: Duration of suspension in hours
            reason: Reason for suspension
            applied_by: User applying the suspension
            
        Returns:
            Dict with suspension details
        """
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                raise ValueError(f"User with ID {user} does not exist")
        
        # Use temporary suspension enforcer
        enforcer = TemporarySuspensionEnforcer()
        
        # Create violation first
        violation = Violation.objects.create(
            user=user,
            violation_type=ViolationType.CHALLENGE_CHEATING,
            severity=ViolationSeverity.CRITICAL,
            reason=reason,
            detected_by=applied_by
        )
        
        # Apply suspension
        result = enforcer.enforce(violation, duration_hours)
        
        self.logger.info(
            "Applied %d hour suspension to user %s for: %s",
            duration_hours, user.id, reason
        )
        
        return result

    def get_sanction_statistics(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get sanction statistics for a date range.
        
        Args:
            start_date: Start date for statistics
            end_date: End date for statistics
            
        Returns:
            Dict with sanction statistics
        """
        queryset = Sanction.objects.all()
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Basic stats
        total_sanctions = queryset.count()
        active_sanctions = queryset.filter(is_resolved=False, expires_at__gt=timezone.now()).count()
        resolved_sanctions = queryset.filter(is_resolved=True).count()
        
        # By type
        sanctions_by_type = queryset.values('sanction_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # By severity
        sanctions_by_severity = queryset.values('violation__severity').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # By violation type
        sanctions_by_violation = queryset.values('violation__violation_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return {
            'total_sanctions': total_sanctions,
            'active_sanctions': active_sanctions,
            'resolved_sanctions': resolved_sanctions,
            'sanctions_by_type': list(sanctions_by_type),
            'sanctions_by_severity': list(sanctions_by_severity),
            'sanctions_by_violation': list(sanctions_by_violation),
            'period': {
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None,
            }
        }

    def cleanup_expired_sanctions(self) -> int:
        """
        Clean up expired sanctions by marking them as resolved.
        
        Returns:
            Number of sanctions cleaned up
        """
        expired_sanctions = Sanction.objects.filter(
            is_resolved=False,
            expires_at__lt=timezone.now()
        )
        
        cleanup_count = 0
        for sanction in expired_sanctions:
            sanction.is_resolved = True
            sanction.resolved_at = timezone.now()
            sanction.resolution_notes = "Automatically resolved due to expiration"
            sanction.save(update_fields=['is_resolved', 'resolved_at', 'resolution_notes'])
            cleanup_count += 1
        
        if cleanup_count > 0:
            self.logger.info("Cleaned up %d expired sanctions", cleanup_count)
        
        return cleanup_count

    def detect_violations(self, user) -> List[Dict[str, Any]]:
        """
        Detect potential violations for a user based on their activity patterns.
        
        Args:
            user: User instance or ID
            
        Returns:
            List of detected violations
        """
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                return []
        
        detected_violations = []
        
        # Check for unusual point accumulation patterns
        try:
            recent_transactions = PointsTransaction.objects.filter(
                user=user,
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).order_by('-created_at')
            
            # Detect rapid point accumulation
            if recent_transactions.count() > 100:  # More than 100 transactions in 24 hours
                detected_violations.append({
                    'type': 'points_manipulation',
                    'severity': 'high',
                    'reason': 'Unusual point accumulation pattern detected',
                    'evidence': {
                        'transaction_count_24h': recent_transactions.count(),
                        'total_points_24h': recent_transactions.aggregate(Sum('amount'))['amount__sum'] or 0
                    }
                })
        except:
            pass
        
        # Check for badge exploitation patterns
        try:
            recent_badges = UserAchievement.objects.filter(
                user=user,
                created_at__gte=timezone.now() - timedelta(hours=1)
            )
            
            if recent_badges.count() > 5:  # More than 5 badges in 1 hour
                detected_violations.append({
                    'type': 'badge_exploitation',
                    'severity': 'medium',
                    'reason': 'Unusual badge earning pattern detected',
                    'evidence': {
                        'badges_earned_1h': recent_badges.count()
                    }
                })
        except:
            pass
        
        # Check for challenge cheating patterns
        try:
            from api.gamification.models import UserDailyChallenge
            recent_challenges = UserDailyChallenge.objects.filter(
                user=user,
                completed_at__gte=timezone.now() - timedelta(minutes=30)
            )
            
            if recent_challenges.count() > 10:  # More than 10 challenges in 30 minutes
                detected_violations.append({
                    'type': 'challenge_cheating',
                    'severity': 'medium',
                    'reason': 'Unusually fast challenge completion pattern',
                    'evidence': {
                        'challenges_completed_30m': recent_challenges.count()
                    }
                })
        except:
            pass
        
        return detected_violations

    def bulk_apply_sanctions(
        self,
        violations: List[Dict[str, Any]],
        applied_by=None
    ) -> List[Sanction]:
        """
        Apply multiple sanctions in bulk.
        
        Args:
            violations: List of violation dictionaries
            applied_by: User applying the sanctions
            
        Returns:
            List of applied sanctions
        """
        applied_sanctions = []
        
        with transaction.atomic():
            for violation_data in violations:
                try:
                    sanction = self.apply_sanction(
                        user=violation_data['user'],
                        violation_type=violation_data['violation_type'],
                        severity=violation_data.get('severity', 'medium'),
                        reason=violation_data.get('reason', ''),
                        evidence=violation_data.get('evidence', {}),
                        applied_by=applied_by,
                        metadata=violation_data.get('metadata', {})
                    )
                    applied_sanctions.append(sanction)
                except Exception as e:
                    self.logger.error(
                        "Failed to apply sanction for user %s: %s",
                        violation_data.get('user', 'unknown'), str(e)
                    )
        
        self.logger.info(
            "Bulk applied %d sanctions, %d successful",
            len(violations), len(applied_sanctions)
        )
        
        return applied_sanctions
