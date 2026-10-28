"""test_new_services.py – Tests for new postback services."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone

from api.postback.services import PostbackInsightService, TemplateService
from api.postback.services import (
    _check_rate_limit,
    _check_ip_enhanced,
    _update_analytics,
)
from api.postback.tests.factories import (
    NetworkPostbackConfigFactory,
    PostbackInsightFactory,
    PostbackTemplateFactory,
    PostbackIPWhitelistFactory,
    PostbackRateLimitFactory,
    PostbackLogFactory,
    AnomalousPostbackInsightFactory,
)
from api.postback.choices import PostbackStatus
from api.postback.exceptions import RateLimitExceededException, IPNotWhitelistedException
from api.postback.models import PostbackInsight


class PostbackInsightServiceTests(TestCase):
    """Test PostbackInsightService functionality."""

    def test_get_daily_insight_new(self):
        """Test getting daily insight for new date."""
        network = NetworkPostbackConfigFactory()
        target_date = date.today()
        
        insight = PostbackInsightService.get_daily_insight(network, target_date)
        
        self.assertEqual(insight.network, network)
        self.assertEqual(insight.date, target_date)
        self.assertEqual(insight.received_count, 0)
        self.assertEqual(insight.rewarded_count, 0)
        self.assertIsNotNone(insight.integrity_hash)

    def test_get_daily_insight_existing(self):
        """Test getting existing daily insight."""
        existing = PostbackInsightFactory()
        
        insight = PostbackInsightService.get_daily_insight(
            existing.network, existing.date
        )
        
        self.assertEqual(insight.id, existing.id)
        self.assertEqual(insight.received_count, existing.received_count)

    def test_recalculate_daily_insight(self):
        """Test recalculation of daily insight from logs."""
        network = NetworkPostbackConfigFactory()
        target_date = date.today()
        
        # Create test logs
        PostbackLogFactory(
            network=network,
            status=PostbackStatus.REWARDED,
            payout="10.00",
            points_awarded=100,
            received_at=timezone.now()
        )
        PostbackLogFactory(
            network=network,
            status=PostbackStatus.REJECTED,
            received_at=timezone.now()
        )
        PostbackLogFactory(
            network=network,
            status=PostbackStatus.DUPLICATE,
            received_at=timezone.now()
        )
        
        insight = PostbackInsightService.recalculate_daily_insight(network, target_date)
        
        self.assertEqual(insight.received_count, 3)
        self.assertEqual(insight.rewarded_count, 1)
        self.assertEqual(insight.rejected_count, 1)
        self.assertEqual(insight.duplicate_count, 1)
        self.assertEqual(float(insight.total_payout), 10.00)
        self.assertEqual(insight.total_points_awarded, 100)
        self.assertIsNotNone(insight.integrity_hash)

    def test_get_network_health_trend(self):
        """Test getting network health trend."""
        network = NetworkPostbackConfigFactory()
        
        # Create insights for multiple days
        for i in range(5):
            PostbackInsightFactory(
                network=network,
                date=date.today() - timedelta(days=i),
                health_score=Decimal(f"{80 + i}.5")
            )
        
        trend = PostbackInsightService.get_network_health_trend(network, 7)
        
        self.assertEqual(len(trend), 5)
        for day_data in trend:
            self.assertIn('date', day_data)
            self.assertIn('health_score', day_data)
            self.assertIn('received_count', day_data)
            self.assertIn('rewarded_count', day_data)

    def test_detect_anomalies_volume_spike(self):
        """Test anomaly detection for volume spike."""
        network = NetworkPostbackConfigFactory()
        target_date = date.today()
        
        # Create baseline data (last 7 days)
        for i in range(7, 0, -1):
            PostbackInsightFactory(
                network=network,
                date=target_date - timedelta(days=i),
                received_count=100
            )
        
        # Create current day with spike
        current_insight = PostbackInsightFactory(
            network=network,
            date=target_date,
            received_count=250  # 150% increase
        )
        
        anomalies = PostbackInsightService.detect_anomalies(network, target_date)
        
        self.assertTrue(anomalies)
        self.assertIn('volume_spike', anomalies)
        self.assertGreater(anomalies['volume_spike']['deviation_percent'], 50)

    def test_detect_anomalies_health_drop(self):
        """Test anomaly detection for health score drop."""
        network = NetworkPostbackConfigFactory()
        target_date = date.today()
        
        # Create baseline with good health
        for i in range(7, 0, -1):
            PostbackInsightFactory(
                network=network,
                date=target_date - timedelta(days=i),
                health_score=Decimal('85.0')
            )
        
        # Create current day with poor health
        current_insight = PostbackInsightFactory(
            network=network,
            date=target_date,
            health_score=Decimal('60.0')  # Significant drop
        )
        
        anomalies = PostbackInsightService.detect_anomalies(network, target_date)
        
        self.assertTrue(anomalies)
        self.assertIn('health_drop', anomalies)

    def test_detect_anomalies_high_rejection_rate(self):
        """Test anomaly detection for high rejection rate."""
        network = NetworkPostbackConfigFactory()
        target_date = date.today()
        
        # Create insight with high rejection rate (>30%)
        insight = PostbackInsightFactory(
            network=network,
            date=target_date,
            received_count=100,
            rejected_count=25,
            failed_count=10  # 35% rejection rate
        )
        
        anomalies = PostbackInsightService.detect_anomalies(network, target_date)
        
        self.assertTrue(anomalies)
        self.assertIn('high_rejection_rate', anomalies)

    def test_detect_anomalies_high_duplicate_rate(self):
        """Test anomaly detection for high duplicate rate."""
        network = NetworkPostbackConfigFactory()
        target_date = date.today()
        
        # Create insight with high duplicate rate (>25%)
        insight = PostbackInsightFactory(
            network=network,
            date=target_date,
            received_count=100,
            duplicate_count=30  # 30% duplicate rate
        )
        
        anomalies = PostbackInsightService.detect_anomalies(network, target_date)
        
        self.assertTrue(anomalies)
        self.assertIn('high_duplicate_rate', anomalies)

    def test_get_network_summary(self):
        """Test getting comprehensive network summary."""
        network = NetworkPostbackConfigFactory()
        
        # Create insights for multiple days
        for i in range(5):
            PostbackInsightFactory(
                network=network,
                date=date.today() - timedelta(days=i),
                received_count=100 + i * 10,
                rewarded_count=80 + i * 5,
                total_payout=Decimal(f"{100 + i * 10}.00")
            )
        
        summary = PostbackInsightService.get_network_summary(network, 7)
        
        self.assertEqual(summary['network_key'], network.network_key)
        self.assertEqual(summary['period_days'], 7)
        self.assertGreater(summary['total_received'], 0)
        self.assertGreater(summary['total_rewarded'], 0)
        self.assertGreater(summary['total_payout'], 0)
        self.assertIn('avg_health_score', summary)
        self.assertIn('daily_breakdown', summary)

    def test_backfill_missing_insights(self):
        """Test backfilling missing insight records."""
        network = NetworkPostbackConfigFactory()
        start_date = date.today() - timedelta(days=5)
        end_date = date.today() - timedelta(days=1)
        
        processed_count = PostbackInsightService.backfill_missing_insights(
            network, start_date, end_date
        )
        
        self.assertEqual(processed_count, 5)
        
        # Verify insights were created
        for i in range(5):
            target_date = start_date + timedelta(days=i)
            insight_exists = PostbackInsight.objects.filter(
                network=network, date=target_date
            ).exists()
            self.assertTrue(insight_exists)


class TemplateServiceTests(TestCase):
    """Test TemplateService functionality."""

    def test_create_template(self):
        """Test template creation."""
        network = NetworkPostbackConfigFactory()
        
        template = TemplateService.create_template(
            network=network,
            name="Test Template",
            template_body="Lead: {{lead_id}}",
            variables={"lead_id": {"type": "string"}},
            required_variables=["lead_id"]
        )
        
        self.assertEqual(template.name, "Test Template")
        self.assertEqual(template.network, network)
        self.assertEqual(template.template_body, "Lead: {{lead_id}}")
        self.assertTrue(template.is_active)
        self.assertIsNotNone(template.integrity_hash)

    def test_render_template(self):
        """Test template rendering."""
        template = PostbackTemplateFactory(
            template_body="Lead: {{lead_id}}, Offer: {{offer_id}}"
        )
        
        context = {"lead_id": "LEAD123", "offer_id": "OFFER456"}
        rendered = TemplateService.render_template(
            str(template.id), context
        )
        
        self.assertEqual(rendered, "Lead: LEAD123, Offer: OFFER456")
        
        # Check usage was incremented
        template.refresh_from_db()
        self.assertEqual(template.usage_count, 1)

    def test_render_template_not_increment_usage(self):
        """Test template rendering without incrementing usage."""
        template = PostbackTemplateFactory()
        initial_usage = template.usage_count
        
        context = {"lead_id": "LEAD123"}
        TemplateService.render_template(
            str(template.id), context, increment_usage=False
        )
        
        template.refresh_from_db()
        self.assertEqual(template.usage_count, initial_usage)

    def test_render_template_not_found(self):
        """Test rendering non-existent template."""
        with self.assertRaises(ValueError) as cm:
            TemplateService.render_template("non-existent-id", {})
        
        self.assertIn("not found", str(cm.exception))

    def test_render_template_validation_error(self):
        """Test template rendering with validation error."""
        template = PostbackTemplateFactory(
            required_variables=["lead_id"]
        )
        
        context = {}  # Missing required variable
        with self.assertRaises(ValueError) as cm:
            TemplateService.render_template(str(template.id), context)
        
        self.assertIn("lead_id", str(cm.exception))

    def test_get_template_for_network(self):
        """Test getting template for network."""
        network = NetworkPostbackConfigFactory()
        template = PostbackTemplateFactory(network=network, name="Test Template")
        
        found = TemplateService.get_template_for_network(network, "Test Template")
        
        self.assertIsNotNone(found)
        self.assertEqual(found.id, template.id)
        
        # Test non-existent template
        not_found = TemplateService.get_template_for_network(
            network, "Non-existent"
        )
        self.assertIsNone(not_found)

    def test_list_network_templates(self):
        """Test listing network templates."""
        network = NetworkPostbackConfigFactory()
        
        # Create active and inactive templates
        PostbackTemplateFactory(network=network, is_active=True)
        PostbackTemplateFactory(network=network, is_active=False)
        PostbackTemplateFactory(network=network, is_active=True)
        
        # List only active
        active_templates = TemplateService.list_network_templates(
            network, active_only=True
        )
        self.assertEqual(len(active_templates), 2)
        
        # List all
        all_templates = TemplateService.list_network_templates(
            network, active_only=False
        )
        self.assertEqual(len(all_templates), 3)

    def test_update_template(self):
        """Test template update."""
        template = PostbackTemplateFactory()
        original_hash = template.integrity_hash
        
        updated = TemplateService.update_template(
            str(template.id),
            name="Updated Name",
            description="Updated description"
        )
        
        self.assertEqual(updated.name, "Updated Name")
        self.assertEqual(updated.description, "Updated description")
        self.assertNotEqual(updated.integrity_hash, original_hash)

    def test_deactivate_template(self):
        """Test template deactivation."""
        template = PostbackTemplateFactory(is_active=True)
        
        result = TemplateService.deactivate_template(str(template.id))
        
        self.assertTrue(result)
        template.refresh_from_db()
        self.assertFalse(template.is_active)

    def test_deactivate_nonexistent_template(self):
        """Test deactivating non-existent template."""
        result = TemplateService.deactivate_template("non-existent")
        self.assertFalse(result)

    def test_validate_template_syntax(self):
        """Test template syntax validation."""
        template_body = "Lead: {{lead_id}}, Offer: {{offer_id}}"
        variables = {"lead_id": "string", "offer_id": "string"}
        
        result = TemplateService.validate_template_syntax(
            template_body, variables
        )
        
        self.assertTrue(result['valid'])
        self.assertEqual(result['found_variables'], ['lead_id', 'offer_id'])
        self.assertEqual(result['variable_count'], 2)

    def test_validate_template_syntax_undefined_variables(self):
        """Test template syntax validation with undefined variables."""
        template_body = "Lead: {{lead_id}}, Offer: {{offer_id}}"
        variables = {"lead_id": "string"}  # Missing offer_id
        
        result = TemplateService.validate_template_syntax(
            template_body, variables
        )
        
        self.assertFalse(result['valid'])
        self.assertIn('offer_id', result['undefined_variables'])

    def test_get_template_usage_stats(self):
        """Test getting template usage statistics."""
        network = NetworkPostbackConfigFactory()
        
        # Create templates with different usage counts
        template1 = PostbackTemplateFactory(network=network, usage_count=10)
        template2 = PostbackTemplateFactory(network=network, usage_count=5)
        
        stats = TemplateService.get_template_usage_stats(network)
        
        self.assertEqual(len(stats), 2)
        # Should be ordered by usage count (descending)
        self.assertEqual(stats[0]['usage_count'], 10)
        self.assertEqual(stats[1]['usage_count'], 5)

    def test_clone_template(self):
        """Test template cloning."""
        original = PostbackTemplateFactory(
            template_body="Lead: {{lead_id}}",
            variables={"lead_id": "string"}
        )
        
        cloned = TemplateService.clone_template(
            str(original.id), "Cloned Template"
        )
        
        self.assertEqual(cloned.name, "Cloned Template")
        self.assertEqual(cloned.network, original.network)
        self.assertEqual(cloned.template_body, original.template_body)
        self.assertEqual(cloned.variables, original.variables)
        self.assertTrue(cloned.is_active)
        self.assertNotEqual(cloned.id, original.id)

    def test_clone_template_to_different_network(self):
        """Test cloning template to different network."""
        original_network = NetworkPostbackConfigFactory()
        target_network = NetworkPostbackConfigFactory()
        
        original = PostbackTemplateFactory(
            network=original_network,
            template_body="Lead: {{lead_id}}"
        )
        
        cloned = TemplateService.clone_template(
            str(original.id), "Cloned Template", target_network
        )
        
        self.assertEqual(cloned.network, target_network)
        self.assertEqual(cloned.template_body, original.template_body)

    def test_verify_template_integrity(self):
        """Test template integrity verification."""
        template = PostbackTemplateFactory()
        
        # Should be valid initially
        self.assertTrue(TemplateService.verify_template_integrity(str(template.id)))
        
        # Tamper with data
        template.template_body = "Tampered content"
        template.save()
        
        # Should detect tampering
        self.assertFalse(TemplateService.verify_template_integrity(str(template.id)))

    def test_batch_verify_integrity(self):
        """Test batch integrity verification."""
        network = NetworkPostbackConfigFactory()
        
        # Create valid and invalid templates
        valid_template = PostbackTemplateFactory(network=network)
        invalid_template = PostbackTemplateFactory(network=network)
        
        # Tamper with invalid template
        invalid_template.template_body = "Tampered"
        invalid_template.save()
        
        results = TemplateService.batch_verify_integrity(network)
        
        self.assertEqual(results['total'], 2)
        self.assertEqual(results['valid'], 1)
        self.assertEqual(results['invalid'], 1)
        self.assertEqual(len(results['invalid_templates']), 1)


class PostbackServiceIntegrationTests(TestCase):
    """Test integration of new services with postback processing."""

    def test_check_rate_limit_success(self):
        """Test successful rate limit check."""
        network = NetworkPostbackConfigFactory()
        PostbackRateLimitFactory(network=network, max_per_minute=100)
        
        # Should not raise exception
        _check_rate_limit(network)

    def test_check_rate_limit_exceeded(self):
        """Test rate limit exceeded exception."""
        network = NetworkPostbackConfigFactory()
        rate_limit = PostbackRateLimitFactory(network=network, max_per_minute=1)
        
        # Simulate rate limit exceeded
        rate_limit.current_count = 5
        rate_limit.save()
        
        with self.assertRaises(RateLimitExceededException):
            _check_rate_limit(network)

    def test_check_ip_enhanced_success(self):
        """Test successful enhanced IP check."""
        network = NetworkPostbackConfigFactory()
        PostbackIPWhitelistFactory(
            network=network,
            ip_address="192.168.1.0/24",
            is_active=True
        )
        
        # Should not raise exception
        result = _check_ip_enhanced("192.168.1.100", network)
        self.assertTrue(result)

    def test_check_ip_enhanced_not_whitelisted(self):
        """Test IP not in enhanced whitelist."""
        network = NetworkPostbackConfigFactory()
        PostbackIPWhitelistFactory(
            network=network,
            ip_address="192.168.1.0/24",
            is_active=True
        )
        
        with self.assertRaises(IPNotWhitelistedException):
            _check_ip_enhanced("10.0.0.1", network)

    def test_check_ip_enhanced_legacy_whitelist(self):
        """Test enhanced IP check with legacy whitelist."""
        network = NetworkPostbackConfigFactory(ip_whitelist=["10.0.0.0/8"])
        
        # Should work with legacy whitelist
        result = _check_ip_enhanced("10.0.0.1", network)
        self.assertTrue(result)

    def test_update_analytics_new_insight(self):
        """Test analytics update for new insight."""
        network = NetworkPostbackConfigFactory()
        log = PostbackLogFactory(
            network=network,
            status=PostbackStatus.REWARDED,
            payout="10.00",
            points_awarded=100,
            processed_at=timezone.now(),
            received_at=timezone.now()
        )
        
        _update_analytics(log, network)
        
        # Verify insight was created/updated
        insight = PostbackInsight.objects.get(network=network, date=timezone.now().date())
        self.assertEqual(insight.received_count, 1)
        self.assertEqual(insight.rewarded_count, 1)
        self.assertEqual(float(insight.total_payout), 10.00)
        self.assertEqual(insight.total_points_awarded, 100)

    def test_update_analytics_existing_insight(self):
        """Test analytics update for existing insight."""
        network = NetworkPostbackConfigFactory()
        existing_insight = PostbackInsightFactory(
            network=network,
            date=timezone.now().date(),
            received_count=5,
            rewarded_count=3,
            total_payout=15.00,
            total_points_awarded=300
        )
        
        log = PostbackLogFactory(
            network=network,
            status=PostbackStatus.REWARDED,
            payout="5.00",
            points_awarded=50,
            processed_at=timezone.now(),
            received_at=timezone.now()
        )
        
        _update_analytics(log, network)
        
        # Verify insight was updated
        existing_insight.refresh_from_db()
        self.assertEqual(existing_insight.received_count, 6)
        self.assertEqual(existing_insight.rewarded_count, 4)
        self.assertEqual(float(existing_insight.total_payout), 20.00)
        self.assertEqual(existing_insight.total_points_awarded, 350)

    def test_update_analytics_different_statuses(self):
        """Test analytics update for different postback statuses."""
        network = NetworkPostbackConfigFactory()
        
        # Test different statuses
        statuses = [
            (PostbackStatus.VALIDATED, 'validated_count', 0),
            (PostbackStatus.REWARDED, 'rewarded_count', 100),
            (PostbackStatus.REJECTED, 'rejected_count', 0),
            (PostbackStatus.DUPLICATE, 'duplicate_count', 0),
            (PostbackStatus.FAILED, 'failed_count', 0),
        ]
        
        for status, field, points in statuses:
            log = PostbackLogFactory(
                network=network,
                status=status,
                points_awarded=points,
                processed_at=timezone.now(),
                received_at=timezone.now()
            )
            
            _update_analytics(log, network)
            
            insight = PostbackInsight.objects.get(network=network, date=timezone.now().date())
            self.assertEqual(getattr(insight, field), 1)
