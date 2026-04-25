"""
Fallback Tasks for Offer Routing System

This module contains background tasks for fallback management,
including health checks, pool updates, and analytics.
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from ..services.fallback import fallback_service
from ..constants import FALLBACK_HEALTH_CHECK_INTERVAL_HOURS

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='offer_routing.tasks.fallback.check_fallback_health')
def check_fallback_health(self):
    """
    Check health of fallback configurations.
    
    This task validates fallback configurations and checks
    for potential issues or improvements.
    """
    try:
        logger.info("Starting fallback health check")
        
        if not fallback_service:
            logger.warning("Fallback service not available")
            return {'success': False, 'error': 'Fallback service not available'}
        
        # Check fallback health
        checked_count = fallback_service.check_fallback_health()
        
        logger.info(f"Fallback health check completed: {checked_count} configurations checked")
        return {
            'success': True,
            'checked_configurations': checked_count,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Fallback health check failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.fallback.update_offer_pools')
def update_offer_pools(self):
    """
    Update default offer pools.
    
    This task updates offer pools with fresh data
    and ensures they contain valid offers.
    """
    try:
        logger.info("Starting offer pool update")
        
        # Get all default offer pools
        from ..models import DefaultOfferPool
        
        pools = DefaultOfferPool.objects.filter(is_active=True)
        
        updated_pools = 0
        failed_pools = 0
        
        for pool in pools:
            try:
                # Check if pool has offers
                if not pool.offers.exists():
                    logger.warning(f"Pool {pool.id} has no offers")
                    failed_pools += 1
                    continue
                
                # Check if offers are still active
                inactive_offers = pool.offers.filter(is_active=False).count()
                if inactive_offers > 0:
                    logger.warning(f"Pool {pool.id} has {inactive_offers} inactive offers")
                    # Remove inactive offers
                    pool.offers.remove(*pool.offers.filter(is_active=False))
                
                updated_pools += 1
                
            except Exception as e:
                logger.error(f"Failed to update pool {pool.id}: {e}")
                failed_pools += 1
        
        logger.info(f"Offer pool update completed: {updated_pools} updated, {failed_pools} failed")
        return {
            'success': True,
            'updated_pools': updated_pools,
            'failed_pools': failed_pools,
            'total_pools': pools.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Offer pool update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.fallback.update_fallback_rules')
def update_fallback_rules(self):
    """
    Update fallback rules based on performance.
    
    This task analyzes fallback rule performance and
    suggests optimizations.
    """
    try:
        logger.info("Starting fallback rule update")
        
        # Get all fallback rules
        from ..models import FallbackRule
        
        rules = FallbackRule.objects.filter(is_active=True)
        
        updated_rules = 0
        failed_rules = 0
        
        for rule in rules:
            try:
                # Check if rule is still valid
                if not rule.is_valid_now():
                    logger.info(f"Deactivating invalid rule {rule.id}")
                    rule.is_active = False
                    rule.save()
                    failed_rules += 1
                    continue
                
                # Check rule performance
                performance_data = self._get_rule_performance(rule)
                
                if performance_data:
                    # Suggest optimizations based on performance
                    if performance_data['usage_rate'] < 0.1:
                        logger.info(f"Rule {rule.id} has low usage rate: {performance_data['usage_rate']:.2%}")
                        # Could suggest rule priority adjustment or removal
                    
                    if performance_data['success_rate'] < 0.5:
                        logger.info(f"Rule {rule.id} has low success rate: {performance_data['success_rate']:.2%}")
                        # Could suggest rule configuration changes
                
                updated_rules += 1
                
            except Exception as e:
                logger.error(f"Failed to update rule {rule.id}: {e}")
                failed_rules += 1
        
        logger.info(f"Fallback rule update completed: {updated_rules} updated, {failed_rules} failed")
        return {
            'success': True,
            'updated_rules': updated_rules,
            'failed_rules': failed_rules,
            'total_rules': rules.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Fallback rule update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }
    
    def _get_rule_performance(self, rule):
        """
        Get performance data for a fallback rule.
        
        Args:
            rule: FallbackRule instance
            
        Returns:
            Dictionary with performance metrics
        """
        try:
            from datetime import timedelta
            from ..models import RoutingDecisionLog
            
            cutoff_date = timezone.now() - timedelta(days=7)
            
            # Get decisions that used this rule
            decisions = RoutingDecisionLog.objects.filter(
                created_at__gte=cutoff_date,
                fallback_used=True
            )
            
            # This would filter by specific rule
            # For now, return placeholder data
            performance_data = {
                'usage_rate': 0.15,  # Placeholder
                'success_rate': 0.75,  # Placeholder
                'avg_response_time': 45.2,  # Placeholder
            }
            
            return performance_data
            
        except Exception as e:
            logger.error(f"Failed to get rule performance: {e}")
            return None


@shared_task(bind=True, name='offer_routing.tasks.fallback.update_empty_handlers')
def update_empty_handlers(self):
    """
    Update empty result handlers.
    
    This task validates empty result handlers and
    ensures they are properly configured.
    """
    try:
        logger.info("Starting empty handler update")
        
        # Get all empty result handlers
        from ..models import EmptyResultHandler
        
        handlers = EmptyResultHandler.objects.filter(is_active=True)
        
        updated_handlers = 0
        failed_handlers = 0
        
        for handler in handlers:
            try:
                # Validate handler configuration
                if not handler.action_type:
                    logger.warning(f"Handler {handler.id} has no action type")
                    failed_handlers += 1
                    continue
                
                # Check if handler has required configuration
                if handler.action_type in ['show_promo', 'redirect_url', 'custom_message'] and not handler.action_value:
                    if handler.action_type == 'redirect_url' and not handler.redirect_url:
                        logger.warning(f"Handler {handler.id} missing required URL")
                        failed_handlers += 1
                        continue
                    elif handler.action_type == 'custom_message' and not handler.custom_message:
                        logger.warning(f"Handler {handler.id} missing custom message")
                        failed_handlers += 1
                        continue
                
                updated_handlers += 1
                
            except Exception as e:
                logger.error(f"Failed to update handler {handler.id}: {e}")
                failed_handlers += 1
        
        logger.info(f"Empty handler update completed: {updated_handlers} updated, {failed_handlers} failed")
        return {
            'success': True,
            'updated_handlers': updated_handlers,
            'failed_handlers': failed_handlers,
            'total_handlers': handlers.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Empty handler update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.fallback.generate_fallback_analytics')
def generate_fallback_analytics(self):
    """
    Generate fallback analytics and insights.
    
    This task analyzes fallback usage patterns and
    generates insights for optimization.
    """
    try:
        logger.info("Starting fallback analytics generation")
        
        # Get recent fallback usage
        from ..models import RoutingDecisionLog
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=30)
        fallback_decisions = RoutingDecisionLog.objects.filter(
            created_at__gte=cutoff_date,
            fallback_used=True
        )
        
        # Calculate fallback metrics
        total_decisions = RoutingDecisionLog.objects.filter(
            created_at__gte=cutoff_date
        ).count()
        
        fallback_rate = (fallback_decisions.count() / total_decisions * 100) if total_decisions > 0 else 0
        
        # Get fallback rule usage
        rule_usage = fallback_decisions.values('route__name').annotate(
            usage_count=Count('id')
        ).order_by('-usage_count')
        
        # Generate insights
        insights = []
        
        if fallback_rate > 20:
            insights.append({
                'type': 'high_fallback_rate',
                'message': f'High fallback rate: {fallback_rate:.1f}%',
                'suggestion': 'Review targeting rules and offer availability'
            })
        
        if rule_usage.exists():
            top_rule = rule_usage.first()
            if top_rule['usage_count'] > fallback_decisions.count() * 0.5:
                insights.append({
                    'type': 'rule_dominance',
                    'message': f'Rule {top_rule["route__name"]} dominates fallback usage',
                    'suggestion': 'Consider diversifying fallback strategies'
                })
        
        # Store analytics (placeholder)
        # This would save the analytics to database or cache
        
        logger.info(f"Fallback analytics generation completed: {len(insights)} insights generated")
        return {
            'success': True,
            'fallback_rate': fallback_rate,
            'total_fallback_decisions': fallback_decisions.count(),
            'rule_usage': list(rule_usage),
            'insights': insights,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Fallback analytics generation failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.fallback.optimize_fallback_configuration')
def optimize_fallback_configuration(self):
    """
    Optimize fallback configuration based on usage patterns.
    
    This task analyzes fallback usage and suggests
    optimizations for better performance.
    """
    try:
        logger.info("Starting fallback configuration optimization")
        
        # Get fallback analytics
        from ..models import FallbackRule, DefaultOfferPool, EmptyResultHandler
        
        rules = FallbackRule.objects.filter(is_active=True)
        pools = DefaultOfferPool.objects.filter(is_active=True)
        handlers = EmptyResultHandler.objects.filter(is_active=True)
        
        optimizations = []
        
        # Analyze fallback rules
        for rule in rules:
            try:
                # Check rule priority
                if rule.priority > 8:
                    optimizations.append({
                        'type': 'rule_priority',
                        'rule_id': rule.id,
                        'message': f'Rule {rule.name} has low priority ({rule.priority})',
                        'suggestion': 'Consider increasing priority for better fallback coverage'
                    })
                
                # Check rule conditions
                if not rule.conditions.exists():
                    optimizations.append({
                        'type': 'rule_conditions',
                        'rule_id': rule.id,
                        'message': f'Rule {rule.name} has no conditions',
                        'suggestion': 'Add conditions to target specific scenarios'
                    })
                
            except Exception as e:
                logger.error(f"Failed to analyze rule {rule.id}: {e}")
        
        # Analyze offer pools
        for pool in pools:
            try:
                # Check pool size
                if pool.offers.count() < 5:
                    optimizations.append({
                        'type': 'pool_size',
                        'pool_id': pool.id,
                        'message': f'Pool {pool.name} has few offers ({pool.offers.count()})',
                        'suggestion': 'Add more offers to the pool for better fallback variety'
                    })
                
                # Check pool rotation strategy
                if pool.rotation_strategy == 'random' and pool.offers.count() < 10:
                    optimizations.append({
                        'type': 'pool_rotation',
                        'pool_id': pool.id,
                        'message': f'Pool {pool.name} uses random rotation with few offers',
                        'suggestion': 'Consider using priority rotation for better results'
                    })
                
            except Exception as e:
                logger.error(f"Failed to analyze pool {pool.id}: {e}")
        
        # Analyze empty handlers
        for handler in handlers:
            try:
                # Check handler action type
                if handler.action_type == 'hide_section':
                    optimizations.append({
                        'type': 'handler_action',
                        'handler_id': handler.id,
                        'message': f'Handler {handler.name} hides section completely',
                        'suggestion': 'Consider showing fallback offers instead of hiding section'
                    })
                
            except Exception as e:
                logger.error(f"Failed to analyze handler {handler.id}: {e}")
        
        logger.info(f"Fallback configuration optimization completed: {len(optimizations)} optimizations suggested")
        return {
            'success': True,
            'optimizations': optimizations,
            'rules_analyzed': rules.count(),
            'pools_analyzed': pools.count(),
            'handlers_analyzed': handlers.count(),
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Fallback configuration optimization failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.fallback.cleanup_inactive_fallbacks')
def cleanup_inactive_fallbacks(self):
    """
    Clean up inactive fallback configurations.
    
    This task removes inactive fallback configurations
    to maintain system performance.
    """
    try:
        logger.info("Starting inactive fallback cleanup")
        
        # Clean up inactive fallback rules
        from ..models import FallbackRule
        
        inactive_rules = FallbackRule.objects.filter(is_active=False)
        deleted_rules = inactive_rules.count()
        
        # Clean up inactive offer pools
        from ..models import DefaultOfferPool
        
        inactive_pools = DefaultOfferPool.objects.filter(is_active=False)
        deleted_pools = inactive_pools.count()
        
        # Clean up inactive empty handlers
        from ..models import EmptyResultHandler
        
        inactive_handlers = EmptyResultHandler.objects.filter(is_active=False)
        deleted_handlers = inactive_handlers.count()
        
        # Delete inactive configurations
        inactive_rules.delete()
        inactive_pools.delete()
        inactive_handlers.delete()
        
        total_deleted = deleted_rules + deleted_pools + deleted_handlers
        
        logger.info(f"Inactive fallback cleanup completed: {total_deleted} configurations deleted")
        return {
            'success': True,
            'deleted_rules': deleted_rules,
            'deleted_pools': deleted_pools,
            'deleted_handlers': deleted_handlers,
            'total_deleted': total_deleted,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Inactive fallback cleanup failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }


@shared_task(bind=True, name='offer_routing.tasks.fallback.update_fallback_metrics')
def update_fallback_metrics(self):
    """
    Update fallback metrics for monitoring.
    
    This task updates metrics tables for fallback
    monitoring and analytics.
    """
    try:
        logger.info("Starting fallback metrics update")
        
        # Get current fallback metrics
        from ..models import FallbackRule, DefaultOfferPool, EmptyResultHandler, RoutingDecisionLog
        from datetime import timedelta
        
        # Calculate fallback usage metrics
        cutoff_date = timezone.now() - timedelta(hours=1)
        recent_decisions = RoutingDecisionLog.objects.filter(
            created_at__gte=cutoff_date
        )
        
        fallback_metrics = {
            'total_rules': FallbackRule.objects.count(),
            'active_rules': FallbackRule.objects.filter(is_active=True).count(),
            'total_pools': DefaultOfferPool.objects.count(),
            'active_pools': DefaultOfferPool.objects.filter(is_active=True).count(),
            'total_handlers': EmptyResultHandler.objects.count(),
            'active_handlers': EmptyResultHandler.objects.filter(is_active=True).count(),
            'recent_fallback_usage': recent_decisions.filter(fallback_used=True).count(),
            'recent_total_decisions': recent_decisions.count()
        }
        
        # Calculate fallback rate
        if fallback_metrics['recent_total_decisions'] > 0:
            fallback_metrics['fallback_rate'] = (
                fallback_metrics['recent_fallback_usage'] / 
                fallback_metrics['recent_total_decisions'] * 100
            )
        else:
            fallback_metrics['fallback_rate'] = 0
        
        # Store metrics (placeholder)
        # This would save the metrics to database or cache
        
        logger.info(f"Fallback metrics update completed: fallback_rate={fallback_metrics['fallback_rate']:.1f}%")
        return {
            'success': True,
            'fallback_metrics': fallback_metrics,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Fallback metrics update failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'completed_at': timezone.now().isoformat()
        }
