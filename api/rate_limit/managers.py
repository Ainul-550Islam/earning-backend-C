# api/rate_limit/managers.py
"""
Custom Managers for Rate Limit Module

Provides custom query managers for rate limiting models with optimized queries
and business logic methods.
"""

import logging
from datetime import datetime, timedelta
from django.db import models
from django.db.models import Q, Count, Sum, Avg, Max, Min, F, Case, When
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class RateLimitLogManager(models.Manager):
    """
    Custom manager for RateLimitLog model with optimized queries.
    """
    
    def get_queryset(self):
        """Get base queryset with select_related optimizations."""
        return super().get_queryset().select_related('user', 'config')
    
    def for_ip(self, ip_address):
        """Get logs for specific IP address."""
        return self.get_queryset().filter(ip_address=ip_address)
    
    def for_user(self, user):
        """Get logs for specific user."""
        return self.get_queryset().filter(user=user)
    
    def for_endpoint(self, endpoint):
        """Get logs for specific endpoint."""
        return self.get_queryset().filter(endpoint=endpoint)
    
    def blocked(self):
        """Get only blocked requests."""
        return self.get_queryset().filter(status='blocked')
    
    def allowed(self):
        """Get only allowed requests."""
        return self.get_queryset().filter(status='allowed')
    
    def since(self, time_delta):
        """Get logs since a specific time delta."""
        since_time = timezone.now() - time_delta
        return self.get_queryset().filter(timestamp__gte=since_time)
    
    def last_hour(self):
        """Get logs from the last hour."""
        return self.since(timedelta(hours=1))
    
    def last_24h(self):
        """Get logs from the last 24 hours."""
        return self.since(timedelta(hours=24))
    
    def last_week(self):
        """Get logs from the last week."""
        return self.since(timedelta(days=7))
    
    def by_suspicion_score(self, min_score=None, max_score=None):
        """Filter logs by suspicion score range."""
        queryset = self.get_queryset()
        if min_score is not None:
            queryset = queryset.filter(suspicion_score__gte=min_score)
        if max_score is not None:
            queryset = queryset.filter(suspicion_score__lte=max_score)
        return queryset
    
    def high_suspicion(self, min_score=70):
        """Get logs with high suspicion scores."""
        return self.by_suspicion_score(min_score=min_score)
    
    def top_offenders(self, time_period=timedelta(hours=24), limit=10):
        """Get top offending IPs by block count."""
        since_time = timezone.now() - time_period
        
        return (
            self.get_queryset()
            .filter(timestamp__gte=since_time, status='blocked')
            .values('ip_address')
            .annotate(
                block_count=Count('id'),
                last_blocked=Max('timestamp'),
                suspicion_score=Avg('suspicion_score')
            )
            .order_by('-block_count')[:limit]
        )
    
    def endpoint_stats(self, time_period=timedelta(hours=24)):
        """Get statistics per endpoint."""
        since_time = timezone.now() - time_period
        
        return (
            self.get_queryset()
            .filter(timestamp__gte=since_time)
            .values('endpoint')
            .annotate(
                total_requests=Count('id'),
                blocked_requests=Count('id', filter=Q(status='blocked')),
                allowed_requests=Count('id', filter=Q(status='allowed')),
                block_rate=Count('id', filter=Q(status='blocked')) * 100.0 / Count('id'),
                avg_suspicion_score=Avg('suspicion_score')
            )
            .order_by('-total_requests')
        )
    
    def hourly_stats(self, hours=24):
        """Get hourly statistics."""
        since_time = timezone.now() - timedelta(hours=hours)
        
        return (
            self.get_queryset()
            .filter(timestamp__gte=since_time)
            .extra({
                'hour': "strftime('%%H', timestamp)"
            })
            .values('hour')
            .annotate(
                total_requests=Count('id'),
                blocked_requests=Count('id', filter=Q(status='blocked')),
                unique_ips=Count('ip_address', distinct=True),
                unique_users=Count('user', distinct=True)
            )
            .order_by('hour')
        )
    
    def cleanup_old_logs(self, days=30):
        """Clean up logs older than specified days."""
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count = self.get_queryset().filter(timestamp__lt=cutoff_date).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old rate limit logs (older than {days} days)")
        return deleted_count
    
    def get_ip_activity_pattern(self, ip_address, hours=24):
        """Get activity pattern for an IP address."""
        since_time = timezone.now() - timedelta(hours=hours)
        
        logs = self.for_ip(ip_address).filter(timestamp__gte=since_time).order_by('timestamp')
        
        # Calculate time gaps between requests
        time_gaps = []
        prev_timestamp = None
        
        for log in logs:
            if prev_timestamp:
                gap = (log.timestamp - prev_timestamp).total_seconds()
                time_gaps.append(gap)
            prev_timestamp = log.timestamp
        
        return {
            'total_requests': logs.count(),
            'blocked_requests': logs.filter(status='blocked').count(),
            'unique_endpoints': logs.values('endpoint').distinct().count(),
            'time_gaps': time_gaps,
            'avg_gap': sum(time_gaps) / len(time_gaps) if time_gaps else 0,
            'max_gap': max(time_gaps) if time_gaps else 0,
            'min_gap': min(time_gaps) if time_gaps else 0,
        }


