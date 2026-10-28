# =============================================================================
# fraud_detection/tests/test_fraud_score_calculator.py
# =============================================================================
"""
Fraud Score Calculator Tests.

Comprehensive tests for fraud score calculation including
weighted scoring, risk assessment, and score aggregation.
"""

import json
import pytest
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from api.fraud_detection.calculators.FraudScoreCalculator import FraudScoreCalculator
from api.fraud_detection.models import FraudAttempt, UserRiskProfile, DeviceFingerprint, IPReputation
from api.fraud_detection.choices import FraudAttemptStatus
from .factories import (
    UserFactory, FraudAttemptFactory, UserRiskProfileFactory,
    DeviceFingerprintFactory, IPReputationFactory
)


class TestFraudScoreCalculator(TestCase):
    """Test cases for FraudScoreCalculator."""
    
    def setUp(self):
        """Set up test data."""
        self.calculator = FraudScoreCalculator()
        self.user = UserFactory.create()
        
    def test_calculate_fraud_score_basic(self):
        """Test basic fraud score calculation."""
        score_data = {
            'account_risk': 30,
            'behavior_risk': 25,
            'payment_risk': 20,
            'device_risk': 15,
            'network_risk': 10,
        }
        
        score = self.calculator.calculate_fraud_score(score_data)
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        
        # Check calculation (weighted average)
        expected_score = (30 * 0.3) + (25 * 0.25) + (20 * 0.2) + (15 * 0.15) + (10 * 0.1)
        self.assertAlmostEqual(score, expected_score, places=2)
    
    def test_calculate_fraud_score_empty_data(self):
        """Test fraud score calculation with empty data."""
        score = self.calculator.calculate_fraud_score({})
        
        self.assertEqual(score, 0.0)
    
    def test_calculate_fraud_score_partial_data(self):
        """Test fraud score calculation with partial data."""
        score_data = {
            'account_risk': 50,
            'behavior_risk': 30,
            # Missing other categories
        }
        
        score = self.calculator.calculate_fraud_score(score_data)
        
        self.assertIsInstance(score, float)
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)
    
    def test_calculate_fraud_score_invalid_data(self):
        """Test fraud score calculation with invalid data."""
        # Test with negative values
        score_data = {
            'account_risk': -10,
            'behavior_risk': 150,  # Over 100
            'payment_risk': 30,
        }
        
        score = self.calculator.calculate_fraud_score(score_data)
        
        # Should handle invalid values gracefully
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
    
    def test_calculate_user_risk_score(self):
        """Test user risk score calculation."""
        # Create user with various risk factors
        UserRiskProfileFactory.create(
            user=self.user,
            overall_risk_score=60,
            is_flagged=True,
            total_fraud_attempts=5,
            confirmed_fraud_attempts=3
        )
        
        # Create fraud attempts
        FraudAttemptFactory.create_batch(
            3,
            user=self.user,
            fraud_score=70,
            status='confirmed'
        )
        
        score = self.calculator.calculate_user_risk_score(self.user.id)
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        
        # Should be higher than base risk score due to confirmed attempts
        self.assertGreater(score, 60)
    
    def test_calculate_transaction_risk_score(self):
        """Test transaction risk score calculation."""
        transaction_data = {
            'amount': 1000.00,
            'currency': 'USD',
            'merchant_category': 'electronics',
            'time_of_day': 2,  # 2 AM
            'user_history': {
                'avg_transaction_amount': 50.00,
                'transaction_frequency': 5,
                'last_transaction_hours': 24,
            },
            'location_data': {
                'ip_country': 'US',
                'billing_country': 'GB',  # Mismatch
            },
        }
        
        score = self.calculator.calculate_transaction_risk_score(transaction_data)
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        
        # Should be high due to amount, time, and location mismatch
        self.assertGreater(score, 50)
    
    def test_calculate_device_risk_score(self):
        """Test device risk score calculation."""
        # Create device with risk factors
        device = DeviceFingerprintFactory.create(
            user=self.user,
            trust_score=30,
            is_vpn=True,
            is_proxy=False
        )
        
        score = self.calculator.calculate_device_risk_score(device.device_hash)
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        
        # Should be high due to low trust score and VPN
        self.assertGreater(score, 60)
    
    def test_calculate_ip_risk_score(self):
        """Test IP risk score calculation."""
        # Create IP with risk factors
        ip_rep = IPReputationFactory.create(
            ip_address='192.168.1.100',
            fraud_score=75,
            spam_score=60,
            malware_score=40,
            is_blacklisted=False
        )
        
        score = self.calculator.calculate_ip_risk_score('192.168.1.100')
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        
        # Should be high due to fraud and spam scores
        self.assertGreater(score, 65)
    
    def test_calculate_behavioral_risk_score(self):
        """Test behavioral risk score calculation."""
        behavior_data = {
            'login_frequency': 20,  # High frequency
            'login_times': [2, 3, 4, 5, 6],  # Unusual times (2-6 AM)
            'session_duration': 30,  # Short sessions
            'page_views': 5,  # Low engagement
            'click_patterns': {
                'rapid_clicks': True,
                'bot_like_behavior': False,
            },
            'location_changes': 5,  # Multiple locations
        }
        
        score = self.calculator.calculate_behavioral_risk_score(behavior_data)
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        
        # Should be high due to unusual timing and multiple locations
        self.assertGreater(score, 50)
    
    def test_aggregate_multiple_scores(self):
        """Test aggregation of multiple risk scores."""
        scores = [
            {'type': 'account', 'score': 70, 'weight': 0.3},
            {'type': 'transaction', 'score': 85, 'weight': 0.4},
            {'type': 'device', 'score': 45, 'weight': 0.2},
            {'type': 'behavior', 'score': 60, 'weight': 0.1},
        ]
        
        aggregated = self.calculator.aggregate_multiple_scores(scores)
        
        self.assertIsInstance(aggregated, dict)
        self.assertIn('overall_score', aggregated)
        self.assertIn('component_scores', aggregated)
        self.assertIn('risk_level', aggregated)
        
        overall_score = aggregated['overall_score']
        self.assertIsInstance(overall_score, float)
        self.assertGreaterEqual(overall_score, 0)
        self.assertLessEqual(overall_score, 100)
        
        # Check calculation
        expected = (70 * 0.3) + (85 * 0.4) + (45 * 0.2) + (60 * 0.1)
        self.assertAlmostEqual(overall_score, expected, places=2)
    
    def test_calculate_risk_trend(self):
        """Test risk trend calculation."""
        historical_scores = [
            {'date': timezone.now() - timedelta(days=4), 'score': 30},
            {'date': timezone.now() - timedelta(days=3), 'score': 35},
            {'date': timezone.now() - timedelta(days=2), 'score': 45},
            {'date': timezone.now() - timedelta(days=1), 'score': 60},
            {'date': timezone.now(), 'score': 75},
        ]
        
        trend = self.calculator.calculate_risk_trend(historical_scores)
        
        self.assertIsInstance(trend, dict)
        self.assertIn('direction', trend)
        self.assertIn('slope', trend)
        self.assertIn('confidence', trend)
        self.assertIn('change_percentage', trend)
        
        # Should detect increasing trend
        self.assertEqual(trend['direction'], 'increasing')
        self.assertGreater(trend['slope'], 0)
        self.assertGreater(trend['change_percentage'], 0)
    
    def test_calculate_confidence_score(self):
        """Test confidence score calculation."""
        evidence = {
            'strong_indicators': [
                {'type': 'confirmed_fraud', 'confidence': 0.9},
                {'type': 'high_risk_device', 'confidence': 0.8},
            ],
            'weak_indicators': [
                {'type': 'unusual_timing', 'confidence': 0.4},
                {'type': 'location_anomaly', 'confidence': 0.3},
            ],
        }
        
        confidence = self.calculator.calculate_confidence_score(evidence)
        
        self.assertIsInstance(confidence, float)
        self.assertGreaterEqual(confidence, 0)
        self.assertLessEqual(confidence, 1)
        
        # Should be higher due to strong indicators
        self.assertGreater(confidence, 0.5)
    
    def test_normalize_score(self):
        """Test score normalization."""
        # Test normalization within range
        normalized = self.calculator.normalize_score(85, 0, 100)
        self.assertEqual(normalized, 85)
        
        # Test normalization of out-of-range values
        normalized_low = self.calculator.normalize_score(-10, 0, 100)
        self.assertEqual(normalized_low, 0)
        
        normalized_high = self.calculator.normalize_score(150, 0, 100)
        self.assertEqual(normalized_high, 100)
        
        # Test normalization with different ranges
        normalized_range = self.calculator.normalize_score(75, 50, 100)
        expected = ((75 - 50) / (100 - 50)) * 100
        self.assertAlmostEqual(normalized_range, expected, places=2)
    
    def test_calculate_weighted_score(self):
        """Test weighted score calculation."""
        scores = [70, 80, 60, 90]
        weights = [0.2, 0.3, 0.1, 0.4]
        
        weighted_score = self.calculator.calculate_weighted_score(scores, weights)
        
        self.assertIsInstance(weighted_score, float)
        self.assertGreaterEqual(weighted_score, 0)
        self.assertLessEqual(weighted_score, 100)
        
        # Check calculation
        expected = (70 * 0.2) + (80 * 0.3) + (60 * 0.1) + (90 * 0.4)
        self.assertAlmostEqual(weighted_score, expected, places=2)
    
    def test_calculate_risk_level(self):
        """Test risk level determination."""
        # Test different risk levels
        self.assertEqual(self.calculator.calculate_risk_level(10), 'low')
        self.assertEqual(self.calculator.calculate_risk_level(35), 'medium')
        self.assertEqual(self.calculator.calculate_risk_level(65), 'high')
        self.assertEqual(self.calculator.calculate_risk_level(85), 'critical')
        
        # Test boundary values
        self.assertEqual(self.calculator.calculate_risk_level(40), 'medium')
        self.assertEqual(self.calculator.calculate_risk_level(70), 'high')
    
    def test_batch_score_calculation(self):
        """Test batch score calculation."""
        users = UserFactory.create_batch(5)
        
        # Create user risk profiles
        for i, user in enumerate(users):
            UserRiskProfileFactory.create(
                user=user,
                overall_risk_score=50 + (i * 10),
                is_flagged=i > 2
            )
        
        # Batch calculate
        results = self.calculator.batch_calculate_user_risk_scores([u.id for u in users])
        
        self.assertIsInstance(results, dict)
        self.assertEqual(len(results), 5)
        
        for user_id, score in results.items():
            self.assertIsInstance(score, float)
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)
    
    def test_score_validation(self):
        """Test score validation."""
        # Test valid scores
        self.assertTrue(self.calculator.validate_score(50))
        self.assertTrue(self.calculator.validate_score(0))
        self.assertTrue(self.calculator.validate_score(100))
        
        # Test invalid scores
        self.assertFalse(self.calculator.validate_score(-1))
        self.assertFalse(self.calculator.validate_score(101))
        self.assertFalse(self.calculator.validate_score('invalid'))
        self.assertFalse(self.calculator.validate_score(None))
    
    def test_calculate_composite_risk_score(self):
        """Test composite risk score calculation."""
        composite_data = {
            'user_profile': {
                'risk_score': 60,
                'is_flagged': True,
                'monitoring_level': 'enhanced',
            },
            'recent_activity': {
                'fraud_attempts': 3,
                'confirmed_fraud': 2,
                'time_since_last': 24,
            },
            'contextual_factors': {
                'ip_risk': 70,
                'device_risk': 40,
                'location_risk': 30,
            },
            'historical_patterns': {
                'risk_trend': 'increasing',
                'anomaly_count': 5,
                'consistency_score': 0.6,
            }
        }
        
        composite_score = self.calculator.calculate_composite_risk_score(composite_data)
        
        self.assertIsInstance(composite_score, dict)
        self.assertIn('overall_score', composite_score)
        self.assertIn('component_breakdown', composite_score)
        self.assertIn('risk_factors', composite_score)
        self.assertIn('confidence', composite_score)
        
        overall_score = composite_score['overall_score']
        self.assertIsInstance(overall_score, float)
        self.assertGreaterEqual(overall_score, 0)
        self.assertLessEqual(overall_score, 100)
    
    def test_calculate_adaptive_score(self):
        """Test adaptive score calculation based on context."""
        base_score = 60
        context = {
            'time_sensitivity': 'high',  # During fraud spike
            'user_importance': 'high',  # VIP user
            'transaction_value': 1000.00,  # High value
            'recent_alerts': 3,  # Recent alerts
        }
        
        adaptive_score = self.calculator.calculate_adaptive_score(base_score, context)
        
        self.assertIsInstance(adaptive_score, float)
        self.assertGreaterEqual(adaptive_score, 0)
        self.assertLessEqual(adaptive_score, 100)
        
        # Should be higher than base score due to context
        self.assertGreater(adaptive_score, base_score)
    
    def test_score_calibration(self):
        """Test score calibration against historical data."""
        # Create calibration data
        calibration_data = [
            {'predicted_score': 70, 'actual_outcome': 'fraud'},
            {'predicted_score': 30, 'actual_outcome': 'legitimate'},
            {'predicted_score': 85, 'actual_outcome': 'fraud'},
            {'predicted_score': 25, 'actual_outcome': 'legitimate'},
            {'predicted_score': 60, 'actual_outcome': 'fraud'},
        ]
        
        calibrated_score = self.calculator.calibrate_score(65, calibration_data)
        
        self.assertIsInstance(calibrated_score, float)
        self.assertGreaterEqual(calibrated_score, 0)
        self.assertLessEqual(calibrated_score, 100)
    
    @patch('fraud_detection.calculators.FraudScoreCalculator.logger')
    def test_error_handling(self, mock_logger):
        """Test error handling in score calculation."""
        # Test with invalid user ID
        with self.assertRaises(ValueError):
            self.calculator.calculate_user_risk_score(999999)
        
        # Test with invalid device hash
        with self.assertRaises(ValueError):
            self.calculator.calculate_device_risk_score('invalid_hash')
        
        # Verify error logging
        mock_logger.error.assert_called()
    
    def test_performance_with_large_dataset(self):
        """Test performance with large dataset."""
        # Create large number of users
        users = UserFactory.create_batch(100)
        
        for user in users:
            UserRiskProfileFactory.create(
                user=user,
                overall_risk_score=random.randint(20, 80)
            )
        
        # Test batch calculation performance
        import time
        start_time = time.time()
        
        results = self.calculator.batch_calculate_user_risk_scores([u.id for u in users])
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(processing_time, 2.0)  # 2 seconds max
        self.assertEqual(len(results), 100)
    
    def test_score_explanation(self):
        """Test score explanation generation."""
        score_data = {
            'account_risk': 70,
            'behavior_risk': 30,
            'payment_risk': 85,
            'device_risk': 45,
            'network_risk': 20,
        }
        
        explanation = self.calculator.generate_score_explanation(score_data)
        
        self.assertIsInstance(explanation, dict)
        self.assertIn('overall_score', explanation)
        self.assertIn('risk_level', explanation)
        self.assertIn('contributing_factors', explanation)
        self.assertIn('recommendations', explanation)
        
        # Check contributing factors
        factors = explanation['contributing_factors']
        self.assertIsInstance(factors, list)
        self.assertGreater(len(factors), 0)
        
        for factor in factors:
            self.assertIn('category', factor)
            self.assertIn('score', factor)
            self.assertIn('impact', factor)
            self.assertIn('description', factor)


