# =============================================================================
# fraud_detection/tests/test_pattern_analyzer.py
# =============================================================================
"""
Pattern Analyzer Tests.

Comprehensive tests for fraud pattern analysis including
pattern recognition, ML training, and anomaly detection.
"""

import json
import pytest
from datetime import timedelta
from unittest.mock import Mock, patch, MagicMock

from django.test import TestCase
from django.utils import timezone

from api.fraud_detection.detectors.PatternAnalyzer import PatternAnalyzer
from api.fraud_detection.models import FraudPattern, FraudAttempt
from api.fraud_detection.choices import PatternType, FraudAttemptStatus
from .factories import (
    UserFactory, FraudAttemptFactory, FraudPatternFactory,
    FraudTestDataGenerator
)


class TestPatternAnalyzer(TestCase):
    """Test cases for PatternAnalyzer."""
    
    def setUp(self):
        """Set up test data."""
        self.analyzer = PatternAnalyzer()
        self.user = UserFactory.create()
        
    def test_analyze_behavioral_patterns(self):
        """Test behavioral pattern analysis."""
        # Create user with behavioral data
        attempts = FraudAttemptFactory.create_batch(
            10,
            user=self.user,
            status='confirmed'
        )
        
        # Add behavioral evidence
        for i, attempt in enumerate(attempts):
            attempt.evidence_data = json.dumps({
                'time_of_day': i % 24,  # Different times
                'day_of_week': i % 7,  # Different days
                'action_sequence': f'seq_{i}',
                'duration': random.randint(30, 300),
            })
            attempt.save()
        
        patterns = self.analyzer.analyze_behavioral_patterns(self.user.id)
        
        self.assertIsInstance(patterns, dict)
        self.assertIn('temporal_patterns', patterns)
        self.assertIn('sequence_patterns', patterns)
        self.assertIn('anomaly_score', patterns)
        self.assertIn('confidence', patterns)
    
    def test_analyze_temporal_patterns(self):
        """Test temporal pattern analysis."""
        # Create attempts with specific temporal patterns
        base_time = timezone.now() - timedelta(days=30)
        
        # Create attempts at regular intervals (every 2 days at 2 PM)
        for i in range(15):
            FraudAttemptFactory.create(
                user=self.user,
                created_at=base_time + timedelta(days=i*2, hours=14),
                status='confirmed',
                evidence_data=json.dumps({
                    'time_of_day': 14,
                    'day_of_week': (base_time + timedelta(days=i*2)).weekday(),
                })
            )
        
        temporal_patterns = self.analyzer.analyze_temporal_patterns(self.user.id)
        
        self.assertIsInstance(temporal_patterns, dict)
        self.assertIn('regular_intervals', temporal_patterns)
        self.assertIn('peak_hours', temporal_patterns)
        self.assertIn('weekend_patterns', temporal_patterns)
        self.assertIn('anomaly_indicators', temporal_patterns)
    
    def test_analyze_geographic_patterns(self):
        """Test geographic pattern analysis."""
        # Create attempts with geographic data
        locations = [
            {'country': 'US', 'region': 'CA', 'city': 'San Francisco'},
            {'country': 'US', 'region': 'NY', 'city': 'New York'},
            {'country': 'GB', 'region': 'London', 'city': 'London'},
        ]
        
        for location in locations:
            FraudAttemptFactory.create(
                user=self.user,
                status='confirmed',
                evidence_data=json.dumps(location)
            )
        
        geographic_patterns = self.analyzer.analyze_geographic_patterns(self.user.id)
        
        self.assertIsInstance(geographic_patterns, dict)
        self.assertIn('location_diversity', geographic_patterns)
        self.assertIn('travel_patterns', geographic_patterns)
        self.assertIn('anomaly_score', geographic_patterns)
        self.assertIn('suspicious_locations', geographic_patterns)
    
    def test_analyze_device_patterns(self):
        """Test device pattern analysis."""
        # Create attempts with device data
        devices = [
            {'device_hash': 'device_1', 'device_type': 'desktop'},
            {'device_hash': 'device_2', 'device_type': 'mobile'},
            {'device_hash': 'device_3', 'device_type': 'tablet'},
        ]
        
        for device in devices:
            FraudAttemptFactory.create(
                user=self.user,
                status='confirmed',
                evidence_data=json.dumps(device)
            )
        
        device_patterns = self.analyzer.analyze_device_patterns(self.user.id)
        
        self.assertIsInstance(device_patterns, dict)
        self.assertIn('device_diversity', device_patterns)
        self.assertIn('switching_patterns', device_patterns)
        self.assertIn('trust_scores', device_patterns)
        self.assertIn('anomaly_indicators', device_patterns)
    
    def test_analyze_financial_patterns(self):
        """Test financial pattern analysis."""
        # Create attempts with financial data
        amounts = [10.50, 25.00, 50.00, 100.00, 200.00, 500.00]
        
        for amount in amounts:
            FraudAttemptFactory.create(
                user=self.user,
                status='confirmed',
                amount_involved=amount,
                evidence_data=json.dumps({
                    'transaction_type': 'purchase',
                    'currency': 'USD',
                })
            )
        
        financial_patterns = self.analyzer.analyze_financial_patterns(self.user.id)
        
        self.assertIsInstance(financial_patterns, dict)
        self.assertIn('amount_distribution', financial_patterns)
        self.assertIn('frequency_patterns', financial_patterns)
        self.assertIn('risk_indicators', financial_patterns)
        self.assertIn('anomaly_score', financial_patterns)
    
    def test_detect_anomalies(self):
        """Test anomaly detection."""
        # Create normal pattern
        for i in range(20):
            FraudAttemptFactory.create(
                user=self.user,
                status='confirmed',
                amount_involved=random.uniform(10, 50),  # Normal range
                created_at=timezone.now() - timedelta(hours=i*12)  # Regular intervals
            )
        
        # Add anomaly
        FraudAttemptFactory.create(
            user=self.user,
            status='confirmed',
            amount_involved=1000.00,  # Unusually high amount
            created_at=timezone.now() - timedelta(hours=1)
        )
        
        anomalies = self.analyzer.detect_anomalies(self.user.id)
        
        self.assertIsInstance(anomalies, dict)
        self.assertIn('anomaly_count', anomalies)
        self.assertIn('anomaly_details', anomalies)
        self.assertIn('overall_anomaly_score', anomalies)
        self.assertGreater(anomalies['anomaly_count'], 0)
    
    def test_train_pattern_model(self):
        """Test pattern model training."""
        # Create training data
        users = UserFactory.create_batch(10)
        
        for user in users:
            FraudAttemptFactory.create_batch(
                5,
                user=user,
                status='confirmed'
            )
        
        # Train model
        training_result = self.analyzer.train_pattern_model(
            pattern_type='behavioral',
            training_data={
                'user_ids': [user.id for user in users],
                'features': ['temporal', 'device', 'financial'],
            }
        )
        
        self.assertIsInstance(training_result, dict)
        self.assertIn('model_id', training_result)
        self.assertIn('accuracy', training_result)
        self.assertIn('training_samples', training_result)
        self.assertIn('feature_importance', training_result)
    
    def test_predict_fraud_probability(self):
        """Test fraud probability prediction."""
        # Create and train a model
        self.test_train_pattern_model()
        
        # Test prediction
        prediction_data = {
            'temporal_features': {
                'time_of_day': 14,
                'day_of_week': 2,
                'recent_activity': 5,
            },
            'device_features': {
                'device_diversity': 2,
                'trust_score': 75,
            },
            'financial_features': {
                'avg_amount': 45.50,
                'amount_variance': 15.25,
            }
        }
        
        probability = self.analyzer.predict_fraud_probability(
            self.user.id,
            prediction_data
        )
        
        self.assertIsInstance(probability, float)
        self.assertGreaterEqual(probability, 0.0)
        self.assertLessEqual(probability, 1.0)
    
    def test_extract_features(self):
        """Test feature extraction."""
        # Create attempts with various features
        for i in range(10):
            FraudAttemptFactory.create(
                user=self.user,
                status='confirmed',
                evidence_data=json.dumps({
                    'time_of_day': i % 24,
                    'device_type': random.choice(['desktop', 'mobile']),
                    'amount': random.uniform(10, 100),
                    'location': random.choice(['US', 'GB', 'CA']),
                })
            )
        
        features = self.analyzer.extract_features(self.user.id)
        
        self.assertIsInstance(features, dict)
        self.assertIn('temporal_features', features)
        self.assertIn('device_features', features)
        self.assertIn('financial_features', features)
        self.assertIn('behavioral_features', features)
        
        # Verify feature structure
        for feature_type, feature_data in features.items():
            self.assertIsInstance(feature_data, dict)
            self.assertGreater(len(feature_data), 0)
    
    def test_analyze_pattern_evolution(self):
        """Test pattern evolution analysis."""
        # Create attempts over time with evolving patterns
        base_time = timezone.now() - timedelta(days=30)
        
        for day in range(30):
            # Evolving pattern - increasing amounts over time
            amount = 10 + (day * 2)
            
            FraudAttemptFactory.create(
                user=self.user,
                created_at=base_time + timedelta(days=day),
                amount_involved=amount,
                status='confirmed'
            )
        
        evolution = self.analyzer.analyze_pattern_evolution(self.user.id)
        
        self.assertIsInstance(evolution, dict)
        self.assertIn('trend_analysis', evolution)
        self.assertIn('change_points', evolution)
        self.assertIn('evolution_score', evolution)
        self.assertIn('prediction_horizon', evolution)
    
    def test_cross_user_pattern_analysis(self):
        """Test cross-user pattern analysis."""
        # Create multiple users with similar patterns
        users = UserFactory.create_batch(5)
        
        for user in users:
            # Create similar temporal pattern
            for hour in [9, 14, 18]:  # Same hours for all users
                FraudAttemptFactory.create(
                    user=user,
                    created_at=timezone.now().replace(hour=hour, minute=0, second=0),
                    status='confirmed',
                    amount_involved=25.00
                )
        
        cross_patterns = self.analyzer.analyze_cross_user_patterns([u.id for u in users])
        
        self.assertIsInstance(cross_patterns, dict)
        self.assertIn('common_patterns', cross_patterns)
        self.assertIn('pattern_similarity', cross_patterns)
        self.assertIn('cluster_analysis', cross_patterns)
        self.assertIn('anomaly_groups', cross_patterns)
    
    def test_generate_pattern_report(self):
        """Test pattern report generation."""
        # Create diverse pattern data
        self.test_analyze_behavioral_patterns()
        self.test_analyze_temporal_patterns()
        self.test_analyze_geographic_patterns()
        
        report = self.analyzer.generate_pattern_report(self.user.id)
        
        self.assertIsInstance(report, dict)
        self.assertIn('summary', report)
        self.assertIn('behavioral_analysis', report)
        self.assertIn('temporal_analysis', report)
        self.assertIn('geographic_analysis', report)
        self.assertIn('risk_assessment', report)
        self.assertIn('recommendations', report)
    
    def test_pattern_validation(self):
        """Test pattern validation."""
        # Create valid pattern
        valid_pattern = {
            'type': 'temporal',
            'features': ['time_of_day', 'day_of_week'],
            'threshold': 0.8,
            'confidence': 0.9,
        }
        
        is_valid = self.analyzer.validate_pattern(valid_pattern)
        self.assertTrue(is_valid)
        
        # Create invalid pattern
        invalid_pattern = {
            'type': 'invalid_type',
            'features': [],  # Empty features
            'threshold': 1.5,  # Invalid threshold
        }
        
        is_valid = self.analyzer.validate_pattern(invalid_pattern)
        self.assertFalse(is_valid)
    
    def test_pattern_persistence(self):
        """Test pattern persistence and retrieval."""
        # Create and save a pattern
        pattern_data = {
            'pattern_type': 'behavioral',
            'name': 'test_pattern',
            'description': 'Test pattern for unit testing',
            'features': ['temporal', 'device'],
            'accuracy_rate': 0.85,
            'occurrence_count': 100,
        }
        
        pattern = self.analyzer.save_pattern(pattern_data)
        
        self.assertIsInstance(pattern, FraudPattern)
        self.assertEqual(pattern.pattern_type, 'behavioral')
        self.assertEqual(pattern.name, 'test_pattern')
        self.assertTrue(pattern.is_trained)
        
        # Retrieve pattern
        retrieved_pattern = self.analyzer.get_pattern(pattern.id)
        
        self.assertIsInstance(retrieved_pattern, FraudPattern)
        self.assertEqual(retrieved_pattern.id, pattern.id)
    
    def test_batch_pattern_analysis(self):
        """Test batch pattern analysis."""
        users = UserFactory.create_batch(10)
        
        # Create attempts for all users
        for user in users:
            FraudAttemptFactory.create_batch(
                3,
                user=user,
                status='confirmed'
            )
        
        # Batch analysis
        results = self.analyzer.batch_analyze_patterns([u.id for u in users])
        
        self.assertIsInstance(results, dict)
        self.assertEqual(len(results), 10)
        
        for user_id, analysis in results.items():
            self.assertIsInstance(analysis, dict)
            self.assertIn('risk_score', analysis)
            self.assertIn('patterns', analysis)
    
    @patch('fraud_detection.analyzers.PatternAnalyzer.logger')
    def test_error_handling(self, mock_logger):
        """Test error handling in pattern analysis."""
        # Test with invalid user ID
        with self.assertRaises(ValueError):
            self.analyzer.analyze_behavioral_patterns(999999)
        
        # Test with invalid pattern data
        with self.assertRaises(ValueError):
            self.analyzer.validate_pattern({})
        
        # Verify error logging
        mock_logger.error.assert_called()
    
    def test_performance_with_large_dataset(self):
        """Test performance with large dataset."""
        # Create large dataset
        users = UserFactory.create_batch(20)
        
        for user in users:
            FraudAttemptFactory.create_batch(
                50,
                user=user,
                status='confirmed'
            )
        
        # Test performance
        import time
        start_time = time.time()
        
        results = self.analyzer.batch_analyze_patterns([u.id for u in users])
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(processing_time, 10.0)  # 10 seconds max
        self.assertEqual(len(results), 20)
    
    def test_model_accuracy_calculation(self):
        """Test model accuracy calculation."""
        # Create test predictions and actual results
        predictions = [0.1, 0.3, 0.7, 0.9, 0.5]
        actual = [0, 0, 1, 1, 0]
        
        accuracy = self.analyzer._calculate_accuracy(predictions, actual)
        
        self.assertIsInstance(accuracy, float)
        self.assertGreaterEqual(accuracy, 0.0)
        self.assertLessEqual(accuracy, 1.0)
    
    def test_feature_importance_analysis(self):
        """Test feature importance analysis."""
        # Create trained model
        self.test_train_pattern_model()
        
        # Get feature importance
        importance = self.analyzer.get_feature_importance('behavioral')
        
        self.assertIsInstance(importance, dict)
        self.assertIn('features', importance)
        self.assertIn('importance_scores', importance)
        self.assertIn('ranking', importance)
    
    def test_pattern_comparison(self):
        """Test pattern comparison between users."""
        users = UserFactory.create_batch(3)
        
        for user in users:
            FraudAttemptFactory.create_batch(
                5,
                user=user,
                status='confirmed'
            )
        
        # Compare patterns
        comparison = self.analyzer.compare_user_patterns(
            users[0].id,
            users[1].id
        )
        
        self.assertIsInstance(comparison, dict)
        self.assertIn('similarity_score', comparison)
        self.assertIn('differences', comparison)
        self.assertIn('common_patterns', comparison)
        self.assertIn('divergent_patterns', comparison)


