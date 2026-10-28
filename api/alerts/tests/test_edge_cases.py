"""
Edge Cases Tests for Alerts API
"""
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
import json

from api.alerts.models.core import AlertRule, AlertLog, Notification, SystemMetrics
from api.alerts.models.threshold import ThresholdConfig, ThresholdBreach
from api.alerts.models.channel import AlertChannel, ChannelRoute
from api.alerts.models.incident import Incident
from api.alerts.models.intelligence import AlertCorrelation
from api.alerts.services.core import AlertProcessingService

User = get_user_model()


class AlertRuleEdgeCasesTest(TestCase):
    """Edge cases for AlertRule model"""

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.get_or_create(
            username='edge_user',
            defaults={'email': 'edge@test.com'}
        )[0]

    def test_alert_rule_with_extreme_values(self):
        """Test alert rule with extreme threshold values"""
        # Very high threshold
        rule = AlertRule.objects.create(
            name='Extreme High Threshold',
            alert_type='payment_spike',
            severity='high',
            threshold_value=999999.0,
            created_by=self.user)
        
        self.assertEqual(rule.threshold_value, 999999.0)
        
        # Very low threshold
        rule = AlertRule.objects.create(
            name='Extreme Low Threshold',
            alert_type='server_error',
            severity='low',
            threshold_value=0.001
        ,
            created_by=self.user)
        
        self.assertEqual(rule.threshold_value, 0.001)
    
    def test_alert_rule_with_unicode_characters(self):
        """Test alert rule with unicode characters"""
        rule = AlertRule.objects.create(
            name='Alert with émojis and unicôde characters',
            alert_type='server_error',
            severity='high',
            threshold_value=80.0,
            description='Description with émojis:  alert, and unicôde: café, résumé'
        ,
            created_by=self.user)
        
        self.assertIn('émojis', rule.name)
        self.assertIn('unicôde', rule.description)
    
    def test_alert_rule_with_very_long_name(self):
        """Test alert rule with very long name — Django enforces max_length=100 via full_clean"""
        from django.core.exceptions import ValidationError as DjangoValidationError
        long_name = 'A' * 500
        with self.assertRaises(DjangoValidationError):
            AlertRule.objects.create(
                name=long_name,
                alert_type='server_error',
                severity='high',
                threshold_value=80.0,
                created_by=self.user)
    
    def test_alert_rule_with_null_fields(self):
        """Test alert rule with blank optional fields (description/cooldown are NOT NULL in schema)"""
        rule = AlertRule.objects.create(
            name='Alert with blank fields',
            alert_type='server_error',
            severity='high',
            threshold_value=80.0,
            description='',   # TextField allows blank string
            created_by=self.user
        )
        self.assertEqual(rule.description, '')
    
    def test_alert_rule_with_invalid_severity(self):
        """Test alert rule with invalid severity — Django 6.0 rejects via full_clean on save"""
        from django.core.exceptions import ValidationError as DjangoValidationError
        rule = AlertRule.objects.create(
            name='Invalid Severity Test',
            alert_type='server_error',
            severity='high',
            threshold_value=80.0,
            created_by=self.user)

        # Django 6.0 calls full_clean() on save(), so invalid choices are rejected
        rule.severity = 'invalid_severity'
        with self.assertRaises(DjangoValidationError):
            rule.save()
    
    def test_alert_rule_with_future_timestamps(self):
        """Test alert rule with future timestamps"""
        future_time = timezone.now() + timedelta(days=365)
        
        rule = AlertRule.objects.create(
            name='Future Timestamp Test',
            alert_type='server_error',
            severity='high',
            threshold_value=80.0
        ,
            created_by=self.user)
        
        # Manually set future timestamp (not typical usage)
        rule.created_at = future_time
        rule.save()
        
        self.assertEqual(rule.created_at, future_time)


