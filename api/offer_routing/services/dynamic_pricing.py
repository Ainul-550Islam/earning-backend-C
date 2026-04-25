"""
Dynamic Pricing Service for Offer Routing System

This module provides comprehensive dynamic pricing capabilities,
including real-time price optimization, demand-based pricing,
and revenue maximization algorithms.
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.core.cache import cache
from django.db.models import Q, Avg, Sum, Count, StdDev
from django.utils import timezone
from django.contrib.auth import get_user_model

from ..models import (
    OfferRoute, UserOfferHistory, RoutePerformanceStat,
    RoutingConfig, OfferQualityScore, RoutingInsight
)
from ..utils import get_client_ip, validate_ip_address

User = get_user_model()
logger = logging.getLogger(__name__)


class DynamicPricingService:
    """
    Comprehensive dynamic pricing service for offer routing.
    
    Manages:
    - Real-time price optimization
    - Demand-based pricing
    - Revenue maximization
    - Competitive pricing
    - Geographic pricing
    - Time-based pricing
    """
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
        self.pricing_history_days = 30
        self.min_price_change = 0.01  # Minimum price change
        self.max_price_change = 2.0  # Maximum price change
        self.price_elasticity_threshold = 0.5  # Price elasticity threshold
    
    def calculate_dynamic_price(self, offer_id: int, context: Dict[str, any]) -> Dict[str, any]:
        """
        Calculate dynamic price for offer based on context.
        
        Args:
            offer_id: Offer ID to price
            context: Pricing context (user, geo, time, etc.)
            
        Returns:
            Dictionary containing pricing data
        """
        try:
            # Get offer details
            offer = self._get_offer_details(offer_id)
            if not offer:
                return {'error': 'Offer not found'}
            
            # Get base price
            base_price = offer.base_price or 1.0
            
            # Calculate pricing factors
            pricing_factors = self._calculate_pricing_factors(offer, context)
            
            # Apply pricing adjustments
            adjusted_price = self._apply_pricing_adjustments(base_price, pricing_factors)
            
            # Apply constraints
            final_price = self._apply_price_constraints(adjusted_price, offer)
            
            # Calculate price confidence
            price_confidence = self._calculate_price_confidence(pricing_factors)
            
            # Get price history
            price_history = self._get_price_history(offer_id)
            
            # Build pricing data
            pricing_data = {
                'offer_id': offer_id,
                'base_price': base_price,
                'final_price': final_price,
                'price_change': final_price - base_price,
                'price_change_percentage': ((final_price - base_price) / base_price) * 100,
                'pricing_factors': pricing_factors,
                'price_confidence': price_confidence,
                'price_history': price_history,
                'context': context,
                'calculation_time': timezone.now().isoformat(),
                'pricing_strategy': self._determine_pricing_strategy(pricing_factors),
                'revenue_impact': self._calculate_revenue_impact(offer, final_price, context),
                'optimization_score': self._calculate_optimization_score(offer, final_price, context)
            }
            
            # Cache pricing data
            cache_key = f"dynamic_price:{offer_id}:{hash(str(context))}"
            cache.set(cache_key, pricing_data, self.cache_timeout)
            
            # Log pricing calculation
            self._log_pricing_calculation(pricing_data)
            
            logger.info(f"Dynamic price calculated for offer {offer_id}: ${final_price:.4f}")
            
            return pricing_data
            
        except Exception as e:
            logger.error(f"Error calculating dynamic price for offer {offer_id}: {e}")
            return {'error': str(e)}
    
    def optimize_pricing_portfolio(self, tenant_id: int, optimization_window: int = 7) -> Dict[str, any]:
        """
        Optimize pricing portfolio for tenant.
        
        Args:
            tenant_id: Tenant ID to optimize for
            optimization_window: Number of days to analyze
            
        Returns:
            Dictionary containing optimization results
        """
        try:
            # Get tenant configuration
            config = RoutingConfig.objects.filter(tenant_id=tenant_id).first()
            if not config:
                return {'error': 'Tenant configuration not found'}
            
            # Get all offers for tenant
            offers = OfferRoute.objects.filter(
                tenant_id=tenant_id,
                is_active=True
            ).select_related('network')
            
            # Analyze current pricing
            current_pricing = self._analyze_current_pricing(offers)
            
            # Calculate optimal prices
            optimal_pricing = self._calculate_optimal_pricing(offers, optimization_window)
            
            # Generate pricing recommendations
            recommendations = self._generate_pricing_recommendations(current_pricing, optimal_pricing)
            
            # Calculate revenue impact
            revenue_impact = self._calculate_portfolio_revenue_impact(offers, recommendations)
            
            # Apply optimizations if enabled
            if config.auto_pricing_optimization:
                applied_changes = self._apply_pricing_optimizations(recommendations)
            else:
                applied_changes = {'status': 'manual_review_required', 'recommendations': recommendations}
            
            # Build optimization results
            optimization_results = {
                'tenant_id': tenant_id,
                'optimization_window': optimization_window,
                'current_pricing': current_pricing,
                'optimal_pricing': optimal_pricing,
                'recommendations': recommendations,
                'revenue_impact': revenue_impact,
                'applied_changes': applied_changes,
                'optimization_time': timezone.now().isoformat(),
                'optimization_score': self._calculate_portfolio_optimization_score(revenue_impact),
                'risk_assessment': self._assess_pricing_risks(recommendations)
            }
            
            # Cache optimization results
            cache_key = f"pricing_optimization:{tenant_id}"
            cache.set(cache_key, optimization_results, self.cache_timeout * 2)
            
            # Log optimization
            self._log_pricing_optimization(optimization_results)
            
            logger.info(f"Pricing optimization completed for tenant {tenant_id}")
            
            return optimization_results
            
        except Exception as e:
            logger.error(f"Error optimizing pricing portfolio for tenant {tenant_id}: {e}")
            return {'error': str(e)}
    
    def get_pricing_analytics(self, offer_id: int, time_window: int = 30) -> Dict[str, any]:
        """
        Get pricing analytics for offer.
        
        Args:
            offer_id: Offer ID to analyze
            time_window: Time window in days
            
        Returns:
            Dictionary containing pricing analytics
        """
        try:
            # Get offer details
            offer = self._get_offer_details(offer_id)
            if not offer:
                return {'error': 'Offer not found'}
            
            # Get pricing history
            pricing_history = self._get_detailed_pricing_history(offer_id, time_window)
            
            # Calculate pricing metrics
            pricing_metrics = self._calculate_pricing_metrics(pricing_history)
            
            # Analyze price elasticity
            elasticity_analysis = self._analyze_price_elasticity(pricing_history)
            
            # Get competitor pricing
            competitor_pricing = self._get_competitor_pricing(offer_id)
            
            # Analyze revenue performance
            revenue_performance = self._analyze_revenue_performance(offer_id, time_window)
            
            # Build analytics data
            analytics_data = {
                'offer_id': offer_id,
                'time_window': time_window,
                'pricing_history': pricing_history,
                'pricing_metrics': pricing_metrics,
                'elasticity_analysis': elasticity_analysis,
                'competitor_pricing': competitor_pricing,
                'revenue_performance': revenue_performance,
                'analysis_time': timezone.now().isoformat(),
                'pricing_trends': self._calculate_pricing_trends(pricing_history),
                'optimization_opportunities': self._identify_optimization_opportunities(offer, pricing_history),
                'price_volatility': self._calculate_price_volatility(pricing_history)
            }
            
            logger.info(f"Pricing analytics generated for offer {offer_id}")
            
            return analytics_data
            
        except Exception as e:
            logger.error(f"Error getting pricing analytics for offer {offer_id}: {e}")
            return {'error': str(e)}
    
    def _get_offer_details(self, offer_id: int) -> Optional[OfferRoute]:
        """Get offer details with related data."""
        try:
            return OfferRoute.objects.filter(
                id=offer_id,
                is_active=True
            ).select_related('network', 'tenant').first()
            
        except Exception as e:
            logger.error(f"Error getting offer details: {e}")
            return None
    
    def _calculate_pricing_factors(self, offer: OfferRoute, context: Dict[str, any]) -> Dict[str, float]:
        """Calculate pricing factors based on context."""
        try:
            factors = {}
            
            # Demand factor
            factors['demand'] = self._calculate_demand_factor(offer, context)
            
            # Geographic factor
            factors['geographic'] = self._calculate_geographic_factor(offer, context)
            
            # Time factor
            factors['time'] = self._calculate_time_factor(offer, context)
            
            # User segment factor
            factors['user_segment'] = self._calculate_user_segment_factor(offer, context)
            
            # Competition factor
            factors['competition'] = self._calculate_competition_factor(offer, context)
            
            # Quality factor
            factors['quality'] = self._calculate_quality_factor(offer)
            
            # Performance factor
            factors['performance'] = self._calculate_performance_factor(offer)
            
            # Seasonality factor
            factors['seasonality'] = self._calculate_seasonality_factor(offer, context)
            
            # Inventory factor
            factors['inventory'] = self._calculate_inventory_factor(offer)
            
            # Market factor
            factors['market'] = self._calculate_market_factor(offer, context)
            
            return factors
            
        except Exception as e:
            logger.error(f"Error calculating pricing factors: {e}")
            return {}
    
    def _calculate_demand_factor(self, offer: OfferRoute, context: Dict[str, any]) -> float:
        """Calculate demand factor based on recent demand."""
        try:
            # Get recent demand data
            recent_demand = RoutePerformanceStat.objects.filter(
                offer_id=offer.id,
                date__gte=timezone.now() - timedelta(days=7)
            ).aggregate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                avg_impressions=Avg('impressions')
            )
            
            if not recent_demand['avg_impressions']:
                return 1.0
            
            # Calculate demand ratio
            current_demand = recent_demand['total_impressions'] / 7  # Daily average
            baseline_demand = recent_demand['avg_impressions']
            
            if baseline_demand > 0:
                demand_ratio = current_demand / baseline_demand
            else:
                demand_ratio = 1.0
            
            # Apply demand factor (higher demand = higher price)
            demand_factor = 1.0 + (demand_ratio - 1.0) * 0.3
            
            return max(min(demand_factor, 0.5), 2.0)  # Clamp between 0.5 and 2.0
            
        except Exception as e:
            logger.error(f"Error calculating demand factor: {e}")
            return 1.0
    
    def _calculate_geographic_factor(self, offer: OfferRoute, context: Dict[str, any]) -> float:
        """Calculate geographic pricing factor."""
        try:
            geo = context.get('geo', {})
            country = geo.get('country')
            
            if not country:
                return 1.0
            
            # Get geographic performance data
            geo_performance = RoutePerformanceStat.objects.filter(
                offer_id=offer.id,
                date__gte=timezone.now() - timedelta(days=30)
            ).values('country').annotate(
                avg_revenue=Avg('revenue'),
                total_conversions=Sum('conversions')
            )
            
            # Find country-specific performance
            country_performance = next(
                (perf for perf in geo_performance if perf['country'] == country),
                None
            )
            
            if not country_performance:
                return 1.0
            
            # Calculate average performance across all countries
            avg_revenue = geo_performance.aggregate(
                avg_revenue=Avg('avg_revenue')
            )['avg_revenue'] or 1.0
            
            # Calculate geographic factor
            if avg_revenue > 0:
                geo_factor = country_performance['avg_revenue'] / avg_revenue
            else:
                geo_factor = 1.0
            
            return max(min(geo_factor, 0.7), 1.5)  # Clamp between 0.7 and 1.5
            
        except Exception as e:
            logger.error(f"Error calculating geographic factor: {e}")
            return 1.0
    
    def _calculate_time_factor(self, offer: OfferRoute, context: Dict[str, any]) -> float:
        """Calculate time-based pricing factor."""
        try:
            current_time = timezone.now()
            hour = current_time.hour
            day_of_week = current_time.weekday()
            
            # Get time-based performance data
            time_performance = RoutePerformanceStat.objects.filter(
                offer_id=offer.id,
                date__gte=timezone.now() - timedelta(days=30)
            ).extra({
                'hour': 'EXTRACT(HOUR FROM date)',
                'day_of_week': 'EXTRACT(DOW FROM date)'
            }).values('hour', 'day_of_week').annotate(
                avg_revenue=Avg('revenue'),
                total_conversions=Sum('conversions')
            )
            
            # Find time-specific performance
            time_perf = next(
                (perf for perf in time_performance 
                 if perf['hour'] == hour and perf['day_of_week'] == day_of_week),
                None
            )
            
            if not time_perf:
                return 1.0
            
            # Calculate average performance
            avg_revenue = time_performance.aggregate(
                avg_revenue=Avg('avg_revenue')
            )['avg_revenue'] or 1.0
            
            # Calculate time factor
            if avg_revenue > 0:
                time_factor = time_perf['avg_revenue'] / avg_revenue
            else:
                time_factor = 1.0
            
            return max(min(time_factor, 0.8), 1.3)  # Clamp between 0.8 and 1.3
            
        except Exception as e:
            logger.error(f"Error calculating time factor: {e}")
            return 1.0
    
    def _calculate_user_segment_factor(self, offer: OfferRoute, context: Dict[str, any]) -> float:
        """Calculate user segment pricing factor."""
        try:
            user = context.get('user')
            if not user:
                return 1.0
            
            # Get user segment performance
            segment_performance = RoutePerformanceStat.objects.filter(
                offer_id=offer.id,
                date__gte=timezone.now() - timedelta(days=30)
            ).values('user_segment').annotate(
                avg_revenue=Avg('revenue'),
                total_conversions=Sum('conversions')
            )
            
            # Determine user segment
            user_segment = self._determine_user_segment(user)
            
            # Find segment-specific performance
            segment_perf = next(
                (perf for perf in segment_performance 
                 if perf['user_segment'] == user_segment),
                None
            )
            
            if not segment_perf:
                return 1.0
            
            # Calculate average performance
            avg_revenue = segment_performance.aggregate(
                avg_revenue=Avg('avg_revenue')
            )['avg_revenue'] or 1.0
            
            # Calculate segment factor
            if avg_revenue > 0:
                segment_factor = segment_perf['avg_revenue'] / avg_revenue
            else:
                segment_factor = 1.0
            
            return max(min(segment_factor, 0.9), 1.2)  # Clamp between 0.9 and 1.2
            
        except Exception as e:
            logger.error(f"Error calculating user segment factor: {e}")
            return 1.0
    
    def _calculate_competition_factor(self, offer: OfferRoute, context: Dict[str, any]) -> float:
        """Calculate competition-based pricing factor."""
        try:
            # Get similar offers from competitors
            similar_offers = OfferRoute.objects.filter(
                categories__in=offer.categories.all(),
                is_active=True
            ).exclude(id=offer.id).annotate(
                avg_price=Avg('base_price')
            )
            
            if not similar_offers.exists():
                return 1.0
            
            # Calculate competition factor
            competitor_avg_price = similar_offers.aggregate(
                avg_price=Avg('avg_price')
            )['avg_price'] or offer.base_price
            
            if competitor_avg_price > 0:
                competition_factor = offer.base_price / competitor_avg_price
            else:
                competition_factor = 1.0
            
            return max(min(competition_factor, 0.8), 1.2)  # Clamp between 0.8 and 1.2
            
        except Exception as e:
            logger.error(f"Error calculating competition factor: {e}")
            return 1.0
    
    def _calculate_quality_factor(self, offer: OfferRoute) -> float:
        """Calculate quality-based pricing factor."""
        try:
            # Get quality score
            quality_score = OfferQualityScore.objects.filter(
                offer_id=offer.id
            ).order_by('-score_calculation_date').first()
            
            if not quality_score:
                return 1.0
            
            # Convert quality score to pricing factor
            # Higher quality = higher price
            quality_factor = 0.8 + (quality_score.overall_score / 100) * 0.4
            
            return max(min(quality_factor, 0.7), 1.3)  # Clamp between 0.7 and 1.3
            
        except Exception as e:
            logger.error(f"Error calculating quality factor: {e}")
            return 1.0
    
    def _calculate_performance_factor(self, offer: OfferRoute) -> float:
        """Calculate performance-based pricing factor."""
        try:
            # Get recent performance data
            performance = RoutePerformanceStat.objects.filter(
                offer_id=offer.id,
                date__gte=timezone.now() - timedelta(days=7)
            ).aggregate(
                avg_revenue=Avg('revenue'),
                conversion_rate=Avg('conversion_rate'),
                epc=Avg('epc')
            )
            
            if not performance['avg_revenue']:
                return 1.0
            
            # Calculate performance score
            performance_score = (
                (performance['conversion_rate'] or 0) * 0.4 +
                (performance['epc'] or 0) * 0.3 +
                (performance['avg_revenue'] or 0) * 0.3
            )
            
            # Convert to pricing factor
            performance_factor = 0.9 + (performance_score / 10) * 0.2
            
            return max(min(performance_factor, 0.8), 1.2)  # Clamp between 0.8 and 1.2
            
        except Exception as e:
            logger.error(f"Error calculating performance factor: {e}")
            return 1.0
    
    def _calculate_seasonality_factor(self, offer: OfferRoute, context: Dict[str, any]) -> float:
        """Calculate seasonality-based pricing factor."""
        try:
            current_date = timezone.now().date()
            
            # Get seasonal performance data
            seasonal_performance = RoutePerformanceStat.objects.filter(
                offer_id=offer.id,
                date__gte=timezone.now() - timedelta(days=365)
            ).extra({
                'month': 'EXTRACT(MONTH FROM date)'
            }).values('month').annotate(
                avg_revenue=Avg('revenue'),
                total_conversions=Sum('conversions')
            )
            
            # Find current month performance
            current_month = current_date.month
            month_perf = next(
                (perf for perf in seasonal_performance if perf['month'] == current_month),
                None
            )
            
            if not month_perf:
                return 1.0
            
            # Calculate average performance
            avg_revenue = seasonal_performance.aggregate(
                avg_revenue=Avg('avg_revenue')
            )['avg_revenue'] or 1.0
            
            # Calculate seasonality factor
            if avg_revenue > 0:
                seasonality_factor = month_perf['avg_revenue'] / avg_revenue
            else:
                seasonality_factor = 1.0
            
            return max(min(seasonality_factor, 0.9), 1.1)  # Clamp between 0.9 and 1.1
            
        except Exception as e:
            logger.error(f"Error calculating seasonality factor: {e}")
            return 1.0
    
    def _calculate_inventory_factor(self, offer: OfferRoute) -> float:
        """Calculate inventory-based pricing factor."""
        try:
            # Get inventory data (this would depend on inventory system)
            # For now, use a placeholder
            inventory_level = 0.8  # Placeholder: 80% inventory available
            
            # Calculate inventory factor
            # Lower inventory = higher price (scarcity)
            if inventory_level > 0.8:
                inventory_factor = 0.95  # High inventory = slight discount
            elif inventory_level > 0.5:
                inventory_factor = 1.0   # Normal inventory = normal price
            else:
                inventory_factor = 1.1   # Low inventory = premium price
            
            return inventory_factor
            
        except Exception as e:
            logger.error(f"Error calculating inventory factor: {e}")
            return 1.0
    
    def _calculate_market_factor(self, offer: OfferRoute, context: Dict[str, any]) -> float:
        """Calculate market-based pricing factor."""
        try:
            # Get market conditions
            # This would integrate with external market data
            # For now, use a placeholder
            market_condition = 1.05  # Placeholder: 5% market uplift
            
            return market_condition
            
        except Exception as e:
            logger.error(f"Error calculating market factor: {e}")
            return 1.0
    
    def _apply_pricing_adjustments(self, base_price: float, factors: Dict[str, float]) -> float:
        """Apply pricing adjustments based on factors."""
        try:
            # Calculate weighted adjustment
            weights = {
                'demand': 0.25,
                'geographic': 0.15,
                'time': 0.10,
                'user_segment': 0.10,
                'competition': 0.15,
                'quality': 0.10,
                'performance': 0.10,
                'seasonality': 0.05,
                'inventory': 0.05,
                'market': 0.05,
            }
            
            # Calculate weighted factor
            weighted_factor = 0.0
            total_weight = 0.0
            
            for factor_name, weight in weights.items():
                if factor_name in factors:
                    weighted_factor += factors[factor_name] * weight
                    total_weight += weight
            
            if total_weight > 0:
                weighted_factor /= total_weight
            
            # Apply adjustment
            adjusted_price = base_price * weighted_factor
            
            return adjusted_price
            
        except Exception as e:
            logger.error(f"Error applying pricing adjustments: {e}")
            return base_price
    
    def _apply_price_constraints(self, price: float, offer: OfferRoute) -> float:
        """Apply price constraints and limits."""
        try:
            # Apply minimum price constraint
            min_price = offer.min_price or 0.01
            price = max(price, min_price)
            
            # Apply maximum price constraint
            max_price = offer.max_price or 100.0
            price = min(price, max_price)
            
            # Apply maximum change constraint
            base_price = offer.base_price or 1.0
            max_change = base_price * self.max_price_change
            min_change = base_price * self.min_price_change
            
            price = max(price, min_change)
            price = min(price, max_change)
            
            return price
            
        except Exception as e:
            logger.error(f"Error applying price constraints: {e}")
            return price
    
    def _calculate_price_confidence(self, factors: Dict[str, float]) -> float:
        """Calculate confidence score for price calculation."""
        try:
            # Calculate confidence based on factor stability
            factor_values = list(factors.values())
            
            if not factor_values:
                return 0.5
            
            # Calculate standard deviation
            mean_value = sum(factor_values) / len(factor_values)
            variance = sum((x - mean_value) ** 2 for x in factor_values) / len(factor_values)
            std_dev = math.sqrt(variance)
            
            # Convert to confidence (lower std dev = higher confidence)
            if mean_value > 0:
                confidence = 1.0 - (std_dev / mean_value)
            else:
                confidence = 0.5
            
            return max(min(confidence, 0.1), 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating price confidence: {e}")
            return 0.5
    
    def _get_price_history(self, offer_id: int) -> List[Dict[str, any]]:
        """Get price history for offer."""
        try:
            # Get price history from cache or database
            cache_key = f"price_history:{offer_id}"
            cached_history = cache.get(cache_key)
            
            if cached_history:
                return cached_history
            
            # Get from database (this would depend on price history table)
            # For now, return empty list
            price_history = []
            
            # Cache for 1 hour
            cache.set(cache_key, price_history, 3600)
            
            return price_history
            
        except Exception as e:
            logger.error(f"Error getting price history: {e}")
            return []
    
    def _determine_pricing_strategy(self, factors: Dict[str, float]) -> str:
        """Determine pricing strategy based on factors."""
        try:
            # Analyze dominant factors
            max_factor = max(factors.items(), key=lambda x: x[1])
            
            if max_factor[1] > 1.2:
                return 'premium'  # High demand or quality
            elif max_factor[1] < 0.8:
                return 'discount'  # Low demand or high competition
            else:
                return 'standard'  # Normal conditions
                
        except Exception as e:
            logger.error(f"Error determining pricing strategy: {e}")
            return 'standard'
    
    def _calculate_revenue_impact(self, offer: OfferRoute, new_price: float, context: Dict[str, any]) -> Dict[str, any]:
        """Calculate revenue impact of price change."""
        try:
            # Get current performance data
            current_performance = RoutePerformanceStat.objects.filter(
                offer_id=offer.id,
                date__gte=timezone.now() - timedelta(days=7)
            ).aggregate(
                avg_revenue=Avg('revenue'),
                total_conversions=Sum('conversions'),
                avg_conversion_rate=Avg('conversion_rate')
            )
            
            if not current_performance['avg_revenue']:
                return {
                    'estimated_revenue_change': 0,
                    'estimated_conversion_change': 0,
                    'confidence': 0.5
                }
            
            # Calculate price elasticity
            price_change = (new_price - (offer.base_price or 1.0)) / (offer.base_price or 1.0)
            
            # Estimate impact based on elasticity
            estimated_conversion_change = price_change * self.price_elasticity_threshold * -1
            estimated_revenue_change = price_change + estimated_conversion_change
            
            return {
                'estimated_revenue_change': estimated_revenue_change,
                'estimated_conversion_change': estimated_conversion_change,
                'confidence': 0.7  # Medium confidence
            }
            
        except Exception as e:
            logger.error(f"Error calculating revenue impact: {e}")
            return {
                'estimated_revenue_change': 0,
                'estimated_conversion_change': 0,
                'confidence': 0.5
            }
    
    def _calculate_optimization_score(self, offer: OfferRoute, price: float, context: Dict[str, any]) -> float:
        """Calculate optimization score for pricing."""
        try:
            # Get quality score
            quality_score = OfferQualityScore.objects.filter(
                offer_id=offer.id
            ).order_by('-score_calculation_date').first()
            
            if not quality_score:
                return 0.5
            
            # Calculate optimization score based on multiple factors
            price_alignment = 1.0 - abs(price - quality_score.overall_score / 100)
            revenue_potential = self._calculate_revenue_potential(offer, price, context)
            
            optimization_score = (price_alignment * 0.6) + (revenue_potential * 0.4)
            
            return max(min(optimization_score, 0.0), 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating optimization score: {e}")
            return 0.5
    
    def _calculate_revenue_potential(self, offer: OfferRoute, price: float, context: Dict[str, any]) -> float:
        """Calculate revenue potential for price."""
        try:
            # Get historical performance
            historical_performance = RoutePerformanceStat.objects.filter(
                offer_id=offer.id,
                date__gte=timezone.now() - timedelta(days=30)
            ).aggregate(
                avg_revenue=Avg('revenue'),
                avg_conversion_rate=Avg('conversion_rate')
            )
            
            if not historical_performance['avg_revenue']:
                return 0.5
            
            # Calculate potential based on price elasticity
            base_price = offer.base_price or 1.0
            price_ratio = price / base_price
            
            # Estimate conversion rate change
            conversion_rate_change = (1.0 - price_ratio) * 0.5  # Elasticity assumption
            
            # Calculate revenue potential
            estimated_conversion_rate = (historical_performance['avg_conversion_rate'] or 0) + conversion_rate_change
            estimated_revenue = price * estimated_conversion_rate
            
            # Normalize to 0-1 scale
            max_revenue = historical_performance['avg_revenue'] * 2  # Assume max 2x current revenue
            
            if max_revenue > 0:
                revenue_potential = min(estimated_revenue / max_revenue, 1.0)
            else:
                revenue_potential = 0.5
            
            return revenue_potential
            
        except Exception as e:
            logger.error(f"Error calculating revenue potential: {e}")
            return 0.5
    
    def _log_pricing_calculation(self, pricing_data: Dict[str, any]):
        """Log pricing calculation for analytics."""
        try:
            # Create pricing log entry
            from ..models import PricingLog
            
            PricingLog.objects.create(
                offer_id=pricing_data['offer_id'],
                base_price=pricing_data['base_price'],
                final_price=pricing_data['final_price'],
                price_change=pricing_data['price_change'],
                pricing_factors=pricing_data['pricing_factors'],
                price_confidence=pricing_data['price_confidence'],
                pricing_strategy=pricing_data['pricing_strategy'],
                context=pricing_data['context'],
                calculation_time=pricing_data['calculation_time']
            )
            
        except Exception as e:
            logger.error(f"Error logging pricing calculation: {e}")
    
    def _determine_user_segment(self, user) -> str:
        """Determine user segment for pricing."""
        try:
            # This would implement user segmentation logic
            # For now, use a simple segment based on user activity
            if hasattr(user, 'profile'):
                if user.profile.conversion_count > 10:
                    return 'high_value'
                elif user.profile.conversion_count > 5:
                    return 'medium_value'
                else:
                    return 'low_value'
            else:
                return 'standard'
                
        except Exception as e:
            logger.error(f"Error determining user segment: {e}")
            return 'standard'
    
    def _analyze_current_pricing(self, offers) -> Dict[str, any]:
        """Analyze current pricing across offers."""
        try:
            # Calculate pricing statistics
            prices = [offer.base_price or 1.0 for offer in offers]
            
            if not prices:
                return {}
            
            current_pricing = {
                'total_offers': len(offers),
                'avg_price': sum(prices) / len(prices),
                'min_price': min(prices),
                'max_price': max(prices),
                'price_range': max(prices) - min(prices),
                'price_distribution': self._calculate_price_distribution(prices),
                'pricing_efficiency': self._calculate_pricing_efficiency(offers)
            }
            
            return current_pricing
            
        except Exception as e:
            logger.error(f"Error analyzing current pricing: {e}")
            return {}
    
    def _calculate_price_distribution(self, prices: List[float]) -> Dict[str, any]:
        """Calculate price distribution statistics."""
        try:
            if not prices:
                return {}
            
            sorted_prices = sorted(prices)
            n = len(sorted_prices)
            
            # Calculate quartiles
            q1_index = n // 4
            q2_index = n // 2
            q3_index = 3 * n // 4
            
            return {
                'q1': sorted_prices[q1_index] if q1_index < n else 0,
                'median': sorted_prices[q2_index] if q2_index < n else 0,
                'q3': sorted_prices[q3_index] if q3_index < n else 0,
                'iqr': sorted_prices[q3_index] - sorted_prices[q1_index] if q3_index < n and q1_index < n else 0
            }
            
        except Exception as e:
            logger.error(f"Error calculating price distribution: {e}")
            return {}
    
    def _calculate_pricing_efficiency(self, offers) -> float:
        """Calculate pricing efficiency score."""
        try:
            # This would implement pricing efficiency calculation
            # For now, return a placeholder
            return 0.75
            
        except Exception as e:
            logger.error(f"Error calculating pricing efficiency: {e}")
            return 0.5


# Global dynamic pricing service instance
dynamic_pricing_service = DynamicPricingService()
