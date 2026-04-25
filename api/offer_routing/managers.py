"""
Custom Managers for Offer Routing System

This module contains custom Django model managers for the offer routing system,
providing optimized queries and business logic methods.
"""

import logging
from typing import Dict, Any, List, Optional, QuerySet
from django.db import models
from django.db.models import Q, Count, Sum, Avg, F, Window
from django.db.models.functions import RowNumber
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from datetime import timedelta, datetime

logger = logging.getLogger(__name__)


class OfferRouteManager(models.Manager):
    """
    Custom manager for OfferRoute model.
    """
    
    def get_active_routes(self) -> QuerySet:
        """Get all active routes."""
        return self.filter(is_active=True, status='active')
    
    def get_routes_by_priority(self) -> QuerySet:
        """Get routes ordered by priority."""
        return self.get_active_routes().order_by('-priority', 'created_at')
    
    def get_routes_for_offer(self, offer_id: int) -> QuerySet:
        """Get routes that include a specific offer."""
        return self.get_active_routes().filter(
            Q(offers__id=offer_id) | Q(default_offers__id=offer_id)
        ).distinct()
    
    def get_routes_by_country(self, country_code: str) -> QuerySet:
        """Get routes available for a specific country."""
        return self.get_active_routes().filter(
            Q(geo_targeting__countries__contains=[country_code]) |
            Q(geo_targeting__countries__isnull=True) |
            Q(geo_targeting__countries=[])
        ).distinct()
    
    def get_routes_by_device(self, device_type: str) -> QuerySet:
        """Get routes available for a specific device type."""
        return self.get_active_routes().filter(
            Q(device_targeting__device_types__contains=[device_type]) |
            Q(device_targeting__device_types__isnull=True) |
            Q(device_targeting__device_types=[])
        ).distinct()
    
    def get_routes_with_performance_stats(self, days: int = 7) -> QuerySet:
        """Get routes with performance statistics for the last N days."""
        from django.db.models import Subquery, OuterRef
        
        start_date = timezone.now() - timedelta(days=days)
        
        # Subquery for performance stats
        performance_stats = self.filter(
            id=OuterRef('pk'),
            routingdecisionlog__created_at__gte=start_date
        ).values('id').annotate(
            total_decisions=Count('routingdecisionlog'),
            successful_decisions=Count('routingdecisionlog', filter=Q(routingdecisionlog__success=True)),
            avg_response_time=Avg('routingdecisionlog__response_time')
        ).values('total_decisions', 'successful_decisions', 'avg_response_time')
        
        return self.get_active_routes().annotate(
            total_decisions=Subquery(performance_stats.values('total_decisions')[:1]),
            successful_decisions=Subquery(performance_stats.values('successful_decisions')[:1]),
            avg_response_time=Subquery(performance_stats.values('avg_response_time')[:1])
        )
    
    def get_routes_by_tenant(self, tenant_id: int) -> QuerySet:
        """Get routes for a specific tenant."""
        return self.get_active_routes().filter(tenant_id=tenant_id)
    
    def search_routes(self, query: str) -> QuerySet:
        """Search routes by name or description."""
        return self.get_active_routes().filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )
    
    def get_route_statistics(self) -> Dict[str, Any]:
        """Get overall route statistics."""
        stats = self.aggregate(
            total_routes=Count('id'),
            active_routes=Count('id', filter=Q(is_active=True, status='active')),
            total_offers=Count('offers', distinct=True),
            avg_priority=Avg('priority')
        )
        
        # Get performance stats
        performance_stats = self.get_routes_with_performance_stats().aggregate(
            avg_response_time=Avg('avg_response_time'),
            total_decisions=Sum('total_decisions'),
            success_rate=Avg('successful_decisions') * 100.0 / Avg('total_decisions')
        )
        
        return {
            **stats,
            **performance_stats
        }