class AlertLogEdgeCasesTest(TestCase):
    """Edge cases for AlertLog model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='edgecasetester129', email='edgecasetester129@example.com', password='testpass123'
        )
        self.user = User.objects.get_or_create(
            username='alertlog_edge_user',
            defaults={'email': 'alertlogedge@test.com', 'is_staff': True}
        )[0]
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='server_error',
            severity='high',
            threshold_value=80.0,
            created_by=self.user)
    
    def test_alert_log_with_negative_values(self):
        """Test alert log with negative trigger values"""
        alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=-50.0,  # Negative value
            threshold_value=80.0,
            message='Negative trigger value'
        )
        
        self.assertEqual(alert.trigger_value, -50.0)
        self.assertLessEqual(alert.get_exceed_percentage(), 0)  # Negative trigger = at or below threshold
    
    def test_alert_log_with_zero_values(self):
        """Test alert log with zero values"""
        alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=0.0,
            threshold_value=0.0,
            message='Zero values'
        )
        
        self.assertEqual(alert.trigger_value, 0.0)
        self.assertEqual(alert.threshold_value, 0.0)
    
    def test_alert_log_with_very_large_details(self):
        """Test alert log with very large details field"""
        large_details = {
            'data': 'x' * 10000,  # 10KB of data
            'nested': {
                'more_data': 'y' * 5000,
                'deeply_nested': {
                    'even_more': 'z' * 2000
                }
            }
        }
        
        alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Large details test',
            details=large_details
        )
        
        self.assertEqual(len(alert.details['data']), 10000)
        self.assertEqual(len(alert.details['nested']['more_data']), 5000)
    
    def test_alert_log_with_unicode_in_message(self):
        """Test alert log with unicode characters in message"""
        unicode_message = 'Alert with émojis:  alert,  and unicôde: café, résumé'
        
        alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message=unicode_message
        )
        
        self.assertIn('émojis', alert.message)
        self.assertIn('unicôde', alert.message)
    
    def test_alert_log_with_resolution_before_trigger(self):
        """Test alert log with resolution time before trigger time"""
        past_time = timezone.now() - timedelta(hours=2)
        future_time = timezone.now() - timedelta(hours=1)
        
        alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Time anomaly test',
            triggered_at=future_time,
            resolved_at=past_time,
            is_resolved=True)

        self.assertTrue(alert.is_resolved)
        # resolved_at (past_time) is before triggered_at (future_time = -1h)
        self.assertLess(alert.resolved_at, alert.triggered_at)
    
    def test_alert_log_with_multiple_status_changes(self):
        """Test alert log with multiple status changes"""
        alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Status change test'
        )
        
        # Acknowledge
        alert.acknowledged_at = timezone.now()
        alert.save()
        
        # Unacknowledge
        alert.acknowledged_at = None
        alert.save()
        
        # Resolve
        alert.is_resolved = True
        alert.resolved_at = timezone.now()
        alert.save()
        
        # Unresolve
        alert.is_resolved = False
        alert.resolved_at = None
        alert.save()
        
        # Final resolve
        alert.is_resolved = True
        alert.resolved_at = timezone.now()
        alert.save()
        
        self.assertTrue(alert.is_resolved)
        self.assertIsNotNone(alert.resolved_at)
    
    def test_alert_log_with_circular_references(self):
        """Test alert log with potential circular references"""
        # This tests for potential issues with self-referencing data
        alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Circular reference test',
            details={
                'self_reference': None  # Will be set later
            }
        )
        
        # Create circular reference
        alert.details['self_reference'] = alert.id
        alert.save()
        
        self.assertEqual(alert.details['self_reference'], alert.id)


class NotificationEdgeCasesTest(TestCase):
    """Edge cases for Notification model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='edgecasetester278', email='edgecasetester278@example.com', password='testpass123'
        )
        self.user = User.objects.get_or_create(
            username='notif_edge_user',
            defaults={'email': 'notifedge@test.com', 'is_staff': True}
        )[0]
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='server_error',
            severity='high',
            threshold_value=80.0,
            created_by=self.user)
        
        self.alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Test alert'
        )
    
    def test_notification_with_invalid_email(self):
        """Test notification with invalid email address"""
        notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='invalid-email-address',
            status='pending'
        )
        
        self.assertEqual(notification.recipient, 'invalid-email-address')
    
    def test_notification_with_empty_recipient(self):
        """Test notification with empty recipient"""
        notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='',
            status='pending'
        )
        
        self.assertEqual(notification.recipient, '')
    
    def test_notification_with_unicode_recipient(self):
        """Test notification with unicode characters in recipient"""
        notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='tést@example.com',
            status='pending'
        )
        
        self.assertEqual(notification.recipient, 'tést@example.com')
    
    def test_notification_with_very_long_recipient(self):
        """Test notification with very long recipient"""
        from django.core.exceptions import ValidationError
        # The column is varchar(255). SQLite silently stores longer values, PostgreSQL raises
        # DataError, so assert the portable contract instead: validation rejects it, and a
        # value at the limit round-trips.
        too_long = Notification(alert_log=self.alert_log, notification_type='email',
                                recipient='a' * 500 + '@example.com', status='pending')
        with self.assertRaises(ValidationError) as ctx:
            too_long.full_clean()
        self.assertIn('recipient', ctx.exception.message_dict)

        at_limit = 'a' * (255 - len('@example.com')) + '@example.com'
        notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient=at_limit,
            status='pending'
        )
        notification.refresh_from_db()
        self.assertEqual(notification.recipient, at_limit)
    
    def test_notification_with_multiple_failed_attempts(self):
        """Test notification with multiple retry attempts"""
        notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='test@example.com',
            status='failed',
            retry_count=999,  # Very high retry count
            error_message='Persistent failure'
        )
        
        self.assertEqual(notification.retry_count, 999)
        self.assertEqual(notification.status, 'failed')
    
    def test_notification_with_future_timestamps(self):
        """Test notification with future timestamps"""
        future_time = timezone.now() + timedelta(hours=1)
        
        notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='test@example.com',
            status='sent',
            sent_at=future_time  # Future timestamp
        )
        
        self.assertEqual(notification.sent_at, future_time)
    
    def test_notification_with_invalid_type(self):
        """Test notification with invalid notification type"""
        notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='invalid_type',
            recipient='test@example.com',
            status='pending'
        )
        
        self.assertEqual(notification.notification_type, 'invalid_type')
    
    def test_notification_with_large_error_message(self):
        """Test notification with large error message"""
        large_error = 'Error: ' + 'x' * 10000  # 10KB error message
        
        notification = Notification.objects.create(
            alert_log=self.alert_log,
            notification_type='email',
            recipient='test@example.com',
            status='failed',
            error_message=large_error
        )
        
        self.assertEqual(len(notification.error_message), len(large_error))


