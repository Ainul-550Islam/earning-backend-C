"""
Selectors for alerts app - implements Query Object pattern
"""
from django.db import models
from django.db.models import Q, Count, Avg, F, Window
from django.utils import timezone
from datetime import timedelta
from typing import List, Dict, Any, Optional
import logging

from api.alerts.models import (
    AlertRule, AlertLog, Notification, SystemHealthCheck,
    AlertAnalytics, AlertChannel,
)

logger = logging.getLogger(__name__)


class AlertRuleSelector:
    """Selector for AlertRule queries"""
    
    def __init__(self, queryset=None):
        self.queryset = queryset or AlertRule.objects.all()
    
    def active(self):
        """Get active alert rules"""
        return self.queryset.filter(is_active=True)
    
    def by_severity(self, severity: str):
        """Filter by severity"""
        return self.queryset.filter(severity=severity)
    
    def by_type(self, alert_type: str):
        """Filter by alert type"""
        return self.queryset.filter(alert_type=alert_type)
    
    def by_user(self, user):
        """Filter by created by user"""
        return self.queryset.filter(created_by=user)
    
    def recently_triggered(self, days: int = 7):
        """Filter rules triggered within specified days"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.queryset.filter(last_triggered__gte=cutoff_date)
    
    def never_triggered(self):
        """Get rules that have never been triggered"""
        return self.queryset.filter(last_triggered__isnull=True)
    
    def with_alert_count(self):
        """Annotate with alert count"""
        return self.queryset.annotate(
            alert_count=Count('alertlog')
        )
    
    def search(self, query: str):
        """Search by name or description"""
        return self.queryset.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )
    
    def get_queryset(self):
        """Get the current queryset"""
        return self.queryset


class AlertLogSelector:
    """Selector for AlertLog queries"""
    
    def __init__(self, queryset=None):
        self.queryset = queryset or AlertLog.objects.all()
    
    def unresolved(self):
        """Get unresolved alerts"""
        return self.queryset.filter(is_resolved=False)
    
    def resolved(self):
        """Get resolved alerts"""
        return self.queryset.filter(is_resolved=True)
    
    def critical(self):
        """Get critical alerts"""
        return self.queryset.filter(rule__severity='critical')
    
    def by_severity(self, severity: str):
        """Filter by severity"""
        return self.queryset.filter(rule__severity=severity)
    
    def by_type(self, alert_type: str):
        """Filter by alert type"""
        return self.queryset.filter(rule__alert_type=alert_type)
    
    def by_rule(self, rule_id: int):
        """Filter by rule ID"""
        return self.queryset.filter(rule_id=rule_id)
    
    def by_user(self, user):
        """Filter by resolved by user"""
        return self.queryset.filter(resolved_by=user)
    
    def recent(self, hours: int = 24):
        """Get alerts within specified hours"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.queryset.filter(triggered_at__gte=cutoff_time)
    
    def escalated(self, level: Optional[int] = None):
        """Filter by escalation level"""
        if level is not None:
            return self.queryset.filter(escalation_level=level)
        return self.queryset.filter(escalation_level__gt=0)
    
    def with_resolution_time(self):
        """Annotate with resolution time"""
        return self.queryset.annotate(
            resolution_time=F('resolved_at') - F('triggered_at')
        )
    
    def search(self, query: str):
        """Search by message or rule name"""
        return self.queryset.filter(
            Q(message__icontains=query) |
            Q(rule__name__icontains=query) |
            Q(rule__description__icontains=query)
        )
    
    def get_queryset(self):
        """Get the current queryset"""
        return self.queryset


