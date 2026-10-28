# =============================================================================
# fraud_detection/tests/test_vpn_proxy_detector.py
# =============================================================================
"""
VPN/Proxy Detector Tests.

Comprehensive tests for VPN and proxy detection including
IP analysis, threat intelligence integration, and pattern recognition.
"""

import json
import pytest
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from api.fraud_detection.detectors.VPNProxyDetector import VPNProxyDetector
from api.fraud_detection.models import IPReputation, FraudAttempt
from api.fraud_detection.choices import FraudAttemptType
from .factories import (
    UserFactory, IPReputationFactory, FraudAttemptFactory,
    FraudTestDataGenerator
)


class TestVPNProxyDetector(TestCase):
    """Test cases for VPNProxyDetector."""
    
    def setUp(self):
        """Set up test data."""
        self.detector = VPNProxyDetector()
        self.user = UserFactory.create()
        
    def test_detect_vpn_connection(self):
        """Test VPN connection detection."""
        # Create IP reputation with VPN indicators
        ip_rep = IPReputationFactory.create(
            ip_address='192.168.1.100',
            is_vpn=True,
            fraud_score=60
        )
        
        result = self.detector.detect_vpn_proxy(self.user.id, '192.168.1.100')
        
        self.assertIsInstance(result, dict)
        self.assertIn('is_vpn', result)
        self.assertIn('is_proxy', result)
        self.assertIn('is_tor', result)
        self.assertIn('risk_score', result)
        self.assertIn('evidence', result)
        
        self.assertTrue(result['is_vpn'])
        self.assertGreaterEqual(result['risk_score'], 50)
    
    def test_detect_proxy_connection(self):
        """Test proxy connection detection."""
        # Create IP reputation with proxy indicators
        ip_rep = IPReputationFactory.create(
            ip_address='192.168.1.101',
            is_proxy=True,
            fraud_score=55
        )
        
        result = self.detector.detect_vpn_proxy(self.user.id, '192.168.1.101')
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result['is_proxy'])
        self.assertGreaterEqual(result['risk_score'], 45)
    
    def test_detect_tor_connection(self):
        """Test Tor connection detection."""
        # Create IP reputation with Tor indicators
        ip_rep = IPReputationFactory.create(
            ip_address='192.168.1.102',
            is_tor=True,
            fraud_score=80
        )
        
        result = self.detector.detect_vpn_proxy(self.user.id, '192.168.1.102')
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result['is_tor'])
        self.assertGreaterEqual(result['risk_score'], 70)
    
    def test_detect_clean_connection(self):
        """Test detection of clean (non-VPN/proxy) connection."""
        # Create IP reputation without VPN/proxy indicators
        ip_rep = IPReputationFactory.create(
            ip_address='192.168.1.103',
            is_vpn=False,
            is_proxy=False,
            is_tor=False,
            fraud_score=10
        )
        
        result = self.detector.detect_vpn_proxy(self.user.id, '192.168.1.103')
        
        self.assertIsInstance(result, dict)
        self.assertFalse(result['is_vpn'])
        self.assertFalse(result['is_proxy'])
        self.assertFalse(result['is_tor'])
        self.assertLess(result['risk_score'], 20)
    
    def test_analyze_ip_reputation(self):
        """Test IP reputation analysis."""
        # Create IP with mixed reputation
        ip_rep = IPReputationFactory.create(
            ip_address='192.168.1.104',
            fraud_score=65,
            spam_score=45,
            malware_score=20,
            total_requests=1000,
            fraud_attempts=15
        )
        
        analysis = self.detector.analyze_ip_reputation('192.168.1.104')
        
        self.assertIsInstance(analysis, dict)
        self.assertIn('reputation_score', analysis)
        self.assertIn('risk_factors', analysis)
        self.assertIn('threat_indicators', analysis)
        self.assertIn('recommendations', analysis)
        
        self.assertGreater(analysis['reputation_score'], 50)
    
    def test_check_known_vpn_ranges(self):
        """Test checking against known VPN ranges."""
        # Test with known VPN IP ranges
        vpn_ips = [
            '1.1.1.1',  # Cloudflare (can be VPN)
            '8.8.8.8',  # Google DNS (can be VPN)
            '208.67.222.222',  # OpenDNS
        ]
        
        for ip in vpn_ips:
            result = self.detector.check_known_vpn_ranges(ip)
            
            self.assertIsInstance(result, dict)
            self.assertIn('is_known_vpn', result)
            self.assertIn('provider', result)
            self.assertIn('confidence', result)
    
    def test_analyze_connection_patterns(self):
        """Test connection pattern analysis."""
        # Create user with multiple connections from different IPs
        ips = ['192.168.1.100', '192.168.1.101', '192.168.1.102']
        
        for ip in ips:
            FraudAttemptFactory.create(
                user=self.user,
                evidence_data=json.dumps({'ip_address': ip}),
                status='confirmed'
            )
        
        patterns = self.detector.analyze_connection_patterns(self.user.id)
        
        self.assertIsInstance(patterns, dict)
        self.assertIn('ip_diversity', patterns)
        self.assertIn('switching_frequency', patterns)
        self.assertIn('geographic_inconsistency', patterns)
        self.assertIn('risk_assessment', patterns)
    
    def test_detect_ip_switching(self):
        """Test IP switching detection."""
        # Create user with frequent IP changes
        base_time = timezone.now() - timedelta(hours=24)
        
        for i in range(10):
            ip = f'192.168.1.{100 + i}'
            FraudAttemptFactory.create(
                user=self.user,
                created_at=base_time + timedelta(hours=i*2),
                evidence_data=json.dumps({'ip_address': ip}),
                status='confirmed'
            )
        
        switching = self.detector.detect_ip_switching(self.user.id)
        
        self.assertIsInstance(switching, dict)
        self.assertIn('is_switching', switching)
        self.assertIn('switch_frequency', switching)
        self.assertIn('unique_ips', switching)
        self.assertIn('risk_score', switching)
        
        self.assertTrue(switching['is_switching'])
        self.assertEqual(switching['unique_ips'], 10)
    
    def test_analyze_geographic_consistency(self):
        """Test geographic consistency analysis."""
        # Create user with connections from different countries
        locations = [
            {'ip_address': '192.168.1.100', 'country': 'US', 'city': 'New York'},
            {'ip_address': '192.168.1.101', 'country': 'GB', 'city': 'London'},
            {'ip_address': '192.168.1.102', 'country': 'JP', 'city': 'Tokyo'},
        ]
        
        for location in locations:
            FraudAttemptFactory.create(
                user=self.user,
                evidence_data=json.dumps(location),
                status='confirmed'
            )
        
        consistency = self.detector.analyze_geographic_consistency(self.user.id)
        
        self.assertIsInstance(consistency, dict)
        self.assertIn('is_consistent', consistency)
        self.assertIn('countries_visited', consistency)
        self.assertIn('travel_speed', consistency)
        self.assertIn('anomaly_score', consistency)
        
        self.assertFalse(consistency['is_consistent'])
        self.assertGreaterEqual(consistency['anomaly_score'], 60)
    
    def test_check_threat_intelligence(self):
        """Test threat intelligence checking."""
        # Test with various threat indicators
        threat_data = {
            'ip_address': '192.168.1.105',
            'threat_feeds': [
                {'source': 'feed1', 'threat_type': 'vpn', 'confidence': 0.9},
                {'source': 'feed2', 'threat_type': 'proxy', 'confidence': 0.7},
            ]
        }
        
        with patch.object(self.detector, '_query_threat_feeds') as mock_query:
            mock_query.return_value = threat_data['threat_feeds']
            
            result = self.detector.check_threat_intelligence('192.168.1.105')
            
            self.assertIsInstance(result, dict)
            self.assertIn('threat_score', result)
            self.assertIn('threat_types', result)
            self.assertIn('sources', result)
            self.assertIn('confidence', result)
            
            mock_query.assert_called_once_with('192.168.1.105')
    
    def test_analyze_user_behavior_with_vpn(self):
        """Test user behavior analysis with VPN usage."""
        # Create user with VPN usage
        vpn_ip = '192.168.1.106'
        
        # Create VPN IP reputation
        IPReputationFactory.create(
            ip_address=vpn_ip,
            is_vpn=True,
            fraud_score=70
        )
        
        # Create user activity with VPN
        for i in range(5):
            FraudAttemptFactory.create(
                user=self.user,
                evidence_data=json.dumps({'ip_address': vpn_ip}),
                status='confirmed'
            )
        
        behavior = self.detector.analyze_user_behavior_with_vpn(self.user.id)
        
        self.assertIsInstance(behavior, dict)
        self.assertIn('vpn_usage_pattern', behavior)
        self.assertIn('activity_risk', behavior)
        self.assertIn('behavioral_anomalies', behavior)
        self.assertIn('recommendations', behavior)
    
    def test_calculate_vpn_risk_score(self):
        """Test VPN risk score calculation."""
        # Test different VPN scenarios
        scenarios = [
            {'is_vpn': True, 'fraud_score': 80, 'spam_score': 60},
            {'is_vpn': True, 'fraud_score': 30, 'spam_score': 20},
            {'is_vpn': False, 'fraud_score': 10, 'spam_score': 5},
        ]
        
        for scenario in scenarios:
            risk_score = self.detector._calculate_vpn_risk_score(scenario)
            
            self.assertIsInstance(risk_score, float)
            self.assertGreaterEqual(risk_score, 0)
            self.assertLessEqual(risk_score, 100)
            
            if scenario['is_vpn']:
                self.assertGreater(risk_score, 30)
            else:
                self.assertLess(risk_score, 25)
    
    def test_detect_vpn_service_provider(self):
        """Test VPN service provider detection."""
        # Test with known VPN provider IPs
        provider_tests = [
            {'ip': '1.1.1.1', 'expected_provider': 'Cloudflare'},
            {'ip': '8.8.8.8', 'expected_provider': 'Google'},
            {'ip': '208.67.222.222', 'expected_provider': 'OpenDNS'},
        ]
        
        for test in provider_tests:
            provider = self.detector.detect_vpn_service_provider(test['ip'])
            
            self.assertIsInstance(provider, dict)
            self.assertIn('provider_name', provider)
            self.assertIn('confidence', provider)
            self.assertIn('service_type', provider)
    
    def test_analyze_connection_timing(self):
        """Test connection timing analysis."""
        # Create user with connections at suspicious times
        suspicious_times = [
            timezone.now().replace(hour=2, minute=0),  # 2 AM
            timezone.now().replace(hour=3, minute=30),  # 3:30 AM
            timezone.now().replace(hour=4, minute=15),  # 4:15 AM
        ]
        
        for i, time in enumerate(suspicious_times):
            FraudAttemptFactory.create(
                user=self.user,
                created_at=time,
                evidence_data=json.dumps({'ip_address': f'192.168.1.{100 + i}'}),
                status='confirmed'
            )
        
        timing = self.detector.analyze_connection_timing(self.user.id)
        
        self.assertIsInstance(timing, dict)
        self.assertIn('suspicious_hours', timing)
        self.assertIn('timing_pattern', timing)
        self.assertIn('anomaly_score', timing)
        self.assertIn('risk_assessment', timing)
    
    def test_batch_vpn_detection(self):
        """Test batch VPN detection."""
        # Create multiple users with VPN usage
        users = UserFactory.create_batch(5)
        vpn_ip = '192.168.1.200'
        
        # Create VPN IP reputation
        IPReputationFactory.create(
            ip_address=vpn_ip,
            is_vpn=True,
            fraud_score=75
        )
        
        # Create activity for all users
        for user in users:
            FraudAttemptFactory.create(
                user=user,
                evidence_data=json.dumps({'ip_address': vpn_ip}),
                status='confirmed'
            )
        
        # Batch detection
        results = self.detector.batch_detect_vpn_proxy([u.id for u in users])
        
        self.assertIsInstance(results, dict)
        self.assertEqual(len(results), 5)
        
        for user_id, result in results.items():
            self.assertIsInstance(result, dict)
            self.assertIn('is_vpn', result)
            self.assertIn('risk_score', result)
            self.assertTrue(result['is_vpn'])
    
    def test_detector_configuration(self):
        """Test detector configuration options."""
        # Test custom configuration
        custom_detector = VPNProxyDetector(
            vpn_threshold=0.8,
            proxy_threshold=0.7,
            tor_threshold=0.9,
            risk_weight=0.6
        )
        
        ip_rep = IPReputationFactory.create(
            ip_address='192.168.1.201',
            is_vpn=True,
            fraud_score=85
        )
        
        result = custom_detector.detect_vpn_proxy(self.user.id, '192.168.1.201')
        
        self.assertIsInstance(result, dict)
        self.assertTrue(result['is_vpn'])
        self.assertGreaterEqual(result['risk_score'], 50)
    
    @patch('fraud_detection.detectors.VPNProxyDetector.logger')
    def test_error_handling(self, mock_logger):
        """Test error handling in VPN/proxy detection."""
        # Test with invalid user ID
        with self.assertRaises(ValueError):
            self.detector.detect_vpn_proxy(999999, '192.168.1.1')
        
        # Test with invalid IP address
        with self.assertRaises(ValueError):
            self.detector.detect_vpn_proxy(self.user.id, 'invalid_ip')
        
        # Verify error logging
        mock_logger.error.assert_called()
    
    def test_evidence_collection(self):
        """Test evidence collection for VPN/proxy detection."""
        # Create IP with multiple threat indicators
        ip_rep = IPReputationFactory.create(
            ip_address='192.168.1.202',
            is_vpn=True,
            is_proxy=True,
            fraud_score=80,
            spam_score=60,
            malware_score=30
        )
        
        result = self.detector.detect_vpn_proxy(self.user.id, '192.168.1.202')
        
        self.assertIn('evidence', result)
        evidence = result['evidence']
        
        self.assertIsInstance(evidence, dict)
        self.assertIn('vpn_indicators', evidence)
        self.assertIn('proxy_indicators', evidence)
        self.assertIn('reputation_risk', evidence)
        
        # Verify evidence details
        for evidence_type, details in evidence.items():
            self.assertIsInstance(details, dict)
            self.assertIn('score', details)
            self.assertIn('description', details)
    
    def test_confidence_calculation(self):
        """Test confidence score calculation."""
        # Test with strong evidence
        strong_evidence = {
            'vpn_indicators': {'score': 80, 'confidence': 0.9},
            'reputation_risk': {'score': 70, 'confidence': 0.8},
        }
        
        confidence = self.detector._calculate_confidence(strong_evidence)
        
        self.assertIsInstance(confidence, float)
        self.assertGreaterEqual(confidence, 0.7)
        self.assertLessEqual(confidence, 1.0)
        
        # Test with weak evidence
        weak_evidence = {
            'minor_indicator': {'score': 20, 'confidence': 0.3},
        }
        
        confidence = self.detector._calculate_confidence(weak_evidence)
        
        self.assertLess(confidence, 0.5)
    
    def test_cache_performance(self):
        """Test cache performance for repeated lookups."""
        # Create IP reputation
        ip_rep = IPReputationFactory.create(
            ip_address='192.168.1.203',
            is_vpn=True,
            fraud_score=75
        )
        
        # Test multiple lookups
        import time
        start_time = time.time()
        
        for _ in range(10):
            result = self.detector.detect_vpn_proxy(self.user.id, '192.168.1.203')
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should be fast due to caching
        self.assertLess(processing_time, 1.0)  # 1 second max for 10 lookups
        
        # Verify consistent results
        self.assertTrue(result['is_vpn'])
        self.assertGreater(result['risk_score'], 60)


