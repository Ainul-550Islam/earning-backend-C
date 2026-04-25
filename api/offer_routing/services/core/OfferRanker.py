"""
Offer Ranker Service

Sorts scored offers and applies diversity rules to ensure
optimal offer presentation and user experience.
"""

import logging
import random
from typing import Dict, List, Any, Optional, Tuple
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Count
from django.core.cache import cache
from ...models import (
    OfferRoute, UserOfferHistory, OfferAffinityScore,
    UserPreferenceVector, RoutingDecisionLog
)
from ...choices import RoutingDecisionReason
from ...constants import (
    MAX_OFFERS_PER_REQUEST, DIVERSITY_THRESHOLD,
    RANKING_CACHE_TIMEOUT, MIN_OFFERS_FOR_DIVERSITY
)
from ...exceptions import RankingError, ConfigurationError
from ...utils import calculate_diversity_score, get_user_recent_offers

User = get_user_model()
logger = logging.getLogger(__name__)


class OfferRanker:
    """
    Service for ranking offers based on scores and applying diversity rules.
    
    Ranking algorithm considers:
    - Base scores from OfferScorer
    - Diversity (avoid showing similar offers)
    - User history (avoid repetition)
    - Business rules (featured offers, exclusives)
    - Performance metrics (CTR, conversion rates)
    
    Performance target: <5ms for ranking 50 offers
    """
    
    def __init__(self):
        self.ranking_cache = {}
        self.diversity_cache = {}
        self.ranking_stats = {
            'total_rankings': 0,
            'cache_hits': 0,
            'avg_time_ms': 0,
            'diversity_applications': 0,
            'repetition_prevented': 0
        }
    
    def rank_offers(self, scored_offers: List[Dict[str, Any]], 
                     user: User, context: Dict[str, Any], 
                     max_offers: int = None) -> List[Dict[str, Any]]:
        """
        Rank offers based on scores and apply diversity rules.
        
        Args:
            scored_offers: List of offers with scores from OfferScorer
            user: User object
            context: User context
            max_offers: Maximum number of offers to return
            
        Returns:
            Ranked list of offers with final scores and metadata
        """
        try:
            start_time = timezone.now()
            
            # Set default max_offers
            if max_offers is None:
                max_offers = MAX_OFFERS_PER_REQUEST
            
            # Check cache first
            cache_key = self._get_ranking_cache_key(scored_offers, user, context, max_offers)
            if cache_key in self.ranking_cache:
                self.ranking_stats['cache_hits'] += 1
                return self.ranking_cache[cache_key]
            
            # Filter out offers user has seen recently
            filtered_offers = self._filter_recent_offers(scored_offers, user)
            
            # Apply business rules and adjustments
            adjusted_offers = self._apply_business_ranking_rules(filtered_offers, user, context)
            
            # Apply diversity rules
            diversified_offers = self._apply_diversity_rules(adjusted_offers, user, context)
            
            # Final ranking and selection
            final_offers = self._final_ranking(diversified_offers, user, context, max_offers)
            
            # Add ranking metadata
            final_offers = self._add_ranking_metadata(final_offers, user, context)
            
            # Cache result
            self.ranking_cache[cache_key] = final_offers
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_ranking_stats(elapsed_ms)
            
            return final_offers
            
        except Exception as e:
            logger.error(f"Error ranking offers for user {user.id}: {e}")
            # Return basic ranking as fallback
            return self._fallback_ranking(scored_offers, max_offers)
    
    def _get_ranking_cache_key(self, scored_offers: List[Dict[str, Any]], 
                                user: User, context: Dict[str, Any], 
                                max_offers: int) -> str:
        """Generate cache key for ranking."""
        # Create a hash of offer IDs and scores
        offer_ids = [str(offer_data['offer'].id) for offer_data in scored_offers[:10]]
        offer_scores = [str(offer_data['score']) for offer_data in scored_offers[:10]]
        
        key_fields = [
            user.id,
            ':'.join(offer_ids),
            ':'.join(offer_scores),
            str(context.get('device', {}).get('type', '')),
            str(context.get('location', {}).get('country', '')),
            str(timezone.now().hour),
            str(max_offers)
        ]
        
        return f"rank:{':'.join(key_fields)}"
    
    def _filter_recent_offers(self, scored_offers: List[Dict[str, Any]], 
                             user: User) -> List[Dict[str, Any]]:
        """Filter out offers user has seen recently."""
        try:
            # Get offers user has seen in the last 24 hours
            recent_cutoff = timezone.now() - timezone.timedelta(hours=24)
            recent_offer_ids = UserOfferHistory.objects.filter(
                user=user,
                viewed_at__gte=recent_cutoff
            ).values_list('offer_id', flat=True)
            
            # Filter out recent offers
            filtered_offers = []
            for offer_data in scored_offers:
                if offer_data['offer'].id not in recent_offer_ids:
                    filtered_offers.append(offer_data)
                else:
                    self.ranking_stats['repetition_prevented'] += 1
            
            # If filtering removes too many offers, relax the constraint
            if len(filtered_offers) < MIN_OFFERS_FOR_DIVERSITY:
                # Only filter out offers seen in last 6 hours
                recent_cutoff = timezone.now() - timezone.timedelta(hours=6)
                recent_offer_ids = UserOfferHistory.objects.filter(
                    user=user,
                    viewed_at__gte=recent_cutoff
                ).values_list('offer_id', flat=True)
                
                filtered_offers = []
                for offer_data in scored_offers:
                    if offer_data['offer'].id not in recent_offer_ids:
                        filtered_offers.append(offer_data)
            
            return filtered_offers
            
        except Exception as e:
            logger.error(f"Error filtering recent offers: {e}")
            return scored_offers
    
    def _apply_business_ranking_rules(self, scored_offers: List[Dict[str, Any]], 
                                      user: User, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply business rules to adjust rankings."""
        try:
            adjusted_offers = []
            
            for offer_data in scored_offers:
                offer = offer_data['offer']
                base_score = offer_data['score']
                
                # Start with base score
                adjusted_score = base_score
                
                # Apply featured offer boost
                if getattr(offer, 'is_featured', False):
                    adjusted_score *= 1.2  # 20% boost
                    offer_data['featured'] = True
                
                # Apply exclusive offer boost
                if getattr(offer, 'is_exclusive', False):
                    adjusted_score *= 1.15  # 15% boost
                    offer_data['exclusive'] = True
                
                # Apply new offer boost
                created_at = getattr(offer, 'created_at', timezone.now())
                age_days = (timezone.now() - created_at).days
                if age_days <= 3:  # New offer (3 days)
                    adjusted_score *= 1.1  # 10% boost
                    offer_data['new'] = True
                
                # Apply premium user boost
                if getattr(user, 'is_premium', False):
                    premium_offers = getattr(offer, 'premium_only', False)
                    if premium_offers:
                        adjusted_score *= 1.3  # 30% boost for premium offers
                        offer_data['premium_match'] = True
                
                # Apply location-based boost
                country = context.get('location', {}).get('country')
                offer_countries = getattr(offer, 'target_countries', [])
                if country and offer_countries and country in offer_countries:
                    adjusted_score *= 1.05  # 5% boost for geo-targeted offers
                    offer_data['geo_match'] = True
                
                # Apply device-specific boost
                device_type = context.get('device', {}).get('type')
                offer_devices = getattr(offer, 'target_devices', [])
                if device_type and offer_devices and device_type in offer_devices:
                    adjusted_score *= 1.05  # 5% boost for device-targeted offers
                    offer_data['device_match'] = True
                
                # Apply time-based boost
                current_hour = timezone.now().hour
                offer_hours = getattr(offer, 'active_hours', [])
                if not offer_hours or current_hour in offer_hours:
                    adjusted_score *= 1.03  # 3% boost for time-appropriate offers
                    offer_data['time_match'] = True
                
                # Apply performance-based boost
                performance_score = self._get_offer_performance_score(offer)
                if performance_score > 0.8:  # High-performing offer
                    adjusted_score *= 1.1  # 10% boost
                    offer_data['high_performer'] = True
                
                # Update offer data with adjusted score
                offer_data['adjusted_score'] = adjusted_score
                offer_data['business_boosts'] = {
                    'featured': getattr(offer, 'is_featured', False),
                    'exclusive': getattr(offer, 'is_exclusive', False),
                    'new': age_days <= 3,
                    'premium_match': getattr(user, 'is_premium', False) and getattr(offer, 'premium_only', False),
                    'geo_match': country and offer_countries and country in offer_countries,
                    'device_match': device_type and offer_devices and device_type in offer_devices,
                    'time_match': not offer_hours or current_hour in offer_hours,
                    'high_performer': performance_score > 0.8
                }
                
                adjusted_offers.append(offer_data)
            
            return adjusted_offers
            
        except Exception as e:
            logger.error(f"Error applying business ranking rules: {e}")
            return scored_offers
    
    def _get_offer_performance_score(self, offer: OfferRoute) -> float:
        """Get performance score for an offer."""
        try:
            # Get recent performance data
            recent_cutoff = timezone.now() - timezone.timedelta(days=7)
            performance_data = RoutingDecisionLog.objects.filter(
                offer=offer,
                created_at__gte=recent_cutoff
            ).aggregate(
                total_impressions=Count('id'),
                total_clicks=Count('id', filter=Q(score__gt=0)),
                total_conversions=Count('id', filter=Q(reason='conversion'))
            )
            
            total_impressions = performance_data['total_impressions']
            if total_impressions == 0:
                return 0.5  # Default score for new offers
            
            # Calculate performance metrics
            click_rate = performance_data['total_clicks'] / total_impressions
            conversion_rate = performance_data['total_conversions'] / total_impressions
            
            # Combine metrics into performance score
            performance_score = (click_rate * 0.6) + (conversion_rate * 0.4)
            
            return min(1.0, max(0.0, performance_score))
            
        except Exception as e:
            logger.error(f"Error getting performance score: {e}")
            return 0.5
    
    def _apply_diversity_rules(self, scored_offers: List[Dict[str, Any]], 
                               user: User, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply diversity rules to ensure varied offer selection."""
        try:
            if len(scored_offers) < MIN_OFFERS_FOR_DIVERSITY:
                return scored_offers
            
            # Get user preferences for diversity calculation
            user_preferences = self._get_user_diversity_preferences(user)
            
            # Group offers by category
            category_groups = self._group_offers_by_category(scored_offers)
            
            # Apply diversity algorithm
            diversified_offers = []
            used_categories = set()
            
            # First, add top offers from different categories
            for category, offers in category_groups.items():
                if len(used_categories) >= 3:  # Limit to 3 categories initially
                    break
                
                # Sort offers within category by adjusted score
                category_offers = sorted(offers, key=lambda x: x['adjusted_score'], reverse=True)
                
                # Take top offer from this category
                if category_offers:
                    top_offer = category_offers[0]
                    top_offer['diversity_category'] = category
                    diversified_offers.append(top_offer)
                    used_categories.add(category)
            
            # Fill remaining slots with highest scoring offers
            remaining_offers = []
            for offer_data in scored_offers:
                offer_category = self._get_offer_category(offer_data['offer'])
                if offer_category not in used_categories:
                    remaining_offers.append(offer_data)
            
            # Sort remaining offers by score
            remaining_offers.sort(key=lambda x: x['adjusted_score'], reverse=True)
            
            # Add remaining offers up to diversity threshold
            slots_remaining = max(0, len(scored_offers) - len(diversified_offers))
            for i, offer_data in enumerate(remaining_offers[:slots_remaining]):
                offer_category = self._get_offer_category(offer_data['offer'])
                offer_data['diversity_category'] = offer_category
                diversified_offers.append(offer_data)
                used_categories.add(offer_category)
            
            # Calculate diversity score
            diversity_score = self._calculate_diversity_score(diversified_offers)
            
            # Update stats
            self.ranking_stats['diversity_applications'] += 1
            
            # Add diversity metadata
            for offer_data in diversified_offers:
                offer_data['diversity_score'] = diversity_score
                offer_data['diversity_applied'] = True
            
            return diversified_offers
            
        except Exception as e:
            logger.error(f"Error applying diversity rules: {e}")
            return scored_offers
    
    def _get_user_diversity_preferences(self, user: User) -> Dict[str, Any]:
        """Get user preferences for diversity calculation."""
        try:
            # Get user's preference vector
            preference_vector = UserPreferenceVector.objects.filter(user=user).first()
            
            if not preference_vector:
                return {'categories': {}, 'weights': {}}
            
            return {
                'categories': preference_vector.vector,
                'weights': preference_vector.category_weights
            }
            
        except Exception as e:
            logger.error(f"Error getting user diversity preferences: {e}")
            return {'categories': {}, 'weights': {}}
    
    def _group_offers_by_category(self, scored_offers: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group offers by category."""
        category_groups = {}
        
        for offer_data in scored_offers:
            category = self._get_offer_category(offer_data['offer'])
            
            if category not in category_groups:
                category_groups[category] = []
            
            category_groups[category].append(offer_data)
        
        return category_groups
    
    def _get_offer_category(self, offer: OfferRoute) -> str:
        """Get category for an offer."""
        return getattr(offer, 'category', 'general')
    
    def _calculate_diversity_score(self, offers: List[Dict[str, Any]]) -> float:
        """Calculate diversity score for a list of offers."""
        try:
            if len(offers) <= 1:
                return 0.0
            
            # Count unique categories
            categories = [self._get_offer_category(offer_data['offer']) for offer_data in offers]
            unique_categories = len(set(categories))
            
            # Calculate category distribution entropy
            category_counts = {}
            for category in categories:
                category_counts[category] = category_counts.get(category, 0) + 1
            
            # Calculate entropy
            total_offers = len(offers)
            entropy = 0.0
            for count in category_counts.values():
                if count > 0:
                    probability = count / total_offers
                    entropy -= probability * math.log2(probability)
            
            # Normalize entropy to 0-1 range
            max_entropy = math.log2(min(unique_categories, len(offers)))
            normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0
            
            # Combine category diversity with entropy
            category_diversity = unique_categories / len(offers)
            diversity_score = (category_diversity * 0.6) + (normalized_entropy * 0.4)
            
            return min(1.0, max(0.0, diversity_score))
            
        except Exception as e:
            logger.error(f"Error calculating diversity score: {e}")
            return 0.5
    
    def _final_ranking(self, diversified_offers: List[Dict[str, Any]], 
                        user: User, context: Dict[str, Any], 
                        max_offers: int) -> List[Dict[str, Any]]:
        """Apply final ranking and selection logic."""
        try:
            # Sort by adjusted score (primary) and diversity score (secondary)
            sorted_offers = sorted(
                diversified_offers,
                key=lambda x: (x['adjusted_score'], x.get('diversity_score', 0)),
                reverse=True
            )
            
            # Apply final business rules
            final_offers = []
            premium_slots = 3 if getattr(user, 'is_premium', False) else 1
            
            for i, offer_data in enumerate(sorted_offers):
                # Check premium slot allocation
                if i < premium_slots:
                    offer_data['premium_slot'] = True
                else:
                    offer_data['premium_slot'] = False
                
                # Apply final position adjustments
                position = i + 1
                offer_data['final_position'] = position
                
                # Apply position-based scoring decay
                position_decay = 1.0 - (position - 1) * 0.02  # 2% decay per position
                offer_data['position_adjusted_score'] = offer_data['adjusted_score'] * position_decay
                
                final_offers.append(offer_data)
            
            # Limit to max_offers
            return final_offers[:max_offers]
            
        except Exception as e:
            logger.error(f"Error in final ranking: {e}")
            return diversified_offers[:max_offers]
    
    def _add_ranking_metadata(self, offers: List[Dict[str, Any]], 
                               user: User, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Add metadata to ranked offers."""
        try:
            for i, offer_data in enumerate(offers):
                # Add ranking metadata
                offer_data['rank_metadata'] = {
                    'position': i + 1,
                    'total_offers': len(offers),
                    'ranking_timestamp': timezone.now().isoformat(),
                    'user_id': user.id,
                    'context_hash': hash(str(context))[:8],
                    'ranking_version': '1.0'
                }
                
                # Add quality indicators
                offer_data['quality_indicators'] = {
                    'has_business_boosts': any(offer_data['business_boosts'].values()),
                    'diversity_applied': offer_data.get('diversity_applied', False),
                    'premium_slot': offer_data.get('premium_slot', False),
                    'featured': offer_data.get('featured', False),
                    'exclusive': offer_data.get('exclusive', False),
                    'new': offer_data.get('new', False)
                }
                
                # Add performance predictions
                offer_data['performance_predictions'] = {
                    'expected_ctr': self._predict_ctr(offer_data, user, context),
                    'expected_conversion_rate': self._predict_conversion_rate(offer_data, user, context),
                    'expected_revenue': self._predict_revenue(offer_data, user, context)
                }
            
            return offers
            
        except Exception as e:
            logger.error(f"Error adding ranking metadata: {e}")
            return offers
    
    def _predict_ctr(self, offer_data: Dict[str, Any], user: User, 
                      context: Dict[str, Any]) -> float:
        """Predict click-through rate for an offer."""
        try:
            base_score = offer_data['adjusted_score']
            
            # Convert score to CTR prediction
            # This would use a trained model, for now use simple mapping
            if base_score > 0.9:
                return 0.15  # 15% CTR
            elif base_score > 0.8:
                return 0.12  # 12% CTR
            elif base_score > 0.7:
                return 0.10  # 10% CTR
            elif base_score > 0.6:
                return 0.08  # 8% CTR
            elif base_score > 0.5:
                return 0.06  # 6% CTR
            else:
                return 0.04  # 4% CTR
                
        except Exception as e:
            logger.error(f"Error predicting CTR: {e}")
            return 0.05  # Default CTR
    
    def _predict_conversion_rate(self, offer_data: Dict[str, Any], 
                                user: User, context: Dict[str, Any]) -> float:
        """Predict conversion rate for an offer."""
        try:
            base_score = offer_data['adjusted_score']
            
            # Convert score to conversion rate prediction
            # This would use a trained model, for now use simple mapping
            if base_score > 0.9:
                return 0.08  # 8% conversion rate
            elif base_score > 0.8:
                return 0.06  # 6% conversion rate
            elif base_score > 0.7:
                return 0.05  # 5% conversion rate
            elif base_score > 0.6:
                return 0.04  # 4% conversion rate
            elif base_score > 0.5:
                return 0.03  # 3% conversion rate
            else:
                return 0.02  # 2% conversion rate
                
        except Exception as e:
            logger.error(f"Error predicting conversion rate: {e}")
            return 0.03  # Default conversion rate
    
    def _predict_revenue(self, offer_data: Dict[str, Any], 
                         user: User, context: Dict[str, Any]) -> float:
        """Predict expected revenue for an offer."""
        try:
            ctr = self._predict_ctr(offer_data, user, context)
            conversion_rate = self._predict_conversion_rate(offer_data, user, context)
            
            # Get expected conversion value
            offer = offer_data['offer']
            expected_value = getattr(offer, 'expected_conversion_value', 10.0)
            
            # Calculate expected revenue per impression
            expected_revenue = ctr * conversion_rate * expected_value
            
            return expected_revenue
            
        except Exception as e:
            logger.error(f"Error predicting revenue: {e}")
            return 0.5  # Default expected revenue
    
    def _fallback_ranking(self, scored_offers: List[Dict[str, Any]], 
                           max_offers: int) -> List[Dict[str, Any]]:
        """Fallback ranking method when main ranking fails."""
        try:
            # Sort by base score
            sorted_offers = sorted(scored_offers, key=lambda x: x['score'], reverse=True)
            
            # Add basic metadata
            for i, offer_data in enumerate(sorted_offers[:max_offers]):
                offer_data['final_position'] = i + 1
                offer_data['fallback_ranking'] = True
                offer_data['adjusted_score'] = offer_data['score']
            
            return sorted_offers[:max_offers]
            
        except Exception as e:
            logger.error(f"Error in fallback ranking: {e}")
            return []
    
    def _update_ranking_stats(self, elapsed_ms: float):
        """Update ranking performance statistics."""
        self.ranking_stats['total_rankings'] += 1
        
        # Update average time
        current_avg = self.ranking_stats['avg_time_ms']
        total_rankings = self.ranking_stats['total_rankings']
        self.ranking_stats['avg_time_ms'] = (
            (current_avg * (total_rankings - 1) + elapsed_ms) / total_rankings
        )
    
    def get_ranking_stats(self) -> Dict[str, Any]:
        """Get ranking performance statistics."""
        return {
            'total_rankings': self.ranking_stats['total_rankings'],
            'cache_hits': self.ranking_stats['cache_hits'],
            'cache_hit_rate': (
                self.ranking_stats['cache_hits'] / 
                max(1, self.ranking_stats['total_rankings'])
            ),
            'cache_size': len(self.ranking_cache),
            'avg_time_ms': self.ranking_stats['avg_time_ms'],
            'diversity_applications': self.ranking_stats['diversity_applications'],
            'repetition_prevented': self.ranking_stats['repetition_prevented']
        }
    
    def clear_cache(self):
        """Clear ranking cache."""
        self.ranking_cache.clear()
        self.diversity_cache.clear()
        logger.info("Offer ranking cache cleared")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on offer ranker."""
        try:
            # Test basic ranking
            test_offers = [
                {'offer': type('MockOffer', (), {'id': 1, 'category': 'tech'}), 'score': 0.8},
                {'offer': type('MockOffer', (), {'id': 2, 'category': 'fashion'}), 'score': 0.7},
                {'offer': type('MockOffer', (), {'id': 3, 'category': 'tech'}), 'score': 0.6}
            ]
            test_user = User(id=1, username='test')
            test_context = {'device': {'type': 'mobile'}, 'location': {'country': 'US'}}
            
            # Test ranking
            ranked_offers = self.rank_offers(test_offers, test_user, test_context, max_offers=5)
            
            return {
                'status': 'healthy',
                'test_ranking_count': len(ranked_offers),
                'cache_size': len(self.ranking_cache),
                'stats': self.get_ranking_stats(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
