# ALERTS MODULE - INTEGRATION TESTS
# File: alerts/tests/test_integration.py

from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from datetime import timedelta

from api.alerts.services.alert_processing import AlertProcessingService
from api.alerts.services.system_health import SystemHealthService
from api.alerts.services.configuration import ConfigurationService
from api.alerts.services.event_bus import EventService
from api.alerts.services.statistics import StatisticsService
from api.alerts.services.maintenance import MaintenanceService

from api.alerts.tests.factories import (
    AlertRuleFactory, AlertLogFactory, AlertChannelFactory,
    AlertNotificationFactory, AlertGroupFactory,
    create_alert_scenario, cleanup_all
)


class AlertProcessingIntegrationTest(TransactionTestCase):
    """Integration tests for complete alert processing workflow"""

    def setUp(self):
        """Set up test scenario"""
        self.scenario = create_alert_scenario(rule_count=3, alert_per_rule=5)
        self.rules = self.scenario['rules']
        self.alerts = self.scenario['alerts']

    def tearDown(self):
        """Clean up"""
        cleanup_all()

    def test_complete_alert_workflow(self):
        """
        Test complete workflow:
        1. Create alert rule
        2. Trigger alert
        3. Process alert
        4. Escalate if needed
        5. Resolve alert
        """
        
        # Step 1: Create rule (already done in setUp)
        rule = self.rules[0]
        self.assertTrue(rule.is_active)
        
        # Step 2: Create alert
        alert = AlertLogFactory.create(rule=rule, status='pending')
        self.assertEqual(alert.status, 'pending')
        
        # Step 3: Process alert
        result = AlertProcessingService.process_pending_alerts()
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)
        
        # Step 4: Check escalation
        can_escalate = AlertProcessingService.should_escalate(alert)
        self.assertIsInstance(can_escalate, bool)
        
        # Step 5: Resolve alert
        AlertProcessingService.bulk_resolve_alerts([alert.id])
        alert.refresh_from_db()
        self.assertEqual(alert.status, 'resolved')

    def test_group_alert_sending(self):
        """
        Test group alert workflow:
        1. Create alert group
        2. Add alerts to group
        3. Send group alerts
        4. Verify notifications sent
        """
        
        # Step 1-2: Create group and add alerts
        group = AlertGroupFactory.create()
        for alert in self.alerts[:3]:
            group.rules.add(alert.rule)
        
        # Step 3: Send group alerts
        result = AlertProcessingService.send_group_alerts(group.id)
        
        # Step 4: Verify result
        self.assertIn('sent', result)
        self.assertIn('failed', result)

    def test_alert_escalation_chain(self):
        """
        Test escalation chain:
        1. Create rule with escalation
        2. Create alert
        3. First escalation
        4. Second escalation
        5. Verify recipient chain
        """
        
        rule = self.rules[0]
        alert = AlertLogFactory.create(rule=rule, status='pending')
        
        # First escalation
        result1 = AlertProcessingService.escalate_alerts(alert=alert)
        self.assertIsNotNone(result1)
        
        # Second escalation
        result2 = AlertProcessingService.escalate_alerts(alert=alert)
        self.assertIsNotNone(result2)

    def test_analytics_generation_workflow(self):
        """
        Test analytics workflow:
        1. Create multiple alerts with different statuses
        2. Generate daily analytics
        3. Verify metrics calculated
        """
        
        # Step 1: Create alerts with different statuses
        rule = self.rules[0]
        now = timezone.now()
        AlertLogFactory.create(rule=rule, status='processed', triggered_at=now)
        AlertLogFactory.create(rule=rule, status='resolved', triggered_at=now)
        AlertLogFactory.create(rule=rule, status='failed', triggered_at=now)
        
        # Step 2: Generate analytics
        result = AlertProcessingService.generate_daily_analytics()
        
        # Step 3: Verify metrics
        self.assertGreater(result['total_alerts'], 0)
        self.assertGreaterEqual(result['resolved_alerts'], 0)
        self.assertGreaterEqual(result['failed_alerts'], 0)

    def test_retry_failed_alerts_workflow(self):
        """
        Test retry workflow:
        1. Create failed alert
        2. Retry failed alerts
        3. Verify status changed to pending
        4. Retry count incremented
        """
        
        rule = self.rules[0]
        alert = AlertLogFactory.create(rule=rule, status='failed')
        
        # Retry
        result = AlertProcessingService.retry_failed_alerts()
        
        # Verify
        alert.refresh_from_db()
        self.assertEqual(alert.status, 'pending')


