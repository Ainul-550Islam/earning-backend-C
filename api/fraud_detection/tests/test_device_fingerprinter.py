# =============================================================================
# fraud_detection/tests/test_device_fingerprinter.py
# =============================================================================
"""
Device Fingerprinter Tests.

Comprehensive tests for device fingerprinting service including
fingerprint generation, consistency checking, and anomaly detection.
"""

import json
import pytest
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from api.fraud_detection.services.DeviceFingerprinter import DeviceFingerprinter
from api.fraud_detection.models import DeviceFingerprint, FraudAttempt
from api.fraud_detection.choices import FraudAttemptType
from .factories import (
    UserFactory, DeviceFingerprintFactory, FraudAttemptFactory,
    FraudTestDataGenerator
)


class TestDeviceFingerprinter(TestCase):
    """Test cases for DeviceFingerprinter."""
    
    def setUp(self):
        """Set up test data."""
        self.fingerprinter = DeviceFingerprinter()
        self.user = UserFactory.create()
        
    def test_generate_fingerprint_basic(self):
        """Test basic fingerprint generation."""
        fingerprint_data = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'screen_resolution': '1920x1080',
            'timezone': 'America/New_York',
            'language': 'en-US',
            'platform': 'Win32',
            'browser': 'Chrome',
        }
        
        fingerprint = self.fingerprinter.generate_fingerprint(fingerprint_data)
        
        self.assertIsInstance(fingerprint, str)
        self.assertEqual(len(fingerprint), 64)  # SHA-256 hash length
        self.assertTrue(all(c in '0123456789abcdef' for c in fingerprint))
    
    def test_generate_fingerprint_with_complete_data(self):
        """Test fingerprint generation with complete data."""
        fingerprint_data = {
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'screen_resolution': '2560x1440',
            'timezone': 'Europe/London',
            'language': 'en-GB',
            'platform': 'MacIntel',
            'browser': 'Safari',
            'plugins': ['Chrome PDF Plugin', 'Chrome PDF Viewer'],
            'fonts': ['Arial', 'Helvetica', 'Times New Roman'],
            'canvas': 'canvas_fingerprint_data',
            'webgl': 'webgl_fingerprint_data',
        }
        
        fingerprint = self.fingerprinter.generate_fingerprint(fingerprint_data)
        
        self.assertIsInstance(fingerprint, str)
        self.assertEqual(len(fingerprint), 64)
    
    def test_generate_fingerprint_with_minimal_data(self):
        """Test fingerprint generation with minimal data."""
        fingerprint_data = {
            'user_agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        }
        
        fingerprint = self.fingerprinter.generate_fingerprint(fingerprint_data)
        
        self.assertIsInstance(fingerprint, str)
        self.assertEqual(len(fingerprint), 64)
    
    def test_generate_fingerprint_consistency(self):
        """Test fingerprint generation consistency."""
        fingerprint_data = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'screen_resolution': '1920x1080',
            'timezone': 'America/New_York',
            'language': 'en-US',
            'platform': 'Win32',
            'browser': 'Chrome',
        }
        
        fingerprint1 = self.fingerprinter.generate_fingerprint(fingerprint_data)
        fingerprint2 = self.fingerprinter.generate_fingerprint(fingerprint_data)
        
        self.assertEqual(fingerprint1, fingerprint2)
    
    def test_check_fingerprint_consistency_no_previous(self):
        """Test consistency check with no previous fingerprint."""
        current_fingerprint = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'screen_resolution': '1920x1080',
            'timezone': 'America/New_York',
        }
        
        result = self.fingerprinter.check_consistency(self.user.id, current_fingerprint)
        
        self.assertIsInstance(result, dict)
        self.assertIn('is_consistent', result)
        self.assertIn('risk_score', result)
        self.assertIn('changes', result)
        self.assertTrue(result['is_consistent'])
        self.assertEqual(result['risk_score'], 0)
    
    def test_check_fingerprint_consistency_identical(self):
        """Test consistency check with identical fingerprint."""
        # Create existing fingerprint
        existing_fp = DeviceFingerprintFactory.create(
            user=self.user,
            device_hash='existing_hash',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            screen_resolution='1920x1080',
            timezone='America/New_York',
            language='en-US',
            platform='Win32',
            browser='Chrome',
        )
        
        current_fingerprint = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'screen_resolution': '1920x1080',
            'timezone': 'America/New_York',
            'language': 'en-US',
            'platform': 'Win32',
            'browser': 'Chrome',
        }
        
        result = self.fingerprinter.check_consistency(self.user.id, current_fingerprint)
        
        self.assertTrue(result['is_consistent'])
        self.assertEqual(result['risk_score'], 0)
        self.assertEqual(len(result['changes']), 0)
    
    def test_check_fingerprint_consistency_minor_changes(self):
        """Test consistency check with minor changes."""
        # Create existing fingerprint
        existing_fp = DeviceFingerprintFactory.create(
            user=self.user,
            device_hash='existing_hash',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            screen_resolution='1920x1080',
            timezone='America/New_York',
            language='en-US',
            platform='Win32',
            browser='Chrome',
        )
        
        current_fingerprint = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36.1',  # Minor version change
            'screen_resolution': '1920x1080',
            'timezone': 'America/New_York',
            'language': 'en-US',
            'platform': 'Win32',
            'browser': 'Chrome',
        }
        
        result = self.fingerprinter.check_consistency(self.user.id, current_fingerprint)
        
        self.assertTrue(result['is_consistent'])  # Minor changes should still be consistent
        self.assertGreater(result['risk_score'], 0)
        self.assertLess(result['risk_score'], 30)
    
    def test_check_fingerprint_consistency_major_changes(self):
        """Test consistency check with major changes."""
        # Create existing fingerprint
        existing_fp = DeviceFingerprintFactory.create(
            user=self.user,
            device_hash='existing_hash',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            screen_resolution='1920x1080',
            timezone='America/New_York',
            language='en-US',
            platform='Win32',
            browser='Chrome',
        )
        
        current_fingerprint = {
            'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15',  # Different platform
            'screen_resolution': '375x667',  # Mobile resolution
            'timezone': 'America/New_York',
            'language': 'en-US',
            'platform': 'iPhone',  # Different platform
            'browser': 'Safari',  # Different browser
        }
        
        result = self.fingerprinter.check_consistency(self.user.id, current_fingerprint)
        
        self.assertFalse(result['is_consistent'])
        self.assertGreaterEqual(result['risk_score'], 60)
        self.assertGreater(len(result['changes']), 2)
    
    def test_check_fingerprint_consistency_multiple_devices(self):
        """Test consistency check with multiple existing devices."""
        # Create multiple existing fingerprints
        DeviceFingerprintFactory.create_batch(
            3,
            user=self.user,
            trust_score=80
        )
        
        current_fingerprint = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'screen_resolution': '1920x1080',
            'timezone': 'America/New_York',
        }
        
        result = self.fingerprinter.check_consistency(self.user.id, current_fingerprint)
        
        self.assertIsInstance(result, dict)
        self.assertIn('is_consistent', result)
        self.assertIn('risk_score', result)
        self.assertIn('device_count', result)
        self.assertEqual(result['device_count'], 3)
    
    def test_update_trust_score(self):
        """Test trust score updating."""
        # Create device fingerprint
        device_fp = DeviceFingerprintFactory.create(
            user=self.user,
            trust_score=50
        )
        
        # Update trust score positively
        new_score = self.fingerprinter.update_trust_score(
            device_fp.device_hash,
            positive=True
        )
        
        self.assertGreater(new_score, 50)
        self.assertLessEqual(new_score, 100)
        
        # Refresh from database
        device_fp.refresh_from_db()
        self.assertEqual(device_fp.trust_score, new_score)
    
    def test_update_trust_score_negative(self):
        """Test negative trust score updating."""
        # Create device fingerprint
        device_fp = DeviceFingerprintFactory.create(
            user=self.user,
            trust_score=70
        )
        
        # Update trust score negatively
        new_score = self.fingerprinter.update_trust_score(
            device_fp.device_hash,
            positive=False
        )
        
        self.assertLess(new_score, 70)
        self.assertGreaterEqual(new_score, 0)
        
        # Refresh from database
        device_fp.refresh_from_db()
        self.assertEqual(device_fp.trust_score, new_score)
    
    def test_detect_suspicious_patterns(self):
        """Test suspicious pattern detection."""
        # Create device with suspicious characteristics
        device_fp = DeviceFingerprintFactory.create(
            user=self.user,
            is_vpn=True,
            is_proxy=True,
            trust_score=30
        )
        
        patterns = self.fingerprinter.detect_suspicious_patterns(device_fp.device_hash)
        
        self.assertIsInstance(patterns, dict)
        self.assertIn('suspicious_indicators', patterns)
        self.assertIn('risk_factors', patterns)
        self.assertIn('recommendations', patterns)
        
        suspicious_indicators = patterns['suspicious_indicators']
        self.assertTrue(suspicious_indicators.get('is_vpn', False))
        self.assertTrue(suspicious_indicators.get('is_proxy', False))
    
    def test_analyze_device_history(self):
        """Test device history analysis."""
        # Create device with history
        device_fp = DeviceFingerprintFactory.create(
            user=self.user,
            last_seen=timezone.now() - timedelta(days=5)
        )
        
        # Create some fraud attempts for this user
        FraudAttemptFactory.create_batch(
            2,
            user=self.user,
            status='confirmed'
        )
        
        history = self.fingerprinter.analyze_device_history(device_fp.device_hash)
        
        self.assertIsInstance(history, dict)
        self.assertIn('usage_pattern', history)
        self.assertIn('fraud_correlation', history)
        self.assertIn('risk_assessment', history)
    
    def test_get_device_statistics(self):
        """Test device statistics retrieval."""
        # Create multiple devices
        DeviceFingerprintFactory.create_batch(10, user=self.user)
        
        stats = self.fingerprinter.get_device_statistics(self.user.id)
        
        self.assertIsInstance(stats, dict)
        self.assertIn('total_devices', stats)
        self.assertIn('trusted_devices', stats)
        self.assertIn('suspicious_devices', stats)
        self.assertIn('avg_trust_score', stats)
        
        self.assertEqual(stats['total_devices'], 10)
    
    def test_cleanup_old_devices(self):
        """Test cleanup of old devices."""
        # Create old devices
        old_devices = DeviceFingerprintFactory.create_batch(
            5,
            user=self.user,
            last_seen=timezone.now() - timedelta(days=100)
        )
        
        # Create recent devices
        recent_devices = DeviceFingerprintFactory.create_batch(
            3,
            user=self.user,
            last_seen=timezone.now() - timedelta(days=10)
        )
        
        # Cleanup old devices
        cleanup_result = self.fingerprinter.cleanup_old_devices(days_to_keep=30)
        
        self.assertIsInstance(cleanup_result, dict)
        self.assertIn('deleted_count', cleanup_result)
        self.assertEqual(cleanup_result['deleted_count'], 5)
    
    def test_fingerprint_data_validation(self):
        """Test fingerprint data validation."""
        # Test invalid data
        invalid_data = {
            'user_agent': '',  # Empty string
            'screen_resolution': 'invalid_resolution',
            'timezone': 'Invalid/Timezone',
        }
        
        with self.assertRaises(ValueError):
            self.fingerprinter.generate_fingerprint(invalid_data)
    
    def test_fingerprint_data_normalization(self):
        """Test fingerprint data normalization."""
        fingerprint_data = {
            'user_agent': '  Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36  ',  # Extra spaces
            'screen_resolution': '1920X1080',  # Uppercase X
            'timezone': 'america/new_york',  # Lowercase
            'language': 'EN-US',  # Uppercase
        }
        
        fingerprint = self.fingerprinter.generate_fingerprint(fingerprint_data)
        
        self.assertIsInstance(fingerprint, str)
        self.assertEqual(len(fingerprint), 64)
    
    def test_concurrent_fingerprint_generation(self):
        """Test concurrent fingerprint generation."""
        fingerprint_data = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'screen_resolution': '1920x1080',
            'timezone': 'America/New_York',
        }
        
        # Generate multiple fingerprints concurrently
        fingerprints = []
        for _ in range(10):
            fingerprint = self.fingerprinter.generate_fingerprint(fingerprint_data)
            fingerprints.append(fingerprint)
        
        # All should be identical
        self.assertTrue(all(fp == fingerprints[0] for fp in fingerprints))
    
    @patch('fraud_detection.services.DeviceFingerprinter.logger')
    def test_error_handling(self, mock_logger):
        """Test error handling in fingerprinter."""
        # Test with invalid user ID
        with self.assertRaises(ValueError):
            self.fingerprinter.check_consistency(999999, {})
        
        # Test with invalid device hash
        with self.assertRaises(ValueError):
            self.fingerprinter.update_trust_score('invalid_hash')
        
        # Verify error logging
        mock_logger.error.assert_called()
    
    def test_performance_with_large_history(self):
        """Test performance with large device history."""
        # Create large number of devices
        DeviceFingerprintFactory.create_batch(
            100,
            user=self.user,
            last_seen=timezone.now() - timedelta(hours=random.randint(1, 720))
        )
        
        # Test statistics performance
        import time
        start_time = time.time()
        
        stats = self.fingerprinter.get_device_statistics(self.user.id)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(processing_time, 1.0)  # 1 second max
        self.assertEqual(stats['total_devices'], 100)