class NotificationSelector:
    """Selector for Notification queries"""
    
    def __init__(self, queryset=None):
        self.queryset = queryset or Notification.objects.all()
    
    def pending(self):
        """Get pending notifications"""
        return self.queryset.filter(status='pending')
    
    def sent(self):
        """Get sent notifications"""
        return self.queryset.filter(status='sent')
    
    def failed(self):
        """Get failed notifications"""
        return self.queryset.filter(status='failed')
    
    def by_type(self, notification_type: str):
        """Filter by notification type"""
        return self.queryset.filter(notification_type=notification_type)
    
    def by_recipient(self, recipient: str):
        """Filter by recipient"""
        return self.queryset.filter(recipient=recipient)
    
    def by_alert(self, alert_id: int):
        """Filter by alert ID"""
        return self.queryset.filter(alert_log_id=alert_id)
    
    def recent(self, hours: int = 24):
        """Get notifications within specified hours"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.queryset.filter(created_at__gte=cutoff_time)
    
    def retryable(self):
        """Get notifications that can be retried"""
        return self.queryset.filter(
            status='failed',
            retry_count__lt=models.F('max_retries')
        )
    
    def overdue(self):
        """Get overdue notifications"""
        from django.utils import timezone
        return self.queryset.filter(
            status='pending',
            created_at__lt=timezone.now() - timezone.timedelta(minutes=30)
        )
    
    def get_queryset(self):
        """Get the current queryset"""
        return self.queryset


class SystemHealthSelector:
    """Selector for SystemHealthCheck queries"""
    
    def __init__(self, queryset=None):
        self.queryset = queryset or SystemHealthCheck.objects.all()
    
    def active(self):
        """Get active health checks"""
        return self.queryset.filter(is_active=True)
    
    def by_status(self, status: str):
        """Filter by status"""
        return self.queryset.filter(status=status)
    
    def by_type(self, check_type: str):
        """Filter by check type"""
        return self.queryset.filter(check_type=check_type)
    
    def recent(self, hours: int = 24):
        """Get health checks within specified hours"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.queryset.filter(checked_at__gte=cutoff_time)
    
    def failing(self):
        """Get only failing health checks"""
        return self.queryset.filter(
            status__in=['unhealthy', 'degraded']
        )
    
    def healthy(self):
        """Get only healthy health checks"""
        return self.queryset.filter(status='healthy')
    
    def with_response_time_stats(self):
        """Annotate with response time statistics"""
        return self.queryset.annotate(
            avg_response_time=Avg('response_time_ms'),
            max_response_time=models.Max('response_time_ms'),
            min_response_time=models.Min('response_time_ms')
        )
    
    def get_queryset(self):
        """Get the current queryset"""
        return self.queryset


class AlertAnalyticsSelector:
    """Selector for AlertAnalytics queries"""
    
    def __init__(self, queryset=None):
        self.queryset = queryset or AlertAnalytics.objects.all()
    
    def by_date_range(self, start_date, end_date):
        """Filter by date range"""
        return self.queryset.filter(
            date__gte=start_date,
            date__lte=end_date
        )
    
    def recent(self, days: int = 30):
        """Get analytics within specified days"""
        cutoff_date = timezone.now().date() - timedelta(days=days)
        return self.queryset.filter(date__gte=cutoff_date)
    
    def by_metric(self, metric_name: str):
        """Filter by metric name"""
        return self.queryset.filter(metric_name=metric_name)
    
    def with_trends(self):
        """Annotate with trend calculations"""
        return self.queryset.annotate(
            prev_value=Window(
                expression=models.F('value'),
                partition_by=['metric_name'],
                order_by=models.F('date').asc(),
                frame=1
            ),
            trend_change=models.F('value') - Window(
                expression=models.F('value'),
                partition_by=['metric_name'],
                order_by=models.F('date').asc(),
                frame=1
            )
        )
    
    def get_queryset(self):
        """Get the current queryset"""
        return self.queryset


class NotificationChannelSelector:
    """Selector for AlertChannel queries"""
    
    def __init__(self, queryset=None):
        self.queryset = queryset or AlertChannel.objects.all()
    
    def enabled(self):
        """Get enabled channels"""
        return self.queryset.filter(is_enabled=True)
    
    def by_type(self, channel_type: str):
        """Filter by channel type"""
        return self.queryset.filter(channel_type=channel_type)
    
    def by_priority(self, priority: str):
        """Filter by priority"""
        return self.queryset.filter(priority=priority)
    
    def healthy(self):
        """Get channels with successful recent deliveries"""
        from django.utils import timezone
        cutoff_time = timezone.now() - timedelta(hours=1)
        
        return self.queryset.filter(
            notifications__status='sent',
            notifications__sent_at__gte=cutoff_time
        ).distinct()
    
    def failing(self):
        """Get channels with recent failures"""
        from django.utils import timezone
        cutoff_time = timezone.now() - timedelta(hours=1)
        
        return self.queryset.filter(
            notifications__status='failed',
            notifications__created_at__gte=cutoff_time
        ).distinct()
    
    def get_queryset(self):
        """Get the current queryset"""
        return self.queryset


