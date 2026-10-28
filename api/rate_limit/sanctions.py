# api/rate_limit/sanctions.py
"""
Sanctions system for rate limit module.

Provides automated sanctioning based on rule violations and abuse patterns.
"""
from django.db.models import Max

import logging
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction

from api.rate_limit.models import (
    RateLimitLog, UserRateLimitProfile, AbuseReport, 
    IPBlockList, RateLimitException
)
from api.rate_limit.repositories import RepositoryFactory
from api.rate_limit.helpers import RateLimitHelper
from api.rate_limit.constants import SANCTION_WARNING_TIMEOUT
from api.rate_limit.constants import SANCTION_TEMPORARY_BLOCK_HOURS
from api.rate_limit.constants import SANCTION_RATE_LIMIT_REDUCTION_FACTOR
from api.rate_limit.constants import SANCTION_DEFAULT_DAILY_LIMIT, SANCTION_DEFAULT_HOURLY_LIMIT
from api.rate_limit.constants import SANCTION_PREMIUM_REVOCATION_DAYS, SANCTION_PREMIUM_DAILY_LIMIT, SANCTION_PREMIUM_HOURLY_LIMIT
from api.rate_limit.constants import SUSPICION_SCORE_HIGH_THRESHOLD
from api.rate_limit.constants import ABUSE_REPORT_COUNT_THRESHOLD, SANCTION_RATE_LIMIT_REDUCTION_FACTOR
from api.rate_limit.constants import ABUSE_SEVERITY_CRITICAL_THRESHOLD, SANCTION_TEMPORARY_BLOCK_HOURS
from api.rate_limit.constants import ABUSE_SEVERITY_SEVERE_THRESHOLD
from api.rate_limit.constants import BLOCK_RATE_THRESHOLD
from api.rate_limit.constants import SANCTION_EVALUATION_HOURS

logger = logging.getLogger(__name__)
User = get_user_model()


class SanctionType:
    """Enumeration of sanction types."""
    
    WARNING = 'warning'
    TEMPORARY_BLOCK = 'temporary_block'
    PERMANENT_BLOCK = 'permanent_block'
    RATE_LIMIT_REDUCTION = 'rate_limit_reduction'
    PREMIUM_REVOCATION = 'premium_revocation'
    ACCOUNT_SUSPENSION = 'account_suspension'
    MANUAL_REVIEW = 'manual_review'
    
    CHOICES = [
        (WARNING, 'Warning'),
        (TEMPORARY_BLOCK, 'Temporary Block'),
        (PERMANENT_BLOCK, 'Permanent Block'),
        (RATE_LIMIT_REDUCTION, 'Rate Limit Reduction'),
        (PREMIUM_REVOCATION, 'Premium Revocation'),
        (ACCOUNT_SUSPENSION, 'Account Suspension'),
        (MANUAL_REVIEW, 'Manual Review'),
    ]


class SanctionSeverity:
    """Enumeration of sanction severities."""
    
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'
    
    CHOICES = [
        (LOW, 'Low'),
        (MEDIUM, 'Medium'),
        (HIGH, 'High'),
        (CRITICAL, 'Critical'),
    ]


class SanctionRule:
    """Represents a sanction rule."""
    
    def __init__(self, name: str, condition: Callable, sanction_type: str, 
                 severity: str, parameters: Dict[str, Any] = None):
        self.name = name
        self.condition = condition
        self.sanction_type = sanction_type
        self.severity = severity
        self.parameters = parameters or {}
        self.is_active = True


class BaseSanction:
    """Base class for sanctions."""
    
    def __init__(self, sanction_type: str, target: Any, reason: str, 
                 severity: str, parameters: Dict[str, Any] = None):
        self.sanction_type = sanction_type
        self.target = target
        self.reason = reason
        self.severity = severity
        self.parameters = parameters or {}
        self.created_at = timezone.now()
        self.expires_at = None
        self.is_active = True
    
    def apply(self) -> Dict[str, Any]:
        """Apply the sanction."""
        raise NotImplementedError("Subclasses must implement apply()")
    
    def revoke(self) -> Dict[str, Any]:
        """Revoke the sanction."""
        raise NotImplementedError("Subclasses must implement revoke()")
    
    def is_expired(self) -> bool:
        """Check if sanction is expired."""
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at


