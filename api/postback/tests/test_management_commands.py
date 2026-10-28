"""test_management_commands.py – Tests for postback management commands."""
from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch, MagicMock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from api.postback.tests.factories import (
    NetworkPostbackConfigFactory,
    PostbackInsightFactory,
    PostbackTemplateFactory,
    PostbackIPWhitelistFactory,
    PostbackRateLimitFactory,
    PostbackLogFactory,
)
from api.postback.models import PostbackInsight, PostbackTemplate, PostbackIPWhitelist, PostbackRateLimit
from api.postback.choices import PostbackStatus


class AggregatePostbackInsightsCommandTests(TestCase):
    """Test aggregate_postback_insights management command."""

    def test_aggregate_insights_default_date(self):
        """Test aggregating insights for default date (yesterday)."""
        network = NetworkPostbackConfigFactory()
        
        # Create logs for yesterday
        yesterday = timezone.now().date() - timedelta(days=1)
        PostbackLogFactory(
            network=network,
            status=PostbackStatus.REWARDED,
            received_at=timezone.now() - timedelta(days=1)
        )
        
        out = StringIO()
        call_command('aggregate_postback_insights', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Processing insights', output)
        self.assertIn('network(s)', output)
        
        # Verify insight was created
        insight = PostbackInsight.objects.filter(network=network, date=yesterday).first()
        self.assertIsNotNone(insight)
        self.assertEqual(insight.received_count, 1)
        self.assertEqual(insight.rewarded_count, 1)

    def test_aggregate_insights_specific_date(self):
        """Test aggregating insights for specific date."""
        network = NetworkPostbackConfigFactory()
        target_date = date(2024, 1, 15)
        
        # Create logs for target date
        PostbackLogFactory(
            network=network,
            status=PostbackStatus.REWARDED,
            received_at=timezone.datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        out = StringIO()
        call_command('aggregate_postback_insights', '--date', '2024-01-15', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Processing insights', output)
        
        # Verify insight was created for correct date
        insight = PostbackInsight.objects.filter(network=network, date=target_date).first()
        self.assertIsNotNone(insight)
        self.assertEqual(insight.date, target_date)

    def test_aggregate_insights_specific_network(self):
        """Test aggregating insights for specific network."""
        network1 = NetworkPostbackConfigFactory()
        network2 = NetworkPostbackConfigFactory()
        
        # Create logs for both networks
        PostbackLogFactory(network=network1, status=PostbackStatus.REWARDED)
        PostbackLogFactory(network=network2, status=PostbackStatus.REWARDED)
        
        out = StringIO()
        call_command('aggregate_postback_insights', '--network', network1.network_key, stdout=out)
        
        output = out.getvalue()
        self.assertIn('Processing insights', output)
        
        # Verify insight was created only for specified network
        insight1 = PostbackInsight.objects.filter(network=network1).exists()
        insight2 = PostbackInsight.objects.filter(network=network2).exists()
        
        self.assertTrue(insight1)
        self.assertFalse(insight2)

    def test_aggregate_insights_backfill(self):
        """Test backfilling insights for multiple days."""
        network = NetworkPostbackConfigFactory()
        
        # Create logs for multiple days
        for i in range(5):
            PostbackLogFactory(
                network=network,
                status=PostbackStatus.REWARDED,
                received_at=timezone.now() - timedelta(days=i)
            )
        
        out = StringIO()
        call_command('aggregate_postback_insights', '--backfill', '5', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Backfilled', output)
        self.assertIn('days', output)
        
        # Verify insights were created for all days
        insights_count = PostbackInsight.objects.filter(network=network).count()
        self.assertEqual(insights_count, 5)

    def test_aggregate_insights_detect_anomalies(self):
        """Test aggregating insights with anomaly detection."""
        network = NetworkPostbackConfigFactory()
        
        # Create baseline data
        for i in range(7, 0, -1):
            PostbackInsightFactory(
                network=network,
                date=timezone.now().date() - timedelta(days=i),
                received_count=100
            )
        
        # Create current day with spike
        PostbackLogFactory(
            network=network,
            status=PostbackStatus.REWARDED,
            received_at=timezone.now()
        )
        # Simulate volume spike by manually creating high count
        # (This would normally come from actual log processing)
        
        out = StringIO()
        call_command('aggregate_postback_insights', '--detect-anomalies', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Processing insights', output)

    def test_aggregate_insights_force_recalculate(self):
        """Test force recalculation of insights."""
        network = NetworkPostbackConfigFactory()
        
        # Create existing insight
        existing_insight = PostbackInsightFactory(
            network=network,
            date=timezone.now().date(),
            received_count=10
        )
        
        # Create new log
        PostbackLogFactory(
            network=network,
            status=PostbackStatus.REWARDED,
            received_at=timezone.now()
        )
        
        out = StringIO()
        call_command('aggregate_postback_insights', '--force-recalculate', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Processing insights', output)
        
        # Verify insight was recalculated
        existing_insight.refresh_from_db()
        self.assertGreater(existing_insight.received_count, 10)

    def test_aggregate_insights_nonexistent_network(self):
        """Test aggregating insights for non-existent network."""
        out = StringIO()
        err = StringIO()
        
        with self.assertRaises(CommandError):
            call_command('aggregate_postback_insights', '--network', 'nonexistent', stdout=out, stderr=err)
        
        err_output = err.getvalue()
        self.assertIn('not found', err_output)


class VerifyPostbackIntegrityCommandTests(TestCase):
    """Test verify_postback_integrity management command."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()

    def test_verify_integrity_all_models(self):
        """Test integrity verification for all models."""
        # Create instances of all models
        PostbackInsightFactory(network=self.network)
        PostbackTemplateFactory(network=self.network)
        PostbackIPWhitelistFactory(network=self.network)
        PostbackRateLimitFactory(network=self.network)
        
        out = StringIO()
        call_command('verify_postback_integrity', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Verifying PostbackLog', output)
        self.assertIn('Verifying PostbackInsight', output)
        self.assertIn('Verifying PostbackTemplate', output)
        self.assertIn('Verifying PostbackIPWhitelist', output)
        self.assertIn('Verifying PostbackRateLimit', output)

    def test_verify_integrity_specific_model(self):
        """Test integrity verification for specific model."""
        PostbackInsightFactory(network=self.network)
        
        out = StringIO()
        call_command('verify_postback_integrity', '--model', 'insight', stdout=out)
        
        output = out.getvalue()
        self.assertNotIn('Verifying PostbackLog', output)
        self.assertIn('Verifying PostbackInsight', output)
        self.assertNotIn('Verifying PostbackTemplate', output)

    def test_verify_integrity_specific_network(self):
        """Test integrity verification for specific network."""
        network1 = self.network
        network2 = NetworkPostbackConfigFactory()
        
        PostbackInsightFactory(network=network1)
        PostbackInsightFactory(network=network2)
        
        out = StringIO()
        call_command('verify_postback_integrity', '--network', network1.network_key, stdout=out)
        
        output = out.getvalue()
        self.assertIn('Checking 1 PostbackInsight', output)  # Only network1's insight

    def test_verify_integrity_with_days_filter(self):
        """Test integrity verification with days filter."""
        # Create insights for different dates
        PostbackInsightFactory(
            network=self.network,
            date=timezone.now().date() - timedelta(days=10)
        )
        PostbackInsightFactory(
            network=self.network,
            date=timezone.now().date() - timedelta(days=1)
        )
        
        out = StringIO()
        call_command('verify_postback_integrity', '--model', 'insight', '--days', '7', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Checking 1 PostbackInsight', output)  # Only recent insight

    def test_verify_integrity_with_fix(self):
        """Test integrity verification with fix option."""
        # Create insight without integrity hash
        insight = PostbackInsightFactory(network=self.network)
        insight.integrity_hash = ''
        insight.save()
        
        out = StringIO()
        call_command('verify_postback_integrity', '--model', 'insight', '--fix', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Fixed hash for insight', output)
        
        # Verify hash was fixed
        insight.refresh_from_db()
        self.assertTrue(insight.verify_integrity())

    def test_verify_integrity_postback_logs(self):
        """Test integrity verification for PostbackLog."""
        PostbackLogFactory(network=self.network)
        
        out = StringIO()
        call_command('verify_postback_integrity', '--model', 'postbacklog', stdout=out)
        
        output = out.getvalue()
        self.assertIn('PostbackLog:', output)
        self.assertIn('valid', output)

    def test_verify_integrity_templates(self):
        """Test integrity verification for PostbackTemplate."""
        PostbackTemplateFactory(network=self.network)
        
        out = StringIO()
        call_command('verify_postback_integrity', '--model', 'template', stdout=out)
        
        output = out.getvalue()
        self.assertIn('PostbackTemplate:', output)
        self.assertIn('valid', output)

    def test_verify_integrity_ip_whitelists(self):
        """Test integrity verification for PostbackIPWhitelist."""
        PostbackIPWhitelistFactory(network=self.network)
        
        out = StringIO()
        call_command('verify_postback_integrity', '--model', 'ipwhitelist', stdout=out)
        
        output = out.getvalue()
        self.assertIn('PostbackIPWhitelist:', output)
        self.assertIn('valid', output)

    def test_verify_integrity_rate_limits(self):
        """Test integrity verification for PostbackRateLimit."""
        PostbackRateLimitFactory(network=self.network)
        
        out = StringIO()
        call_command('verify_postback_integrity', '--model', 'ratelimit', stdout=out)
        
        output = out.getvalue()
        self.assertIn('PostbackRateLimit:', output)
        self.assertIn('valid', output)

    def test_verify_integrity_detect_tampering(self):
        """Test integrity verification detects tampering."""
        # Create template and tamper with it
        template = PostbackTemplateFactory(network=self.network)
        original_hash = template.integrity_hash
        
        template.template_body = "Tampered content"
        template.save()
        
        out = StringIO()
        call_command('verify_postback_integrity', '--model', 'template', stdout=out)
        
        output = out.getvalue()
        self.assertIn('invalid', output)
        self.assertIn('Use --fix', output)

    def test_verify_integrity_batch_processing(self):
        """Test integrity verification with multiple instances."""
        # Create multiple instances
        for i in range(5):
            PostbackInsightFactory(network=self.network)
        
        out = StringIO()
        call_command('verify_postback_integrity', '--model', 'insight', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Checking 5 PostbackInsight', output)
        self.assertIn('5 valid', output)

    def test_verify_integrity_no_instances(self):
        """Test integrity verification with no instances."""
        out = StringIO()
        call_command('verify_postback_integrity', '--model', 'insight', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Checking 0 PostbackInsight', output)
        self.assertIn('0 valid', output)


class ManagementCommandIntegrationTests(TestCase):
    """Test management command integration scenarios."""

    def test_aggregate_and_verify_workflow(self):
        """Test complete workflow of aggregation and verification."""
        network = NetworkPostbackConfigFactory()
        
        # Create test data
        PostbackLogFactory(
            network=network,
            status=PostbackStatus.REWARDED,
            payout="10.00",
            points_awarded=100
        )
        
        # Step 1: Aggregate insights
        out = StringIO()
        call_command('aggregate_postback_insights', stdout=out)
        
        # Verify insight was created
        insight = PostbackInsight.objects.filter(network=network).first()
        self.assertIsNotNone(insight)
        
        # Step 2: Verify integrity
        out = StringIO()
        call_command('verify_postback_integrity', '--model', 'insight', stdout=out)
        
        output = out.getvalue()
        self.assertIn('1 valid', output)

    def test_backfill_and_anomaly_detection(self):
        """Test backfill with anomaly detection."""
        network = NetworkPostbackConfigFactory()
        
        # Create baseline data
        for i in range(7, 0, -1):
            PostbackLogFactory(
                network=network,
                status=PostbackStatus.REWARDED,
                received_at=timezone.now() - timedelta(days=i)
            )
        
        # Create current day with volume spike
        for i in range(50):  # Much higher volume
            PostbackLogFactory(
                network=network,
                status=PostbackStatus.REWARDED,
                received_at=timezone.now()
            )
        
        # Backfill with anomaly detection
        out = StringIO()
        call_command('aggregate_postback_insights', '--backfill', '7', '--detect-anomalies', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Backfilled', output)

    def test_integrity_fix_workflow(self):
        """Test integrity fix workflow."""
        network = NetworkPostbackConfigFactory()
        
        # Create templates without integrity hashes
        templates = []
        for i in range(3):
            template = PostbackTemplateFactory(network=network)
            template.integrity_hash = ''
            template.save()
            templates.append(template)
        
        # Verify integrity (should show invalid)
        out = StringIO()
        call_command('verify_postback_integrity', '--model', 'template', stdout=out)
        
        output = out.getvalue()
        self.assertIn('invalid', output)
        
        # Fix integrity
        out = StringIO()
        call_command('verify_postback_integrity', '--model', 'template', '--fix', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Fixed hash', output)
        
        # Verify all are now valid
        for template in templates:
            template.refresh_from_db()
            self.assertTrue(template.verify_integrity())

    def test_network_specific_operations(self):
        """Test operations specific to a network."""
        network1 = NetworkPostbackConfigFactory(network_key='network-001')
        network2 = NetworkPostbackConfigFactory(network_key='network-002')
        
        # Create data for both networks
        PostbackLogFactory(network=network1, status=PostbackStatus.REWARDED)
        PostbackLogFactory(network=network2, status=PostbackStatus.REWARDED)
        
        # Aggregate only for network1
        out = StringIO()
        call_command('aggregate_postback_insights', '--network', 'network-001', stdout=out)
        
        # Verify only network1 has insight
        insight1 = PostbackInsight.objects.filter(network=network1).exists()
        insight2 = PostbackIntegrity.objects.filter(network=network2).exists()
        
        self.assertTrue(insight1)
        self.assertFalse(insight2)
        
        # Verify integrity only for network1
        out = StringIO()
        call_command('verify_postback_integrity', '--network', 'network-001', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Checking 1', output)  # Only network1's insight

    def test_error_handling(self):
        """Test error handling in management commands."""
        # Test non-existent network
        out = StringIO()
        err = StringIO()
        
        with self.assertRaises(CommandError):
            call_command('aggregate_postback_insights', '--network', 'non-existent', stdout=out, stderr=err)
        
        # Test invalid date format
        out = StringIO()
        err = StringIO()
        
        with self.assertRaises(CommandError):
            call_command('aggregate_postback_insights', '--date', 'invalid-date', stdout=out, stderr=err)

    def test_dry_run_simulation(self):
        """Test dry-run simulation of commands."""
        network = NetworkPostbackConfigFactory()
        
        # Create some test data
        PostbackLogFactory(network=network, status=PostbackStatus.REWARDED)
        
        # Run aggregation
        out = StringIO()
        call_command('aggregate_postback_insights', stdout=out)
        
        # Check output format
        output = out.getvalue()
        self.assertIn('Processing insights', output)
        self.assertIn('network(s)', output)
        self.assertIn('Completed', output)

    def test_large_volume_processing(self):
        """Test commands with large volume of data."""
        network = NetworkPostbackConfigFactory()
        
        # Create large number of logs
        for i in range(100):
            PostbackLogFactory(
                network=network,
                status=PostbackStatus.REWARDED,
                received_at=timezone.now() - timedelta(minutes=i)
            )
        
        # Aggregate insights
        out = StringIO()
        call_command('aggregate_postback_insights', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Processing insights', output)
        
        # Verify insight was created with correct count
        insight = PostbackInsight.objects.filter(network=network).first()
        self.assertIsNotNone(insight)
        self.assertEqual(insight.received_count, 100)
        self.assertEqual(insight.rewarded_count, 100)
