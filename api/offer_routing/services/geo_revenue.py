"""
Geographic Revenue Optimization Service for Offer Routing System

This module provides comprehensive geographic revenue optimization,
including location-based pricing, regional performance analysis,
and geo-targeted revenue maximization.
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


class GeoRevenueService:
    """
    Comprehensive geographic revenue optimization service.
    
    Manages:
    - Location-based pricing optimization
    - Regional performance analysis
    - Geographic revenue tracking
    - Market opportunity identification
    - Geo-targeted campaign optimization
    """
    
    def __init__(self):
        self.cache_timeout = 1800  # 30 minutes
        self.geo_analysis_days = 30
        self.min_geo_data_points = 10
        self.revenue_threshold = 1.0  # Minimum revenue for analysis
    
    def optimize_geo_pricing(self, offer_id: int, geo_context: Dict[str, any]) -> Dict[str, any]:
        """
        Optimize pricing based on geographic context.
        
        Args:
            offer_id: Offer ID to optimize
            geo_context: Geographic context (country, region, city)
            
        Returns:
            Dictionary containing geo-pricing optimization results
        """
        try:
            # Get offer details
            offer = self._get_offer_details(offer_id)
            if not offer:
                return {'error': 'Offer not found'}
            
            # Get geographic performance data
            geo_performance = self._get_geo_performance_data(offer_id, geo_context)
            
            # Calculate geo-based pricing factors
            pricing_factors = self._calculate_geo_pricing_factors(geo_performance, geo_context)
            
            # Apply geo-pricing adjustments
            optimized_prices = self._apply_geo_pricing_adjustments(offer, pricing_factors)
            
            # Calculate revenue impact
            revenue_impact = self._calculate_geo_revenue_impact(offer, optimized_prices, geo_performance)
            
            # Get market opportunity analysis
            market_opportunities = self._analyze_market_opportunities(offer, geo_context, geo_performance)
            
            # Build optimization results
            optimization_results = {
                'offer_id': offer_id,
                'geo_context': geo_context,
                'base_price': offer.base_price,
                'optimized_prices': optimized_prices,
                'pricing_factors': pricing_factors,
                'revenue_impact': revenue_impact,
                'market_opportunities': market_opportunities,
                'optimization_confidence': self._calculate_optimization_confidence(geo_performance),
                'geo_performance': geo_performance,
                'optimization_time': timezone.now().isoformat(),
                'pricing_strategy': self._determine_geo_pricing_strategy(pricing_factors),
                'regional_benchmarks': self._get_regional_benchmarks(offer_id, geo_context)
            }
            
            # Cache optimization results
            cache_key = f"geo_pricing_optimization:{offer_id}:{hash(str(geo_context))}"
            cache.set(cache_key, optimization_results, self.cache_timeout)
            
            # Log optimization
            self._log_geo_pricing_optimization(optimization_results)
            
            logger.info(f"Geo-pricing optimization completed for offer {offer_id}")
            
            return optimization_results
            
        except Exception as e:
            logger.error(f"Error optimizing geo-pricing for offer {offer_id}: {e}")
            return {'error': str(e)}
    
    def analyze_geo_performance(self, tenant_id: int, time_window: int = 30) -> Dict[str, any]:
        """
        Analyze geographic performance for tenant.
        
        Args:
            tenant_id: Tenant ID to analyze
            time_window: Time window in days
            
        Returns:
            Dictionary containing geographic performance analysis
        """
        try:
            # Get geographic performance data
            geo_performance = self._get_comprehensive_geo_performance(tenant_id, time_window)
            
            # Calculate regional metrics
            regional_metrics = self._calculate_regional_metrics(geo_performance)
            
            # Identify top performing regions
            top_regions = self._identify_top_performing_regions(geo_performance)
            
            # Identify underperforming regions
            underperforming_regions = self._identify_underperforming_regions(geo_performance)
            
            # Calculate geographic trends
            geo_trends = self._calculate_geographic_trends(geo_performance)
            
            # Get market penetration analysis
            market_penetration = self._analyze_market_penetration(geo_performance)
            
            # Build analysis results
            analysis_results = {
                'tenant_id': tenant_id,
                'time_window': time_window,
                'geo_performance': geo_performance,
                'regional_metrics': regional_metrics,
                'top_regions': top_regions,
                'underperforming_regions': underperforming_regions,
                'geo_trends': geo_trends,
                'market_penetration': market_penetration,
                'analysis_time': timezone.now().isoformat(),
                'recommendations': self._generate_geo_performance_recommendations(geo_performance),
                'opportunity_score': self._calculate_geo_opportunity_score(geo_performance),
                'performance_variance': self._calculate_geo_performance_variance(geo_performance)
            }
            
            # Cache analysis results
            cache_key = f"geo_performance_analysis:{tenant_id}:{time_window}"
            cache.set(cache_key, analysis_results, self.cache_timeout)
            
            logger.info(f"Geographic performance analysis completed for tenant {tenant_id}")
            
            return analysis_results
            
        except Exception as e:
            logger.error(f"Error analyzing geographic performance for tenant {tenant_id}: {e}")
            return {'error': str(e)}
    
    def optimize_geo_targeting(self, tenant_id: int, campaign_budget: float = 10000) -> Dict[str, any]:
        """
        Optimize geographic targeting for campaigns.
        
        Args:
            tenant_id: Tenant ID to optimize for
            campaign_budget: Campaign budget for optimization
            
        Returns:
            Dictionary containing geo-targeting optimization results
        """
        try:
            # Get current geo performance
            geo_performance = self._get_comprehensive_geo_performance(tenant_id, 30)
            
            # Calculate ROI by region
            regional_roi = self._calculate_regional_roi(geo_performance)
            
            # Optimize budget allocation
            budget_allocation = self._optimize_geo_budget_allocation(regional_roi, campaign_budget)
            
            # Get targeting recommendations
            targeting_recommendations = self._generate_geo_targeting_recommendations(geo_performance, budget_allocation)
            
            # Calculate expected performance
            expected_performance = self._calculate_expected_geo_performance(geo_performance, budget_allocation)
            
            # Build optimization results
            optimization_results = {
                'tenant_id': tenant_id,
                'campaign_budget': campaign_budget,
                'geo_performance': geo_performance,
                'regional_roi': regional_roi,
                'budget_allocation': budget_allocation,
                'targeting_recommendations': targeting_recommendations,
                'expected_performance': expected_performance,
                'optimization_time': timezone.now().isoformat(),
                'confidence_level': self._calculate_optimization_confidence(geo_performance),
                'risk_assessment': self._assess_geo_targeting_risks(geo_performance),
                'market_opportunities': self._identify_geo_market_opportunities(geo_performance)
            }
            
            # Cache optimization results
            cache_key = f"geo_targeting_optimization:{tenant_id}"
            cache.set(cache_key, optimization_results, self.cache_timeout)
            
            logger.info(f"Geo-targeting optimization completed for tenant {tenant_id}")
            
            return optimization_results
            
        except Exception as e:
            logger.error(f"Error optimizing geo-targeting for tenant {tenant_id}: {e}")
            return {'error': str(e)}
    
    def get_geo_revenue_breakdown(self, offer_id: int, time_window: int = 30) -> Dict[str, any]:
        """
        Get detailed geographic revenue breakdown for offer.
        
        Args:
            offer_id: Offer ID to analyze
            time_window: Time window in days
            
        Returns:
            Dictionary containing geographic revenue breakdown
        """
        try:
            # Get offer details
            offer = self._get_offer_details(offer_id)
            if not offer:
                return {'error': 'Offer not found'}
            
            # Get geographic revenue data
            geo_revenue = self._get_geo_revenue_data(offer_id, time_window)
            
            # Calculate revenue metrics by geography
            revenue_by_country = self._calculate_revenue_by_country(geo_revenue)
            revenue_by_region = self._calculate_revenue_by_region(geo_revenue)
            revenue_by_city = self._calculate_revenue_by_city(geo_revenue)
            
            # Calculate performance metrics
            performance_metrics = self._calculate_geo_performance_metrics(geo_revenue)
            
            # Identify revenue patterns
            revenue_patterns = self._identify_revenue_patterns(geo_revenue)
            
            # Get competitive analysis
            competitive_analysis = self._get_geo_competitive_analysis(offer_id, geo_revenue)
            
            # Build breakdown results
            breakdown_results = {
                'offer_id': offer_id,
                'time_window': time_window,
                'geo_revenue': geo_revenue,
                'revenue_by_country': revenue_by_country,
                'revenue_by_region': revenue_by_region,
                'revenue_by_city': revenue_by_city,
                'performance_metrics': performance_metrics,
                'revenue_patterns': revenue_patterns,
                'competitive_analysis': competitive_analysis,
                'analysis_time': timezone.now().isoformat(),
                'total_revenue': sum(revenue['revenue'] for revenue in geo_revenue),
                'top_geo_markets': self._identify_top_geo_markets(geo_revenue),
                'growth_opportunities': self._identify_geo_growth_opportunities(geo_revenue)
            }
            
            logger.info(f"Geographic revenue breakdown completed for offer {offer_id}")
            
            return breakdown_results
            
        except Exception as e:
            logger.error(f"Error getting geo revenue breakdown for offer {offer_id}: {e}")
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
    
    def _get_geo_performance_data(self, offer_id: int, geo_context: Dict[str, any]) -> Dict[str, any]:
        """Get geographic performance data for offer."""
        try:
            country = geo_context.get('country')
            region = geo_context.get('region')
            city = geo_context.get('city')
            
            # Get performance data with geo filters
            performance_data = RoutePerformanceStat.objects.filter(
                offer_id=offer_id,
                date__gte=timezone.now() - timedelta(days=self.geo_analysis_days)
            )
            
            if country:
                performance_data = performance_data.filter(country=country)
            
            if region:
                performance_data = performance_data.filter(region=region)
            
            if city:
                performance_data = performance_data.filter(city=city)
            
            # Aggregate by geography
            geo_performance = performance_data.values('country', 'region', 'city').annotate(
                total_revenue=Sum('revenue'),
                total_conversions=Sum('conversions'),
                total_impressions=Sum('impressions'),
                avg_revenue=Avg('revenue'),
                conversion_rate=Avg('conversion_rate'),
                epc=Avg('epc'),
                performance_days=Count('date')
            ).order_by('-total_revenue')
            
            return list(geo_performance)
            
        except Exception as e:
            logger.error(f"Error getting geo performance data: {e}")
            return []
    
    def _calculate_geo_pricing_factors(self, geo_performance: List[Dict], geo_context: Dict[str, any]) -> Dict[str, float]:
        """Calculate geographic pricing factors."""
        try:
            factors = {}
            
            # Country-level factor
            country_performance = next(
                (perf for perf in geo_performance if perf['country'] == geo_context.get('country')),
                None
            )
            
            if country_performance:
                factors['country_performance'] = min(country_performance['avg_revenue'] / 10, 2.0)  # Normalize to 0-2 scale
            
            # Regional factor
            region_performance = next(
                (perf for perf in geo_performance if perf['region'] == geo_context.get('region')),
                None
            )
            
            if region_performance:
                factors['regional_performance'] = min(region_performance['avg_revenue'] / 8, 1.8)  # Normalize to 0-1.8 scale
            
            # Market demand factor
            total_impressions = sum(perf['total_impressions'] for perf in geo_performance)
            if total_impressions > 0:
                factors['market_demand'] = min(total_impressions / 10000, 1.5)  # Normalize to 0-1.5 scale
            
            # Competition factor
            avg_revenue_by_geo = sum(perf['avg_revenue'] for perf in geo_performance) / len(geo_performance) if geo_performance else 0
            if country_performance and avg_revenue_by_geo > 0:
                factors['competition'] = min(avg_revenue_by_geo / country_performance['avg_revenue'], 1.3)  # Lower competition = higher price
            
            # Economic factor (placeholder - would integrate with economic data)
            factors['economic_factor'] = 1.0  # Would be based on GDP, income levels, etc.
            
            # Seasonal factor
            current_month = timezone.now().month
            factors['seasonal_factor'] = self._calculate_seasonal_geo_factor(current_month, geo_context.get('country'))
            
            return factors
            
        except Exception as e:
            logger.error(f"Error calculating geo pricing factors: {e}")
            return {}
    
    def _apply_geo_pricing_adjustments(self, offer: OfferRoute, pricing_factors: Dict[str, float]) -> Dict[str, any]:
        """Apply geographic pricing adjustments to offer."""
        try:
            base_price = offer.base_price or 1.0
            
            # Calculate adjusted prices by geography
            country = pricing_factors.get('country_performance', 1.0)
            region = pricing_factors.get('regional_performance', 1.0)
            demand = pricing_factors.get('market_demand', 1.0)
            competition = pricing_factors.get('competition', 1.0)
            economic = pricing_factors.get('economic_factor', 1.0)
            seasonal = pricing_factors.get('seasonal_factor', 1.0)
            
            # Calculate weighted adjustment
            weights = {
                'country_performance': 0.3,
                'regional_performance': 0.2,
                'market_demand': 0.2,
                'competition': 0.15,
                'economic_factor': 0.1,
                'seasonal_factor': 0.05
            }
            
            weighted_factor = 0.0
            total_weight = 0.0
            
            for factor_name, weight in weights.items():
                if factor_name in pricing_factors:
                    weighted_factor += pricing_factors[factor_name] * weight
                    total_weight += weight
            
            if total_weight > 0:
                weighted_factor /= total_weight
            
            # Apply adjustments
            adjusted_prices = {
                'country_adjusted': base_price * country,
                'regional_adjusted': base_price * region,
                'demand_adjusted': base_price * demand,
                'competition_adjusted': base_price * competition,
                'economic_adjusted': base_price * economic,
                'seasonal_adjusted': base_price * seasonal,
                'final_adjusted': base_price * weighted_factor,
                'adjustment_factors': pricing_factors,
                'weights': weights
            }
            
            # Apply constraints
            min_price = offer.min_price or 0.01
            max_price = offer.max_price or 100.0
            
            for key in adjusted_prices:
                if key != 'adjustment_factors' and key != 'weights':
                    adjusted_prices[key] = max(min(adjusted_prices[key], min_price), max_price)
            
            return adjusted_prices
            
        except Exception as e:
            logger.error(f"Error applying geo pricing adjustments: {e}")
            return {}
    
    def _calculate_geo_revenue_impact(self, offer: OfferRoute, optimized_prices: Dict[str, any], geo_performance: List[Dict]) -> Dict[str, any]:
        """Calculate revenue impact of geo-pricing optimization."""
        try:
            base_price = offer.base_price or 1.0
            final_price = optimized_prices.get('final_adjusted', base_price)
            
            # Calculate price change
            price_change = (final_price - base_price) / base_price * 100
            
            # Estimate revenue impact
            if geo_performance:
                avg_revenue = sum(perf['avg_revenue'] for perf in geo_performance) / len(geo_performance)
                estimated_revenue_change = price_change * avg_revenue * 0.5  # Assume 50% elasticity
            else:
                estimated_revenue_change = 0
            
            # Calculate confidence
            confidence = self._calculate_optimization_confidence(geo_performance)
            
            return {
                'base_price': base_price,
                'final_price': final_price,
                'price_change_percentage': price_change,
                'estimated_revenue_change': estimated_revenue_change,
                'confidence': confidence,
                'risk_level': 'low' if confidence > 0.7 else 'medium' if confidence > 0.5 else 'high'
            }
            
        except Exception as e:
            logger.error(f"Error calculating geo revenue impact: {e}")
            return {}
    
    def _analyze_market_opportunities(self, offer: OfferRoute, geo_context: Dict[str, any], geo_performance: List[Dict]) -> List[Dict[str, any]]:
        """Analyze market opportunities based on geographic data."""
        try:
            opportunities = []
            
            # Identify underserved markets
            if geo_performance:
                avg_revenue = sum(perf['avg_revenue'] for perf in geo_performance) / len(geo_performance)
                
                for perf in geo_performance:
                    if perf['avg_revenue'] < avg_revenue * 0.7:  # 30% below average
                        opportunities.append({
                            'type': 'underserved_market',
                            'location': {
                                'country': perf['country'],
                                'region': perf['region'],
                                'city': perf['city']
                            },
                            'current_performance': perf,
                            'opportunity_score': (avg_revenue - perf['avg_revenue']) / avg_revenue,
                            'recommended_action': 'increase_marketing_effort',
                            'potential_revenue_lift': avg_revenue * 0.3
                        })
            
            # Identify high-potential markets
            for perf in geo_performance:
                if perf['conversion_rate'] and perf['conversion_rate'] > 5.0:  # High conversion rate
                    opportunities.append({
                        'type': 'high_potential_market',
                        'location': {
                            'country': perf['country'],
                            'region': perf['region'],
                            'city': perf['city']
                        },
                        'current_performance': perf,
                        'opportunity_score': min(perf['conversion_rate'] / 10, 1.0),
                        'recommended_action': 'increase_budget_allocation',
                        'potential_revenue_lift': perf['avg_revenue'] * 0.5
                    })
            
            # Sort by opportunity score
            opportunities.sort(key=lambda x: x['opportunity_score'], reverse=True)
            
            return opportunities[:10]  # Top 10 opportunities
            
        except Exception as e:
            logger.error(f"Error analyzing market opportunities: {e}")
            return []
    
    def _calculate_optimization_confidence(self, geo_performance: List[Dict]) -> float:
        """Calculate confidence level for optimization."""
        try:
            if not geo_performance:
                return 0.5
            
            # Calculate data quality factors
            data_points = len(geo_performance)
            data_quality = min(data_points / 50, 1.0)  # More data = higher confidence
            
            # Calculate performance consistency
            revenues = [perf['avg_revenue'] for perf in geo_performance]
            if len(revenues) > 1:
                avg_revenue = sum(revenues) / len(revenues)
                variance = sum((r - avg_revenue) ** 2 for r in revenues) / len(revenues)
                consistency = max(1.0 - (variance / (avg_revenue ** 2)), 0.0)
            else:
                consistency = 0.5
            
            # Calculate recency factor
            recency = 0.8  # Assume recent data is good
            
            # Combine factors
            confidence = (data_quality * 0.4) + (consistency * 0.4) + (recency * 0.2)
            
            return max(min(confidence, 1.0), 0.0)
            
        except Exception as e:
            logger.error(f"Error calculating optimization confidence: {e}")
            return 0.5
    
    def _determine_geo_pricing_strategy(self, pricing_factors: Dict[str, float]) -> str:
        """Determine geographic pricing strategy."""
        try:
            # Analyze dominant factors
            max_factor = max(pricing_factors.items(), key=lambda x: x[1])
            
            if max_factor[1] > 1.3:
                return 'premium_pricing'  # High performance areas
            elif max_factor[1] < 0.8:
                return 'penetration_pricing'  # Low performance areas
            elif pricing_factors.get('market_demand', 0) > 1.2:
                return 'demand_based_pricing'
            elif pricing_factors.get('competition', 0) < 0.8:
                return 'competitive_pricing'
            else:
                return 'balanced_pricing'
                
        except Exception as e:
            logger.error(f"Error determining geo pricing strategy: {e}")
            return 'balanced_pricing'
    
    def _get_regional_benchmarks(self, offer_id: int, geo_context: Dict[str, any]) -> Dict[str, any]:
        """Get regional benchmarks for comparison."""
        try:
            country = geo_context.get('country')
            
            if not country:
                return {}
            
            # Get country-wide performance
            country_performance = RoutePerformanceStat.objects.filter(
                country=country,
                date__gte=timezone.now() - timedelta(days=30)
            ).aggregate(
                avg_revenue=Avg('revenue'),
                avg_conversion_rate=Avg('conversion_rate'),
                avg_epc=Avg('epc'),
                total_offers=Count('offer_id', distinct=True)
            )
            
            # Get regional performance
            region = geo_context.get('region')
            if region:
                regional_performance = RoutePerformanceStat.objects.filter(
                    country=country,
                    region=region,
                    date__gte=timezone.now() - timedelta(days=30)
                ).aggregate(
                    avg_revenue=Avg('revenue'),
                    avg_conversion_rate=Avg('conversion_rate'),
                    avg_epc=Avg('epc')
                )
            else:
                regional_performance = country_performance
            
            return {
                'country_benchmark': country_performance,
                'regional_benchmark': regional_performance,
                'performance_ratio': (
                    regional_performance['avg_revenue'] / country_performance['avg_revenue']
                    if country_performance['avg_revenue'] > 0 else 1.0
                )
            }
            
        except Exception as e:
            logger.error(f"Error getting regional benchmarks: {e}")
            return {}
    
    def _log_geo_pricing_optimization(self, optimization_results: Dict[str, any]):
        """Log geo-pricing optimization for analytics."""
        try:
            # Create insight record
            RoutingInsight.objects.create(
                tenant_id=optimization_results.get('offer_id'),  # Would need to get tenant from offer
                insight_type='geo_pricing_optimization',
                title=f'Geo Pricing Optimization for Offer {optimization_results["offer_id"]}',
                description=f'Optimized pricing for {optimization_results["geo_context"]["country"]}',
                data=optimization_results
            )
            
        except Exception as e:
            logger.error(f"Error logging geo pricing optimization: {e}")
    
    def _get_comprehensive_geo_performance(self, tenant_id: int, time_window: int) -> List[Dict[str, any]]:
        """Get comprehensive geographic performance data."""
        try:
            cutoff_date = timezone.now() - timedelta(days=time_window)
            
            # Get performance data grouped by geography
            geo_performance = RoutePerformanceStat.objects.filter(
                tenant_id=tenant_id,
                date__gte=cutoff_date
            ).values('country', 'region', 'city').annotate(
                total_revenue=Sum('revenue'),
                total_conversions=Sum('conversions'),
                total_impressions=Sum('impressions'),
                avg_revenue=Avg('revenue'),
                conversion_rate=Avg('conversion_rate'),
                epc=Avg('epc'),
                performance_days=Count('date')
            ).order_by('-total_revenue')
            
            return list(geo_performance)
            
        except Exception as e:
            logger.error(f"Error getting comprehensive geo performance: {e}")
            return []
    
    def _calculate_regional_metrics(self, geo_performance: List[Dict[str, any]]) -> Dict[str, any]:
        """Calculate regional performance metrics."""
        try:
            if not geo_performance:
                return {}
            
            # Calculate aggregate metrics
            total_revenue = sum(perf['total_revenue'] for perf in geo_performance)
            total_conversions = sum(perf['total_conversions'] for perf in geo_performance)
            total_impressions = sum(perf['total_impressions'] for perf in geo_performance)
            
            # Calculate top regions
            top_regions = sorted(geo_performance, key=lambda x: x['total_revenue'], reverse=True)[:10]
            
            return {
                'total_regions': len(geo_performance),
                'total_revenue': total_revenue,
                'total_conversions': total_conversions,
                'total_impressions': total_impressions,
                'avg_revenue_per_region': total_revenue / len(geo_performance) if geo_performance else 0,
                'conversion_rate': (total_conversions / total_impressions * 100) if total_impressions > 0 else 0,
                'top_regions': top_regions,
                'revenue_distribution': self._calculate_revenue_distribution(geo_performance)
            }
            
        except Exception as e:
            logger.error(f"Error calculating regional metrics: {e}")
            return {}
    
    def _identify_top_performing_regions(self, geo_performance: List[Dict[str, any]]) -> List[Dict[str, any]]:
        """Identify top performing regions."""
        try:
            if not geo_performance:
                return []
            
            # Sort by revenue and conversion rate
            sorted_performance = sorted(
                geo_performance,
                key=lambda x: (x['total_revenue'] * 0.6 + x['conversion_rate'] * 100 * 0.4),
                reverse=True
            )
            
            return sorted_performance[:20]  # Top 20 regions
            
        except Exception as e:
            logger.error(f"Error identifying top performing regions: {e}")
            return []
    
    def _identify_underperforming_regions(self, geo_performance: List[Dict[str, any]]) -> List[Dict[str, any]]:
        """Identify underperforming regions."""
        try:
            if not geo_performance:
                return []
            
            # Calculate performance thresholds
            avg_revenue = sum(perf['total_revenue'] for perf in geo_performance) / len(geo_performance)
            avg_conversion_rate = sum(perf['conversion_rate'] for perf in geo_performance) / len(geo_performance)
            
            # Identify underperformers
            underperformers = []
            for perf in geo_performance:
                revenue_score = perf['total_revenue'] / avg_revenue if avg_revenue > 0 else 1.0
                conversion_score = perf['conversion_rate'] / avg_conversion_rate if avg_conversion_rate > 0 else 1.0
                
                overall_score = (revenue_score * 0.7 + conversion_score * 0.3)
                
                if overall_score < 0.7:  # 30% below average
                    underperformers.append({
                        'region': perf,
                        'performance_score': overall_score,
                        'revenue_gap': avg_revenue - perf['total_revenue'],
                        'conversion_gap': avg_conversion_rate - perf['conversion_rate']
                    })
            
            return sorted(underperformers, key=lambda x: x['performance_score'])[:10]
            
        except Exception as e:
            logger.error(f"Error identifying underperforming regions: {e}")
            return []
    
    def _calculate_geographic_trends(self, geo_performance: List[Dict[str, any]]) -> Dict[str, any]:
        """Calculate geographic performance trends."""
        try:
            if not geo_performance:
                return {}
            
            # This would implement trend analysis over time
            # For now, return placeholder data
            return {
                'trend_direction': 'stable',
                'growth_rate': 0.05,
                'volatility': 0.15,
                'seasonal_pattern': 'none'
            }
            
        except Exception as e:
            logger.error(f"Error calculating geographic trends: {e}")
            return {}
    
    def _analyze_market_penetration(self, geo_performance: List[Dict[str, any]]) -> Dict[str, any]:
        """Analyze market penetration by geography."""
        try:
            if not geo_performance:
                return {}
            
            # Calculate penetration metrics
            total_impressions = sum(perf['total_impressions'] for perf in geo_performance)
            total_conversions = sum(perf['total_conversions'] for perf in geo_performance)
            
            penetration_by_region = {}
            for perf in geo_performance:
                region_key = f"{perf['country']}-{perf['region']}"
                region_impressions = perf['total_impressions']
                region_conversions = perf['total_conversions']
                
                penetration_by_region[region_key] = {
                    'impressions': region_impressions,
                    'conversions': region_conversions,
                    'penetration_rate': (region_conversions / region_impressions * 100) if region_impressions > 0 else 0,
                    'market_share': region_impressions / total_impressions if total_impressions > 0 else 0
                }
            
            return {
                'total_impressions': total_impressions,
                'total_conversions': total_conversions,
                'overall_penetration_rate': (total_conversions / total_impressions * 100) if total_impressions > 0 else 0,
                'penetration_by_region': penetration_by_region,
                'top_penetrated_regions': sorted(
                    penetration_by_region.items(),
                    key=lambda x: x[1]['penetration_rate'],
                    reverse=True
                )[:10]
            }
            
        except Exception as e:
            logger.error(f"Error analyzing market penetration: {e}")
            return {}
    
    def _generate_geo_performance_recommendations(self, geo_performance: List[Dict[str, any]]) -> List[str]:
        """Generate recommendations based on geographic performance."""
        try:
            recommendations = []
            
            if not geo_performance:
                return recommendations
            
            # Analyze performance distribution
            revenues = [perf['total_revenue'] for perf in geo_performance]
            if len(revenues) > 1:
                avg_revenue = sum(revenues) / len(revenues)
                std_revenue = math.sqrt(sum((r - avg_revenue) ** 2 for r in revenues) / len(revenues))
                
                # High variance indicates opportunity
                if std_revenue / avg_revenue > 0.5:
                    recommendations.append("High revenue variance detected - consider regional pricing optimization")
                
                # Low average revenue indicates opportunity
                if avg_revenue < 10:
                    recommendations.append("Low average revenue - consider market expansion or offer optimization")
            
            # Check conversion rates
            conversion_rates = [perf['conversion_rate'] for perf in geo_performance if perf['conversion_rate']]
            if conversion_rates:
                avg_conversion = sum(conversion_rates) / len(conversion_rates)
                
                if avg_conversion < 2:
                    recommendations.append("Low conversion rates - consider improving offer quality or targeting")
                elif avg_conversion > 8:
                    recommendations.append("High conversion rates - consider increasing prices or expanding reach")
            
            return recommendations[:10]  # Top 10 recommendations
            
        except Exception as e:
            logger.error(f"Error generating geo performance recommendations: {e}")
            return []
    
    def _calculate_geo_opportunity_score(self, geo_performance: List[Dict[str, any]]) -> float:
        """Calculate overall geographic opportunity score."""
        try:
            if not geo_performance:
                return 0.5
            
            # Calculate opportunity factors
            revenue_variance = self._calculate_revenue_variance(geo_performance)
            untapped_potential = self._calculate_untapped_potential(geo_performance)
            market_growth = self._calculate_market_growth_potential(geo_performance)
            
            # Combine into opportunity score
            opportunity_score = (
                revenue_variance * 0.3 +
                untapped_potential * 0.4 +
                market_growth * 0.3
            )
            
            return max(min(opportunity_score, 1.0), 0.0)
            
        except Exception as e:
            logger.error(f"Error calculating geo opportunity score: {e}")
            return 0.5
    
    def _calculate_revenue_variance(self, geo_performance: List[Dict[str, any]]) -> float:
        """Calculate revenue variance across regions."""
        try:
            if not geo_performance:
                return 0.0
            
            revenues = [perf['total_revenue'] for perf in geo_performance]
            if len(revenues) < 2:
                return 0.0
            
            avg_revenue = sum(revenues) / len(revenues)
            variance = sum((r - avg_revenue) ** 2 for r in revenues) / len(revenues)
            
            # Normalize to 0-1 scale
            max_possible_variance = avg_revenue ** 2  # Maximum possible variance
            return min(variance / max_possible_variance, 1.0) if max_possible_variance > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating revenue variance: {e}")
            return 0.0
    
    def _calculate_untapped_potential(self, geo_performance: List[Dict[str, any]]) -> float:
        """Calculate untapped market potential."""
        try:
            if not geo_performance:
                return 0.5
            
            # This would integrate with market size data
            # For now, use a heuristic based on performance gaps
            conversion_rates = [perf['conversion_rate'] for perf in geo_performance if perf['conversion_rate']]
            
            if conversion_rates:
                avg_conversion = sum(conversion_rates) / len(conversion_rates)
                max_conversion = max(conversion_rates)
                
                # High gap between max and average indicates untapped potential
                potential_gap = (max_conversion - avg_conversion) / max_conversion if max_conversion > 0 else 0
                return min(potential_gap, 1.0)
            
            return 0.5
            
        except Exception as e:
            logger.error(f"Error calculating untapped potential: {e}")
            return 0.5
    
    def _calculate_market_growth_potential(self, geo_performance: List[Dict[str, any]]) -> float:
        """Calculate market growth potential."""
        try:
            if not geo_performance:
                return 0.5
            
            # This would integrate with market growth data
            # For now, use a heuristic based on recent performance trends
            # Placeholder implementation
            return 0.6
            
        except Exception as e:
            logger.error(f"Error calculating market growth potential: {e}")
            return 0.5
    
    def _calculate_revenue_distribution(self, geo_performance: List[Dict[str, any]]) -> Dict[str, any]:
        """Calculate revenue distribution statistics."""
        try:
            if not geo_performance:
                return {}
            
            revenues = [perf['total_revenue'] for perf in geo_performance]
            
            if not revenues:
                return {}
            
            # Calculate distribution metrics
            sorted_revenues = sorted(revenues)
            n = len(sorted_revenues)
            
            # Calculate percentiles
            p25 = sorted_revenues[n // 4] if n >= 4 else 0
            p50 = sorted_revenues[n // 2] if n >= 2 else 0
            p75 = sorted_revenues[3 * n // 4] if n >= 4 else 0
            
            return {
                'min': min(revenues),
                'max': max(revenues),
                'mean': sum(revenues) / n,
                'median': p50,
                'p25': p25,
                'p75': p75,
                'std_dev': math.sqrt(sum((r - sum(revenues) / n) ** 2 for r in revenues) / n),
                'skewness': self._calculate_skewness(revenues)
            }
            
        except Exception as e:
            logger.error(f"Error calculating revenue distribution: {e}")
            return {}
    
    def _calculate_skewness(self, data: List[float]) -> float:
        """Calculate skewness of data distribution."""
        try:
            if len(data) < 3:
                return 0.0
            
            n = len(data)
            mean = sum(data) / n
            std_dev = math.sqrt(sum((x - mean) ** 2 for x in data) / n)
            
            if std_dev == 0:
                return 0.0
            
            skewness = sum((x - mean) ** 3 for x in data) / (n * std_dev ** 3)
            return skewness
            
        except Exception as e:
            logger.error(f"Error calculating skewness: {e}")
            return 0.0
    
    def _calculate_seasonal_geo_factor(self, month: int, country: str) -> float:
        """Calculate seasonal geographic factor."""
        try:
            # This would integrate with seasonal data by country
            # For now, use a simple seasonal pattern
            seasonal_factors = {
                1: 0.9,   # January - post holiday slowdown
                2: 0.85,  # February - winter
                3: 0.95,  # March - spring beginning
                4: 1.0,   # April - spring
                5: 1.05,  # May - late spring
                6: 1.1,   # June - summer beginning
                7: 1.15,  # July - summer
                8: 1.1,   # August - summer
                9: 1.05,  # September - back to school
                10: 1.0,  # October - fall
                11: 1.05, # November - pre-holiday
                12: 1.2   # December - holiday season
            }
            
            return seasonal_factors.get(month, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating seasonal geo factor: {e}")
            return 1.0


# Global geo revenue service instance
geo_revenue_service = GeoRevenueService()