class TestFraudScoreCalculatorIntegration(TestCase):
    """Integration tests for FraudScoreCalculator."""
    
    def setUp(self):
        """Set up integration test data."""
        self.calculator = FraudScoreCalculator()
        
    def test_end_to_end_score_calculation(self):
        """Test end-to-end score calculation workflow."""
        user = UserFactory.create()
        
        # Create comprehensive user scenario
        UserRiskProfileFactory.create(
            user=user,
            overall_risk_score=60,
            is_flagged=True,
            total_fraud_attempts=5,
            confirmed_fraud_attempts=3
        )
        
        # Create device with risk factors
        device = DeviceFingerprintFactory.create(
            user=user,
            trust_score=35,
            is_vpn=True
        )
        
        # Create IP with risk factors
        ip_rep = IPReputationFactory.create(
            ip_address='192.168.1.100',
            fraud_score=70,
            spam_score=50
        )
        
        # Create fraud attempts
        FraudAttemptFactory.create_batch(
            3,
            user=user,
            fraud_score=75,
            status='confirmed',
            evidence_data=json.dumps({
                'ip_address': ip_rep.ip_address,
                'device_hash': device.device_hash
            })
        )
        
        # Calculate comprehensive score
        user_score = self.calculator.calculate_user_risk_score(user.id)
        device_score = self.calculator.calculate_device_risk_score(device.device_hash)
        ip_score = self.calculator.calculate_ip_risk_score(ip_rep.ip_address)
        
        # Aggregate scores
        aggregated = self.calculator.aggregate_multiple_scores([
            {'type': 'user', 'score': user_score, 'weight': 0.4},
            {'type': 'device', 'score': device_score, 'weight': 0.3},
            {'type': 'ip', 'score': ip_score, 'weight': 0.3},
        ])
        
        # Verify results
        self.assertIsInstance(user_score, float)
        self.assertIsInstance(device_score, float)
        self.assertIsInstance(ip_score, float)
        self.assertIsInstance(aggregated, dict)
        
        self.assertGreater(user_score, 50)
        self.assertGreater(device_score, 50)
        self.assertGreater(ip_score, 50)
        
        overall_score = aggregated['overall_score']
        self.assertGreater(overall_score, 50)
        
        # Generate explanation
        explanation = self.calculator.generate_score_explanation({
            'user_risk': user_score,
            'device_risk': device_score,
            'ip_risk': ip_score,
        })
        
        self.assertIsInstance(explanation, dict)
        self.assertIn('overall_score', explanation)
        self.assertIn('contributing_factors', explanation)
    
    def test_score_trend_analysis(self):
        """Test score trend analysis over time."""
        user = UserFactory.create()
        
        # Create historical data
        base_time = timezone.now() - timedelta(days=30)
        
        historical_scores = []
        for day in range(30):
            # Gradually increasing risk
            score = 30 + (day * 2)
            
            # Create risk profile for that day
            UserRiskProfileFactory.create(
                user=user,
                overall_risk_score=score,
                last_risk_assessment=base_time + timedelta(days=day)
            )
            
            historical_scores.append({
                'date': base_time + timedelta(days=day),
                'score': score
            })
        
        # Calculate trend
        trend = self.calculator.calculate_risk_trend(historical_scores)
        
        self.assertIsInstance(trend, dict)
        self.assertEqual(trend['direction'], 'increasing')
        self.assertGreater(trend['slope'], 0)
        self.assertGreater(trend['change_percentage'], 0)
        
        # Calculate adaptive score based on trend
        current_score = historical_scores[-1]['score']
        adaptive_score = self.calculator.calculate_adaptive_score(
            current_score,
            {'risk_trend': trend}
        )
        
        self.assertGreater(adaptive_score, current_score)
    
    def test_batch_processing_performance(self):
        """Test batch processing performance with realistic data."""
        # Create realistic dataset
        users = UserFactory.create_batch(50)
        
        user_data = []
        for user in users:
            # Create user profile
            profile = UserRiskProfileFactory.create(
                user=user,
                overall_risk_score=random.randint(20, 90),
                is_flagged=random.choice([True, False])
            )
            
            # Create device
            device = DeviceFingerprintFactory.create(
                user=user,
                trust_score=random.randint(10, 90)
            )
            
            # Create IP reputation
            ip_rep = IPReputationFactory.create(
                ip_address=f'192.168.1.{random.randint(1, 254)}',
                fraud_score=random.randint(0, 100)
            )
            
            user_data.append({
                'user_id': user.id,
                'profile': profile,
                'device': device,
                'ip': ip_rep
            })
        
        # Batch calculate all scores
        import time
        start_time = time.time()
        
        results = []
        for data in user_data:
            user_score = self.calculator.calculate_user_risk_score(data['user_id'])
            device_score = self.calculator.calculate_device_risk_score(data['device'].device_hash)
            ip_score = self.calculator.calculate_ip_risk_score(data['ip'].ip_address)
            
            aggregated = self.calculator.aggregate_multiple_scores([
                {'type': 'user', 'score': user_score, 'weight': 0.4},
                {'type': 'device', 'score': device_score, 'weight': 0.3},
                {'type': 'ip', 'score': ip_score, 'weight': 0.3},
            ])
            
            results.append({
                'user_id': data['user_id'],
                'user_score': user_score,
                'device_score': device_score,
                'ip_score': ip_score,
                'overall_score': aggregated['overall_score'],
                'risk_level': aggregated['risk_level']
            })
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Performance check
        self.assertLess(processing_time, 5.0)  # 5 seconds max
        self.assertEqual(len(results), 50)
        
        # Verify all results are valid
        for result in results:
            self.assertIsInstance(result['overall_score'], float)
            self.assertGreaterEqual(result['overall_score'], 0)
            self.assertLessEqual(result['overall_score'], 100)
            self.assertIn(result['risk_level'], ['low', 'medium', 'high', 'critical'])


if __name__ == '__main__':
    import random
    
    # Add random import for integration tests
    TestFraudScoreCalculatorIntegration.setUp = lambda self: (
        setattr(self, 'calculator', FraudScoreCalculator())
    )
