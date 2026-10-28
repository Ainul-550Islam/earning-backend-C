# ALERTS MODULE - TEST FIXTURES & FACTORIES
# File: alerts/tests/factories.py

from factory import django, Faker, SubFactory, post_generation, Sequence
from factory.django import DjangoModelFactory
from django.utils import timezone
from datetime import timedelta, timezone as dt_timezone

from api.alerts.models import (
    AlertRule, AlertLog, AlertChannel, Notification,
    AlertSuppression, AlertSchedule, AlertEscalation,
    AlertGroup, AlertAnalytics, SystemHealthCheck,
    Incident, AlertCorrelation, AlertDashboardConfig
)


class AlertRuleFactory(DjangoModelFactory):
    """Factory for AlertRule model"""
    
    class Meta:
        model = AlertRule
    
    name = Sequence(lambda n: f'rule_{n}')
    description = Faker('sentence')
    is_active = True
    alert_type = 'server_error'
    threshold_value = 100.0
    severity = 'high'
    created_at = Faker('date_time', tzinfo=dt_timezone.utc)
    updated_at = Faker('date_time', tzinfo=dt_timezone.utc)


class AlertChannelFactory(DjangoModelFactory):
    """Factory for AlertChannel model"""
    
    class Meta:
        model = AlertChannel
    
    name = Sequence(lambda n: f'channel_{n}')
    channel_type = 'email'
    is_enabled = True
    config = {'email': 'test@example.com'}
    created_at = Faker('date_time', tzinfo=dt_timezone.utc)


class AlertLogFactory(DjangoModelFactory):
    """Factory for AlertLog model"""
    
    class Meta:
        model = AlertLog
    
    rule = SubFactory(AlertRuleFactory)
    status = 'pending'
    severity = 'high'
    message = Faker('sentence')
    trigger_value = 100.0
    threshold_value = 90.0
    triggered_at = Faker('date_time', tzinfo=dt_timezone.utc)
    
    @post_generation
    def set_resolved_time(obj, create, extracted, **kwargs):
        """Set resolved time if status is resolved"""
        if create and obj.status == 'resolved':
            obj.resolved_at = obj.triggered_at + timedelta(minutes=30)
            obj.save()


class AlertNotificationFactory(DjangoModelFactory):
    """Factory for Notification model"""
    
    class Meta:
        model = Notification
    
    alert_log = SubFactory(AlertLogFactory)
    recipient = Faker('email')
    notification_type = 'alert'
    status = 'pending'
    created_at = Faker('date_time', tzinfo=dt_timezone.utc)


class AlertSuppressionFactory(DjangoModelFactory):
    """Factory for AlertSuppression model"""
    
    class Meta:
        model = AlertSuppression
    
    name = Sequence(lambda n: f'suppression_{n}')
    suppression_type = 'rule'
    rule = SubFactory(AlertRuleFactory)
    is_active = True
    start_time = Faker('date_time', tzinfo=dt_timezone.utc)
    end_time = Faker('date_time', tzinfo=dt_timezone.utc)
    description = Faker('sentence')


class AlertScheduleFactory(DjangoModelFactory):
    """Factory for AlertSchedule model"""
    
    class Meta:
        model = AlertSchedule
    
    rule = SubFactory(AlertRuleFactory)
    name = Faker('word')
    start_time = '09:00'
    end_time = '17:00'
    is_active = True
    timezone = 'UTC'


class AlertEscalationFactory(DjangoModelFactory):
    """Factory for AlertEscalation model"""
    
    class Meta:
        model = AlertEscalation
    
    rule = SubFactory(AlertRuleFactory)
    name = Faker('word')
    level = 1
    delay_minutes = 5
    escalate_to_email = 'user@example.com'


class AlertGroupFactory(DjangoModelFactory):
    """Factory for AlertGroup model"""
    
    class Meta:
        model = AlertGroup
    
    name = Sequence(lambda n: f'group_{n}')
    description = Faker('sentence')
    is_active = True
    cached_alert_count = 0


class AlertAnalyticsFactory(DjangoModelFactory):
    """Factory for AlertAnalytics model"""
    
    class Meta:
        model = AlertAnalytics
    
    date = Faker('date')
    total_alerts = Faker('random_int', min=1, max=100)
    resolved_alerts = Faker('random_int', min=0, max=50)
    escalated_alerts = Faker('random_int', min=0, max=20)


