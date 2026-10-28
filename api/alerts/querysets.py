"""
Custom QuerySets for alerts app
"""
from django.db import models
from django.db.models import Q, Count, Avg, Sum, F, Window, Prefetch
from django.utils import timezone
from datetime import timedelta
from typing import Optional, List


class AlertRuleQuerySet(models.QuerySet):
    """Custom QuerySet for AlertRule model"""
    
    def active(self):
        """Get only active alert rules"""
        return self.filter(is_active=True)
    
    def inactive(self):
        """Get only inactive alert rules"""
        return self.filter(is_active=False)
    
    def by_severity(self, severity: str):
        """Filter by severity level"""
        return self.filter(severity=severity)
    
    def by_type(self, alert_type: str):
        """Filter by alert type"""
        return self.filter(alert_type=alert_type)
    
    def by_user(self, user):
        """Filter by created by user"""
        return self.filter(created_by=user)
    
    def recently_triggered(self, days: int = 7):
        """Get rules triggered within specified days"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(last_triggered__gte=cutoff_date)
    
    def never_triggered(self):
        """Get rules that have never been triggered"""
        return self.filter(last_triggered__isnull=True)
    
    def with_alert_count(self):
        """Annotate with alert count"""
        return self.annotate(
            alert_count=Count('alertlog')
        )
    
    def with_last_triggered(self):
        """Annotate with last triggered time"""
        return self.annotate(
            last_triggered=models.Max('alertlog__triggered_at')
        )
    
    def search(self, query: str):
        """Search by name or description"""
        return self.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )
    
    def for_tenant(self, tenant):
        """Filter by tenant"""
        return self.filter(tenant=tenant)

    def high_severity(self):
        """Get high and critical severity rules"""
        return self.filter(severity__in=['high', 'critical'])

    def needs_attention(self):
        """Get rules that haven't triggered recently but should be monitored"""
        return self.filter(
            is_active=True,
            last_triggered__lt=timezone.now() - timedelta(hours=24)
        )

    def with_recent_alerts(self, hours=24):
        """Prefetch recent alerts to avoid N+1 queries"""
        from api.alerts.models.core import AlertLog
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.prefetch_related(
            Prefetch(
                'logs',
                queryset=AlertLog.objects.filter(
                    triggered_at__gte=cutoff
                ).order_by('-triggered_at')[:10],
                to_attr='recent_alerts'
            )
        )

    def bulk_update_status(self, is_active=True):
        """Bulk update rule status"""
        return self.update(is_active=is_active)


