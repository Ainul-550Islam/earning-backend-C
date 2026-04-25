"""
Personalization Tests for Offer Routing System

This module contains unit tests for personalization functionality,
including preference vectors, collaborative filtering, and affinity scoring.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Sum
from ..services.personalization import (
    PersonalizationService, personalization_service,
    CollaborativeFilterService, collaborative_service,
    ContentBasedService, content_based_service,
    AffinityService, affinity_service
)
from ..models import UserPreferenceVector, ContextualSignal, PersonalizationConfig, OfferAffinityScore
from ..exceptions import PersonalizationError, ValidationError

User = get_user_model()


class PersonalizationServiceTestCase(TestCase):
    """Test cases for PersonalizationService."""
    
    def setUp(self):
        """Set up test data."""
        self.personalization_service = PersonalizationService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
        
        # Create personalization config
        self.config = PersonalizationConfig.objects.create(
            tenant=self.tenant,
            user=self.user,
            algorithm='hybrid',
            collaborative_weight=0.4,
            content_based_weight=0.3,
            hybrid_weight=0.3,
            real_time_enabled=True,
            context_signals_enabled=True
        )
        
        # Create test offer route
        from ..models import OfferRoute
        self.offer_route = OfferRoute.objects.create(
            name='Test Route',
            description='Test route for unit testing',
            tenant=self.tenant,
            priority=5,
            max_offers=10,
            is_active=True
        )
    
    def test_is_enabled(self):
        """Test personalization enabled check."""
        is_enabled = self.personalization_service.is_enabled(self.user)
        
        self.assertTrue(is_enabled)
        
        # Test with disabled config
        self.config.is_active = False
        self.config.save()
        
        is_enabled = self.personalization_service.is_enabled(self.user)
        
        self.assertFalse(is_enabled)
    
    def test_is_enabled_no_config(self):
        """Test personalization enabled check without config."""
        # Delete config
        self.config.delete()
        
        is_enabled = self.personalization_service.is_enabled(self.user)
        
        self.assertFalse(is_enabled)
    
    def test_apply_personalization(self):
        """Test personalization application."""
        offers = [self.offer_route]
        score_data = {'score': 85.5}
        context = {'location': {'country': 'US'}}
        
        personalized_offers = self.personalization_service.apply_personalization(
            user=self.user,
            offers=offers,
            score_data=score_data,
            context=context
        )
        
        self.assertIsInstance(personalized_offers, list)
        self.assertEqual(len(personalized_offers), len(offers))
        
        # Check if personalization was applied
        for offer in personalized_offers:
            self.assertIn('personalized_score', offer)
    
    def test_apply_personalization_disabled(self):
        """Test personalization application when disabled."""
        # Disable personalization
        self.config.is_active = False
        self.config.save()
        
        offers = [self.offer_route]
        score_data = {'score': 85.5}
        context = {'location': {'country': 'US'}}
        
        personalized_offers = self.personalization_service.apply_personalization(
            user=self.user,
            offers=offers,
            score_data=score_data,
            context=context
        )
        
        self.assertIsInstance(personalized_offers, list)
        self.assertEqual(len(personalized_offers), len(offers))
        
        # Should return original scores
        for offer in personalized_offers:
            self.assertEqual(offer['score'], score_data['score'])
    
    def test_update_user_preferences(self):
        """Test user preference update."""
        interaction_data = [
            {
                'offer_id': self.offer_route.id,
                'interaction_type': 'view',
                'timestamp': timezone.now().isoformat(),
                'value': 1.0
            }
        ]
        
        success = self.personalization_service.update_user_preferences(
            user=self.user,
            interaction_data=interaction_data
        )
        
        self.assertTrue(success)
        
        # Check if preference vector was created/updated
        preference_vector = UserPreferenceVector.objects.filter(user=self.user).first()
        self.assertIsNotNone(preference_vector)
    
    def test_update_user_preferences_no_data(self):
        """Test user preference update with no data."""
        success = self.personalization_service.update_user_preferences(
            user=self.user,
            interaction_data=[]
        )
        
        self.assertFalse(success)
    
    def test_get_personalization_config(self):
        """Test getting personalization config."""
        config = self.personalization_service.get_personalization_config(self.user.id)
        
        self.assertIsNotNone(config)
        self.assertEqual(config['algorithm'], 'hybrid')
        self.assertEqual(config['collaborative_weight'], 0.4)
    
    def test_get_personalization_config_no_config(self):
        """Test getting personalization config without config."""
        # Delete config
        self.config.delete()
        
        config = self.personalization_service.get_personalization_config(self.user.id)
        
        self.assertIsNone(config)
    
    def test_update_personalization_config(self):
        """Test updating personalization config."""
        config_data = {
            'algorithm': 'collaborative',
            'collaborative_weight': 0.6,
            'content_based_weight': 0.4,
            'real_time_enabled': False
        }
        
        success = self.personalization_service.update_personalization_config(
            user_id=self.user.id,
            config_data=config_data
        )
        
        self.assertTrue(success)
        
        # Check if config was updated
        updated_config = PersonalizationService.get_personalization_config(self.user.id)
        self.assertEqual(updated_config['algorithm'], 'collaborative')
        self.assertEqual(updated_config['collaborative_weight'], 0.6)
    
    def test_process_contextual_signal(self):
        """Test contextual signal processing."""
        # Create contextual signal
        signal = ContextualSignal.objects.create(
            user=self.user,
            signal_type='time',
            value='morning',
            expires_at=timezone.now() + timezone.timedelta(hours=1)
        )
        
        success = self.personalization_service.process_contextual_signal(signal)
        
        self.assertTrue(success)
    
    def test_train_ml_model(self):
        """Test ML model training."""
        # Enable ML in config
        self.config.machine_learning_enabled = True
        self.config.save()
        
        success = self.personalization_service.train_ml_model(self.user.id)
        
        # Should return True (mock implementation)
        self.assertTrue(success)
    
    def test_update_real_time_personalization(self):
        """Test real-time personalization update."""
        # Enable real-time personalization
        self.config.real_time_enabled = True
        self.config.save()
        
        success = self.personalization_service.update_real_time_personalization(self.user.id)
        
        self.assertTrue(success)
    
    def test_get_effective_weights(self):
        """Test getting effective weights."""
        weights = self.config.get_effective_weights()
        
        self.assertIsInstance(weights, dict)
        self.assertIn('collaborative_weight', weights)
        self.assertIn('content_based_weight', weights)
        self.assertIn('hybrid_weight', weights)
        
        # Weights should sum to 1.0
        total_weight = sum(weights.values())
        self.assertAlmostEqual(total_weight, 1.0, places=2)


class CollaborativeFilterServiceTestCase(TestCase):
    """Test cases for CollaborativeFilterService."""
    
    def setUp(self):
        """Set up test data."""
        self.collaborative_service = CollaborativeFilterService()
        
        # Create test users
        self.users = []
        for i in range(3):
            user = User.objects.create_user(
                username=f'user{i}',
                email=f'user{i}@example.com',
                password='testpass123'
            )
            self.users.append(user)
        
        # Create test offers
        from ..models import OfferRoute
        self.offers = []
        for i in range(3):
            offer = OfferRoute.objects.create(
                name=f'Test Route {i}',
                description=f'Test route {i} for unit testing',
                tenant=self.users[0],
                priority=i + 1,
                max_offers=10,
                is_active=True
            )
            self.offers.append(offer)
    
    def test_get_similar_users(self):
        """Test getting similar users."""
        similar_users = self.collaborative_service.get_similar_users(
            user=self.users[0],
            limit=5
        )
        
        self.assertIsInstance(similar_users, list)
        self.assertLessEqual(len(similar_users), 5)
        
        # Each result should be a tuple of (user, similarity)
        for result in similar_users:
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 2)
            self.assertIsInstance(result[0], User)
            self.assertIsInstance(result[1], (int, float))
    
    def test_get_user_similarity(self):
        """Test user similarity calculation."""
        similarity = self.collaborative_service.get_user_similarity(
            self.users[0],
            self.users[1]
        )
        
        self.assertIsInstance(similarity, (int, float))
        self.assertGreaterEqual(similarity, -1)
        self.assertLessEqual(similarity, 1)
    
    def test_update_user_similarity_matrix(self):
        """Test user similarity matrix update."""
        updated_count = self.collaborative_service.update_user_similarity_matrix()
        
        self.assertIsInstance(updated_count, int)
        self.assertGreaterEqual(updated_count, 0)
    
    def test_get_collaborative_recommendations(self):
        """Test getting collaborative recommendations."""
        recommendations = self.collaborative_service.get_collaborative_recommendations(
            user=self.users[0],
            limit=5
        )
        
        self.assertIsInstance(recommendations, list)
        self.assertLessEqual(len(recommendations), 5)
        
        # Each recommendation should have offer_id and score
        for rec in recommendations:
            self.assertIn('offer_id', rec)
            self.assertIn('score', rec)
    
    def test_update_collaborative_recommendations(self):
        """Test updating collaborative recommendations."""
        updated_count = self.collaborative_service.update_collaborative_recommendations()
        
        self.assertIsInstance(updated_count, int)
        self.assertGreaterEqual(updated_count, 0)
    
    def test_calculate_user_item_matrix(self):
        """Test user-item matrix calculation."""
        matrix = self.collaborative_service._calculate_user_item_matrix()
        
        self.assertIsInstance(matrix, dict)
        # Matrix should contain user IDs as keys
        for user_id in matrix:
            self.assertIsInstance(user_id, int)
            self.assertIsInstance(matrix[user_id], dict)
    
    def test_calculate_cosine_similarity(self):
        """Test cosine similarity calculation."""
        vector1 = {'offer1': 1.0, 'offer2': 0.5, 'offer3': 0.0}
        vector2 = {'offer1': 0.8, 'offer2': 0.6, 'offer3': 0.2}
        
        similarity = self.collaborative_service._calculate_cosine_similarity(
            vector1, vector2
        )
        
        self.assertIsInstance(similarity, (int, float))
        self.assertGreaterEqual(similarity, -1)
        self.assertLessEqual(similarity, 1)
    
    def test_get_user_interactions(self):
        """Test getting user interactions."""
        interactions = self.collaborative_service._get_user_interactions(self.users[0])
        
        self.assertIsInstance(interactions, list)
        # Each interaction should be a dict
        for interaction in interactions:
            self.assertIsInstance(interaction, dict)


class ContentBasedServiceTestCase(TestCase):
    """Test cases for ContentBasedService."""
    
    def setUp(self):
        """Set up test data."""
        self.content_based_service = ContentBasedService()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test offers
        from ..models import OfferRoute
        self.offers = []
        for i in range(3):
            offer = OfferRoute.objects.create(
                name=f'Test Route {i}',
                description=f'Test route {i} for unit testing',
                tenant=self.user,
                priority=i + 1,
                max_offers=10,
                is_active=True
            )
            self.offers.append(offer)
    
    def test_analyze_offer_content(self):
        """Test offer content analysis."""
        analyzed_count = self.content_based_service.analyze_offer_content()
        
        self.assertIsInstance(analyzed_count, int)
        self.assertGreaterEqual(analyzed_count, 0)
    
    def test_get_content_based_recommendations(self):
        """Test getting content-based recommendations."""
        recommendations = self.content_based_service.get_content_based_recommendations(
            user=self.user,
            limit=5
        )
        
        self.assertIsInstance(recommendations, list)
        self.assertLessEqual(len(recommendations), 5)
        
        # Each recommendation should have offer_id and score
        for rec in recommendations:
            self.assertIn('offer_id', rec)
            self.assertIn('score', rec)
    
    def test_update_content_based_recommendations(self):
        """Test updating content-based recommendations."""
        updated_count = self.content_based_service.update_content_based_recommendations()
        
        self.assertIsInstance(updated_count, int)
        self.assertGreaterEqual(updated_count, 0)
    
    def test_rebuild_preference_vectors(self):
        """Test preference vector rebuilding."""
        rebuilt_count = self.content_based_service.rebuild_preference_vectors()
        
        self.assertIsInstance(rebuilt_count, int)
        self.assertGreaterEqual(rebuilt_count, 0)
    
    def test_extract_offer_features(self):
        """Test offer feature extraction."""
        features = self.content_based_service._extract_offer_features(self.offers[0])
        
        self.assertIsInstance(features, dict)
        # Should contain common features
        expected_features = ['title', 'description', 'categories']
        for feature in expected_features:
            self.assertIn(feature, features)
    
    def test_calculate_content_similarity(self):
        """Test content similarity calculation."""
        features1 = {'title': 'Test Offer', 'categories': ['tech', 'finance']}
        features2 = {'title': 'Test Product', 'categories': ['tech', 'shopping']}
        
        similarity = self.content_based_service._calculate_content_similarity(
            features1, features2
        )
        
        self.assertIsInstance(similarity, (int, float))
        self.assertGreaterEqual(similarity, 0)
        self.assertLessEqual(similarity, 1)
    
    def test_get_offer_content_vector(self):
        """Test getting offer content vector."""
        vector = self.content_based_service._get_offer_content_vector(self.offers[0])
        
        self.assertIsInstance(vector, dict)
        # Vector should contain numeric values
        for key, value in vector.items():
            self.assertIsInstance(value, (int, float))


class AffinityServiceTestCase(TestCase):
    """Test cases for AffinityService."""
    
    def setUp(self):
        """Set up test data."""
        self.affinity_service = AffinityService()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test offers
        from ..models import OfferRoute
        self.offers = []
        for i in range(3):
            offer = OfferRoute.objects.create(
                name=f'Test Route {i}',
                description=f'Test route {i} for unit testing',
                tenant=self.user,
                priority=i + 1,
                max_offers=10,
                is_active=True
            )
            self.offers.append(offer)
    
    def test_update_affinity_score(self):
        """Test affinity score update."""
        success = self.affinity_service.update_affinity_score(
            user_id=self.user.id,
            category='test_category',
            score=0.8,
            confidence=0.9
        )
        
        self.assertTrue(success)
        
        # Check if affinity score was created
        affinity_score = OfferAffinityScore.objects.filter(
            user=self.user,
            category='test_category'
        ).first()
        
        self.assertIsNotNone(affinity_score)
        self.assertEqual(affinity_score.score, 0.8)
        self.assertEqual(affinity_score.confidence, 0.9)
    
    def test_get_affinity_score(self):
        """Test getting affinity score."""
        # Create affinity score
        OfferAffinityScore.objects.create(
            user=self.user,
            category='test_category',
            score=0.75,
            confidence=0.8
        )
        
        affinity_score = self.affinity_service.get_affinity_score(
            user_id=self.user.id,
            category='test_category'
        )
        
        self.assertIsNotNone(affinity_score)
        self.assertEqual(affinity_score.score, 0.75)
    
    def test_get_affinity_score_not_found(self):
        """Test getting non-existent affinity score."""
        affinity_score = self.affinity_service.get_affinity_score(
            user_id=self.user.id,
            category='nonexistent_category'
        )
        
        self.assertIsNone(affinity_score)
    
    def test_update_user_affinity_scores(self):
        """Test updating user affinity scores."""
        updated_count = self.affinity_service.update_user_affinity_scores(self.user.id)
        
        self.assertIsInstance(updated_count, int)
        self.assertGreaterEqual(updated_count, 0)
    
    def test_get_user_affinity_scores(self):
        """Test getting user affinity scores."""
        # Create some affinity scores
        categories = ['tech', 'finance', 'shopping']
        for category in categories:
            OfferAffinityScore.objects.create(
                user=self.user,
                category=category,
                score=0.5,
                confidence=0.7
            )
        
        affinity_scores = self.affinity_service.get_user_affinity_scores(self.user.id)
        
        self.assertIsInstance(affinity_scores, list)
        self.assertEqual(len(affinity_scores), len(categories))
        
        # Each score should have category, score, and confidence
        for score in affinity_scores:
            self.assertIn('category', score)
            self.assertIn('score', score)
            self.assertIn('confidence', score)
    
    def test_calculate_affinity_from_interactions(self):
        """Test affinity calculation from interactions."""
        # Create user interactions
        from ..models import UserOfferHistory
        UserOfferHistory.objects.create(
            user=self.user,
            offer=self.offers[0],
            route=self.offers[0],
            viewed_at=timezone.now(),
            clicked_at=timezone.now(),
            completed_at=timezone.now()
        )
        
        affinity = self.affinity_service._calculate_affinity_from_interactions(
            self.user, 'test_category'
        )
        
        self.assertIsInstance(affinity, (int, float))
        self.assertGreaterEqual(affinity, 0)
        self.assertLessEqual(affinity, 1)
    
    def test_decay_affinity_scores(self):
        """Test affinity score decay."""
        # Create old affinity score
        old_date = timezone.now() - timezone.timedelta(days=30)
        OfferAffinityScore.objects.create(
            user=self.user,
            category='old_category',
            score=0.9,
            confidence=0.8,
            created_at=old_date
        )
        
        decayed_count = self.affinity_service.decay_affinity_scores(decay_factor=0.9)
        
        self.assertIsInstance(decayed_count, int)
        self.assertGreaterEqual(decayed_count, 0)
    
    def test_cleanup_low_confidence_scores(self):
        """Test cleanup of low confidence scores."""
        # Create low confidence score
        OfferAffinityScore.objects.create(
            user=self.user,
            category='low_confidence',
            score=0.5,
            confidence=0.1  # Low confidence
        )
        
        deleted_count = self.affinity_service.cleanup_low_confidence_scores(
            min_confidence=0.5
        )
        
        self.assertIsInstance(deleted_count, int)
        self.assertGreaterEqual(deleted_count, 0)


class PersonalizationIntegrationTestCase(TestCase):
    """Integration tests for personalization functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test offers
        from ..models import OfferRoute
        self.offers = []
        for i in range(3):
            offer = OfferRoute.objects.create(
                name=f'Test Route {i}',
                description=f'Test route {i} for integration testing',
                tenant=self.user,
                priority=i + 1,
                max_offers=10,
                is_active=True
            )
            self.offers.append(offer)
    
    def test_personalization_workflow(self):
        """Test complete personalization workflow."""
        # Create personalization config
        config = PersonalizationConfig.objects.create(
            tenant=self.user,
            user=self.user,
            algorithm='hybrid',
            collaborative_weight=0.4,
            content_based_weight=0.3,
            hybrid_weight=0.3,
            real_time_enabled=True,
            context_signals_enabled=True
        )
        
        # Update user preferences
        interaction_data = [
            {
                'offer_id': self.offers[0].id,
                'interaction_type': 'view',
                'timestamp': timezone.now().isoformat(),
                'value': 1.0
            }
        ]
        
        success = personalization_service.update_user_preferences(
            user=self.user,
            interaction_data=interaction_data
        )
        
        self.assertTrue(success)
        
        # Apply personalization
        score_data = {'score': 85.5}
        context = {'location': {'country': 'US'}}
        
        personalized_offers = personalization_service.apply_personalization(
            user=self.user,
            offers=self.offers,
            score_data=score_data,
            context=context
        )
        
        self.assertIsInstance(personalized_offers, list)
        self.assertEqual(len(personalized_offers), len(self.offers))
        
        # Check if personalization was applied
        for offer in personalized_offers:
            self.assertIn('personalized_score', offer)
    
    def test_collaborative_filtering_integration(self):
        """Test collaborative filtering integration."""
        # Create multiple users and interactions
        other_users = []
        for i in range(2):
            user = User.objects.create_user(
                username=f'otheruser{i}',
                email=f'otheruser{i}@example.com',
                password='testpass123'
            )
            other_users.append(user)
        
        # Update similarity matrix
        updated_count = collaborative_service.update_user_similarity_matrix()
        
        self.assertIsInstance(updated_count, int)
        self.assertGreaterEqual(updated_count, 0)
        
        # Get collaborative recommendations
        recommendations = collaborative_service.get_collaborative_recommendations(
            user=self.user,
            limit=3
        )
        
        self.assertIsInstance(recommendations, list)
        self.assertLessEqual(len(recommendations), 3)
    
    def test_content_based_integration(self):
        """Test content-based filtering integration."""
        # Analyze offer content
        analyzed_count = content_based_service.analyze_offer_content()
        
        self.assertIsInstance(analyzed_count, int)
        self.assertGreaterEqual(analyzed_count, 0)
        
        # Rebuild preference vectors
        rebuilt_count = content_based_service.rebuild_preference_vectors()
        
        self.assertIsInstance(rebuilt_count, int)
        self.assertGreaterEqual(rebuilt_count, 0)
        
        # Get content-based recommendations
        recommendations = content_based_service.get_content_based_recommendations(
            user=self.user,
            limit=3
        )
        
        self.assertIsInstance(recommendations, list)
        self.assertLessEqual(len(recommendations), 3)
    
    def test_affinity_scoring_integration(self):
        """Test affinity scoring integration."""
        # Update affinity scores
        categories = ['tech', 'finance', 'shopping']
        for i, category in enumerate(categories):
            affinity_service.update_affinity_score(
                user_id=self.user.id,
                category=category,
                score=0.5 + (i * 0.1),
                confidence=0.8
            )
        
        # Get user affinity scores
        affinity_scores = affinity_service.get_user_affinity_scores(self.user.id)
        
        self.assertIsInstance(affinity_scores, list)
        self.assertEqual(len(affinity_scores), len(categories))
        
        # Update all user affinity scores
        updated_count = affinity_service.update_user_affinity_scores(self.user.id)
        
        self.assertIsInstance(updated_count, int)
        self.assertGreaterEqual(updated_count, 0)
    
    def test_personalization_performance(self):
        """Test personalization performance."""
        import time
        
        # Create config
        config = PersonalizationConfig.objects.create(
            tenant=self.user,
            user=self.user,
            algorithm='hybrid',
            collaborative_weight=0.4,
            content_based_weight=0.3,
            hybrid_weight=0.3
        )
        
        # Measure personalization time
        start_time = time.time()
        
        score_data = {'score': 85.5}
        context = {'location': {'country': 'US'}}
        
        personalized_offers = personalization_service.apply_personalization(
            user=self.user,
            offers=self.offers,
            score_data=score_data,
            context=context
        )
        
        end_time = time.time()
        personalization_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within reasonable time
        self.assertLess(personalization_time, 500)  # Within 500ms
    
    def test_error_handling(self):
        """Test error handling in personalization."""
        # Test with invalid user
        with self.assertRaises(Exception):
            personalization_service.apply_personalization(
                user=None,
                offers=self.offers,
                score_data={'score': 85.5},
                context={}
            )
        
        # Test with invalid offers
        with self.assertRaises(Exception):
            personalization_service.apply_personalization(
                user=self.user,
                offers=None,
                score_data={'score': 85.5},
                context={}
            )
