# =============================================================================
# fraud_detection/tests/test_multi_account_detector.py
# =============================================================================
"""
Multi-Account Detector Tests.

Comprehensive tests for multi-account fraud detection including
account correlation, pattern analysis, and relationship mapping.
"""

import json
import pytest
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from api.fraud_detection.detectors.MultiAccountDetector import MultiAccountDetector
from api.fraud_detection.models import FraudAttempt, UserRiskProfile
from api.fraud_detection.choices import FraudAttemptType
from .factories import (
    UserFactory, FraudAttemptFactory, UserRiskProfileFactory,
    FraudTestDataGenerator
)


class TestMultiAccountDetector(TestCase):
    """Test cases for MultiAccountDetector."""
    
    def setUp(self):
        """Set up test data."""
        self.detector = MultiAccountDetector()
        
    def test_detect_single_user_normal_activity(self):
        """Test detection with single user normal activity."""
        user = UserFactory.create()
        
        # Create normal activity
        FraudAttemptFactory.create(
            user=user,
            status='false_positive'
        )
        
        result = self.detector.detect_multi_account_activity(user.id)
        
        self.assertIsInstance(result, dict)
        self.assertIn('is_suspicious', result)
        self.assertIn('risk_score', result)
        self.assertIn('evidence', result)
        self.assertFalse(result['is_suspicious'])
        self.assertLess(result['risk_score'], 30)
    
    def test_detect_multiple_accounts_same_ip(self):
        """Test detection of multiple accounts from same IP."""
        # Create multiple users
        users = UserFactory.create_batch(5)
        
        # Create attempts from same IP
        common_ip = '192.168.1.100'
        
        for user in users:
            FraudAttemptFactory.create(
                user=user,
                evidence_data=json.dumps({'ip_address': common_ip}),
                status='confirmed'
            )
        
        # Test detection for each user
        for user in users:
            result = self.detector.detect_multi_account_activity(user.id)
            
            self.assertIsInstance(result, dict)
            self.assertIn('shared_ip_addresses', result['evidence'])
            self.assertGreaterEqual(result['risk_score'], 60)
    
    def test_detect_multiple_accounts_same_device(self):
        """Test detection of multiple accounts from same device."""
        # Create multiple users
        users = UserFactory.create_batch(3)
        
        # Create attempts from same device
        common_device = 'device_hash_12345'
        
        for user in users:
            FraudAttemptFactory.create(
                user=user,
                evidence_data=json.dumps({'device_hash': common_device}),
                status='confirmed'
            )
        
        # Test detection for each user
        for user in users:
            result = self.detector.detect_multi_account_activity(user.id)
            
            self.assertIsInstance(result, dict)
            self.assertIn('shared_devices', result['evidence'])
            self.assertGreaterEqual(result['risk_score'], 70)
    
    def test_detect_similar_registration_patterns(self):
        """Test detection of similar registration patterns."""
        # Create users with similar registration patterns
        base_time = timezone.now() - timedelta(days=30)
        
        users = []
        for i in range(4):
            user = UserFactory.create(
                date_joined=base_time + timedelta(minutes=i*5),  # Close registration times
                email=f'user_{i:03d}@similar-domain.com',  # Similar email domain
                first_name='Test',  # Same first name
                last_name=f'User{i}',  # Similar last name pattern
            )
            users.append(user)
        
        # Create attempts
        for user in users:
            FraudAttemptFactory.create(
                user=user,
                status='confirmed'
            )
        
        # Test detection
        for user in users:
            result = self.detector.detect_multi_account_activity(user.id)
            
            self.assertIsInstance(result, dict)
            if 'similar_registration' in result['evidence']:
                self.assertGreater(result['risk_score'], 40)
    
    def test_detect_behavioral_patterns(self):
        """Test detection of similar behavioral patterns."""
        # Create users with similar behavior
        users = UserFactory.create_batch(3)
        
        # Create attempts with similar timing patterns
        base_time = timezone.now() - timedelta(days=7)
        
        for i, user in enumerate(users):
            # Create attempts at similar times
            for day in range(7):
                FraudAttemptFactory.create(
                    user=user,
                    created_at=base_time + timedelta(days=day, hours=9),  # Same time each day
                    status='confirmed'
                )
        
        # Test detection
        for user in users:
            result = self.detector.detect_multi_account_activity(user.id)
            
            self.assertIsInstance(result, dict)
            if 'behavioral_patterns' in result['evidence']:
                self.assertGreater(result['risk_score'], 50)
    
    def test_detect_geographic_proximity(self):
        """Test detection of geographic proximity between accounts."""
        # Create users from same geographic area
        users = UserFactory.create_batch(3)
        
        # Create attempts from same location
        location_data = {
            'country': 'US',
            'region': 'CA',
            'city': 'San Francisco',
            'latitude': 37.7749,
            'longitude': -122.4194,
        }
        
        for user in users:
            FraudAttemptFactory.create(
                user=user,
                evidence_data=json.dumps(location_data),
                status='confirmed'
            )
        
        # Test detection
        for user in users:
            result = self.detector.detect_multi_account_activity(user.id)
            
            self.assertIsInstance(result, dict)
            if 'geographic_proximity' in result['evidence']:
                self.assertGreater(result['risk_score'], 35)
    
    def test_detect_financial_patterns(self):
        """Test detection of similar financial patterns."""
        # Create users with similar financial behavior
        users = UserFactory.create_batch(3)
        
        # Create attempts with similar amounts
        common_amounts = [10.50, 25.00, 50.00]
        
        for user in users:
            for amount in common_amounts:
                FraudAttemptFactory.create(
                    user=user,
                    amount_involved=amount,
                    status='confirmed'
                )
        
        # Test detection
        for user in users:
            result = self.detector.detect_multi_account_activity(user.id)
            
            self.assertIsInstance(result, dict)
            if 'financial_patterns' in result['evidence']:
                self.assertGreater(result['risk_score'], 45)
    
    def test_analyze_user_relationships(self):
        """Test user relationship analysis."""
        # Create related users
        users = UserFactory.create_batch(5)
        
        # Create network of relationships
        relationships = [
            (users[0], users[1], 'same_ip'),
            (users[1], users[2], 'same_device'),
            (users[2], users[3], 'similar_behavior'),
            (users[3], users[4], 'geographic_proximity'),
        ]
        
        for user1, user2, relationship_type in relationships:
            # Create evidence for relationship
            if relationship_type == 'same_ip':
                ip = '192.168.1.100'
                FraudAttemptFactory.create(
                    user=user1,
                    evidence_data=json.dumps({'ip_address': ip})
                )
                FraudAttemptFactory.create(
                    user=user2,
                    evidence_data=json.dumps({'ip_address': ip})
                )
            elif relationship_type == 'same_device':
                device = 'device_hash_123'
                FraudAttemptFactory.create(
                    user=user1,
                    evidence_data=json.dumps({'device_hash': device})
                )
                FraudAttemptFactory.create(
                    user=user2,
                    evidence_data=json.dumps({'device_hash': device})
                )
        
        # Analyze relationships
        relationships = self.detector.analyze_user_relationships(users[0].id)
        
        self.assertIsInstance(relationships, dict)
        self.assertIn('direct_connections', relationships)
        self.assertIn('indirect_connections', relationships)
        self.assertIn('network_size', relationships)
    
    def test_calculate_relationship_strength(self):
        """Test relationship strength calculation."""
        # Test different relationship types
        relationship_evidence = {
            'shared_ip_addresses': 5,
            'shared_devices': 3,
            'similar_timing': 10,
            'geographic_proximity': 2,
            'financial_similarity': 8,
        }
        
        strength = self.detector._calculate_relationship_strength(relationship_evidence)
        
        self.assertIsInstance(strength, float)
        self.assertGreaterEqual(strength, 0)
        self.assertLessEqual(strength, 1)
    
    def test_detect_account_clusters(self):
        """Test account cluster detection."""
        # Create cluster of related accounts
        cluster_size = 7
        users = UserFactory.create_batch(cluster_size)
        
        # Create shared evidence within cluster
        common_ip = '192.168.1.200'
        common_device = 'device_cluster_123'
        
        for i, user in enumerate(users):
            # Shared patterns within cluster
            FraudAttemptFactory.create(
                user=user,
                evidence_data=json.dumps({
                    'ip_address': common_ip,
                    'device_hash': common_device,
                    'cluster_id': 'cluster_1'
                }),
                status='confirmed'
            )
        
        # Detect clusters
        clusters = self.detector.detect_account_clusters()
        
        self.assertIsInstance(clusters, list)
        self.assertGreater(len(clusters), 0)
        
        # Check cluster details
        cluster = clusters[0]
        self.assertIn('cluster_id', cluster)
        self.assertIn('users', cluster)
        self.assertIn('strength', cluster)
        self.assertIn('evidence_types', cluster)
    
    def test_track_account_evolution(self):
        """Test account evolution tracking."""
        user = UserFactory.create()
        
        # Create account evolution over time
        base_time = timezone.now() - timedelta(days=30)
        
        # Initial activity
        FraudAttemptFactory.create(
            user=user,
            created_at=base_time,
            status='false_positive'
        )
        
        # Gradual escalation
        for day in range(1, 30):
            risk_score = min(day * 2, 80)
            FraudAttemptFactory.create(
                user=user,
                created_at=base_time + timedelta(days=day),
                fraud_score=risk_score,
                status='confirmed' if risk_score > 50 else 'reviewing'
            )
        
        # Track evolution
        evolution = self.detector.track_account_evolution(user.id)
        
        self.assertIsInstance(evolution, dict)
        self.assertIn('risk_trend', evolution)
        self.assertIn('behavior_changes', evolution)
        self.assertIn('escalation_points', evolution)
    
    def test_generate_account_profile(self):
        """Test account profile generation."""
        user = UserFactory.create()
        
        # Create diverse activity
        FraudAttemptFactory.create_batch(
            5,
            user=user,
            status='confirmed'
        )
        FraudAttemptFactory.create_batch(
            2,
            user=user,
            status='false_positive'
        )
        
        # Generate profile
        profile = self.detector.generate_account_profile(user.id)
        
        self.assertIsInstance(profile, dict)
        self.assertIn('risk_score', profile)
        self.assertIn('activity_patterns', profile)
        self.assertIn('relationships', profile)
        self.assertIn('anomalies', profile)
    
    def test_batch_detection(self):
        """Test batch multi-account detection."""
        users = UserFactory.create_batch(10)
        
        # Create mixed activity
        for user in users:
            FraudAttemptFactory.create(
                user=user,
                status='confirmed' if random.random() < 0.7 else 'false_positive'
            )
        
        # Batch detection
        results = self.detector.batch_detect_multi_account_activity([u.id for u in users])
        
        self.assertIsInstance(results, dict)
        self.assertEqual(len(results), 10)
        
        for user_id, result in results.items():
            self.assertIsInstance(result, dict)
            self.assertIn('is_suspicious', result)
            self.assertIn('risk_score', result)
    
    def test_detector_configuration(self):
        """Test detector configuration options."""
        # Test custom thresholds
        custom_detector = MultiAccountDetector(
            min_relationship_strength=0.8,
            cluster_min_size=5,
            risk_threshold=40
        )
        
        user = UserFactory.create()
        FraudAttemptFactory.create(user=user, status='confirmed')
        
        result = custom_detector.detect_multi_account_activity(user.id)
        
        self.assertIsInstance(result, dict)
        self.assertIn('is_suspicious', result)
    
    @patch('fraud_detection.detectors.MultiAccountDetector.logger')
    def test_error_handling(self, mock_logger):
        """Test error handling in detection process."""
        # Test with invalid user ID
        with self.assertRaises(ValueError):
            self.detector.detect_multi_account_activity(999999)
        
        # Test with invalid batch data
        with self.assertRaises(ValueError):
            self.detector.batch_detect_multi_account_activity([])
        
        # Verify error logging
        mock_logger.error.assert_called()
    
    def test_evidence_collection(self):
        """Test evidence collection and analysis."""
        # Create user with multiple evidence types
        user = UserFactory.create()
        
        # IP evidence
        FraudAttemptFactory.create(
            user=user,
            evidence_data=json.dumps({'ip_address': '192.168.1.100'})
        )
        
        # Device evidence
        FraudAttemptFactory.create(
            user=user,
            evidence_data=json.dumps({'device_hash': 'device_123'})
        )
        
        # Behavioral evidence
        FraudAttemptFactory.create(
            user=user,
            evidence_data=json.dumps({'timing_pattern': 'regular'})
        )
        
        result = self.detector.detect_multi_account_activity(user.id)
        
        self.assertIn('evidence', result)
        evidence = result['evidence']
        
        self.assertIsInstance(evidence, dict)
        # Should contain evidence from different categories
        evidence_types = list(evidence.keys())
        self.assertGreater(len(evidence_types), 1)
    
    def test_confidence_calculation(self):
        """Test confidence score calculation."""
        # Test with strong evidence
        strong_evidence = {
            'shared_ip_addresses': {'count': 10, 'users': 5},
            'shared_devices': {'count': 8, 'users': 4},
            'behavioral_patterns': {'similarity': 0.9},
        }
        
        confidence = self.detector._calculate_confidence(strong_evidence)
        
        self.assertIsInstance(confidence, float)
        self.assertGreaterEqual(confidence, 0.7)
        self.assertLessEqual(confidence, 1.0)
        
        # Test with weak evidence
        weak_evidence = {
            'minor_similarity': {'score': 0.3},
        }
        
        confidence = self.detector._calculate_confidence(weak_evidence)
        
        self.assertLess(confidence, 0.5)