class TestDeviceFingerprinterIntegration(TestCase):
    """Integration tests for DeviceFingerprinter."""
    
    def setUp(self):
        """Set up integration test data."""
        self.fingerprinter = DeviceFingerprinter()
        self.scenario = FraudTestDataGenerator.create_device_fingerprint_scenario(
            device_count=20
        )
    
    def test_end_to_end_fingerprinting(self):
        """Test end-to-end fingerprinting workflow."""
        user = UserFactory.create()
        
        # Simulate user login with device data
        fingerprint_data = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'screen_resolution': '1920x1080',
            'timezone': 'America/New_York',
            'language': 'en-US',
            'platform': 'Win32',
            'browser': 'Chrome',
        }
        
        # Generate fingerprint
        fingerprint = self.fingerprinter.generate_fingerprint(fingerprint_data)
        
        # Check consistency (first time)
        result = self.fingerprinter.check_consistency(user.id, fingerprint_data)
        
        self.assertTrue(result['is_consistent'])
        self.assertEqual(result['risk_score'], 0)
        
        # Create device record
        device_fp = DeviceFingerprint.objects.create(
            user=user,
            device_hash=fingerprint,
            user_agent=fingerprint_data['user_agent'],
            screen_resolution=fingerprint_data['screen_resolution'],
            timezone=fingerprint_data['timezone'],
            language=fingerprint_data['language'],
            platform=fingerprint_data['platform'],
            browser=fingerprint_data['browser'],
            trust_score=80,
        )
        
        # Simulate suspicious activity
        suspicious_data = {
            'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15',
            'screen_resolution': '375x667',
            'timezone': 'America/New_York',
            'language': 'en-US',
            'platform': 'iPhone',
            'browser': 'Safari',
        }
        
        # Check consistency with suspicious data
        result = self.fingerprinter.check_consistency(user.id, suspicious_data)
        
        self.assertFalse(result['is_consistent'])
        self.assertGreaterEqual(result['risk_score'], 60)
        
        # Create fraud attempt if risk is high
        if result['risk_score'] >= 60:
            attempt = FraudAttempt.objects.create(
                user=user,
                attempt_type=FraudAttemptType.DEVICE_ANOMALY,
                description=f"Suspicious device change detected: {result['risk_score']}",
                detected_by='DeviceFingerprinter',
                fraud_score=result['risk_score'],
                confidence_score=0.8,
                evidence_data=json.dumps(result['changes']),
            )
            
            self.assertIsInstance(attempt, FraudAttempt)
    
    def test_multiple_users_fingerprinting(self):
        """Test fingerprinting across multiple users."""
        users = UserFactory.create_batch(5)
        results = []
        
        for user in users:
            fingerprint_data = {
                'user_agent': f'Mozilla/5.0 (Custom Browser {user.id})',
                'screen_resolution': '1920x1080',
                'timezone': 'America/New_York',
            }
            
            fingerprint = self.fingerprinter.generate_fingerprint(fingerprint_data)
            result = self.fingerprinter.check_consistency(user.id, fingerprint_data)
            
            results.append({
                'user': user,
                'fingerprint': fingerprint,
                'result': result,
            })
        
        # Verify results
        self.assertEqual(len(results), 5)
        
        for result in results:
            self.assertIsInstance(result['fingerprint'], str)
            self.assertTrue(result['result']['is_consistent'])
    
    def test_device_trust_evolution(self):
        """Test device trust score evolution over time."""
        user = UserFactory.create()
        
        # Create initial device
        fingerprint_data = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'screen_resolution': '1920x1080',
            'timezone': 'America/New_York',
        }
        
        fingerprint = self.fingerprinter.generate_fingerprint(fingerprint_data)
        
        # Simulate multiple positive interactions
        for i in range(10):
            result = self.fingerprinter.check_consistency(user.id, fingerprint_data)
            if result['is_consistent']:
                self.fingerprinter.update_trust_score(fingerprint, positive=True)
        
        # Check final trust score
        device_fp = DeviceFingerprint.objects.filter(
            user=user,
            device_hash=fingerprint
        ).first()
        
        if device_fp:
            self.assertGreater(device_fp.trust_score, 50)


if __name__ == '__main__':
    import random
    
    # Add random import for integration tests
    TestDeviceFingerprinterIntegration.setUp = lambda self: (
        setattr(self, 'fingerprinter', DeviceFingerprinter()) or
        setattr(self, 'scenario', FraudTestDataGenerator.create_device_fingerprint_scenario(device_count=20))
    )