class ThresholdEdgeCasesTest(TestCase):
    """Edge cases for Threshold models"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='edgecasetester400', email='edgecasetester400@example.com', password='testpass123'
        )
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='server_error',
            severity='high',
            threshold_value=80.0
        ,
            created_by=self.user)
    
    def test_threshold_config_with_negative_values(self):
        """Test threshold config with negative values"""
        config = ThresholdConfig.objects.create(
            alert_rule=self.alert_rule,
            threshold_type='static',
            comparison_operator='gt',
            primary_threshold=-50.0,  # Negative threshold
            secondary_threshold=-25.0
        )
        
        self.assertEqual(config.primary_threshold, -50.0)
        self.assertEqual(config.secondary_threshold, -25.0)
    
    def test_threshold_config_with_zero_thresholds(self):
        """Test threshold config with zero thresholds"""
        config = ThresholdConfig.objects.create(
            alert_rule=self.alert_rule,
            threshold_type='static',
            comparison_operator='gt',
            primary_threshold=0.0,
            secondary_threshold=0.0
        )
        
        self.assertEqual(config.primary_threshold, 0.0)
        self.assertEqual(config.secondary_threshold, 0.0)
    
    def test_threshold_config_with_very_large_window(self):
        """Test threshold config with very large time window"""
        config = ThresholdConfig.objects.create(
            alert_rule=self.alert_rule,
            threshold_type='static',
            comparison_operator='gt',
            primary_threshold=85.0,
            secondary_threshold=90.0,
            calculation_window_minutes=999999  # Very large window
        )
        
        self.assertEqual(config.calculation_window_minutes, 999999)
    
    def test_threshold_breach_with_negative_breach_percentage(self):
        """Test threshold breach with negative breach percentage"""
        config = ThresholdConfig.objects.create(
            alert_rule=self.alert_rule,
            threshold_type='static',
            comparison_operator='gt',
            primary_threshold=100.0,
            secondary_threshold=150.0
        )
        
        breach = ThresholdBreach.objects.create(
            threshold_config=config,
            severity='low',
            breach_value=50.0,  # Below threshold
            threshold_value=100.0,
            breach_percentage=-50.0  # Negative percentage
        )
        
        self.assertEqual(breach.breach_percentage, -50.0)
    
    def test_threshold_breach_with_zero_duration(self):
        """Test threshold breach with zero duration"""
        config = ThresholdConfig.objects.create(
            alert_rule=self.alert_rule,
            threshold_type='static',
            comparison_operator='gt',
            primary_threshold=85.0,
            secondary_threshold=90.0
        )
        
        same_time = timezone.now()
        breach = ThresholdBreach.objects.create(
            threshold_config=config,
            severity='high',
            breach_value=95.0,
            threshold_value=85.0,
            detected_at=same_time,
            resolved_at=same_time,  # Zero duration
        )
        
        self.assertEqual(breach.duration_minutes, 0)
    
    def test_threshold_config_with_invalid_operator(self):
        """Test threshold config with invalid operator"""
        from django.core.exceptions import ValidationError
        # (the column is varchar(15): the old 16-character value only "worked" on SQLite)
        config = ThresholdConfig.objects.create(
            alert_rule=self.alert_rule,
            threshold_type='static',
            comparison_operator='bad_op',  # Invalid operator (not one of the choices)
            primary_threshold=85.0,
            secondary_threshold=90.0
        )
        
        self.assertEqual(config.comparison_operator, 'bad_op')
        with self.assertRaises(ValidationError) as ctx:
            config.full_clean()
        self.assertIn('comparison_operator', ctx.exception.message_dict)
    
    def test_threshold_evaluation_with_division_by_zero(self):
        """Test threshold evaluation with potential division by zero"""
        config = ThresholdConfig.objects.create(
            alert_rule=self.alert_rule,
            threshold_type='dynamic',
            comparison_operator='gt',
            primary_threshold=0.0,  # Zero threshold - potential division by zero
            secondary_threshold=10.0
        )
        
        # Evaluate with zero threshold
        result = config.evaluate_condition(50.0)
        
        # Should handle gracefully without division by zero, returning a
        # plain boolean (the contract relied on by admin/threshold.py and
        # viewsets/threshold.py)
        self.assertIsInstance(result, bool)
        self.assertTrue(result)


class ChannelEdgeCasesTest(TestCase):
    """Edge cases for Channel models"""
    
    def test_alert_channel_with_empty_config(self):
        """Test alert channel with empty config"""
        channel = AlertChannel.objects.create(
            name='Empty Config Channel',
            channel_type='email',
            is_enabled=True,
            config={}  # Empty config
        )
        
        self.assertEqual(channel.config, {})
    
    def test_alert_channel_with_invalid_config_type(self):
        """Test alert channel with invalid config type"""
        channel = AlertChannel.objects.create(
            name='Invalid Config Channel',
            channel_type='email',
            is_enabled=True,
            config='invalid_config_type'  # String instead of dict
        )
        
        self.assertEqual(channel.config, 'invalid_config_type')
    
    def test_alert_channel_with_very_large_config(self):
        """Test alert channel with very large config"""
        large_config = {
            'large_data': 'x' * 10000,
            'nested': {
                'more_data': 'y' * 5000,
                'deeply_nested': {
                    'even_more': 'z' * 2000
                }
            }
        }
        
        channel = AlertChannel.objects.create(
            name='Large Config Channel',
            channel_type='email',
            is_enabled=True,
            config=large_config
        )
        
        self.assertEqual(len(channel.config['large_data']), 10000)
    
    def test_channel_route_with_no_channels(self):
        """Test channel route with no source or destination channels"""
        route = ChannelRoute.objects.create(
            name='Empty Route',
            route_type='escalation',
            is_active=True
        )
        
        # Should be able to create without channels
        self.assertEqual(route.source_channels.count(), 0)
        self.assertEqual(route.destination_channels.count(), 0)
    
    def test_channel_route_with_circular_routing(self):
        """Test channel route with potential circular routing"""
        channel1 = AlertChannel.objects.create(
            name='Channel 1',
            channel_type='email',
            is_enabled=True
        )
        
        channel2 = AlertChannel.objects.create(
            name='Channel 2',
            channel_type='sms',
            is_enabled=True
        )
        
        # Create route from channel1 to channel2
        route1 = ChannelRoute.objects.create(
            name='Route 1->2',
            route_type='escalation',
            is_active=True
        )
        route1.source_channels.add(channel1)
        route1.destination_channels.add(channel2)
        
        # Create route from channel2 back to channel1 (circular)
        route2 = ChannelRoute.objects.create(
            name='Route 2->1',
            route_type='escalation',
            is_active=True
        )
        route2.source_channels.add(channel2)
        route2.destination_channels.add(channel1)
        
        # Should be able to create circular routes
        self.assertEqual(route1.source_channels.count(), 1)
        self.assertEqual(route1.destination_channels.count(), 1)
        self.assertEqual(route2.source_channels.count(), 1)
        self.assertEqual(route2.destination_channels.count(), 1)
    
    def test_alert_channel_with_unicode_in_config(self):
        """Test alert channel with unicode characters in config"""
        unicode_config = {
            'unicode_field': 'tést unicode with émojis: ',
            'nested_unicode': {
                'more_unicode': 'café, résumé'
            }
        }
        
        channel = AlertChannel.objects.create(
            name='Unicode Config Channel',
            channel_type='email',
            is_enabled=True,
            config=unicode_config
        )
        
        self.assertIn('émojis', channel.config['unicode_field'])
        self.assertIn('café', channel.config['nested_unicode']['more_unicode'])


class IncidentEdgeCasesTest(TestCase):
    """Edge cases for Incident models"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_incident_with_future_detected_time(self):
        """Test incident with future detected time"""
        future_time = timezone.now() + timedelta(hours=1)
        
        incident = Incident.objects.create(
            title='Future Incident',
            description='Incident detected in future',
            severity='high',
            impact='minor',
            urgency='medium',
            status='open',
            detected_at=future_time
        )
        
        self.assertEqual(incident.detected_at, future_time)
    
    def test_incident_with_resolution_before_detection(self):
        """Test incident with resolution timestamp before detection timestamp (data anomaly)"""
        detected_time = timezone.now() - timedelta(hours=1)
        resolved_time = timezone.now() - timedelta(hours=2)  # before detected_time
        
        incident = Incident.objects.create(
            title='Time Anomaly Incident',
            description='Resolved before detected',
            severity='high',
            impact='minor',
            urgency='medium',
            status='resolved',
            detected_at=detected_time,
            resolved_at=resolved_time)
        
        self.assertTrue(incident.is_resolved)
        self.assertLess(incident.resolved_at, incident.detected_at)
    
    def test_incident_with_very_long_description(self):
        """Test incident with very long description"""
        long_description = 'A' * 10000  # 10KB description
        
        incident = Incident.objects.create(
            title='Long Description Incident',
            description=long_description,
            severity='high',
            impact='minor',
            urgency='medium',
            status='open'
        )
        
        self.assertEqual(len(incident.description), 10000)
    
    def test_incident_with_unicode_in_fields(self):
        """Test incident with unicode characters in fields"""
        unicode_title = 'Incident with émojis:  and unicôde: café'
        unicode_description = 'Description with unicôde characters: résumé, café, naïve'
        
        incident = Incident.objects.create(
            title=unicode_title,
            description=unicode_description,
            severity='high',
            impact='minor',
            urgency='medium',
            status='open'
        )
        
        self.assertIn('émojis', incident.title)
        self.assertIn('unicôde', incident.description)
    
    def test_incident_with_empty_affected_services(self):
        """Test incident with empty affected services"""
        incident = Incident.objects.create(
            title='Empty Services Incident',
            description='No affected services',
            severity='high',
            impact='minor',
            urgency='medium',
            status='open',
            affected_services=[]  # Empty list
        )
        
        self.assertEqual(incident.affected_services, [])
    
    def test_incident_with_negative_users_count(self):
        """Test incident with negative affected users count"""
        incident = Incident.objects.create(
            title='Negative Users Incident',
            description='Negative user count',
            severity='high',
            impact='minor',
            urgency='medium',
            status='open',
            affected_users_count=-100  # Negative count
        )
        
        self.assertEqual(incident.affected_users_count, -100)
    
    def test_incident_timeline_with_future_timestamps(self):
        """Test incident timeline with future timestamps"""
        incident = Incident.objects.create(
            title='Future Timeline Incident',
            description='Timeline with future events',
            severity='high',
            impact='minor',
            urgency='medium',
            status='open'
        )
        
        future_time = timezone.now() + timedelta(hours=1)
        
        from api.alerts.models.incident import IncidentTimeline
        timeline = IncidentTimeline.objects.create(
            incident=incident,
            event_type='status_change',
            title='Future Event',
            description='Event scheduled for future',
            timestamp=future_time
        )
        
        self.assertEqual(timeline.timestamp, future_time)