class TestMultiAccountDetectorIntegration(TestCase):
    """Integration tests for MultiAccountDetector."""
    
    def setUp(self):
        """Set up integration test data."""
        self.detector = MultiAccountDetector()
        self.scenario = FraudTestDataGenerator.create_fraud_scenario(
            user_count=15,
            days=30
        )
    
    def test_end_to_end_multi_account_detection(self):
        """Test end-to-end multi-account detection workflow."""
        # Create suspicious multi-account scenario
        users = UserFactory.create_batch(5)
        
        # Create shared evidence between users
        common_ip = '192.168.1.150'
        common_device = 'device_multi_123'
        
        for i, user in enumerate(users):
            # Create attempts with shared characteristics
            FraudAttemptFactory.create_batch(
                3,
                user=user,
                evidence_data=json.dumps({
                    'ip_address': common_ip,
                    'device_hash': common_device,
                    'timing_pattern': f'pattern_{i % 3}',
                }),
                status='confirmed'
            )
        
        # Detect multi-account activity
        for user in users:
            result = self.detector.detect_multi_account_activity(user.id)
            
            # Verify detection result
            self.assertGreaterEqual(result['risk_score'], 70)
            
            # Create fraud attempt if score is high enough
            if result['risk_score'] >= 60:
                attempt = FraudAttempt.objects.create(
                    user=user,
                    attempt_type=FraudAttemptType.MULTI_ACCOUNT,
                    description=f"Multi-account activity detected: {result['risk_score']}",
                    detected_by='MultiAccountDetector',
                    fraud_score=result['risk_score'],
                    confidence_score=0.85,
                    evidence_data=json.dumps(result['evidence']),
                )
                
                self.assertIsInstance(attempt, FraudAttempt)
                self.assertEqual(attempt.fraud_score, result['risk_score'])
    
    def test_cluster_analysis_integration(self):
        """Test cluster analysis integration."""
        # Create multiple clusters
        cluster_1_users = UserFactory.create_batch(4)
        cluster_2_users = UserFactory.create_batch(3)
        
        # Cluster 1 - shared IP and device
        cluster_1_ip = '192.168.1.200'
        cluster_1_device = 'device_cluster_1'
        
        for user in cluster_1_users:
            FraudAttemptFactory.create(
                user=user,
                evidence_data=json.dumps({
                    'ip_address': cluster_1_ip,
                    'device_hash': cluster_1_device
                }),
                status='confirmed'
            )
        
        # Cluster 2 - shared behavior
        for user in cluster_2_users:
            FraudAttemptFactory.create(
                user=user,
                evidence_data=json.dumps({
                    'behavior_pattern': 'cluster_2_pattern'
                }),
                status='confirmed'
            )
        
        # Detect clusters
        clusters = self.detector.detect_account_clusters()
        
        self.assertIsInstance(clusters, list)
        self.assertGreaterEqual(len(clusters), 1)
        
        # Verify cluster structure
        for cluster in clusters:
            self.assertIn('cluster_id', cluster)
            self.assertIn('users', cluster)
            self.assertIn('strength', cluster)
            self.assertGreater(len(cluster['users']), 1)
    
    def test_relationship_mapping_integration(self):
        """Test relationship mapping integration."""
        # Create complex relationship network
        central_users = UserFactory.create_batch(2)
        peripheral_users = UserFactory.create_batch(6)
        
        # Connect peripheral users to central users
        for i, user in enumerate(peripheral_users):
            central_user = central_users[i % 2]
            
            # Create shared evidence
            FraudAttemptFactory.create(
                user=user,
                evidence_data=json.dumps({
                    'related_to': central_user.id,
                    'connection_type': 'shared_behavior'
                }),
                status='confirmed'
            )
            
            FraudAttemptFactory.create(
                user=central_user,
                evidence_data=json.dumps({
                    'related_to': user.id,
                    'connection_type': 'shared_behavior'
                }),
                status='confirmed'
            )
        
        # Analyze relationships for central users
        for central_user in central_users:
            relationships = self.detector.analyze_user_relationships(central_user.id)
            
            self.assertIsInstance(relationships, dict)
            self.assertIn('direct_connections', relationships)
            self.assertGreater(len(relationships['direct_connections']), 0)
    
    def test_performance_with_large_dataset(self):
        """Test performance with large dataset."""
        # Create large number of users and activities
        users = UserFactory.create_batch(50)
        
        for user in users:
            FraudAttemptFactory.create_batch(
                random.randint(1, 10),
                user=user,
                status='confirmed'
            )
        
        # Test batch detection performance
        import time
        start_time = time.time()
        
        user_ids = [user.id for user in users]
        results = self.detector.batch_detect_multi_account_activity(user_ids)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(processing_time, 5.0)  # 5 seconds max
        self.assertEqual(len(results), 50)
        
        # Verify all results
        for user_id, result in results.items():
            self.assertIsInstance(result, dict)
            self.assertIn('is_suspicious', result)
            self.assertIn('risk_score', result)


if __name__ == '__main__':
    import random
    
    # Add random import for integration tests
    TestMultiAccountDetectorIntegration.setUp = lambda self: (
        setattr(self, 'detector', MultiAccountDetector()) or
        setattr(self, 'scenario', FraudTestDataGenerator.create_fraud_scenario(user_count=15, days=30))
    )
