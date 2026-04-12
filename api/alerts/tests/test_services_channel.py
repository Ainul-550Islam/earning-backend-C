"""
Tests for Channel Services
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
import json

from alerts.models.channel import (
    AlertChannel, ChannelRoute, ChannelHealthLog, ChannelRateLimit, AlertRecipient
)
from alerts.services.channel import (
    NotificationService, ChannelRoutingService, ChannelHealthService,
    ChannelRateLimitService, RecipientManagementService
)


class NotificationServiceTest(TestCase):
    """Test cases for NotificationService"""
    
    def setUp(self):
        self.service = NotificationService()
        
        self.alert_channel = AlertChannel.objects.create(
            name='Email Channel',
            channel_type='email',
            is_enabled=True,
            config={
                'smtp_server': 'smtp.example.com',
                'smtp_port': 587,
                'smtp_username': 'alerts@example.com',
                'smtp_password': 'password',
                'use_tls': True
            }
        )
    
    def test_send_notification(self):
        """Test sending notification"""
        notification_data = {
            'channel_id': self.alert_channel.id,
            'recipient': 'test@example.com',
            'subject': 'Test Alert',
            'message': 'This is a test alert message',
            'priority': 'high'
        }
        
        result = self.service.send_notification(notification_data)
        
        self.assertIn('success', result)
        self.assertIn('notification_id', result)
        self.assertIn('delivery_status', result)
    
    def test_send_notification_with_attachments(self):
        """Test sending notification with attachments"""
        notification_data = {
            'channel_id': self.alert_channel.id,
            'recipient': 'test@example.com',
            'subject': 'Test Alert with Attachments',
            'message': 'This is a test alert with attachments',
            'attachments': [
                {'name': 'report.pdf', 'content': 'base64_content'},
                {'name': 'data.csv', 'content': 'base64_content'}
            ]
        }
        
        result = self.service.send_notification(notification_data)
        
        self.assertIn('success', result)
        self.assertIn('attachments_sent', result)
    
    def test_validate_notification_data(self):
        """Test validating notification data"""
        # Valid data
        valid_data = {
            'channel_id': self.alert_channel.id,
            'recipient': 'test@example.com',
            'subject': 'Test Alert',
            'message': 'Test message'
        }
        
        result = self.service.validate_notification_data(valid_data)
        self.assertTrue(result['valid'])
        
        # Invalid data - missing required fields
        invalid_data = {
            'recipient': 'test@example.com',
            'subject': 'Test Alert'
        }
        
        result = self.service.validate_notification_data(invalid_data)
        self.assertFalse(result['valid'])
        self.assertIn('errors', result)
    
    def test_format_notification_content(self):
        """Test formatting notification content"""
        content_data = {
            'subject': 'Alert: CPU Usage High',
            'message': 'CPU usage has exceeded threshold',
            'alert_details': {
                'current_value': 85.0,
                'threshold': 80.0,
                'severity': 'high'
            }
        }
        
        formatted = self.service.format_notification_content(
            content_data,
            self.alert_channel.channel_type
        )
        
        self.assertIn('subject', formatted)
        self.assertIn('message', formatted)
        self.assertIn('html_content', formatted)
    
    def test_retry_failed_notification(self):
        """Test retrying failed notification"""
        notification_id = 1  # Mock ID
        retry_data = {
            'max_retries': 3,
            'retry_delay_minutes': 5
        }
        
        result = self.service.retry_failed_notification(notification_id, retry_data)
        
        self.assertIn('success', result)
        self.assertIn('retry_count', result)
        self.assertIn('delivery_status', result)
    
    def test_get_notification_status(self):
        """Test getting notification status"""
        notification_id = 1  # Mock ID
        
        status = self.service.get_notification_status(notification_id)
        
        self.assertIn('status', status)
        self.assertIn('sent_at', status)
        self.assertIn('delivery_details', status)
    
    def test_batch_send_notifications(self):
        """Test batch sending notifications"""
        batch_data = {
            'channel_id': self.alert_channel.id,
            'notifications': [
                {
                    'recipient': 'user1@example.com',
                    'subject': 'Alert 1',
                    'message': 'Message 1'
                },
                {
                    'recipient': 'user2@example.com',
                    'subject': 'Alert 2',
                    'message': 'Message 2'
                }
            ]
        }
        
        result = self.service.batch_send_notifications(batch_data)
        
        self.assertIn('batch_id', result)
        self.assertIn('total_sent', result)
        self.assertIn('failed_count', result)
        self.assertIn('success_rate', result)
    
    def test_get_notification_statistics(self):
        """Test getting notification statistics"""
        stats = self.service.get_notification_statistics(days=7)
        
        self.assertIn('total_sent', stats)
        self.assertIn('total_failed', stats)
        self.assertIn('success_rate', stats)
        self.assertIn('delivery_times', stats)
        self.assertIn('channel_breakdown', stats)


class ChannelRoutingServiceTest(TestCase):
    """Test cases for ChannelRoutingService"""
    
    def setUp(self):
        self.service = ChannelRoutingService()
        
        self.source_channel = AlertChannel.objects.create(
            name='Primary Channel',
            channel_type='email',
            is_enabled=True
        )
        
        self.destination_channel = AlertChannel.objects.create(
            name='Backup Channel',
            channel_type='sms',
            is_enabled=True
        )
        
        self.channel_route = ChannelRoute.objects.create(
            name='Email to SMS Route',
            route_type='escalation',
            is_active=True,
            priority=1,
            escalation_delay_minutes=30
        )
        
        self.channel_route.source_channels.add(self.source_channel)
        self.channel_route.destination_channels.add(self.destination_channel)
    
    def test_route_notification(self):
        """Test routing notification"""
        routing_data = {
            'source_channel_id': self.source_channel.id,
            'notification_data': {
                'recipient': 'test@example.com',
                'subject': 'Test Alert',
                'message': 'Test message'
            },
            'routing_rules': ['escalation', 'load_balancing']
        }
        
        result = self.service.route_notification(routing_data)
        
        self.assertIn('success', result)
        self.assertIn('routing_result', result)
        self.assertIn('destinations', result)
    
    def test_determine_routing_path(self):
        """Test determining routing path"""
        routing_request = {
            'source_channel_id': self.source_channel.id,
            'notification_priority': 'high',
            'recipient_preferences': ['email', 'sms'],
            'time_constraints': {'business_hours_only': False}
        }
        
        path = self.service.determine_routing_path(routing_request)
        
        self.assertIsInstance(path, list)
        self.assertGreater(len(path), 0)
        
        for step in path:
            self.assertIn('channel_id', step)
            self.assertIn('channel_type', step)
            self.assertIn('priority', step)
    
    def test_apply_routing_rules(self):
        """Test applying routing rules"""
        notification_data = {
            'priority': 'critical',
            'recipient': 'test@example.com',
            'subject': 'Critical Alert'
        }
        
        routing_rules = ['escalation', 'broadcast', 'load_balancing']
        
        result = self.service.apply_routing_rules(notification_data, routing_rules)
        
        self.assertIn('applied_rules', result)
        self.assertIn('routing_decisions', result)
    
    def test_check_channel_availability(self):
        """Test checking channel availability"""
        availability = self.service.check_channel_availability(self.source_channel.id)
        
        self.assertIn('is_available', availability)
        self.assertIn('health_status', availability)
        self.assertIn('last_check', availability)
    
    def test_get_routing_statistics(self):
        """Test getting routing statistics"""
        stats = self.service.get_routing_statistics(days=7)
        
        self.assertIn('total_routed', stats)
        self.assertIn('successful_routes', stats)
        self.assertIn('failed_routes', stats)
        self.assertIn('route_breakdown', stats)
        self.assertIn('avg_routing_time', stats)
    
    def test_optimize_routing(self):
        """Test optimizing routing"""
        optimization_data = {
            'time_period_days': 30,
            'optimization_goals': ['success_rate', 'delivery_time'],
            'constraints': ['max_cost', 'min_reliability']
        }
        
        result = self.service.optimize_routing(optimization_data)
        
        self.assertIn('optimization_result', result)
        self.assertIn('recommendations', result)
        self.assertIn('expected_improvement', result)
    
    def test_create_routing_rule(self):
        """Test creating routing rule"""
        rule_data = {
            'name': 'Critical Alert Escalation',
            'rule_type': 'escalation',
            'conditions': {
                'priority': 'critical',
                'time_without_response': 15
            },
            'actions': {
                'escalate_to': ['sms', 'phone'],
                'notify_managers': True
            }
        }
        
        result = self.service.create_routing_rule(rule_data)
        
        self.assertTrue(result['success'])
        self.assertIn('rule_id', result)
    
    def test_update_routing_rule(self):
        """Test updating routing rule"""
        rule_id = 1  # Mock ID
        update_data = {
            'conditions': {
                'priority': 'high',
                'time_without_response': 10
            },
            'actions': {
                'escalate_to': ['sms'],
                'notify_managers': False
            }
        }
        
        result = self.service.update_routing_rule(rule_id, update_data)
        
        self.assertTrue(result['success'])
    
    def test_delete_routing_rule(self):
        """Test deleting routing rule"""
        rule_id = 1  # Mock ID
        
        result = self.service.delete_routing_rule(rule_id)
        
        self.assertTrue(result['success'])


class ChannelHealthServiceTest(TestCase):
    """Test cases for ChannelHealthService"""
    
    def setUp(self):
        self.service = ChannelHealthService()
        
        self.alert_channel = AlertChannel.objects.create(
            name='Test Channel',
            channel_type='email',
            is_enabled=True
        )
    
    def test_perform_health_check(self):
        """Test performing health check"""
        health_data = {
            'channel_id': self.alert_channel.id,
            'check_types': ['connectivity', 'performance', 'authentication'],
            'timeout_seconds': 30
        }
        
        result = self.service.perform_health_check(health_data)
        
        self.assertIn('overall_status', result)
        self.assertIn('checks_performed', result)
        self.assertIn('check_results', result)
        self.assertIn('timestamp', result)
    
    def test_check_connectivity(self):
        """Test checking connectivity"""
        connectivity_result = self.service.check_connectivity(self.alert_channel.id)
        
        self.assertIn('status', connectivity_result)
        self.assertIn('response_time_ms', connectivity_result)
        self.assertIn('error_message', connectivity_result)
        self.assertIn('timestamp', connectivity_result)
    
    def test_check_performance(self):
        """Test checking performance"""
        performance_result = self.service.check_performance(self.alert_channel.id)
        
        self.assertIn('status', performance_result)
        self.assertIn('metrics', performance_result)
        self.assertIn('response_time', performance_result)
        self.assertIn('throughput', performance_result)
    
    def test_check_authentication(self):
        """Test checking authentication"""
        auth_result = self.service.check_authentication(self.alert_channel.id)
        
        self.assertIn('status', auth_result)
        self.assertIn('authenticated', auth_result)
        self.assertIn('auth_method', auth_result)
        self.assertIn('last_auth_check', auth_result)
    
    def test_get_channel_health_history(self):
        """Test getting channel health history"""
        history = self.service.get_channel_health_history(
            channel_id=self.alert_channel.id,
            days=7
        )
        
        self.assertIsInstance(history, list)
        self.assertIn('health_checks', history)
        self.assertIn('trend_data', history)
    
    def test_get_health_summary(self):
        """Test getting health summary"""
        summary = self.service.get_health_summary(days=7)
        
        self.assertIn('total_channels', summary)
        self.assertIn('healthy_channels', summary)
        self.assertIn('unhealthy_channels', summary)
        self.assertIn('health_percentage', summary)
        self.assertIn('channel_breakdown', summary)
    
    def test_set_health_thresholds(self):
        """Test setting health thresholds"""
        thresholds = {
            'response_time_warning': 1000,  # ms
            'response_time_critical': 5000,  # ms
            'success_rate_warning': 95,     # %
            'success_rate_critical': 80      # %
        }
        
        result = self.service.set_health_thresholds(self.alert_channel.id, thresholds)
        
        self.assertTrue(result['success'])
        self.assertIn('thresholds_set', result)
    
    def test_get_health_alerts(self):
        """Test getting health alerts"""
        alerts = self.service.get_health_alerts(days=1)
        
        self.assertIsInstance(alerts, list)
        self.assertIn('active_alerts', alerts)
        self.assertIn('alert_count', alerts)
    
    def test_create_health_alert(self):
        """Test creating health alert"""
        alert_data = {
            'channel_id': self.alert_channel.id,
            'alert_type': 'performance',
            'severity': 'warning',
            'message': 'Response time degradation detected',
            'metrics': {
                'response_time': 2500,
                'threshold': 1000
            }
        }
        
        result = self.service.create_health_alert(alert_data)
        
        self.assertTrue(result['success'])
        self.assertIn('alert_id', result)
    
    def test_resolve_health_alert(self):
        """Test resolving health alert"""
        alert_id = 1  # Mock ID
        resolution_data = {
            'resolution_note': 'Issue resolved',
            'resolution_actions': ['Restarted service', 'Updated configuration']
        }
        
        result = self.service.resolve_health_alert(alert_id, resolution_data)
        
        self.assertTrue(result['success'])
        self.assertIn('resolved_at', result)


class ChannelRateLimitServiceTest(TestCase):
    """Test cases for ChannelRateLimitService"""
    
    def setUp(self):
        self.service = ChannelRateLimitService()
        
        self.alert_channel = AlertChannel.objects.create(
            name='Test Channel',
            channel_type='email',
            is_enabled=True
        )
        
        self.rate_limit = ChannelRateLimit.objects.create(
            channel=self.alert_channel,
            limit_type='per_minute',
            window_seconds=60,
            max_requests=100,
            current_tokens=100,
            last_refill=timezone.now()
        )
    
    def test_check_rate_limit(self):
        """Test checking rate limit"""
        check_data = {
            'channel_id': self.alert_channel.id,
            'request_type': 'notification',
            'request_size': 1024  # bytes
        }
        
        result = self.service.check_rate_limit(check_data)
        
        self.assertIn('allowed', result)
        self.assertIn('remaining_tokens', result)
        self.assertIn('time_until_refill', result)
        self.assertIn('current_utilization', result)
    
    def test_consume_token(self):
        """Test consuming token"""
        consume_data = {
            'channel_id': self.alert_channel.id,
            'tokens_to_consume': 1
        }
        
        result = self.service.consume_token(consume_data)
        
        self.assertTrue(result['success'])
        self.assertIn('tokens_remaining', result)
        self.assertIn('consumed_at', result)
    
    def test_refill_tokens(self):
        """Test refilling tokens"""
        # Consume some tokens first
        self.rate_limit.current_tokens = 50
        self.rate_limit.save()
        
        result = self.service.refill_tokens(self.alert_channel.id)
        
        self.assertTrue(result['success'])
        self.assertIn('tokens_refilled', result)
        self.assertIn('new_token_count', result)
        
        # Verify tokens were refilled
        self.rate_limit.refresh_from_db()
        self.assertEqual(self.rate_limit.current_tokens, self.rate_limit.max_requests)
    
    def test_get_rate_limit_status(self):
        """Test getting rate limit status"""
        status = self.service.get_rate_limit_status(self.alert_channel.id)
        
        self.assertIn('current_tokens', status)
        self.assertIn('max_tokens', status)
        self.assertIn('utilization_percentage', status)
        self.assertIn('last_refill', status)
        self.assertIn('next_refill', status)
    
    def test_update_rate_limit_config(self):
        """Test updating rate limit configuration"""
        config_data = {
            'max_requests': 200,
            'window_seconds': 60,
            'refill_rate': 1.0
        }
        
        result = self.service.update_rate_limit_config(self.alert_channel.id, config_data)
        
        self.assertTrue(result['success'])
        self.assertIn('config_updated', result)
    
    def test_get_rate_limit_statistics(self):
        """Test getting rate limit statistics"""
        stats = self.service.get_rate_limit_statistics(days=7)
        
        self.assertIn('total_requests', stats)
        self.assertIn('successful_requests', stats)
        self.assertIn('rejected_requests', stats)
        self.assertIn('rejection_rate', stats)
        self.assertIn('peak_utilization', stats)
    
    def test_create_custom_rate_limit(self):
        """Test creating custom rate limit"""
        limit_data = {
            'channel_id': self.alert_channel.id,
            'limit_type': 'custom',
            'window_seconds': 3600,  # 1 hour
            'max_requests': 1000,
            'custom_rules': {
                'time_based': True,
                'business_hours_multiplier': 1.5
            }
        }
        
        result = self.service.create_custom_rate_limit(limit_data)
        
        self.assertTrue(result['success'])
        self.assertIn('limit_id', result)
    
    def test_delete_rate_limit(self):
        """Test deleting rate limit"""
        limit_id = self.rate_limit.id
        
        result = self.service.delete_rate_limit(limit_id)
        
        self.assertTrue(result['success'])
        self.assertIn('deleted_at', result)
    
    def test_get_rate_limit_recommendations(self):
        """Test getting rate limit recommendations"""
        recommendations = self.service.get_rate_limit_recommendations(
            channel_id=self.alert_channel.id,
            days=30
        )
        
        self.assertIsInstance(recommendations, list)
        self.assertIn('analysis_period', recommendations)
        self.assertIn('suggested_limits', recommendations)
        self.assertIn('reasoning', recommendations)


class RecipientManagementServiceTest(TestCase):
    """Test cases for RecipientManagementService"""
    
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        self.service = RecipientManagementService()
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.alert_recipient = AlertRecipient.objects.create(
            name='Test User',
            recipient_type='user',
            user=self.user,
            email_address='test@example.com',
            phone_number='+1234567890',
            priority=1,
            is_active=True,
            max_notifications_per_hour=50
        )
    
    def test_add_recipient(self):
        """Test adding recipient"""
        recipient_data = {
            'name': 'New User',
            'recipient_type': 'email',
            'email_address': 'newuser@example.com',
            'phone_number': '+1234567891',
            'priority': 2,
            'is_active': True,
            'max_notifications_per_hour': 25
        }
        
        result = self.service.add_recipient(recipient_data)
        
        self.assertTrue(result['success'])
        self.assertIn('recipient_id', result)
    
    def test_update_recipient(self):
        """Test updating recipient"""
        update_data = {
            'name': 'Updated User',
            'priority': 3,
            'max_notifications_per_hour': 75
        }
        
        result = self.service.update_recipient(self.alert_recipient.id, update_data)
        
        self.assertTrue(result['success'])
        self.assertIn('updated_fields', result)
    
    def test_remove_recipient(self):
        """Test removing recipient"""
        result = self.service.remove_recipient(self.alert_recipient.id)
        
        self.assertTrue(result['success'])
        self.assertIn('removed_at', result)
    
    def test_get_recipient_by_contact(self):
        """Test getting recipient by contact"""
        # Test by email
        recipient = self.service.get_recipient_by_contact('test@example.com')
        self.assertIsNotNone(recipient)
        self.assertEqual(recipient.id, self.alert_recipient.id)
        
        # Test by phone
        recipient = self.service.get_recipient_by_contact('+1234567890')
        self.assertIsNotNone(recipient)
        self.assertEqual(recipient.id, self.alert_recipient.id)
    
    def test_get_available_recipients(self):
        """Test getting available recipients"""
        available = self.service.get_available_recipients(
            notification_type='email',
            priority='high'
        )
        
        self.assertIsInstance(available, list)
        self.assertGreater(len(available), 0)
    
    def test_check_recipient_availability(self):
        """Test checking recipient availability"""
        availability = self.service.check_recipient_availability(self.alert_recipient.id)
        
        self.assertIn('is_available', availability)
        self.assertIn('available_channels', availability)
        self.assertIn('last_notification', availability)
        self.assertIn('notification_count_today', availability)
    
    def test_get_recipient_preferences(self):
        """Test getting recipient preferences"""
        preferences = self.service.get_recipient_preferences(self.alert_recipient.id)
        
        self.assertIn('preferred_channels', preferences)
        self.assertIn('notification_schedule', preferences)
        self.assertIn('severity_preferences', preferences)
        self.assertIn('quiet_hours', preferences)
    
    def test_update_recipient_preferences(self):
        """Test updating recipient preferences"""
        preferences_data = {
            'preferred_channels': ['email', 'sms'],
            'notification_schedule': {
                'business_hours_only': False,
                'weekend_notifications': True
            },
            'severity_preferences': {
                'critical': True,
                'high': True,
                'medium': False,
                'low': False
            }
        }
        
        result = self.service.update_recipient_preferences(
            self.alert_recipient.id,
            preferences_data
        )
        
        self.assertTrue(result['success'])
        self.assertIn('preferences_updated', result)
    
    def test_get_recipient_statistics(self):
        """Test getting recipient statistics"""
        stats = self.service.get_recipient_statistics(self.alert_recipient.id, days=30)
        
        self.assertIn('notifications_sent', stats)
        self.assertIn('notifications_delivered', stats)
        self.assertIn('delivery_rate', stats)
        self.assertIn('avg_response_time', stats)
        self.assertIn('channel_breakdown', stats)
    
    def test_get_recipient_groups(self):
        """Test getting recipient groups"""
        groups = self.service.get_recipient_groups()
        
        self.assertIsInstance(groups, list)
        self.assertIn('total_groups', groups)
        self.assertIn('group_details', groups)
    
    def test_create_recipient_group(self):
        """Test creating recipient group"""
        group_data = {
            'name': 'DevOps Team',
            'description': 'DevOps team members',
            'recipient_ids': [self.alert_recipient.id],
            'notification_rules': {
                'severity': ['critical', 'high'],
                'channels': ['email', 'sms']
            }
        }
        
        result = self.service.create_recipient_group(group_data)
        
        self.assertTrue(result['success'])
        self.assertIn('group_id', result)