class RateLimitConfigManager(models.Manager):
    """
    Custom manager for RateLimitConfig model.
    """
    
    def get_queryset(self):
        """Get base queryset."""
        return super().get_queryset()
    
    def active(self):
        """Get only active configurations."""
        return self.get_queryset().filter(is_active=True)
    
    def inactive(self):
        """Get only inactive configurations."""
        return self.get_queryset().filter(is_active=False)
    
    def for_type(self, rate_limit_type):
        """Get configurations for specific type."""
        return self.get_queryset().filter(rate_limit_type=rate_limit_type)
    
    def for_endpoint(self, endpoint):
        """Get configurations for specific endpoint."""
        return self.get_queryset().filter(endpoint=endpoint)
    
    def for_ip(self, ip_address):
        """Get configurations for specific IP address."""
        return self.get_queryset().filter(ip_address=ip_address)
    
    def for_user(self, user):
        """Get configurations for specific user."""
        return self.get_queryset().filter(user=user)
    
    def global_configs(self):
        """Get global rate limit configurations."""
        return self.get_queryset().filter(rate_limit_type='global')
    
    def user_configs(self):
        """Get user-based rate limit configurations."""
        return self.get_queryset().filter(rate_limit_type='user')
    
    def ip_configs(self):
        """Get IP-based rate limit configurations."""
        return self.get_queryset().filter(rate_limit_type='ip')
    
    def endpoint_configs(self):
        """Get endpoint-based rate limit configurations."""
        return self.get_queryset().filter(rate_limit_type='endpoint')
    
    def applicable_configs(self, request):
        """Get all configurations applicable to a request."""
        configs = self.active()
        
        user = getattr(request, 'user', None)
        ip_address = self._get_client_ip(request)
        endpoint = request.path
        
        applicable = []
        
        # Add global configs
        applicable.extend(self.global_configs())
        
        # Add IP-specific configs
        applicable.extend(self.for_ip(ip_address))
        
        # Add user-specific configs
        if user and user.is_authenticated:
            applicable.extend(self.for_user(user))
        
        # Add endpoint-specific configs
        applicable.extend(self.for_endpoint(endpoint))
        
        return applicable
    
    def _get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
    
    def get_most_hit_configs(self, limit=10):
        """Get configurations with most hits."""
        return self.get_queryset().order_by('-hit_count')[:limit]
    
    def get_most_blocked_configs(self, limit=10):
        """Get configurations with most blocks."""
        return self.get_queryset().order_by('-block_count')[:limit]
    
    def reset_statistics(self, config_ids=None):
        """Reset statistics for configurations."""
        queryset = self.get_queryset()
        if config_ids:
            queryset = queryset.filter(id__in=config_ids)
        
        updated = queryset.update(hit_count=0, block_count=0, last_hit_at=None)
        logger.info(f"Reset statistics for {updated} rate limit configurations")
        return updated
    
    def bulk_activate(self, config_ids):
        """Bulk activate configurations."""
        updated = self.get_queryset().filter(id__in=config_ids).update(is_active=True)
        logger.info(f"Activated {updated} rate limit configurations")
        return updated
    
    def bulk_deactivate(self, config_ids):
        """Bulk deactivate configurations."""
        updated = self.get_queryset().filter(id__in=config_ids).update(is_active=False)
        logger.info(f"Deactivated {updated} rate limit configurations")
        return updated