class SystemMetricsEdgeCasesTest(TestCase):
    """Edge cases for SystemMetrics model"""
    
    def test_system_metrics_with_negative_values(self):
        """Test system metrics with negative values"""
        metrics = SystemMetrics.objects.create(
            total_users=-100,  # Negative users
            active_users_1h=-50,  # Negative active users
            total_earnings_1h=-1000.0,  # Negative earnings
            avg_response_time_ms=-200.0  # Negative response time
        )
        
        self.assertEqual(metrics.total_users, -100)
        self.assertEqual(metrics.active_users_1h, -50)
        self.assertEqual(metrics.total_earnings_1h, -1000.0)
        self.assertEqual(metrics.avg_response_time_ms, -200.0)
    
    def test_system_metrics_with_zero_values(self):
        """Test system metrics with zero values"""
        metrics = SystemMetrics.objects.create(
            total_users=0,
            active_users_1h=0,
            total_earnings_1h=0.0,
            avg_response_time_ms=0.0
        )
        
        self.assertEqual(metrics.total_users, 0)
        self.assertEqual(metrics.active_users_1h, 0)
        self.assertEqual(metrics.total_earnings_1h, 0.0)
        self.assertEqual(metrics.avg_response_time_ms, 0.0)
    
    def test_system_metrics_with_very_large_values(self):
        """Test system metrics with very large values"""
        metrics = SystemMetrics.objects.create(
            total_users=999999999,  # Very large number
            active_users_1h=999999999,
            total_earnings_1h=999999999.0,
            avg_response_time_ms=999999999.0
        )
        
        self.assertEqual(metrics.total_users, 999999999)
        self.assertEqual(metrics.active_users_1h, 999999999)
        self.assertEqual(metrics.total_earnings_1h, 999999999.0)
        self.assertEqual(metrics.avg_response_time_ms, 999999999.0)
    
    def test_system_metrics_with_future_timestamp(self):
        """Test system metrics with future timestamp"""
        future_time = timezone.now() + timedelta(hours=1)
        
        metrics = SystemMetrics.objects.create(
            total_users=1000,
            active_users_1h=500,
            total_earnings_1h=1000.0,
            avg_response_time_ms=200.0,
            timestamp=future_time
        )
        
        self.assertEqual(metrics.timestamp, future_time)
    
    def test_system_metrics_with_null_timestamp(self):
        """Test system metrics with null timestamp - should be auto-filled"""
        metrics = SystemMetrics.objects.create(
            total_users=1000,
            active_users_1h=500,
            total_earnings_1h=1000.0,
            avg_response_time_ms=200.0,
            timestamp=None  # Null timestamp - pre_save signal should fill this in
        )
        
        # system_metrics_pre_save auto-fills a missing timestamp so metrics
        # rows always have one for time-series ordering/querying.
        self.assertIsNotNone(metrics.timestamp)


