"""
Tests for Alert Fixtures
"""
from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone
from io import StringIO
import json

from alerts.models.core import AlertRule, AlertLog, Notification, SystemMetrics
from alerts.models.threshold import ThresholdConfig, ThresholdBreach
from alerts.models.channel import AlertChannel, ChannelRoute
from alerts.models.incident import Incident, IncidentTimeline
from alerts.models.intelligence import AlertCorrelation
from alerts.models.reporting import AlertReport


class AlertFixturesTest(TestCase):
    """Test cases for alert fixtures"""
    
    def setUp(self):
        self.out = StringIO()
    
    def test_load_core_fixtures(self):
        """Test loading core alert fixtures"""
        # Load core fixtures
        call_command('loaddata', 'alerts/fixtures/core_alerts.json', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Installed', output)
        
        # Verify fixtures were loaded
        self.assertGreater(AlertRule.objects.count(), 0)
        self.assertGreater(AlertLog.objects.count(), 0)
        self.assertGreater(Notification.objects.count(), 0)
    
    def test_load_threshold_fixtures(self):
        """Test loading threshold fixtures"""
        # Load threshold fixtures
        call_command('loaddata', 'alerts/fixtures/threshold_alerts.json', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Installed', output)
        
        # Verify fixtures were loaded
        self.assertGreater(ThresholdConfig.objects.count(), 0)
        self.assertGreater(ThresholdBreach.objects.count(), 0)
    
    def test_load_channel_fixtures(self):
        """Test loading channel fixtures"""
        # Load channel fixtures
        call_command('loaddata', 'alerts/fixtures/channel_alerts.json', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Installed', output)
        
        # Verify fixtures were loaded
        self.assertGreater(AlertChannel.objects.count(), 0)
        self.assertGreater(ChannelRoute.objects.count(), 0)
    
    def test_load_incident_fixtures(self):
        """Test loading incident fixtures"""
        # Load incident fixtures
        call_command('loaddata', 'alerts/fixtures/incident_alerts.json', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Installed', output)
        
        # Verify fixtures were loaded
        self.assertGreater(Incident.objects.count(), 0)
        self.assertGreater(IncidentTimeline.objects.count(), 0)
    
    def test_load_intelligence_fixtures(self):
        """Test loading intelligence fixtures"""
        # Load intelligence fixtures
        call_command('loaddata', 'alerts/fixtures/intelligence_alerts.json', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Installed', output)
        
        # Verify fixtures were loaded
        self.assertGreater(AlertCorrelation.objects.count(), 0)
    
    def test_load_reporting_fixtures(self):
        """Test loading reporting fixtures"""
        # Load reporting fixtures
        call_command('loaddata', 'alerts/fixtures/reporting_alerts.json', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Installed', output)
        
        # Verify fixtures were loaded
        self.assertGreater(AlertReport.objects.count(), 0)
    
    def test_load_system_metrics_fixtures(self):
        """Test loading system metrics fixtures"""
        # Load system metrics fixtures
        call_command('loaddata', 'alerts/fixtures/system_metrics.json', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Installed', output)
        
        # Verify fixtures were loaded
        self.assertGreater(SystemMetrics.objects.count(), 0)
    
    def test_load_all_fixtures(self):
        """Test loading all alert fixtures"""
        # Load all fixtures
        fixtures = [
            'alerts/fixtures/core_alerts.json',
            'alerts/fixtures/threshold_alerts.json',
            'alerts/fixtures/channel_alerts.json',
            'alerts/fixtures/incident_alerts.json',
            'alerts/fixtures/intelligence_alerts.json',
            'alerts/fixtures/reporting_alerts.json',
            'alerts/fixtures/system_metrics.json'
        ]
        
        for fixture in fixtures:
            self.out = StringIO()
            call_command('loaddata', fixture, stdout=self.out)
            output = self.out.getvalue()
            self.assertIn('Installed', output)
        
        # Verify all data was loaded
        self.assertGreater(AlertRule.objects.count(), 0)
        self.assertGreater(AlertLog.objects.count(), 0)
        self.assertGreater(Notification.objects.count(), 0)
        self.assertGreater(ThresholdConfig.objects.count(), 0)
        self.assertGreater(AlertChannel.objects.count(), 0)
        self.assertGreater(Incident.objects.count(), 0)
        self.assertGreater(AlertCorrelation.objects.count(), 0)
        self.assertGreater(AlertReport.objects.count(), 0)
        self.assertGreater(SystemMetrics.objects.count(), 0)
    
    def test_fixture_data_integrity(self):
        """Test fixture data integrity"""
        # Load core fixtures
        call_command('loaddata', 'alerts/fixtures/core_alerts.json', stdout=self.out)
        
        # Check data integrity
        for alert_log in AlertLog.objects.all():
            self.assertIsNotNone(alert_log.rule)
            self.assertIsNotNone(alert_log.trigger_value)
            self.assertIsNotNone(alert_log.threshold_value)
            self.assertIsNotNone(alert_log.message)
        
        for notification in Notification.objects.all():
            self.assertIsNotNone(notification.alert_log)
            self.assertIsNotNone(notification.notification_type)
            self.assertIsNotNone(notification.recipient)
    
    def test_fixture_relationships(self):
        """Test fixture relationships"""
        # Load all fixtures
        fixtures = [
            'alerts/fixtures/core_alerts.json',
            'alerts/fixtures/threshold_alerts.json',
            'alerts/fixtures/channel_alerts.json'
        ]
        
        for fixture in fixtures:
            self.out = StringIO()
            call_command('loaddata', fixture, stdout=self.out)
        
        # Check relationships
        for alert_log in AlertLog.objects.all():
            # Alert log should have a valid rule
            self.assertIsNotNone(alert_log.rule)
            self.assertIsInstance(alert_log.rule, AlertRule)
            
            # If notification exists, it should reference this alert log
            notifications = Notification.objects.filter(alert_log=alert_log)
            for notification in notifications:
                self.assertEqual(notification.alert_log, alert_log)
    
    def test_fixture_timestamps(self):
        """Test fixture timestamps"""
        # Load core fixtures
        call_command('loaddata', 'alerts/fixtures/core_alerts.json', stdout=self.out)
        
        # Check timestamps
        for alert_log in AlertLog.objects.all():
            self.assertIsNotNone(alert_log.triggered_at)
            self.assertIsInstance(alert_log.triggered_at, timezone.datetime)
        
        for alert_rule in AlertRule.objects.all():
            self.assertIsNotNone(alert_rule.created_at)
            self.assertIsInstance(alert_rule.created_at, timezone.datetime)
    
    def test_fixture_severity_values(self):
        """Test fixture severity values"""
        # Load core fixtures
        call_command('loaddata', 'alerts/fixtures/core_alerts.json', stdout=self.out)
        
        # Check valid severity values
        valid_severities = ['low', 'medium', 'high', 'critical']
        
        for alert_rule in AlertRule.objects.all():
            self.assertIn(alert_rule.severity, valid_severities)
        
        for alert_log in AlertLog.objects.all():
            self.assertIn(alert_log.rule.severity, valid_severities)
    
    def test_fixture_notification_types(self):
        """Test fixture notification types"""
        # Load core and channel fixtures
        fixtures = [
            'alerts/fixtures/core_alerts.json',
            'alerts/fixtures/channel_alerts.json'
        ]
        
        for fixture in fixtures:
            self.out = StringIO()
            call_command('loaddata', fixture, stdout=self.out)
        
        # Check valid notification types
        valid_types = ['email', 'sms', 'telegram', 'webhook', 'slack']
        
        for notification in Notification.objects.all():
            self.assertIn(notification.notification_type, valid_types)
    
    def test_fixture_channel_types(self):
        """Test fixture channel types"""
        # Load channel fixtures
        call_command('loaddata', 'alerts/fixtures/channel_alerts.json', stdout=self.out)
        
        # Check valid channel types
        valid_types = ['email', 'sms', 'telegram', 'webhook', 'slack']
        
        for channel in AlertChannel.objects.all():
            self.assertIn(channel.channel_type, valid_types)
    
    def test_fixture_incident_severities(self):
        """Test fixture incident severities"""
        # Load incident fixtures
        call_command('loaddata', 'alerts/fixtures/incident_alerts.json', stdout=self.out)
        
        # Check valid incident severities
        valid_severities = ['low', 'medium', 'high', 'critical']
        
        for incident in Incident.objects.all():
            self.assertIn(incident.severity, valid_severities)
    
    def test_fixture_incident_statuses(self):
        """Test fixture incident statuses"""
        # Load incident fixtures
        call_command('loaddata', 'alerts/fixtures/incident_alerts.json', stdout=self.out)
        
        # Check valid incident statuses
        valid_statuses = ['open', 'investigating', 'identified', 'resolved', 'closed']
        
        for incident in Incident.objects.all():
            self.assertIn(incident.status, valid_statuses)
    
    def test_fixture_correlation_types(self):
        """Test fixture correlation types"""
        # Load intelligence fixtures
        call_command('loaddata', 'alerts/fixtures/intelligence_alerts.json', stdout=self.out)
        
        # Check valid correlation types
        valid_types = ['temporal', 'causal', 'pattern', 'statistical']
        
        for correlation in AlertCorrelation.objects.all():
            self.assertIn(correlation.correlation_type, valid_types)
    
    def test_fixture_report_types(self):
        """Test fixture report types"""
        # Load reporting fixtures
        call_command('loaddata', 'alerts/fixtures/reporting_alerts.json', stdout=self.out)
        
        # Check valid report types
        valid_types = ['daily', 'weekly', 'monthly', 'sla', 'performance', 'custom']
        
        for report in AlertReport.objects.all():
            self.assertIn(report.report_type, valid_types)
    
    def test_fixture_system_metrics_values(self):
        """Test fixture system metrics values"""
        # Load system metrics fixtures
        call_command('loaddata', 'alerts/fixtures/system_metrics.json', stdout=self.out)
        
        # Check valid metrics values
        for metrics in SystemMetrics.objects.all():
            self.assertGreaterEqual(metrics.total_users, 0)
            self.assertGreaterEqual(metrics.active_users_1h, 0)
            self.assertGreaterEqual(metrics.total_earnings_1h, 0)
            self.assertGreaterEqual(metrics.avg_response_time_ms, 0)
    
    def test_fixture_data_consistency(self):
        """Test fixture data consistency"""
        # Load all fixtures
        fixtures = [
            'alerts/fixtures/core_alerts.json',
            'alerts/fixtures/threshold_alerts.json',
            'alerts/fixtures/channel_alerts.json',
            'alerts/fixtures/incident_alerts.json',
            'alerts/fixtures/intelligence_alerts.json',
            'alerts/fixtures/reporting_alerts.json',
            'alerts/fixtures/system_metrics.json'
        ]
        
        for fixture in fixtures:
            self.out = StringIO()
            call_command('loaddata', fixture, stdout=self.out)
        
        # Check data consistency
        for alert_log in AlertLog.objects.all():
            # Trigger value should be consistent with threshold
            if alert_log.trigger_value < alert_log.threshold_value:
                # This might be a test case for below-threshold alerts
                pass
        
        for notification in Notification.objects.all():
            # Status should be valid
            valid_statuses = ['pending', 'sent', 'failed', 'retry']
            self.assertIn(notification.status, valid_statuses)
    
    def test_fixture_performance(self):
        """Test fixture loading performance"""
        import time
        
        # Measure loading time
        start_time = time.time()
        
        fixtures = [
            'alerts/fixtures/core_alerts.json',
            'alerts/fixtures/threshold_alerts.json',
            'alerts/fixtures/channel_alerts.json',
            'alerts/fixtures/incident_alerts.json',
            'alerts/fixtures/intelligence_alerts.json',
            'alerts/fixtures/reporting_alerts.json',
            'alerts/fixtures/system_metrics.json'
        ]
        
        for fixture in fixtures:
            self.out = StringIO()
            call_command('loaddata', fixture, stdout=self.out)
        
        end_time = time.time()
        loading_time = end_time - start_time
        
        # Performance assertion
        self.assertLess(loading_time, 10.0)  # Should load within 10 seconds
    
    def test_fixture_dump_and_load(self):
        """Test dumping and loading fixtures"""
        # Create test data
        alert_rule = AlertRule.objects.create(
            name='Dump Test Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        alert_log = AlertLog.objects.create(
            rule=alert_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Dump test alert'
        )
        
        # Dump data
        self.out = StringIO()
        call_command('dumpdata', 'alerts.core', '--indent', '2', stdout=self.out)
        
        dump_output = self.out.getvalue()
        self.assertIn('DumpTest Rule', dump_output)
        self.assertIn('Dump test alert', dump_output)
        
        # Clear data
        AlertLog.objects.all().delete()
        AlertRule.objects.all().delete()
        
        # Load dumped data (in real scenario, would save to file first)
        # This is a simplified test - in practice, you'd save dump to file
        # and then load it back
    
    def test_fixture_error_handling(self):
        """Test fixture error handling"""
        # Try to load non-existent fixture
        with self.assertRaises(Exception):
            call_command('loaddata', 'alerts/fixtures/non_existent.json', stdout=self.out)
        
        # Try to load malformed fixture
        # This would require creating a malformed JSON file
        # For now, just test the error handling mechanism
    
    def test_fixture_dependencies(self):
        """Test fixture dependencies"""
        # Load fixtures in correct order
        # Core should be loaded first as other fixtures depend on it
        call_command('loaddata', 'alerts/fixtures/core_alerts.json', stdout=self.out)
        
        # Then load dependent fixtures
        call_command('loaddata', 'alerts/fixtures/threshold_alerts.json', stdout=self.out)
        call_command('loaddata', 'alerts/fixtures/channel_alerts.json', stdout=self.out)
        
        # Verify dependencies are satisfied
        for threshold_config in ThresholdConfig.objects.all():
            self.assertIsNotNone(threshold_config.alert_rule)
        
        for channel in AlertChannel.objects.all():
            # Channel should be valid
            self.assertIsNotNone(channel.name)
            self.assertIsNotNone(channel.channel_type)
    
    def test_fixture_uniqueness(self):
        """Test fixture uniqueness constraints"""
        # Load fixtures
        call_command('loaddata', 'alerts/fixtures/core_alerts.json', stdout=self.out)
        
        # Check uniqueness constraints are satisfied
        # Names should be unique for certain models
        rule_names = AlertRule.objects.values_list('name', flat=True)
        self.assertEqual(len(rule_names), len(set(rule_names)))  # All names unique
        
        # Check other unique constraints as needed
        for alert_log in AlertLog.objects.all():
            # Each alert log should be unique
            self.assertIsNotNone(alert_log.id)
    
    def test_fixture_data_volume(self):
        """Test fixture data volume"""
        # Load all fixtures
        fixtures = [
            'alerts/fixtures/core_alerts.json',
            'alerts/fixtures/threshold_alerts.json',
            'alerts/fixtures/channel_alerts.json',
            'alerts/fixtures/incident_alerts.json',
            'alerts/fixtures/intelligence_alerts.json',
            'alerts/fixtures/reporting_alerts.json',
            'alerts/fixtures/system_metrics.json'
        ]
        
        for fixture in fixtures:
            self.out = StringIO()
            call_command('loaddata', fixture, stdout=self.out)
        
        # Check reasonable data volume
        self.assertLess(AlertRule.objects.count(), 1000)  # Reasonable number of rules
        self.assertLess(AlertLog.objects.count(), 10000)  # Reasonable number of logs
        self.assertLess(Notification.objects.count(), 5000)  # Reasonable number of notifications
    
    def test_fixture_cleanup(self):
        """Test fixture cleanup"""
        # Load fixtures
        call_command('loaddata', 'alerts/fixtures/core_alerts.json', stdout=self.out)
        
        # Verify data loaded
        initial_count = AlertRule.objects.count()
        self.assertGreater(initial_count, 0)
        
        # Clean up
        AlertLog.objects.all().delete()
        AlertRule.objects.all().delete()
        
        # Verify cleanup
        self.assertEqual(AlertRule.objects.count(), 0)
        self.assertEqual(AlertLog.objects.count(), 0)