class AlertLogQuerySet(models.QuerySet):
    """Custom QuerySet for AlertLog model"""
    
    def unresolved(self):
        """Get only unresolved alerts"""
        return self.filter(is_resolved=False)
    
    def resolved(self):
        """Get only resolved alerts"""
        return self.filter(is_resolved=True)
    
    def acknowledged(self):
        """Get only acknowledged alerts"""
        return self.filter(acknowledged_at__isnull=False)
    
    def unacknowledged(self):
        """Get only unacknowledged alerts"""
        return self.filter(acknowledged_at__isnull=True)
    
    def by_severity(self, severity: str):
        """Filter by severity level"""
        return self.filter(rule__severity=severity)
    
    def by_type(self, alert_type: str):
        """Filter by alert type"""
        return self.filter(rule__alert_type=alert_type)
    
    def by_rule(self, rule_id: int):
        """Filter by rule ID"""
        return self.filter(rule_id=rule_id)
    
    def by_user(self, user):
        """Filter by resolved by user"""
        return self.filter(resolved_by=user)
    
    def recent(self, hours: int = 24):
        """Get alerts within specified hours"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.filter(triggered_at__gte=cutoff_time)
    
    def critical(self):
        """Get only critical alerts"""
        return self.filter(rule__severity='critical')
    
    def high_priority(self):
        """Get high priority alerts (critical and high)"""
        return self.filter(rule__severity__in=['critical', 'high'])
    
    def escalated(self, level: Optional[int] = None):
        """Filter by escalation level"""
        if level is not None:
            return self.filter(escalation_level=level)
        return self.filter(escalation_level__gt=0)
    
    def with_resolution_time(self):
        """Annotate with resolution time"""
        return self.annotate(
            resolution_time=F('resolved_at') - F('triggered_at')
        )
    
    def with_age_minutes(self):
        """Annotate with age in minutes"""
        return self.annotate(
            age_minutes=models.ExpressionWrapper(
                (timezone.now() - F('triggered_at')).total_seconds() / 60,
                output_field=models.FloatField()
            )
        )
    
    def search(self, query: str):
        """Search by message or rule name"""
        return self.filter(
            Q(message__icontains=query) |
            Q(rule__name__icontains=query) |
            Q(rule__description__icontains=query)
        )
    
    def for_tenant(self, tenant):
        """Filter by tenant"""
        return self.filter(tenant=tenant)
    
    def in_time_range(self, start_date, end_date):
        """Filter by time range"""
        return self.filter(
            triggered_at__gte=start_date,
            triggered_at__lte=end_date
        )
    
    def by_recipient(self, recipient: str):
        """Filter by notification recipient"""
        return self.filter(
            notifications__recipient=recipient
        ).distinct()
    
    def failed_notifications(self):
        """Get alerts with failed notifications"""
        return self.filter(
            notifications__status='failed'
        ).distinct()

    def needs_escalation(self):
        """Get alerts that need escalation"""
        return self.filter(
            is_resolved=False,
            triggered_at__lt=timezone.now() - timedelta(minutes=30)
        )

    def with_performance_data(self):
        """Include performance metrics"""
        return self.select_related('rule').annotate(
            time_since_trigger=models.ExpressionWrapper(
                timezone.now() - F('triggered_at'),
                output_field=models.DurationField()
            )
        )

    def bulk_resolve(self, resolved_by=None, note=""):
        """Bulk resolve alerts"""
        return self.update(
            is_resolved=True,
            resolved_at=timezone.now(),
            resolved_by=resolved_by,
            resolution_note=note
        )


class NotificationQuerySet(models.QuerySet):
    """Custom QuerySet for Notification model"""
    
    def pending(self):
        """Get only pending notifications"""
        return self.filter(status='pending')
    
    def sent(self):
        """Get only sent notifications"""
        return self.filter(status='sent')
    
    def failed(self):
        """Get only failed notifications"""
        return self.filter(status='failed')
    
    def delivered(self):
        """Get only delivered notifications"""
        return self.filter(status='delivered')
    
    def by_type(self, notification_type: str):
        """Filter by notification type"""
        return self.filter(notification_type=notification_type)
    
    def by_recipient(self, recipient: str):
        """Filter by recipient"""
        return self.filter(recipient=recipient)
    
    def by_alert(self, alert_id: int):
        """Filter by alert ID"""
        return self.filter(alert_log_id=alert_id)
    
    def recent(self, hours: int = 24):
        """Get notifications within specified hours"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.filter(created_at__gte=cutoff_time)
    
    def retryable(self):
        """Get notifications that can be retried"""
        return self.filter(
            status='failed',
            retry_count__lt=models.F('max_retries')
        )
    
    def overdue(self):
        """Get overdue notifications"""
        from django.utils import timezone
        return self.filter(
            status='pending',
            created_at__lt=timezone.now() - timezone.timedelta(minutes=30)
        )
    
    def with_retry_count(self):
        """Annotate with retry count"""
        return self.annotate(
            retry_count=models.Count('id')  # This would need proper implementation
        )
    
    def by_priority(self):
        """Order by priority (based on alert severity and age)"""
        return self.annotate(
            alert_severity=models.F('alert_log__rule__severity'),
            alert_age=timezone.now() - models.F('alert_log__triggered_at')
        ).order_by(
            models.Case(
                models.When(alert_severity='critical', then=0),
                models.When(alert_severity='high', then=1),
                models.When(alert_severity='medium', then=2),
                models.When(alert_severity='low', then=3),
                default=4
            ),
            'alert_age'
        )
    
    def for_tenant(self, tenant):
        """Filter by tenant"""
        return self.filter(tenant=tenant)