class ServiceEdgeCasesTest(TransactionTestCase):
    """Edge cases for service classes"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='edgecasetester837', email='edgecasetester837@example.com', password='testpass123'
        )
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='server_error',
            severity='high',
            threshold_value=80.0
        ,
            created_by=self.user)
        
        self.service = AlertProcessingService()
    
    def test_process_alert_with_invalid_data(self):
        """Test processing alert with invalid data"""
        invalid_data = {
            'rule_id': 999999,  # Non-existent rule
            'trigger_value': 'invalid_value',  # String instead of number
            'threshold_value': None,  # None value
            'message': ''  # Empty message
        }
        
        result = self.service.process_alert(invalid_data)
        
        # Should handle gracefully
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    def test_process_alert_with_missing_fields(self):
        """Test processing alert with missing fields"""
        incomplete_data = {
            'rule_id': self.alert_rule.id
            # Missing other required fields
        }
        
        result = self.service.process_alert(incomplete_data)
        
        # Should handle gracefully
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    def test_process_alert_with_unicode_data(self):
        """Test processing alert with unicode data"""
        unicode_data = {
            'rule_id': self.alert_rule.id,
            'trigger_value': 85.0,
            'threshold_value': 80.0,
            'message': 'Alert with émojis:  and unicôde: café',
            'details': {
                'unicode_field': 'tést data with résumé, naïve',
                'emojis': ''
            }
        }
        
        result = self.service.process_alert(unicode_data)
        
        # Should handle unicode correctly
        self.assertTrue(result['success'])
    
    def test_process_alert_with_very_large_data(self):
        """Test processing alert with very large data"""
        large_data = {
            'rule_id': self.alert_rule.id,
            'trigger_value': 85.0,
            'threshold_value': 80.0,
            'message': 'A' * 1000,  # 1KB message
            'details': {
                'large_field': 'x' * 10000,  # 10KB field
                'nested_large': {
                    'more_data': 'y' * 5000,
                    'deeply_nested': {
                        'even_more': 'z' * 2000
                    }
                }
            }
        }
        
        result = self.service.process_alert(large_data)
        
        # Should handle large data
        self.assertTrue(result['success'])
    
    def test_process_alert_with_circular_references(self):
        """Test processing alert with circular references in data"""
        # Create circular reference
        circular_data = {
            'rule_id': self.alert_rule.id,
            'trigger_value': 85.0,
            'threshold_value': 80.0,
            'message': 'Circular reference test'
        }
        
        # Add self-reference
        circular_data['self_ref'] = circular_data
        
        result = self.service.process_alert(circular_data)
        
        # Should handle circular references
        self.assertTrue(result['success'])
    
    def test_process_alert_with_none_values(self):
        """Test processing alert with None values"""
        none_data = {
            'rule_id': self.alert_rule.id,
            'trigger_value': None,  # None value
            'threshold_value': None,  # None value
            'message': None,  # None message
            'details': None  # None details
        }
        
        result = self.service.process_alert(none_data)
        
        # Should handle None values gracefully
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    def test_process_alert_with_extreme_numeric_values(self):
        """Test processing alert with extreme numeric values"""
        extreme_data = {
            'rule_id': self.alert_rule.id,
            'trigger_value': 999999999.0,  # Very large value
            'threshold_value': 0.000001,  # Very small value
            'message': 'Extreme values test'
        }
        
        result = self.service.process_alert(extreme_data)
        
        # Should handle extreme values
        self.assertTrue(result['success'])
    
    def test_process_alert_concurrent_access(self):
        """Test processing alert with concurrent access"""
        import threading
        import queue
        
        results = queue.Queue()
        
        def process_alert_thread(thread_id):
            try:
                data = {
                    'rule_id': self.alert_rule.id,
                    'trigger_value': 85.0 + thread_id,
                    'threshold_value': 80.0,
                    'message': f'Concurrent test {thread_id}'
                }
                
                result = self.service.process_alert(data)
                results.put(('success', thread_id, result))
            except Exception as e:
                results.put(('error', thread_id, str(e)))
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=process_alert_thread, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        success_count = 0
        error_count = 0
        
        while not results.empty():
            status, thread_id, result = results.get()
            if status == 'success':
                success_count += 1
                self.assertTrue(result['success'])
            else:
                error_count += 1
        
        # Should handle concurrent access
        self.assertEqual(success_count, 10)
        self.assertEqual(error_count, 0)