class WarningSanction(BaseSanction):
    """Warning sanction - logs warning but no action."""
    
    def apply(self) -> Dict[str, Any]:
        """Apply warning sanction."""
        logger.warning(f"Warning sanction applied to {self.target}: {self.reason}")
        
        # Store warning in cache
        cache_key = f"sanction:warning:{self.target}"
        cache.set(cache_key, {
            'reason': self.reason,
            'created_at': self.created_at.isoformat(),
            'severity': self.severity
        }, timeout=SANCTION_WARNING_TIMEOUT)
        
        return {
            'success': True,
            'sanction_type': self.sanction_type,
            'target': str(self.target),
            'message': 'Warning issued'
        }
    
    def revoke(self) -> Dict[str, Any]:
        """Revoke warning sanction."""
        cache_key = f"sanction:warning:{self.target}"
        cache.delete(cache_key)
        
        return {
            'success': True,
            'sanction_type': self.sanction_type,
            'target': str(self.target),
            'message': 'Warning revoked'
        }


class TemporaryBlockSanction(BaseSanction):
    """Temporary block sanction."""
    

    def __init__(self, target: Any, reason: str, severity: str, 
                 hours: int = SANCTION_TEMPORARY_BLOCK_HOURS, **kwargs):
        super().__init__(SanctionType.TEMPORARY_BLOCK, target, reason, severity, kwargs)
        self.hours = hours
        self.expires_at = timezone.now() + timedelta(hours=hours)
    
    def apply(self) -> Dict[str, Any]:
        """Apply temporary block."""
        block_repo = RepositoryFactory.get_repository('ip_block_list')
        
        if isinstance(self.target, str):  # IP address
            block = block_repo.block_ip(
                ip_address=self.target,
                block_reason=self.reason,
                hours=self.hours
            )
            
            return {
                'success': True,
                'sanction_type': self.sanction_type,
                'target': self.target,
                'block_id': block.id,
                'expires_at': self.expires_at.isoformat(),
                'message': f'IP {self.target} temporarily blocked for {self.hours} hours'
            }
        else:
            return {
                'success': False,
                'error': 'Temporary block only supports IP addresses'
            }
    
    def revoke(self) -> Dict[str, Any]:
        """Revoke temporary block."""
        block_repo = RepositoryFactory.get_repository('ip_block_list')
        updated_count = block_repo.unblock_ip(self.target)
        
        return {
            'success': updated_count > 0,
            'sanction_type': self.sanction_type,
            'target': self.target,
            'message': 'Temporary block revoked' if updated_count > 0 else 'No active block found'
        }


class PermanentBlockSanction(BaseSanction):
    """Permanent block sanction."""
    
    def apply(self) -> Dict[str, Any]:
        """Apply permanent block."""
        block_repo = RepositoryFactory.get_repository('ip_block_list')
        
        if isinstance(self.target, str):  # IP address
            block = block_repo.block_ip(
                ip_address=self.target,
                block_reason=self.reason,
                hours=None  # Permanent
            )
            
            return {
                'success': True,
                'sanction_type': self.sanction_type,
                'target': self.target,
                'block_id': block.id,
                'message': f'IP {self.target} permanently blocked'
            }
        else:
            return {
                'success': False,
                'error': 'Permanent block only supports IP addresses'
            }
    
    def revoke(self) -> Dict[str, Any]:
        """Revoke permanent block."""
        block_repo = RepositoryFactory.get_repository('ip_block_list')
        updated_count = block_repo.unblock_ip(self.target)
        
        return {
            'success': updated_count > 0,
            'sanction_type': self.sanction_type,
            'target': self.target,
            'message': 'Permanent block revoked' if updated_count > 0 else 'No active block found'
        }