class TestVPNProxyDetectorIntegration(TestCase):
    """Integration tests for VPNProxyDetector."""
    
    def setUp(self):
        """Set up integration test data."""
        self.detector = VPNProxyDetector()
        self.scenario = FraudTestDataGenerator.create_ip_reputation_scenario(
            ip_count=30
        )
    
    def test_end_to_end_vpn_detection(self):
        """Test end-to-end VPN detection workflow."""
        user = UserFactory.create()
        
        # Create VPN IP reputation
        vpn_ip = '192.168.1.250'
        IPReputationFactory.create(
            ip_address=vpn_ip,
            is_vpn=True,
            is_proxy=False,
            fraud_score=80,
            spam_score=60,
        )
        
        # Simulate user activity with VPN
        FraudAttemptFactory.create(
            user=user,
            evidence_data=json.dumps({'ip_address': vpn_ip}),
            status='confirmed',
            amount_involved=150.00
        )
        
        # Detect VPN usage
        result = self.detector.detect_vpn_proxy(user.id, vpn_ip)
        
        # Verify detection result
        self.assertTrue(result['is_vpn'])
        self.assertGreaterEqual(result['risk_score'], 70)
        
        # Create fraud attempt if risk is high enough
        if result['risk_score'] >= 60:
            attempt = FraudAttempt.objects.create(
                user=user,
                attempt_type=FraudAttemptType.VPN_PROXY,
                description=f"VPN usage detected: {result['risk_score']}",
                detected_by='VPNProxyDetector',
                fraud_score=result['risk_score'],
                confidence_score=0.9,
                evidence_data=json.dumps(result['evidence']),
                amount_involved=150.00,
            )
            
            self.assertIsInstance(attempt, FraudAttempt)
            self.assertEqual(attempt.fraud_score, result['risk_score'])
    
    def test_multiple_vpn_providers_detection(self):
        """Test detection of multiple VPN providers."""
        user = UserFactory.create()
        
        # Create multiple VPN provider IPs
        vpn_providers = [
            {'ip': '1.1.1.1', 'provider': 'Cloudflare'},
            {'ip': '8.8.8.8', 'provider': 'Google'},
            {'ip': '208.67.222.222', 'provider': 'OpenDNS'},
        ]
        
        for provider_info in vpn_providers:
            IPReputationFactory.create(
                ip_address=provider_info['ip'],
                is_vpn=True,
                fraud_score=70
            )
            
            FraudAttemptFactory.create(
                user=user,
                evidence_data=json.dumps({'ip_address': provider_info['ip']}),
                status='confirmed'
            )
        
        # Analyze connection patterns
        patterns = self.detector.analyze_connection_patterns(user.id)
        
        self.assertIsInstance(patterns, dict)
        self.assertIn('ip_diversity', patterns)
        self.assertIn('provider_diversity', patterns)
        self.assertIn('risk_assessment', patterns)
        
        # Should detect multiple VPN usage
        self.assertGreater(patterns['ip_diversity'], 2)
    
    def test_vpn_with_geographic_anomalies(self):
        """Test VPN usage combined with geographic anomalies."""
        user = UserFactory.create()
        
        # Create VPN IP in one country but user activity in another
        vpn_ip = '192.168.1.251'
        IPReputationFactory.create(
            ip_address=vpn_ip,
            is_vpn=True,
            country='US',
            city='New York'
        )
        
        # Create user activity appearing from different country
        FraudAttemptFactory.create(
            user=user,
            evidence_data=json.dumps({
                'ip_address': vpn_ip,
                'actual_country': 'GB',
                'actual_city': 'London'
            }),
            status='confirmed'
        )
        
        # Analyze geographic consistency
        consistency = self.detector.analyze_geographic_consistency(user.id)
        
        self.assertIsInstance(consistency, dict)
        self.assertFalse(consistency['is_consistent'])
        self.assertGreater(consistency['anomaly_score'], 70)
        
        # Should detect VPN masking location
        self.assertIn('vpn_location_masking', consistency)
    
    def test_vpn_pattern_evolution(self):
        """Test VPN usage pattern evolution over time."""
        user = UserFactory.create()
        
        # Create evolving VPN usage pattern
        base_time = timezone.now() - timedelta(days=30)
        
        for day in range(30):
            # Gradually increase VPN usage
            if day < 10:
                # No VPN initially
                ip = f'192.168.1.{day}'
                is_vpn = False
            elif day < 20:
                # Occasional VPN
                ip = '192.168.1.200'
                is_vpn = True
            else:
                # Consistent VPN
                ip = '192.168.1.201'
                is_vpn = True
            
            if is_vpn:
                IPReputationFactory.create(
                    ip_address=ip,
                    is_vpn=True,
                    fraud_score=70
                )
            
            FraudAttemptFactory.create(
                user=user,
                created_at=base_time + timedelta(days=day),
                evidence_data=json.dumps({'ip_address': ip}),
                status='confirmed'
            )
        
        # Analyze pattern evolution
        evolution = self.detector.analyze_vpn_pattern_evolution(user.id)
        
        self.assertIsInstance(evolution, dict)
        self.assertIn('usage_trend', evolution)
        self.assertIn('escalation_points', evolution)
        self.assertIn('risk_evolution', evolution)
        
        # Should detect increasing VPN usage
        self.assertEqual(evolution['usage_trend'], 'increasing')
    
    def test_performance_with_large_dataset(self):
        """Test performance with large dataset."""
        # Create large number of users and IP reputations
        users = UserFactory.create_batch(50)
        
        # Create mixed IP reputations
        clean_ips = IPReputationFactory.create_batch(
            25,
            is_vpn=False,
            is_proxy=False,
            fraud_score=fuzzy.FuzzyInteger(0, 30)
        )
        
        vpn_ips = IPReputationFactory.create_batch(
            25,
            is_vpn=True,
            fraud_score=fuzzy.FuzzyInteger(60, 90)
        )
        
        all_ips = clean_ips + vpn_ips
        
        # Create user activity
        for user in users:
            ip = random.choice(all_ips)
            FraudAttemptFactory.create(
                user=user,
                evidence_data=json.dumps({'ip_address': ip.ip_address}),
                status='confirmed'
            )
        
        # Test batch detection performance
        import time
        start_time = time.time()
        
        user_ids = [user.id for user in users]
        results = self.detector.batch_detect_vpn_proxy(user_ids)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(processing_time, 5.0)  # 5 seconds max
        self.assertEqual(len(results), 50)
        
        # Verify results
        vpn_count = sum(1 for result in results.values() if result.get('is_vpn', False))
        self.assertGreater(vpn_count, 0)  # Should detect some VPN usage


if __name__ == '__main__':
    import random
    from factory import fuzzy
    
    # Add imports for integration tests
    TestVPNProxyDetectorIntegration.setUp = lambda self: (
        setattr(self, 'detector', VPNProxyDetector()) or
        setattr(self, 'scenario', FraudTestDataGenerator.create_ip_reputation_scenario(ip_count=30))
    )
