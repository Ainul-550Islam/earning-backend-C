"""
Network Waterfall Service for Offer Routing System

This module provides comprehensive network waterfall management,
including offer prioritization, fallback chains, and revenue optimization.
"""

import logging
import heapq
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.core.cache import cache
from django.db.models import Q, F, Sum, Avg, Count
from django.utils import timezone
from django.contrib.auth import get_user_model

from ..models import (
    OfferRoute, UserOfferHistory, RoutingDecisionLog,
    RoutingConfig, OfferRoutingCap, UserOfferCap,
    RoutePerformanceStat, RoutingInsight
)
from ..utils import get_client_ip, validate_ip_address

User = get_user_model()
logger = logging.getLogger(__name__)


class WaterfallService:
    """
    Comprehensive network waterfall service for offer routing.
    
    Manages:
    - Offer prioritization and ranking
    - Fallback chain management
    - Revenue optimization
    - Performance-based routing
    - Real-time waterfall updates
    """
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
        self.max_waterfall_depth = 10
        self.min_revenue_threshold = 0.01
        self.performance_weight = 0.7
        self.revenue_weight = 0.3
    
    def generate_waterfall(self, user_id: int, context: Dict[str, any]) -> Dict[str, any]:
        """
        Generate optimized waterfall for user.
        
        Args:
            user_id: User ID to generate waterfall for
            context: Routing context (geo, device, etc.)
            
        Returns:
            Dictionary containing waterfall data
        """
        try:
            # Get user and tenant
            user = User.objects.filter(id=user_id).first()
            if not user:
                return {'error': 'User not found'}
            
            tenant_id = user.tenant_id
            
            # Get available offers
            available_offers = self._get_available_offers(user, context)
            
            # Apply caps and filters
            filtered_offers = self._apply_caps_and_filters(available_offers, user, context)
            
            # Score and rank offers
            scored_offers = self._score_offers(filtered_offers, user, context)
            
            # Generate waterfall chain
            waterfall_chain = self._generate_waterfall_chain(scored_offers, user, context)
            
            # Apply revenue optimization
            optimized_chain = self._apply_revenue_optimization(waterfall_chain, user, context)
            
            # Cache waterfall
            cache_key = f"waterfall:user_{user_id}:{hash(str(context))}"
            cache.set(cache_key, optimized_chain, self.cache_timeout)
            
            # Log waterfall generation
            self._log_waterfall_generation(user, optimized_chain, context)
            
            logger.info(f"Waterfall generated for user {user_id}: {len(optimized_chain)} offers")
            
            return {
                'user_id': user_id,
                'waterfall_chain': optimized_chain,
                'total_offers': len(optimized_chain),
                'estimated_revenue': self._calculate_estimated_revenue(optimized_chain),
                'generation_time': timezone.now().isoformat(),
                'context': context
            }
            
        except Exception as e:
            logger.error(f"Error generating waterfall for user {user_id}: {e}")
            return {'error': str(e)}
    
    def get_waterfall_performance(self, user_id: int, time_window: int = 86400) -> Dict[str, any]:
        """
        Get waterfall performance metrics for user.
        
        Args:
            user_id: User ID
            time_window: Time window in seconds (default: 24 hours)
            
        Returns:
            Dictionary containing performance metrics
        """
        try:
            # Get recent routing decisions
            cutoff_time = timezone.now() - timedelta(seconds=time_window)
            
            decisions = RoutingDecisionLog.objects.filter(
                user_id=user_id,
                created_at__gte=cutoff_time
            ).order_by('-created_at')
            
            if not decisions.exists():
                return {
                    'user_id': user_id,
                    'time_window': time_window,
                    'total_decisions': 0,
                    'conversion_rate': 0,
                    'revenue_per_offer': 0,
                    'waterfall_efficiency': 0
                }
            
            # Calculate performance metrics
            total_decisions = decisions.count()
            conversions = UserOfferHistory.objects.filter(
                user_id=user_id,
                completed_at__gte=cutoff_time
            ).count()
            
            total_revenue = UserOfferHistory.objects.filter(
                user_id=user_id,
                completed_at__gte=cutoff_time
            ).aggregate(total_revenue=Sum('revenue'))['total_revenue'] or 0
            
            conversion_rate = (conversions / total_decisions) * 100 if total_decisions > 0 else 0
            revenue_per_offer = total_revenue / total_decisions if total_decisions > 0 else 0
            
            # Calculate waterfall efficiency
            waterfall_efficiency = self._calculate_waterfall_efficiency(decisions, conversions)
            
            # Get offer performance breakdown
            offer_performance = self._get_offer_performance_breakdown(user_id, cutoff_time)
            
            return {
                'user_id': user_id,
                'time_window': time_window,
                'total_decisions': total_decisions,
                'conversions': conversions,
                'total_revenue': total_revenue,
                'conversion_rate': conversion_rate,
                'revenue_per_offer': revenue_per_offer,
                'waterfall_efficiency': waterfall_efficiency,
                'offer_performance': offer_performance,
                'generation_time': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting waterfall performance for user {user_id}: {e}")
            return {'error': str(e)}
    
    def optimize_waterfall_globally(self, tenant_id: int) -> Dict[str, any]:
        """
        Optimize waterfall globally for tenant.
        
        Args:
            tenant_id: Tenant ID to optimize for
            
        Returns:
            Dictionary containing optimization results
        """
        try:
            # Get tenant configuration
            config = RoutingConfig.objects.filter(tenant_id=tenant_id).first()
            if not config:
                return {'error': 'Tenant configuration not found'}
            
            # Get performance data for last 7 days
            cutoff_time = timezone.now() - timedelta(days=7)
            
            performance_data = RoutePerformanceStat.objects.filter(
                tenant_id=tenant_id,
                date__gte=cutoff_time
            ).order_by('-date')
            
            if not performance_data.exists():
                return {'error': 'No performance data available'}
            
            # Analyze performance patterns
            analysis = self._analyze_performance_patterns(performance_data)
            
            # Generate optimization recommendations
            recommendations = self._generate_optimization_recommendations(analysis, config)
            
            # Apply optimizations if auto-optimization is enabled
            if config.auto_optimization_enabled:
                optimization_results = self._apply_optimizations(recommendations, tenant_id)
            else:
                optimization_results = {'status': 'manual_review_required', 'recommendations': recommendations}
            
            # Log optimization
            self._log_optimization_event(tenant_id, analysis, recommendations, optimization_results)
            
            logger.info(f"Waterfall optimization completed for tenant {tenant_id}")
            
            return {
                'tenant_id': tenant_id,
                'analysis': analysis,
                'recommendations': recommendations,
                'optimization_results': optimization_results,
                'optimization_time': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error optimizing waterfall for tenant {tenant_id}: {e}")
            return {'error': str(e)}
    
    def _get_available_offers(self, user: User, context: Dict[str, any]) -> List[OfferRoute]:
        """Get available offers for user."""
        try:
            # Base query
            offers = OfferRoute.objects.filter(
                tenant_id=user.tenant_id,
                is_active=True
            ).select_related('offer', 'network')
            
            # Apply targeting filters
            if 'geo' in context:
                geo = context['geo']
                offers = offers.filter(
                    Q(geo_targeting__country=geo.get('country')) |
                    Q(geo_targeting__region=geo.get('region')) |
                    Q(geo_targeting__city=geo.get('city'))
                )
            
            if 'device' in context:
                device = context['device']
                offers = offers.filter(
                    Q(device_targeting__device_type=device.get('type')) |
                    Q(device_targeting__os_type=device.get('os')) |
                    Q(device_targeting__browser=device.get('browser'))
                )
            
            # Apply time-based filters
            current_time = timezone.now()
            offers = offers.filter(
                Q(valid_from__lte=current_time) | Q(valid_from__isnull=True),
                Q(valid_to__gte=current_time) | Q(valid_to__isnull=True)
            )
            
            # Apply user segment filters
            if 'segments' in context:
                segments = context['segments']
                offers = offers.filter(
                    user_segments__segment_type__in=segments
                )
            
            return list(offers.distinct())
            
        except Exception as e:
            logger.error(f"Error getting available offers: {e}")
            return []
    
    def _apply_caps_and_filters(self, offers: List[OfferRoute], user: User, context: Dict[str, any]) -> List[OfferRoute]:
        """Apply caps and additional filters to offers."""
        try:
            filtered_offers = []
            
            for offer in offers:
                # Check global caps
                global_cap = OfferRoutingCap.objects.filter(
                    offer=offer,
                    is_active=True
                ).first()
                
                if global_cap and global_cap.current_count >= global_cap.cap_value:
                    continue  # Skip if cap is reached
                
                # Check user-specific caps
                user_cap = UserOfferCap.objects.filter(
                    user=user,
                    offer=offer
                ).first()
                
                if user_cap and user_cap.shown_today >= user_cap.max_shows_per_day:
                    continue  # Skip if user cap is reached
                
                # Check minimum revenue threshold
                if offer.min_revenue and offer.min_revenue < self.min_revenue_threshold:
                    continue  # Skip if revenue is too low
                
                # Check network availability
                if not self._is_network_available(offer.network, context):
                    continue  # Skip if network is not available
                
                filtered_offers.append(offer)
            
            return filtered_offers
            
        except Exception as e:
            logger.error(f"Error applying caps and filters: {e}")
            return offers
    
    def _score_offers(self, offers: List[OfferRoute], user: User, context: Dict[str, any]) -> List[Tuple[OfferRoute, float]]:
        """Score offers based on multiple factors."""
        try:
            scored_offers = []
            
            for offer in offers:
                score = 0.0
                
                # Base score from offer configuration
                score += offer.base_score or 0
                
                # Performance score
                performance_score = self._calculate_performance_score(offer, user)
                score += performance_score * self.performance_weight
                
                # Revenue score
                revenue_score = self._calculate_revenue_score(offer, user)
                score += revenue_score * self.revenue_weight
                
                # Personalization score
                personalization_score = self._calculate_personalization_score(offer, user)
                score += personalization_score * 0.2
                
                # Freshness score
                freshness_score = self._calculate_freshness_score(offer)
                score += freshness_score * 0.1
                
                # Quality score
                quality_score = self._calculate_quality_score(offer)
                score += quality_score * 0.15
                
                scored_offers.append((offer, score))
            
            # Sort by score (descending)
            scored_offers.sort(key=lambda x: x[1], reverse=True)
            
            return scored_offers
            
        except Exception as e:
            logger.error(f"Error scoring offers: {e}")
            return []
    
    def _generate_waterfall_chain(self, scored_offers: List[Tuple[OfferRoute, float]], user: User, context: Dict[str, any]) -> List[Dict[str, any]]:
        """Generate waterfall chain from scored offers."""
        try:
            waterfall_chain = []
            
            for i, (offer, score) in enumerate(scored_offers[:self.max_waterfall_depth]):
                # Get offer metadata
                offer_data = {
                    'position': i + 1,
                    'offer_id': offer.id,
                    'offer_name': offer.name,
                    'network_id': offer.network.id if offer.network else None,
                    'network_name': offer.network.name if offer.network else None,
                    'score': score,
                    'base_score': offer.base_score or 0,
                    'revenue': offer.expected_revenue or 0,
                    'epc': offer.epc or 0,
                    'conversion_rate': offer.conversion_rate or 0,
                    'priority': offer.priority or 0,
                    'fallback_enabled': offer.fallback_enabled,
                    'fallback_depth': offer.fallback_depth or 0,
                    'conditions': {
                        'geo_targeting': self._get_geo_conditions(offer),
                        'device_targeting': self._get_device_conditions(offer),
                        'time_targeting': self._get_time_conditions(offer),
                        'user_segments': self._get_user_segments(offer)
                    },
                    'performance': {
                        'impressions': self._get_offer_impressions(offer),
                        'conversions': self._get_offer_conversions(offer),
                        'revenue': self._get_offer_revenue(offer),
                        'last_24h_performance': self._get_24h_performance(offer)
                    },
                    'estimated_metrics': {
                        'click_probability': self._estimate_click_probability(offer, user, context),
                        'conversion_probability': self._estimate_conversion_probability(offer, user, context),
                        'expected_revenue': self._estimate_expected_revenue(offer, user, context)
                    }
                }
                
                waterfall_chain.append(offer_data)
            
            return waterfall_chain
            
        except Exception as e:
            logger.error(f"Error generating waterfall chain: {e}")
            return []
    
    def _apply_revenue_optimization(self, waterfall_chain: List[Dict[str, any]], user: User, context: Dict[str, any]) -> List[Dict[str, any]]:
        """Apply revenue optimization to waterfall chain."""
        try:
            # Calculate revenue potential for each offer
            for offer_data in waterfall_chain:
                revenue_potential = self._calculate_revenue_potential(offer_data, user, context)
                offer_data['revenue_potential'] = revenue_potential
            
            # Sort by revenue potential (descending)
            optimized_chain = sorted(waterfall_chain, key=lambda x: x['revenue_potential'], reverse=True)
            
            # Reassign positions
            for i, offer_data in enumerate(optimized_chain):
                offer_data['optimized_position'] = i + 1
                offer_data['position_change'] = offer_data['optimized_position'] - offer_data['position']
            
            return optimized_chain
            
        except Exception as e:
            logger.error(f"Error applying revenue optimization: {e}")
            return waterfall_chain
    
    def _calculate_performance_score(self, offer: OfferRoute, user: User) -> float:
        """Calculate performance score for offer."""
        try:
            # Get recent performance data
            cutoff_time = timezone.now() - timedelta(days=7)
            
            performance = RoutePerformanceStat.objects.filter(
                offer_id=offer.id,
                date__gte=cutoff_time
            ).aggregate(
                total_impressions=Sum('impressions'),
                total_conversions=Sum('conversions'),
                avg_response_time=Avg('response_time_ms')
            )
            
            if not performance['total_impressions']:
                return 0.0
            
            # Calculate performance metrics
            conversion_rate = (performance['total_conversions'] / performance['total_impressions']) * 100
            avg_response_time = performance['avg_response_time'] or 0
            
            # Normalize scores (0-100)
            conversion_score = min(conversion_rate * 10, 100)  # 10% CR = 100 points
            response_score = max(100 - (avg_response_time / 10), 0)  # Lower is better
            
            # Weighted average
            return (conversion_score * 0.7) + (response_score * 0.3)
            
        except Exception as e:
            logger.error(f"Error calculating performance score: {e}")
            return 0.0
    
    def _calculate_revenue_score(self, offer: OfferRoute, user: User) -> float:
        """Calculate revenue score for offer."""
        try:
            # Get offer revenue data
            expected_revenue = offer.expected_revenue or 0
            epc = offer.epc or 0
            
            # Normalize to 0-100 scale
            # Assuming max expected revenue is $10
            revenue_score = min((expected_revenue / 10) * 100, 100)
            
            # Adjust for EPC
            epc_score = min((epc / 0.5) * 100, 100)  # Assuming max EPC is $0.5
            
            # Weighted average
            return (revenue_score * 0.6) + (epc_score * 0.4)
            
        except Exception as e:
            logger.error(f"Error calculating revenue score: {e}")
            return 0.0
    
    def _calculate_personalization_score(self, offer: OfferRoute, user: User) -> float:
        """Calculate personalization score for offer."""
        try:
            # Get user preferences
            from ..models import UserPreferenceVector
            preference_vector = UserPreferenceVector.objects.filter(user=user).first()
            
            if not preference_vector:
                return 50.0  # Default score
            
            # Get offer categories
            categories = offer.categories.all()
            
            if not categories.exists():
                return 50.0
            
            # Calculate preference match
            total_preference = 0
            category_count = 0
            
            for category in categories:
                preference_score = preference_vector.vector.get(category.name, 0)
                total_preference += preference_score
                category_count += 1
            
            if category_count == 0:
                return 50.0
            
            avg_preference = total_preference / category_count
            
            # Normalize to 0-100 scale
            return min((avg_preference / 10) * 100, 100)
            
        except Exception as e:
            logger.error(f"Error calculating personalization score: {e}")
            return 50.0
    
    def _calculate_freshness_score(self, offer: OfferRoute) -> float:
        """Calculate freshness score for offer."""
        try:
            # Get offer age
            if offer.created_at:
                age_days = (timezone.now() - offer.created_at).days
            else:
                age_days = 30  # Default to 30 days
            
            # Freshness decreases with age
            # New offers (0-7 days) get 100 points
            # Old offers (30+ days) get 20 points
            if age_days <= 7:
                return 100.0
            elif age_days <= 14:
                return 80.0
            elif age_days <= 21:
                return 60.0
            elif age_days <= 30:
                return 40.0
            else:
                return 20.0
                
        except Exception as e:
            logger.error(f"Error calculating freshness score: {e}")
            return 50.0
    
    def _calculate_quality_score(self, offer: OfferRoute) -> float:
        """Calculate quality score for offer."""
        try:
            # Get quality metrics
            quality_score = 0.0
            
            # Network quality
            if offer.network and hasattr(offer.network, 'quality_score'):
                quality_score += offer.network.quality_score * 0.4
            
            # Offer quality score
            if hasattr(offer, 'quality_score'):
                quality_score += offer.quality_score * 0.3
            
            # Historical quality
            quality_score += self._calculate_historical_quality(offer) * 0.3
            
            return min(quality_score, 100.0)
            
        except Exception as e:
            logger.error(f"Error calculating quality score: {e}")
            return 50.0
    
    def _is_network_available(self, network, context: Dict[str, any]) -> bool:
        """Check if network is available."""
        try:
            if not network:
                return True
            
            # Check network status
            if not network.is_active:
                return False
            
            # Check geo availability
            if 'geo' in context:
                geo = context['geo']
                if network.geo_restrictions:
                    if geo.get('country') not in network.geo_restrictions:
                        return False
            
            # Check device availability
            if 'device' in context:
                device = context['device']
                if network.device_restrictions:
                    if device.get('type') not in network.device_restrictions:
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking network availability: {e}")
            return True
    
    def _calculate_estimated_revenue(self, waterfall_chain: List[Dict[str, any]]) -> float:
        """Calculate estimated revenue for waterfall chain."""
        try:
            total_revenue = 0.0
            
            for offer_data in waterfall_chain:
                estimated_revenue = offer_data.get('estimated_metrics', {}).get('expected_revenue', 0)
                total_revenue += estimated_revenue
            
            return total_revenue
            
        except Exception as e:
            logger.error(f"Error calculating estimated revenue: {e}")
            return 0.0
    
    def _log_waterfall_generation(self, user: User, waterfall_chain: List[Dict[str, any]], context: Dict[str, any]):
        """Log waterfall generation event."""
        try:
            RoutingInsight.objects.create(
                tenant_id=user.tenant_id,
                user=user,
                insight_type='waterfall_generation',
                title=f'Waterfall Generated for User {user.id}',
                description=f'Generated waterfall with {len(waterfall_chain)} offers',
                data={
                    'user_id': user.id,
                    'offer_count': len(waterfall_chain),
                    'estimated_revenue': self._calculate_estimated_revenue(waterfall_chain),
                    'context': context,
                    'top_offers': [offer['offer_id'] for offer in waterfall_chain[:5]]
                }
            )
            
        except Exception as e:
            logger.error(f"Error logging waterfall generation: {e}")
    
    def _calculate_waterfall_efficiency(self, decisions, conversions) -> float:
        """Calculate waterfall efficiency."""
        try:
            if not decisions.exists():
                return 0.0
            
            # Efficiency based on conversion rate and position
            total_decisions = decisions.count()
            
            # Get positions of conversions
            conversion_positions = []
            for decision in decisions:
                if UserOfferHistory.objects.filter(
                    user_id=decision.user_id,
                    offer_id=decision.offer_id,
                    completed_at__gte=decision.created_at
                ).exists():
                    conversion_positions.append(decision.rank)
            
            if not conversion_positions:
                return 0.0
            
            # Average position of conversions
            avg_position = sum(conversion_positions) / len(conversion_positions)
            
            # Efficiency: lower position = higher efficiency
            efficiency = max(100 - (avg_position * 10), 0)
            
            return efficiency
            
        except Exception as e:
            logger.error(f"Error calculating waterfall efficiency: {e}")
            return 0.0
    
    def _get_offer_performance_breakdown(self, user_id: int, cutoff_time) -> List[Dict[str, any]]:
        """Get performance breakdown by offer."""
        try:
            # Get offer performance for user
            offer_performance = []
            
            offers = OfferRoute.objects.filter(
                routingdecisionlog__user_id=user_id,
                routingdecisionlog__created_at__gte=cutoff_time
            ).distinct()
            
            for offer in offers:
                decisions = RoutingDecisionLog.objects.filter(
                    user_id=user_id,
                    offer_id=offer.id,
                    created_at__gte=cutoff_time
                )
                
                conversions = UserOfferHistory.objects.filter(
                    user_id=user_id,
                    offer_id=offer.id,
                    completed_at__gte=cutoff_time
                )
                
                total_revenue = conversions.aggregate(
                    total_revenue=Sum('revenue')
                )['total_revenue'] or 0
                
                offer_performance.append({
                    'offer_id': offer.id,
                    'offer_name': offer.name,
                    'decisions': decisions.count(),
                    'conversions': conversions.count(),
                    'revenue': total_revenue,
                    'conversion_rate': (conversions.count() / decisions.count() * 100) if decisions.count() > 0 else 0
                })
            
            return sorted(offer_performance, key=lambda x: x['revenue'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error getting offer performance breakdown: {e}")
            return []
    
    def _analyze_performance_patterns(self, performance_data) -> Dict[str, any]:
        """Analyze performance patterns from data."""
        try:
            analysis = {
                'total_days': performance_data.count(),
                'avg_impressions': performance_data.aggregate(avg=Avg('impressions'))['avg'] or 0,
                'avg_conversions': performance_data.aggregate(avg=Avg('conversions'))['avg'] or 0,
                'avg_revenue': performance_data.aggregate(avg=Avg('revenue'))['avg'] or 0,
                'trends': {},
                'insights': []
            }
            
            # Calculate trends
            if len(performance_data) >= 7:
                recent_data = performance_data[:7]  # Last 7 days
                older_data = performance_data[7:14]  # Previous 7 days
                
                recent_avg = recent_data.aggregate(avg=Avg('revenue'))['avg'] or 0
                older_avg = older_data.aggregate(avg=Avg('revenue'))['avg'] or 0
                
                if older_avg > 0:
                    trend_percentage = ((recent_avg - older_avg) / older_avg) * 100
                    analysis['trends']['revenue_trend'] = trend_percentage
            
            # Generate insights
            if analysis['avg_conversion_rate'] > 5:
                analysis['insights'].append('High conversion rate detected')
            
            if analysis['avg_response_time'] > 500:
                analysis['insights'].append('High response time detected')
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing performance patterns: {e}")
            return {}
    
    def _generate_optimization_recommendations(self, analysis: Dict[str, any], config: RoutingConfig) -> List[Dict[str, any]]:
        """Generate optimization recommendations."""
        try:
            recommendations = []
            
            # Revenue optimization
            if analysis.get('avg_revenue', 0) < 1.0:
                recommendations.append({
                    'type': 'revenue_optimization',
                    'priority': 'high',
                    'description': 'Low average revenue detected',
                    'action': 'Consider adjusting revenue thresholds or offer prioritization'
                })
            
            # Performance optimization
            if analysis.get('avg_response_time', 0) > 300:
                recommendations.append({
                    'type': 'performance_optimization',
                    'priority': 'medium',
                    'description': 'High response time detected',
                    'action': 'Consider optimizing offer selection or caching'
                })
            
            # Conversion optimization
            if analysis.get('avg_conversion_rate', 0) < 2:
                recommendations.append({
                    'type': 'conversion_optimization',
                    'priority': 'high',
                    'description': 'Low conversion rate detected',
                    'action': 'Consider improving offer targeting or quality'
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating optimization recommendations: {e}")
            return []
    
    def _apply_optimizations(self, recommendations: List[Dict[str, any]], tenant_id: int) -> Dict[str, any]:
        """Apply optimization recommendations."""
        try:
            applied_optimizations = []
            
            for recommendation in recommendations:
                # Apply optimization based on type
                if recommendation['type'] == 'revenue_optimization':
                    # Update revenue thresholds
                    result = self._apply_revenue_optimization(tenant_id)
                    applied_optimizations.append(result)
                
                elif recommendation['type'] == 'performance_optimization':
                    # Update performance settings
                    result = self._apply_performance_optimization(tenant_id)
                    applied_optimizations.append(result)
                
                elif recommendation['type'] == 'conversion_optimization':
                    # Update conversion settings
                    result = self._apply_conversion_optimization(tenant_id)
                    applied_optimizations.append(result)
            
            return {
                'status': 'applied',
                'optimizations': applied_optimizations,
                'applied_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error applying optimizations: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _log_optimization_event(self, tenant_id: int, analysis: Dict[str, any], recommendations: List[Dict[str, any]], results: Dict[str, any]):
        """Log optimization event."""
        try:
            RoutingInsight.objects.create(
                tenant_id=tenant_id,
                insight_type='waterfall_optimization',
                title='Waterfall Optimization Applied',
                description=f'Applied {len(recommendations)} optimization recommendations',
                data={
                    'analysis': analysis,
                    'recommendations': recommendations,
                    'results': results
                }
            )
            
        except Exception as e:
            logger.error(f"Error logging optimization event: {e}")


# Global waterfall service instance
waterfall_service = WaterfallService()
