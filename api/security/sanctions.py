"""
Security Sanctions Module
Sanctions management and enforcement system
"""

import logging
from typing import Dict, List, Any, Optional, Type, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.core.cache import cache
from django.conf import settings

from .models import SecurityLog, UserBan, SecurityIncident
from .repositories import UserBanRepository, SecurityLogRepository
from .utils import SecurityUtils
from .helpers import TimeHelper

User = get_user_model()
logger = logging.getLogger('security.sanctions')


class SanctionType:
    """Types of security sanctions"""
    WARNING = 'warning'
    TEMPORARY_BAN = 'temporary_ban'
    PERMANENT_BAN = 'permanent_ban'
    ACCOUNT_RESTRICTION = 'account_restriction'
    FEATURE_RESTRICTION = 'feature_restriction'
    IP_BLOCK = 'ip_block'
    DEVICE_BLOCK = 'device_block'
    RATE_LIMIT = 'rate_limit'
    MONITORING = 'monitoring'
    VERIFICATION_REQUIRED = 'verification_required'


class SanctionSeverity:
    """Sanction severity levels"""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


class SanctionStatus:
    """Sanction status"""
    ACTIVE = 'active'
    EXPIRED = 'expired'
    LIFTED = 'lifted'
    SUSPENDED = 'suspended'
    APPEALED = 'appealed'


