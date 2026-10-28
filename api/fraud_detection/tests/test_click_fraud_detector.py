# =============================================================================
# fraud_detection/tests/test_click_fraud_detector.py
# =============================================================================
"""
Click Fraud Detector Tests.

Comprehensive tests for the click fraud detection service including
pattern recognition, threshold analysis, and integration testing.
"""

import json
import pytest
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from api.fraud_detection.detectors.ClickFraudDetector import ClickFraudDetector
from api.fraud_detection.models import FraudAttempt, OfferCompletion
from api.fraud_detection.choices import FraudAttemptType
from .factories import (
    UserFactory, OfferCompletionFactory, FraudAttemptFactory,
    FraudTestDataGenerator
)


class TestClickFraudDetector(TestCase):
    """Test cases for ClickFraudDetector."""
    
    def setUp(self):
        """Set up test data."""
        self.detector = ClickFraudDetector()
        self.user = UserFactory.create()
        
    def test_detect_normal_click_pattern(self):
        """Test detection of normal click patterns."""
        click_data = {
            'user_id': self.user.id,
            'offer_id': 'offer_123',
            'click_data': {
                'revenue': 5.50,
                'completion_time': timezone.now().isoformat(),
                'click_position': {'x': 100, 'y': 200},
                'viewport': {'width': 1920, 'height': 1080},
            }
        }
        
        result = self.detector.detect(click_data)
        
        self.assertIsInstance(result, dict)
        self.assertIn('fraud_score', result)
        self.assertIn('confidence', result)
        self.assertIn('evidence', result)
        self.assertLess(result['fraud_score'], 30)  # Normal pattern should have low score
    
    def test_detect_rapid_clicks(self):
        """Test detection of rapid successive clicks."""
        # Create multiple completions in short time
        base_time = timezone.now()
        
        for i in range(10):
            OfferCompletionFactory.create(
                user=self.user,
                offer_id=f'offer_{i}',
                completed_at=base_time + timedelta(seconds=i*5),  # 5 seconds apart
            )
        
        click_data = {
            'user_id': self.user.id,
            'offer_id': 'offer_new',
            'click_data': {
                'revenue': 10.0,
                'completion_time': base_time.isoformat(),
            }
        }
        
        result = self.detector.detect(click_data)
        
        self.assertGreaterEqual(result['fraud_score'], 60)
        self.assertIn('rapid_clicks', result['evidence'])
    
    def test_detect_unrealistic_click_timing(self):
        """Test detection of unrealistic click timing."""
        click_data = {
            'user_id': self.user.id,
            'offer_id': 'offer_123',
            'click_data': {
                'revenue': 50.0,
                'completion_time': timezone.now().isoformat(),
                'time_on_page': 0.5,  # Less than 1 second
            }
        }
        
        result = self.detector.detect(click_data)
        
        self.assertGreaterEqual(result['fraud_score'], 40)
        self.assertIn('unrealistic_timing', result['evidence'])
    
    def test_detect_high_value_targeting(self):
        """Test detection of high-value offer targeting."""
        click_data = {
            'user_id': self.user.id,
            'offer_id': 'offer_123',
            'click_data': {
                'revenue': 500.0,  # Very high value
                'completion_time': timezone.now().isoformat(),
            }
        }
        
        result = self.detector.detect(click_data)
        
        self.assertGreaterEqual(result['fraud_score'], 50)
        self.assertIn('high_value_targeting', result['evidence'])
    
    def test_detect_ip_consistency_issues(self):
        """Test detection of IP consistency issues."""
        # Create completions from different IPs
        ips = ['192.168.1.1', '192.168.1.2', '10.0.0.1']
        
        for i, ip in enumerate(ips):
            OfferCompletionFactory.create(
                user=self.user,
                offer_id=f'offer_{i}',
                evidence_data=json.dumps({'ip_address': ip})
            )
        
        click_data = {
            'user_id': self.user.id,
            'offer_id': 'offer_new',
            'click_data': {
                'revenue': 25.0,
                'completion_time': timezone.now().isoformat(),
                'ip_address': '192.168.1.4',  # New IP
            }
        }
        
        result = self.detector.detect(click_data)
        
        self.assertGreaterEqual(result['fraud_score'], 45)
        self.assertIn('ip_inconsistency', result['evidence'])
    
    def test_detect_device_fingerprint_anomalies(self):
        """Test detection of device fingerprint anomalies."""
        # Create completions with different device fingerprints
        devices = ['device_123', 'device_456', 'device_789']
        
        for i, device in enumerate(devices):
            OfferCompletionFactory.create(
                user=self.user,
                offer_id=f'offer_{i}',
                evidence_data=json.dumps({'device_hash': device})
            )
        
        click_data = {
            'user_id': self.user.id,
            'offer_id': 'offer_new',
            'click_data': {
                'revenue': 15.0,
                'completion_time': timezone.now().isoformat(),
                'device_hash': 'device_999',  # New device
            }
        }
        
        result = self.detector.detect(click_data)
        
        self.assertGreaterEqual(result['fraud_score'], 40)
        self.assertIn('device_anomaly', result['evidence'])
    
    def test_detect_geographic_anomalies(self):
        """Test detection of geographic anomalies."""
        # Create completions from different countries
        countries = ['US', 'GB', 'CA']
        
        for i, country in enumerate(countries):
            OfferCompletionFactory.create(
                user=self.user,
                offer_id=f'offer_{i}',
                evidence_data=json.dumps({'country': country})
            )
        
        click_data = {
            'user_id': self.user.id,
            'offer_id': 'offer_new',
            'click_data': {
                'revenue': 20.0,
                'completion_time': timezone.now().isoformat(),
                'country': 'JP',  # New country
            }
        }
        
        result = self.detector.detect(click_data)
        
        self.assertGreaterEqual(result['fraud_score'], 35)
        self.assertIn('geographic_anomaly', result['evidence'])
    
    def test_calculate_click_velocity(self):
        """Test click velocity calculation."""
        base_time = timezone.now()
        
        # Create completions with varying time intervals
        intervals = [5, 10, 15, 20, 30]  # seconds
        
        for i, interval in enumerate(intervals):
            OfferCompletionFactory.create(
                user=self.user,
                offer_id=f'offer_{i}',
                completed_at=base_time + timedelta(seconds=sum(intervals[:i+1]))
            )
        
        velocity = self.detector._calculate_click_velocity(self.user.id)
        
        self.assertIsInstance(velocity, float)
        self.assertGreater(velocity, 0)
    
    def test_analyze_click_patterns(self):
        """Test click pattern analysis."""
        # Create varied click patterns
        patterns = [
            {'x': 100, 'y': 200},
            {'x': 150, 'y': 250},
            {'x': 200, 'y': 300},
        ]
        
        for i, pattern in enumerate(patterns):
            OfferCompletionFactory.create(
                user=self.user,
                offer_id=f'offer_{i}',
                evidence_data=json.dumps({'click_position': pattern})
            )
        
        analysis = self.detector._analyze_click_patterns(self.user.id)
        
        self.assertIsInstance(analysis, dict)
        self.assertIn('pattern_score', analysis)
        self.assertIn('anomalies', analysis)
    
    def test_check_reputation_indicators(self):
        """Test reputation indicator checking."""
        # Create user with some fraud attempts
        FraudAttemptFactory.create_batch(
            3,
            user=self.user,
            status='confirmed'
        )
        
        indicators = self.detector._check_reputation_indicators(self.user.id)
        
        self.assertIsInstance(indicators, dict)
        self.assertIn('user_reputation', indicators)
        self.assertIn('ip_reputation', indicators)
        self.assertIn('device_reputation', indicators)
    
    def test_detect_with_invalid_data(self):
        """Test detection with invalid data."""
        invalid_data = {
            'user_id': 999999,  # Non-existent user
            'offer_id': '',
            'click_data': {}
        }
        
        result = self.detector.detect(invalid_data)
        
        self.assertIsInstance(result, dict)
        self.assertIn('error', result)
        self.assertIn('fraud_score', result)
        self.assertEqual(result['fraud_score'], 0)
    
    def test_detect_with_missing_fields(self):
        """Test detection with missing required fields."""
        incomplete_data = {
            'user_id': self.user.id,
            # Missing offer_id and click_data
        }
        
        result = self.detector.detect(incomplete_data)
        
        self.assertIsInstance(result, dict)
        self.assertIn('error', result)
    
    def test_batch_detection(self):
        """Test batch fraud detection."""
        click_data_list = [
            {
                'user_id': self.user.id,
                'offer_id': f'offer_{i}',
                'click_data': {
                    'revenue': 10.0,
                    'completion_time': timezone.now().isoformat(),
                }
            }
            for i in range(5)
        ]
        
        results = self.detector.batch_detect(click_data_list)
        
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 5)
        
        for result in results:
            self.assertIsInstance(result, dict)
            self.assertIn('fraud_score', result)
    
    def test_detector_configuration(self):
        """Test detector configuration options."""
        # Test custom thresholds
        custom_detector = ClickFraudDetector(
            rapid_click_threshold=5,
            high_value_threshold=100,
            timing_threshold=0.3
        )
        
        click_data = {
            'user_id': self.user.id,
            'offer_id': 'offer_123',
            'click_data': {
                'revenue': 150.0,  # Above custom high value threshold
                'completion_time': timezone.now().isoformat(),
                'time_on_page': 0.2,  # Below custom timing threshold
            }
        }
        
        result = custom_detector.detect(click_data)
        
        self.assertGreaterEqual(result['fraud_score'], 70)
    
    @patch('fraud_detection.detectors.ClickFraudDetector.logger')
    def test_error_handling(self, mock_logger):
        """Test error handling in detection process."""
        # Simulate database error
        with patch('fraud_detection.models.OfferCompletion.objects.filter') as mock_filter:
            mock_filter.side_effect = Exception("Database error")
            
            click_data = {
                'user_id': self.user.id,
                'offer_id': 'offer_123',
                'click_data': {
                    'revenue': 10.0,
                    'completion_time': timezone.now().isoformat(),
                }
            }
            
            result = self.detector.detect(click_data)
            
            # Should return safe default result
            self.assertIsInstance(result, dict)
            self.assertIn('fraud_score', result)
            self.assertEqual(result['fraud_score'], 0)
            
            # Should log the error
            mock_logger.error.assert_called()
    
    def test_evidence_collection(self):
        """Test evidence collection and formatting."""
        click_data = {
            'user_id': self.user.id,
            'offer_id': 'offer_123',
            'click_data': {
                'revenue': 500.0,
                'completion_time': timezone.now().isoformat(),
                'ip_address': '192.168.1.1',
                'user_agent': 'Mozilla/5.0...',
                'time_on_page': 0.5,
            }
        }
        
        result = self.detector.detect(click_data)
        
        self.assertIn('evidence', result)
        evidence = result['evidence']
        
        self.assertIsInstance(evidence, dict)
        self.assertIn('high_value_targeting', evidence)
        self.assertIn('unrealistic_timing', evidence)
        
        # Check evidence details
        for evidence_type, details in evidence.items():
            self.assertIsInstance(details, dict)
            self.assertIn('score', details)
            self.assertIn('description', details)
    
    def test_confidence_calculation(self):
        """Test confidence score calculation."""
        # Test with strong evidence
        strong_evidence = {
            'rapid_clicks': {'score': 50, 'description': 'Multiple rapid clicks'},
            'high_value_targeting': {'score': 30, 'description': 'High value targeting'},
        }
        
        confidence = self.detector._calculate_confidence(strong_evidence)
        
        self.assertIsInstance(confidence, float)
        self.assertGreaterEqual(confidence, 0.7)
        self.assertLessEqual(confidence, 1.0)
        
        # Test with weak evidence
        weak_evidence = {
            'minor_anomaly': {'score': 10, 'description': 'Minor timing issue'},
        }
        
        confidence = self.detector._calculate_confidence(weak_evidence)
        
        self.assertLess(confidence, 0.5)


