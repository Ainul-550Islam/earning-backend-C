"""tests/test_comprehensive.py — fixed version"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class ComprehensiveAlertTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='comp_test', email='comp@test.com', password='pass')
        from api.alerts.models.core import AlertRule
        self.rule = AlertRule.objects.create(
            name='Comprehensive Rule', alert_type='server_error', severity='high',
            threshold_value=80.0, time_window_minutes=60, cooldown_minutes=30,
            created_by=self.user)

    def test_complete_alert_lifecycle(self):
        from api.alerts.models.core import AlertLog, Notification
        # 1. Create alert
        log = AlertLog.objects.create(
            rule=self.rule, trigger_value=90.0, threshold_value=80.0,
            message='Critical alert fired', is_resolved=False)
        self.assertFalse(log.is_resolved)
        # 2. Create notification
        notif = Notification.objects.create(
            alert_log=log, notification_type='email',
            status='pending', recipient='ops@test.com',
            message='Alert fired')
        self.assertEqual(notif.status, 'pending')
        # 3. Send notification
        notif.status = 'sent'
        notif.save()
        self.assertEqual(Notification.objects.get(pk=notif.pk).status, 'sent')
        # 4. Resolve alert
        log.is_resolved = True
        log.resolved_at = timezone.now()
        log.save()
        self.assertTrue(AlertLog.objects.get(pk=log.pk).is_resolved)

    def test_bulk_operations(self):
        from api.alerts.models.core import AlertLog
        for i in range(10):
            AlertLog.objects.create(
                rule=self.rule, trigger_value=85.0 + i,
                threshold_value=80.0, message=f'Bulk alert {i}', is_resolved=False)
        count = AlertLog.objects.filter(is_resolved=False).count()
        self.assertGreaterEqual(count, 10)
        AlertLog.objects.filter(rule=self.rule, is_resolved=False).update(is_resolved=True)
        remaining = AlertLog.objects.filter(rule=self.rule, is_resolved=False).count()
        self.assertEqual(remaining, 0)

    def test_threshold_alert_flow(self):
        from api.alerts.models.threshold import ThresholdConfig, ThresholdBreach
        config = ThresholdConfig.objects.create(
            name='Comp Threshold', alert_rule=self.rule,
            threshold_type='static', primary_threshold=80.0,
            comparison_operator='gt', is_active=True)
        breach = ThresholdBreach.objects.create(
            threshold_config=config, breach_value=95.0,
            threshold_value=80.0, severity='high', status='open')
        self.assertEqual(breach.status, 'open')
        breach.status = 'resolved'
        breach.save()
        self.assertEqual(ThresholdBreach.objects.get(pk=breach.pk).status, 'resolved')

    def test_channel_routing_flow(self):
        from api.alerts.models.channel import AlertChannel, ChannelRoute
        channel = AlertChannel.objects.create(
            name='Comp Channel', channel_type='slack', is_enabled=True,
            config={'webhook_url': 'https://test.slack.com'}, created_by=self.user)
        route = ChannelRoute.objects.create(
            name='Comp Route', route_type='severity',
            conditions={'severity': 'high'}, is_active=True)
        route.destination_channels.add(channel)
        self.assertEqual(route.destination_channels.count(), 1)

    def test_incident_from_alert(self):
        from api.alerts.models.core import AlertLog
        from api.alerts.models.incident import Incident
        log = AlertLog.objects.create(
            rule=self.rule, trigger_value=95.0, threshold_value=80.0,
            message='Incident trigger', is_resolved=False)
        incident = Incident.objects.create(
            title='Auto Incident', description='Created from alert',
            severity='high', status='open', created_by=self.user)
        self.assertIsNotNone(incident.id)

    def test_sla_breach_detection(self):
        from api.alerts.models.reporting import SLABreach
        breach = SLABreach.objects.create(
            sla_name='Response SLA', breach_type='resolution_time',
            severity='high', status='open',
            breached_at=timezone.now() - timedelta(hours=2),
            target_minutes=30, actual_minutes=150)
        self.assertEqual(breach.status, 'open')
        self.assertGreater(breach.actual_minutes, breach.target_minutes)
