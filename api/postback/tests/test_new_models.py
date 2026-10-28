"""test_new_models.py – Tests for new postback models."""
import hashlib
import json
from decimal import Decimal
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from api.postback.tests.factories import (
    NetworkPostbackConfigFactory,
    PostbackInsightFactory,
    PostbackTemplateFactory,
    PostbackIPWhitelistFactory,
    PostbackRateLimitFactory,
    AnomalousPostbackInsightFactory,
    InactivePostbackTemplateFactory,
    BlockedRateLimitFactory,
    HighUsageRateLimitFactory,
)


class PostbackInsightTests(TestCase):
    """Test PostbackInsight model functionality."""

    def test_insight_creation(self):
        """Test basic insight creation."""
        insight = PostbackInsightFactory()
        self.assertIsNotNone(insight.id)
        self.assertIsNotNone(insight.network)
        self.assertIsNotNone(insight.date)
        self.assertEqual(insight.received_count, 100)
        self.assertEqual(insight.rewarded_count, 60)
        self.assertFalse(insight.anomaly_detected)

    def test_health_score_calculation(self):
        """Test health score calculation logic."""
        insight = PostbackInsightFactory(
            received_count=100,
            validated_count=80,
            rewarded_count=60,
            rejected_count=15,
            duplicate_count=5,
            failed_count=0
        )
        
        health_score = insight.calculate_health_score()
        self.assertIsInstance(health_score, Decimal)
        self.assertGreaterEqual(health_score, 0)
        self.assertLessEqual(health_score, 100)

    def test_health_score_with_zero_received(self):
        """Test health score with no received postbacks."""
        insight = PostbackInsightFactory(received_count=0)
        health_score = insight.calculate_health_score()
        self.assertEqual(health_score, Decimal('0'))

    def test_integrity_hash_generation(self):
        """Test SHA-256 integrity hash generation."""
        insight = PostbackInsightFactory()
        hash_value = insight.generate_integrity_hash()
        
        # Should be 64 characters (SHA-256 hex)
        self.assertEqual(len(hash_value), 64)
        self.assertIsInstance(hash_value, str)
        
        # Should be consistent for same data
        hash_value2 = insight.generate_integrity_hash()
        self.assertEqual(hash_value, hash_value2)

    def test_integrity_verification(self):
        """Test integrity hash verification."""
        insight = PostbackInsightFactory()
        
        # Initially no hash, should be invalid
        self.assertFalse(insight.verify_integrity())
        
        # Generate hash and verify
        insight.integrity_hash = insight.generate_integrity_hash()
        insight.save()
        self.assertTrue(insight.verify_integrity())

    def test_integrity_verification_tampering(self):
        """Test integrity verification detects tampering."""
        insight = PostbackInsightFactory()
        insight.integrity_hash = insight.generate_integrity_hash()
        insight.save()
        
        # Tamper with data
        insight.received_count = 999
        insight.save()
        
        # Should detect tampering
        self.assertFalse(insight.verify_integrity())

    def test_anomaly_detection_flag(self):
        """Test anomaly detection functionality."""
        normal_insight = PostbackInsightFactory()
        anomalous_insight = AnomalousPostbackInsightFactory()
        
        self.assertFalse(normal_insight.anomaly_detected)
        self.assertTrue(anomalous_insight.anomaly_detected)
        self.assertIsInstance(anomalous_insight.anomaly_details, dict)