class UserRateLimitProfileManager(models.Manager):
    """
    Custom manager for UserRateLimitProfile model.
    """
    
    def get_queryset(self):
        """Get base queryset with select_related optimizations."""
        return super().get_queryset().select_related('user')
    
    def premium_users(self):
        """Get premium user profiles."""
        return self.get_queryset().filter(is_premium=True)
    
    def standard_users(self):
        """Get standard user profiles."""
        return self.get_queryset().filter(is_premium=False)
    
    def expired_premium(self):
        """Get users with expired premium status."""
        return self.get_queryset().filter(
            is_premium=True,
            premium_until__lt=timezone.now()
        )
    
    def high_usage_users(self, threshold=0.8):
        """Get users with high usage (80%+ of their limits)."""
        return self.get_queryset().filter(
            current_usage__gt=F('custom_daily_limit') * threshold
        )
    
    def blocked_users(self):
        """Get users with high block rates."""
        return self.get_queryset().filter(
            blocked_requests__gt=F('total_requests') * 0.3  # 30%+ block rate
        )
    
    def suspicious_users(self, min_score=70):
        """Get users with high suspicion scores."""
        return self.get_queryset().filter(suspicion_score__gte=min_score)
    
    def top_users_by_requests(self, limit=10, days=30):
        """Get top users by request count."""
        since_time = timezone.now() - timedelta(days=days)
        
        return (
            self.get_queryset()
            .filter(last_request_at__gte=since_time)
            .order_by('-total_requests')[:limit]
        )
    
    def users_needing_attention(self):
        """Get users that need admin attention."""
        return self.get_queryset().filter(
            Q(suspicion_score__gte=70) |
            Q(api_health_score__lte=40) |
            Q(is_premium=True, premium_until__lt=timezone.now())
        )
    
    def upgrade_to_premium(self, user_ids, days=30):
        """Upgrade users to premium status."""
        expires_at = timezone.now() + timedelta(days=days)
        updated = self.get_queryset().filter(user_id__in=user_ids).update(
            is_premium=True,
            premium_until=expires_at
        )
        logger.info(f"Upgraded {updated} users to premium for {days} days")
        return updated
    
    def downgrade_to_standard(self, user_ids):
        """Downgrade users to standard status."""
        updated = self.get_queryset().filter(user_id__in=user_ids).update(
            is_premium=False,
            premium_until=None
        )
        logger.info(f"Downgraded {updated} users to standard")
        return updated
    
    def reset_usage_stats(self, user_ids=None):
        """Reset usage statistics for users."""
        queryset = self.get_queryset()
        if user_ids:
            queryset = queryset.filter(user_id__in=user_ids)
        
        updated = queryset.update(
            current_usage=0,
            daily_usage=0,
            hourly_usage=0,
            api_health_score=100,
            suspicion_score=0
        )
        logger.info(f"Reset usage statistics for {updated} users")
        return updated


