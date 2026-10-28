"""
Enhanced Password History Service with comprehensive security model integration
Author: System Security Team
Version: 2.0.0

Advanced password management, compliance checking, and security analytics.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from ..models import PasswordHistory
from ..utils.cache_manager import CacheManager, handle_gracefully

logger = logging.getLogger(__name__)


class PasswordHistoryService:
    """
    Service for managing password history with defensive coding patterns
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_service_instance(cls):
        """Get singleton instance of the service"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """Initialize service with cache manager"""
        self.cache_manager = CacheManager.get_instance()
        self.logger = logging.getLogger(__name__)
    
    @handle_gracefully(default_return=[])
    def get_password_history(self, user, limit: int = 10, 
                           include_inactive: bool = False) -> List[PasswordHistory]:
        """
        Get password history for a user
        """
        try:
            cache_key = f"password_history_{user.id}_{limit}_{include_inactive}"
            cached_result = self.cache_manager.get(cache_key)
            
            if cached_result is not None:
                return cached_result
            
            queryset = PasswordHistory.objects.filter(user=user)
            
            if not include_inactive:
                queryset = queryset.filter(is_active=True)
            
            history = list(queryset.order_by('-changed_at')[:limit])
            
            # Convert to dict format
            result = []
            for record in history:
                result.append({
                    'id': record.id,
                    'password_strength': record.password_strength,
                    'algorithm': record.password_algorithm,
                    'change_reason': record.change_reason,
                    'changed_at': record.changed_at.isoformat(),
                    'changed_by': record.changed_by.username if record.changed_by else None,
                    'is_compromised': record.is_compromised,
                    'ip_address': record.ip_address
                })
            
            # Cache for 10 minutes
            self.cache_manager.set(cache_key, result, timeout=600)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting password history: {e}")
            return []
    
    @handle_gracefully(default_return=False)
    def check_password_reuse(self, user, new_password_hash: str, 
                          reuse_limit: int = 5) -> Tuple[bool, List[str]]:
        """
        Check if password is being reused
        """
        try:
            recent_passwords = PasswordHistory.objects.filter(
                user=user,
                is_active=True
            ).order_by('-changed_at')[:reuse_limit]
            
            reused_passwords = [
                pwd.password_hash for pwd in recent_passwords 
                if pwd.password_hash == new_password_hash
            ]
            
            is_reused = len(reused_passwords) > 0
            return is_reused, reused_passwords
            
        except Exception as e:
            self.logger.error(f"Error checking password reuse: {e}")
            return False, []
    
    @handle_gracefully(default_return=False)
    def add_password_change(self, user, password_hash: str, password_strength: int,
                        algorithm: str = 'pbkdf2_sha256', change_reason: str = 'user_request',
                        ip_address: str = None, user_agent: str = None,
                        changed_by=None) -> Optional[PasswordHistory]:
        """
        Add a password change record
        """
        try:
            # Check if this password was recently used
            is_reused, reused_passwords = self.check_password_reuse(
                user, password_hash, getattr(settings, 'PASSWORD_REUSE_LIMIT', 5)
            )
            
            if is_reused:
                self.logger.warning(f"Password reuse detected for user {user.username}")
                return None
            
            # Create password history record
            password_history = PasswordHistory.objects.create(
                user=user,
                password_hash=password_hash,
                password_algorithm=algorithm,
                password_strength=password_strength,
                change_reason=change_reason,
                ip_address=ip_address,
                user_agent=user_agent,
                changed_by=changed_by or user
            )
            
            self.logger.info(f"Password change recorded for user {user.username}")
            
            # Clear password history cache
            cache_key = f"password_history_{user.id}_10_false"
            self.cache_manager.delete(cache_key)
            
            return password_history
            
        except Exception as e:
            self.logger.error(f"Error adding password change: {e}")
            return None
    
    @handle_gracefully(default_return=False)
    def mark_password_compromised(self, user, password_history_id: int, 
                                reason: str = "Security compromise detected") -> bool:
        """
        Mark a password as compromised
        """
        try:
            password_history = PasswordHistory.objects.get(
                id=password_history_id,
                user=user
            )
            
            password_history.is_compromised = True
            password_history.save()
            
            # Log security event
            from ..models import SecurityLog
            SecurityLog.objects.create(
                user=user,
                action_type='PASSWORD_COMPROMISE',
                description=f"Password marked as compromised: {reason}",
                severity='critical',
                ip_address=password_history.ip_address
            )
            
            self.logger.warning(f"Password marked as compromised for user {user.username}")
            return True
            
        except PasswordHistory.DoesNotExist:
            self.logger.error(f"Password history not found: {password_history_id}")
            return False
        except Exception as e:
            self.logger.error(f"Error marking password compromised: {e}")
            return False
    
    @handle_gracefully(default_return=[])
    def get_password_strength_trends(self, user, days: int = 30) -> Dict[str, Any]:
        """
        Get password strength trends for a user
        """
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            history = PasswordHistory.objects.filter(
                user=user,
                changed_at__gte=start_date,
                changed_at__lte=end_date
            ).order_by('changed_at')
            
            strength_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
            
            for record in history:
                strength = record.password_strength
                if strength in strength_counts:
                    strength_counts[strength] += 1
            
            total = sum(strength_counts.values())
            
            trends = {
                'period': f"Last {days} days",
                'total_changes': total,
                'strength_distribution': strength_counts,
                'average_strength': sum(
                    strength * count for strength, count in strength_counts.items()
                ) / total if total > 0 else 0,
                'strongest_strength': max(strength_counts.keys()) if strength_counts else 1,
                'weakest_strength': min(strength_counts.keys()) if strength_counts else 1
            }
            
            return trends
            
        except Exception as e:
            self.logger.error(f"Error getting password strength trends: {e}")
            return {}
    
    @handle_gracefully(default_return=False)
    def cleanup_old_password_history(self, user, days_to_keep: int = 365) -> int:
        """
        Clean up old password history records
        """
        try:
            cutoff_date = timezone.now() - timedelta(days=days_to_keep)
            
            deleted_count = PasswordHistory.objects.filter(
                user=user,
                changed_at__lt=cutoff_date
            ).delete()
            
            self.logger.info(f"Cleaned up {deleted_count} old password history records for user {user.username}")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Error cleaning up password history: {e}")
            return 0
    
    @handle_gracefully(default_return={})
    def get_password_policy_compliance(self, user) -> Dict[str, Any]:
        """
        Check user's password history against security policies
        """
        try:
            from ..models import SecurityPolicy
            
            # Get active password policies
            policies = SecurityPolicy.objects.filter(
                policy_type='password',
                is_active=True
            )
            
            user_history = PasswordHistory.objects.filter(
                user=user,
                is_active=True
            ).order_by('-changed_at')[:10]
            
            compliance_result = {
                'user_id': user.id,
                'username': user.username,
                'policies_checked': policies.count(),
                'password_history_count': user_history.count(),
                'compliance_issues': [],
                'recommendations': []
            }
            
            # Check each policy
            for policy in policies:
                policy_value = policy.get_policy_value()
                validation_rules = policy.validation_rules or {}
                
                if policy.policy_key == 'min_length':
                    min_length = validation_rules.get('min', 8)
                    if policy_value and policy_value < min_length:
                        compliance_result['compliance_issues'].append(
                            f"Password length {policy_value} < minimum {min_length}"
                        )
                
                elif policy.policy_key == 'max_age_days':
                    max_age = validation_rules.get('max', 90)
                    if user_history:
                        latest_change = user_history[0]
                        age_days = (timezone.now() - latest_change.changed_at).days
                        if age_days > max_age:
                            compliance_result['compliance_issues'].append(
                                f"Password age {age_days} days > maximum {max_age}"
                            )
                            compliance_result['recommendations'].append(
                                "Password should be changed"
                            )
                
                elif policy.policy_key == 'no_reuse':
                    reuse_limit = validation_rules.get('limit', 5)
                    if len(user_history) > reuse_limit:
                        compliance_result['compliance_issues'].append(
                            f"Password history count {len(user_history)} > limit {reuse_limit}"
                        )
            
            return compliance_result
            
        except Exception as e:
            self.logger.error(f"Error checking password policy compliance: {e}")
            return {'error': str(e)}