class PostbackTemplateTests(TestCase):
    """Test PostbackTemplate model functionality."""

    def test_template_creation(self):
        """Test basic template creation."""
        template = PostbackTemplateFactory()
        self.assertIsNotNone(template.id)
        self.assertIsNotNone(template.network)
        self.assertIsNotNone(template.name)
        self.assertIsNotNone(template.template_body)
        self.assertTrue(template.is_active)
        self.assertEqual(template.usage_count, 0)

    def test_template_rendering(self):
        """Test template rendering with context."""
        template = PostbackTemplateFactory(
            template_body="Lead: {{lead_id}}, Offer: {{offer_id}}, Amount: {{amount}}"
        )
        
        context = {
            "lead_id": "LEAD123",
            "offer_id": "OFFER456",
            "amount": "$25.00"
        }
        
        rendered = template.render_template(context)
        expected = "Lead: LEAD123, Offer: OFFER456, Amount: $25.00"
        self.assertEqual(rendered, expected)

    def test_template_rendering_missing_required_variable(self):
        """Test template rendering fails with missing required variables."""
        template = PostbackTemplateFactory(
            required_variables=["lead_id", "offer_id"]
        )
        
        context = {"lead_id": "LEAD123"}  # Missing offer_id
        
        with self.assertRaises(ValueError) as cm:
            template.render_template(context)
        
        self.assertIn("offer_id", str(cm.exception))

    def test_template_rendering_with_validation_regex(self):
        """Test template rendering with regex validation."""
        template = PostbackTemplateFactory(
            template_body="Lead: {{lead_id}}",
            validation_regex=r"^Lead: [A-Z0-9]{6,20}$"
        )
        
        # Valid context
        valid_context = {"lead_id": "LEAD123"}
        rendered = template.render_template(valid_context)
        self.assertEqual(rendered, "Lead: LEAD123")
        
        # Invalid context
        invalid_context = {"lead_id": "invalid_lead"}
        with self.assertRaises(ValueError):
            template.render_template(invalid_context)

    def test_template_usage_tracking(self):
        """Test template usage tracking."""
        template = PostbackTemplateFactory()
        initial_usage = template.usage_count
        
        template.increment_usage()
        template.refresh_from_db()
        
        self.assertEqual(template.usage_count, initial_usage + 1)
        self.assertIsNotNone(template.last_used_at)

    def test_ip_whitelist_single_ip(self):
        """Test IP whitelist with single IP address."""
        whitelist = PostbackIPWhitelistFactory(
            ip_address="192.168.1.100"
        )
        
        # Should match exact IP
        self.assertTrue(whitelist.is_ip_allowed("192.168.1.100"))
        
        # Should not match different IP
        self.assertFalse(whitelist.is_ip_allowed("192.168.1.101"))

    def test_ip_whitelist_cidr_range(self):
        """Test IP whitelist with CIDR range."""
        whitelist = PostbackIPWhitelistFactory(
            ip_address="192.168.1.0/24"
        )
        
        # Should match IPs in range
        self.assertTrue(whitelist.is_ip_allowed("192.168.1.1"))
        self.assertTrue(whitelist.is_ip_allowed("192.168.1.254"))
        
        # Should not match IPs outside range
        self.assertFalse(whitelist.is_ip_allowed("192.168.2.1"))
        self.assertFalse(whitelist.is_ip_allowed("10.0.0.1"))

    def test_ip_whitelist_ipv6(self):
        """Test IP whitelist with IPv6 addresses."""
        whitelist = PostbackIPWhitelistFactory(
            ip_address="2001:db8::/32"
        )
        
        # Should match IPv6 in range
        self.assertTrue(whitelist.is_ip_allowed("2001:db8::1"))
        
        # Should not match IPv6 outside range
        self.assertFalse(whitelist.is_ip_allowed("2001:db9::1"))

    def test_ip_whitelist_priority_evaluation(self):
        """Test IP whitelist priority-based evaluation."""
        network = NetworkPostbackConfigFactory()
        
        # Create multiple whitelists with different priorities
        low_priority = PostbackIPWhitelistFactory(
            network=network,
            ip_address="192.168.1.0/24",
            priority=1
        )
        high_priority = PostbackIPWhitelistFactory(
            network=network,
            ip_address="192.168.1.100",
            priority=10
        )
        
        # Higher priority should be checked first
        # This would be tested in the service layer

    def test_ip_whitelist_usage_tracking(self):
        """Test IP whitelist usage tracking."""
        whitelist = PostbackIPWhitelistFactory()
        initial_usage = whitelist.usage_count
        
        whitelist.increment_usage()
        whitelist.refresh_from_db()
        
        self.assertEqual(whitelist.usage_count, initial_usage + 1)
        self.assertIsNotNone(whitelist.last_used_at)

    def test_rate_limit_basic_functionality(self):
        """Test basic rate limit functionality."""
        rate_limit = PostbackRateLimitFactory(
            max_per_minute=100,
            max_per_hour=5000,
            max_per_day=100000
        )
        
        self.assertEqual(rate_limit.max_per_minute, 100)
        self.assertEqual(rate_limit.max_per_hour, 5000)
        self.assertEqual(rate_limit.max_per_day, 100000)
        self.assertFalse(rate_limit.is_blocked)
        self.assertEqual(rate_limit.current_count, 0)

    def test_rate_limit_exceeded(self):
        """Test rate limit exceeded detection."""
        rate_limit = PostbackRateLimitFactory(max_per_minute=10)
        
        # Should not exceed when under limit
        self.assertFalse(rate_limit.is_rate_exceeded(5))
        
        # Should exceed when over limit
        self.assertTrue(rate_limit.is_rate_exceeded(15))

    def test_rate_limit_increment_count(self):
        """Test rate limit count increment."""
        rate_limit = PostbackRateLimitFactory(max_per_minute=10)
        
        # Should return True when under limit
        result = rate_limit.increment_count()
        self.assertTrue(result)
        self.assertEqual(rate_limit.current_count, 1)
        
        # Should return False when over limit
        for _ in range(9):  # Total 10 requests
            rate_limit.increment_count()
        
        result = rate_limit.increment_count()  # 11th request
        self.assertFalse(result)
        self.assertTrue(rate_limit.is_blocked)

    def test_rate_limit_violation_recording(self):
        """Test rate limit violation recording."""
        rate_limit = PostbackRateLimitFactory()
        initial_violations = rate_limit.total_violations
        
        rate_limit.record_violation()
        rate_limit.refresh_from_db()
        
        self.assertEqual(rate_limit.total_violations, initial_violations + 1)
        self.assertTrue(rate_limit.is_blocked)
        self.assertIsNotNone(rate_limit.blocked_until)

    def test_rate_limit_window_reset(self):
        """Test rate limit window reset."""
        rate_limit = HighUsageRateLimitFactory(current_count=50)
        
        rate_limit.reset_window()
        rate_limit.refresh_from_db()
        
        self.assertEqual(rate_limit.current_count, 0)
        self.assertIsNotNone(rate_limit.last_reset_at)

    def test_rate_limit_unblock_expired(self):
        """Test rate limit unblocking when block expires."""
        # Create a rate limit with expired block
        rate_limit = BlockedRateLimitFactory(
            blocked_until=timezone.now() - timedelta(hours=1)
        )
        
        rate_limit.reset_window()
        rate_limit.refresh_from_db()
        
        self.assertFalse(rate_limit.is_blocked)
        self.assertIsNone(rate_limit.blocked_until)

    def test_rate_limit_integrity_hash(self):
        """Test rate limit integrity hash generation."""
        rate_limit = PostbackRateLimitFactory()
        
        # Generate hash
        hash_value = rate_limit.generate_integrity_hash()
        self.assertEqual(len(hash_value), 64)
        
        # Verify integrity
        rate_limit.integrity_hash = hash_value
        rate_limit.save()
        self.assertTrue(rate_limit.verify_integrity())

    def test_template_integrity_hash(self):
        """Test template integrity hash generation."""
        template = PostbackTemplateFactory()
        
        # Generate hash
        hash_value = template.generate_integrity_hash()
        self.assertEqual(len(hash_value), 64)
        
        # Verify integrity
        template.integrity_hash = hash_value
        template.save()
        self.assertTrue(template.verify_integrity())

    def test_ip_whitelist_integrity_hash(self):
        """Test IP whitelist integrity hash generation."""
        whitelist = PostbackIPWhitelistFactory()
        
        # Generate hash
        hash_value = whitelist.generate_integrity_hash()
        self.assertEqual(len(hash_value), 64)
        
        # Verify integrity
        whitelist.integrity_hash = hash_value
        whitelist.save()
        self.assertTrue(whitelist.verify_integrity())

    def test_model_string_representations(self):
        """Test string representations of new models."""
        insight = PostbackInsightFactory()
        template = PostbackTemplateFactory()
        whitelist = PostbackIPWhitelistFactory()
        rate_limit = PostbackRateLimitFactory()
        
        # Test __str__ methods
        self.assertIn(str(insight.network.network_key), str(insight))
        self.assertIn(str(insight.date), str(insight))
        
        self.assertIn(template.name, str(template))
        self.assertIn(template.network.network_key, str(template))
        
        self.assertIn(whitelist.ip_address, str(whitelist))
        self.assertIn(whitelist.network.network_key, str(whitelist))
        
        self.assertIn(rate_limit.name, str(rate_limit))
        self.assertIn(rate_limit.network.network_key, str(rate_limit))
        self.assertIn(str(rate_limit.max_per_minute), str(rate_limit))

    def test_model_meta_constraints(self):
        """Test model meta constraints and unique constraints."""
        network = NetworkPostbackConfigFactory()
        
        # Test PostbackInsight unique constraint
        insight1 = PostbackInsightFactory(network=network, date=date.today())
        with self.assertRaises(Exception):  # Should raise IntegrityError
            PostbackInsightFactory(network=network, date=date.today())
        
        # Test PostbackTemplate unique constraint
        template1 = PostbackTemplateFactory(network=network, name="Test")
        with self.assertRaises(Exception):  # Should raise IntegrityError
            PostbackTemplateFactory(network=network, name="Test")
        
        # Test PostbackIPWhitelist unique constraint
        whitelist1 = PostbackIPWhitelistFactory(network=network, ip_address="192.168.1.1")
        with self.assertRaises(Exception):  # Should raise IntegrityError
            PostbackIPWhitelistFactory(network=network, ip_address="192.168.1.1")
        
        # Test PostbackRateLimit unique constraint
        rate_limit1 = PostbackRateLimitFactory(network=network, name="Test")
        with self.assertRaises(Exception):  # Should raise IntegrityError
            PostbackRateLimitFactory(network=network, name="Test")