class RouteConditionManager(models.Manager):
    """
    Custom manager for RouteCondition model.
    """
    
    def get_conditions_for_route(self, route_id: int) -> QuerySet:
        """Get all conditions for a specific route."""
        return self.filter(route_id=route_id).order_by('priority', 'id')
    
    def get_active_conditions(self) -> QuerySet:
        """Get all active conditions."""
        return self.filter(is_active=True)
    
    def get_conditions_by_type(self, condition_type: str) -> QuerySet:
        """Get conditions by type."""
        return self.get_active_conditions().filter(condition_type=condition_type)
    
    def evaluate_conditions_for_context(self, route_id: int, context: Dict[str, Any]) -> Dict[str, bool]:
        """Evaluate all conditions for a route against given context."""
        conditions = self.get_conditions_for_route(route_id)
        results = {}
        
        for condition in conditions:
            try:
                results[condition.id] = condition.evaluate(context)
            except Exception as e:
                logger.error(f"Error evaluating condition {condition.id}: {str(e)}")
                results[condition.id] = False
        
        return results


class RouteActionManager(models.Manager):
    """
    Custom manager for RouteAction model.
    """
    
    def get_actions_for_route(self, route_id: int) -> QuerySet:
        """Get all actions for a specific route."""
        return self.filter(route_id=route_id).order_by('priority', 'id')
    
    def get_active_actions(self) -> QuerySet:
        """Get all active actions."""
        return self.filter(is_active=True)
    
    def get_actions_by_type(self, action_type: str) -> QuerySet:
        """Get actions by type."""
        return self.get_active_actions().filter(action_type=action_type)
    
    def execute_actions_for_context(self, route_id: int, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute all actions for a route against given context."""
        actions = self.get_actions_for_route(route_id)
        results = []
        
        for action in actions:
            try:
                result = action.execute(context)
                results.append({
                    'action_id': action.id,
                    'action_type': action.action_type,
                    'success': True,
                    'result': result
                })
            except Exception as e:
                logger.error(f"Error executing action {action.id}: {str(e)}")
                results.append({
                    'action_id': action.id,
                    'action_type': action.action_type,
                    'success': False,
                    'error': str(e)
                })
        
        return results


class OfferScoreManager(models.Manager):
    """
    Custom manager for OfferScore model.
    """
    
    def get_scores_for_user(self, user_id: int) -> QuerySet:
        """Get all scores for a specific user."""
        return self.filter(user_id=user_id)
    
    def get_scores_for_offer(self, offer_id: int) -> QuerySet:
        """Get all scores for a specific offer."""
        return self.filter(offer_id=offer_id)
    
    def get_top_scoring_offers(self, user_id: int, limit: int = 10) -> QuerySet:
        """Get top scoring offers for a user."""
        return self.get_scores_for_user(user_id).order_by('-score', '-created_at')[:limit]
    
    def update_score(self, user_id: int, offer_id: int, score: float, components: Dict[str, float] = None) -> 'OfferScore':
        """Update or create a score for a user-offer pair."""
        score_obj, created = self.update_or_create(
            user_id=user_id,
            offer_id=offer_id,
            defaults={
                'score': score,
                'score_components': components or {}
            }
        )
        
        if not created:
            score_obj.score = score
            score_obj.score_components = components or {}
            score_obj.save()
        
        return score_obj
    
    def get_score_distribution(self, offer_id: int) -> Dict[str, int]:
        """Get distribution of scores for an offer."""
        scores = self.get_scores_for_offer(offer_id)
        
        distribution = {
            'low': scores.filter(score__lt=0.3).count(),
            'medium': scores.filter(score__gte=0.3, score__lt=0.7).count(),
            'high': scores.filter(score__gte=0.7).count()
        }
        
        return distribution
    
    def get_average_score_for_offer(self, offer_id: int) -> float:
        """Get average score for an offer."""
        result = self.get_scores_for_offer(offer_id).aggregate(avg_score=Avg('score'))
        return result['avg_score'] or 0.0


class UserOfferHistoryManager(models.Manager):
    """
    Custom manager for UserOfferHistory model.
    """
    
    def get_history_for_user(self, user_id: int, days: int = 30) -> QuerySet:
        """Get offer history for a user for the last N days."""
        start_date = timezone.now() - timedelta(days=days)
        return self.filter(user_id=user_id, created_at__gte=start_date)
    
    def get_history_for_offer(self, offer_id: int, days: int = 30) -> QuerySet:
        """Get offer history for an offer for the last N days."""
        start_date = timezone.now() - timedelta(days=days)
        return self.filter(offer_id=offer_id, created_at__gte=start_date)
    
    def get_user_interaction_stats(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get interaction statistics for a user."""
        history = self.get_history_for_user(user_id, days)
        
        stats = history.aggregate(
            total_interactions=Count('id'),
            unique_offers=Count('offer', distinct=True),
            avg_score=Avg('score'),
            click_rate=Avg('clicked') * 100.0,
            conversion_rate=Avg('converted') * 100.0
        )
        
        return stats
    
    def get_offer_performance_stats(self, offer_id: int, days: int = 30) -> Dict[str, Any]:
        """Get performance statistics for an offer."""
        history = self.get_history_for_offer(offer_id, days)
        
        stats = history.aggregate(
            total_interactions=Count('id'),
            unique_users=Count('user', distinct=True),
            avg_score=Avg('score'),
            click_rate=Avg('clicked') * 100.0,
            conversion_rate=Avg('converted') * 100.0
        )
        
        return stats
    
    def record_interaction(self, user_id: int, offer_id: int, score: float, clicked: bool = False, converted: bool = False, context: Dict[str, Any] = None) -> 'UserOfferHistory':
        """Record a user-offer interaction."""
        return self.create(
            user_id=user_id,
            offer_id=offer_id,
            score=score,
            clicked=clicked,
            converted=converted,
            context=context or {}
        )


class RoutingDecisionLogManager(models.Manager):
    """
    Custom manager for RoutingDecisionLog model.
    """
    
    def get_logs_for_user(self, user_id: int, days: int = 7) -> QuerySet:
        """Get routing logs for a user for the last N days."""
        start_date = timezone.now() - timedelta(days=days)
        return self.filter(user_id=user_id, created_at__gte=start_date)
    
    def get_logs_for_route(self, route_id: int, days: int = 7) -> QuerySet:
        """Get routing logs for a route for the last N days."""
        start_date = timezone.now() - timedelta(days=days)
        return self.filter(route_id=route_id, created_at__gte=start_date)
    
    def get_performance_metrics(self, route_id: int = None, days: int = 7) -> Dict[str, Any]:
        """Get performance metrics for routing decisions."""
        queryset = self.filter(created_at__gte=timezone.now() - timedelta(days=days))
        
        if route_id:
            queryset = queryset.filter(route_id=route_id)
        
        metrics = queryset.aggregate(
            total_decisions=Count('id'),
            successful_decisions=Count('id', filter=Q(success=True)),
            avg_response_time=Avg('response_time'),
            avg_score=Avg('score')
        )
        
        total_decisions = metrics['total_decisions'] or 0
        success_rate = (metrics['successful_decisions'] or 0) / total_decisions * 100 if total_decisions > 0 else 0
        
        return {
            **metrics,
            'success_rate': success_rate
        }
    
    def log_decision(self, user_id: int, route_id: int, context: Dict[str, Any], success: bool, response_time: float, score: float = None, error_message: str = None) -> 'RoutingDecisionLog':
        """Log a routing decision."""
        return self.create(
            user_id=user_id,
            route_id=route_id,
            context=context,
            success=success,
            response_time=response_time,
            score=score,
            error_message=error_message
        )
    
    def cleanup_old_logs(self, days_to_keep: int = 30) -> int:
        """Clean up old routing logs."""
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        deleted_count = self.filter(created_at__lt=cutoff_date).delete()[0]
        logger.info(f"Cleaned up {deleted_count} old routing logs")
        return deleted_count


class RoutingInsightManager(models.Manager):
    """
    Custom manager for RoutingInsight model.
    """
    
    def get_insights_for_route(self, route_id: int) -> QuerySet:
        """Get insights for a specific route."""
        return self.filter(route_id=route_id).order_by('-created_at')
    
    def get_insights_by_type(self, insight_type: str) -> QuerySet:
        """Get insights by type."""
        return self.filter(insight_type=insight_type).order_by('-created_at')
    
    def get_recent_insights(self, hours: int = 24) -> QuerySet:
        """Get recent insights."""
        start_time = timezone.now() - timedelta(hours=hours)
        return self.filter(created_at__gte=start_time).order_by('-created_at')
    
    def create_insight(self, route_id: int, insight_type: str, title: str, description: str, data: Dict[str, Any], priority: str = 'medium') -> 'RoutingInsight':
        """Create a new routing insight."""
        return self.create(
            route_id=route_id,
            insight_type=insight_type,
            title=title,
            description=description,
            data=data,
            priority=priority
        )
    
    def get_insight_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get summary of insights."""
        start_date = timezone.now() - timedelta(days=days)
        
        summary = self.filter(created_at__gte=start_date).values('insight_type').annotate(
            count=Count('id'),
            avg_priority=Avg('priority')
        ).order_by('-count')
        
        return list(summary)


class OfferRoutingCapManager(models.Manager):
    """
    Custom manager for OfferRoutingCap model.
    """
    
    def get_active_caps(self) -> QuerySet:
        """Get all active caps."""
        return self.filter(is_active=True)
    
    def get_caps_for_offer(self, offer_id: int) -> QuerySet:
        """Get caps for a specific offer."""
        return self.get_active_caps().filter(offer_id=offer_id)
    
    def get_daily_caps(self) -> QuerySet:
        """Get all daily caps."""
        return self.get_active_caps().filter(cap_type='daily')
    
    def get_hourly_caps(self) -> QuerySet:
        """Get all hourly caps."""
        return self.get_active_caps().filter(cap_type='hourly')
    
    def check_cap_limit(self, offer_id: int, cap_type: str) -> bool:
        """Check if cap limit is reached for an offer."""
        cap = self.get_caps_for_offer(offer_id).filter(cap_type=cap_type).first()
        
        if not cap:
            return True  # No cap means no limit
        
        return not cap.is_limit_reached()
    
    def update_cap_usage(self, offer_id: int, cap_type: str) -> bool:
        """Update cap usage for an offer."""
        cap = self.get_caps_for_offer(offer_id).filter(cap_type=cap_type).first()
        
        if not cap:
            return False
        
        cap.increment_usage()
        return True
    
    def reset_daily_caps(self) -> int:
        """Reset all daily caps."""
        updated_count = self.filter(cap_type='daily').update(current_count=0, last_reset_date=timezone.now())
        logger.info(f"Reset {updated_count} daily caps")
        return updated_count
    
    def reset_hourly_caps(self) -> int:
        """Reset all hourly caps."""
        updated_count = self.filter(cap_type='hourly').update(current_count=0, last_reset_date=timezone.now())
        logger.info(f"Reset {updated_count} hourly caps")
        return updated_count


class UserOfferCapManager(models.Manager):
    """
    Custom manager for UserOfferCap model.
    """
    
    def get_caps_for_user(self, user_id: int) -> QuerySet:
        """Get caps for a specific user."""
        return self.filter(user_id=user_id, is_active=True)
    
    def get_caps_for_user_offer(self, user_id: int, offer_id: int) -> QuerySet:
        """Get caps for a specific user-offer pair."""
        return self.filter(user_id=user_id, offer_id=offer_id, is_active=True)
    
    def check_user_cap_limit(self, user_id: int, offer_id: int, cap_type: str) -> bool:
        """Check if user cap limit is reached."""
        cap = self.get_caps_for_user_offer(user_id, offer_id).filter(cap_type=cap_type).first()
        
        if not cap:
            return True  # No cap means no limit
        
        return not cap.is_limit_reached()
    
    def update_user_cap_usage(self, user_id: int, offer_id: int, cap_type: str) -> bool:
        """Update user cap usage."""
        cap = self.get_caps_for_user_offer(user_id, offer_id).filter(cap_type=cap_type).first()
        
        if not cap:
            return False
        
        cap.increment_usage()
        return True


class RoutingABTestManager(models.Manager):
    """
    Custom manager for RoutingABTest model.
    """
    
    def get_active_tests(self) -> QuerySet:
        """Get all active A/B tests."""
        return self.filter(is_active=True, status='running')
    
    def get_tests_for_route(self, route_id: int) -> QuerySet:
        """Get A/B tests for a specific route."""
        return self.get_active_tests().filter(route_id=route_id)
    
    def get_completed_tests(self) -> QuerySet:
        """Get completed A/B tests."""
        return self.filter(status='completed').order_by('-completed_at')
    
    def assign_user_to_test(self, user_id: int, test_id: int) -> Optional[str]:
        """Assign a user to an A/B test variant."""
        from .models import ABTestAssignment
        
        # Check if already assigned
        assignment = ABTestAssignment.objects.filter(user_id=user_id, test_id=test_id).first()
        if assignment:
            return assignment.variant
        
        # Get test
        test = self.get(id=test_id)
        if test.status != 'running':
            return None
        
        # Assign to variant
        variant = test.get_variant_for_user(user_id)
        
        ABTestAssignment.objects.create(
            user_id=user_id,
            test_id=test_id,
            variant=variant,
            assigned_at=timezone.now()
        )
        
        return variant
    
    def get_test_results(self, test_id: int) -> Dict[str, Any]:
        """Get results for an A/B test."""
        from .models import ABTestAssignment, ABTestResult
        
        test = self.get(id=test_id)
        
        # Get assignments
        assignments = ABTestAssignment.objects.filter(test_id=test_id)
        
        # Get results
        results = ABTestResult.objects.filter(test_id=test_id)
        
        return {
            'test': test,
            'assignments': assignments,
            'results': results,
            'total_assignments': assignments.count(),
            'total_results': results.count()
        }


class NetworkPerformanceCacheManager(models.Manager):
    """
    Custom manager for NetworkPerformanceCache model.
    """
    
    def get_cache_entry(self, cache_key: str, cache_type: str = None) -> Optional['NetworkPerformanceCache']:
        """Get a cache entry."""
        queryset = self.filter(cache_key=cache_key)
        
        if cache_type:
            queryset = queryset.filter(cache_type=cache_type)
        
        return queryset.first()
    
    def set_cache_entry(self, cache_key: str, cache_data: Dict[str, Any], cache_type: str = None, expires_at: datetime = None) -> 'NetworkPerformanceCache':
        """Set a cache entry."""
        if not expires_at:
            expires_at = timezone.now() + timedelta(hours=1)
        
        return self.update_or_create(
            cache_key=cache_key,
            defaults={
                'cache_data': cache_data,
                'cache_type': cache_type or 'general',
                'expires_at': expires_at,
                'hit_count': 0
            }
        )[0]
    
    def increment_hit_count(self, cache_key: str) -> bool:
        """Increment hit count for a cache entry."""
        updated = self.filter(cache_key=cache_key).update(hit_count=F('hit_count') + 1)
        return updated > 0
    
    def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries."""
        deleted_count = self.filter(expires_at__lt=timezone.now()).delete()[0]
        logger.info(f"Cleaned up {deleted_count} expired cache entries")
        return deleted_count
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = self.aggregate(
            total_entries=Count('id'),
            expired_entries=Count('id', filter=Q(expires_at__lt=timezone.now())),
            total_hits=Sum('hit_count'),
            avg_hits=Avg('hit_count')
        )
        
        return stats


# Export all managers
__all__ = [
    'OfferRouteManager',
    'RouteConditionManager',
    'RouteActionManager',
    'OfferScoreManager',
    'UserOfferHistoryManager',
    'RoutingDecisionLogManager',
    'RoutingInsightManager',
    'OfferRoutingCapManager',
    'UserOfferCapManager',
    'RoutingABTestManager',
    'NetworkPerformanceCacheManager',
]
