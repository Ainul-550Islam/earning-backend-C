"""
Tests for Core Tasks
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
import json

from alerts.models.core import AlertRule, AlertLog, Notification
from alerts.tasks.core import (
    ProcessAlertsTask, EscalateAlertsTask, GenerateReportsTask,
    CleanupAlertsTask, CheckHealthTask
)


class ProcessAlertsTaskTest(TestCase):
    """Test cases for ProcessAlertsTask"""
    
    def setUp(self):
        self.task = ProcessAlertsTask()
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0,
            is_active=True
        )
    
    def test_process_pending_alerts(self):
        """Test processing pending alerts"""
        # Create some alerts
        for i in range(5):
            AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Alert {i}'
            )
        
        result = self.task.process_pending_alerts(
            limit=10,
            severity_filter=None,
            dry_run=False
        )
        
        self.assertIn('processed_count', result)
        self.assertIn('notifications_sent', result)
        self.assertIn('errors', result)
        self.assertGreater(result['processed_count'], 0)
    
    def test_process_pending_alerts_dry_run(self):
        """Test processing pending alerts with dry run"""
        AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Test alert'
        )
        
        result = self.task.process_pending_alerts(
            limit=10,
            severity_filter=None,
            dry_run=True
        )
        
        self.assertIn('would_process', result)
        self.assertIn('would_send_notifications', result)
        self.assertIn('dry_run', result)
        self.assertTrue(result['dry_run'])
    
    def test_process_pending_alerts_with_severity_filter(self):
        """Test processing pending alerts with severity filter"""
        # Create alerts with different severities
        high_rule = AlertRule.objects.create(
            name='High Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        low_rule = AlertRule.objects.create(
            name='Low Alert',
            alert_type='cpu_usage',
            severity='low',
            threshold_value=80.0
        )
        
        AlertLog.objects.create(rule=high_rule, trigger_value=85.0, threshold_value=80.0, message='High alert')
        AlertLog.objects.create(rule=low_rule, trigger_value=85.0, threshold_value=80.0, message='Low alert')
        
        result = self.task.process_pending_alerts(
            limit=10,
            severity_filter='high',
            dry_run=False
        )
        
        self.assertEqual(result['processed_count'], 1)
    
    def test_process_single_alert(self):
        """Test processing single alert"""
        alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Test alert'
        )
        
        result = self.task.process_single_alert(alert.id)
        
        self.assertIn('success', result)
        self.assertIn('notifications', result)
        self.assertIn('processing_time', result)
    
    def test_get_alert_statistics(self):
        """Test getting alert statistics"""
        # Create some alerts
        for i in range(10):
            AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Alert {i}'
            )
        
        stats = self.task.get_alert_statistics(hours=24)
        
        self.assertIn('total_alerts', stats)
        self.assertIn('pending_alerts', stats)
        self.assertIn('resolved_alerts', stats)
        self.assertIn('by_severity', stats)
    
    def test_validate_alert_data(self):
        """Test validating alert data"""
        valid_alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Valid alert'
        )
        
        result = self.task.validate_alert_data(valid_alert.id)
        
        self.assertTrue(result['valid'])
        self.assertIn('validation_time', result)
    
    def test_format_notification_message(self):
        """Test formatting notification message"""
        alert = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='CPU usage is high',
            details={'current_usage': 85.0}
        )
        
        message = self.task.format_notification_message(alert.id)
        
        self.assertIsInstance(message, str)
        self.assertIn('CPU usage is high', message)
        self.assertIn('85.0', message)


class EscalateAlertsTaskTest(TestCase):
    """Test cases for EscalateAlertsTask"""
    
    def setUp(self):
        self.task = EscalateAlertsTask()
        
        self.alert_rule = AlertRule.objects.create(
            name='Critical Alert',
            alert_type='system_error',
            severity='critical',
            threshold_value=1.0,
            escalation_enabled=True,
            escalation_delay_minutes=15
        )
        
        # Create an old alert that should be escalated
        self.alert_log = AlertLog.objects.create(
            rule=self.alert_rule,
            trigger_value=1.0,
            threshold_value=1.0,
            message='Critical system error',
            triggered_at=timezone.now() - timedelta(minutes=30)
        )
    
    def test_check_and_escalate_alerts(self):
        """Test checking and escalating alerts"""
        result = self.task.check_and_escalate_alerts(
            hours_back=24,
            dry_run=False
        )
        
        self.assertIn('alerts_checked', result)
        self.assertIn('alerts_escalated', result)
        self.assertIn('notifications_sent', result)
    
    def test_check_and_escalate_alerts_dry_run(self):
        """Test checking and escalating alerts with dry run"""
        result = self.task.check_and_escalate_alerts(
            hours_back=24,
            dry_run=True
        )
        
        self.assertIn('would_escalate', result)
        self.assertIn('dry_run', result)
        self.assertTrue(result['dry_run'])
    
    def test_escalate_single_alert(self):
        """Test escalating single alert"""
        result = self.task.escalate_single_alert(
            self.alert_log.id,
            escalation_level=1,
            reason='No response within SLA'
        )
        
        self.assertIn('success', result)
        self.assertIn('escalation_id', result)
        self.assertIn('notifications_sent', result)
    
    def test_get_escalation_candidates(self):
        """Test getting escalation candidates"""
        candidates = self.task.get_escalation_candidates(hours_back=24)
        
        self.assertIsInstance(candidates, list)
        # Should include our old alert
        self.assertGreater(len(candidates), 0)
    
    def test_calculate_escalation_priority(self):
        """Test calculating escalation priority"""
        priority = self.task.calculate_escalation_priority(
            self.alert_log,
            escalation_level=1
        )
        
        self.assertIsInstance(priority, int)
        self.assertGreater(priority, 0)
        self.assertLessEqual(priority, 100)
    
    def test_format_escalation_message(self):
        """Test formatting escalation message"""
        message = self.task.format_escalation_message(
            self.alert_log.id,
            escalation_level=1,
            reason='No response within SLA'
        )
        
        self.assertIsInstance(message, str)
        self.assertIn('escalation', message.lower())
        self.assertIn('critical', message.lower())
    
    def test_get_escalation_statistics(self):
        """Test getting escalation statistics"""
        stats = self.task.get_escalation_statistics(days=7)
        
        self.assertIn('total_escalations', stats)
        self.assertIn('escalations_by_level', stats)
        self.assertIn('escalations_by_severity', stats)
        self.assertIn('avg_escalation_time', stats)


class GenerateReportsTaskTest(TestCase):
    """Test cases for GenerateReportsTask"""
    
    def setUp(self):
        self.task = GenerateReportsTask()
        
        # Create some test data
        for i in range(10):
            AlertRule.objects.create(
                name=f'Alert {i}',
                alert_type='cpu_usage',
                severity='high' if i % 2 == 0 else 'medium',
                threshold_value=80.0
            )
            
            AlertLog.objects.create(
                rule=AlertRule.objects.get(name=f'Alert {i}'),
                trigger_value=85.0,
                threshold_value=80.0,
                message=f'Test alert {i}'
            )
    
    def test_generate_daily_report(self):
        """Test generating daily report"""
        result = self.task.generate_daily_report(
            date=timezone.now().date(),
            format_type='json',
            recipients=['admin@example.com']
        )
        
        self.assertIn('report_id', result)
        self.assertIn('generated_at', result)
        self.assertIn('record_count', result)
        self.assertIn('file_path', result)
    
    def test_generate_weekly_report(self):
        """Test generating weekly report"""
        result = self.task.generate_weekly_report(
            week_start=timezone.now().date() - timezone.timedelta(days=7),
            format_type='pdf',
            recipients=['team@example.com']
        )
        
        self.assertIn('report_id', result)
        self.assertIn('generated_at', result)
        self.assertIn('record_count', result)
    
    def test_generate_monthly_report(self):
        """Test generating monthly report"""
        result = self.task.generate_monthly_report(
            month=timezone.now().date().replace(day=1),
            format_type='xlsx',
            recipients=['management@example.com']
        )
        
        self.assertIn('report_id', result)
        self.assertIn('generated_at', result)
        self.assertIn('record_count', result)
    
    def test_generate_sla_report(self):
        """Test generating SLA report"""
        result = self.task.generate_sla_report(
            start_date=timezone.now().date() - timezone.timedelta(days=30),
            end_date=timezone.now().date(),
            format_type='json'
        )
        
        self.assertIn('report_id', result)
        self.assertIn('generated_at', result)
        self.assertIn('sla_metrics', result)
    
    def test_generate_performance_report(self):
        """Test generating performance report"""
        result = self.task.generate_performance_report(
            start_date=timezone.now().date() - timezone.timedelta(days=7),
            end_date=timezone.now().date(),
            format_type='json'
        )
        
        self.assertIn('report_id', result)
        self.assertIn('generated_at', result)
        self.assertIn('performance_metrics', result)
    
    def test_distribute_report(self):
        """Test distributing report"""
        result = self.task.distribute_report(
            report_id=1,  # Mock ID
            recipients=['admin@example.com', 'ops@example.com']
        )
        
        self.assertIn('distributed', result)
        self.assertIn('recipients', result)
        self.assertIn('sent_count', result)
    
    def test_get_report_statistics(self):
        """Test getting report statistics"""
        stats = self.task.get_report_statistics(days=30)
        
        self.assertIn('total_reports', stats)
        self.assertIn('reports_by_type', stats)
        self.assertIn('avg_generation_time', stats)
        self.assertIn('distribution_success_rate', stats)


class CleanupAlertsTaskTest(TestCase):
    """Test cases for CleanupAlertsTask"""
    
    def setUp(self):
        self.task = CleanupAlertsTask()
        
        # Create old data for cleanup
        old_date = timezone.now() - timedelta(days=100)
        
        # Create old alerts
        for i in range(10):
            AlertLog.objects.create(
                rule=AlertRule.objects.create(
                    name=f'Old Alert {i}',
                    alert_type='cpu_usage',
                    severity='medium',
                    threshold_value=80.0
                ),
                trigger_value=85.0,
                threshold_value=80.0,
                message=f'Old alert {i}',
                triggered_at=old_date
            )
    
    def test_cleanup_old_alerts(self):
        """Test cleaning up old alerts"""
        initial_count = AlertLog.objects.count()
        
        result = self.task.cleanup_old_alerts(
            days=90,
            batch_size=5,
            dry_run=False
        )
        
        self.assertIn('deleted_count', result)
        self.assertIn('batches_processed', result)
        self.assertLess(AlertLog.objects.count(), initial_count)
    
    def test_cleanup_old_alerts_dry_run(self):
        """Test cleaning up old alerts with dry run"""
        result = self.task.cleanup_old_alerts(
            days=90,
            batch_size=5,
            dry_run=True
        )
        
        self.assertIn('would_delete', result)
        self.assertIn('dry_run', result)
        self.assertTrue(result['dry_run'])
        
        # Should not actually delete anything
        self.assertEqual(AlertLog.objects.count(), 10)
    
    def test_cleanup_old_notifications(self):
        """Test cleaning up old notifications"""
        # Create old notifications
        old_date = timezone.now() - timedelta(days=100)
        
        for i in range(5):
            Notification.objects.create(
                alert_log=AlertLog.objects.first(),
                notification_type='email',
                recipient='test@example.com',
                status='sent',
                created_at=old_date
            )
        
        initial_count = Notification.objects.count()
        
        result = self.task.cleanup_old_notifications(
            days=90,
            dry_run=False
        )
        
        self.assertIn('deleted_count', result)
        self.assertLess(Notification.objects.count(), initial_count)
    
    def test_cleanup_old_health_logs(self):
        """Test cleaning up old health logs"""
        from alerts.models.channel import ChannelHealthLog, AlertChannel
        
        # Create channel and old health logs
        channel = AlertChannel.objects.create(
            name='Test Channel',
            channel_type='email',
            is_enabled=True
        )
        
        old_date = timezone.now() - timedelta(days=100)
        
        for i in range(3):
            ChannelHealthLog.objects.create(
                channel=channel,
                check_name='connectivity',
                check_type='connectivity',
                status='healthy',
                checked_at=old_date
            )
        
        initial_count = ChannelHealthLog.objects.count()
        
        result = self.task.cleanup_old_health_logs(
            days=90,
            dry_run=False
        )
        
        self.assertIn('deleted_count', result)
        self.assertLess(ChannelHealthLog.objects.count(), initial_count)
    
    def test_cleanup_old_timeline_events(self):
        """Test cleaning up old timeline events"""
        from alerts.models.incident import Incident, IncidentTimeline
        
        # Create incident and old timeline events
        incident = Incident.objects.create(
            title='Old Incident',
            severity='medium',
            status='resolved',
            detected_at=timezone.now() - timedelta(days=100)
        )
        
        old_date = timezone.now() - timedelta(days=100)
        
        for i in range(3):
            IncidentTimeline.objects.create(
                incident=incident,
                event_type='status_change',
                title='Old event',
                timestamp=old_date
            )
        
        initial_count = IncidentTimeline.objects.count()
        
        result = self.task.cleanup_old_timeline_events(
            days=90,
            dry_run=False
        )
        
        self.assertIn('deleted_count', result)
        self.assertLess(IncidentTimeline.objects.count(), initial_count)
    
    def test_get_cleanup_statistics(self):
        """Test getting cleanup statistics"""
        stats = self.task.get_cleanup_statistics()
        
        self.assertIn('total_alerts', stats)
        self.assertIn('old_alerts', stats)
        self.assertIn('total_notifications', stats)
        self.assertIn('old_notifications', stats)
        self.assertIn('estimated_space_savings', stats)


class CheckHealthTaskTest(TestCase):
    """Test cases for CheckHealthTask"""
    
    def setUp(self):
        self.task = CheckHealthTask()
        
        # Create some test data
        for i in range(5):
            AlertRule.objects.create(
                name=f'Alert {i}',
                alert_type='cpu_usage',
                severity='high' if i % 2 == 0 else 'medium',
                threshold_value=80.0,
                is_active=i % 3 != 0  # Some inactive
            )
    
    def test_check_alert_system_health(self):
        """Test checking alert system health"""
        result = self.task.check_alert_system_health(
            time_period_hours=24,
            verbose=True
        )
        
        self.assertIn('overall_health', result)
        self.assertIn('alerts_health', result)
        self.assertIn('rules_health', result)
        self.assertIn('notifications_health', result)
        self.assertIn('timestamp', result)
    
    def test_check_channel_health(self):
        """Test checking channel health"""
        from alerts.models.channel import AlertChannel
        
        # Create test channels
        for i in range(3):
            AlertChannel.objects.create(
                name=f'Channel {i}',
                channel_type='email',
                is_enabled=i % 2 == 0,
                status='active' if i % 2 == 0 else 'inactive'
            )
        
        result = self.task.check_channel_health(
            time_period_hours=24,
            verbose=True
        )
        
        self.assertIn('overall_health', result)
        self.assertIn('channel_details', result)
        self.assertIn('health_summary', result)
    
    def test_check_incident_system_health(self):
        """Test checking incident system health"""
        from alerts.models.incident import Incident
        
        # Create test incidents
        for i in range(3):
            Incident.objects.create(
                title=f'Incident {i}',
                severity='high' if i % 2 == 0 else 'medium',
                status='open' if i % 2 == 0 else 'resolved',
                detected_at=timezone.now() - timedelta(hours=i * 4)
            )
        
        result = self.task.check_incident_system_health(
            time_period_hours=24,
            verbose=True
        )
        
        self.assertIn('overall_health', result)
        self.assertIn('incident_details', result)
        self.assertIn('resolution_metrics', result)
    
    def test_check_system_metrics(self):
        """Test checking system metrics"""
        from alerts.models.core import SystemMetrics
        
        # Create some metrics
        for i in range(5):
            SystemMetrics.objects.create(
                total_users=1000 + i * 100,
                active_users_1h=500 + i * 50,
                total_earnings_1h=1000.0 + i * 100,
                avg_response_time_ms=200.0 + i * 20,
                timestamp=timezone.now() - timedelta(hours=i)
            )
        
        result = self.task.check_system_metrics(
            time_period_hours=24,
            verbose=True
        )
        
        self.assertIn('metrics_health', result)
        self.assertIn('performance_trends', result)
        self.assertIn('anomalies_detected', result)
    
    def test_generate_health_report(self):
        """Test generating health report"""
        result = self.task.generate_health_report(
            time_period_hours=24,
            output_format='json',
            save_results=True
        )
        
        self.assertIn('report_id', result)
        self.assertIn('generated_at', result)
        self.assertIn('health_summary', result)
        self.assertIn('file_path', result)
    
    def test_get_health_trends(self):
        """Test getting health trends"""
        trends = self.task.get_health_trends(days=7)
        
        self.assertIn('overall_trend', trends)
        self.assertIn('component_trends', trends)
        self.assertIn('health_score_history', trends)
        self.assertIn('recommendations', trends)
    
    def test_identify_health_issues(self):
        """Test identifying health issues"""
        issues = self.task.identify_health_issues(
            time_period_hours=24,
            severity_threshold='medium'
        )
        
        self.assertIn('critical_issues', issues)
        self.assertIn('warning_issues', issues)
        self.assertIn('info_issues', issues)
        self.assertIn('total_issues', issues)