class AlertEscalationQuerySet(models.QuerySet):
    """Custom QuerySet for AlertEscalation model"""
    
    def active(self):
        """Get only active escalations"""
        return self.filter(is_active=True)
    
    def by_level(self, level: int):
        """Filter by escalation level"""
        return self.filter(level=level)
    
    def by_rule(self, rule_id: int):
        """Filter by rule ID"""
        return self.filter(rule_id=rule_id)
    
    def auto_escalate(self):
        """Get escalations with auto-escalate enabled"""
        return self.filter(auto_escalate=True)
    
    def due_for_escalation(self):
        """Get escalations that should trigger"""
        return self.filter(
            is_active=True,
            auto_escalate=True
        ).annotate(
            alert_age=timezone.now() - models.F('alertlog__triggered_at')
        ).filter(
            alert_age__gte=models.F('delay_minutes')
        )
    
    def for_tenant(self, tenant):
        """Filter by tenant"""
        return self.filter(tenant=tenant)


class AlertScheduleQuerySet(models.QuerySet):
    """Custom QuerySet for AlertSchedule model"""
    
    def active(self):
        """Get only active schedules"""
        return self.filter(is_active=True)
    
    def current(self):
        """Get schedules currently active"""
        now = timezone.now()
        return self.filter(
            is_active=True,
            start_time__lte=now.time(),
            end_time__gte=now.time(),
            days_of_week__contains=[now.weekday()]
        )
    
    def by_day(self, day: int):
        """Filter by day of week"""
        return self.filter(days_of_week__contains=[day])
    
    def by_time_range(self, start_time, end_time):
        """Filter by time range"""
        return self.filter(
            start_time__gte=start_time,
            end_time__lte=end_time
        )
    
    def for_tenant(self, tenant):
        """Filter by tenant"""
        return self.filter(tenant=tenant)