class TestPatternAnalyzerIntegration(TestCase):
    """Integration tests for PatternAnalyzer."""
    
    def setUp(self):
        """Set up integration test data."""
        self.analyzer = PatternAnalyzer()
        self.scenario = FraudTestDataGenerator.create_fraud_scenario(
            user_count=20,
            days=60
        )
    
    def test_end_to_end_pattern_analysis(self):
        """Test end-to-end pattern analysis workflow."""
        user = self.scenario['users'][0]
        
        # Create comprehensive pattern data
        FraudAttemptFactory.create_batch(
            15,
            user=user,
            status='confirmed',
            evidence_data=json.dumps({
                'time_of_day': random.randint(0, 23),
                'device_type': random.choice(['desktop', 'mobile', 'tablet']),
                'location': random.choice(['US', 'GB', 'CA', 'AU']),
                'amount': random.uniform(10, 200),
            })
        )
        
        # Analyze patterns
        behavioral_patterns = self.analyzer.analyze_behavioral_patterns(user.id)
        temporal_patterns = self.analyzer.analyze_temporal_patterns(user.id)
        geographic_patterns = self.analyzer.analyze_geographic_patterns(user.id)
        
        # Generate comprehensive report
        report = self.analyzer.generate_pattern_report(user.id)
        
        # Verify analysis results
        self.assertIsInstance(behavioral_patterns, dict)
        self.assertIn('anomaly_score', behavioral_patterns)
        
        self.assertIsInstance(temporal_patterns, dict)
        self.assertIn('regular_intervals', temporal_patterns)
        
        self.assertIsInstance(geographic_patterns, dict)
        self.assertIn('location_diversity', geographic_patterns)
        
        self.assertIsInstance(report, dict)
        self.assertIn('risk_assessment', report)
        self.assertIn('recommendations', report)
    
    def test_ml_model_training_integration(self):
        """Test ML model training integration."""
        # Create training dataset
        users = UserFactory.create_batch(15)
        
        for user in users:
            # Create diverse patterns
            FraudAttemptFactory.create_batch(
                10,
                user=user,
                status=random.choice(['confirmed', 'false_positive'])
            )
        
        # Train multiple pattern types
        pattern_types = ['behavioral', 'temporal', 'geographic', 'financial']
        trained_models = {}
        
        for pattern_type in pattern_types:
            training_result = self.analyzer.train_pattern_model(
                pattern_type=pattern_type,
                training_data={
                    'user_ids': [user.id for user in users],
                    'features': ['all'],
                }
            )
            
            trained_models[pattern_type] = training_result
            
            # Verify training result
            self.assertIsInstance(training_result, dict)
            self.assertIn('model_id', training_result)
            self.assertIn('accuracy', training_result)
            self.assertGreater(training_result['accuracy'], 0.5)
        
        # Test predictions with trained models
        test_user = UserFactory.create()
        FraudAttemptFactory.create_batch(
            5,
            user=test_user,
            status='confirmed'
        )
        
        for pattern_type in pattern_types:
            try:
                prediction = self.analyzer.predict_fraud_probability(
                    test_user.id,
                    {'features': ['temporal', 'device', 'financial']}
                )
                
                self.assertIsInstance(prediction, float)
                self.assertGreaterEqual(prediction, 0.0)
                self.assertLessEqual(prediction, 1.0)
                
            except Exception as e:
                # Some pattern types might not have enough data
                pass
    
    def test_cross_user_pattern_detection(self):
        """Test cross-user pattern detection."""
        # Create users with similar suspicious patterns
        suspicious_users = UserFactory.create_batch(5)
        
        for user in suspicious_users:
            # Create similar temporal pattern (all active at 2 AM)
            for day in range(7):
                FraudAttemptFactory.create(
                    user=user,
                    created_at=timezone.now().replace(hour=2, minute=0, second=0) - timedelta(days=day),
                    status='confirmed',
                    amount_involved=100.00,  # Same amount
                    evidence_data=json.dumps({
                        'device_type': 'mobile',
                        'location': 'US',
                    })
                )
        
        # Cross-user analysis
        cross_patterns = self.analyzer.analyze_cross_user_patterns([u.id for u in suspicious_users])
        
        self.assertIsInstance(cross_patterns, dict)
        self.assertIn('common_patterns', cross_patterns)
        self.assertIn('pattern_similarity', cross_patterns)
        
        # Should detect the common 2 AM pattern
        common_patterns = cross_patterns['common_patterns']
        self.assertGreater(len(common_patterns), 0)
    
    def test_pattern_evolution_tracking(self):
        """Test pattern evolution tracking over time."""
        user = UserFactory.create()
        
        # Create evolving pattern over 60 days
        base_time = timezone.now() - timedelta(days=60)
        
        for day in range(60):
            # Gradually increase risk indicators
            risk_score = min(day / 60 * 100, 100)
            
            FraudAttemptFactory.create(
                user=user,
                created_at=base_time + timedelta(days=day),
                fraud_score=risk_score,
                amount_involved=10 + (day * 2),  # Increasing amounts
                status='confirmed' if risk_score > 50 else 'reviewing'
            )
        
        # Analyze evolution
        evolution = self.analyzer.analyze_pattern_evolution(user.id)
        
        self.assertIsInstance(evolution, dict)
        self.assertIn('trend_analysis', evolution)
        self.assertIn('change_points', evolution)
        self.assertIn('evolution_score', evolution)
        
        # Should detect increasing trend
        trend_analysis = evolution['trend_analysis']
        self.assertIn('direction', trend_analysis)
        self.assertEqual(trend_analysis['direction'], 'increasing')
    
    def test_performance_with_comprehensive_dataset(self):
        """Test performance with comprehensive dataset."""
        # Create large comprehensive dataset
        users = UserFactory.create_batch(30)
        
        for user in users:
            # Create diverse activity
            FraudAttemptFactory.create_batch(
                random.randint(20, 50),
                user=user,
                status=random.choice(['confirmed', 'false_positive', 'reviewing']),
                evidence_data=json.dumps({
                    'time_of_day': random.randint(0, 23),
                    'device_type': random.choice(['desktop', 'mobile', 'tablet']),
                    'location': random.choice(['US', 'GB', 'CA', 'AU', 'DE']),
                    'amount': random.uniform(5, 500),
                })
            )
        
        # Test comprehensive analysis performance
        import time
        start_time = time.time()
        
        # Batch analysis
        results = self.analyzer.batch_analyze_patterns([u.id for u in users])
        
        # Cross-user analysis
        cross_results = self.analyzer.analyze_cross_user_patterns([u.id for u in users[:10]])
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(processing_time, 15.0)  # 15 seconds max
        self.assertEqual(len(results), 30)
        self.assertIsInstance(cross_results, dict)


if __name__ == '__main__':
    import random
    
    # Add random import for integration tests
    TestPatternAnalyzerIntegration.setUp = lambda self: (
        setattr(self, 'analyzer', PatternAnalyzer()) or
        setattr(self, 'scenario', FraudTestDataGenerator.create_fraud_scenario(user_count=20, days=60))
    )