class Sanction(models.Model):
    """Sanction model for tracking security sanctions"""
    
    id = models.UUIDField(primary_key=True, default=SecurityUtils.generate_uuid)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sanctions')
    sanction_type = models.CharField(max_length=50, choices=[
        (SanctionType.WARNING, 'Warning'),
        (SanctionType.TEMPORARY_BAN, 'Temporary Ban'),
        (SanctionType.PERMANENT_BAN, 'Permanent Ban'),
        (SanctionType.ACCOUNT_RESTRICTION, 'Account Restriction'),
        (SanctionType.FEATURE_RESTRICTION, 'Feature Restriction'),
        (SanctionType.IP_BLOCK, 'IP Block'),
        (SanctionType.DEVICE_BLOCK, 'Device Block'),
        (SanctionType.RATE_LIMIT, 'Rate Limit'),
        (SanctionType.MONITORING, 'Enhanced Monitoring'),
        (SanctionType.VERIFICATION_REQUIRED, 'Verification Required'),
    ])
    severity = models.CharField(max_length=20, choices=[
        (SanctionSeverity.LOW, 'Low'),
        (SanctionSeverity.MEDIUM, 'Medium'),
        (SanctionSeverity.HIGH, 'High'),
        (SanctionSeverity.CRITICAL, 'Critical'),
    ])
    status = models.CharField(max_length=20, choices=[
        (SanctionStatus.ACTIVE, 'Active'),
        (SanctionStatus.EXPIRED, 'Expired'),
        (SanctionStatus.LIFTED, 'Lifted'),
        (SanctionStatus.SUSPENDED, 'Suspended'),
        (SanctionStatus.APPEALED, 'Appealed'),
    ], default=SanctionStatus.ACTIVE)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    starts_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    lifted_at = models.DateTimeField(null=True, blank=True)
    
    # Details
    reason = models.TextField()
    violation_type = models.CharField(max_length=100)
    violation_severity = models.CharField(max_length=20, choices=[
        (SanctionSeverity.LOW, 'Low'),
        (SanctionSeverity.MEDIUM, 'Medium'),
        (SanctionSeverity.HIGH, 'High'),
        (SanctionSeverity.CRITICAL, 'Critical'),
    ])
    
    # Enforcement
    enforced_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                   related_name='enforced_sanctions')
    auto_enforced = models.BooleanField(default=False)
    enforcement_data = models.JSONField(default=dict, blank=True)
    
    # Appeal process
    can_appeal = models.BooleanField(default=True)
    appeal_deadline = models.DateTimeField(null=True, blank=True)
    appeal_notes = models.TextField(blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'security_sanctions'
        verbose_name = "Sanction"
        verbose_name_plural = "Sanctions"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['sanction_type', 'status']),
            models.Index(fields=['severity', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.get_sanction_type_display()} - {self.user.username}"
    
    def is_active(self):
        """Check if sanction is currently active"""
        if self.status != SanctionStatus.ACTIVE:
            return False
        
        now = timezone.now()
        
        # Check if sanction has started
        if self.starts_at > now:
            return False
        
        # Check if sanction has expired
        if self.expires_at and self.expires_at <= now:
            return False
        
        return True
    
    def is_expired(self):
        """Check if sanction has expired"""
        if self.expires_at and self.expires_at <= timezone.now():
            return True
        return False
    
    def days_until_expiry(self):
        """Get days until sanction expires"""
        if not self.expires_at:
            return None
        
        delta = self.expires_at - timezone.now()
        return max(0, delta.days)
    
    def can_be_appealed(self):
        """Check if sanction can be appealed"""
        if not self.can_appeal:
            return False
        
        if self.status not in [SanctionStatus.ACTIVE, SanctionStatus.SUSPENDED]:
            return False
        
        if self.appeal_deadline and self.appeal_deadline <= timezone.now():
            return False
        
        return True
    
    def lift(self, lifted_by: User, reason: str = ''):
        """Lift the sanction"""
        self.status = SanctionStatus.LIFTED
        self.lifted_at = timezone.now()
        self.appeal_notes = f"Lifted by {lifted_by.username}: {reason}"
        self.save()
        
        # Log the lift
        self._log_action('lifted', lifted_by, reason)
    
    def extend(self, days: int, extended_by: User, reason: str = ''):
        """Extend sanction duration"""
        if self.expires_at:
            self.expires_at += timedelta(days=days)
        else:
            self.expires_at = timezone.now() + timedelta(days=days)
        
        self.appeal_notes = f"Extended by {extended_by.username} for {days} days: {reason}"
        self.save()
        
        # Log the extension
        self._log_action('extended', extended_by, f"Extended by {days} days: {reason}")
    
    def _log_action(self, action: str, performed_by: User, details: str = ''):
        """Log sanction action"""
        try:
            SecurityLog.objects.create(
                user=performed_by,
                security_type='sanction_action',
                severity='medium',
                description=f'Sanction {action}: {self.get_sanction_type_display()} for {self.user.username}',
                metadata={
                    'sanction_id': str(self.id),
                    'action': action,
                    'sanction_type': self.sanction_type,
                    'user_id': self.user.id,
                    'details': details
                }
            )
        except Exception as e:
            logger.error(f"Failed to log sanction action: {e}")


class SanctionPolicy(models.Model):
    """Sanction policy for automated enforcement"""
    
    id = models.UUIDField(primary_key=True, default=SecurityUtils.generate_uuid)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    
    # Policy conditions
    violation_types = models.JSONField(default=list)  # List of violation types
    severity_threshold = models.CharField(max_length=20, choices=[
        (SanctionSeverity.LOW, 'Low'),
        (SanctionSeverity.MEDIUM, 'Medium'),
        (SanctionSeverity.HIGH, 'High'),
        (SanctionSeverity.CRITICAL, 'Critical'),
    ])
    
    # Time-based conditions
    time_window_hours = models.IntegerField(default=24)
    max_violations = models.IntegerField(default=3)
    
    # Sanction to apply
    sanction_type = models.CharField(max_length=50, choices=[
        (SanctionType.WARNING, 'Warning'),
        (SanctionType.TEMPORARY_BAN, 'Temporary Ban'),
        (SanctionType.PERMANENT_BAN, 'Permanent Ban'),
        (SanctionType.ACCOUNT_RESTRICTION, 'Account Restriction'),
        (SanctionType.FEATURE_RESTRICTION, 'Feature Restriction'),
        (SanctionType.IP_BLOCK, 'IP Block'),
        (SanctionType.DEVICE_BLOCK, 'Device Block'),
        (SanctionType.RATE_LIMIT, 'Rate Limit'),
        (SanctionType.MONITORING, 'Enhanced Monitoring'),
        (SanctionType.VERIFICATION_REQUIRED, 'Verification Required'),
    ])
    
    sanction_duration_days = models.IntegerField(null=True, blank=True)  # Null for permanent
    
    # Policy settings
    is_active = models.BooleanField(default=True)
    auto_enforce = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'security_sanction_policies'
        verbose_name = "Sanction Policy"
        verbose_name_plural = "Sanction Policies"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def evaluate_user(self, user: User) -> bool:
        """Evaluate if user meets policy conditions"""
        if not self.is_active:
            return False
        
        # Check recent violations
        time_window = timezone.now() - timedelta(hours=self.time_window_hours)
        
        recent_violations = SecurityLog.objects.filter(
            user=user,
            created_at__gte=time_window,
            security_type__in=self.violation_types
        ).count()
        
        return recent_violations >= self.max_violations
    
    def apply_sanction(self, user: User, enforced_by: User = None) -> Optional[Sanction]:
        """Apply sanction to user"""
        if not self.evaluate_user(user):
            return None
        
        # Check if similar sanction already exists
        existing_sanction = Sanction.objects.filter(
            user=user,
            sanction_type=self.sanction_type,
            status=SanctionStatus.ACTIVE
        ).first()
        
        if existing_sanction:
            return existing_sanction
        
        # Create new sanction
        expires_at = None
        if self.sanction_duration_days:
            expires_at = timezone.now() + timedelta(days=self.sanction_duration_days)
        
        sanction = Sanction.objects.create(
            user=user,
            sanction_type=self.sanction_type,
            severity=self.severity_threshold,
            reason=f"Automated sanction based on policy: {self.name}",
            violation_type=self.violation_types[0] if self.violation_types else 'unknown',
            violation_severity=self.severity_threshold,
            enforced_by=enforced_by,
            auto_enforced=True,
            expires_at=expires_at,
            can_appeal=True,
            appeal_deadline=timezone.now() + timedelta(days=7),
            metadata={
                'policy_id': str(self.id),
                'policy_name': self.name,
                'violation_count': self.max_violations
            }
        )
        
        return sanction


class SanctionManager:
    """Manager for sanctions and policies"""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
    
    def create_sanction(self, user: User, sanction_type: str, severity: str,
                       reason: str, violation_type: str, enforced_by: User = None,
                       duration_days: int = None, **kwargs) -> Sanction:
        """Create a new sanction"""
        with transaction.atomic():
            expires_at = None
            if duration_days:
                expires_at = timezone.now() + timedelta(days=duration_days)
            
            sanction = Sanction.objects.create(
                user=user,
                sanction_type=sanction_type,
                severity=severity,
                reason=reason,
                violation_type=violation_type,
                violation_severity=severity,
                enforced_by=enforced_by,
                expires_at=expires_at,
                **kwargs
            )
            
            # Apply sanction effects
            self._apply_sanction_effects(sanction)
            
            logger.info(f"Created sanction {sanction.id} for user {user.username}")
            return sanction
    
    def lift_sanction(self, sanction_id: str, lifted_by: User, reason: str = '') -> bool:
        """Lift a sanction"""
        try:
            sanction = Sanction.objects.get(id=sanction_id)
            sanction.lift(lifted_by, reason)
            
            # Remove sanction effects
            self._remove_sanction_effects(sanction)
            
            logger.info(f"Lifted sanction {sanction_id}")
            return True
        except Sanction.DoesNotExist:
            logger.error(f"Sanction {sanction_id} not found")
            return False
    
    def extend_sanction(self, sanction_id: str, days: int, extended_by: User, reason: str = '') -> bool:
        """Extend a sanction"""
        try:
            sanction = Sanction.objects.get(id=sanction_id)
            sanction.extend(days, extended_by, reason)
            
            logger.info(f"Extended sanction {sanction_id} by {days} days")
            return True
        except Sanction.DoesNotExist:
            logger.error(f"Sanction {sanction_id} not found")
            return False
    
    def get_user_sanctions(self, user: User, active_only: bool = True) -> List[Sanction]:
        """Get sanctions for user"""
        sanctions = Sanction.objects.filter(user=user)
        
        if active_only:
            sanctions = sanctions.filter(status=SanctionStatus.ACTIVE)
        
        return list(sanctions)
    
    def get_active_sanctions(self) -> List[Sanction]:
        """Get all active sanctions"""
        return list(Sanction.objects.filter(status=SanctionStatus.ACTIVE))
    
    def get_expired_sanctions(self) -> List[Sanction]:
        """Get expired sanctions"""
        return list(Sanction.objects.filter(
            status=SanctionStatus.ACTIVE,
            expires_at__lte=timezone.now()
        ))
    
    def process_expired_sanctions(self) -> int:
        """Process expired sanctions"""
        expired_count = 0
        
        for sanction in self.get_expired_sanctions():
            sanction.status = SanctionStatus.EXPIRED
            sanction.save()
            
            # Remove sanction effects
            self._remove_sanction_effects(sanction)
            
            expired_count += 1
        
        logger.info(f"Processed {expired_count} expired sanctions")
        return expired_count
    
    def evaluate_policies(self, user: User) -> List[Sanction]:
        """Evaluate all policies for user"""
        applied_sanctions = []
        
        for policy in SanctionPolicy.objects.filter(is_active=True, auto_enforce=True):
            if policy.evaluate_user(user):
                sanction = policy.apply_sanction(user)
                if sanction:
                    applied_sanctions.append(sanction)
                    self._apply_sanction_effects(sanction)
        
        return applied_sanctions
    
    def _apply_sanction_effects(self, sanction: Sanction):
        """Apply sanction effects to user"""
        try:
            if sanction.sanction_type == SanctionType.TEMPORARY_BAN:
                # Create user ban
                UserBan.objects.create(
                    user=sanction.user,
                    reason=sanction.reason,
                    expires_at=sanction.expires_at,
                    banned_by=sanction.enforced_by,
                    metadata={'sanction_id': str(sanction.id)}
                )
            
            elif sanction.sanction_type == SanctionType.PERMANENT_BAN:
                # Create permanent user ban
                UserBan.objects.create(
                    user=sanction.user,
                    reason=sanction.reason,
                    banned_by=sanction.enforced_by,
                    metadata={'sanction_id': str(sanction.id)}
                )
            
            elif sanction.sanction_type == SanctionType.RATE_LIMIT:
                # Apply rate limiting (simplified - would integrate with rate limiting system)
                cache.set(f"rate_limit_{sanction.user.id}", True, timeout=3600)
            
            elif sanction.sanction_type == SanctionType.FEATURE_RESTRICTION:
                # Apply feature restrictions (simplified)
                cache.set(f"restricted_features_{sanction.user.id}", True, timeout=3600)
            
            # Log sanction application
            SecurityLog.objects.create(
                user=sanction.user,
                security_type='sanction_applied',
                severity='medium',
                description=f'Sanction applied: {sanction.get_sanction_type_display()}',
                metadata={
                    'sanction_id': str(sanction.id),
                    'sanction_type': sanction.sanction_type,
                    'severity': sanction.severity
                }
            )
            
        except Exception as e:
            logger.error(f"Error applying sanction effects: {e}")
    
    def _remove_sanction_effects(self, sanction: Sanction):
        """Remove sanction effects from user"""
        try:
            if sanction.sanction_type in [SanctionType.TEMPORARY_BAN, SanctionType.PERMANENT_BAN]:
                # Remove user ban
                UserBan.objects.filter(
                    user=sanction.user,
                    metadata__sanction_id=str(sanction.id)
                ).update(is_active=False)
            
            elif sanction.sanction_type == SanctionType.RATE_LIMIT:
                # Remove rate limiting
                cache.delete(f"rate_limit_{sanction.user.id}")
            
            elif sanction.sanction_type == SanctionType.FEATURE_RESTRICTION:
                # Remove feature restrictions
                cache.delete(f"restricted_features_{sanction.user.id}")
            
            # Log sanction removal
            SecurityLog.objects.create(
                user=sanction.user,
                security_type='sanction_removed',
                severity='info',
                description=f'Sanction removed: {sanction.get_sanction_type_display()}',
                metadata={
                    'sanction_id': str(sanction.id),
                    'sanction_type': sanction.sanction_type,
                    'status': sanction.status
                }
            )
            
        except Exception as e:
            logger.error(f"Error removing sanction effects: {e}")
    
    def get_sanction_statistics(self) -> Dict[str, Any]:
        """Get sanction statistics"""
        total_sanctions = Sanction.objects.count()
        active_sanctions = Sanction.objects.filter(status=SanctionStatus.ACTIVE).count()
        
        # By type
        by_type = {}
        for choice in Sanction._meta.get_field('sanction_type').choices:
            type_name = choice[0]
            count = Sanction.objects.filter(sanction_type=type_name).count()
            by_type[type_name] = count
        
        # By severity
        by_severity = {}
        for choice in Sanction._meta.get_field('severity').choices:
            severity_name = choice[0]
            count = Sanction.objects.filter(severity=severity_name).count()
            by_severity[severity_name] = count
        
        # By status
        by_status = {}
        for choice in Sanction._meta.get_field('status').choices:
            status_name = choice[0]
            count = Sanction.objects.filter(status=status_name).count()
            by_status[status_name] = count
        
        return {
            'total_sanctions': total_sanctions,
            'active_sanctions': active_sanctions,
            'by_type': by_type,
            'by_severity': by_severity,
            'by_status': by_status,
            'expired_count': len(self.get_expired_sanctions())
        }
    
    def create_policy(self, name: str, description: str, violation_types: List[str],
                     severity_threshold: str, sanction_type: str, **kwargs) -> SanctionPolicy:
        """Create a new sanction policy"""
        policy = SanctionPolicy.objects.create(
            name=name,
            description=description,
            violation_types=violation_types,
            severity_threshold=severity_threshold,
            sanction_type=sanction_type,
            **kwargs
        )
        
        logger.info(f"Created sanction policy: {name}")
        return policy
    
    def get_user_violation_history(self, user: User, days: int = 30) -> List[Dict[str, Any]]:
        """Get user violation history"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        violations = SecurityLog.objects.filter(
            user=user,
            created_at__gte=cutoff_date,
            security_type__in=[
                'login_failed', 'access_denied', 'permission_denied',
                'malicious_activity', 'policy_violation', 'suspicious_activity'
            ]
        ).order_by('-created_at')
        
        history = []
        for violation in violations:
            history.append({
                'timestamp': violation.created_at.isoformat(),
                'type': violation.security_type,
                'severity': violation.severity,
                'description': violation.description,
                'ip_address': violation.ip_address,
                'metadata': violation.metadata
            })
        
        return history
    
    def recommend_sanction(self, user: User, violation_type: str, 
                          violation_severity: str) -> Optional[Dict[str, Any]]:
        """Recommend sanction based on violation and user history"""
        # Get user's violation history
        history = self.get_user_violation_history(user, days=30)
        
        # Get existing sanctions
        existing_sanctions = self.get_user_sanctions(user, active_only=True)
        
        # Calculate recommendation
        recommendation = self._calculate_recommendation(
            user, violation_type, violation_severity, history, existing_sanctions
        )
        
        return recommendation
    
    def _calculate_recommendation(self, user: User, violation_type: str,
                                violation_severity: str, history: List[Dict[str, Any]],
                                existing_sanctions: List[Sanction]) -> Dict[str, Any]:
        """Calculate sanction recommendation"""
        # Count recent violations
        recent_violations = len([h for h in history if 
                               h['type'] == violation_type or 
                               h['severity'] == violation_severity])
        
        # Check for existing similar sanctions
        existing_similar = [s for s in existing_sanctions if s.violation_type == violation_type]
        
        recommendation = {
            'recommended_sanction': None,
            'severity': violation_severity,
            'duration_days': None,
            'reasoning': [],
            'confidence': 0.5
        }
        
        # Base recommendation on violation severity
        if violation_severity == SanctionSeverity.CRITICAL:
            if existing_similar:
                recommendation['recommended_sanction'] = SanctionType.PERMANENT_BAN
                recommendation['reasoning'].append('Critical violation with existing sanctions')
                recommendation['confidence'] = 0.9
            else:
                recommendation['recommended_sanction'] = SanctionType.TEMPORARY_BAN
                recommendation['duration_days'] = 30
                recommendation['reasoning'].append('Critical violation')
                recommendation['confidence'] = 0.8
        
        elif violation_severity == SanctionSeverity.HIGH:
            if recent_violations >= 3:
                recommendation['recommended_sanction'] = SanctionType.TEMPORARY_BAN
                recommendation['duration_days'] = 14
                recommendation['reasoning'].append(f'High violation with {recent_violations} recent offenses')
                recommendation['confidence'] = 0.8
            else:
                recommendation['recommended_sanction'] = SanctionType.FEATURE_RESTRICTION
                recommendation['duration_days'] = 7
                recommendation['reasoning'].append('High violation')
                recommendation['confidence'] = 0.7
        
        elif violation_severity == SanctionSeverity.MEDIUM:
            if recent_violations >= 5:
                recommendation['recommended_sanction'] = SanctionType.TEMPORARY_BAN
                recommendation['duration_days'] = 7
                recommendation['reasoning'].append(f'Medium violation with {recent_violations} recent offenses')
                recommendation['confidence'] = 0.7
            else:
                recommendation['recommended_sanction'] = SanctionType.WARNING
                recommendation['reasoning'].append('Medium violation')
                recommendation['confidence'] = 0.6
        
        else:  # Low severity
            if recent_violations >= 10:
                recommendation['recommended_sanction'] = SanctionType.MONITORING
                recommendation['duration_days'] = 30
                recommendation['reasoning'].append(f'Low violation with {recent_violations} recent offenses')
                recommendation['confidence'] = 0.6
            else:
                recommendation['recommended_sanction'] = SanctionType.WARNING
                recommendation['reasoning'].append('Low violation')
                recommendation['confidence'] = 0.5
        
        return recommendation


# Global sanction manager
sanction_manager = SanctionManager()


# Automated sanction processor
class SanctionProcessor:
    """Automated sanction processing"""
    
    def __init__(self):
        self.manager = sanction_manager
        self.processing_interval = 3600  # 1 hour
    
    def process_violations(self):
        """Process violations and apply sanctions"""
        # Process expired sanctions
        self.manager.process_expired_sanctions()
        
        # Evaluate policies for active users
        recent_users = User.objects.filter(
            last_login__gte=timezone.now() - timedelta(days=1)
        )
        
        for user in recent_users:
            self.manager.evaluate_policies(user)
    
    def process_user_violations(self, user: User):
        """Process violations for specific user"""
        # Evaluate policies
        sanctions = self.manager.evaluate_policies(user)
        
        # Log processing
        if sanctions:
            logger.info(f"Applied {len(sanctions)} sanctions to user {user.username}")
    
    def get_processing_status(self) -> Dict[str, Any]:
        """Get processing status"""
        return {
            'last_processed': cache.get('sanction_processor_last_run'),
            'active_sanctions': len(self.manager.get_active_sanctions()),
            'expired_sanctions': len(self.manager.get_expired_sanctions()),
            'next_run': cache.get('sanction_processor_next_run')
        }


# Global sanction processor
sanction_processor = SanctionProcessor()


# Export classes and utilities
__all__ = [
    'SanctionType',
    'SanctionSeverity',
    'SanctionStatus',
    'Sanction',
    'SanctionPolicy',
    'SanctionManager',
    'sanction_manager',
    'SanctionProcessor',
    'sanction_processor'
]