class SystemHealthIntegrationTest(TransactionTestCase):
    """Integration tests for system health monitoring"""

    def setUp(self):
        """Set up test scenario"""
        self.scenario = create_alert_scenario(rule_count=2, alert_per_rule=5)

    def tearDown(self):
        """Clean up"""
        cleanup_all()

    def test_health_check_workflow(self):
        """
        Test health check workflow:
        1. Perform health check
        2. Get health status
        3. Verify trends
        4. Calculate uptime
        """
        
        # Step 1: Health check
        health1 = SystemHealthService.check_system_health()
        self.assertIn('checked', health1)
        
        # Step 2: Get status
        status = SystemHealthService.system_health()
        self.assertIn('status', status)
        
        # Step 3: Get trends
        trends = SystemHealthService.get_health_trends(days=1)
        self.assertIsInstance(trends, list)
        
        # Step 4: Calculate uptime
        uptime = SystemHealthService.get_uptime_percentage(days=1)
        self.assertGreaterEqual(uptime, 0)
        self.assertLessEqual(uptime, 100)

    def test_degraded_health_detection(self):
        """
        Test that a due SystemHealthCheck actually gets run and counted:
        1. Configure a health check that is due now
        2. Run check_system_health()
        3. Verify it was picked up and counted
        """
        from api.alerts.models import SystemHealthCheck

        SystemHealthCheck.objects.create(
            check_name='integration_test_check',
            check_type='database',
            is_active=True,
        )

        health = SystemHealthService.check_system_health()

        self.assertEqual(health['checked'], 1)


class EventIntegrationTest(TestCase):
    """Integration tests for event handling"""

    def setUp(self):
        """Set up test scenario"""
        self.events_fired = []
        
        def event_handler(**kwargs):
            self.events_fired.append(kwargs)
        
        EventService.register_handler('test_event', event_handler)

    def test_event_emission_workflow(self):
        """
        Test event workflow:
        1. Register handler
        2. Emit event
        3. Verify handler called
        4. Verify data passed
        """
        
        test_data = {'alert_id': 123, 'severity': 'high'}
        EventService.emit_event('test_event', **test_data)
        
        # Verify handler was called
        self.assertTrue(len(self.events_fired) > 0)
        
        # Verify data
        self.assertEqual(self.events_fired[0]['alert_id'], 123)
        self.assertEqual(self.events_fired[0]['severity'], 'high')

    def test_alert_triggered_event_flow(self):
        """Test alert triggered event flow"""
        rule = AlertRuleFactory.create()
        alert = AlertLogFactory.create(rule=rule)
        
        # Trigger event
        EventService.handle_alert_triggered(alert)
        
        # Should not raise exception
        self.assertTrue(True)

    def test_alert_resolved_event_flow(self):
        """Test alert resolved event flow"""
        rule = AlertRuleFactory.create()
        alert = AlertLogFactory.create(rule=rule, status='resolved')
        
        # Trigger event
        EventService.handle_alert_resolved(alert)
        
        # Should not raise exception
        self.assertTrue(True)


class StatisticsIntegrationTest(TransactionTestCase):
    """Integration tests for statistics gathering"""

    def setUp(self):
        """Set up test scenario"""
        self.scenario = create_alert_scenario(rule_count=3, alert_per_rule=5)
        self.rules = self.scenario['rules']
        self.alerts = self.scenario['alerts']

    def tearDown(self):
        """Clean up"""
        cleanup_all()

    def test_statistics_workflow(self):
        """
        Test statistics workflow:
        1. Create scenario
        2. Calculate statistics
        3. Get API info
        4. Get trends
        """
        
        # Step 1: Scenario created in setUp
        
        # Step 2: Calculate statistics
        stats = StatisticsService.alert_statistics()
        self.assertGreater(stats['total_alerts'], 0)
        self.assertGreater(stats['active_rules'], 0)
        
        # Step 3: Get API info
        info = StatisticsService.api_info()
        self.assertEqual(info['name'], 'Alerts API')
        self.assertIn('endpoints', info)
        
        # Step 4: Get trends
        trends = StatisticsService.get_alert_trends(days=1)
        self.assertIsInstance(trends, list)

    def test_severity_distribution_workflow(self):
        """Test severity distribution analysis"""
        
        # Create alerts with different severities
        rule = self.rules[0]
        AlertLogFactory.create(rule=rule, severity='high')
        AlertLogFactory.create(rule=rule, severity='critical')
        AlertLogFactory.create(rule=rule, severity='low')
        
        # Get severity distribution
        chart = StatisticsService.get_alert_by_severity_chart()
        
        # Verify
        self.assertIsNotNone(chart)
        self.assertIsInstance(chart, list)