class TestClickFraudDetectorIntegration(TestCase):
    """Integration tests for ClickFraudDetector."""
    
    def setUp(self):
        """Set up integration test data."""
        self.detector = ClickFraudDetector()
        self.scenario = FraudTestDataGenerator.create_fraud_scenario(
            user_count=5,
            days=7
        )
    
    def test_end_to_end_detection(self):
        """Test end-to-end fraud detection workflow."""
        user = self.scenario['users'][0]
        
        # Create suspicious click pattern
        click_data = {
            'user_id': user.id,
            'offer_id': 'offer_suspicious',
            'click_data': {
                'revenue': 200.0,
                'completion_time': timezone.now().isoformat(),
                'ip_address': '192.168.1.100',
                'time_on_page': 0.3,
            }
        }
        
        # Detect fraud
        result = self.detector.detect(click_data)
        
        # Verify detection result
        self.assertGreaterEqual(result['fraud_score'], 60)
        
        # Create fraud attempt if score is high enough
        if result['fraud_score'] >= 60:
            attempt = FraudAttempt.objects.create(
                user=user,
                attempt_type=FraudAttemptType.CLICK_FRAUD,
                description=f"Suspicious click detected: {result['fraud_score']}",
                detected_by='ClickFraudDetector',
                fraud_score=result['fraud_score'],
                confidence_score=result['confidence'],
                evidence_data=json.dumps(result['evidence']),
                amount_involved=200.0,
            )
            
            self.assertIsInstance(attempt, FraudAttempt)
            self.assertEqual(attempt.fraud_score, result['fraud_score'])
    
    def test_multiple_users_detection(self):
        """Test detection across multiple users."""
        results = []
        
        for user in self.scenario['users'][:3]:
            click_data = {
                'user_id': user.id,
                'offer_id': f'offer_{user.id}',
                'click_data': {
                    'revenue': random.uniform(5, 100),
                    'completion_time': timezone.now().isoformat(),
                }
            }
            
            result = self.detector.detect(click_data)
            results.append(result)
        
        # Verify results
        self.assertEqual(len(results), 3)
        
        for result in results:
            self.assertIsInstance(result, dict)
            self.assertIn('fraud_score', result)
            self.assertIn('confidence', result)
    
    def test_performance_with_large_dataset(self):
        """Test performance with large dataset."""
        # Create large number of completions
        user = self.scenario['users'][0]
        
        OfferCompletionFactory.create_batch(
            100,
            user=user,
            completed_at=timezone.now() - timedelta(hours=random.randint(1, 24))
        )
        
        # Test detection performance
        import time
        start_time = time.time()
        
        click_data = {
            'user_id': user.id,
            'offer_id': 'offer_performance_test',
            'click_data': {
                'revenue': 25.0,
                'completion_time': timezone.now().isoformat(),
            }
        }
        
        result = self.detector.detect(click_data)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(processing_time, 2.0)  # 2 seconds max
        self.assertIsInstance(result, dict)


if __name__ == '__main__':
    import random
    
    # Add random import for integration tests
    TestClickFraudDetectorIntegration.setUp = lambda self: (
        setattr(self, 'detector', ClickFraudDetector()) or
        setattr(self, 'scenario', FraudTestDataGenerator.create_fraud_scenario(user_count=5, days=7))
    )
