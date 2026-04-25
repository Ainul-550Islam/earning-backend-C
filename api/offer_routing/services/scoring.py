"""
Scoring Service for Offer Routing System

This module provides scoring functionality to calculate
offer scores based on various metrics and factors.
"""

import logging
import math
from typing import Dict, List, Any, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Avg, Count, Sum
from ..models import (
    OfferScore, OfferScoreConfig, GlobalOfferRank,
    UserOfferHistory, OfferAffinityScore
)
from ..utils import (
    calculate_score, calculate_freshness_score, calculate_cr_score,
    normalize_score, calculate_percentile_rank
)
from ..constants import (
    DEFAULT_EPC_WEIGHT, DEFAULT_CR_WEIGHT, DEFAULT_RELEVANCE_WEIGHT,
    DEFAULT_FRESHNESS_WEIGHT, SCORE_CACHE_TIMEOUT
)
from ..exceptions import ScoringError

User = get_user_model()
logger = logging.getLogger(__name__)


class OfferScoringService:
    """
    Service for calculating and managing offer scores.
    
    Provides scoring algorithms, score calculation,
    and score management functionality.
    """
    
    def __init__(self):
        self.cache_service = None
        self.affinity_service = None
        
        # Initialize services
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize scoring services."""
        try:
            from .cache import RoutingCacheService
            from .personalization import AffinityService
            
            self.cache_service = RoutingCacheService()
            self.affinity_service = AffinityService()
            
        except ImportError as e:
            logger.error(f"Failed to initialize scoring services: {e}")
            raise
    
    def calculate_offer_score(self, offer: Any, user: User, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate score for an offer for a specific user.
        
        Args:
            offer: Offer object
            user: User object
            context: User context
            
        Returns:
            Dictionary with score and components
        """
        try:
            # Get score configuration
            score_config = self._get_score_config(offer, user)
            
            # Calculate base metrics
            epc = self._calculate_epc(offer, user)
            cr = self._calculate_cr(offer, user)
            relevance = self._calculate_relevance(offer, user, context)
            freshness = self._calculate_freshness(offer, user)
            
            # Calculate personalization score
            personalization_score = self._calculate_personalization_score(offer, user, context)
            
            # Calculate weighted score
            total_score = calculate_score(
                epc=epc,
                cr=cr,
                relevance=relevance,
                freshness=freshness,
                weights={
                    'epc': score_config.epc_weight,
                    'cr': score_config.cr_weight,
                    'relevance': score_config.relevance_weight,
                    'freshness': score_config.freshness_weight
                }
            )
            
            # Apply personalization boost
            if score_config.personalization_enabled and personalization_score > 0:
                personalization_boost = personalization_score * score_config.personalization_weight
                total_score = min(total_score * (1 + personalization_boost), 100.0)
            
            # Apply new offer boost
            if score_config.boost_new_offers:
                new_offer_boost = self._calculate_new_offer_boost(offer, score_config)
                total_score = min(total_score * new_offer_boost, 100.0)
            
            # Create score data
            score_data = {
                'score': total_score,
                'epc': epc,
                'cr': cr,
                'relevance': relevance,
                'freshness': freshness,
                'personalization_score': personalization_score,
                'components': {
                    'epc_component': score_config.epc_weight,
                    'cr_component': score_config.cr_weight,
                    'relevance_component': score_config.relevance_weight,
                    'freshness_component': score_config.freshness_weight
                },
                'boosts': {
                    'personalization_boost': personalization_score * score_config.personalization_weight if score_config.personalization_enabled else 0,
                    'new_offer_boost': self._calculate_new_offer_boost(offer, score_config) - 1 if score_config.boost_new_offers else 0
                }
            }
            
            # Cache score
            self._cache_score(offer.id, user.id, score_data)
            
            # Save score to database
            self._save_score(offer, user, score_data)
            
            logger.debug(f"Calculated score {total_score:.2f} for offer {offer.id}, user {user.id}")
            return score_data
            
        except Exception as e:
            logger.error(f"Error calculating offer score: {e}")
            raise ScoringError(f"Failed to calculate score: {e}")
    
    def _get_score_config(self, offer: Any, user: User) -> OfferScoreConfig:
        """Get score configuration for offer and user."""
        try:
            # Try to get specific config
            config = OfferScoreConfig.objects.filter(
                offer=offer,
                tenant=user.tenant,
                is_active=True
            ).first()
            
            if not config:
                # Create default config
                config = OfferScoreConfig.objects.create(
                    offer=offer,
                    tenant=user.tenant,
                    epc_weight=DEFAULT_EPC_WEIGHT,
                    cr_weight=DEFAULT_CR_WEIGHT,
                    relevance_weight=DEFAULT_RELEVANCE_WEIGHT,
                    freshness_weight=DEFAULT_FRESHNESS_WEIGHT
                )
            
            return config
            
        except Exception as e:
            logger.error(f"Error getting score config: {e}")
            # Return default config
            return OfferScoreConfig(
                epc_weight=DEFAULT_EPC_WEIGHT,
                cr_weight=DEFAULT_CR_WEIGHT,
                relevance_weight=DEFAULT_RELEVANCE_WEIGHT,
                freshness_weight=DEFAULT_FRESHNESS_WEIGHT
            )
    
    def _calculate_epc(self, offer: Any, user: User) -> float:
        """Calculate EPC (Earnings Per Click) for offer."""
        try:
            # Get offer performance data
            from ..models import RoutePerformanceStat
            
            # Get recent performance stats
            recent_stats = RoutePerformanceStat.objects.filter(
                offer=offer,
                date__gte=timezone.now() - timezone.timedelta(days=30)
            ).aggregate(
                total_revenue=Sum('revenue'),
                total_clicks=Sum('clicks')
            )
            
            total_revenue = recent_stats['total_revenue'] or 0
            total_clicks = recent_stats['total_clicks'] or 0
            
            if total_clicks == 0:
                return 0.0
            
            epc = total_revenue / total_clicks
            return min(normalize_score(epc, 0, 10), 100.0)
            
        except Exception as e:
            logger.error(f"Error calculating EPC: {e}")
            return 0.0
    
    def _calculate_cr(self, offer: Any, user: User) -> float:
        """Calculate conversion rate for offer."""
        try:
            # Get user-specific conversion data
            user_history = UserOfferHistory.objects.filter(
                user=user,
                offer=offer,
                viewed_at__isnull=False
            ).aggregate(
                total_views=Count('id'),
                total_conversions=Count('id', filter=models.Q(completed_at__isnull=False))
            )
            
            total_views = user_history['total_views'] or 0
            total_conversions = user_history['total_conversions'] or 0
            
            if total_views == 0:
                # Fall back to global CR
                return self._get_global_cr(offer)
            
            cr = calculate_cr_score(total_conversions, total_views)
            return normalize_score(cr, 0, 100)
            
        except Exception as e:
            logger.error(f"Error calculating CR: {e}")
            return 0.0
    
    def _get_global_cr(self, offer: Any) -> float:
        """Get global conversion rate for offer."""
        try:
            from ..models import RoutePerformanceStat
            
            global_stats = RoutePerformanceStat.objects.filter(
                offer=offer,
                date__gte=timezone.now() - timezone.timedelta(days=30)
            ).aggregate(
                total_impressions=Sum('impressions'),
                total_conversions=Sum('conversions')
            )
            
            total_impressions = global_stats['total_impressions'] or 0
            total_conversions = global_stats['total_conversions'] or 0
            
            if total_impressions == 0:
                return 0.0
            
            cr = calculate_cr_score(total_conversions, total_impressions)
            return normalize_score(cr, 0, 100)
            
        except Exception as e:
            logger.error(f"Error getting global CR: {e}")
            return 0.0
    
    def _calculate_relevance(self, offer: Any, user: User, context: Dict[str, Any]) -> float:
        """Calculate relevance score for offer."""
        try:
            relevance_score = 0.0
            
            # Category affinity
            if hasattr(offer, 'category') and self.affinity_service:
                affinity_data = self.affinity_service.get_affinity_score(user.id, offer.category)
                if affinity_data:
                    relevance_score += affinity_data['score'] * 0.6
            
            # Contextual relevance
            contextual_score = self._calculate_contextual_relevance(offer, user, context)
            relevance_score += contextual_score * 0.4
            
            return min(relevance_score, 100.0)
            
        except Exception as e:
            logger.error(f"Error calculating relevance: {e}")
            return 0.0
    
    def _calculate_contextual_relevance(self, offer: Any, user: User, context: Dict[str, Any]) -> float:
        """Calculate contextual relevance score."""
        try:
            score = 0.0
            
            # Page relevance
            if 'page' in context:
                page_score = self._get_page_relevance(offer, context['page'])
                score += page_score * 0.5
            
            # Location relevance
            if 'location' in context:
                location_score = self._get_location_relevance(offer, context['location'])
                score += location_score * 0.3
            
            # Device relevance
            if 'device_info' in context:
                device_score = self._get_device_relevance(offer, context['device_info'])
                score += device_score * 0.2
            
            return min(score, 100.0)
            
        except Exception as e:
            logger.error(f"Error calculating contextual relevance: {e}")
            return 0.0
    
    def _get_page_relevance(self, offer: Any, page: str) -> float:
        """Get page relevance score for offer."""
        # This would implement page-specific relevance logic
        # For now, return placeholder
        return 50.0
    
    def _get_location_relevance(self, offer: Any, location: Dict[str, Any]) -> float:
        """Get location relevance score for offer."""
        # This would implement location-specific relevance logic
        # For now, return placeholder
        return 50.0
    
    def _get_device_relevance(self, offer: Any, device_info: Dict[str, Any]) -> float:
        """Get device relevance score for offer."""
        # This would implement device-specific relevance logic
        # For now, return placeholder
        return 50.0
    
    def _calculate_freshness(self, offer: Any, user: User) -> float:
        """Calculate freshness score for offer."""
        try:
            if hasattr(offer, 'created_at'):
                freshness_score = calculate_freshness_score(offer.created_at)
                return normalize_score(freshness_score, 0, 1)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating freshness: {e}")
            return 0.0
    
    def _calculate_personalization_score(self, offer: Any, user: User, context: Dict[str, Any]) -> float:
        """Calculate personalization score for offer."""
        try:
            if not self.affinity_service:
                return 0.0
            
            personalization_score = 0.0
            
            # Get user preference vector
            if hasattr(offer, 'category'):
                affinity_data = self.affinity_service.get_affinity_score(user.id, offer.category)
                if affinity_data:
                    personalization_score += affinity_data['score'] * 0.7
            
            # Get contextual signals
            contextual_score = self._get_contextual_personalization_score(user, context)
            personalization_score += contextual_score * 0.3
            
            return min(personalization_score, 100.0)
            
        except Exception as e:
            logger.error(f"Error calculating personalization score: {e}")
            return 0.0
    
    def _get_contextual_personalization_score(self, user: User, context: Dict[str, Any]) -> float:
        """Get contextual personalization score."""
        # This would implement contextual personalization logic
        # For now, return placeholder
        return 50.0
    
    def _calculate_new_offer_boost(self, offer: Any, score_config: OfferScoreConfig) -> float:
        """Calculate new offer boost factor."""
        try:
            if not hasattr(offer, 'created_at'):
                return 1.0
            
            days_since_creation = (timezone.now() - offer.created_at).days
            
            if days_since_creation <= score_config.new_offer_boost_days:
                return score_config.new_offer_boost_factor
            
            return 1.0
            
        except Exception as e:
            logger.error(f"Error calculating new offer boost: {e}")
            return 1.0
    
    def _cache_score(self, offer_id: int, user_id: int, score_data: Dict[str, Any]):
        """Cache score data."""
        try:
            if self.cache_service:
                self.cache_service.set_offer_score(offer_id, user_id, score_data)
        except Exception as e:
            logger.warning(f"Error caching score: {e}")
    
    def _save_score(self, offer: Any, user: User, score_data: Dict[str, Any]):
        """Save score to database."""
        try:
            OfferScore.objects.update_or_create(
                offer=offer,
                user=user,
                defaults={
                    'score': score_data['score'],
                    'epc': score_data['epc'],
                    'cr': score_data['cr'],
                    'relevance': score_data['relevance'],
                    'freshness': score_data['freshness'],
                    'personalization_score': score_data['personalization_score'],
                    'epc_component': score_data['components']['epc_component'],
                    'cr_component': score_data['components']['cr_component'],
                    'relevance_component': score_data['components']['relevance_component'],
                    'freshness_component': score_data['components']['freshness_component']
                }
            )
        except Exception as e:
            logger.error(f"Error saving score: {e}")
    
    def update_all_scores(self) -> int:
        """Update scores for all active offers."""
        try:
            updated_count = 0
            
            # Get all active offers
            from ..models import OfferRoute
            active_offers = OfferRoute.objects.filter(is_active=True)
            
            for offer in active_offers:
                # Get users who have seen this offer
                users = UserOfferHistory.objects.filter(
                    offer=offer
                ).values_list('user_id', flat=True).distinct()
                
                for user_id in users:
                    try:
                        user = User.objects.get(id=user_id)
                        # Calculate score (this would use context)
                        self.calculate_offer_score(offer, user, {})
                        updated_count += 1
                    except User.DoesNotExist:
                        continue
            
            logger.info(f"Updated {updated_count} offer scores")
            return updated_count
            
        except Exception as e:
            logger.error(f"Error updating all scores: {e}")
            return 0
    
    def get_cached_score(self, offer_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Get cached score."""
        try:
            if self.cache_service:
                return self.cache_service.get_offer_score(offer_id, user_id)
            return None
        except Exception as e:
            logger.error(f"Error getting cached score: {e}")
            return None
    
    def invalidate_score_cache(self, offer_id: int, user_id: int = None):
        """Invalidate score cache."""
        try:
            if self.cache_service:
                if user_id:
                    self.cache_service.delete_offer_score(offer_id, user_id)
                else:
                    # Invalidate all scores for this offer
                    # This would implement pattern-based deletion
                    pass
        except Exception as e:
            logger.error(f"Error invalidating score cache: {e}")


class OfferRankerService:
    """Service for ranking offers based on scores."""
    
    def __init__(self):
        self.scoring_service = OfferScoringService()
    
    def rank_offers_for_user(self, user: User, offers: List[Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Rank offers for a user based on scores."""
        try:
            scored_offers = []
            
            for offer in offers:
                # Calculate score
                score_data = self.scoring_service.calculate_offer_score(offer, user, context)
                
                scored_offers.append({
                    'offer': offer,
                    'score': score_data['score'],
                    'score_data': score_data,
                    'rank': 0  # Will be set after sorting
                })
            
            # Sort by score (descending)
            scored_offers.sort(key=lambda x: x['score'], reverse=True)
            
            # Set ranks
            for i, offer_data in enumerate(scored_offers):
                offer_data['rank'] = i + 1
            
            return scored_offers
            
        except Exception as e:
            logger.error(f"Error ranking offers: {e}")
            return []
    
    def update_global_rankings(self) -> int:
        """Update global offer rankings."""
        try:
            updated_count = 0
            
            # Get all offers with performance data
            from ..models import OfferRoute, RoutePerformanceStat
            
            offers = OfferRoute.objects.filter(is_active=True)
            
            for offer in offers:
                # Calculate ranking metrics
                ranking_data = self._calculate_ranking_metrics(offer)
                
                if ranking_data:
                    # Save global rank
                    GlobalOfferRank.objects.update_or_create(
                        offer=offer,
                        tenant=offer.tenant,
                        defaults=ranking_data
                    )
                    updated_count += 1
            
            logger.info(f"Updated {updated_count} global rankings")
            return updated_count
            
        except Exception as e:
            logger.error(f"Error updating global rankings: {e}")
            return 0
    
    def _calculate_ranking_metrics(self, offer: Any) -> Optional[Dict[str, Any]]:
        """Calculate ranking metrics for an offer."""
        try:
            from ..models import RoutePerformanceStat
            from datetime import timedelta
            
            # Get last 30 days of performance
            cutoff_date = timezone.now() - timedelta(days=30)
            
            stats = RoutePerformanceStat.objects.filter(
                offer=offer,
                date__gte=cutoff_date
            ).aggregate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_revenue=Sum('revenue')
            )
            
            if not stats['total_impressions']:
                return None
            
            # Calculate metrics
            total_impressions = stats['total_impressions'] or 0
            total_clicks = stats['total_clicks'] or 0
            total_conversions = stats['total_conversions'] or 0
            total_revenue = stats['total_revenue'] or 0
            
            click_through_rate = (total_clicks / total_impressions) * 100 if total_impressions > 0 else 0
            conversion_rate = (total_conversions / total_impressions) * 100 if total_impressions > 0 else 0
            average_order_value = total_revenue / total_conversions if total_conversions > 0 else 0
            epc = total_revenue / total_clicks if total_clicks > 0 else 0
            
            # Calculate rank score (weighted combination)
            rank_score = (
                (conversion_rate * 0.4) +
                (epc * 100 * 0.3) +  # EPC scaled to 0-100
                (click_through_rate * 0.2) +
                (average_order_value * 0.1)
            )
            
            return {
                'rank_date': timezone.now().date(),
                'rank_period_start': cutoff_date.date(),
                'rank_period_end': timezone.now().date(),
                'total_impressions': total_impressions,
                'total_clicks': total_clicks,
                'total_conversions': total_conversions,
                'total_revenue': total_revenue,
                'click_through_rate': click_through_rate,
                'conversion_rate': conversion_rate,
                'average_order_value': average_order_value,
                'epc': epc,
                'rank_score': min(rank_score, 100.0)
            }
            
        except Exception as e:
            logger.error(f"Error calculating ranking metrics: {e}")
            return None


# Singleton instances
scoring_service = OfferScoringService()
ranker_service = OfferRankerService()