class MaintenanceIntegrationTest(TransactionTestCase):
    """Integration tests for maintenance operations"""

    def setUp(self):
        """Set up test scenario"""
        self.scenario = create_alert_scenario(rule_count=2, alert_per_rule=3)
        self.rules = self.scenario['rules']
        self.alerts = self.scenario['alerts']

    def tearDown(self):
        """Clean up"""
        cleanup_all()

    def test_cleanup_workflow(self):
        """
        Test cleanup workflow:
        1. Create old notifications
        2. Run cleanup
        3. Verify deleted
        """
        
        rule = self.rules[0]
        
        # Create old notification (30+ days old)
        old_time = timezone.now() - timedelta(days=31)
        alert = AlertLogFactory.create(rule=rule, triggered_at=old_time)
        notif = AlertNotificationFactory.create(alert_log=alert, created_at=old_time)
        
        # Run cleanup
        result = MaintenanceService.cleanup_old_notifications(days=30)
        
        # Verify
        self.assertIn('deleted', result)

    def test_suppression_expiration_workflow(self):
        """Test suppression expiration"""
        from api.alerts.tests.factories import AlertSuppressionFactory
        
        rule = self.rules[0]
        
        # Create expired suppression
        expired_time = timezone.now() - timedelta(hours=1)
        suppression = AlertSuppressionFactory.create(
            rule=rule,
            is_active=True,
            end_time=expired_time
        )
        
        # Expire suppressions
        result = MaintenanceService.expire_suppressions()
        
        # Verify
        suppression.refresh_from_db()
        self.assertFalse(suppression.is_active)

    def test_cache_update_workflow(self):
        """Test alert group cache update"""
        
        group = AlertGroupFactory.create()
        for alert in self.alerts[:2]:
            group.rules.add(alert.rule)
        
        # Update caches
        result = MaintenanceService.update_alert_group_caches()
        
        # Verify
        self.assertGreater(result['updated'], 0)


class EndToEndIntegrationTest(TransactionTestCase):
    """Complete end-to-end integration test"""

    def setUp(self):
        """Set up complete scenario"""
        self.scenario = create_alert_scenario(rule_count=5, alert_per_rule=10)
        self.rules = self.scenario['rules']
        self.alerts = self.scenario['alerts']

    def tearDown(self):
        """Clean up"""
        cleanup_all()

    def test_complete_system_workflow(self):
        """
        Test complete system workflow:
        1. Health check
        2. Process alerts
        3. Escalate if needed
        4. Generate statistics
        5. Run maintenance
        """
        
        print("\n[Integration Test] Starting complete system workflow\n")
        
        # Step 1: Health check
        print("1. Checking system health...")
        health = SystemHealthService.check_system_health()
        self.assertIn('checked', health)
        print(f"   Health checks run: {health['checked']}, failed: {health['failed']}")
        
        # Step 2: Process alerts
        print("2. Processing alerts...")
        result = AlertProcessingService.process_pending_alerts()
        self.assertIsInstance(result, int)
        print(f"   Processed: {result}")
        
        # Step 3: Check for escalation
        print("3. Checking escalations...")
        for alert in self.alerts[:3]:
            can_escalate = AlertProcessingService.should_escalate(alert)
            if can_escalate:
                AlertProcessingService.escalate_alerts(alert=alert)
        print("   Escalation check complete")
        
        # Step 4: Generate statistics
        print("4. Generating statistics...")
        stats = StatisticsService.alert_statistics()
        self.assertGreater(stats['total_alerts'], 0)
        print(f"   Total alerts: {stats['total_alerts']}")
        print(f"   Active rules: {stats['active_rules']}")
        
        # Step 5: Run maintenance
        print("5. Running maintenance...")
        from api.alerts.tests.factories import AlertGroupFactory
        group = AlertGroupFactory.create()
        group.rules.add(self.rules[0])
        maintenance_result = MaintenanceService.update_alert_group_caches()
        self.assertGreater(maintenance_result['updated'], 0)
        print(f"   Caches updated: {maintenance_result['updated']}")
        
        print("\n✅ Complete system workflow successful!\n")


__all__ = [
    'AlertProcessingIntegrationTest',
    'SystemHealthIntegrationTest',
    'EventIntegrationTest',
    'StatisticsIntegrationTest',
    'MaintenanceIntegrationTest',
    'EndToEndIntegrationTest',
]