class SystemHealthCheckQuerySet(models.QuerySet):
    """Custom QuerySet for SystemHealthCheck model"""
    
    def active(self):
        """Get only active health checks"""
        return self.filter(is_active=True)
    
    def by_status(self, status: str):
        """Filter by status"""
        return self.filter(status=status)
    
    def by_type(self, check_type: str):
        """Filter by check type"""
        return self.filter(check_type=check_type)
    
    def recent(self, hours: int = 24):
        """Get health checks within specified hours"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.filter(last_checked__gte=cutoff_time)
    
    def failing(self):
        """Get only failing health checks"""
        return self.filter(
            status__in=['critical', 'warning', 'offline']
        )
    
    def healthy(self):
        """Get only healthy health checks"""
        return self.filter(status='healthy')
    
    def with_response_time_stats(self):
        """Annotate with response time statistics"""
        return self.annotate(
            avg_response_time=Avg('response_time_ms'),
            max_response_time=models.Max('response_time_ms'),
            min_response_time=models.Min('response_time_ms')
        )
    
    def for_tenant(self, tenant):
        """Filter by tenant"""
        return self.filter(tenant=tenant)


class AlertAnalyticsQuerySet(models.QuerySet):
    """Custom QuerySet for AlertAnalytics model"""
    
    def by_date_range(self, start_date, end_date):
        """Filter by date range"""
        return self.filter(
            date__gte=start_date,
            date__lte=end_date
        )
    
    def recent(self, days: int = 30):
        """Get analytics within specified days"""
        cutoff_date = timezone.now().date() - timedelta(days=days)
        return self.filter(date__gte=cutoff_date)
    
    def by_metric(self, metric_name: str):
        """Filter by metric name"""
        return self.filter(metric_name=metric_name)
    
    def with_trends(self):
        """Annotate with trend calculations"""
        return self.annotate(
            prev_value=Window(
                expression=models.F('value'),
                partition_by=[],
                order_by=models.F('date').asc(),
                frame=1
            ),
            trend_change=models.F('value') - Window(
                expression=models.F('value'),
                partition_by=[],
                order_by=models.F('date').asc(),
                frame=1
            )
        )
    
    def for_tenant(self, tenant):
        """Filter by tenant"""
        return self.filter(tenant=tenant)


# Custom managers
class AlertRuleManager(models.Manager):
    """Custom manager for AlertRule model"""
    
    def get_queryset(self):
        return AlertRuleQuerySet(self.model, using=self._db)
    
    def active_rules(self):
        """Get all active rules"""
        return self.get_queryset().active()
    
    def rules_by_severity(self, severity: str):
        """Get rules by severity"""
        return self.get_queryset().by_severity(severity)
    
    def search_rules(self, query: str):
        """Search rules"""
        return self.get_queryset().search(query)
    
    def rules_with_stats(self):
        """Get rules with alert statistics"""
        return self.get_queryset().with_alert_count().with_last_triggered()


class AlertLogManager(models.Manager):
    """Custom manager for AlertLog model"""
    
    def get_queryset(self):
        return AlertLogQuerySet(self.model, using=self._db)
    
    def unresolved_alerts(self):
        """Get all unresolved alerts"""
        return self.get_queryset().unresolved()
    
    def critical_alerts(self):
        """Get all critical alerts"""
        return self.get_queryset().critical()
    
    def recent_alerts(self, hours: int = 24):
        """Get recent alerts"""
        return self.get_queryset().recent(hours)
    
    def alerts_by_severity(self, severity: str):
        """Get alerts by severity"""
        return self.get_queryset().by_severity(severity)
    
    def search_alerts(self, query: str):
        """Search alerts"""
        return self.get_queryset().search(query)


class NotificationManager(models.Manager):
    """Custom manager for Notification model"""
    
    def get_queryset(self):
        return NotificationQuerySet(self.model, using=self._db)
    
    def pending_notifications(self):
        """Get all pending notifications"""
        return self.get_queryset().pending()
    
    def failed_notifications(self):
        """Get all failed notifications"""
        return self.get_queryset().failed()
    
    def notifications_by_type(self, notification_type: str):
        """Get notifications by type"""
        return self.get_queryset().by_type(notification_type)
    
    def overdue_notifications(self):
        """Get overdue notifications"""
        return self.get_queryset().overdue()


class SystemHealthCheckManager(models.Manager):
    """Custom manager for SystemHealthCheck model"""
    
    def get_queryset(self):
        return SystemHealthCheckQuerySet(self.model, using=self._db)
    
    def active_checks(self):
        """Get all active health checks"""
        return self.get_queryset().active()
    
    def failing_checks(self):
        """Get all failing health checks"""
        return self.get_queryset().failing()
    
    def checks_by_type(self, check_type: str):
        """Get health checks by type"""
        return self.get_queryset().by_type(check_type)
    
    def recent_checks(self, hours: int = 24):
        """Get recent health checks"""
        return self.get_queryset().recent(hours)


# Utility functions for QuerySets
def get_alert_statistics(queryset, days: int = 7):
    """Get statistics for alert queryset"""
    cutoff_date = timezone.now() - timedelta(days=days)
    recent_alerts = queryset.filter(triggered_at__gte=cutoff_date)
    
    return {
        'total': queryset.count(),
        'recent': recent_alerts.count(),
        'resolved': recent_alerts.filter(is_resolved=True).count(),
        'unresolved': recent_alerts.filter(is_resolved=False).count(),
        'by_severity': dict(
            recent_alerts.values('rule__severity').annotate(
                count=Count('id')
            ).values_list('rule__severity', 'count')
        )
    }


def get_resolution_metrics(queryset):
    """Get resolution metrics for alert queryset"""
    resolved_alerts = queryset.filter(
        is_resolved=True,
        resolved_at__isnull=False
    )
    
    if not resolved_alerts.exists():
        return {
            'mttr': 0,
            'resolution_rate': 0,
            'avg_resolution_time': 0
        }
    
    # Calculate MTTR (Mean Time To Resolution)
    resolution_times = [
        (alert.resolved_at - alert.triggered_at).total_seconds() / 60
        for alert in resolved_alerts
    ]
    
    mttr = sum(resolution_times) / len(resolution_times)
    
    # Calculate resolution rate
    total_alerts = queryset.count()
    resolution_rate = (len(resolved_alerts) / total_alerts) * 100
    
    return {
        'mttr': round(mttr, 2),
        'resolution_rate': round(resolution_rate, 2),
        'avg_resolution_time': round(mttr, 2),
        'resolved_count': len(resolved_alerts),
        'total_count': total_alerts
    }


def get_alert_trends(queryset, days: int = 30):
    """Get alert trends over time"""
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    alerts_in_period = queryset.filter(
        triggered_at__gte=start_date,
        triggered_at__lte=end_date
    )
    
    # Group by day
    daily_counts = alerts_in_period.extra(
        {'day': "date(triggered_at)"}
    ).values('day').annotate(
        count=Count('id'),
        resolved=Count('id', filter=Q(is_resolved=True))
    ).order_by('day')
    
    return list(daily_counts)