class SystemHealthCheckFactory(DjangoModelFactory):
    """Factory for SystemHealthCheck model"""
    
    class Meta:
        model = SystemHealthCheck
    
    check_name = Sequence(lambda n: f'health_check_{n}')
    check_type = 'api'
    status = 'healthy'
    status_message = 'database: healthy, processing: healthy, notifications: healthy'
    created_at = Faker('date_time', tzinfo=dt_timezone.utc)


class IncidentFactory(DjangoModelFactory):
    """Factory for Incident model"""
    
    class Meta:
        model = Incident
    
    title = Faker('sentence')
    description = Faker('paragraph')
    severity = 'high'
    status = 'open'
    created_at = Faker('date_time', tzinfo=dt_timezone.utc)


class AlertCorrelationFactory(DjangoModelFactory):
    """Factory for AlertCorrelation model"""
    
    class Meta:
        model = AlertCorrelation
    
    alert1 = SubFactory(AlertLogFactory)
    alert2 = SubFactory(AlertLogFactory)
    correlation_score = Faker('pyfloat', min_value=0, max_value=1)
    correlation_type = 'rule_based'


class AlertDashboardConfigFactory(DjangoModelFactory):
    """Factory for AlertDashboardConfig model"""
    
    class Meta:
        model = AlertDashboardConfig
    
    user_id = Faker('random_int', min=1, max=1000)
    visible_severities = ['high', 'critical']
    visible_alert_types = ['rule_based', 'anomaly']
    is_default = False


# Batch factories for creating multiple related objects

def create_alert_scenario(rule_count=5, alert_per_rule=10):
    """
    Create a complete alert scenario with rules, channels, alerts, and notifications
    
    Args:
        rule_count: Number of alert rules to create
        alert_per_rule: Number of alerts per rule
        
    Returns:
        dict with all created objects
    """
    rules = AlertRuleFactory.create_batch(rule_count)
    channels = AlertChannelFactory.create_batch(3)
    
    # Create alerts for each rule
    alerts = []
    for rule in rules:
        rule_alerts = AlertLogFactory.create_batch(
            alert_per_rule,
            rule=rule
        )
        alerts.extend(rule_alerts)
    
    # Create notifications for alerts
    notifications = []
    for alert in alerts:
        notif = AlertNotificationFactory.create(alert_log=alert)
        notifications.append(notif)
    
    return {
        'rules': rules,
        'channels': channels,
        'alerts': alerts,
        'notifications': notifications
    }


def create_health_check_history(days=7):
    """
    Create a history of system health checks
    
    Args:
        days: Number of days of history to create
        
    Returns:
        list of SystemHealthCheck objects
    """
    checks = []
    base_time = timezone.now()
    
    for i in range(days * 24):  # Hourly checks
        check_time = base_time - timedelta(hours=i)
        check = SystemHealthCheckFactory.create(
            created_at=check_time,
            status='healthy' if i % 5 != 0 else 'degraded'
        )
        checks.append(check)
    
    return checks


def create_analytics_history(days=30):
    """
    Create analytics history for a month
    
    Args:
        days: Number of days
        
    Returns:
        list of AlertAnalytics objects
    """
    analytics = []
    base_date = timezone.now().date()
    
    for i in range(days):
        analytics_date = base_date - timedelta(days=i)
        analytic = AlertAnalyticsFactory.create(
            date=analytics_date
        )
        analytics.append(analytic)
    
    return analytics


# Cleanup functions

def cleanup_all_alerts():
    """Delete all alert-related test data"""
    AlertLog.objects.all().delete()
    AlertRule.objects.all().delete()
    Notification.objects.all().delete()


def cleanup_all_health():
    """Delete all health check test data"""
    SystemHealthCheck.objects.all().delete()


def cleanup_all():
    """Delete all test data"""
    cleanup_all_alerts()
    cleanup_all_health()
    AlertChannel.objects.all().delete()
    AlertGroup.objects.all().delete()
    AlertAnalytics.objects.all().delete()
    Incident.objects.all().delete()


__all__ = [
    'AlertRuleFactory',
    'AlertChannelFactory',
    'AlertLogFactory',
    'AlertNotificationFactory',
    'AlertSuppressionFactory',
    'AlertScheduleFactory',
    'AlertEscalationFactory',
    'AlertGroupFactory',
    'AlertAnalyticsFactory',
    'SystemHealthCheckFactory',
    'IncidentFactory',
    'AlertCorrelationFactory',
    'AlertDashboardConfigFactory',
    'create_alert_scenario',
    'create_health_check_history',
    'create_analytics_history',
    'cleanup_all_alerts',
    'cleanup_all_health',
    'cleanup_all',
]