class AbuseReportManager(models.Manager):
    """
    Custom manager for AbuseReport model.
    """
    
    def get_queryset(self):
        """Get base queryset with select_related optimizations."""
        return super().get_queryset().select_related('user', 'created_by')
    
    def active(self):
        """Get active abuse reports."""
        return self.get_queryset().filter(is_active=True)
    
    def investigated(self):
        """Get investigated abuse reports."""
        return self.get_queryset().filter(is_investigated=True)
    
    def uninvestigated(self):
        """Get uninvestigated abuse reports."""
        return self.get_queryset().filter(is_investigated=False)
    
    def blocked(self):
        """Get reports that resulted in blocks."""
        return self.get_queryset().filter(is_blocked=True)
    
    def for_ip(self, ip_address):
        """Get reports for specific IP address."""
        return self.get_queryset().filter(ip_address=ip_address)
    
    def for_user(self, user):
        """Get reports for specific user."""
        return self.get_queryset().filter(user=user)
    
    def by_abuse_type(self, abuse_type):
        """Get reports by abuse type."""
        return self.get_queryset().filter(abuse_type=abuse_type)
    
    def high_severity(self, min_severity=4):
        """Get high severity abuse reports."""
        return self.get_queryset().filter(severity__gte=min_severity)
    
    def recent(self, hours=24):
        """Get recent abuse reports."""
        since_time = timezone.now() - timedelta(hours=hours)
        return self.get_queryset().filter(created_at__gte=since_time)
    
    def top_abusive_ips(self, hours=24, limit=10):
        """Get IPs with most abuse reports."""
        since_time = timezone.now() - timedelta(hours=hours)
        
        return (
            self.get_queryset()
            .filter(created_at__gte=since_time)
            .values('ip_address')
            .annotate(
                report_count=Count('id'),
                avg_severity=Avg('severity'),
                blocked_count=Count('id', filter=Q(is_blocked=True))
            )
            .order_by('-report_count')[:limit]
        )
    
    def abuse_types_stats(self, hours=24):
        """Get statistics by abuse types."""
        since_time = timezone.now() - timedelta(hours=hours)
        
        return (
            self.get_queryset()
            .filter(created_at__gte=since_time)
            .values('abuse_type')
            .annotate(
                count=Count('id'),
                avg_severity=Avg('severity'),
                blocked_rate=Count('id', filter=Q(is_blocked=True)) * 100.0 / Count('id')
            )
            .order_by('-count')
        )
    
    def mark_as_investigated(self, report_ids, investigator=None):
        """Mark reports as investigated."""
        queryset = self.get_queryset().filter(id__in=report_ids)
        if investigator:
            queryset = queryset.filter(investigated_by=investigator)
        
        updated = queryset.update(is_investigated=True)
        logger.info(f"Marked {updated} abuse reports as investigated")
        return updated
    
    def auto_block_ips(self, threshold=5, hours=24):
        """Automatically block IPs with multiple abuse reports."""
        since_time = timezone.now() - timedelta(hours=hours)
        
        # Find IPs with multiple reports
        abusive_ips = (
            self.get_queryset()
            .filter(created_at__gte=since_time, is_blocked=False)
            .values('ip_address')
            .annotate(report_count=Count('id'))
            .filter(report_count__gte=threshold)
            .values_list('ip_address', flat=True)
        )
        
        # Create IP blocks
        from api.rate_limit.models import IPBlockList
        blocks_created = 0
        
        for ip_address in abusive_ips:
            block, created = IPBlockList.objects.get_or_create(
                ip_address=ip_address,
                defaults={
                    'block_type': 'single',
                    'block_reason': 'auto_detection',
                    'is_active': True,
                    'expires_at': timezone.now() + timedelta(days=7)
                }
            )
            if created:
                blocks_created += 1
        
        logger.info(f"Auto-blocked {blocks_created} IPs based on abuse reports")
        return blocks_created


