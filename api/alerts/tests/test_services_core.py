"""
Tests for Core Services
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
import json

from alerts.models.core import AlertRule, AlertLog, Notification, SystemMetrics
from alerts.services.core import (
    AlertProcessingService, AlertEscalationService, AlertAnalyticsService,
    AlertGroupService, AlertMaintenanceService
)


class AlertProcessingServiceTest(TestCase):
    """Test cases for AlertProcessingService"""
    
    def setUp(self):
        self.service = AlertProcessingService()
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0,
            time_window_minutes=15,
            cooldown_minutes=30
        )
    
    def test_process_alert(self):
        """Test processing an alert"""
        alert_data = {
            'rule_id': self.alert_rule.id,
            'trigger_value': 85.0,
            'threshold_value': 80.0,
            'message': 'CPU usage is high',
            'details': {'current_usage': 85.0}
        }
        
        result = self.service.process_alert(alert_data)
        
        self.assertTrue(result['success'])
        self.assertIn('alert_id', result)
        self.assertIn('notifications_sent', result)
    
    def test_process_alert_with_cooldown(self):
        """Test processing alert during cooldown"""
        # Set last triggered time to be within cooldown
        self.alert_rule.last_triggered = timezone.now() - timedelta(minutes=10)
        self.alert_rule.save()
        
        alert_data = {
            'rule_id': self.alert_rule.id,
            'trigger_value': 85.0,
            'threshold_value': 80.0,
            'message': 'CPU usage is high'
        }
        
        result = self.service.process_alert(alert_data)
        
        self.assertFalse(result['success'])
        self.assertIn('reason', result)
        self.assertEqual(result['reason'], 'Alert rule is in cooldown period')
    
    def test_process_alert_below_threshold(self):
        """Test processing alert with value below threshold"""
        alert_data = {
            'rule_id': self.alert_rule.id,
            'trigger_value': 75.0,
            'threshold_value': 80.0,
            'message': 'CPU usage is normal'
        }
        
        result = self.service.process_alert(alert_data)
        
        self.assertFalse(result['success'])
        self.assertIn('reason', result)
        self.assertEqual(result['reason'], 'Alert value is below threshold')
    
    def test_validate_alert_data(self):
        """Test validating alert data"""
        # Valid data
        valid_data = {
            'rule_id': self.alert_rule.id,
            'trigger_value': 85.0,
            'threshold_value': 80.0,
            'message': 'Test alert'
        }
        
        result = self.service.validate_alert_data(valid_data)
        self.assertTrue(result['valid'])
        
        # Invalid data - missing required fields
        invalid_data = {
            'trigger_value': 85.0,
            'message': 'Test alert'
        }
        
        result = self.service.validate_alert_data(invalid_data)
        self.assertFalse(result['valid'])
        self.assertIn('errors', result)
    
    def test_check_rate_limit(self):
        """Test rate limiting check"""
        # Should pass initially
        result = self.service.check_rate_limit(self.alert_rule)
        self.assertTrue(result['allowed'])
        
        # Simulate rate limit exceeded
        self.alert_rule.rate_limit_per_minute = 1
        self.alert_rule.save()
        
        # Create a recent alert
        AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Test alert',
            triggered_at=timezone.now() - timedelta(minutes=1)
        )
        
        result = self.service.check_rate_limit(self.alert_rule)
        self.assertFalse(result['allowed'])
    
    def test_get_alert_context(self):
        """Test getting alert context"""
        context = self.service.get_alert_context(self.alert_rule)
        
        self.assertIn('rule_name', context)
        self.assertIn('alert_type', context)
        self.assertIn('severity', context)
        self.assertIn('threshold_value', context)
        self.assertIn('cooldown_minutes', context)
    
    def test_format_alert_message(self):
        """Test formatting alert message"""
        alert_data = {
            'trigger_value': 85.0,
            'threshold_value': 80.0,
            'message': 'CPU usage is high',
            'details': {'current_usage': 85.0}
        }
        
        formatted_message = self.service.format_alert_message(alert_data, self.alert_rule)
        
        self.assertIsInstance(formatted_message, str)
        self.assertIn('CPU usage is high', formatted_message)
        self.assertIn('85.0', formatted_message)
        self.assertIn('80.0', formatted_message)


class AlertEscalationServiceTest(TestCase):
    """Test cases for AlertEscalationService"""
    
    def setUp(self):
        self.service = AlertEscalationService()
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='critical',
            threshold_value=80.0,
            escalation_enabled=True,
            escalation_delay_minutes=15,
            max_escalation_level=3
        )
        
        self.alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=95.0,
            threshold_value=80.0,
            message='Critical CPU usage',
            triggered_at=timezone.now() - timedelta(minutes=30)
        )
    
    def test_check_escalation_needed(self):
        """Test checking if escalation is needed"""
        # Alert is old enough for escalation
        result = self.service.check_escalation_needed(self.alert_log)
        self.assertTrue(result['escalate'])
        self.assertIn('reason', result)
        
        # Recent alert should not escalate
        self.alert_log.triggered_at = timezone.now() - timedelta(minutes=5)
        self.alert_log.save()
        
        result = self.service.check_escalation_needed(self.alert_log)
        self.assertFalse(result['escalate'])
    
    def test_escalate_alert(self):
        """Test escalating an alert"""
        escalation_data = {
            'alert_log_id': self.alert_log.id,
            'escalation_level': 1,
            'reason': 'No response within SLA'
        }
        
        result = self.service.escalate_alert(escalation_data)
        
        self.assertTrue(result['success'])
        self.assertIn('escalation_id', result)
        self.assertIn('notification_sent', result)
    
    def test_get_escalation_recipients(self):
        """Test getting escalation recipients"""
        recipients = self.service.get_escalation_recipients(
            self.alert_rule, 
            escalation_level=1
        )
        
        self.assertIsInstance(recipients, list)
        # Should include escalation contacts if configured
    
    def test_format_escalation_message(self):
        """Test formatting escalation message"""
        escalation_data = {
            'alert_log_id': self.alert_log.id,
            'escalation_level': 1,
            'reason': 'No response within SLA'
        }
        
        message = self.service.format_escalation_message(escalation_data)
        
        self.assertIsInstance(message, str)
        self.assertIn('escalation', message.lower())
        self.assertIn('critical', message.lower())
    
    def test_check_escalation_limits(self):
        """Test checking escalation limits"""
        # Should allow escalation
        result = self.service.check_escalation_limits(self.alert_rule, 1)
        self.assertTrue(result['allowed'])
        
        # Should not allow escalation beyond max level
        result = self.service.check_escalation_limits(self.alert_rule, 5)
        self.assertFalse(result['allowed'])
        self.assertIn('reason', result)
    
    def test_get_escalation_history(self):
        """Test getting escalation history"""
        history = self.service.get_escalation_history(self.alert_log)
        
        self.assertIsInstance(history, list)
    
    def test_calculate_escalation_priority(self):
        """Test calculating escalation priority"""
        priority = self.service.calculate_escalation_priority(
            self.alert_rule,
            self.alert_log,
            escalation_level=1
        )
        
        self.assertIsInstance(priority, int)
        self.assertGreater(priority, 0)
        self.assertLessEqual(priority, 100)


class AlertAnalyticsServiceTest(TestCase):
    """Test cases for AlertAnalyticsService"""
    
    def setUp(self):
        self.service = AlertAnalyticsService()
        
        # Create test data
        for i in range(10):
            alert_rule = AlertRule.objects.create(
                name=f'Alert {i}',
                alert_type='cpu_usage' if i % 2 == 0 else 'memory_usage',
                severity='critical' if i % 3 == 0 else 'high' if i % 2 == 0 else 'medium',
                threshold_value=80.0
            )
            
            AlertLog.objects.create(
                rule=alert_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Test alert {i}',
                triggered_at=timezone.now() - timedelta(hours=i),
                is_resolved=i % 3 == 0,
                resolved_at=timezone.now() - timedelta(hours=i-1) if i % 3 == 0 else None
            )
    
    def test_get_alert_statistics(self):
        """Test getting alert statistics"""
        stats = self.service.get_alert_statistics(days=7)
        
        self.assertIn('total_alerts', stats)
        self.assertIn('resolved_alerts', stats)
        self.assertIn('resolution_rate', stats)
        self.assertIn('avg_resolution_time', stats)
        self.assertIn('alerts_by_severity', stats)
        self.assertIn('alerts_by_type', stats)
    
    def test_get_trend_data(self):
        """Test getting trend data"""
        trends = self.service.get_trend_data(days=7)
        
        self.assertIn('daily_trends', trends)
        self.assertIn('hourly_trends', trends)
        self.assertIsInstance(trends['daily_trends'], list)
    
    def test_get_mttr_metrics(self):
        """Test getting MTTR metrics"""
        mttr = self.service.get_mttr_metrics(days=30)
        
        self.assertIn('overall_mttr', mttr)
        self.assertIn('mttr_by_severity', mttr)
        self.assertIn('mttr_trend', mttr)
    
    def test_get_top_alert_rules(self):
        """Test getting top alert rules"""
        top_rules = self.service.get_top_alert_rules(limit=5, days=7)
        
        self.assertIsInstance(top_rules, list)
        self.assertLessEqual(len(top_rules), 5)
        
        for rule in top_rules:
            self.assertIn('rule_name', rule)
            self.assertIn('alert_count', rule)
            self.assertIn('severity', rule)
    
    def test_get_performance_metrics(self):
        """Test getting performance metrics"""
        metrics = self.service.get_performance_metrics(days=7)
        
        self.assertIn('alert_volume', metrics)
        self.assertIn('processing_time', metrics)
        self.assertIn('notification_success_rate', metrics)
        self.assertIn('escalation_rate', metrics)
    
    def test_generate_alert_report(self):
        """Test generating alert report"""
        report_data = self.service.generate_alert_report(
            report_type='daily',
            start_date=timezone.now().date() - timedelta(days=1),
            end_date=timezone.now().date()
        )
        
        self.assertIn('summary', report_data)
        self.assertIn('statistics', report_data)
        self.assertIn('trends', report_data)
        self.assertIn('recommendations', report_data)
    
    def test_calculate_severity_distribution(self):
        """Test calculating severity distribution"""
        distribution = self.service.calculate_severity_distribution(days=7)
        
        self.assertIn('critical', distribution)
        self.assertIn('high', distribution)
        self.assertIn('medium', distribution)
        self.assertIn('low', distribution)
        
        total = sum(distribution.values())
        self.assertGreater(total, 0)
    
    def test_get_resolution_time_percentiles(self):
        """Test getting resolution time percentiles"""
        percentiles = self.service.get_resolution_time_percentiles(days=30)
        
        self.assertIn('p50', percentiles)
        self.assertIn('p90', percentiles)
        self.assertIn('p95', percentiles)
        self.assertIn('p99', percentiles)


class AlertGroupServiceTest(TestCase):
    """Test cases for AlertGroupService"""
    
    def setUp(self):
        self.service = AlertGroupService()
        
        # Create test data
        self.alert_rule1 = AlertRule.objects.create(
            name='CPU Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        self.alert_rule2 = AlertRule.objects.create(
            name='Memory Alert',
            alert_type='memory_usage',
            severity='high',
            threshold_value=85.0
        )
        
        # Create alerts that should be grouped
        base_time = timezone.now() - timedelta(minutes=10)
        for i in range(5):
            AlertLog.objects.create(
                rule=self.alert_rule1 if i % 2 == 0 else self.alert_rule2,
                trigger_value=90.0 + i,
                threshold_value=80.0 if i % 2 == 0 else 85.0,
                message=f'Related alert {i}',
                triggered_at=base_time + timedelta(minutes=i)
            )
    
    def test_group_related_alerts(self):
        """Test grouping related alerts"""
        groups = self.service.group_related_alerts(
            time_window_minutes=15,
            min_group_size=2
        )
        
        self.assertIsInstance(groups, list)
        # Should find at least one group
        self.assertGreater(len(groups), 0)
        
        if groups:
            group = groups[0]
            self.assertIn('group_id', group)
            self.assertIn('alert_ids', group)
            self.assertIn('group_type', group)
            self.assertIn('confidence', group)
    
    def test_detect_alert_patterns(self):
        """Test detecting alert patterns"""
        patterns = self.service.detect_alert_patterns(
            time_window_hours=1,
            min_occurrences=3
        )
        
        self.assertIsInstance(patterns, list)
        # Should detect some patterns
        self.assertGreater(len(patterns), 0)
        
        for pattern in patterns:
            self.assertIn('pattern_type', pattern)
            self.assertIn('alert_rules', pattern)
            self.assertIn('frequency', pattern)
            self.assertIn('confidence', pattern)
    
    def test_create_alert_group(self):
        """Test creating alert group"""
        alert_ids = [1, 2, 3]  # Mock IDs
        group_data = {
            'group_type': 'correlation',
            'name': 'CPU-Memory Correlation',
            'description': 'Related CPU and memory alerts',
            'severity': 'high'
        }
        
        group = self.service.create_alert_group(alert_ids, group_data)
        
        self.assertIn('group_id', group)
        self.assertIn('created_at', group)
    
    def test_update_alert_group(self):
        """Test updating alert group"""
        group_id = 1  # Mock ID
        update_data = {
            'status': 'resolved',
            'resolution_note': 'Issue resolved'
        }
        
        result = self.service.update_alert_group(group_id, update_data)
        
        self.assertTrue(result['success'])
    
    def test_get_group_statistics(self):
        """Test getting group statistics"""
        stats = self.service.get_group_statistics(days=7)
        
        self.assertIn('total_groups', stats)
        self.assertIn('active_groups', stats)
        self.assertIn('resolved_groups', stats)
        self.assertIn('avg_group_size', stats)
    
    def test_get_group_trends(self):
        """Test getting group trends"""
        trends = self.service.get_group_trends(days=7)
        
        self.assertIn('daily_trends', trends)
        self.assertIn('group_types', trends)
        self.assertIn('avg_confidence', trends)
    
    def test_dissolve_group(self):
        """Test dissolving a group"""
        group_id = 1  # Mock ID
        reason = 'Alerts resolved individually'
        
        result = self.service.dissolve_group(group_id, reason)
        
        self.assertTrue(result['success'])
        self.assertIn('dissolved_at', result)


class AlertMaintenanceServiceTest(TestCase):
    """Test cases for AlertMaintenanceService"""
    
    def setUp(self):
        self.service = AlertMaintenanceService()
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0,
            is_active=True
        )
    
    def test_schedule_maintenance(self):
        """Test scheduling maintenance"""
        maintenance_data = {
            'title': 'System Maintenance',
            'description': 'Scheduled system maintenance',
            'start_time': timezone.now() + timedelta(hours=2),
            'end_time': timezone.now() + timedelta(hours=4),
            'maintenance_type': 'scheduled',
            'severity': 'medium',
            'affected_services': ['api', 'database'],
            'alert_rules': [self.alert_rule.id],
            'action': 'suppress'
        }
        
        result = self.service.schedule_maintenance(maintenance_data)
        
        self.assertTrue(result['success'])
        self.assertIn('maintenance_id', result)
        self.assertIn('scheduled_alerts', result)
    
    def test_suppress_alerts_during_maintenance(self):
        """Test suppressing alerts during maintenance"""
        maintenance_id = 1  # Mock ID
        alert_rules = [self.alert_rule.id]
        suppression_reason = 'Maintenance in progress'
        
        result = self.service.suppress_alerts_during_maintenance(
            maintenance_id,
            alert_rules,
            suppression_reason
        )
        
        self.assertTrue(result['success'])
        self.assertIn('suppressed_count', result)
        self.assertIn('suppression_details', result)
    
    def test_extend_maintenance(self):
        """Test extending maintenance"""
        maintenance_id = 1  # Mock ID
        new_end_time = timezone.now() + timedelta(hours=6)
        reason = 'Maintenance taking longer than expected'
        
        result = self.service.extend_maintenance(maintenance_id, new_end_time, reason)
        
        self.assertTrue(result['success'])
        self.assertIn('extended_until', result)
    
    def test_complete_maintenance(self):
        """Test completing maintenance"""
        maintenance_id = 1  # Mock ID
        completion_data = {
            'completion_note': 'Maintenance completed successfully',
            'actual_end_time': timezone.now(),
            'issues_resolved': ['Database connection issue fixed']
        }
        
        result = self.service.complete_maintenance(maintenance_id, completion_data)
        
        self.assertTrue(result['success'])
        self.assertIn('completed_at', result)
    
    def test_get_maintenance_impact(self):
        """Test getting maintenance impact"""
        impact_data = {
            'start_time': timezone.now() + timedelta(hours=2),
            'end_time': timezone.now() + timedelta(hours=4),
            'affected_services': ['api', 'database'],
            'alert_rules': [self.alert_rule.id]
        }
        
        impact = self.service.get_maintenance_impact(impact_data)
        
        self.assertIn('affected_rules', impact)
        self.assertIn('estimated_alerts', impact)
        self.assertIn('affected_services', impact)
        self.assertIn('business_impact', impact)
    
    def test_get_active_maintenance(self):
        """Test getting active maintenance"""
        active_maintenance = self.service.get_active_maintenance()
        
        self.assertIsInstance(active_maintenance, list)
    
    def test_get_maintenance_history(self):
        """Test getting maintenance history"""
        history = self.service.get_maintenance_history(days=30)
        
        self.assertIsInstance(history, list)
        self.assertIn('maintenance_count', history)
        self.assertIn('maintenance_summary', history)
    
    def test_validate_maintenance_schedule(self):
        """Test validating maintenance schedule"""
        valid_schedule = {
            'title': 'Test Maintenance',
            'start_time': timezone.now() + timedelta(hours=1),
            'end_time': timezone.now() + timedelta(hours=3),
            'maintenance_type': 'scheduled',
            'severity': 'medium'
        }
        
        result = self.service.validate_maintenance_schedule(valid_schedule)
        self.assertTrue(result['valid'])
        
        # Invalid schedule - end time before start time
        invalid_schedule = {
            'title': 'Test Maintenance',
            'start_time': timezone.now() + timedelta(hours=3),
            'end_time': timezone.now() + timedelta(hours=1),
            'maintenance_type': 'scheduled',
            'severity': 'medium'
        }
        
        result = self.service.validate_maintenance_schedule(invalid_schedule)
        self.assertFalse(result['valid'])
        self.assertIn('errors', result)
