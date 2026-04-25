"""
Offer Scorer Service

Scores each eligible offer based on EPC × CR × relevance × freshness
and other factors to determine which offers should be shown first.
"""

import logging
import math
from typing import Dict, List, Any, Optional, Tuple
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Avg, Max, Min, Count, Q
from django.core.cache import cache
from decimal import Decimal
from ...models import (
    OfferRoute, OfferScore, OfferScoreConfig, GlobalOfferRank,
    UserOfferHistory, OfferAffinityScore, UserPreferenceVector
)
from ...choices import PersonalizationAlgorithm
from ...constants import (
    DEFAULT_EPC_WEIGHT, DEFAULT_CR_WEIGHT, DEFAULT_RELEVANCE_WEIGHT,
    DEFAULT_FRESHNESS_WEIGHT, SCORE_CACHE_TIMEOUT
)
from ...exceptions import ScoringError, ConfigurationError
from ...utils import calculate_epc, calculate_cr, get_user_affinity

User = get_user_model()
logger = logging.getLogger(__name__)


class OfferScorer:
    """
    Service for calculating and managing offer scores.
    
    Calculates comprehensive scores for offers based on:
    - EPC (Earnings Per Click)
    - CR (Conversion Rate)
    - Relevance (user-offer match)
    - Freshness (how recent the offer is)
    - Personalization factors
    - Business rules
    
    Performance target: <10ms per offer scoring
    """
    
    def __init__(self):
        self.score_cache = {}
        self.config_cache = {}
        self.scoring_stats = {
            'total_scores': 0,
            'cache_hits': 0,
            'avg_time_ms': 0,
            'config_updates': 0
        }
    
    def score_offer(self, offer: OfferRoute, user: User, 
                   context: Dict[str, Any], route: OfferRoute = None) -> float:
        """
        Calculate comprehensive score for an offer.
        
        Args:
            offer: Offer to score
            user: User object
            context: User context (device, location, time, etc.)
            route: Route that contains the offer
            
        Returns:
            Score between 0.0 and 1.0 (higher is better)
        """
        try:
            start_time = timezone.now()
            
            # Check cache first
            cache_key = self._get_score_cache_key(offer, user, context)
            if cache_key in self.score_cache:
                self.scoring_stats['cache_hits'] += 1
                return self.score_cache[cache_key]
            
            # Get scoring configuration
            config = self._get_scoring_config(offer, user)
            
            # Calculate individual components
            epc_score = self._calculate_epc_score(offer, user, config)
            cr_score = self._calculate_cr_score(offer, user, config)
            relevance_score = self._calculate_relevance_score(offer, user, context, config)
            freshness_score = self._calculate_freshness_score(offer, config)
            personalization_score = self._calculate_personalization_score(offer, user, context, config)
            
            # Apply weights and calculate final score
            final_score = self._apply_weights(
                epc_score, cr_score, relevance_score, freshness_score,
                personalization_score, config
            )
            
            # Apply business rules and adjustments
            final_score = self._apply_business_rules(final_score, offer, user, context)
            
            # Cache result
            self.score_cache[cache_key] = final_score
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_scoring_stats(elapsed_ms)
            
            # Save score to database
            self._save_offer_score(offer, user, final_score, config)
            
            return final_score
            
        except Exception as e:
            logger.error(f"Error scoring offer {offer.id} for user {user.id}: {e}")
            return 0.0
    
    def _get_score_cache_key(self, offer: OfferRoute, user: User, 
                             context: Dict[str, Any]) -> str:
        """Generate cache key for offer scoring."""
        # Include user, offer, and key context fields
        key_fields = [
            str(offer.id),
            str(user.id),
            str(context.get('device', {}).get('type', '')),
            str(context.get('location', {}).get('country', '')),
            str(timezone.now().hour),
            str(timezone.now().date())
        ]
        return f"score:{':'.join(key_fields)}"
    
    def _get_scoring_config(self, offer: OfferRoute, user: User) -> OfferScoreConfig:
        """Get scoring configuration for an offer and user."""
        # Try to get from cache first
        cache_key = f"config:{offer.id}:{user.id}"
        if cache_key in self.config_cache:
            return self.config_cache[cache_key]
        
        # Get from database
        try:
            config = OfferScoreConfig.objects.filter(
                offer=offer,
                tenant=user
            ).first()
            
            if not config:
                # Create default config
                config = self._create_default_config(offer, user)
            
            # Cache config
            self.config_cache[cache_key] = config
            
            return config
            
        except Exception as e:
            logger.error(f"Error getting scoring config for offer {offer.id}: {e}")
            # Return default config
            return self._get_default_config()
    
    def _create_default_config(self, offer: OfferRoute, user: User) -> OfferScoreConfig:
        """Create default scoring configuration."""
        return OfferScoreConfig.objects.create(
            offer=offer,
            tenant=user,
            algorithm='weighted',
            epc_weight=DEFAULT_EPC_WEIGHT,
            cr_weight=DEFAULT_CR_WEIGHT,
            relevance_weight=DEFAULT_RELEVANCE_WEIGHT,
            freshness_weight=DEFAULT_FRESHNESS_WEIGHT,
            personalization_weight=0.2,
            min_epc=0.0,
            max_epc=10.0,
            min_cr=0.0,
            max_cr=1.0,
            min_relevance=0.0,
            max_relevance=1.0,
            personalization_enabled=True,
            use_historical_data=True,
            historical_weight_days=90,
            boost_new_offers=True,
            new_offer_boost_days=7,
            new_offer_boost_factor=1.5,
            is_active=True
        )
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default scoring configuration as dict."""
        return {
            'epc_weight': DEFAULT_EPC_WEIGHT,
            'cr_weight': DEFAULT_CR_WEIGHT,
            'relevance_weight': DEFAULT_RELEVANCE_WEIGHT,
            'freshness_weight': DEFAULT_FRESHNESS_WEIGHT,
            'personalization_weight': 0.2,
            'min_epc': 0.0,
            'max_epc': 10.0,
            'min_cr': 0.0,
            'max_cr': 1.0,
            'min_relevance': 0.0,
            'max_relevance': 1.0,
            'personalization_enabled': True,
            'boost_new_offers': True,
            'new_offer_boost_days': 7,
            'new_offer_boost_factor': 1.5
        }
    
    def _calculate_epc_score(self, offer: OfferRoute, user: User, 
                            config: Any) -> float:
        """Calculate EPC (Earnings Per Click) score component."""
        try:
            # Get historical EPC for this offer
            epc_data = self._get_offer_epc_data(offer, user)
            
            if not epc_data or epc_data['epc'] <= 0:
                return 0.0
            
            epc = epc_data['epc']
            
            # Normalize EPC to 0-1 range
            min_epc = getattr(config, 'min_epc', 0.0)
            max_epc = getattr(config, 'max_epc', 10.0)
            
            if max_epc <= min_epc:
                return 0.0
            
            normalized_epc = min(1.0, max(0.0, (epc - min_epc) / (max_epc - min_epc)))
            
            # Apply logarithmic scaling for better distribution
            if normalized_epc > 0:
                scaled_epc = math.log(normalized_epc * 9 + 1) / math.log(10)
            else:
                scaled_epc = 0.0
            
            return scaled_epc
            
        except Exception as e:
            logger.error(f"Error calculating EPC score for offer {offer.id}: {e}")
            return 0.0
    
    def _get_offer_epc_data(self, offer: OfferRoute, user: User) -> Optional[Dict[str, Any]]:
        """Get EPC data for an offer."""
        try:
            # Get from global ranks first
            global_rank = GlobalOfferRank.objects.filter(
                offer=offer
            ).order_by('-rank_date').first()
            
            if global_rank:
                return {
                    'epc': float(global_rank.epc),
                    'source': 'global',
                    'date': global_rank.rank_date
                }
            
            # Calculate from user history
            history_data = UserOfferHistory.objects.filter(
                offer=offer,
                completed_at__isnull=False
            ).aggregate(
                total_revenue=Avg('conversion_value'),
                total_clicks=Count('id', filter=Q(clicked_at__isnull=False))
            )
            
            if history_data['total_clicks'] > 0 and history_data['total_revenue']:
                epc = history_data['total_revenue'] / history_data['total_clicks']
                return {
                    'epc': epc,
                    'source': 'calculated',
                    'date': timezone.now().date()
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting EPC data for offer {offer.id}: {e}")
            return None
    
    def _calculate_cr_score(self, offer: OfferRoute, user: User, 
                           config: Any) -> float:
        """Calculate CR (Conversion Rate) score component."""
        try:
            # Get historical CR for this offer
            cr_data = self._get_offer_cr_data(offer, user)
            
            if not cr_data or cr_data['cr'] <= 0:
                return 0.0
            
            cr = cr_data['cr']
            
            # Normalize CR to 0-1 range
            min_cr = getattr(config, 'min_cr', 0.0)
            max_cr = getattr(config, 'max_cr', 1.0)
            
            if max_cr <= min_cr:
                return 0.0
            
            normalized_cr = min(1.0, max(0.0, (cr - min_cr) / (max_cr - min_cr)))
            
            # Apply square root scaling for better distribution
            scaled_cr = math.sqrt(normalized_cr)
            
            return scaled_cr
            
        except Exception as e:
            logger.error(f"Error calculating CR score for offer {offer.id}: {e}")
            return 0.0
    
    def _get_offer_cr_data(self, offer: OfferRoute, user: User) -> Optional[Dict[str, Any]]:
        """Get CR data for an offer."""
        try:
            # Get from global ranks first
            global_rank = GlobalOfferRank.objects.filter(
                offer=offer
            ).order_by('-rank_date').first()
            
            if global_rank:
                return {
                    'cr': float(global_rank.conversion_rate) / 100.0,  # Convert from percentage
                    'source': 'global',
                    'date': global_rank.rank_date
                }
            
            # Calculate from user history
            history_data = UserOfferHistory.objects.filter(
                offer=offer,
                viewed_at__isnull=False
            ).aggregate(
                total_views=Count('id', filter=Q(viewed_at__isnull=False)),
                total_conversions=Count('id', filter=Q(completed_at__isnull=False))
            )
            
            if history_data['total_views'] > 0:
                cr = history_data['total_conversions'] / history_data['total_views']
                return {
                    'cr': cr,
                    'source': 'calculated',
                    'date': timezone.now().date()
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting CR data for offer {offer.id}: {e}")
            return None
    
    def _calculate_relevance_score(self, offer: OfferRoute, user: User, 
                                 context: Dict[str, Any], config: Any) -> float:
        """Calculate relevance score based on user preferences and offer attributes."""
        try:
            # Get user preference vector
            preference_vector = self._get_user_preference_vector(user)
            
            if not preference_vector:
                return 0.5  # Default relevance
            
            # Get offer attributes
            offer_attributes = self._get_offer_attributes(offer)
            
            # Calculate category relevance
            category_relevance = self._calculate_category_relevance(
                preference_vector, offer_attributes
            )
            
            # Calculate contextual relevance
            contextual_relevance = self._calculate_contextual_relevance(
                offer, user, context
            )
            
            # Combine relevance scores
            relevance_score = (category_relevance * 0.7) + (contextual_relevance * 0.3)
            
            return min(1.0, max(0.0, relevance_score))
            
        except Exception as e:
            logger.error(f"Error calculating relevance score for offer {offer.id}: {e}")
            return 0.5
    
    def _get_user_preference_vector(self, user: User) -> Optional[UserPreferenceVector]:
        """Get user preference vector."""
        try:
            return UserPreferenceVector.objects.filter(user=user).first()
        except Exception as e:
            logger.error(f"Error getting preference vector for user {user.id}: {e}")
            return None
    
    def _get_offer_attributes(self, offer: OfferRoute) -> Dict[str, Any]:
        """Get offer attributes for relevance calculation."""
        # This would extract offer attributes
        # For now, return basic attributes
        return {
            'category': getattr(offer, 'category', 'general'),
            'tags': getattr(offer, 'tags', []),
            'price_range': getattr(offer, 'price_range', 'medium'),
            'target_audience': getattr(offer, 'target_audience', 'general')
        }
    
    def _calculate_category_relevance(self, preference_vector: UserPreferenceVector, 
                                   offer_attributes: Dict[str, Any]) -> float:
        """Calculate category-based relevance."""
        try:
            category = offer_attributes.get('category', 'general')
            category_weight = preference_vector.get_category_weight(category)
            
            # Normalize to 0-1 range
            return min(1.0, max(0.0, category_weight))
            
        except Exception as e:
            logger.error(f"Error calculating category relevance: {e}")
            return 0.5
    
    def _calculate_contextual_relevance(self, offer: OfferRoute, user: User, 
                                      context: Dict[str, Any]) -> float:
        """Calculate contextual relevance based on current context."""
        try:
            relevance_score = 0.5  # Base relevance
            
            # Time-based relevance
            current_hour = timezone.now().hour
            if 6 <= current_hour <= 12:  # Morning
                relevance_score += 0.1
            elif 18 <= current_hour <= 22:  # Evening
                relevance_score += 0.1
            
            # Device-based relevance
            device_type = context.get('device', {}).get('type')
            if device_type == 'mobile':
                relevance_score += 0.05  # Mobile offers often have higher engagement
            
            # Location-based relevance
            country = context.get('location', {}).get('country')
            if country and country in ['US', 'CA', 'UK']:  # High-value markets
                relevance_score += 0.05
            
            return min(1.0, max(0.0, relevance_score))
            
        except Exception as e:
            logger.error(f"Error calculating contextual relevance: {e}")
            return 0.5
    
    def _calculate_freshness_score(self, offer: OfferRoute, config: Any) -> float:
        """Calculate freshness score based on offer age."""
        try:
            # Get offer creation date
            created_at = getattr(offer, 'created_at', timezone.now())
            age_days = (timezone.now() - created_at).days
            
            # Get freshness decay settings
            decay_days = getattr(config, 'freshness_decay_days', 30)
            
            # Calculate freshness score (newer offers get higher scores)
            if age_days <= 0:
                return 1.0
            
            freshness_score = math.exp(-age_days / decay_days)
            
            # Apply new offer boost if configured
            boost_new_offers = getattr(config, 'boost_new_offers', True)
            if boost_new_offers:
                new_offer_days = getattr(config, 'new_offer_boost_days', 7)
                boost_factor = getattr(config, 'new_offer_boost_factor', 1.5)
                
                if age_days <= new_offer_days:
                    freshness_score *= boost_factor
            
            return min(1.0, max(0.0, freshness_score))
            
        except Exception as e:
            logger.error(f"Error calculating freshness score for offer {offer.id}: {e}")
            return 0.5
    
    def _calculate_personalization_score(self, offer: OfferRoute, user: User, 
                                     context: Dict[str, Any], config: Any) -> float:
        """Calculate personalization score based on user behavior and preferences."""
        try:
            # Check if personalization is enabled
            personalization_enabled = getattr(config, 'personalization_enabled', True)
            if not personalization_enabled:
                return 0.5
            
            # Get user affinity scores
            affinity_scores = self._get_user_affinity_scores(user)
            
            if not affinity_scores:
                return 0.5
            
            # Get offer category
            offer_category = self._get_offer_attributes(offer).get('category', 'general')
            
            # Get affinity for offer category
            affinity_score = self._get_affinity_for_category(affinity_scores, offer_category)
            
            # Calculate collaborative filtering score
            collaborative_score = self._calculate_collaborative_score(offer, user)
            
            # Calculate content-based score
            content_score = self._calculate_content_score(offer, user)
            
            # Combine personalization scores
            personalization_weight = getattr(config, 'personalization_weight', 0.2)
            personalization_score = (
                affinity_score * 0.4 +
                collaborative_score * 0.3 +
                content_score * 0.3
            )
            
            return min(1.0, max(0.0, personalization_score))
            
        except Exception as e:
            logger.error(f"Error calculating personalization score for offer {offer.id}: {e}")
            return 0.5
    
    def _get_user_affinity_scores(self, user: User) -> List[OfferAffinityScore]:
        """Get user's affinity scores."""
        try:
            return OfferAffinityScore.objects.filter(user=user).order_by('-score')
        except Exception as e:
            logger.error(f"Error getting affinity scores for user {user.id}: {e}")
            return []
    
    def _get_affinity_for_category(self, affinity_scores: List[OfferAffinityScore], 
                                  category: str) -> float:
        """Get affinity score for a specific category."""
        for affinity in affinity_scores:
            if affinity.category == category:
                return float(affinity.score) / 100.0  # Normalize to 0-1
        return 0.5  # Default affinity
    
    def _calculate_collaborative_score(self, offer: OfferRoute, user: User) -> float:
        """Calculate collaborative filtering score."""
        try:
            # Find similar users who liked this offer
            similar_users = self._find_similar_users(user)
            
            if not similar_users:
                return 0.5
            
            # Calculate average score from similar users
            total_score = 0.0
            count = 0
            
            for similar_user in similar_users:
                user_score = OfferScore.objects.filter(
                    offer=offer,
                    user=similar_user
                ).first()
                
                if user_score:
                    total_score += float(user_score.score) / 100.0
                    count += 1
            
            if count > 0:
                return total_score / count
            
            return 0.5
            
        except Exception as e:
            logger.error(f"Error calculating collaborative score: {e}")
            return 0.5
    
    def _find_similar_users(self, user: User, limit: int = 10) -> List[User]:
        """Find users similar to the given user."""
        try:
            # This would implement user similarity algorithm
            # For now, return users with similar preferences
            user_preferences = UserPreferenceVector.objects.filter(user=user).first()
            
            if not user_preferences:
                return []
            
            # Find users with similar category weights
            similar_users = UserPreferenceVector.objects.filter(
                user__is_active=True
            ).exclude(user=user)
            
            # Calculate similarity and return top similar users
            similar_user_list = []
            for other_user_pref in similar_users[:limit]:
                similarity = user_preferences.calculate_similarity(other_user_pref.vector)
                if similarity > 0.3:  # Similarity threshold
                    similar_user_list.append(other_user_pref.user)
            
            return similar_user_list
            
        except Exception as e:
            logger.error(f"Error finding similar users: {e}")
            return []
    
    def _calculate_content_score(self, offer: OfferRoute, user: User) -> float:
        """Calculate content-based filtering score."""
        try:
            # Get user's historical interactions
            user_history = UserOfferHistory.objects.filter(
                user=user,
                completed_at__isnull=False
            ).order_by('-completed_at')[:50]
            
            if not user_history:
                return 0.5
            
            # Get offer attributes
            offer_attributes = self._get_offer_attributes(offer)
            
            # Calculate content similarity based on historical offers
            total_similarity = 0.0
            count = 0
            
            for history_item in user_history:
                historical_offer = history_item.offer
                historical_attributes = self._get_offer_attributes(historical_offer)
                
                similarity = self._calculate_content_similarity(
                    offer_attributes, historical_attributes
                )
                
                total_similarity += similarity
                count += 1
            
            if count > 0:
                return total_similarity / count
            
            return 0.5
            
        except Exception as e:
            logger.error(f"Error calculating content score: {e}")
            return 0.5
    
    def _calculate_content_similarity(self, offer1_attrs: Dict[str, Any], 
                                   offer2_attrs: Dict[str, Any]) -> float:
        """Calculate similarity between two offers based on attributes."""
        try:
            similarity_score = 0.0
            
            # Category similarity
            if offer1_attrs.get('category') == offer2_attrs.get('category'):
                similarity_score += 0.4
            
            # Tag similarity
            tags1 = set(offer1_attrs.get('tags', []))
            tags2 = set(offer2_attrs.get('tags', []))
            
            if tags1 and tags2:
                tag_similarity = len(tags1 & tags2) / len(tags1 | tags2)
                similarity_score += tag_similarity * 0.3
            
            # Price range similarity
            if offer1_attrs.get('price_range') == offer2_attrs.get('price_range'):
                similarity_score += 0.2
            
            # Target audience similarity
            if offer1_attrs.get('target_audience') == offer2_attrs.get('target_audience'):
                similarity_score += 0.1
            
            return min(1.0, max(0.0, similarity_score))
            
        except Exception as e:
            logger.error(f"Error calculating content similarity: {e}")
            return 0.5
    
    def _apply_weights(self, epc_score: float, cr_score: float, 
                      relevance_score: float, freshness_score: float,
                      personalization_score: float, config: Any) -> float:
        """Apply weights to score components and calculate final score."""
        try:
            # Get weights from config
            epc_weight = getattr(config, 'epc_weight', DEFAULT_EPC_WEIGHT)
            cr_weight = getattr(config, 'cr_weight', DEFAULT_CR_WEIGHT)
            relevance_weight = getattr(config, 'relevance_weight', DEFAULT_RELEVANCE_WEIGHT)
            freshness_weight = getattr(config, 'freshness_weight', DEFAULT_FRESHNESS_WEIGHT)
            personalization_weight = getattr(config, 'personalization_weight', 0.2)
            
            # Calculate weighted sum
            final_score = (
                epc_score * epc_weight +
                cr_score * cr_weight +
                relevance_score * relevance_weight +
                freshness_score * freshness_weight +
                personalization_score * personalization_weight
            )
            
            return min(1.0, max(0.0, final_score))
            
        except Exception as e:
            logger.error(f"Error applying weights: {e}")
            return 0.5
    
    def _apply_business_rules(self, score: float, offer: OfferRoute, 
                             user: User, context: Dict[str, Any]) -> float:
        """Apply business rules and adjustments to the score."""
        try:
            adjusted_score = score
            
            # Apply user-specific adjustments
            if self._is_premium_user(user):
                adjusted_score *= 1.1  # 10% boost for premium users
            
            # Apply time-based adjustments
            current_hour = timezone.now().hour
            if 0 <= current_hour < 6:  # Late night
                adjusted_score *= 0.9  # Reduce score for late night
            
            # Apply device-specific adjustments
            device_type = context.get('device', {}).get('type')
            if device_type == 'mobile':
                adjusted_score *= 1.05  # 5% boost for mobile
            
            # Apply location-based adjustments
            country = context.get('location', {}).get('country')
            if country in ['US', 'CA', 'UK', 'AU']:  # High-value countries
                adjusted_score *= 1.1  # 10% boost for high-value countries
            
            # Apply offer-specific adjustments
            if getattr(offer, 'is_featured', False):
                adjusted_score *= 1.2  # 20% boost for featured offers
            
            if getattr(offer, 'is_exclusive', False):
                adjusted_score *= 1.15  # 15% boost for exclusive offers
            
            return min(1.0, max(0.0, adjusted_score))
            
        except Exception as e:
            logger.error(f"Error applying business rules: {e}")
            return score
    
    def _is_premium_user(self, user: User) -> bool:
        """Check if user is premium."""
        return getattr(user, 'is_premium', False)
    
    def _save_offer_score(self, offer: OfferRoute, user: User, 
                          score: float, config: Any):
        """Save offer score to database."""
        try:
            # Check if score already exists and is recent
            existing_score = OfferScore.objects.filter(
                offer=offer,
                user=user,
                scored_at__gte=timezone.now() - timezone.timedelta(hours=1)
            ).first()
            
            if existing_score:
                # Update existing score
                existing_score.score = Decimal(str(score * 100))  # Convert to 0-100 scale
                existing_score.scored_at = timezone.now()
                existing_score.save()
            else:
                # Create new score
                OfferScore.objects.create(
                    offer=offer,
                    user=user,
                    score=Decimal(str(score * 100)),  # Convert to 0-100 scale
                    epc=Decimal(str(self._get_current_epc(offer))),
                    cr=Decimal(str(self._get_current_cr(offer))),
                    relevance=Decimal(str(score)),  # Use overall score as relevance
                    freshness=Decimal(str(self._calculate_freshness_score(offer, config))),
                    personalization_score=Decimal(str(self._calculate_personalization_score(offer, user, {}, config))),
                    scored_at=timezone.now(),
                    expires_at=timezone.now() + timezone.timedelta(hours=24),
                    score_version=1
                )
                
        except Exception as e:
            logger.error(f"Error saving offer score: {e}")
    
    def _get_current_epc(self, offer: OfferRoute) -> float:
        """Get current EPC for an offer."""
        try:
            global_rank = GlobalOfferRank.objects.filter(
                offer=offer
            ).order_by('-rank_date').first()
            
            if global_rank:
                return float(global_rank.epc)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting current EPC: {e}")
            return 0.0
    
    def _get_current_cr(self, offer: OfferRoute) -> float:
        """Get current CR for an offer."""
        try:
            global_rank = GlobalOfferRank.objects.filter(
                offer=offer
            ).order_by('-rank_date').first()
            
            if global_rank:
                return float(global_rank.conversion_rate) / 100.0
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting current CR: {e}")
            return 0.0
    
    def _update_scoring_stats(self, elapsed_ms: float):
        """Update scoring performance statistics."""
        self.scoring_stats['total_scores'] += 1
        
        # Update average time
        current_avg = self.scoring_stats['avg_time_ms']
        total_scores = self.scoring_stats['total_scores']
        self.scoring_stats['avg_time_ms'] = (
            (current_avg * (total_scores - 1) + elapsed_ms) / total_scores
        )
    
    def batch_score_offers(self, offers: List[OfferRoute], user: User, 
                           context: Dict[str, Any]) -> List[Tuple[OfferRoute, float]]:
        """
        Score multiple offers efficiently.
        
        Args:
            offers: List of offers to score
            user: User object
            context: User context
            
        Returns:
            List of (offer, score) tuples
        """
        try:
            start_time = timezone.now()
            
            scored_offers = []
            
            for offer in offers:
                score = self.score_offer(offer, user, context)
                scored_offers.append((offer, score))
            
            # Sort by score (descending)
            scored_offers.sort(key=lambda x: x[1], reverse=True)
            
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            logger.debug(f"Batch scored {len(offers)} offers in {elapsed_ms:.2f}ms")
            
            return scored_offers
            
        except Exception as e:
            logger.error(f"Error in batch scoring: {e}")
            return [(offer, 0.0) for offer in offers]
    
    def clear_cache(self):
        """Clear scoring cache."""
        self.score_cache.clear()
        self.config_cache.clear()
        logger.info("Offer scoring cache cleared")
    
    def get_scoring_stats(self) -> Dict[str, Any]:
        """Get scoring performance statistics."""
        return {
            'total_scores': self.scoring_stats['total_scores'],
            'cache_hits': self.scoring_stats['cache_hits'],
            'cache_hit_rate': (
                self.scoring_stats['cache_hits'] / 
                max(1, self.scoring_stats['total_scores'])
            ),
            'cache_size': len(self.score_cache),
            'config_cache_size': len(self.config_cache),
            'avg_time_ms': self.scoring_stats['avg_time_ms'],
            'config_updates': self.scoring_stats['config_updates']
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on offer scorer."""
        try:
            # Test basic scoring
            test_user = User(id=1, username='test')
            test_offer = OfferRoute(id=1, name='test')
            test_context = {'device': {'type': 'mobile'}, 'location': {'country': 'US'}}
            
            # Test scoring
            score = self.score_offer(test_offer, test_user, test_context)
            
            return {
                'status': 'healthy',
                'test_score': score,
                'cache_size': len(self.score_cache),
                'stats': self.get_scoring_stats(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
