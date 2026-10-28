"""
rate_limit_service.py – Per-network rate limiting service.

Provides comprehensive rate limiting functionality for postback processing.
Handles multiple time windows, violation tracking, and progressive blocking.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

from api.postback.models import NetworkPostbackConfig, PostbackRateLimit, PostbackLog
from api.postback.exceptions import RateLimitExceededException
from api.postback.choices import PostbackStatus

logger = logging.getLogger(__name__)


class RateLimitService:
    """Service for managing per-network rate limiting."""

    @staticmethod
    def check_rate_limit(network: NetworkPostbackConfig) -> bool:
        """
        Check if the network is currently rate limited.
        Raises RateLimitExceededException if rate limit is exceeded.
        Returns True if request is allowed, False otherwise.
        """
        # Get active rate limits for the network
        rate_limits = PostbackRateLimit.objects.filter(
            network=network,
            is_active=True
        ).order_by('priority')  # Higher priority first
        
        if not rate_limits.exists():
            return True  # No rate limits configured
        
        for rate_limit in rate_limits:
            if rate_limit.is_currently_blocked():
                # Check if block has expired
                if rate_limit.blocked_until and rate_limit.blocked_until <= timezone.now():
                    # Unblock automatically
                    rate_limit.is_blocked = False
                    rate_limit.blocked_until = None
                    rate_limit.save(update_fields=['is_blocked', 'blocked_until', 'updated_at'])
                    logger.info(
                        "Auto-unblocked rate limit %s for network %s",
                        rate_limit.name, network.network_key
                    )
                else:
                    # Still blocked
                    raise RateLimitExceededException(
                        f"Rate limit '{rate_limit.name}' is blocked until {rate_limit.blocked_until}"
                    )
            
            # Check if rate limit is exceeded
            if rate_limit.is_rate_exceeded():
                # Record violation and block
                rate_limit.record_violation()
                raise RateLimitExceededException(
                    f"Rate limit '{rate_limit.name}' exceeded. "
                    f"Current: {rate_limit.current_count}, "
                    f"Limit: {rate_limit.max_per_minute}/min"
                )
        
        return True

    @staticmethod
    def increment_usage(network: NetworkPostbackConfig, increment_count: int = 1) -> bool:
        """
        Increment usage counters for all active rate limits of a network.
        Returns True if increment was successful for all limits, False if any limit was exceeded.
        """
        rate_limits = PostbackRateLimit.objects.filter(
            network=network,
            is_active=True
        ).order_by('priority')
        
        if not rate_limits.exists():
            return True  # No rate limits configured
        
        all_success = True
        
        for rate_limit in rate_limits:
            try:
                success = rate_limit.increment_count()
                if not success:
                    all_success = False
                    logger.warning(
                        "Rate limit %s exceeded for network %s",
                        rate_limit.name, network.network_key
                    )
            except Exception as exc:
                logger.error(
                    "Error incrementing rate limit %s for network %s: %s",
                    rate_limit.name, network.network_key, exc
                )
                all_success = False
        
        return all_success

    @staticmethod
    def get_network_rate_limits(network: NetworkPostbackConfig) -> List[PostbackRateLimit]:
        """Get all rate limits for a network, ordered by priority."""
        return PostbackRateLimit.objects.filter(
            network=network
        ).order_by('-priority', 'name')

    @staticmethod
    def get_active_rate_limits(network: NetworkPostbackConfig) -> List[PostbackRateLimit]:
        """Get active rate limits for a network, ordered by priority."""
        return PostbackRateLimit.objects.filter(
            network=network,
            is_active=True
        ).order_by('-priority', 'name')

    @staticmethod
    def get_blocked_rate_limits(network: NetworkPostbackConfig) -> List[PostbackRateLimit]:
        """Get currently blocked rate limits for a network."""
        return PostbackRateLimit.objects.filter(
            network=network,
            is_active=True,
            is_blocked=True
        ).order_by('-priority', 'name')

    @staticmethod
    def create_rate_limit(
        network: NetworkPostbackConfig,
        name: str,
        max_per_minute: int,
        max_per_hour: Optional[int] = None,
        max_per_day: Optional[int] = None,
        priority: int = 0,
        description: str = ""
    ) -> PostbackRateLimit:
        """Create a new rate limit for a network."""
        # Set default values if not provided
        if max_per_hour is None:
            max_per_hour = max_per_minute * 60  # Default: 60x minute limit
        if max_per_day is None:
            max_per_day = max_per_hour * 24  # Default: 24x hour limit
        
        # Validate hierarchy
        if max_per_hour < max_per_minute:
            raise ValueError("max_per_hour must be >= max_per_minute")
        if max_per_day < max_per_hour:
            raise ValueError("max_per_day must be >= max_per_hour")
        
        rate_limit = PostbackRateLimit.objects.create(
            network=network,
            name=name,
            max_per_minute=max_per_minute,
            max_per_hour=max_per_hour,
            max_per_day=max_per_day,
            priority=priority,
            description=description,
            current_count=0,
            is_active=True,
            is_blocked=False,
            total_violations=0
        )
        
        # Generate integrity hash
        rate_limit.integrity_hash = rate_limit.generate_integrity_hash()
        rate_limit.save()
        
        logger.info(
            "Created rate limit %s for network %s: %d/min, %d/hour, %d/day",
            name, network.network_key, max_per_minute, max_per_hour, max_per_day
        )
        
        return rate_limit

    @staticmethod
    def update_rate_limit(
        rate_limit_id: str,
        name: Optional[str] = None,
        max_per_minute: Optional[int] = None,
        max_per_hour: Optional[int] = None,
        max_per_day: Optional[int] = None,
        priority: Optional[int] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> PostbackRateLimit:
        """Update an existing rate limit."""
        try:
            rate_limit = PostbackRateLimit.objects.get(id=rate_limit_id)
        except PostbackRateLimit.DoesNotExist:
            raise ValueError(f"Rate limit with id {rate_limit_id} not found")
        
        # Update fields if provided
        if name is not None:
            rate_limit.name = name
        if max_per_minute is not None:
            rate_limit.max_per_minute = max_per_minute
        if max_per_hour is not None:
            rate_limit.max_per_hour = max_per_hour
        if max_per_day is not None:
            rate_limit.max_per_day = max_per_day
        if priority is not None:
            rate_limit.priority = priority
        if description is not None:
            rate_limit.description = description
        if is_active is not None:
            rate_limit.is_active = is_active
        
        # Validate hierarchy if limits were updated
        if (rate_limit.max_per_hour < rate_limit.max_per_minute or
            rate_limit.max_per_day < rate_limit.max_per_hour):
            raise ValueError("Rate limit hierarchy must be: minute <= hour <= day")
        
        # Generate new integrity hash
        rate_limit.integrity_hash = rate_limit.generate_integrity_hash()
        rate_limit.save()
        
        logger.info(
            "Updated rate limit %s for network %s",
            rate_limit.name, rate_limit.network.network_key
        )
        
        return rate_limit

    @staticmethod
    def reset_rate_limit(rate_limit_id: str) -> PostbackRateLimit:
        """Reset the counting window for a rate limit."""
        try:
            rate_limit = PostbackRateLimit.objects.get(id=rate_limit_id)
        except PostbackRateLimit.DoesNotExist:
            raise ValueError(f"Rate limit with id {rate_limit_id} not found")
        
        rate_limit.reset_window()
        
        logger.info(
            "Reset rate limit %s for network %s",
            rate_limit.name, rate_limit.network.network_key
        )
        
        return rate_limit

    @staticmethod
    def unblock_rate_limit(rate_limit_id: str) -> PostbackRateLimit:
        """Manually unblock a rate limit."""
        try:
            rate_limit = PostbackRateLimit.objects.get(id=rate_limit_id)
        except PostbackRateLimit.DoesNotExist:
            raise ValueError(f"Rate limit with id {rate_limit_id} not found")
        
        rate_limit.is_blocked = False
        rate_limit.blocked_until = None
        rate_limit.save(update_fields=['is_blocked', 'blocked_until', 'updated_at'])
        
        logger.info(
            "Manually unblocked rate limit %s for network %s",
            rate_limit.name, rate_limit.network.network_key
        )
        
        return rate_limit

    @staticmethod
    def delete_rate_limit(rate_limit_id: str) -> bool:
        """Delete a rate limit."""
        try:
            rate_limit = PostbackRateLimit.objects.get(id=rate_limit_id)
            network_key = rate_limit.network.network_key
            rate_limit_name = rate_limit.name
            rate_limit.delete()
            
            logger.info(
                "Deleted rate limit %s for network %s",
                rate_limit_name, network_key
            )
            
            return True
        except PostbackRateLimit.DoesNotExist:
            return False

    @staticmethod
    def get_rate_limit_statistics(network: NetworkPostbackConfig) -> Dict:
        """Get comprehensive statistics for all rate limits of a network."""
        rate_limits = PostbackRateLimit.objects.filter(network=network)
        
        if not rate_limits.exists():
            return {
                'network_key': network.network_key,
                'total_limits': 0,
                'active_limits': 0,
                'blocked_limits': 0,
                'total_violations': 0,
                'average_utilization': 0.0,
                'limits': []
            }
        
        active_limits = rate_limits.filter(is_active=True)
        blocked_limits = active_limits.filter(is_blocked=True)
        
        # Calculate utilization
        total_utilization = 0
        utilizations = []
        
        for rate_limit in rate_limits:
            utilization = rate_limit.current_utilization()
            utilizations.append({
                'name': rate_limit.name,
                'current_count': rate_limit.current_count,
                'max_per_minute': rate_limit.max_per_minute,
                'utilization': utilization,
                'is_blocked': rate_limit.is_blocked,
                'total_violations': rate_limit.total_violations
            })
            
            if rate_limit.is_active:
                total_utilization += utilization
        
        avg_utilization = total_utilization / active_limits.count() if active_limits.exists() else 0
        
        return {
            'network_key': network.network_key,
            'total_limits': rate_limits.count(),
            'active_limits': active_limits.count(),
            'blocked_limits': blocked_limits.count(),
            'total_violations': sum(rl.total_violations for rl in rate_limits),
            'average_utilization': round(avg_utilization, 2),
            'limits': utilizations
        }

    @staticmethod
    def get_violation_history(
        network: NetworkPostbackConfig,
        days: int = 7
    ) -> List[Dict]:
        """Get violation history for a network over the specified period."""
        # This would typically require a separate violation log table
        # For now, we'll return recent violations from rate limits
        
        rate_limits = PostbackRateLimit.objects.filter(
            network=network,
            total_violations__gt=0
        ).order_by('-last_violation_at')
        
        violations = []
        
        for rate_limit in rate_limits:
            if rate_limit.last_violation_at:
                violations.append({
                    'rate_limit_name': rate_limit.name,
                    'violation_count': rate_limit.total_violations,
                    'last_violation_at': rate_limit.last_violation_at.isoformat(),
                    'blocked_until': rate_limit.blocked_until.isoformat() if rate_limit.blocked_until else None,
                    'is_currently_blocked': rate_limit.is_blocked
                })
        
        return violations

    @staticmethod
    @transaction.atomic
    def reset_all_rate_limits(network: NetworkPostbackConfig) -> int:
        """Reset all rate limits for a network."""
        rate_limits = PostbackRateLimit.objects.filter(network=network)
        reset_count = 0
        
        for rate_limit in rate_limits:
            rate_limit.reset_window()
            reset_count += 1
        
        logger.info(
            "Reset %d rate limits for network %s",
            reset_count, network.network_key
        )
        
        return reset_count

    @staticmethod
    @transaction.atomic
    def unblock_all_rate_limits(network: NetworkPostbackConfig) -> int:
        """Unblock all rate limits for a network."""
        updated_count = PostbackRateLimit.objects.filter(
            network=network,
            is_blocked=True
        ).update(
            is_blocked=False,
            blocked_until=None,
            updated_at=timezone.now()
        )
        
        logger.info(
            "Unblocked %d rate limits for network %s",
            updated_count, network.network_key
        )
        
        return updated_count

    @staticmethod
    def get_rate_limit_recommendations(network: NetworkPostbackConfig) -> Dict:
        """Get recommendations for rate limit configuration based on usage patterns."""
        # Get recent postback logs for analysis
        recent_logs = PostbackLog.objects.filter(
            network=network,
            received_at__gte=timezone.now() - timedelta(days=7)
        )
        
        if not recent_logs.exists():
            return {
                'network_key': network.network_key,
                'recommendations': [
                    'No recent activity found. Consider monitoring usage before setting rate limits.'
                ],
                'current_limits': [],
                'usage_stats': {}
            }
        
        # Analyze usage patterns
        total_logs = recent_logs.count()
        logs_by_hour = {}
        
        for log in recent_logs:
            hour = log.received_at.hour
            logs_by_hour[hour] = logs_by_hour.get(hour, 0) + 1
        
        # Calculate statistics
        peak_hour = max(logs_by_hour.items(), key=lambda x: x[1])[0] if logs_by_hour else 0
        peak_count = logs_by_hour.get(peak_hour, 0)
        avg_per_hour = total_logs / 24 if total_logs > 0 else 0
        
        # Get current rate limits
        current_limits = RateLimitService.get_active_rate_limits(network)
        
        recommendations = []
        
        # Generate recommendations
        if not current_limits:
            recommendations.append(
                f"Consider setting a rate limit of ~{int(peak_count * 1.5)}/minute based on peak usage."
            )
        else:
            for limit in current_limits:
                utilization = limit.current_utilization
                if utilization > 80:
                    recommendations.append(
                        f"Rate limit '{limit.name}' is at {utilization:.1f}% utilization. "
                        f"Consider increasing the limit to {int(limit.max_per_minute * 1.5)}/minute."
                    )
                elif utilization < 20:
                    recommendations.append(
                        f"Rate limit '{limit.name}' is only at {utilization:.1f}% utilization. "
                        f"Consider reducing the limit to {int(limit.max_per_minute * 0.5)}/minute."
                    )
        
        if avg_per_hour > 0:
            recommendations.append(
                f"Average usage is {avg_per_hour:.1f}/hour. "
                f"Set hourly limits to ~{int(avg_per_hour * 1.5)} for comfortable headroom."
            )
        
        return {
            'network_key': network.network_key,
            'recommendations': recommendations,
            'current_limits': [
                {
                    'name': limit.name,
                    'max_per_minute': limit.max_per_minute,
                    'current_utilization': limit.current_utilization(),
                    'is_blocked': limit.is_blocked
                }
                for limit in current_limits
            ],
            'usage_stats': {
                'total_requests_7days': total_logs,
                'peak_hour_requests': peak_count,
                'peak_hour': peak_hour,
                'avg_per_hour': round(avg_per_hour, 2),
                'requests_by_hour': logs_by_hour
            }
        }

    @staticmethod
    def cleanup_expired_blocks(network: NetworkPostbackConfig) -> int:
        """Clean up expired blocks for a network."""
        now = timezone.now()
        expired_count = PostbackRateLimit.objects.filter(
            network=network,
            is_blocked=True,
            blocked_until__lt=now
        ).update(
            is_blocked=False,
            blocked_until=None,
            updated_at=now
        )
        
        if expired_count > 0:
            logger.info(
                "Cleaned up %d expired blocks for network %s",
                expired_count, network.network_key
            )
        
        return expired_count

    @staticmethod
    def verify_rate_limit_integrity(rate_limit_id: str) -> Dict:
        """Verify the integrity hash of a rate limit."""
        try:
            rate_limit = PostbackRateLimit.objects.get(id=rate_limit_id)
        except PostbackRateLimit.DoesNotExist:
            raise ValueError(f"Rate limit with id {rate_limit_id} not found")
        
        is_valid = rate_limit.verify_integrity()
        
        return {
            'rate_limit_id': rate_limit_id,
            'rate_limit_name': rate_limit.name,
            'network_key': rate_limit.network.network_key,
            'is_valid': is_valid,
            'last_updated': rate_limit.updated_at.isoformat(),
            'integrity_hash': rate_limit.integrity_hash
        }

    @staticmethod
    def batch_verify_integrity(network: NetworkPostbackConfig) -> Dict:
        """Verify integrity of all rate limits for a network."""
        rate_limits = PostbackRateLimit.objects.filter(network=network)
        
        results = {
            'network_key': network.network_key,
            'total_limits': rate_limits.count(),
            'valid': 0,
            'invalid': 0,
            'invalid_limits': []
        }
        
        for rate_limit in rate_limits:
            is_valid = rate_limit.verify_integrity()
            
            if is_valid:
                results['valid'] += 1
            else:
                results['invalid'] += 1
                results['invalid_limits'].append({
                    'rate_limit_id': str(rate_limit.id),
                    'rate_limit_name': rate_limit.name,
                    'integrity_hash': rate_limit.integrity_hash
                })
        
        return results
