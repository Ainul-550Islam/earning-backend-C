"""
Tests for Management Commands
"""
from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from io import StringIO
import json

from alerts.models.core import AlertRule, AlertLog, Notification, SystemMetrics
from alerts.management.commands.process_alerts import Command as ProcessAlertsCommand
from alerts.management.commands.generate_reports import Command as GenerateReportsCommand
from alerts.management.commands.cleanup_alerts import Command as CleanupAlertsCommand
from alerts.management.commands.test_alerts import Command as TestAlertsCommand
from alerts.management.commands.check_health import Command as CheckHealthCommand


class ProcessAlertsCommandTest(TestCase):
    """Test cases for ProcessAlertsCommand"""
    
    def setUp(self):
        self.command = ProcessAlertsCommand()
        self.out = StringIO()
        
        # Create test data
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert Rule',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0,
            is_active=True
        )
        
        # Create pending alerts
        for i in range(5):
            AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=85.0 + i,
                threshold_value=80.0,
                message=f'Alert {i}'
            )
    
    def test_process_alerts_command_basic(self):
        """Test basic process_alerts command"""
        call_command('process_alerts', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Processing pending alerts', output)
        self.assertIn('Processed', output)
        self.assertIn('notifications sent', output)
    
    def test_process_alerts_with_limit(self):
        """Test process_alerts command with limit"""
        call_command('process_alerts', '--limit', '3', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Processing pending alerts', output)
        self.assertIn('Limit: 3', output)
    
    def test_process_alerts_dry_run(self):
        """Test process_alerts command with dry run"""
        call_command('process_alerts', '--dry-run', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('DRY RUN', output)
        self.assertIn('Would process', output)
        self.assertIn('Would send', output)
    
    def test_process_alerts_with_severity_filter(self):
        """Test process_alerts command with severity filter"""
        call_command('process_alerts', '--severity', 'high', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Severity filter: high', output)
    
    def test_process_alerts_with_time_filter(self):
        """Test process_alerts command with time filter"""
        call_command('process_alerts', '--hours', '24', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Time filter: last 24 hours', output)
    
    def test_process_alerts_force_processing(self):
        """Test process_alerts command with force processing"""
        call_command('process_alerts', '--force', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Force processing enabled', output)
    
    def test_process_alerts_no_pending_alerts(self):
        """Test process_alerts command with no pending alerts"""
        # Clear all alerts
        AlertLog.objects.all().delete()
        
        call_command('process_alerts', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('No pending alerts found', output)
    
    def test_process_alerts_command_error_handling(self):
        """Test process_alerts command error handling"""
        # Create invalid alert rule
        invalid_rule = AlertRule.objects.create(
            name='Invalid Rule',
            alert_type='invalid_type',
            severity='high',
            threshold_value=80.0,
            is_active=False  # Inactive rule
        )
        
        AlertLog.objects.create(
            rule=invalid_rule,
            trigger_value=85.0,
            threshold_value=80.0,
            message='Invalid alert'
        )
        
        call_command('process_alerts', stdout=self.out)
        
        output = self.out.getvalue()
        # Should handle errors gracefully
        self.assertIn('Processing complete', output)


class GenerateReportsCommandTest(TestCase):
    """Test cases for GenerateReportsCommand"""
    
    def setUp(self):
        self.command = GenerateReportsCommand()
        self.out = StringIO()
        
        # Create test data
        for i in range(10):
            AlertRule.objects.create(
                name=f'Alert {i}',
                alert_type='cpu_usage' if i % 2 == 0 else 'memory_usage',
                severity='high' if i % 3 == 0 else 'medium',
                threshold_value=80.0
            )
            
            AlertLog.objects.create(
                rule=AlertRule.objects.get(name=f'Alert {i}'),
                trigger_value=85.0,
                threshold_value=80.0,
                message=f'Alert {i}'
            )
    
    def test_generate_daily_report(self):
        """Test generate daily report"""
        call_command('generate_reports', 'daily', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Generating daily report', output)
        self.assertIn('Report generated', output)
        self.assertIn('Record count:', output)
    
    def test_generate_weekly_report(self):
        """Test generate weekly report"""
        call_command('generate_reports', 'weekly', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Generating weekly report', output)
        self.assertIn('Report generated', output)
    
    def test_generate_monthly_report(self):
        """Test generate monthly report"""
        call_command('generate_reports', 'monthly', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Generating monthly report', output)
        self.assertIn('Report generated', output)
    
    def test_generate_sla_report(self):
        """Test generate SLA report"""
        call_command('generate_reports', 'sla', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Generating SLA report', output)
        self.assertIn('SLA metrics', output)
    
    def test_generate_performance_report(self):
        """Test generate performance report"""
        call_command('generate_reports', 'performance', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Generating performance report', output)
        self.assertIn('Performance metrics', output)
    
    def test_generate_report_with_date(self):
        """Test generate report with specific date"""
        from datetime import date
        test_date = date.today()
        
        call_command('generate_reports', 'daily', '--date', test_date.isoformat(), stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn(f'Date: {test_date}', output)
    
    def test_generate_report_with_format(self):
        """Test generate report with specific format"""
        call_command('generate_reports', 'daily', '--format', 'json', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Format: json', output)
    
    def test_generate_report_with_recipients(self):
        """Test generate report with recipients"""
        recipients = 'admin@example.com,ops@example.com'
        
        call_command('generate_reports', 'daily', '--recipients', recipients, stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Recipients:', output)
        self.assertIn('admin@example.com', output)
    
    def test_generate_report_auto_distribute(self):
        """Test generate report with auto distribute"""
        call_command('generate_reports', 'daily', '--auto-distribute', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Auto distribute: Yes', output)
    
    def test_generate_report_invalid_type(self):
        """Test generate report with invalid type"""
        with self.assertRaises(CommandError):
            call_command('generate_reports', 'invalid_type', stdout=self.out)


class CleanupAlertsCommandTest(TestCase):
    """Test cases for CleanupAlertsCommand"""
    
    def setUp(self):
        self.command = CleanupAlertsCommand()
        self.out = StringIO()
        
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
    
    def test_cleanup_alerts_basic(self):
        """Test basic cleanup alerts command"""
        initial_count = AlertLog.objects.count()
        
        call_command('cleanup_alerts', '--days', '90', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Cleaning up old alert data', output)
        self.assertIn('Deleted', output)
        self.assertIn('alerts', output)
        
        # Check that alerts were deleted
        self.assertLess(AlertLog.objects.count(), initial_count)
    
    def test_cleanup_alerts_dry_run(self):
        """Test cleanup alerts with dry run"""
        initial_count = AlertLog.objects.count()
        
        call_command('cleanup_alerts', '--days', '90', '--dry-run', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('DRY RUN', output)
        self.assertIn('Would delete', output)
        
        # Should not actually delete anything
        self.assertEqual(AlertLog.objects.count(), initial_count)
    
    def test_cleanup_alerts_with_batch_size(self):
        """Test cleanup alerts with batch size"""
        call_command('cleanup_alerts', '--days', '90', '--batch-size', '5', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Batch size: 5', output)
        self.assertIn('Batches processed:', output)
    
    def test_cleanup_alerts_specific_data_type(self):
        """Test cleanup alerts for specific data type"""
        call_command('cleanup_alerts', '--days', '90', '--data-type', 'alerts', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Data type: alerts', output)
    
    def test_cleanup_alerts_all_data_types(self):
        """Test cleanup alerts for all data types"""
        call_command('cleanup_alerts', '--days', '90', '--data-type', 'all', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Data type: all', output)
        self.assertIn('alerts', output)
        self.assertIn('notifications', output)
        self.assertIn('health_logs', output)
    
    def test_cleanup_alerts_with_exclude(self):
        """Test cleanup alerts with exclude"""
        call_command('cleanup_alerts', '--days', '90', '--exclude', 'notifications', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Excluding: notifications', output)
    
    def test_cleanup_alerts_very_old_data(self):
        """Test cleanup alerts with very old data"""
        call_command('cleanup_alerts', '--days', '365', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Days: 365', output)
        self.assertIn('Deleted', output)
    
    def test_cleanup_alerts_no_data_to_delete(self):
        """Test cleanup alerts with no data to delete"""
        # Clear all data
        AlertLog.objects.all().delete()
        
        call_command('cleanup_alerts', '--days', '30', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('No data found to cleanup', output)


class TestAlertsCommandTest(TestCase):
    """Test cases for TestAlertsCommand"""
    
    def setUp(self):
        self.command = TestAlertsCommand()
        self.out = StringIO()
        
        # Create test alert rules
        for i in range(5):
            AlertRule.objects.create(
                name=f'Test Rule {i}',
                alert_type='cpu_usage',
                severity='high' if i % 2 == 0 else 'medium',
                threshold_value=80.0,
                is_active=True
            )
    
    def test_test_alerts_basic(self):
        """Test basic test alerts command"""
        call_command('test_alerts', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Testing alert rules', output)
        self.assertIn('Test alerts created', output)
        self.assertIn('Test results:', output)
    
    def test_test_alerts_specific_rule(self):
        """Test test alerts for specific rule"""
        rule_id = AlertRule.objects.first().id
        
        call_command('test_alerts', '--rule', str(rule_id), stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn(f'Testing rule {rule_id}', output)
    
    def test_test_alerts_with_severity(self):
        """Test test alerts with severity filter"""
        call_command('test_alerts', '--severity', 'high', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Severity filter: high', output)
    
    def test_test_alerts_with_type(self):
        """Test test alerts with type filter"""
        call_command('test_alerts', '--type', 'cpu_usage', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Type filter: cpu_usage', output)
    
    def test_test_alerts_active_only(self):
        """Test test alerts for active rules only"""
        call_command('test_alerts', '--active-only', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Active rules only', output)
    
    def test_test_alerts_with_custom_message(self):
        """Test test alerts with custom message"""
        call_command('test_alerts', '--message', 'Custom test message', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Custom test message', output)
    
    def test_test_alerts_dry_run(self):
        """Test test alerts with dry run"""
        call_command('test_alerts', '--dry-run', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('DRY RUN', output)
        self.assertIn('Would create', output)
    
    def test_test_alerts_with_trigger_value(self):
        """Test test alerts with custom trigger value"""
        call_command('test_alerts', '--trigger-value', '95.0', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Trigger value: 95.0', output)
    
    def test_test_alerts_no_active_rules(self):
        """Test test alerts with no active rules"""
        # Deactivate all rules
        AlertRule.objects.all().update(is_active=False)
        
        call_command('test_alerts', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('No active rules found', output)


class CheckHealthCommandTest(TestCase):
    """Test cases for CheckHealthCommand"""
    
    def setUp(self):
        self.command = CheckHealthCommand()
        self.out = StringIO()
        
        # Create test data
        for i in range(5):
            AlertRule.objects.create(
                name=f'Alert {i}',
                alert_type='cpu_usage',
                severity='high' if i % 2 == 0 else 'medium',
                threshold_value=80.0,
                is_active=i % 3 != 0  # Some inactive
            )
        
        # Create system metrics
        for i in range(3):
            SystemMetrics.objects.create(
                total_users=1000 + i * 100,
                active_users_1h=500 + i * 50,
                total_earnings_1h=1000.0 + i * 100,
                avg_response_time_ms=200.0 + i * 20,
                timestamp=timezone.now() - timedelta(hours=i)
            )
    
    def test_check_health_basic(self):
        """Test basic check health command"""
        call_command('check_health', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Checking system health', output)
        self.assertIn('Alert System Health:', output)
        self.assertIn('Overall Health:', output)
    
    def test_check_health_specific_component(self):
        """Test check health for specific component"""
        call_command('check_health', '--component', 'alerts', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Component: alerts', output)
        self.assertIn('Alert System Health:', output)
    
    def test_check_health_all_components(self):
        """Test check health for all components"""
        call_command('check_health', '--component', 'all', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Component: all', output)
        self.assertIn('Alert System Health:', output)
        self.assertIn('Channel Health:', output)
        self.assertIn('Incident System Health:', output)
    
    def test_check_health_with_time_period(self):
        """Test check health with time period"""
        call_command('check_health', '--hours', '12', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Time period: 12 hours', output)
    
    def test_check_health_verbose(self):
        """Test check health with verbose output"""
        call_command('check_health', '--verbose', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Verbose: Yes', output)
        self.assertIn('Detailed metrics:', output)
    
    def test_check_health_json_output(self):
        """Test check health with JSON output"""
        call_command('check_health', '--format', 'json', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Format: json', output)
        # Should contain JSON structure
        self.assertIn('"overall_health":', output)
    
    def test_check_health_save_results(self):
        """Test check health with save results"""
        call_command('check_health', '--save', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Save results: Yes', output)
        self.assertIn('Results saved to:', output)
    
    def test_check_health_with_thresholds(self):
        """Test check health with custom thresholds"""
        call_command('check_health', '--warning-threshold', '80', '--critical-threshold', '90', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('Warning threshold: 80', output)
        self.assertIn('Critical threshold: 90', output)
    
    def test_check_health_no_data(self):
        """Test check health with no data"""
        # Clear all data
        AlertRule.objects.all().delete()
        SystemMetrics.objects.all().delete()
        
        call_command('check_health', stdout=self.out)
        
        output = self.out.getvalue()
        self.assertIn('No data available', output)
        self.assertIn('Health Status: Unknown', output)


class ManagementCommandsIntegrationTest(TestCase):
    """Test cases for management commands integration"""
    
    def setUp(self):
        self.out = StringIO()
    
    def test_command_sequence_workflow(self):
        """Test typical command sequence workflow"""
        # 1. Check health first
        call_command('check_health', stdout=self.out)
        health_output = self.out.getvalue()
        self.out = StringIO()
        
        # 2. Process any pending alerts
        call_command('process_alerts', stdout=self.out)
        process_output = self.out.getvalue()
        self.out = StringIO()
        
        # 3. Generate reports
        call_command('generate_reports', 'daily', stdout=self.out)
        report_output = self.out.getvalue()
        self.out = StringIO()
        
        # 4. Check health again
        call_command('check_health', stdout=self.out)
        final_health_output = self.out.getvalue()
        
        # Verify all commands executed successfully
        self.assertIn('Checking system health', health_output)
        self.assertIn('Processing pending alerts', process_output)
        self.assertIn('Generating daily report', report_output)
        self.assertIn('Checking system health', final_health_output)
    
    def test_error_handling_workflow(self):
        """Test error handling in command workflow"""
        # Test with invalid parameters
        try:
            call_command('generate_reports', 'invalid_type', stdout=self.out)
        except CommandError:
            pass  # Expected
        
        # Test with no data
        call_command('process_alerts', stdout=self.out)
        no_data_output = self.out.getvalue()
        self.out = StringIO()
        
        # Should handle gracefully
        self.assertIn('Processing complete', no_data_output)
    
    def test_performance_with_large_dataset(self):
        """Test command performance with large dataset"""
        # Create large dataset
        for i in range(100):
            AlertRule.objects.create(
                name=f'Rule {i}',
                alert_type='cpu_usage',
                severity='high',
                threshold_value=80.0
            )
            
            AlertLog.objects.create(
                rule=AlertRule.objects.get(name=f'Rule {i}'),
                trigger_value=85.0,
                threshold_value=80.0,
                message=f'Alert {i}'
            )
        
        # Test performance
        import time
        start_time = time.time()
        
        call_command('process_alerts', '--limit', '50', stdout=self.out)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(duration, 10.0)  # 10 seconds max
        
        output = self.out.getvalue()
        self.assertIn('Processing complete', output)
    
    def test_command_output_formatting(self):
        """Test command output formatting"""
        # Test different output formats
        commands_formats = [
            ('check_health', '--format', 'json'),
            ('generate_reports', 'daily', '--format', 'csv'),
            ('process_alerts', '--verbose'),
            ('cleanup_alerts', '--dry-run')
        ]
        
        for command_args in commands_formats:
            self.out = StringIO()
            call_command(*command_args, stdout=self.out)
            
            output = self.out.getvalue()
            self.assertTrue(len(output) > 0)  # Should have some output
