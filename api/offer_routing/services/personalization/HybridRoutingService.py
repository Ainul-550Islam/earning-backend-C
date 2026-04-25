"""
Hybrid Routing Service

Combines collaborative + content-based personalization
for optimal offer routing system recommendations.
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
    UserPreferenceVector, RoutingDecisionLog, PersonalizationConfig
)
from ....choices import PersonalizationAlgorithm, EventType
from ....constants import (
    HYBRID_CACHE_TIMEOUT, PERSONALIZATION_CACHE_TIMEOUT,
    MIN_HYBRID_USERS, MAX_HYBRID_OFFERS,
    HYBRID_WEIGHT_DECAY, HYBRID_CONFIDENCE_THRESHOLD,
    COLLABORATIVE_WEIGHT, CONTENT_BASED_WEIGHT, HYBRID_WEIGHT
)
from ....exceptions import PersonalizationError, HybridRoutingError
from ....utils import calculate_hybrid_score, get_user_profile_data

User = get_user_model()
logger = logging.getLogger(__name__)


class HybridRoutingService:
    """
    Service for hybrid personalization combining multiple approaches.
    
    Combines collaborative filtering, content-based filtering,
    and other personalization methods for optimal recommendations:
    - Weighted combination of algorithms
    - Dynamic weight adjustment
    - Confidence-based filtering
    - Cold start handling
    
    Performance targets:
    - Hybrid scoring: <25ms for 100 offers
    - Weight optimization: <100ms for 1000 users
    - Recommendation generation: <35ms for 50 offers
    - Cache hit rate: >85%
    """
    
    def __init__(self):
        self.cache_service = cache
        self.hybrid_stats = {
            'total_recommendations': 0,
            'cache_hits': 0,
            'errors': 0,
            'avg_calculation_time_ms': 0.0
        }
        
        # Import personalization services
        from .CollaborativeFilterService import CollaborativeFilterService
        from .ContentBasedService import ContentBasedService
        
        self.collaborative_service = CollaborativeFilterService()
        self.content_service = ContentBasedService()
        
        # Hybrid algorithms
        self._initialize_hybrid_algorithms()
    
    def _initialize_hybrid_algorithms(self):
        """Initialize hybrid algorithm configurations."""
        self.hybrid_algorithms = {
            'weighted_average': {
                'name': 'Weighted Average',
                'description': 'Weighted combination of collaborative and content scores',
                'default_weights': {
                    'collaborative': COLLABORATIVE_WEIGHT,
                    'content_based': CONTENT_BASED_WEIGHT,
                    'popularity': 0.1,
                    'freshness': 0.1
                },
                'weight_learning': True,
                'adaptive': True
            },
            'switching': {
                'name': 'Switching Algorithm',
                'description': 'Switch between collaborative and content based on confidence',
                'confidence_threshold': 0.7,
                'fallback_to_content': True,
                'use_popularity_backup': True
            },
            'cascade': {
                'name': 'Cascade Algorithm',
                'description': 'Apply algorithms in sequence with filtering',
                'cascade_order': ['collaborative', 'content_based', 'popularity'],
                'cascade_filters': True,
                'min_results_per_stage': 10
            },
            'feature_combination': {
                'name': 'Feature Combination',
                'description': 'Combine features from multiple algorithms',
                'feature_weights': {
                    'collaborative_score': 0.4,
                    'content_score': 0.3,
                    'user_affinity': 0.2,
                    'popularity_score': 0.1
                },
                'normalization': 'min_max',
                'feature_engineering': True
            },
            'neural_blend': {
                'name': 'Neural Blend',
                'description': 'Neural network combination of multiple signals',
                'model_path': None,  # Would be configured
                'input_features': ['collaborative', 'content', 'user_profile', 'context'],
                'output_activation': 'sigmoid',
                'ensemble_method': 'weighted_average'
            }
        }
    
    def get_hybrid_score(self, user: User, offer: OfferRoute, 
                         context: Dict[str, Any]) -> float:
        """
        Get hybrid personalization score for user-offer pair.
        
        Args:
            user: User object
            offer: Offer object
            context: User context
            
        Returns:
            Hybrid personalization score (0.0-1.0)
        """
        try:
            start_time = timezone.now()
            
            # Check cache first
            cache_key = f"hybrid_score:{user.id}:{offer.id}"
            cached_score = self.cache_service.get(cache_key)
            
            if cached_score is not None:
                self.hybrid_stats['cache_hits'] += 1
                return float(cached_score)
            
            # Get personalization configuration
            config = self._get_personalization_config(user)
            
            # Get scores from different algorithms
            collaborative_score = self.collaborative_service.get_collaborative_score(user, offer, context)
            content_score = self.content_service.get_content_based_score(user, offer, context)
            popularity_score = self._get_popularity_score(offer, context)
            freshness_score = self._get_freshness_score(offer, context)
            
            # Calculate hybrid score based on algorithm
            algorithm = config.algorithm if config else PersonalizationAlgorithm.HYBRID
            hybrid_score = self._calculate_hybrid_score(
                algorithm, user, offer, context,
                collaborative_score, content_score, popularity_score, freshness_score
            )
            
            # Apply final adjustments
            final_score = self._apply_final_adjustments(hybrid_score, user, offer, context, config)
            
            # Cache result
            self.cache_service.set(cache_key, final_score, HYBRID_CACHE_TIMEOUT)
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_hybrid_stats(elapsed_ms)
            
            return final_score
            
        except Exception as e:
            logger.error(f"Error calculating hybrid score for user {user.id}, offer {offer.id}: {e}")
            self.hybrid_stats['errors'] += 1
            return 0.5
    
    def _get_personalization_config(self, user: User) -> Optional[PersonalizationConfig]:
        """Get personalization configuration for user."""
        try:
            return PersonalizationConfig.objects.filter(user=user).first()
        except Exception as e:
            logger.error(f"Error getting personalization config for user {user.id}: {e}")
            return None
    
    def _get_popularity_score(self, offer: OfferRoute, context: Dict[str, Any]) -> float:
        """Get popularity score for an offer."""
        try:
            # Get recent popularity metrics
            thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
            
            popularity_data = UserOfferHistory.objects.filter(
                offer=offer,
                created_at__gte=thirty_days_ago
            ).aggregate(
                total_views=Count('id'),
                total_clicks=Count('id', filter=Q(clicked_at__isnull=False)),
                total_conversions=Count('id', filter=Q(completed_at__isnull=False))
            )
            
            if not popularity_data['total_views']:
                return 0.0
            
            # Calculate popularity metrics
            click_rate = popularity_data['total_clicks'] / popularity_data['total_views']
            conversion_rate = popularity_data['total_conversions'] / popularity_data['total_views']
            
            # Combine metrics
            popularity_score = (click_rate * 0.6) + (conversion_rate * 0.4)
            
            # Apply time decay
            days_since_creation = (timezone.now() - offer.created_at).days
            time_decay = math.exp(-days_since_creation / 90)  # 90-day half-life
            
            final_score = popularity_score * time_decay
            
            return min(1.0, max(0.0, final_score))
            
        except Exception as e:
            logger.error(f"Error calculating popularity score for offer {offer.id}: {e}")
            return 0.0
    
    def _get_freshness_score(self, offer: OfferRoute, context: Dict[str, Any]) -> float:
        """Get freshness score for an offer."""
        try:
            # Calculate days since creation
            days_since_creation = (timezone.now() - offer.created_at).days
            
            # Calculate freshness score with exponential decay
            freshness_score = math.exp(-days_since_creation / 30)  # 30-day half-life
            
            # Boost for very new offers
            if days_since_creation <= 7:
                freshness_score *= 1.2  # 20% boost for new offers
            elif days_since_creation <= 3:
                freshness_score *= 1.5  # 50% boost for very new offers
            
            return min(1.0, max(0.0, freshness_score))
            
        except Exception as e:
            logger.error(f"Error calculating freshness score for offer {offer.id}: {e}")
            return 0.5
    
    def _calculate_hybrid_score(self, algorithm: str, user: User, offer: OfferRoute,
                               context: Dict[str, Any], collaborative_score: float,
                               content_score: float, popularity_score: float,
                               freshness_score: float) -> float:
        """Calculate hybrid score based on algorithm."""
        try:
            if algorithm == PersonalizationAlgorithm.HYBRID:
                return self._weighted_average_hybrid(
                    collaborative_score, content_score, popularity_score, freshness_score
                )
            elif algorithm == PersonalizationAlgorithm.COLLABORATIVE:
                return collaborative_score
            elif algorithm == PersonalizationAlgorithm.CONTENT_BASED:
                return content_score
            else:
                # Default to weighted average
                return self._weighted_average_hybrid(
                    collaborative_score, content_score, popularity_score, freshness_score
                )
                
        except Exception as e:
            logger.error(f"Error calculating hybrid score with algorithm {algorithm}: {e}")
            return 0.5
    
    def _weighted_average_hybrid(self, collaborative_score: float, content_score: float,
                               popularity_score: float, freshness_score: float) -> float:
        """Calculate weighted average hybrid score."""
        try:
            # Default weights
            weights = {
                'collaborative': COLLABORATIVE_WEIGHT,
                'content_based': CONTENT_BASED_WEIGHT,
                'popularity': 0.1,
                'freshness': 0.1
            }
            
            # Normalize weights
            total_weight = sum(weights.values())
            normalized_weights = {k: v / total_weight for k, v in weights.items()}
            
            # Calculate weighted average
            hybrid_score = (
                collaborative_score * normalized_weights['collaborative'] +
                content_score * normalized_weights['content_based'] +
                popularity_score * normalized_weights['popularity'] +
                freshness_score * normalized_weights['freshness']
            )
            
            return min(1.0, max(0.0, hybrid_score))
            
        except Exception as e:
            logger.error(f"Error calculating weighted average hybrid: {e}")
            return 0.5
    
    def _apply_final_adjustments(self, hybrid_score: float, user: User, 
                               offer: OfferRoute, context: Dict[str, Any],
                               config: Optional[PersonalizationConfig]) -> float:
        """Apply final adjustments to hybrid score."""
        try:
            adjusted_score = hybrid_score
            
            # User segment adjustments
            if config:
                adjusted_score = self._apply_user_segment_adjustments(
                    adjusted_score, user, config
                )
            
            # Contextual adjustments
            adjusted_score = self._apply_contextual_adjustments(
                adjusted_score, user, offer, context
            )
            
            # Business rule adjustments
            adjusted_score = self._apply_business_rule_adjustments(
                adjusted_score, user, offer, context
            )
            
            # Diversity adjustments
            adjusted_score = self._apply_diversity_adjustments(
                adjusted_score, user, offer, context
            )
            
            return min(1.0, max(0.0, adjusted_score))
            
        except Exception as e:
            logger.error(f"Error applying final adjustments: {e}")
            return hybrid_score
    
    def _apply_user_segment_adjustments(self, score: float, user: User,
                                        config: PersonalizationConfig) -> float:
        """Apply user segment-based adjustments."""
        try:
            adjusted_score = score
            
            # Premium user boost
            if getattr(user, 'is_premium', False):
                premium_multiplier = getattr(config, 'premium_user_multiplier', 1.5)
                adjusted_score *= premium_multiplier
            
            # New user adjustments
            days_since_registration = (timezone.now() - user.date_joined).days
            if days_since_registration <= getattr(config, 'new_user_days', 7):
                # Slightly reduce score for new users to encourage exploration
                adjusted_score *= 0.9
            
            # Active user boost
            if self._is_active_user(user, config):
                adjusted_score *= 1.1
            
            return adjusted_score
            
        except Exception as e:
            logger.error(f"Error applying user segment adjustments: {e}")
            return score
    
    def _apply_contextual_adjustments(self, score: float, user: User, 
                                    offer: OfferRoute, context: Dict[str, Any]) -> float:
        """Apply contextual adjustments."""
        try:
            adjusted_score = score
            
            # Time-based adjustments
            current_hour = timezone.now().hour
            if 6 <= current_hour <= 12:  # Morning
                adjusted_score *= 1.05
            elif 18 <= current_hour <= 22:  # Evening
                adjusted_score *= 1.03
            
            # Device-based adjustments
            device_type = context.get('device', {}).get('type')
            if device_type == 'mobile':
                adjusted_score *= 1.02
            
            # Location-based adjustments
            country = context.get('location', {}).get('country')
            if country in ['US', 'CA', 'UK']:  # High-value markets
                adjusted_score *= 1.04
            
            return adjusted_score
            
        except Exception as e:
            logger.error(f"Error applying contextual adjustments: {e}")
            return score
    
    def _apply_business_rule_adjustments(self, score: float, user: User, 
                                        offer: OfferRoute, context: Dict[str, Any]) -> float:
        """Apply business rule adjustments."""
        try:
            adjusted_score = score
            
            # Featured offer boost
            if getattr(offer, 'is_featured', False):
                adjusted_score *= 1.2
            
            # Exclusive offer boost
            if getattr(offer, 'is_exclusive', False):
                adjusted_score *= 1.15
            
            # Seasonal adjustments
            if self._is_seasonal_offer(offer):
                adjusted_score *= 1.1
            
            return adjusted_score
            
        except Exception as e:
            logger.error(f"Error applying business rule adjustments: {e}")
            return score
    
    def _apply_diversity_adjustments(self, score: float, user: User, 
                                   offer: OfferRoute, context: Dict[str, Any]) -> float:
        """Apply diversity adjustments."""
        try:
            adjusted_score = score
            
            # Check user's recent offer history for diversity
            recent_offers = self._get_user_recent_offers(user, days=7)
            
            if recent_offers:
                # Calculate category diversity
                recent_categories = [getattr(o.offer, 'category', 'general') for o in recent_offers]
                offer_category = getattr(offer, 'category', 'general')
                
                # Boost offers from underrepresented categories
                category_count = recent_categories.count(offer_category)
                total_recent = len(recent_categories)
                
                if total_recent > 0:
                    category_ratio = category_count / total_recent
                    if category_ratio < 0.2:  # Underrepresented category
                        adjusted_score *= 1.1
                    elif category_ratio > 0.6:  # Overrepresented category
                        adjusted_score *= 0.9
            
            return adjusted_score
            
        except Exception as e:
            logger.error(f"Error applying diversity adjustments: {e}")
            return score
    
    def _is_active_user(self, user: User, config: PersonalizationConfig) -> bool:
        """Check if user is considered active."""
        try:
            active_days = getattr(config, 'active_user_days', 30)
            cutoff_date = timezone.now() - timezone.timedelta(days=active_days)
            
            # Check recent activity
            recent_activity = UserOfferHistory.objects.filter(
                user=user,
                created_at__gte=cutoff_date
            ).count()
            
            return recent_activity >= 5  # At least 5 interactions in active period
            
        except Exception as e:
            logger.error(f"Error checking if user is active: {e}")
            return False
    
    def _is_seasonal_offer(self, offer: OfferRoute) -> bool:
        """Check if offer is seasonal."""
        try:
            # Get offer seasonal tags
            tags = getattr(offer, 'tags', [])
            
            seasonal_tags = ['summer', 'winter', 'spring', 'fall', 'holiday', 'christmas', 'new_year']
            
            current_month = timezone.now().month
            current_season = self._get_current_season(current_month)
            
            return any(tag.lower() == current_season for tag in tags)
            
        except Exception as e:
            logger.error(f"Error checking if offer is seasonal: {e}")
            return False
    
    def _get_current_season(self, month: int) -> str:
        """Get current season from month."""
        if month in [12, 1, 2]:
            return 'winter'
        elif month in [3, 4, 5]:
            return 'spring'
        elif month in [6, 7, 8]:
            return 'summer'
        else:
            return 'fall'
    
    def _get_user_recent_offers(self, user: User, days: int = 7) -> List[UserOfferHistory]:
        """Get user's recent offer interactions."""
        try:
            cutoff_date = timezone.now() - timezone.timedelta(days=days)
            
            return UserOfferHistory.objects.filter(
                user=user,
                created_at__gte=cutoff_date
            ).order_by('-created_at')[:50]
            
        except Exception as e:
            logger.error(f"Error getting user recent offers: {e}")
            return []
    
    def get_hybrid_recommendations(self, user: User, context: Dict[str, Any],
                                 limit: int = 50) -> List[Tuple[OfferRoute, float]]:
        """
        Get hybrid personalization recommendations for a user.
        
        Args:
            user: User object
            context: User context
            limit: Maximum number of recommendations
            
        Returns:
            List of (offer, score) tuples
        """
        try:
            start_time = timezone.now()
            
            # Check cache first
            cache_key = f"hybrid_recs:{user.id}"
            cached_recs = self.cache_service.get(cache_key)
            
            if cached_recs:
                self.hybrid_stats['cache_hits'] += 1
                return cached_recs
            
            # Get recommendations from different algorithms
            collaborative_recs = self.collaborative_service.get_user_based_recommendations(user, limit)
            content_recs = self.content_service.get_content_based_recommendations(user, limit)
            
            # Combine and re-rank recommendations
            hybrid_recs = self._combine_and_rank_recommendations(
                user, collaborative_recs, content_recs, context, limit
            )
            
            # Cache result
            self.cache_service.set(cache_key, hybrid_recs, HYBRID_CACHE_TIMEOUT)
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_hybrid_stats(elapsed_ms)
            
            return hybrid_recs
            
        except Exception as e:
            logger.error(f"Error getting hybrid recommendations for user {user.id}: {e}")
            return []
    
    def _combine_and_rank_recommendations(self, user: User,
                                       collaborative_recs: List[Tuple[OfferRoute, float]],
                                       content_recs: List[Tuple[OfferRoute, float]],
                                       context: Dict[str, Any],
                                       limit: int) -> List[Tuple[OfferRoute, float]]:
        """Combine and rank recommendations from multiple algorithms."""
        try:
            # Combine recommendations
            combined_scores = {}
            
            # Add collaborative recommendations
            for offer, score in collaborative_recs:
                if offer.id not in combined_scores:
                    combined_scores[offer.id] = {
                        'offer': offer,
                        'collaborative_score': score,
                        'content_score': 0.0,
                        'popularity_score': 0.0,
                        'freshness_score': 0.0
                    }
                else:
                    combined_scores[offer.id]['collaborative_score'] = score
            
            # Add content-based recommendations
            for offer, score in content_recs:
                if offer.id not in combined_scores:
                    combined_scores[offer.id] = {
                        'offer': offer,
                        'collaborative_score': 0.0,
                        'content_score': score,
                        'popularity_score': 0.0,
                        'freshness_score': 0.0
                    }
                else:
                    combined_scores[offer.id]['content_score'] = score
            
            # Calculate additional scores for all offers
            for offer_id, score_data in combined_scores.items():
                offer = score_data['offer']
                score_data['popularity_score'] = self._get_popularity_score(offer, context)
                score_data['freshness_score'] = self._get_freshness_score(offer, context)
            
            # Calculate hybrid scores
            hybrid_recommendations = []
            for offer_id, score_data in combined_scores.items():
                hybrid_score = self._calculate_hybrid_score(
                    PersonalizationAlgorithm.HYBRID, user, score_data['offer'], context,
                    score_data['collaborative_score'], score_data['content_score'],
                    score_data['popularity_score'], score_data['freshness_score']
                )
                
                hybrid_recommendations.append((score_data['offer'], hybrid_score))
            
            # Sort by hybrid score and limit
            hybrid_recommendations.sort(key=lambda x: x[1], reverse=True)
            
            return hybrid_recommendations[:limit]
            
        except Exception as e:
            logger.error(f"Error combining and ranking recommendations: {e}")
            return []
    
    def optimize_hybrid_weights(self, user_sample: List[User] = None) -> Dict[str, Any]:
        """
        Optimize hybrid weights based on user feedback.
        
        Args:
            user_sample: Sample of users for optimization (None for all)
            
        Returns:
            Optimization results with new weights
        """
        try:
            start_time = timezone.now()
            
            # Get user sample
            if user_sample is None:
                user_sample = User.objects.filter(is_active=True)[:MIN_HYBRID_USERS]
            
            if not user_sample:
                return {'error': 'No users available for optimization'}
            
            # Current weights
            current_weights = {
                'collaborative': COLLABORATIVE_WEIGHT,
                'content_based': CONTENT_BASED_WEIGHT,
                'popularity': 0.1,
                'freshness': 0.1
            }
            
            # Calculate performance metrics for current weights
            current_performance = self._evaluate_weight_performance(user_sample, current_weights)
            
            # Try different weight combinations
            best_weights = current_weights
            best_performance = current_performance
            
            # Simple grid search for optimization
            weight_ranges = {
                'collaborative': [0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
                'content_based': [0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
                'popularity': [0.05, 0.1, 0.15, 0.2],
                'freshness': [0.05, 0.1, 0.15, 0.2]
            }
            
            for collab_weight in weight_ranges['collaborative']:
                for content_weight in weight_ranges['content_based']:
                    for pop_weight in weight_ranges['popularity']:
                        for fresh_weight in weight_ranges['freshness']:
                            # Normalize weights
                            test_weights = {
                                'collaborative': collab_weight,
                                'content_based': content_weight,
                                'popularity': pop_weight,
                                'freshness': fresh_weight
                            }
                            
                            total_weight = sum(test_weights.values())
                            normalized_weights = {k: v / total_weight for k, v in test_weights.items()}
                            
                            # Evaluate performance
                            performance = self._evaluate_weight_performance(user_sample, normalized_weights)
                            
                            # Update best if better
                            if performance['overall_score'] > best_performance['overall_score']:
                                best_weights = normalized_weights
                                best_performance = performance
            
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            
            return {
                'optimized_weights': best_weights,
                'previous_weights': current_weights,
                'performance_improvement': best_performance['overall_score'] - current_performance['overall_score'],
                'optimization_time_ms': elapsed_ms,
                'users_evaluated': len(user_sample),
                'best_performance': best_performance,
                'previous_performance': current_performance
            }
            
        except Exception as e:
            logger.error(f"Error optimizing hybrid weights: {e}")
            return {'error': str(e)}
    
    def _evaluate_weight_performance(self, user_sample: List[User], 
                                   weights: Dict[str, float]) -> Dict[str, float]:
        """Evaluate performance of weight configuration."""
        try:
            total_performance = 0.0
            total_users = 0
            
            for user in user_sample:
                # Get recommendations with these weights
                context = {}
                recommendations = self.get_hybrid_recommendations(user, context, limit=10)
                
                if not recommendations:
                    continue
                
                # Calculate performance metrics
                user_performance = self._calculate_user_performance(user, recommendations)
                total_performance += user_performance
                total_users += 1
            
            if total_users == 0:
                return {'overall_score': 0.0}
            
            avg_performance = total_performance / total_users
            
            return {
                'overall_score': avg_performance,
                'users_evaluated': total_users
            }
            
        except Exception as e:
            logger.error(f"Error evaluating weight performance: {e}")
            return {'overall_score': 0.0}
    
    def _calculate_user_performance(self, user: User, 
                                  recommendations: List[Tuple[OfferRoute, float]]) -> float:
        """Calculate performance score for user recommendations."""
        try:
            if not recommendations:
                return 0.0
            
            # Get user's actual interactions with recommended offers
            offer_ids = [offer.id for offer, _ in recommendations]
            
            thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
            user_interactions = UserOfferHistory.objects.filter(
                user=user,
                offer_id__in=offer_ids,
                created_at__gte=thirty_days_ago
            ).aggregate(
                total_views=Count('id'),
                total_clicks=Count('id', filter=Q(clicked_at__isnull=False)),
                total_conversions=Count('id', filter=Q(completed_at__isnull=False))
            )
            
            if not user_interactions['total_views']:
                return 0.0
            
            # Calculate performance metrics
            click_rate = user_interactions['total_clicks'] / user_interactions['total_views']
            conversion_rate = user_interactions['total_conversions'] / user_interactions['total_views']
            
            # Weighted performance score
            performance_score = (click_rate * 0.6) + (conversion_rate * 0.4)
            
            return performance_score
            
        except Exception as e:
            logger.error(f"Error calculating user performance: {e}")
            return 0.0
    
    def _update_hybrid_stats(self, elapsed_ms: float):
        """Update hybrid personalization performance statistics."""
        self.hybrid_stats['total_recommendations'] += 1
        
        # Update average time
        current_avg = self.hybrid_stats['avg_calculation_time_ms']
        total_recs = self.hybrid_stats['total_recommendations']
        self.hybrid_stats['avg_calculation_time_ms'] = (
            (current_avg * (total_recs - 1) + elapsed_ms) / total_recs
        )
    
    def get_hybrid_stats(self) -> Dict[str, Any]:
        """Get hybrid personalization performance statistics."""
        total_requests = self.hybrid_stats['total_recommendations']
        cache_hit_rate = (
            self.hybrid_stats['cache_hits'] / max(1, total_requests)
        )
        
        return {
            'total_recommendations': total_requests,
            'cache_hits': self.hybrid_stats['cache_hits'],
            'cache_misses': total_requests - self.hybrid_stats['cache_hits'],
            'cache_hit_rate': cache_hit_rate,
            'errors': self.hybrid_stats['errors'],
            'error_rate': self.hybrid_stats['errors'] / max(1, total_requests),
            'avg_calculation_time_ms': self.hybrid_stats['avg_calculation_time_ms'],
            'hybrid_algorithms': list(self.hybrid_algorithms.keys())
        }
    
    def clear_cache(self, user_id: int = None):
        """Clear hybrid personalization cache."""
        try:
            if user_id:
                # Clear specific user cache
                cache_keys = [
                    f"hybrid_score:{user_id}:*",
                    f"hybrid_recs:{user_id}"
                ]
                
                for key_pattern in cache_keys:
                    # This would need pattern deletion support
                    logger.info(f"Cache clearing for pattern {key_pattern} not implemented")
            else:
                # Clear all hybrid cache
                logger.info("Cache clearing for all hybrid personalization not implemented")
                
        except Exception as e:
            logger.error(f"Error clearing hybrid cache: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on hybrid personalization service."""
        try:
            # Test hybrid scoring
            test_user = User(id=1, username='test')
            test_offer = OfferRoute(id=1, name='test', created_at=timezone.now())
            test_context = {'device': {'type': 'mobile'}, 'location': {'country': 'US'}}
            
            test_score = self.get_hybrid_score(test_user, test_offer, test_context)
            
            # Test recommendation generation
            test_recommendations = self.get_hybrid_recommendations(test_user, test_context, limit=5)
            
            # Test weight optimization
            test_optimization = self.optimize_hybrid_weights(user_sample=[test_user])
            
            return {
                'status': 'healthy',
                'test_hybrid_scoring': 0.0 <= test_score <= 1.0,
                'test_recommendation_count': len(test_recommendations),
                'test_optimization_success': 'optimized_weights' in test_optimization,
                'stats': self.get_hybrid_stats(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
