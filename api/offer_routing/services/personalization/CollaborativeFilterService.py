"""
Collaborative Filter Service

Implements collaborative filtering personalization where
similar users liked this offer for offer routing system.
"""

import logging
import math
from typing import Dict, List, Any, Optional, Tuple, Set
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
from django.core.cache import cache
from ....models import (
    OfferRoute, UserOfferHistory, OfferScore, OfferAffinityScore,
    UserPreferenceVector, RoutingDecisionLog
)
from ....choices import PersonalizationAlgorithm, EventType
from ....constants import (
    COLLABORATIVE_CACHE_TIMEOUT, SIMILARITY_CACHE_TIMEOUT,
    MIN_COLLABORATIVE_USERS, MAX_COLLABORATIVE_USERS,
    MIN_COMMON_ITEMS, SIMILARITY_THRESHOLD, COLLABORATIVE_WEIGHT
)
from ....exceptions import PersonalizationError, CollaborativeFilterError
from ....utils import calculate_user_similarity, get_user_item_matrix

User = get_user_model()
logger = logging.getLogger(__name__)


class CollaborativeFilterService:
    """
    Service for collaborative filtering personalization.
    
    Provides recommendations based on similar users' preferences:
    - User-based collaborative filtering
    - Item-based collaborative filtering
    - Matrix factorization
    - Neighborhood-based approaches
    
    Performance targets:
    - Similarity calculation: <50ms for 1000 users
    - Recommendation generation: <20ms for 50 offers
    - Cache hit rate: >85%
    """
    
    def __init__(self):
        self.cache_service = cache
        self.collaborative_stats = {
            'total_recommendations': 0,
            'cache_hits': 0,
            'errors': 0,
            'avg_calculation_time_ms': 0.0
        }
        
        # Similarity calculation methods
        self.similarity_methods = {
            'cosine': self._cosine_similarity,
            'pearson': self._pearson_correlation,
            'jaccard': self._jaccard_similarity,
            'adjusted_cosine': self._adjusted_cosine_similarity
        }
    
    def get_collaborative_score(self, user: User, offer: OfferRoute, 
                               context: Dict[str, Any]) -> float:
        """
        Get collaborative filtering score for user-offer pair.
        
        Args:
            user: User object
            offer: Offer object
            context: User context
            
        Returns:
            Collaborative filtering score (0.0-1.0)
        """
        try:
            start_time = timezone.now()
            
            # Check cache first
            cache_key = f"collab_score:{user.id}:{offer.id}"
            cached_score = self.cache_service.get(cache_key)
            
            if cached_score is not None:
                self.collaborative_stats['cache_hits'] += 1
                return float(cached_score)
            
            # Get similar users
            similar_users = self._get_similar_users(user, limit=MAX_COLLABORATIVE_USERS)
            
            if not similar_users:
                return 0.0
            
            # Calculate collaborative score
            collaborative_score = self._calculate_collaborative_score(
                user, offer, similar_users, context
            )
            
            # Cache result
            self.cache_service.set(cache_key, collaborative_score, COLLABORATIVE_CACHE_TIMEOUT)
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_collaborative_stats(elapsed_ms)
            
            return collaborative_score
            
        except Exception as e:
            logger.error(f"Error calculating collaborative score for user {user.id}, offer {offer.id}: {e}")
            self.collaborative_stats['errors'] += 1
            return 0.0
    
    def _get_similar_users(self, user: User, limit: int = None) -> List[Tuple[User, float]]:
        """Get users similar to the given user."""
        try:
            # Check cache first
            cache_key = f"similar_users:{user.id}"
            cached_similar = self.cache_service.get(cache_key)
            
            if cached_similar:
                self.collaborative_stats['cache_hits'] += 1
                return cached_similar
            
            start_time = timezone.now()
            
            # Get user's preference vector
            user_preferences = self._get_user_preferences(user)
            
            if not user_preferences:
                return []
            
            # Get all other users with preferences
            other_users = UserPreferenceVector.objects.exclude(user=user).select_related('user')
            
            similar_users = []
            
            for other_user_pref in other_users:
                # Calculate similarity
                similarity = self._calculate_user_similarity(
                    user_preferences, other_user_pref
                )
                
                if similarity >= SIMILARITY_THRESHOLD:
                    similar_users.append((other_user_pref.user, similarity))
            
            # Sort by similarity (descending) and limit
            similar_users.sort(key=lambda x: x[1], reverse=True)
            
            if limit:
                similar_users = similar_users[:limit]
            
            # Cache result
            self.cache_service.set(cache_key, similar_users, SIMILARITY_CACHE_TIMEOUT)
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_collaborative_stats(elapsed_ms)
            
            return similar_users
            
        except Exception as e:
            logger.error(f"Error getting similar users for {user.id}: {e}")
            return []
    
    def _get_user_preferences(self, user: User) -> Optional[Dict[str, float]]:
        """Get user's preference vector."""
        try:
            preference_vector = UserPreferenceVector.objects.filter(user=user).first()
            
            if not preference_vector:
                return None
            
            return preference_vector.vector
            
        except Exception as e:
            logger.error(f"Error getting user preferences for {user.id}: {e}")
            return None
    
    def _calculate_user_similarity(self, user1_prefs: Dict[str, float], 
                               user2_prefs: Dict[str, float]) -> float:
        """Calculate similarity between two users."""
        try:
            # Use cosine similarity by default
            return self._cosine_similarity(user1_prefs, user2_prefs)
            
        except Exception as e:
            logger.error(f"Error calculating user similarity: {e}")
            return 0.0
    
    def _cosine_similarity(self, user1_prefs: Dict[str, float], 
                           user2_prefs: Dict[str, float]) -> float:
        """Calculate cosine similarity between two users."""
        try:
            # Get common categories
            common_categories = set(user1_prefs.keys()) & set(user2_prefs.keys())
            
            if not common_categories:
                return 0.0
            
            # Calculate dot product
            dot_product = sum(
                user1_prefs[cat] * user2_prefs[cat] 
                for cat in common_categories
            )
            
            # Calculate magnitudes
            magnitude1 = math.sqrt(
                sum(user1_prefs[cat] ** 2 for cat in common_categories)
            )
            magnitude2 = math.sqrt(
                sum(user2_prefs[cat] ** 2 for cat in common_categories)
            )
            
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
            
            # Calculate cosine similarity
            cosine_sim = dot_product / (magnitude1 * magnitude2)
            
            return max(0.0, min(1.0, cosine_sim))
            
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    def _pearson_correlation(self, user1_prefs: Dict[str, float], 
                             user2_prefs: Dict[str, float]) -> float:
        """Calculate Pearson correlation between two users."""
        try:
            # Get common categories
            common_categories = set(user1_prefs.keys()) & set(user2_prefs.keys())
            
            if len(common_categories) < MIN_COMMON_ITEMS:
                return 0.0
            
            # Calculate means
            mean1 = sum(user1_prefs[cat] for cat in common_categories) / len(common_categories)
            mean2 = sum(user2_prefs[cat] for cat in common_categories) / len(common_categories)
            
            # Calculate correlation
            numerator = sum(
                (user1_prefs[cat] - mean1) * (user2_prefs[cat] - mean2)
                for cat in common_categories
            )
            
            denominator1 = math.sqrt(
                sum((user1_prefs[cat] - mean1) ** 2 for cat in common_categories)
            )
            denominator2 = math.sqrt(
                sum((user2_prefs[cat] - mean2) ** 2 for cat in common_categories)
            )
            
            if denominator1 == 0 or denominator2 == 0:
                return 0.0
            
            correlation = numerator / (denominator1 * denominator2)
            
            return max(-1.0, min(1.0, correlation))
            
        except Exception as e:
            logger.error(f"Error calculating Pearson correlation: {e}")
            return 0.0
    
    def _jaccard_similarity(self, user1_prefs: Dict[str, float], 
                           user2_prefs: Dict[str, float]) -> float:
        """Calculate Jaccard similarity between two users."""
        try:
            # Get sets of categories (ignoring ratings)
            set1 = set(user1_prefs.keys())
            set2 = set(user2_prefs.keys())
            
            # Calculate Jaccard similarity
            intersection = len(set1 & set2)
            union = len(set1 | set2)
            
            if union == 0:
                return 0.0
            
            jaccard_sim = intersection / union
            
            return jaccard_sim
            
        except Exception as e:
            logger.error(f"Error calculating Jaccard similarity: {e}")
            return 0.0
    
    def _adjusted_cosine_similarity(self, user1_prefs: Dict[str, float], 
                                 user2_prefs: Dict[str, float]) -> float:
        """Calculate adjusted cosine similarity between two users."""
        try:
            # Get common categories
            common_categories = set(user1_prefs.keys()) & set(user2_prefs.keys())
            
            if not common_categories:
                return 0.0
            
            # Calculate user averages
            user1_avg = sum(user1_prefs.values()) / len(user1_prefs)
            user2_avg = sum(user2_prefs.values()) / len(user2_prefs)
            
            # Calculate adjusted dot product
            adjusted_dot_product = sum(
                (user1_prefs[cat] - user1_avg) * (user2_prefs[cat] - user2_avg)
                for cat in common_categories
            )
            
            # Calculate adjusted magnitudes
            magnitude1 = math.sqrt(
                sum((user1_prefs[cat] - user1_avg) ** 2 for cat in common_categories)
            )
            magnitude2 = math.sqrt(
                sum((user2_prefs[cat] - user2_avg) ** 2 for cat in common_categories)
            )
            
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
            
            # Calculate adjusted cosine similarity
            adjusted_cosine = adjusted_dot_product / (magnitude1 * magnitude2)
            
            return max(0.0, min(1.0, adjusted_cosine))
            
        except Exception as e:
            logger.error(f"Error calculating adjusted cosine similarity: {e}")
            return 0.0
    
    def _calculate_collaborative_score(self, user: User, offer: OfferRoute, 
                                    similar_users: List[Tuple[User, float]], 
                                    context: Dict[str, Any]) -> float:
        """Calculate collaborative filtering score for an offer."""
        try:
            if not similar_users:
                return 0.0
            
            # Get offer category
            offer_category = getattr(offer, 'category', 'general')
            
            # Get ratings from similar users for this offer
            user_ratings = []
            
            for similar_user, similarity in similar_users:
                # Get user's rating for this offer
                user_rating = self._get_user_offer_rating(similar_user, offer)
                
                if user_rating is not None:
                    # Weight by similarity
                    weighted_rating = user_rating * similarity
                    user_ratings.append(weighted_rating)
            
            if not user_ratings:
                return 0.0
            
            # Calculate weighted average
            total_weight = sum(similarity for _, similarity in similar_users)
            weighted_sum = sum(user_ratings)
            
            collaborative_score = weighted_sum / total_weight if total_weight > 0 else 0.0
            
            # Normalize to 0-1 range
            return min(1.0, max(0.0, collaborative_score))
            
        except Exception as e:
            logger.error(f"Error calculating collaborative score: {e}")
            return 0.0
    
    def _get_user_offer_rating(self, user: User, offer: OfferRoute) -> Optional[float]:
        """Get user's rating for a specific offer."""
        try:
            # Try to get explicit rating first
            offer_score = OfferScore.objects.filter(
                user=user,
                offer=offer
            ).order_by('-scored_at').first()
            
            if offer_score:
                return float(offer_score.score) / 100.0  # Convert from 0-100 to 0-1
            
            # Try to infer rating from behavior
            return self._infer_rating_from_behavior(user, offer)
            
        except Exception as e:
            logger.error(f"Error getting user offer rating: {e}")
            return None
    
    def _infer_rating_from_behavior(self, user: User, offer: OfferRoute) -> Optional[float]:
        """Infer user's rating for an offer from behavior."""
        try:
            # Get user's interaction history with this offer
            history = UserOfferHistory.objects.filter(
                user=user,
                offer=offer
            ).order_by('-created_at')[:10]
            
            if not history:
                return None
            
            # Calculate rating based on interactions
            total_score = 0.0
            weight_sum = 0.0
            
            for interaction in history:
                weight = 1.0  # Base weight
                score = 0.0
                
                # Score based on interaction type
                if interaction.viewed_at:
                    score += 0.1  # View = 0.1
                    weight += 0.1
                
                if interaction.clicked_at:
                    score += 0.5  # Click = 0.5
                    weight += 0.5
                
                if interaction.completed_at:
                    score += 1.0  # Conversion = 1.0
                    weight += 1.0
                
                # Apply time decay
                days_ago = (timezone.now() - interaction.created_at).days
                time_weight = math.exp(-days_ago / 30)  # 30-day half-life
                
                total_score += score * time_weight
                weight_sum += weight * time_weight
            
            if weight_sum > 0:
                inferred_rating = total_score / weight_sum
                return min(1.0, max(0.0, inferred_rating))
            
            return None
            
        except Exception as e:
            logger.error(f"Error inferring rating from behavior: {e}")
            return None
    
    def get_item_based_recommendations(self, user: User, 
                                   limit: int = 50) -> List[Tuple[OfferRoute, float]]:
        """
        Get item-based collaborative filtering recommendations.
        
        Args:
            user: User object
            limit: Maximum number of recommendations
            
        Returns:
            List of (offer, score) tuples
        """
        try:
            start_time = timezone.now()
            
            # Check cache first
            cache_key = f"item_recs:{user.id}"
            cached_recs = self.cache_service.get(cache_key)
            
            if cached_recs:
                self.collaborative_stats['cache_hits'] += 1
                return cached_recs
            
            # Get user's highly rated offers
            user_ratings = self._get_user_ratings(user)
            
            if not user_ratings:
                return []
            
            # Find similar offers for each highly rated offer
            offer_similarities = {}
            
            for offer_id, rating in user_ratings.items():
                if rating >= 0.7:  # Only consider highly rated offers
                    similar_offers = self._find_similar_offers(offer_id, limit=20)
                    
                    for similar_offer_id, similarity in similar_offers:
                        if similar_offer_id not in offer_similarities:
                            offer_similarities[similar_offer_id] = 0.0
                        
                        offer_similarities[similar_offer_id] += similarity * rating
            
            # Sort by similarity score and limit
            sorted_offers = sorted(
                offer_similarities.items(),
                key=lambda x: x[1],
                reverse=True
            )[:limit]
            
            # Convert to offer objects
            recommendations = []
            for offer_id, score in sorted_offers:
                try:
                    offer = OfferRoute.objects.get(id=offer_id)
                    recommendations.append((offer, score))
                except OfferRoute.DoesNotExist:
                    continue
            
            # Cache result
            self.cache_service.set(cache_key, recommendations, COLLABORATIVE_CACHE_TIMEOUT)
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_collaborative_stats(elapsed_ms)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting item-based recommendations for user {user.id}: {e}")
            return []
    
    def _get_user_ratings(self, user: User) -> Dict[int, float]:
        """Get all ratings for a user."""
        try:
            ratings = {}
            
            # Get explicit ratings
            offer_scores = OfferScore.objects.filter(user=user)
            
            for score in offer_scores:
                ratings[score.offer_id] = float(score.score) / 100.0
            
            # Add inferred ratings for offers without explicit ratings
            user_history = UserOfferHistory.objects.filter(user=user)
            
            for history in user_history:
                if history.offer_id not in ratings:
                    inferred_rating = self._infer_rating_from_behavior(user, history.offer)
                    if inferred_rating is not None:
                        ratings[history.offer_id] = inferred_rating
            
            return ratings
            
        except Exception as e:
            logger.error(f"Error getting user ratings: {e}")
            return {}
    
    def _find_similar_offers(self, offer_id: int, limit: int = 20) -> List[Tuple[int, float]]:
        """Find offers similar to the given offer."""
        try:
            # Get users who rated this offer
            user_ratings = OfferScore.objects.filter(offer_id=offer_id).select_related('user')
            
            if not user_ratings:
                return []
            
            # Get other offers rated by these users
            other_offer_ratings = OfferScore.objects.filter(
                user_id__in=[ur.user_id for ur in user_ratings],
                offer_id__ne=offer_id
            ).exclude(offer_id=offer_id)
            
            # Calculate offer similarities
            offer_similarities = {}
            
            for other_rating in other_offer_ratings:
                # Calculate similarity based on user ratings
                similarity = self._calculate_offer_similarity(offer_id, other_rating.offer_id, user_ratings)
                
                if other_rating.offer_id not in offer_similarities:
                    offer_similarities[other_rating.offer_id] = similarity
                else:
                    # Take maximum similarity
                    offer_similarities[other_rating.offer_id] = max(
                        offer_similarities[other_rating.offer_id], similarity
                    )
            
            # Sort by similarity and limit
            sorted_similar = sorted(
                offer_similarities.items(),
                key=lambda x: x[1],
                reverse=True
            )[:limit]
            
            return sorted_similar
            
        except Exception as e:
            logger.error(f"Error finding similar offers for {offer_id}: {e}")
            return []
    
    def _calculate_offer_similarity(self, offer1_id: int, offer2_id: int, 
                                user_ratings: List[OfferScore]) -> float:
        """Calculate similarity between two offers based on user ratings."""
        try:
            # Get users who rated both offers
            common_users = []
            
            for rating in user_ratings:
                if rating.offer_id in [offer1_id, offer2_id]:
                    common_users.append(rating.user_id)
            
            common_users = list(set(common_users))
            
            if len(common_users) < MIN_COMMON_ITEMS:
                return 0.0
            
            # Calculate similarity based on ratings
            rating_pairs = []
            
            for user_id in common_users:
                user_ratings_list = [r for r in user_ratings if r.user_id == user_id]
                
                rating1 = None
                rating2 = None
                
                for rating in user_ratings_list:
                    if rating.offer_id == offer1_id:
                        rating1 = float(rating.score) / 100.0
                    elif rating.offer_id == offer2_id:
                        rating2 = float(rating.score) / 100.0
                
                if rating1 is not None and rating2 is not None:
                    rating_pairs.append((rating1, rating2))
            
            if not rating_pairs:
                return 0.0
            
            # Calculate Pearson correlation
            return self._calculate_pearson_correlation_from_pairs(rating_pairs)
            
        except Exception as e:
            logger.error(f"Error calculating offer similarity: {e}")
            return 0.0
    
    def _calculate_pearson_correlation_from_pairs(self, rating_pairs: List[Tuple[float, float]]) -> float:
        """Calculate Pearson correlation from rating pairs."""
        try:
            if len(rating_pairs) < 2:
                return 0.0
            
            # Extract ratings
            ratings1 = [pair[0] for pair in rating_pairs]
            ratings2 = [pair[1] for pair in rating_pairs]
            
            # Calculate means
            mean1 = sum(ratings1) / len(ratings1)
            mean2 = sum(ratings2) / len(ratings2)
            
            # Calculate correlation
            numerator = sum(
                (r1 - mean1) * (r2 - mean2)
                for r1, r2 in rating_pairs
            )
            
            denominator1 = math.sqrt(sum((r1 - mean1) ** 2 for r1 in ratings1))
            denominator2 = math.sqrt(sum((r2 - mean2) ** 2 for r2 in ratings2))
            
            if denominator1 == 0 or denominator2 == 0:
                return 0.0
            
            correlation = numerator / (denominator1 * denominator2)
            
            return max(-1.0, min(1.0, correlation))
            
        except Exception as e:
            logger.error(f"Error calculating Pearson correlation from pairs: {e}")
            return 0.0
    
    def get_user_based_recommendations(self, user: User, 
                                     limit: int = 50) -> List[Tuple[OfferRoute, float]]:
        """
        Get user-based collaborative filtering recommendations.
        
        Args:
            user: User object
            limit: Maximum number of recommendations
            
        Returns:
            List of (offer, score) tuples
        """
        try:
            start_time = timezone.now()
            
            # Check cache first
            cache_key = f"user_recs:{user.id}"
            cached_recs = self.cache_service.get(cache_key)
            
            if cached_recs:
                self.collaborative_stats['cache_hits'] += 1
                return cached_recs
            
            # Get similar users
            similar_users = self._get_similar_users(user, limit=MAX_COLLABORATIVE_USERS)
            
            if not similar_users:
                return []
            
            # Get offers liked by similar users
            offer_scores = {}
            
            for similar_user, similarity in similar_users:
                # Get similar user's ratings
                user_ratings = self._get_user_ratings(similar_user)
                
                for offer_id, rating in user_ratings.items():
                    if rating >= 0.6:  # Only consider offers user liked
                        if offer_id not in offer_scores:
                            offer_scores[offer_id] = 0.0
                        
                        # Weight by similarity and rating
                        offer_scores[offer_id] += similarity * rating
            
            # Sort by score and limit
            sorted_offers = sorted(
                offer_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )[:limit]
            
            # Convert to offer objects
            recommendations = []
            for offer_id, score in sorted_offers:
                try:
                    offer = OfferRoute.objects.get(id=offer_id)
                    recommendations.append((offer, score))
                except OfferRoute.DoesNotExist:
                    continue
            
            # Cache result
            self.cache_service.set(cache_key, recommendations, COLLABORATIVE_CACHE_TIMEOUT)
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_collaborative_stats(elapsed_ms)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting user-based recommendations for user {user.id}: {e}")
            return []
    
    def _update_collaborative_stats(self, elapsed_ms: float):
        """Update collaborative filtering performance statistics."""
        self.collaborative_stats['total_recommendations'] += 1
        
        # Update average time
        current_avg = self.collaborative_stats['avg_calculation_time_ms']
        total_recs = self.collaborative_stats['total_recommendations']
        self.collaborative_stats['avg_calculation_time_ms'] = (
            (current_avg * (total_recs - 1) + elapsed_ms) / total_recs
        )
    
    def get_collaborative_stats(self) -> Dict[str, Any]:
        """Get collaborative filtering performance statistics."""
        total_requests = self.collaborative_stats['total_recommendations']
        cache_hit_rate = (
            self.collaborative_stats['cache_hits'] / max(1, total_requests)
        )
        
        return {
            'total_recommendations': total_requests,
            'cache_hits': self.collaborative_stats['cache_hits'],
            'cache_misses': total_requests - self.collaborative_stats['cache_hits'],
            'cache_hit_rate': cache_hit_rate,
            'errors': self.collaborative_stats['errors'],
            'error_rate': self.collaborative_stats['errors'] / max(1, total_requests),
            'avg_calculation_time_ms': self.collaborative_stats['avg_calculation_time_ms'],
            'similarity_methods': list(self.similarity_methods.keys())
        }
    
    def clear_cache(self, user_id: int = None):
        """Clear collaborative filtering cache."""
        try:
            if user_id:
                # Clear specific user cache
                cache_keys = [
                    f"collab_score:{user_id}:*",
                    f"similar_users:{user_id}",
                    f"user_recs:{user_id}",
                    f"item_recs:{user_id}"
                ]
                
                for key_pattern in cache_keys:
                    # This would need pattern deletion support
                    logger.info(f"Cache clearing for pattern {key_pattern} not implemented")
            else:
                # Clear all collaborative filtering cache
                logger.info("Cache clearing for all collaborative filtering not implemented")
                
        except Exception as e:
            logger.error(f"Error clearing collaborative cache: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on collaborative filtering service."""
        try:
            # Test similarity calculation
            test_user1_prefs = {'electronics': 0.8, 'fashion': 0.6, 'books': 0.9}
            test_user2_prefs = {'electronics': 0.7, 'fashion': 0.8, 'books': 0.7}
            
            similarity_score = self._cosine_similarity(test_user1_prefs, test_user2_prefs)
            
            # Test recommendation generation
            test_user = User(id=1, username='test')
            test_recommendations = self.get_user_based_recommendations(test_user, limit=5)
            
            return {
                'status': 'healthy',
                'test_similarity_calculation': 0.0 <= similarity_score <= 1.0,
                'test_recommendation_count': len(test_recommendations),
                'stats': self.get_collaborative_stats(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