class RateLimitReductionSanction(BaseSanction):
    """Rate limit reduction sanction."""
    

    def __init__(self, target: Any, reason: str, severity: str, 
                 reduction_factor: float = SANCTION_RATE_LIMIT_REDUCTION_FACTOR, **kwargs):
        super().__init__(SanctionType.RATE_LIMIT_REDUCTION, target, reason, severity, kwargs)
        self.reduction_factor = reduction_factor
    
    def apply(self) -> Dict[str, Any]:
        """Apply rate limit reduction."""
        if isinstance(self.target, int):  # User ID
            profile_repo = RepositoryFactory.get_repository('user_rate_limit_profile')
            profile = profile_repo.get_by_user_id(self.target)
            
            if profile:
                # Reduce rate limits
                new_daily_limit = int(profile.custom_daily_limit * self.reduction_factor)
                new_hourly_limit = int(profile.custom_hourly_limit * self.reduction_factor)
                
                profile.custom_daily_limit = new_daily_limit
                profile.custom_hourly_limit = new_hourly_limit
                profile.save(update_fields=['custom_daily_limit', 'custom_hourly_limit'])
                
                return {
                    'success': True,
                    'sanction_type': self.sanction_type,
                    'target': self.target,
                    'old_daily_limit': profile.custom_daily_limit / self.reduction_factor,
                    'new_daily_limit': new_daily_limit,
                    'old_hourly_limit': profile.custom_hourly_limit / self.reduction_factor,
                    'new_hourly_limit': new_hourly_limit,
                    'message': f'Rate limits reduced by {self.reduction_factor * 100}%'
                }
            else:
                return {
                    'success': False,
                    'error': 'User profile not found'
                }
        else:
            return {
                'success': False,
                'error': 'Rate limit reduction only supports user IDs'
            }
    
    def revoke(self) -> Dict[str, Any]:
        """Revoke rate limit reduction."""
        if isinstance(self.target, int):  # User ID
            profile_repo = RepositoryFactory.get_repository('user_rate_limit_profile')
            profile = profile_repo.get_by_user_id(self.target)
            
            if profile:

                # Restore default limits
                profile.custom_daily_limit = SANCTION_DEFAULT_DAILY_LIMIT
                profile.custom_hourly_limit = SANCTION_DEFAULT_HOURLY_LIMIT
                profile.save(update_fields=['custom_daily_limit', 'custom_hourly_limit'])
                
                return {
                    'success': True,
                    'sanction_type': self.sanction_type,
                    'target': self.target,
                    'message': 'Rate limits restored to default'
                }
            else:
                return {
                    'success': False,
                    'error': 'User profile not found'
                }
        else:
            return {
                'success': False,
                'error': 'Rate limit reduction only supports user IDs'
            }


class PremiumRevocationSanction(BaseSanction):
    """Premium revocation sanction."""
    
    def apply(self) -> Dict[str, Any]:
        """Apply premium revocation."""
        if isinstance(self.target, int):  # User ID
            profile_repo = RepositoryFactory.get_repository('user_rate_limit_profile')
            profile = profile_repo.get_by_user_id(self.target)
            
            if profile and profile.is_premium:
                profile.is_premium = False
                profile.premium_until = timezone.now() + timedelta(days=SANCTION_PREMIUM_REVOCATION_DAYS)
                profile.custom_daily_limit = SANCTION_DEFAULT_DAILY_LIMIT
                profile.custom_hourly_limit = SANCTION_DEFAULT_HOURLY_LIMIT
                profile.save(update_fields=['is_premium', 'premium_until', 'custom_daily_limit', 'custom_hourly_limit'])
                
                return {
                    'success': True,
                    'sanction_type': self.sanction_type,
                    'target': self.target,
                    'message': 'Premium status revoked'
                }
            else:
                return {
                    'success': False,
                    'error': 'User not found or not premium'
                }
        else:
            return {
                'success': False,
                'error': 'Premium revocation only supports user IDs'
            }
    
    def revoke(self) -> Dict[str, Any]:
        """Revoke premium revocation (restore premium)."""
        if isinstance(self.target, int):  # User ID
            profile_repo = RepositoryFactory.get_repository('user_rate_limit_profile')
            profile = profile_repo.get_by_user_id(self.target)
            
            if profile:
                profile.is_premium = True

                profile.premium_until = timezone.now() + timedelta(days=SANCTION_PREMIUM_REVOCATION_DAYS)
                profile.custom_daily_limit = SANCTION_PREMIUM_DAILY_LIMIT
                profile.custom_hourly_limit = SANCTION_PREMIUM_HOURLY_LIMIT
                profile.save(update_fields=['is_premium', 'premium_until', 'custom_daily_limit', 'custom_hourly_limit'])
                
                return {
                    'success': True,
                    'sanction_type': self.sanction_type,
                    'target': self.target,
                    'message': 'Premium status restored'
                }
            else:
                return {
                    'success': False,
                    'error': 'User profile not found'
                }
        else:
            return {
                'success': False,
                'error': 'Premium revocation only supports user IDs'
            }


