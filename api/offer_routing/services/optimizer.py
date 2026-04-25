"""
Optimizer Service for Offer Routing System

This module provides optimization functionality to improve
routing performance, configuration, and results.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Avg, Count, Sum, Max, Min, Q, F
from ..models import (
    OfferRoute, RoutePerformanceStat, RoutingDecisionLog,
    PersonalizationConfig, OfferScoreConfig
)
from ..constants import MAX_ROUTING_TIME_MS, DEFAULT_ROUTE_PRIORITY
from ..exceptions import ValidationError

User = get_user_model()
logger = logging.getLogger(__name__)


class RoutingOptimizer:
    """
    Service for optimizing routing configurations and performance.
    
    Provides optimization algorithms for routes, scores,
    and personalization settings.
    """
    
    def __init__(self):
        self.cache_service = None
        self.analytics_service = None
        
        # Initialize services
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize optimizer services."""
        try:
            from .cache import RoutingCacheService
            from .analytics import RoutingAnalyticsService
            
            self.cache_service = RoutingCacheService()
            self.analytics_service = RoutingAnalyticsService()
        except ImportError as e:
            logger.error(f"Failed to initialize optimizer services: {e}")
    
    def optimize_route_priorities(self, tenant_id: int) -> Dict[str, Any]:
        """Optimize route priorities based on performance data."""
        try:
            optimization_result = {
                'optimized_routes': 0,
                'route_changes': [],
                'performance_improvement': 0.0,
                'recommendations': []
            }
            
            # Get route performance data
            routes = OfferRoute.objects.filter(tenant_id=tenant_id, is_active=True)
            
            if not routes.exists():
                return optimization_result
            
            # Calculate performance scores for each route
            route_scores = []
            for route in routes:
                score = self._calculate_route_performance_score(route)
                route_scores.append({
                    'route': route,
                    'score': score,
                    'current_priority': route.priority
                })
            
            # Sort by performance score (descending)
            route_scores.sort(key=lambda x: x['score'], reverse=True)
            
            # Assign new priorities based on performance
            for i, route_data in enumerate(route_scores):
                new_priority = i + 1
                
                if route_data['route'].priority != new_priority:
                    # Update priority
                    route_data['route'].priority = new_priority
                    route_data['route'].save()
                    
                    optimization_result['route_changes'].append({
                        'route_id': route_data['route'].id,
                        'route_name': route_data['route'].name,
                        'old_priority': route_data['current_priority'],
                        'new_priority': new_priority,
                        'performance_score': route_data['score']
                    })
                    
                    optimization_result['optimized_routes'] += 1
            
            # Calculate expected performance improvement
            if optimization_result['optimized_routes'] > 0:
                optimization_result['performance_improvement'] = self._estimate_priority_improvement(
                    optimization_result['route_changes']
                )
            
            # Generate recommendations
            optimization_result['recommendations'] = self._generate_priority_recommendations(route_scores)
            
            logger.info(f"Optimized priorities for {optimization_result['optimized_routes']} routes")
            return optimization_result
            
        except Exception as e:
            logger.error(f"Error optimizing route priorities: {e}")
            return {
                'optimized_routes': 0,
                'route_changes': [],
                'performance_improvement': 0.0,
                'recommendations': [],
                'error': str(e)
            }
    
    def _calculate_route_performance_score(self, route: OfferRoute) -> float:
        """Calculate performance score for a route."""
        try:
            # Get recent performance stats
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=30)
            
            stats = RoutePerformanceStat.objects.filter(
                route=route,
                date__gte=cutoff_date.date()
            ).aggregate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                avg_response_time=Avg('avg_response_time_ms'),
                avg_cache_hit_rate=Avg('cache_hit_rate')
            )
            
            if not stats['total_impressions']:
                return 0.0
            
            # Calculate performance metrics
            total_impressions = stats['total_impressions'] or 0
            total_clicks = stats['total_clicks'] or 0
            total_conversions = stats['total_conversions'] or 0
            avg_response_time = stats['avg_response_time'] or 0
            avg_cache_hit_rate = stats['avg_cache_hit_rate'] or 0
            
            # Calculate individual scores
            click_rate = (total_clicks / total_impressions) * 100
            conversion_rate = (total_conversions / total_impressions) * 100
            response_time_score = max(0, 100 - (avg_response_time / MAX_ROUTING_TIME_MS * 100))
            cache_score = avg_cache_hit_rate
            
            # Calculate weighted overall score
            performance_score = (
                (conversion_rate * 0.4) +
                (click_rate * 0.3) +
                (response_time_score * 0.2) +
                (cache_score * 0.1)
            )
            
            return performance_score
            
        except Exception as e:
            logger.error(f"Error calculating route performance score: {e}")
            return 0.0
    
    def _estimate_priority_improvement(self, route_changes: List[Dict[str, Any]]) -> float:
        """Estimate performance improvement from priority changes."""
        try:
            if not route_changes:
                return 0.0
            
            # Simple heuristic: higher priority routes get more impressions
            # Calculate expected improvement based on priority changes
            total_improvement = 0.0
            
            for change in route_changes:
                old_priority = change['old_priority']
                new_priority = change['new_priority']
                performance_score = change['performance_score']
                
                # Estimate improvement based on priority change and performance
                if new_priority < old_priority:  # Higher priority
                    priority_improvement = (old_priority - new_priority) * 0.1
                    performance_improvement = performance_score * priority_improvement
                    total_improvement += performance_improvement
            
            return total_improvement
            
        except Exception as e:
            logger.error(f"Error estimating priority improvement: {e}")
            return 0.0
    
    def _generate_priority_recommendations(self, route_scores: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on priority optimization."""
        recommendations = []
        
        try:
            # Check for low-performing high-priority routes
            for route_data in route_scores[:5]:  # Top 5 routes
                if route_data['score'] < 30:  # Low performance
                    recommendations.append(
                        f"Consider reviewing route '{route_data['route'].name}' - "
                        f"high priority but low performance score ({route_data['score']:.1f})"
                    )
            
            # Check for high-performing low-priority routes
            for route_data in route_scores[-5:]:  # Bottom 5 routes
                if route_data['score'] > 70:  # High performance
                    recommendations.append(
                        f"Consider increasing priority for route '{route_data['route'].name}' - "
                        f"low priority but high performance score ({route_data['score']:.1f})"
                    )
            
            # General recommendations
            if len(route_scores) > 20:
                recommendations.append("Consider deactivating low-performing routes to improve overall performance")
            
            if not recommendations:
                recommendations.append("Route priorities appear well-optimized")
            
        except Exception as e:
            logger.error(f"Error generating priority recommendations: {e}")
        
        return recommendations
    
    def optimize_score_weights(self, tenant_id: int) -> Dict[str, Any]:
        """Optimize score weights based on performance data."""
        try:
            optimization_result = {
                'optimized_configs': 0,
                'config_changes': [],
                'performance_improvement': 0.0,
                'recommendations': []
            }
            
            # Get score configurations
            configs = OfferScoreConfig.objects.filter(tenant_id=tenant_id, is_active=True)
            
            for config in configs:
                # Calculate optimal weights for this offer
                optimal_weights = self._calculate_optimal_weights(config.offer)
                
                if optimal_weights:
                    # Compare with current weights
                    current_weights = {
                        'epc_weight': float(config.epc_weight),
                        'cr_weight': float(config.cr_weight),
                        'relevance_weight': float(config.relevance_weight),
                        'freshness_weight': float(config.freshness_weight)
                    }
                    
                    # Calculate difference
                    weight_diff = self._calculate_weight_difference(current_weights, optimal_weights)
                    
                    if weight_diff['total_difference'] > 0.2:  # Significant difference
                        # Update configuration
                        config.epc_weight = optimal_weights['epc_weight']
                        config.cr_weight = optimal_weights['cr_weight']
                        config.relevance_weight = optimal_weights['relevance_weight']
                        config.freshness_weight = optimal_weights['freshness_weight']
                        config.save()
                        
                        optimization_result['config_changes'].append({
                            'offer_id': config.offer.id,
                            'offer_name': config.offer.name,
                            'old_weights': current_weights,
                            'new_weights': optimal_weights,
                            'difference': weight_diff
                        })
                        
                        optimization_result['optimized_configs'] += 1
            
            # Calculate overall performance improvement
            if optimization_result['optimized_configs'] > 0:
                optimization_result['performance_improvement'] = self._estimate_weight_improvement(
                    optimization_result['config_changes']
                )
            
            # Generate recommendations
            optimization_result['recommendations'] = self._generate_weight_recommendations(
                optimization_result['config_changes']
            )
            
            logger.info(f"Optimized score weights for {optimization_result['optimized_configs']} offers")
            return optimization_result
            
        except Exception as e:
            logger.error(f"Error optimizing score weights: {e}")
            return {
                'optimized_configs': 0,
                'config_changes': [],
                'performance_improvement': 0.0,
                'recommendations': [],
                'error': str(e)
            }
    
    def _calculate_optimal_weights(self, offer: Any) -> Optional[Dict[str, float]]:
        """Calculate optimal weights for an offer based on performance data."""
        try:
            # Get performance data for this offer
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=30)
            
            stats = RoutePerformanceStat.objects.filter(
                offer=offer,
                date__gte=cutoff_date.date()
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
            
            click_rate = (total_clicks / total_impressions) * 100
            conversion_rate = (total_conversions / total_impressions) * 100
            epc = total_revenue / total_clicks if total_clicks > 0 else 0
            
            # Calculate optimal weights based on performance
            # Higher performing metrics get higher weights
            weights = {
                'epc_weight': min(epc * 10, 0.5),  # Cap at 0.5
                'cr_weight': min(conversion_rate, 0.4),  # Cap at 0.4
                'relevance_weight': 0.2,  # Fixed weight for relevance
                'freshness_weight': 0.1   # Fixed weight for freshness
            }
            
            # Normalize weights to sum to 1.0
            total_weight = sum(weights.values())
            if total_weight > 0:
                for key in weights:
                    weights[key] = weights[key] / total_weight
            
            return weights
            
        except Exception as e:
            logger.error(f"Error calculating optimal weights: {e}")
            return None
    
    def _calculate_weight_difference(self, current_weights: Dict[str, float], 
                                   optimal_weights: Dict[str, float]) -> Dict[str, Any]:
        """Calculate difference between current and optimal weights."""
        try:
            differences = {}
            total_difference = 0.0
            
            for key in current_weights:
                diff = abs(current_weights[key] - optimal_weights.get(key, 0))
                differences[key] = diff
                total_difference += diff
            
            return {
                'differences': differences,
                'total_difference': total_difference
            }
            
        except Exception as e:
            logger.error(f"Error calculating weight difference: {e}")
            return {'differences': {}, 'total_difference': 0.0}
    
    def _estimate_weight_improvement(self, config_changes: List[Dict[str, Any]]) -> float:
        """Estimate performance improvement from weight changes."""
        try:
            if not config_changes:
                return 0.0
            
            total_improvement = 0.0
            
            for change in config_changes:
                difference = change['difference']['total_difference']
                # Estimate improvement based on weight difference
                improvement = difference * 10  # Heuristic: 1% weight difference = 10% performance improvement
                total_improvement += improvement
            
            return min(total_improvement / len(config_changes), 50.0)  # Cap at 50%
            
        except Exception as e:
            logger.error(f"Error estimating weight improvement: {e}")
            return 0.0
    
    def _generate_weight_recommendations(self, config_changes: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on weight optimization."""
        recommendations = []
        
        try:
            if not config_changes:
                recommendations.append("Score weights appear well-optimized")
                return recommendations
            
            # Analyze common patterns in weight changes
            epc_increases = sum(1 for change in config_changes 
                              if change['new_weights']['epc_weight'] > change['old_weights']['epc_weight'])
            cr_increases = sum(1 for change in config_changes 
                             if change['new_weights']['cr_weight'] > change['old_weights']['cr_weight'])
            
            if epc_increases > len(config_changes) * 0.7:
                recommendations.append("EPC is becoming more important - consider focusing on revenue optimization")
            
            if cr_increases > len(config_changes) * 0.7:
                recommendations.append("Conversion rate is becoming more important - consider focusing on user experience")
            
            # General recommendations
            recommendations.append("Monitor performance after weight changes to validate improvements")
            recommendations.append("Consider A/B testing new weight configurations")
            
        except Exception as e:
            logger.error(f"Error generating weight recommendations: {e}")
        
        return recommendations
    
    def optimize_personalization_config(self, tenant_id: int) -> Dict[str, Any]:
        """Optimize personalization configuration."""
        try:
            optimization_result = {
                'optimized_configs': 0,
                'config_changes': [],
                'performance_improvement': 0.0,
                'recommendations': []
            }
            
            # Get personalization configurations
            configs = PersonalizationConfig.objects.filter(tenant_id=tenant_id, is_active=True)
            
            for config in configs:
                # Calculate optimal personalization settings
                optimal_config = self._calculate_optimal_personalization_config(config.user)
                
                if optimal_config:
                    # Compare with current config
                    current_config = {
                        'algorithm': config.algorithm,
                        'collaborative_weight': float(config.collaborative_weight),
                        'content_based_weight': float(config.content_based_weight),
                        'hybrid_weight': float(config.hybrid_weight),
                        'real_time_enabled': config.real_time_enabled,
                        'real_time_weight': float(config.real_time_weight)
                    }
                    
                    # Calculate difference
                    config_diff = self._calculate_personalization_config_difference(
                        current_config, optimal_config
                    )
                    
                    if config_diff['significant_changes']:
                        # Update configuration
                        config.algorithm = optimal_config['algorithm']
                        config.collaborative_weight = optimal_config['collaborative_weight']
                        config.content_based_weight = optimal_config['content_based_weight']
                        config.hybrid_weight = optimal_config['hybrid_weight']
                        config.real_time_enabled = optimal_config['real_time_enabled']
                        config.real_time_weight = optimal_config['real_time_weight']
                        config.save()
                        
                        optimization_result['config_changes'].append({
                            'user_id': config.user.id,
                            'old_config': current_config,
                            'new_config': optimal_config,
                            'difference': config_diff
                        })
                        
                        optimization_result['optimized_configs'] += 1
            
            # Generate recommendations
            optimization_result['recommendations'] = self._generate_personalization_recommendations(
                optimization_result['config_changes']
            )
            
            logger.info(f"Optimized personalization for {optimization_result['optimized_configs']} users")
            return optimization_result
            
        except Exception as e:
            logger.error(f"Error optimizing personalization config: {e}")
            return {
                'optimized_configs': 0,
                'config_changes': [],
                'performance_improvement': 0.0,
                'recommendations': [],
                'error': str(e)
            }
    
    def _calculate_optimal_personalization_config(self, user: User) -> Optional[Dict[str, Any]]:
        """Calculate optimal personalization configuration for a user."""
        try:
            # Get user's interaction history
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=30)
            
            user_history = RoutingDecisionLog.objects.filter(
                user=user,
                created_at__gte=cutoff_date
            ).aggregate(
                total_decisions=Count('id'),
                avg_personalization_rate=Avg('personalization_applied'),
                avg_score=Avg('score')
            )
            
            if not user_history['total_decisions']:
                return self._get_default_personalization_config()
            
            # Calculate optimal configuration based on user behavior
            personalization_rate = user_history['avg_personalization_rate'] or 0
            avg_score = user_history['avg_score'] or 0
            
            optimal_config = {
                'algorithm': 'hybrid',
                'collaborative_weight': 0.4,
                'content_based_weight': 0.3,
                'hybrid_weight': 0.3,
                'real_time_enabled': True,
                'real_time_weight': 0.5
            }
            
            # Adjust based on user behavior
            if personalization_rate > 0.8:  # High personalization usage
                optimal_config['real_time_weight'] = 0.7
                optimal_config['collaborative_weight'] = 0.5
                optimal_config['content_based_weight'] = 0.3
                optimal_config['hybrid_weight'] = 0.2
            elif personalization_rate < 0.3:  # Low personalization usage
                optimal_config['real_time_enabled'] = False
                optimal_config['algorithm'] = 'collaborative'
                optimal_config['collaborative_weight'] = 1.0
                optimal_config['content_based_weight'] = 0.0
                optimal_config['hybrid_weight'] = 0.0
            
            return optimal_config
            
        except Exception as e:
            logger.error(f"Error calculating optimal personalization config: {e}")
            return None
    
    def _get_default_personalization_config(self) -> Dict[str, Any]:
        """Get default personalization configuration."""
        return {
            'algorithm': 'hybrid',
            'collaborative_weight': 0.4,
            'content_based_weight': 0.3,
            'hybrid_weight': 0.3,
            'real_time_enabled': True,
            'real_time_weight': 0.5
        }
    
    def _calculate_personalization_config_difference(self, current_config: Dict[str, Any], 
                                                   optimal_config: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate difference between personalization configurations."""
        try:
            differences = {}
            significant_changes = False
            
            # Check algorithm change
            if current_config['algorithm'] != optimal_config['algorithm']:
                differences['algorithm'] = {
                    'current': current_config['algorithm'],
                    'optimal': optimal_config['algorithm']
                }
                significant_changes = True
            
            # Check weight changes
            weight_fields = ['collaborative_weight', 'content_based_weight', 'hybrid_weight', 'real_time_weight']
            for field in weight_fields:
                current_value = current_config.get(field, 0)
                optimal_value = optimal_config.get(field, 0)
                
                if abs(current_value - optimal_value) > 0.1:  # Significant change
                    differences[field] = {
                        'current': current_value,
                        'optimal': optimal_value,
                        'difference': abs(current_value - optimal_value)
                    }
                    significant_changes = True
            
            # Check real_time_enabled change
            if current_config['real_time_enabled'] != optimal_config['real_time_enabled']:
                differences['real_time_enabled'] = {
                    'current': current_config['real_time_enabled'],
                    'optimal': optimal_config['real_time_enabled']
                }
                significant_changes = True
            
            return {
                'differences': differences,
                'significant_changes': significant_changes
            }
            
        except Exception as e:
            logger.error(f"Error calculating personalization config difference: {e}")
            return {'differences': {}, 'significant_changes': False}
    
    def _generate_personalization_recommendations(self, config_changes: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on personalization optimization."""
        recommendations = []
        
        try:
            if not config_changes:
                recommendations.append("Personalization configurations appear well-optimized")
                return recommendations
            
            # Analyze common patterns
            algorithm_changes = sum(1 for change in config_changes 
                                  if 'algorithm' in change['difference']['differences'])
            real_time_changes = sum(1 for change in config_changes 
                                  if 'real_time_enabled' in change['difference']['differences'])
            
            if algorithm_changes > len(config_changes) * 0.5:
                recommendations.append("Consider reviewing algorithm choices - significant changes detected")
            
            if real_time_changes > len(config_changes) * 0.5:
                recommendations.append("Real-time personalization settings are changing - monitor performance impact")
            
            # General recommendations
            recommendations.append("Test personalization changes with A/B tests before full rollout")
            recommendations.append("Monitor user engagement after personalization changes")
            
        except Exception as e:
            logger.error(f"Error generating personalization recommendations: {e}")
        
        return recommendations
    
    def optimize_all_configurations(self, tenant_id: int) -> Dict[str, Any]:
        """Optimize all configurations for a tenant."""
        try:
            optimization_results = {
                'route_priorities': self.optimize_route_priorities(tenant_id),
                'score_weights': self.optimize_score_weights(tenant_id),
                'personalization': self.optimize_personalization_config(tenant_id),
                'overall_improvement': 0.0,
                'total_changes': 0,
                'recommendations': []
            }
            
            # Calculate total changes and improvement
            total_changes = (
                optimization_results['route_priorities']['optimized_routes'] +
                optimization_results['score_weights']['optimized_configs'] +
                optimization_results['personalization']['optimized_configs']
            )
            
            total_improvement = (
                optimization_results['route_priorities']['performance_improvement'] +
                optimization_results['score_weights']['performance_improvement'] +
                optimization_results['personalization']['performance_improvement']
            )
            
            optimization_results['total_changes'] = total_changes
            optimization_results['overall_improvement'] = total_improvement / 3  # Average
            
            # Combine recommendations
            all_recommendations = []
            all_recommendations.extend(optimization_results['route_priorities']['recommendations'])
            all_recommendations.extend(optimization_results['score_weights']['recommendations'])
            all_recommendations.extend(optimization_results['personalization']['recommendations'])
            
            optimization_results['recommendations'] = all_recommendations
            
            logger.info(f"Optimized {total_changes} configurations for tenant {tenant_id}")
            return optimization_results
            
        except Exception as e:
            logger.error(f"Error optimizing all configurations: {e}")
            return {
                'route_priorities': {'optimized_routes': 0, 'error': str(e)},
                'score_weights': {'optimized_configs': 0, 'error': str(e)},
                'personalization': {'optimized_configs': 0, 'error': str(e)},
                'overall_improvement': 0.0,
                'total_changes': 0,
                'recommendations': [f"Optimization failed: {str(e)}"]
            }


# Singleton instance
routing_optimizer = RoutingOptimizer()
