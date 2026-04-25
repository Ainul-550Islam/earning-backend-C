"""
Test Collaborative Filter

Tests for the collaborative filtering service
to ensure it works correctly.
"""

import logging
import pytest
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch
from ..services.personalization import CollaborativeFilterService
from ..models import UserOfferHistory, OfferAffinityScore
from ..constants import DEFAULT_ROUTING_LIMIT

logger = logging.getLogger(__name__)

User = get_user_model()


class TestCollaborativeFilter(TestCase):
    """Test cases for CollaborativeFilterService."""
    
    def setUp(self):
        """Set up test environment."""
        self.collab_service = CollaborativeFilterService()
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            is_active=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        User.objects.filter(id=self.test_user.id).delete()
    
    def test_get_similar_users_basic(self):
        """Test basic similar user finding."""
        try:
            # Create test users with similar behavior
            users = []
            for i in range(5):
                users.append(User.objects.create_user(
                    username=f'similaruser{i+1}',
                    email=f'similar{i+1}@example.com',
                    is_active=True
                ))
            
            # Create similar offer history
            for user in users:
                UserOfferHistory.objects.create(
                    user=user,
                    offer_id=1,
                    score_at_time=0.8,
                    clicked_at=timezone.now() - timezone.timedelta(hours=1)
                )
            
            # Get similar users
            result = self.collab_service.get_similar_users(self.test_user, limit=3)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(len(result['similar_users']), 3)
            self.assertEqual(result['metadata']['total_users'], 5)
            self.assertEqual(result['metadata']['limit'], 3)
            
            # Verify similarity scores are reasonable
            for similar_user in result['similar_users']:
                self.assertIn('similarity_score', similar_user)
                self.assertGreaterEqual(similar_user['similarity_score'], 0.0)
                self.assertLessEqual(similar_user['similarity_score'], 1.0)
                
        except Exception as e:
            self.fail(f"Error in test_get_similar_users_basic: {e}")
    
    def test_get_similar_users_with_no_history(self):
        """Test similar user finding with no history."""
        try:
            # Get similar users for user with no history
            result = self.collab_service.get_similar_users(self.test_user, limit=5)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(len(result['similar_users']), 0)
            self.assertEqual(result['metadata']['total_users'], 0)
            
        except Exception as e:
            self.fail(f"Error in test_get_similar_users_with_no_history: {e}")
    
    def test_calculate_user_similarity_basic(self):
        """Test basic user similarity calculation."""
        try:
            # Create test users
            user1 = User.objects.create_user(
                username='user1',
                email='user1@example.com',
                is_active=True
            )
            user2 = User.objects.create_user(
                username='user2',
                email='user2@example.com',
                is_active=True
            )
            
            # Create similar offer history
            common_offers = [1, 2, 3]
            for offer_id in common_offers:
                UserOfferHistory.objects.create(
                    user=user1,
                    offer_id=offer_id,
                    score_at_time=0.8,
                    clicked_at=timezone.now() - timezone.timedelta(hours=1)
                )
                UserOfferHistory.objects.create(
                    user=user2,
                    offer_id=offer_id,
                    score_at_time=0.9,
                    clicked_at=timezone.now() - timezone.timedelta(hours=2)
                )
            
            # Calculate similarity
            similarity = self.collab_service.calculate_user_similarity(user1, user2)
            
            # Assertions
            self.assertIsInstance(similarity, dict)
            self.assertIn('similarity_score', similarity)
            self.assertIn('common_offers', similarity)
            self.assertIn('total_offers_user1', similarity)
            self.assertIn('total_offers_user2', similarity)
            self.assertIn('jaccard_similarity', similarity)
            
            # Verify similarity score is reasonable
            self.assertGreaterEqual(similarity['similarity_score'], 0.0)
            self.assertLessEqual(similarity['similarity_score'], 1.0)
            self.assertEqual(len(similarity['common_offers']), 3)
            self.assertEqual(similarity['jaccard_similarity'], 3.0 / 3.0)  # All offers common
            
        except Exception as e:
            self.fail(f"Error in test_calculate_user_similarity_basic: {e}")
    
    def test_calculate_user_similarity_no_overlap(self):
        """Test user similarity calculation with no overlap."""
        try:
            # Create test users
            user1 = User.objects.create_user(
                username='user1',
                email='user1@example.com',
                is_active=True
            )
            user2 = User.objects.create_user(
                username='user2',
                email='user2@example.com',
                is_active=True
            )
            
            # Create different offer history
            UserOfferHistory.objects.create(
                user=user1,
                offer_id=1,
                score_at_time=0.8,
                clicked_at=timezone.now() - timezone.timedelta(hours=1)
            )
            UserOfferHistory.objects.create(
                user=user2,
                offer_id=2,
                score_at_time=0.9,
                clicked_at=timezone.now() - timezone.timedelta(hours=2)
            )
            
            # Calculate similarity
            similarity = self.collab_service.calculate_user_similarity(user1, user2)
            
            # Assertions
            self.assertEqual(similarity['similarity_score'], 0.0)
            self.assertEqual(len(similarity['common_offers']), 0)
            self.assertEqual(similarity['jaccard_similarity'], 0.0)
            
        except Exception as e:
            self.fail(f"Error in test_calculate_user_similarity_no_overlap: {e}")
    
    def test_get_item_based_recommendations_basic(self):
        """Test basic item-based recommendations."""
        try:
            # Create test user and offer history
            UserOfferHistory.objects.create(
                user=self.test_user,
                offer_id=1,
                score_at_time=0.8,
                clicked_at=timezone.now() - timezone.timedelta(hours=1)
            )
            UserOfferHistory.objects.create(
                user=self.test_user,
                offer_id=2,
                score_at_time=0.9,
                clicked_at=timezone.now() - timezone.timedelta(hours=2)
            )
            
            # Get item-based recommendations
            result = self.collab_service.get_item_based_recommendations(
                user_id=self.test_user.id,
                limit=5
            )
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(len(result['recommendations']), 5)
            self.assertEqual(result['metadata']['method'], 'item_based')
            self.assertEqual(result['metadata']['limit'], 5)
            
            # Verify recommendations have required fields
            for rec in result['recommendations']:
                self.assertIn('offer_id', rec)
                self.assertIn('score', rec)
                self.assertIn('similarity', rec)
                self.assertIn('reason', rec)
                
        except Exception as e:
            self.fail(f"Error in test_get_item_based_recommendations_basic: {e}")
    
    def test_get_item_based_recommendations_with_no_history(self):
        """Test item-based recommendations with no history."""
        try:
            # Get recommendations for user with no history
            result = self.collab_service.get_item_based_recommendations(
                user_id=self.test_user.id,
                limit=5
            )
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(len(result['recommendations']), 0)
            self.assertEqual(result['metadata']['method'], 'item_based')
            
        except Exception as e:
            self.fail(f"Error in test_get_item_based_recommendations_with_no_history: {e}")
    
    def test_get_user_based_recommendations_basic(self):
        """Test basic user-based recommendations."""
        try:
            # Create similar users and their history
            similar_users = []
            for i in range(3):
                user = User.objects.create_user(
                    username=f'similaruser{i+1}',
                    email=f'similar{i+1}@example.com',
                    is_active=True
                )
                similar_users.append(user)
                
                # Create history for similar user
                UserOfferHistory.objects.create(
                    user=user,
                    offer_id=10 + i,  # Different offers
                    score_at_time=0.7 + (i * 0.1),
                    clicked_at=timezone.now() - timezone.timedelta(hours=1)
                )
            
            # Create test user history
            UserOfferHistory.objects.create(
                user=self.test_user,
                offer_id=1,
                score_at_time=0.8,
                clicked_at=timezone.now() - timezone.timedelta(hours=1)
            )
            
            # Mock similar users
            with patch.object(self.collab_service, 'get_similar_users') as mock_similar:
                mock_similar.return_value = {
                    'success': True,
                    'similar_users': [
                        {'user_id': user.id, 'similarity_score': 0.8}
                        for user in similar_users
                    ]
                }
                
                # Get user-based recommendations
                result = self.collab_service.get_user_based_recommendations(
                    user_id=self.test_user.id,
                    limit=5
                )
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertEqual(len(result['recommendations']), 5)
                self.assertEqual(result['metadata']['method'], 'user_based')
                mock_similar.assert_called_once_with(self.test_user.id, limit=10)
                
        except Exception as e:
            self.fail(f"Error in test_get_user_based_recommendations_basic: {e}")
    
    def test_get_hybrid_recommendations_basic(self):
        """Test basic hybrid recommendations."""
        try:
            # Create test user and history
            UserOfferHistory.objects.create(
                user=self.test_user,
                offer_id=1,
                score_at_time=0.8,
                clicked_at=timezone.now() - timezone.timedelta(hours=1)
            )
            
            # Mock item-based and user-based recommendations
            with patch.object(self.collab_service, 'get_item_based_recommendations') as mock_item:
                mock_item.return_value = {
                    'success': True,
                    'recommendations': [
                        {'offer_id': 1, 'score': 0.9, 'similarity': 0.8}
                    ]
                }
                
                with patch.object(self.collab_service, 'get_user_based_recommendations') as mock_user:
                    mock_user.return_value = {
                        'success': True,
                        'recommendations': [
                            {'offer_id': 2, 'score': 0.7, 'similarity': 0.6}
                        ]
                    }
                    
                    # Get hybrid recommendations
                    result = self.collab_service.get_hybrid_recommendations(
                        user_id=self.test_user.id,
                        limit=5
                    )
                    
                    # Assertions
                    self.assertTrue(result['success'])
                    self.assertEqual(len(result['recommendations']), 5)
                    self.assertEqual(result['metadata']['method'], 'hybrid')
                    mock_item.assert_called_once()
                    mock_user.assert_called_once()
                    
        except Exception as e:
            self.fail(f"Error in test_get_hybrid_recommendations_basic: {e}")
    
    def test_update_collaborative_model_basic(self):
        """Test basic collaborative model update."""
        try:
            # Create test data
            test_data = {
                'user_interactions': [
                    {'user_id': self.test_user.id, 'offer_id': 1, 'rating': 5},
                    {'user_id': self.test_user.id, 'offer_id': 2, 'rating': 4}
                ],
                'timestamp': timezone.now().isoformat()
            }
            
            # Update model
            result = self.collab_service.update_collaborative_model(test_data)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['metadata']['interactions_processed'], 2)
            self.assertEqual(result['metadata']['model_updated'], True)
            
        except Exception as e:
            self.fail(f"Error in test_update_collaborative_model_basic: {e}")
    
    def test_calculate_pearson_correlation_basic(self):
        """Test basic Pearson correlation calculation."""
        try:
            # Test data
            user1_ratings = [5, 4, 3, 5, 4]
            user2_ratings = [4, 3, 4, 5, 3]
            
            # Calculate correlation
            correlation = self.collab_service.calculate_pearson_correlation(
                user1_ratings, user2_ratings
            )
            
            # Assertions
            self.assertIsInstance(correlation, dict)
            self.assertIn('correlation_coefficient', correlation)
            self.assertIn('p_value', correlation)
            
            # Verify correlation coefficient is reasonable
            self.assertGreaterEqual(correlation['correlation_coefficient'], -1.0)
            self.assertLessEqual(correlation['correlation_coefficient'], 1.0)
            
        except Exception as e:
            self.fail(f"Error in test_calculate_pearson_correlation_basic: {e}")
    
    def test_calculate_cosine_similarity_basic(self):
        """Test basic cosine similarity calculation."""
        try:
            # Test vectors
            vector1 = [1, 0, 1, 0, 1]
            vector2 = [0, 1, 1, 0, 0]
            
            # Calculate cosine similarity
            similarity = self.collab_service.calculate_cosine_similarity(vector1, vector2)
            
            # Assertions
            self.assertIsInstance(similarity, dict)
            self.assertIn('cosine_similarity', similarity)
            
            # Verify similarity is reasonable
            self.assertGreaterEqual(similarity['cosine_similarity'], 0.0)
            self.assertLessEqual(similarity['cosine_similarity'], 1.0)
            
        except Exception as e:
            self.fail(f"Error in test_calculate_cosine_similarity_basic: {e}")
    
    def test_health_check(self):
        """Test collaborative filter service health check."""
        try:
            # Test health check
            health = self.collab_service.health_check()
            
            # Assertions
            self.assertIsInstance(health, dict)
            self.assertIn('status', health)
            self.assertIn('timestamp', health)
            self.assertIn('model_status', health)
            self.assertIn('cache_status', health)
            self.assertIn('performance_stats', health)
            
        except Exception as e:
            self.fail(f"Error in test_health_check: {e}")
    
    def test_performance_under_load(self):
        """Test collaborative filter performance under load."""
        try:
            # Create many test users
            users = []
            for i in range(50):
                users.append(User.objects.create_user(
                    username=f'loaduser{i+1}',
                    email=f'loaduser{i+1}@example.com',
                    is_active=True
                ))
            
            # Create test interactions
            interactions = []
            for user in users:
                for j in range(10):
                    interactions.append({
                        'user_id': user.id,
                        'offer_id': j,
                        'rating': (j % 5) + 1
                    })
            
            # Measure performance
            start_time = timezone.now()
            result = self.collab_service.update_collaborative_model({
                'user_interactions': interactions,
                'timestamp': timezone.now().isoformat()
            })
            
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['metadata']['interactions_processed'], len(interactions))
            self.assertLess(elapsed_ms, 5000)  # Should complete in under 5 seconds
            
        except Exception as e:
            self.fail(f"Error in test_performance_under_load: {e}")


if __name__ == '__main__':
    pytest.main()