# Utility functions for selectors
def create_alert_rule_selector(filters: Dict[str, Any] = None) -> AlertRuleSelector:
    """Create AlertRuleSelector with optional filters"""
    queryset = AlertRule.objects.all()
    
    if filters:
        if 'is_active' in filters:
            queryset = queryset.filter(is_active=filters['is_active'])
        if 'severity' in filters:
            queryset = queryset.filter(severity=filters['severity'])
        if 'alert_type' in filters:
            queryset = queryset.filter(alert_type=filters['alert_type'])
        if 'created_by' in filters:
            queryset = queryset.filter(created_by=filters['created_by'])
    
    return AlertRuleSelector(queryset)


def create_alert_log_selector(filters: Dict[str, Any] = None) -> AlertLogSelector:
    """Create AlertLogSelector with optional filters"""
    queryset = AlertLog.objects.select_related('rule', 'resolved_by').all()
    
    if filters:
        if 'is_resolved' in filters:
            queryset = queryset.filter(is_resolved=filters['is_resolved'])
        if 'severity' in filters:
            queryset = queryset.filter(rule__severity=filters['severity'])
        if 'rule_id' in filters:
            queryset = queryset.filter(rule_id=filters['rule_id'])
        if 'resolved_by' in filters:
            queryset = queryset.filter(resolved_by=filters['resolved_by'])
        if 'start_date' in filters:
            queryset = queryset.filter(triggered_at__gte=filters['start_date'])
        if 'end_date' in filters:
            queryset = queryset.filter(triggered_at__lte=filters['end_date'])
    
    return AlertLogSelector(queryset)


def create_notification_selector(filters: Dict[str, Any] = None) -> NotificationSelector:
    """Create NotificationSelector with optional filters"""
    queryset = Notification.objects.select_related('alert_log').all()
    
    if filters:
        if 'status' in filters:
            queryset = queryset.filter(status=filters['status'])
        if 'notification_type' in filters:
            queryset = queryset.filter(notification_type=filters['notification_type'])
        if 'recipient' in filters:
            queryset = queryset.filter(recipient=filters['recipient'])
        if 'alert_log_id' in filters:
            queryset = queryset.filter(alert_log_id=filters['alert_log_id'])
    
    return NotificationSelector(queryset)


# Complex selectors for advanced queries
class AlertAggregationSelector:
    """Selector for aggregated alert data"""
    
    def __init__(self, queryset=None):
        self.queryset = queryset or AlertLog.objects.all()
    
    def by_day(self, days: int = 7):
        """Aggregate alerts by day"""
        from django.utils import timezone
        cutoff_date = timezone.now() - timedelta(days=days)
        
        return self.queryset.filter(
            triggered_at__gte=cutoff_date
        ).extra(
            {'day': "date(triggered_at)"}
        ).values('day').annotate(
            count=Count('id'),
            resolved=Count('id', filter=Q(is_resolved=True))
        ).order_by('day')
    
    def by_severity(self):
        """Aggregate alerts by severity"""
        return self.queryset.values('rule__severity').annotate(
            count=Count('id'),
            resolved=Count('id', filter=Q(is_resolved=True))
        ).order_by('rule__severity')
    
    def by_type(self):
        """Aggregate alerts by type"""
        return self.queryset.values('rule__alert_type').annotate(
            count=Count('id'),
            resolved=Count('id', filter=Q(is_resolved=True))
        ).order_by('-count')
    
    def by_rule(self, limit: int = 10):
        """Aggregate alerts by rule"""
        return self.queryset.values('rule__name', 'rule__id').annotate(
            count=Count('id'),
            last_triggered=models.Max('triggered_at'),
            avg_resolution_time=Avg(
                models.F('resolved_at') - models.F('triggered_at')
            )
        ).order_by('-count')[:limit]
    
    def get_queryset(self):
        """Get the current queryset"""
        return self.queryset


# Selector factory
class SelectorFactory:
    """Factory for creating selectors"""
    
    @staticmethod
    def create_selector(selector_type: str, **kwargs):
        """Create selector by type"""
        selectors = {
            'alert_rule': AlertRuleSelector,
            'alert_log': AlertLogSelector,
            'notification': NotificationSelector,
            'system_health': SystemHealthSelector,
            'alert_analytics': AlertAnalyticsSelector,
            'notification_channel': NotificationChannelSelector,
            'alert_aggregation': AlertAggregationSelector
        }
        
        selector_class = selectors.get(selector_type)
        if not selector_class:
            raise ValueError(f"Unknown selector type: {selector_type}")
        
        return selector_class(**kwargs)
    
    @staticmethod
    def get_available_selectors():
        """Get list of available selectors"""
        return [
            'alert_rule',
            'alert_log',
            'notification',
            'system_health',
            'alert_analytics',
            'notification_channel',
            'alert_aggregation'
        ]