class SanctionEngine:
    """
    Engine for applying and managing sanctions.
    """
    
    def __init__(self):
        self.repositories = RepositoryFactory.get_all_repositories()
        self.rules = []
        self.active_sanctions = {}
        self._load_default_rules()
    
    def _load_default_rules(self):
        """Load default sanction rules."""
        

        # Rule: High suspicion score (>80)
        def high_suspicion_rule(context):
            return context.get('suspicion_score', 0) > SUSPICION_SCORE_HIGH_THRESHOLD
        
        self.add_rule(SanctionRule(
            name='high_suspicion',
            condition=high_suspicion_rule,
            sanction_type=SanctionType.WARNING,
            severity=SanctionSeverity.HIGH
        ))
        
        # Rule: Multiple abuse reports

        def multiple_abuse_reports_rule(context):
            return context.get('abuse_report_count', 0) >= ABUSE_REPORT_COUNT_THRESHOLD
        
        self.add_rule(SanctionRule(
            name='multiple_abuse_reports',
            condition=multiple_abuse_reports_rule,
            sanction_type=SanctionType.RATE_LIMIT_REDUCTION,
            severity=SanctionSeverity.MEDIUM,
            parameters={'reduction_factor': SANCTION_RATE_LIMIT_REDUCTION_FACTOR}
        ))
        
        # Rule: Critical abuse

        def critical_abuse_rule(context):
            return context.get('abuse_severity', 0) >= ABUSE_SEVERITY_CRITICAL_THRESHOLD
        
        self.add_rule(SanctionRule(
            name='critical_abuse',
            condition=critical_abuse_rule,
            sanction_type=SanctionType.TEMPORARY_BLOCK,
            severity=SanctionSeverity.HIGH,
            parameters={'hours': SANCTION_TEMPORARY_BLOCK_HOURS}
        ))
        
        # Rule: Severe abuse

        def severe_abuse_rule(context):
            return context.get('abuse_severity', 0) == ABUSE_SEVERITY_SEVERE_THRESHOLD
        
        self.add_rule(SanctionRule(
            name='severe_abuse',
            condition=severe_abuse_rule,
            sanction_type=SanctionType.PERMANENT_BLOCK,
            severity=SanctionSeverity.CRITICAL
        ))
        
        # Rule: High block rate

        def high_block_rate_rule(context):
            return context.get('block_rate', 0) > BLOCK_RATE_THRESHOLD
        
        self.add_rule(SanctionRule(
            name='high_block_rate',
            condition=high_block_rate_rule,
            sanction_type=SanctionType.PREMIUM_REVOCATION,
            severity=SanctionSeverity.MEDIUM
        ))
    
    def add_rule(self, rule: SanctionRule):
        """Add a sanction rule."""
        self.rules.append(rule)
    
    def evaluate_context(self, context: Dict[str, Any]) -> List[BaseSanction]:
        """
        Evaluate context against rules and return applicable sanctions.
        
        Args:
            context: Context data for evaluation
            
        Returns:
            List of applicable sanctions
        """
        sanctions = []
        
        for rule in self.rules:
            if not rule.is_active:
                continue
            
            try:
                if rule.condition(context):
                    sanction = self._create_sanction(rule, context)
                    if sanction:
                        sanctions.append(sanction)
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.name}: {str(e)}")
        
        return sanctions
    
    def _create_sanction(self, rule: SanctionRule, context: Dict[str, Any]) -> Optional[BaseSanction]:
        """Create sanction instance based on rule."""
        target = context.get('target')
        reason = f"Auto-sanction: {rule.name}"
        
        if rule.sanction_type == SanctionType.WARNING:
            return WarningSanction(target, reason, rule.severity, rule.parameters)
        elif rule.sanction_type == SanctionType.TEMPORARY_BLOCK:

            hours = rule.parameters.get('hours', SANCTION_TEMPORARY_BLOCK_HOURS)
            return TemporaryBlockSanction(target, reason, rule.severity, hours=hours)
        elif rule.sanction_type == SanctionType.PERMANENT_BLOCK:
            return PermanentBlockSanction(target, reason, rule.severity, rule.parameters)
        elif rule.sanction_type == SanctionType.RATE_LIMIT_REDUCTION:
            reduction_factor = rule.parameters.get('reduction_factor', SANCTION_RATE_LIMIT_REDUCTION_FACTOR)
            return RateLimitReductionSanction(target, reason, rule.severity, reduction_factor=reduction_factor)
        elif rule.sanction_type == SanctionType.PREMIUM_REVOCATION:
            return PremiumRevocationSanction(target, reason, rule.severity, rule.parameters)
        
        return None
    
    def apply_sanctions(self, sanctions: List[BaseSanction]) -> Dict[str, Any]:
        """
        Apply multiple sanctions.
        
        Args:
            sanctions: List of sanctions to apply
            
        Returns:
            Application results
        """
        results = []
        
        for sanction in sanctions:
            try:
                result = sanction.apply()
                results.append(result)
                
                # Track active sanction
                key = f"{sanction.sanction_type}:{sanction.target}"
                self.active_sanctions[key] = sanction
                
            except Exception as e:
                logger.error(f"Failed to apply sanction: {str(e)}")
                results.append({
                    'success': False,
                    'error': str(e),
                    'sanction_type': sanction.sanction_type,
                    'target': str(sanction.target)
                })
        
        return {
            'success': True,
            'applied_count': len([r for r in results if r.get('success', False)]),
            'failed_count': len([r for r in results if not r.get('success', False)]),
            'results': results
        }
    
    def revoke_sanction(self, sanction_type: str, target: Any) -> Dict[str, Any]:
        """
        Revoke a specific sanction.
        
        Args:
            sanction_type: Type of sanction
            target: Sanction target
            
        Returns:
            Revocation result
        """
        key = f"{sanction_type}:{target}"
        
        if key in self.active_sanctions:
            sanction = self.active_sanctions[key]
            result = sanction.revoke()
            
            if result.get('success', False):
                del self.active_sanctions[key]
            
            return result
        else:
            return {
                'success': False,
                'error': 'No active sanction found',
                'sanction_type': sanction_type,
                'target': str(target)
            }
    
    def get_active_sanctions(self) -> List[Dict[str, Any]]:
        """Get list of active sanctions."""
        sanctions = []
        
        for key, sanction in self.active_sanctions.items():
            if sanction.is_active and not sanction.is_expired():
                sanctions.append({
                    'sanction_type': sanction.sanction_type,
                    'target': str(sanction.target),
                    'reason': sanction.reason,
                    'severity': sanction.severity,
                    'created_at': sanction.created_at.isoformat(),
                    'expires_at': sanction.expires_at.isoformat() if sanction.expires_at else None
                })
        
        return sanctions
    
    def evaluate_user(self, user_id: int) -> Dict[str, Any]:
        """
        Evaluate user for sanctions.
        
        Args:
            user_id: User ID to evaluate
            
        Returns:
            Evaluation results
        """
        try:
            # Get user context
            profile_repo = self.repositories['user_rate_limit_profile']
            profile = profile_repo.get_by_user_id(user_id)
            
            if not profile:
                return {'success': False, 'error': 'User profile not found'}
            
            # Get abuse reports
            abuse_repo = self.repositories['abuse_report']
            abuse_reports = abuse_repo.get_by_user_id(user_id)
            
            # Get recent logs
            log_repo = self.repositories['rate_limit_log']

            recent_logs = log_repo.get_recent(hours=SANCTION_EVALUATION_HOURS, user_id=user_id)
            
            # Build context
            context = {
                'target': user_id,
                'suspicion_score': profile.suspicion_score,
                'abuse_report_count': abuse_reports.count(),
                'abuse_severity': abuse_reports.aggregate(max_severity=Max('severity'))['max_severity'] or 0,
                'block_rate': (recent_logs.filter(status='blocked').count() / max(recent_logs.count(), 1)) * 100,
                'is_premium': profile.is_premium
            }
            
            # Evaluate sanctions
            sanctions = self.evaluate_context(context)
            
            # Apply sanctions
            if sanctions:
                results = self.apply_sanctions(sanctions)
                return {
                    'success': True,
                    'user_id': user_id,
                    'sanctions_applied': len(sanctions),
                    'results': results
                }
            else:
                return {
                    'success': True,
                    'user_id': user_id,
                    'sanctions_applied': 0,
                    'message': 'No sanctions applied'
                }
            
        except Exception as e:
            logger.error(f"Failed to evaluate user {user_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def evaluate_ip(self, ip_address: str) -> Dict[str, Any]:
        """
        Evaluate IP address for sanctions.
        
        Args:
            ip_address: IP address to evaluate
            
        Returns:
            Evaluation results
        """
        try:
            # Get recent logs
            log_repo = self.repositories['rate_limit_log']

            recent_logs = log_repo.get_recent(hours=SANCTION_EVALUATION_HOURS)
            ip_logs = recent_logs.filter(ip_address=ip_address)
            
            # Get abuse reports
            abuse_repo = self.repositories['abuse_report']
            abuse_reports = abuse_repo.get_by_ip(ip_address)
            
            # Build context
            context = {
                'target': ip_address,
                'suspicion_score': RateLimitHelper.calculate_suspicion_score({
                    'ip_address': ip_address,
                    'recent_requests': ip_logs.count(),
                    'unique_endpoints': ip_logs.values('endpoint').distinct().count()
                }),
                'abuse_report_count': abuse_reports.count(),
                'abuse_severity': abuse_reports.aggregate(max_severity=Max('severity'))['max_severity'] or 0,
                'block_rate': (ip_logs.filter(status='blocked').count() / max(ip_logs.count(), 1)) * 100
            }
            
            # Evaluate sanctions
            sanctions = self.evaluate_context(context)
            
            # Apply sanctions
            if sanctions:
                results = self.apply_sanctions(sanctions)
                return {
                    'success': True,
                    'ip_address': ip_address,
                    'sanctions_applied': len(sanctions),
                    'results': results
                }
            else:
                return {
                    'success': True,
                    'ip_address': ip_address,
                    'sanctions_applied': 0,
                    'message': 'No sanctions applied'
                }
            
        except Exception as e:
            logger.error(f"Failed to evaluate IP {ip_address}: {str(e)}")
            return {'success': False, 'error': str(e)}


# Global sanction engine instance
sanction_engine = SanctionEngine()


# Export classes and functions
__all__ = [
    'SanctionType',
    'SanctionSeverity',
    'SanctionRule',
    'BaseSanction',
    'WarningSanction',
    'TemporaryBlockSanction',
    'PermanentBlockSanction',
    'RateLimitReductionSanction',
    'PremiumRevocationSanction',
    'SanctionEngine',
    'sanction_engine'
]