class IPBlockListManager(models.Manager):
    """
    Custom manager for IPBlockList model.
    """
    
    def get_queryset(self):
        """Get base queryset with select_related optimizations."""
        return super().get_queryset().select_related('created_by')
    
    def active(self):
        """Get active IP blocks."""
        return self.get_queryset().filter(is_active=True)
    
    def inactive(self):
        """Get inactive IP blocks."""
        return self.get_queryset().filter(is_active=False)
    
    def expired(self):
        """Get expired IP blocks."""
        return self.get_queryset().filter(
            expires_at__lt=timezone.now()
        )
    
    def permanent(self):
        """Get permanent IP blocks (no expiry)."""
        return self.get_queryset().filter(expires_at__isnull=True)
    
    def by_reason(self, block_reason):
        """Get blocks by reason."""
        return self.get_queryset().filter(block_reason=block_reason)
    
    def by_type(self, block_type):
        """Get blocks by type."""
        return self.get_queryset().filter(block_type=block_type)
    
    def is_ip_blocked(self, ip_address):
        """Check if IP address is blocked."""
        return self.active().filter(ip_address=ip_address).exists()
    
    def get_block_info(self, ip_address):
        """Get block information for IP address."""
        try:
            return self.active().get(ip_address=ip_address)
        except self.model.DoesNotExist:
            return None
    
    def cleanup_expired(self):
        """Deactivate expired blocks."""
        expired_blocks = self.expired()
        count = expired_blocks.update(is_active=False)
        logger.info(f"Deactivated {count} expired IP blocks")
        return count
    
    def block_ip(self, ip_address, block_type='single', block_reason='manual', 
                 expires_at=None, created_by=None):
        """Block an IP address."""
        block, created = self.get_or_create(
            ip_address=ip_address,
            defaults={
                'block_type': block_type,
                'block_reason': block_reason,
                'is_active': True,
                'expires_at': expires_at,
                'created_by': created_by
            }
        )
        
        if created:
            logger.info(f"Blocked IP {ip_address} (reason: {block_reason})")
        else:
            # Reactivate existing block
            block.is_active = True
            block.block_reason = block_reason
            block.expires_at = expires_at
            block.save()
            logger.info(f"Reactivated block for IP {ip_address}")
        
        return block
    
    def unblock_ip(self, ip_address):
        """Unblock an IP address."""
        try:
            block = self.get(ip_address=ip_address)
            block.is_active = False
            block.save()
            logger.info(f"Unblocked IP {ip_address}")
            return True
        except self.model.DoesNotExist:
            return False
    
    def get_blocked_count(self):
        """Get count of active blocked IPs."""
        return self.active().count()
    
    def get_blocks_by_reason(self):
        """Get blocks grouped by reason."""
        return (
            self.active()
            .values('block_reason')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
    
    def get_recent_blocks(self, hours=24, limit=50):
        """Get recent IP blocks."""
        since_time = timezone.now() - timedelta(hours=hours)
        return self.get_queryset().filter(
            created_at__gte=since_time
        ).order_by('-created_at')[:limit]


class RateLimitInsightManager(models.Manager):
    """
    Custom manager for RateLimitInsight model.
    """
    
    def get_queryset(self):
        """Get base queryset."""
        return super().get_queryset()
    
    def for_date(self, date):
        """Get insights for specific date."""
        return self.get_queryset().filter(date=date)
    
    def for_date_range(self, start_date, end_date):
        """Get insights for date range."""
        return self.get_queryset().filter(
            date__gte=start_date,
            date__lte=end_date
        )
    
    def recent(self, days=7):
        """Get recent insights."""
        since_date = timezone.now().date() - timedelta(days=days)
        return self.get_queryset().filter(date__gte=since_date)
    
    def get_daily_summary(self, date=None):
        """Get daily summary for a specific date."""
        if date is None:
            date = timezone.now().date()
        
        try:
            return self.for_date(date).get()
        except self.model.DoesNotExist:
            return None
    
    def get_trend_data(self, days=30):
        """Get trend data for insights."""
        since_date = timezone.now().date() - timedelta(days=days)
        
        return (
            self.get_queryset()
            .filter(date__gte=since_date)
            .order_by('date')
            .values('date', 'total_requests', 'blocked_requests', 
                   'unique_ips', 'unique_users', 'avg_response_time')
        )
    
    def generate_insight(self, date):
        """Generate insight for a specific date."""
        from api.rate_limit.models import RateLimitLog
        
        # Calculate metrics for the date
        start_datetime = timezone.make_aware(datetime.combine(date, datetime.min.time()))
        end_datetime = timezone.make_aware(datetime.combine(date, datetime.max.time()))
        
        logs = RateLimitLog.objects.filter(
            timestamp__gte=start_datetime,
            timestamp__lte=end_datetime
        )
        
        total_requests = logs.count()
        blocked_requests = logs.filter(status='blocked').count()
        unique_ips = logs.values('ip_address').distinct().count()
        unique_users = logs.values('user').distinct().count()
        
        # Calculate average response time (if available)
        avg_response_time = logs.aggregate(
            avg_time=Avg('response_time')
        )['avg_time'] or 0
        
        insight, created = self.get_or_create(
            date=date,
            defaults={
                'total_requests': total_requests,
                'blocked_requests': blocked_requests,
                'unique_ips': unique_ips,
                'unique_users': unique_users,
                'avg_response_time': avg_response_time,
                'peak_hour': self._calculate_peak_hour(logs),
                'top_endpoints': self._get_top_endpoints(logs),
                'top_ips': self._get_top_ips(logs),
            }
        )
        
        if not created:
            # Update existing insight
            insight.total_requests = total_requests
            insight.blocked_requests = blocked_requests
            insight.unique_ips = unique_ips
            insight.unique_users = unique_users
            insight.avg_response_time = avg_response_time
            insight.peak_hour = self._calculate_peak_hour(logs)
            insight.top_endpoints = self._get_top_endpoints(logs)
            insight.top_ips = self._get_top_ips(logs)
            insight.save()
        
        return insight
    
    def _calculate_peak_hour(self, logs):
        """Calculate peak hour from logs."""
        hourly_counts = (
            logs.extra({'hour': "strftime('%%H', timestamp)"})
            .values('hour')
            .annotate(count=Count('id'))
            .order_by('-count')
            .first()
        )
        
        return hourly_counts['hour'] if hourly_counts else None
    
    def _get_top_endpoints(self, logs, limit=5):
        """Get top endpoints from logs."""
        return list(
            logs.values('endpoint')
            .annotate(count=Count('id'))
            .order_by('-count')[:limit]
            .values_list('endpoint', flat=True)
        )
    
    def _get_top_ips(self, logs, limit=5):
        """Get top IPs from logs."""
        return list(
            logs.values('ip_address')
            .annotate(count=Count('id'))
            .order_by('-count')[:limit]
            .values_list('ip_address', flat=True)
        )
