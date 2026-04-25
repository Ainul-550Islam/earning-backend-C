"""
Scoring Tests for Offer Routing System

This module contains unit tests for scoring functionality,
including offer scoring, ranking, and score optimization.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Sum, Max, Min
from ..services.scoring import OfferScoringService, scoring_service, OfferRankerService, ranker_service
from ..models import OfferScore, OfferScoreConfig, GlobalOfferRank, UserOfferHistory
from ..exceptions import ScoringError, ValidationError

User = get_user_model()


class OfferScoringServiceTestCase(TestCase):
    """Test cases for OfferScoringService."""
    
    def setUp(self):
        """Set up test data."""
        self.scoring_service = OfferScoringService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
        
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
        
        # Create offer score config
        self.score_config = OfferScoreConfig.objects.create(
            tenant=self.tenant,
            offer=self.offer_route,
            epc_weight=0.4,
            cr_weight=0.3,
            relevance_weight=0.2,
            freshness_weight=0.1
        )
    
    def test_calculate_offer_score(self):
        """Test offer score calculation."""
        context = {'location': {'country': 'US'}}
        
        score_data = self.scoring_service.calculate_offer_score(
            offer=self.offer_route,
            user=self.user,
            context=context
        )
        
        self.assertIsInstance(score_data, dict)
        self.assertIn('score', score_data)
        self.assertIn('epc', score_data)
        self.assertIn('cr', score_data)
        self.assertIn('relevance', score_data)
        self.assertIn('freshness', score_data)
        self.assertIsInstance(score_data['score'], (int, float))
        self.assertGreaterEqual(score_data['score'], 0)
        self.assertLessEqual(score_data['score'], 100)
    
    def test_calculate_offer_score_with_history(self):
        """Test offer score calculation with user history."""
        # Create user offer history
        UserOfferHistory.objects.create(
            user=self.user,
            offer=self.offer_route,
            route=self.offer_route,
            viewed_at=timezone.now(),
            clicked_at=timezone.now()
        )
        
        context = {'location': {'country': 'US'}}
        
        score_data = self.scoring_service.calculate_offer_score(
            offer=self.offer_route,
            user=self.user,
            context=context
        )
        
        self.assertIsInstance(score_data, dict)
        self.assertIn('score', score_data)
        # Score should be higher due to previous interactions
        self.assertGreater(score_data['score'], 50)
    
    def test_calculate_offer_score_no_config(self):
        """Test score calculation without config."""
        # Delete the config
        self.score_config.delete()
        
        context = {'location': {'country': 'US'}}
        
        score_data = self.scoring_service.calculate_offer_score(
            offer=self.offer_route,
            user=self.user,
            context=context
        )
        
        self.assertIsInstance(score_data, dict)
        self.assertIn('score', score_data)
        # Should use default weights
        self.assertGreaterEqual(score_data['score'], 0)
    
    def test_update_offer_score(self):
        """Test updating offer score."""
        score_data = self.scoring_service.update_offer_score(self.offer_route)
        
        self.assertIsInstance(score_data, dict)
        self.assertIn('score', score_data)
        
        # Check if score was saved
        saved_score = OfferScore.objects.filter(
            offer=self.offer_route
        ).first()
        
        self.assertIsNotNone(saved_score)
        self.assertEqual(saved_score.score, score_data['score'])
    
    def test_update_all_scores(self):
        """Test updating all offer scores."""
        # Create another offer
        from ..models import OfferRoute
        another_offer = OfferRoute.objects.create(
            name='Another Route',
            description='Another test route',
            tenant=self.tenant,
            priority=3,
            max_offers=5,
            is_active=True
        )
        
        updated_count = self.scoring_service.update_all_scores()
        
        self.assertGreaterEqual(updated_count, 2)  # Should update both offers
        
        # Check if scores were created
        scores = OfferScore.objects.all()
        self.assertGreaterEqual(scores.count(), 2)
    
    def test_get_offer_score(self):
        """Test getting offer score."""
        # Create a score record
        OfferScore.objects.create(
            offer=self.offer_route,
            user=self.user,
            score=85.5,
            epc=2.5,
            cr=3.2,
            relevance=0.8,
            freshness=0.9
        )
        
        score_data = self.scoring_service.get_offer_score(
            offer_id=self.offer_route.id,
            user_id=self.user.id
        )
        
        self.assertIsNotNone(score_data)
        self.assertEqual(score_data['score'], 85.5)
    
    def test_get_offer_score_not_found(self):
        """Test getting non-existent offer score."""
        score_data = self.scoring_service.get_offer_score(
            offer_id=999999,
            user_id=self.user.id
        )
        
        self.assertIsNone(score_data)
    
    def test_delete_offer_scores(self):
        """Test deleting offer scores."""
        # Create score records
        OfferScore.objects.create(
            offer=self.offer_route,
            user=self.user,
            score=85.5
        )
        
        deleted_count = self.scoring_service.delete_offer_scores(self.offer_route.id)
        
        self.assertGreaterEqual(deleted_count, 1)
        
        # Check if scores were deleted
        remaining_scores = OfferScore.objects.filter(offer=self.offer_route)
        self.assertEqual(remaining_scores.count(), 0)
    
    def test_calculate_epc(self):
        """Test EPC calculation."""
        # Create user history with conversions
        for i in range(10):
            UserOfferHistory.objects.create(
                user=self.user,
                offer=self.offer_route,
                route=self.offer_route,
                clicked_at=timezone.now(),
                completed_at=timezone.now(),
                conversion_value=10.0
            )
        
        epc = self.scoring_service._calculate_epc(self.offer_route, self.user)
        
        self.assertIsInstance(epc, (int, float))
        self.assertGreaterEqual(epc, 0)
        # Should be 10.0 (10 conversions * $10 value / 10 clicks)
        self.assertEqual(epc, 10.0)
    
    def test_calculate_cr(self):
        """Test conversion rate calculation."""
        # Create user history
        for i in range(10):
            UserOfferHistory.objects.create(
                user=self.user,
                offer=self.offer_route,
                route=self.offer_route,
                viewed_at=timezone.now(),
                clicked_at=timezone.now()
            )
        
        # Add some conversions
        for i in range(3):
            UserOfferHistory.objects.create(
                user=self.user,
                offer=self.offer_route,
                route=self.offer_route,
                viewed_at=timezone.now(),
                clicked_at=timezone.now(),
                completed_at=timezone.now()
            )
        
        cr = self.scoring_service._calculate_cr(self.offer_route, self.user)
        
        self.assertIsInstance(cr, (int, float))
        self.assertGreaterEqual(cr, 0)
        self.assertLessEqual(cr, 100)
    
    def test_calculate_relevance(self):
        """Test relevance calculation."""
        context = {'location': {'country': 'US'}}
        
        relevance = self.scoring_service._calculate_relevance(
            self.offer_route, self.user, context
        )
        
        self.assertIsInstance(relevance, (int, float))
        self.assertGreaterEqual(relevance, 0)
        self.assertLessEqual(relevance, 1)
    
    def test_calculate_freshness(self):
        """Test freshness calculation."""
        freshness = self.scoring_service._calculate_freshness(self.offer_route)
        
        self.assertIsInstance(freshness, (int, float))
        self.assertGreaterEqual(freshness, 0)
        self.assertLessEqual(freshness, 1)
    
    def test_normalize_score(self):
        """Test score normalization."""
        score = 150.0  # Above 100
        min_val = 0
        max_val = 100
        
        normalized = self.scoring_service._normalize_score(score, min_val, max_val)
        
        self.assertEqual(normalized, 100.0)
        
        # Test below minimum
        score = -10.0
        normalized = self.scoring_service._normalize_score(score, min_val, max_val)
        
        self.assertEqual(normalized, 0.0)
    
    def test_get_score_weights(self):
        """Test getting score weights."""
        weights = self.scoring_service._get_score_weights(self.offer_route)
        
        self.assertIsInstance(weights, dict)
        self.assertIn('epc_weight', weights)
        self.assertIn('cr_weight', weights)
        self.assertIn('relevance_weight', weights)
        self.assertIn('freshness_weight', weights)
        
        # Weights should sum to 1.0
        total_weight = sum(weights.values())
        self.assertAlmostEqual(total_weight, 1.0, places=2)


class OfferRankerServiceTestCase(TestCase):
    """Test cases for OfferRankerService."""
    
    def setUp(self):
        """Set up test data."""
        self.ranker_service = OfferRankerService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
        
        # Create test offer routes
        from ..models import OfferRoute
        self.offers = []
        for i in range(5):
            offer = OfferRoute.objects.create(
                name=f'Test Route {i}',
                description=f'Test route {i} for unit testing',
                tenant=self.tenant,
                priority=i + 1,
                max_offers=10,
                is_active=True
            )
            self.offers.append(offer)
    
    def test_rank_offers(self):
        """Test offer ranking."""
        # Create scored offers
        scored_offers = []
        for i, offer in enumerate(self.offers):
            scored_offers.append({
                'offer': offer,
                'score': 100 - (i * 10)  # Decreasing scores
            })
        
        ranked_offers = self.ranker_service.rank_offers(scored_offers)
        
        self.assertIsInstance(ranked_offers, list)
        self.assertEqual(len(ranked_offers), len(scored_offers))
        
        # Check if offers are ranked by score (descending)
        for i in range(len(ranked_offers) - 1):
            self.assertGreaterEqual(
                ranked_offers[i]['score'],
                ranked_offers[i + 1]['score']
            )
    
    def test_rank_offers_with_ties(self):
        """Test offer ranking with tied scores."""
        # Create scored offers with same scores
        scored_offers = []
        for offer in self.offers:
            scored_offers.append({
                'offer': offer,
                'score': 85.5  # Same score for all
            })
        
        ranked_offers = self.ranker_service.rank_offers(scored_offers)
        
        self.assertIsInstance(ranked_offers, list)
        self.assertEqual(len(ranked_offers), len(scored_offers))
        
        # All scores should be the same
        scores = [offer['score'] for offer in ranked_offers]
        self.assertTrue(all(score == 85.5 for score in scores))
    
    def test_rank_offers_empty_list(self):
        """Test ranking empty offer list."""
        ranked_offers = self.ranker_service.rank_offers([])
        
        self.assertIsInstance(ranked_offers, list)
        self.assertEqual(len(ranked_offers), 0)
    
    def test_get_top_offers(self):
        """Test getting top offers."""
        # Create global rankings
        for i, offer in enumerate(self.offers):
            GlobalOfferRank.objects.create(
                offer=offer,
                tenant=self.tenant,
                rank_score=100 - (i * 10),
                rank_date=timezone.now().date()
            )
        
        top_offers = self.ranker_service.get_top_offers(limit=3)
        
        self.assertIsInstance(top_offers, list)
        self.assertLessEqual(len(top_offers), 3)
        
        # Check if offers are ranked by score (descending)
        for i in range(len(top_offers) - 1):
            self.assertGreaterEqual(
                top_offers[i].rank_score,
                top_offers[i + 1].rank_score
            )
    
    def test_update_global_rankings(self):
        """Test updating global rankings."""
        # Create some offer scores
        for i, offer in enumerate(self.offers):
            OfferScore.objects.create(
                offer=offer,
                user=self.user,
                score=100 - (i * 10)
            )
        
        updated_count = self.ranker_service.update_global_rankings()
        
        self.assertGreaterEqual(updated_count, len(self.offers))
        
        # Check if global rankings were created
        rankings = GlobalOfferRank.objects.all()
        self.assertGreaterEqual(rankings.count(), len(self.offers))
    
    def test_get_offer_rank(self):
        """Test getting offer rank."""
        # Create global rankings
        for i, offer in enumerate(self.offers):
            GlobalOfferRank.objects.create(
                offer=offer,
                tenant=self.tenant,
                rank_score=100 - (i * 10),
                rank_date=timezone.now().date()
            )
        
        # Get rank for first offer
        rank = self.ranker_service.get_offer_rank(self.offers[0].id)
        
        self.assertIsInstance(rank, dict)
        self.assertIn('rank', rank)
        self.assertIn('score', rank)
        self.assertEqual(rank['rank'], 1)  # Should be ranked #1
    
    def test_get_offer_rank_not_found(self):
        """Test getting rank for non-existent offer."""
        rank = self.ranker_service.get_offer_rank(999999)
        
        self.assertIsNone(rank)
    
    def test_calculate_rank_score(self):
        """Test rank score calculation."""
        # Create multiple scores for an offer
        scores = [95.0, 85.0, 90.0, 88.0, 92.0]
        
        for score in scores:
            OfferScore.objects.create(
                offer=self.offers[0],
                user=self.user,
                score=score
            )
        
        rank_score = self.ranker_service._calculate_rank_score(self.offers[0])
        
        self.assertIsInstance(rank_score, (int, float))
        # Should be close to the average of scores
        expected_avg = sum(scores) / len(scores)
        self.assertAlmostEqual(rank_score, expected_avg, places=2)
    
    def test_get_ranking_history(self):
        """Test getting ranking history."""
        # Create historical rankings
        for i in range(5):
            GlobalOfferRank.objects.create(
                offer=self.offers[0],
                tenant=self.tenant,
                rank_score=100 - i,
                rank_date=timezone.now().date() - timezone.timedelta(days=i)
            )
        
        history = self.ranker_service.get_ranking_history(self.offers[0].id, days=7)
        
        self.assertIsInstance(history, list)
        self.assertLessEqual(len(history), 5)
        
        # Check if history is ordered by date
        for i in range(len(history) - 1):
            self.assertLessEqual(
                history[i]['rank_date'],
                history[i + 1]['rank_date']
            )
    
    def test_cleanup_old_rankings(self):
        """Test cleanup of old rankings."""
        # Create old rankings
        old_date = timezone.now().date() - timezone.timedelta(days=100)
        GlobalOfferRank.objects.create(
            offer=self.offers[0],
            tenant=self.tenant,
            rank_score=85.0,
            rank_date=old_date
        )
        
        # Create recent rankings
        GlobalOfferRank.objects.create(
            offer=self.offers[1],
            tenant=self.tenant,
            rank_score=90.0,
            rank_date=timezone.now().date()
        )
        
        deleted_count = self.ranker_service.cleanup_old_rankings(days=30)
        
        self.assertGreaterEqual(deleted_count, 1)
        
        # Check if old rankings were deleted
        remaining_rankings = GlobalOfferRank.objects.all()
        self.assertEqual(remaining_rankings.count(), 1)


class ScoringIntegrationTestCase(TestCase):
    """Integration tests for scoring functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test offer routes
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
    
    def test_scoring_workflow(self):
        """Test complete scoring workflow."""
        # Update scores for all offers
        updated_count = scoring_service.update_all_scores()
        
        self.assertGreaterEqual(updated_count, len(self.offers))
        
        # Check if scores were created
        scores = OfferScore.objects.all()
        self.assertGreaterEqual(scores.count(), len(self.offers))
        
        # Update global rankings
        ranking_count = ranker_service.update_global_rankings()
        
        self.assertGreaterEqual(ranking_count, len(self.offers))
        
        # Check if rankings were created
        rankings = GlobalOfferRank.objects.all()
        self.assertGreaterEqual(rankings.count(), len(self.offers))
        
        # Get top offers
        top_offers = ranker_service.get_top_offers(limit=3)
        
        self.assertIsInstance(top_offers, list)
        self.assertLessEqual(len(top_offers), 3)
    
    def test_scoring_with_user_history(self):
        """Test scoring with user interaction history."""
        # Create user history for first offer
        UserOfferHistory.objects.create(
            user=self.user,
            offer=self.offers[0],
            route=self.offers[0],
            viewed_at=timezone.now(),
            clicked_at=timezone.now(),
            completed_at=timezone.now(),
            conversion_value=25.0
        )
        
        # Calculate score for first offer
        score_data = scoring_service.calculate_offer_score(
            offer=self.offers[0],
            user=self.user,
            context={}
        )
        
        self.assertIsInstance(score_data, dict)
        self.assertIn('score', score_data)
        
        # Score should be higher due to conversion
        self.assertGreater(score_data['score'], 50)
    
    def test_ranking_consistency(self):
        """Test ranking consistency across multiple updates."""
        # Update scores multiple times
        for i in range(3):
            scoring_service.update_all_scores()
            ranker_service.update_global_rankings()
        
        # Get rankings
        rankings = GlobalOfferRank.objects.all().order_by('-rank_score')
        
        # Check if rankings are consistent
        self.assertEqual(rankings.count(), len(self.offers))
        
        # Scores should be in descending order
        for i in range(len(rankings) - 1):
            self.assertGreaterEqual(
                rankings[i].rank_score,
                rankings[i + 1].rank_score
            )
    
    def test_scoring_performance(self):
        """Test scoring performance."""
        import time
        
        # Measure scoring time for multiple offers
        start_time = time.time()
        
        for offer in self.offers:
            scoring_service.calculate_offer_score(
                offer=offer,
                user=self.user,
                context={}
            )
        
        end_time = time.time()
        scoring_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within reasonable time
        self.assertLess(scoring_time, 1000)  # Within 1 second
    
    def test_error_handling(self):
        """Test error handling in scoring."""
        # Test with invalid offer
        with self.assertRaises(Exception):
            scoring_service.calculate_offer_score(
                offer=None,
                user=self.user,
                context={}
            )
        
        # Test with invalid user
        with self.assertRaises(Exception):
            scoring_service.calculate_offer_score(
                offer=self.offers[0],
                user=None,
                context={}
            )
