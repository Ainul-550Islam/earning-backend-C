"""
Test Content Based

Tests for the content-based personalization service
to ensure it works correctly.
"""

import logging
import pytest
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch
from ..services.personalization import ContentBasedService
from ..models import OfferRoute, UserOfferHistory, OfferAffinityScore
from ..constants import DEFAULT_ROUTING_LIMIT

logger = logging.getLogger(__name__)

User = get_user_model()


class TestContentBased(TestCase):
    """Test cases for ContentBasedService."""
    
    def setUp(self):
        """Set up test environment."""
        self.content_service = ContentBasedService()
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            is_active=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        User.objects.filter(id=self.test_user.id).delete()
    
    def test_calculate_content_similarity_basic(self):
        """Test basic content similarity calculation."""
        try:
            # Create test offers
            offer1 = OfferRoute.objects.create(
                name='Electronics Offer',
                description='Latest smartphone with advanced features',
                category='electronics',
                tags='["smartphone", "5G", "AI"]',
                price=999.99
            )
            offer2 = OfferRoute.objects.create(
                name='Fashion Offer',
                description='Trendy clothing for young adults',
                category='fashion',
                tags='["clothing", "trendy", "youth"]',
                price=49.99
            )
            
            # Calculate similarity
            similarity = self.content_service.calculate_content_similarity(offer1, offer2)
            
            # Assertions
            self.assertIsInstance(similarity, dict)
            self.assertIn('similarity_score', similarity)
            self.assertIn('name_similarity', similarity)
            self.assertIn('description_similarity', similarity)
            self.assertIn('category_similarity', similarity)
            self.assertIn('tag_similarity', similarity)
            
            # Verify similarity score is reasonable
            self.assertGreaterEqual(similarity['similarity_score'], 0.0)
            self.assertLessEqual(similarity['similarity_score'], 1.0)
            
        except Exception as e:
            self.fail(f"Error in test_calculate_content_similarity_basic: {e}")
    
    def test_calculate_content_similarity_identical(self):
        """Test content similarity with identical offers."""
        try:
            # Create identical offers
            offer1 = OfferRoute.objects.create(
                name='Same Offer',
                description='Same description',
                category='test',
                tags='["tag1", "tag2"]',
                price=100.0
            )
            offer2 = OfferRoute.objects.create(
                name='Same Offer',
                description='Same description',
                category='test',
                tags='["tag1", "tag2"]',
                price=100.0
            )
            
            # Calculate similarity
            similarity = self.content_service.calculate_content_similarity(offer1, offer2)
            
            # Should have high similarity
            self.assertGreaterEqual(similarity['similarity_score'], 0.9)
            self.assertEqual(similarity['name_similarity'], 1.0)
            self.assertEqual(similarity['description_similarity'], 1.0)
            self.assertEqual(similarity['category_similarity'], 1.0)
            self.assertEqual(similarity['tag_similarity'], 1.0)
            
        except Exception as e:
            self.fail(f"Error in test_calculate_content_similarity_identical: {e}")
    
    def test_calculate_content_similarity_different(self):
        """Test content similarity with different offers."""
        try:
            # Create very different offers
            offer1 = OfferRoute.objects.create(
                name='Electronics Offer',
                description='Computer hardware and accessories',
                category='electronics',
                tags='["computer", "hardware", "tech"]',
                price=999.99
            )
            offer2 = OfferRoute.objects.create(
                name='Food Offer',
                description='Restaurant dining experience',
                category='food',
                tags='["restaurant", "dining", "cuisine"]',
                price=50.0
            )
            
            # Calculate similarity
            similarity = self.content_service.calculate_content_similarity(offer1, offer2)
            
            # Should have low similarity
            self.assertLessEqual(similarity['similarity_score'], 0.3)
            self.assertLessEqual(similarity['name_similarity'], 0.2)
            self.assertLessEqual(similarity['description_similarity'], 0.2)
            self.assertEqual(similarity['category_similarity'], 0.0)
            self.assertEqual(similarity['tag_similarity'], 0.0)
            
        except Exception as e:
            self.fail(f"Error in test_calculate_content_similarity_different: {e}")
    
    def test_extract_features_basic(self):
        """Test basic feature extraction."""
        try:
            # Create test offer
            offer = OfferRoute.objects.create(
                name='Test Offer',
                description='Premium smartphone with 5G and AI features',
                category='electronics',
                tags='["smartphone", "5G", "AI", "premium"]',
                price=1299.99
            )
            
            # Extract features
            features = self.content_service.extract_features(offer)
            
            # Assertions
            self.assertIsInstance(features, dict)
            self.assertIn('name_features', features)
            self.assertIn('description_features', features)
            self.assertIn('category_features', features)
            self.assertIn('tag_features', features)
            self.assertIn('price_features', features)
            
            # Verify name features
            name_features = features['name_features']
            self.assertIn('word_count', name_features)
            self.assertIn('char_count', name_features)
            self.assertIn('avg_word_length', name_features)
            
            # Verify description features
            desc_features = features['description_features']
            self.assertIn('word_count', desc_features)
            self.assertIn('char_count', desc_features)
            self.assertIn('sentence_count', desc_features)
            
        except Exception as e:
            self.fail(f"Error in test_extract_features_basic: {e}")
    
    def test_calculate_tfidf_basic(self):
        """Test basic TF-IDF calculation."""
        try:
            # Create test documents
            documents = [
                'This is a test document about smartphones',
                'Another document about computer hardware',
                'Third document about mobile applications'
            ]
            
            # Calculate TF-IDF
            tfidf = self.content_service.calculate_tfidf(documents)
            
            # Assertions
            self.assertIsInstance(tfidf, dict)
            self.assertIn('vocabulary', tfidf)
            self.assertIn('idf_scores', tfidf)
            self.assertIn('tfidf_matrix', tfidf)
            
            # Verify vocabulary
            self.assertGreater(len(tfidf['vocabulary']), 0)
            self.assertIn('smartphone', tfidf['vocabulary'])
            self.assertIn('computer', tfidf['vocabulary'])
            
            # Verify IDF scores
            idf_scores = tfidf['idf_scores']
            self.assertIn('smartphone', idf_scores)
            self.assertIn('computer', idf_scores)
            
        except Exception as e:
            self.fail(f"Error in test_calculate_tfidf_basic: {e}")
    
    def test_get_content_based_recommendations_basic(self):
        """Test basic content-based recommendations."""
        try:
            # Create test offers
            offers = []
            for i in range(5):
                offers.append(OfferRoute.objects.create(
                    name=f'Offer {i+1}',
                    description=f'Test offer {i+1} description',
                    category=f'category{i%2+1}',
                    tags=[f'tag{i%2+1}', f'tag{i%2+2}'],
                    price=10.0 * (i+1)
                ))
            
            # Create test user history
            UserOfferHistory.objects.create(
                user=self.test_user,
                offer=offers[0],
                score_at_time=0.8,
                clicked_at=timezone.now() - timezone.timedelta(hours=1)
            )
            
            # Get recommendations
            result = self.content_service.get_content_based_recommendations(
                user_id=self.test_user.id,
                limit=3
            )
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(len(result['recommendations']), 3)
            self.assertEqual(result['metadata']['method'], 'content_based')
            self.assertEqual(result['metadata']['limit'], 3)
            
            # Verify recommendations have required fields
            for rec in result['recommendations']:
                self.assertIn('offer_id', rec)
                self.assertIn('similarity_score', rec)
                self.assertIn('similarity_reason', rec)
                
        except Exception as e:
            self.fail(f"Error in test_get_content_based_recommendations_basic: {e}")
    
    def test_get_content_based_recommendations_with_no_history(self):
        """Test content-based recommendations with no user history."""
        try:
            # Create test offers
            offers = []
            for i in range(3):
                offers.append(OfferRoute.objects.create(
                    name=f'Offer {i+1}',
                    description=f'Test offer {i+1} description',
                    category=f'category{i%2+1}',
                    tags=[f'tag{i%2+1}'],
                    price=10.0 * (i+1)
                ))
            
            # Get recommendations with no history
            result = self.content_service.get_content_based_recommendations(
                user_id=self.test_user.id,
                limit=3
            )
            
            # Should return recommendations based on content similarity
            self.assertTrue(result['success'])
            self.assertEqual(len(result['recommendations']), 3)
            self.assertEqual(result['metadata']['method'], 'content_based')
            
        except Exception as e:
            self.fail(f"Error in test_get_content_based_recommendations_with_no_history: {e}")
    
    def test_update_content_model_basic(self):
        """Test basic content model update."""
        try:
            # Create test data
            test_data = {
                'user_interactions': [
                    {'offer_id': 1, 'rating': 5, 'viewed_at': timezone.now()},
                    {'offer_id': 2, 'rating': 4, 'viewed_at': timezone.now() - timezone.timedelta(hours=1)}
                ],
                'timestamp': timezone.now().isoformat()
            }
            
            # Update content model
            result = self.content_service.update_content_model(test_data)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['metadata']['interactions_processed'], 2)
            self.assertEqual(result['metadata']['model_updated'], True)
            self.assertIn('model_version', result['metadata'])
            
        except Exception as e:
            self.fail(f"Error in test_update_content_model_basic: {e}")
    
    def test_calculate_content_profile_basic(self):
        """Test basic content profile calculation."""
        try:
            # Create test user history
            UserOfferHistory.objects.create(
                user=self.test_user,
                offer_id=1,
                score_at_time=0.8,
                clicked_at=timezone.now() - timezone.timedelta(hours=1)
            )
            UserOfferHistory.objects.create(
                user=self.test_user,
                offer_id=2,
                score_at_time=0.6,
                clicked_at=timezone.now() - timezone.timedelta(hours=2)
            )
            
            # Calculate content profile
            profile = self.content_service.calculate_content_profile(self.test_user.id)
            
            # Assertions
            self.assertIsInstance(profile, dict)
            self.assertIn('preferred_categories', profile)
            self.assertIn('preferred_tags', profile)
            self.assertIn('content_affinity_scores', profile)
            self.assertIn('profile_updated_at', profile)
            
            # Verify preferred categories
            preferred_cats = profile['preferred_categories']
            self.assertIsInstance(preferred_cats, dict)
            
        except Exception as e:
            self.fail(f"Error in test_calculate_content_profile_basic: {e}")
    
    def test_health_check(self):
        """Test content-based service health check."""
        try:
            # Test health check
            health = self.content_service.health_check()
            
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
        """Test content-based service performance under load."""
        try:
            # Create many test offers
            offers = []
            for i in range(50):
                offers.append(OfferRoute.objects.create(
                    name=f'Performance Test Offer {i+1}',
                    description=f'Performance test offer {i+1} description',
                    category=f'category{i%3+1}',
                    tags=[f'tag{i%3+1}', f'tag{i%3+2}', f'tag{i%3+3}'],
                    price=10.0 * (i+1)
                ))
            
            # Create test user history
            for i in range(10):
                UserOfferHistory.objects.create(
                    user=self.test_user,
                    offer=offers[i % len(offers)],
                    score_at_time=0.5 + (i * 0.05),
                    clicked_at=timezone.now() - timezone.timedelta(hours=i+1)
                )
            
            # Measure performance
            start_time = timezone.now()
            result = self.content_service.get_content_based_recommendations(
                user_id=self.test_user.id,
                limit=20
            )
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(len(result['recommendations']), 20)
            self.assertLess(elapsed_ms, 1000)  # Should complete in under 1 second
            
        except Exception as e:
            self.fail(f"Error in test_performance_under_load: {e}")


if __name__ == '__main__':
    pytest.main()
