"""
Fallback Health Tasks

Periodic tasks for checking fallback pool health
in the offer routing system.
"""

import logging
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.contrib.auth import get_user_model
from ..services.fallback import FallbackService
from ..services.analytics import analytics_service
from ..services.cache import cache_service
from ..models import FallbackRule, DefaultOfferPool, EmptyResultHandler
from ..constants import FALLBACK_HEALTH_CHECK_INTERVAL, FALLBACK_CACHE_TIMEOUT
from ..exceptions import FallbackError

logger = logging.getLogger(__name__)

User = get_user_model()


class FallbackHealthTask:
    """
    Task for checking fallback pool health.
    
    Runs periodically to:
    - Check fallback pool availability
    - Monitor fallback rule effectiveness
    - Validate default offer pools
    - Test empty result handlers
    - Alert on fallback issues
    """
    
    def __init__(self):
        self.fallback_service = FallbackService()
        self.analytics_service = analytics_service
        self.cache_service = cache_service
        self.task_stats = {
            'total_health_checks': 0,
            'successful_checks': 0,
            'failed_checks': 0,
            'issues_found': 0,
            'avg_check_time_ms': 0.0
        }
    
    def run_fallback_health_check(self) -> Dict[str, Any]:
        """
        Run the fallback health check task.
        
        Returns:
            Task execution results
        """
        try:
            start_time = timezone.now()
            
            # Check all fallback components
            fallback_rules_health = self._check_fallback_rules()
            default_pools_health = self._check_default_offer_pools()
            empty_handlers_health = self._check_empty_result_handlers()
            fallback_service_health = self._check_fallback_service()
            
            # Calculate overall health
            all_components_healthy = all([
                fallback_rules_health['healthy'],
                default_pools_health['healthy'],
                empty_handlers_health['healthy'],
                fallback_service_health['healthy']
            ])
            
            overall_health = 'healthy' if all_components_healthy else 'unhealthy'
            
            # Update task statistics
            self._update_task_stats(start_time)
            
            # Clear relevant cache
            self._clear_fallback_cache()
            
            return {
                'success': True,
                'message': 'Fallback health check completed',
                'overall_health': overall_health,
                'fallback_rules_health': fallback_rules_health,
                'default_pools_health': default_pools_health,
                'empty_handlers_health': empty_handlers_health,
                'fallback_service_health': fallback_service_health,
                'issues_found': self.task_stats['issues_found'],
                'execution_time_ms': (timezone.now() - start_time).total_seconds() * 1000,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in fallback health check task: {e}")
            return {
                'success': False,
                'error': str(e),
                'execution_time_ms': 0,
                'timestamp': timezone.now().isoformat()
            }
    
    def _check_fallback_rules(self) -> Dict[str, Any]:
        """Check health of fallback rules."""
        try:
            # Get all fallback rules
            rules = FallbackRule.objects.filter(is_active=True)
            
            if not rules.exists():
                return {
                    'healthy': True,
                    'message': 'No fallback rules configured',
                    'rules_count': 0,
                    'issues': []
                }
            
            issues = []
            healthy_rules = 0
            
            for rule in rules:
                rule_issues = []
                
                # Check rule configuration
                if not rule.name:
                    rule_issues.append('Missing rule name')
                
                if not rule.fallback_type:
                    rule_issues.append('Missing fallback type')
                
                # Check if fallback target is valid
                if rule.fallback_type == 'offer_pool' and not rule.offer_pool:
                    rule_issues.append('Invalid offer pool reference')
                
                # Check if rule has proper priority
                if rule.priority <= 0:
                    rule_issues.append('Invalid priority value')
                
                # Check if rule is active
                if not rule.is_active:
                    rule_issues.append('Rule is marked as inactive')
                
                if not rule_issues:
                    healthy_rules += 1
                else:
                    issues.append({
                        'rule_id': rule.id,
                        'rule_name': rule.name,
                        'issues': rule_issues
                    })
            
            return {
                'healthy': len(issues) == 0,
                'message': 'Fallback rules check completed',
                'rules_count': rules.count(),
                'healthy_rules': healthy_rules,
                'unhealthy_rules': rules.count() - healthy_rules,
                'issues': issues,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking fallback rules: {e}")
            return {
                'healthy': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _check_default_offer_pools(self) -> Dict[str, Any]:
        """Check health of default offer pools."""
        try:
            # Get all default offer pools
            pools = DefaultOfferPool.objects.filter(is_active=True)
            
            if not pools.exists():
                return {
                    'healthy': True,
                    'message': 'No default offer pools configured',
                    'pools_count': 0,
                    'issues': []
                }
            
            issues = []
            healthy_pools = 0
            
            for pool in pools:
                pool_issues = []
                
                # Check if pool has offers
                if not pool.offers.exists():
                    pool_issues.append('Pool has no offers')
                
                # Check if pool offers are valid
                invalid_offers = pool.offers.filter(is_active=False).count()
                if invalid_offers > 0:
                    pool_issues.append(f'Has {invalid_offers} inactive offers')
                
                # Check if pool has minimum offers
                if pool.offers.count() < 5:
                    pool_issues.append('Pool has less than 5 offers')
                
                # Check if pool is properly configured
                if not pool.name:
                    pool_issues.append('Missing pool name')
                
                if not pool.is_active:
                    pool_issues.append('Pool is marked as inactive')
                
                if not pool_issues:
                    healthy_pools += 1
                else:
                    issues.append({
                        'pool_id': pool.id,
                        'pool_name': pool.name,
                        'issues': pool_issues
                    })
            
            return {
                'healthy': len(issues) == 0,
                'message': 'Default offer pools check completed',
                'pools_count': pools.count(),
                'healthy_pools': healthy_pools,
                'unhealthy_pools': pools.count() - healthy_pools,
                'issues': issues,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking default offer pools: {e}")
            return {
                'healthy': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _check_empty_result_handlers(self) -> Dict[str, Any]:
        """Check health of empty result handlers."""
        try:
            # Get all empty result handlers
            handlers = EmptyResultHandler.objects.filter(is_active=True)
            
            if not handlers.exists():
                return {
                    'healthy': True,
                    'message': 'No empty result handlers configured',
                    'handlers_count': 0,
                    'issues': []
                }
            
            issues = []
            healthy_handlers = 0
            
            for handler in handlers:
                handler_issues = []
                
                # Check if handler has proper configuration
                if not handler.handler_type:
                    handler_issues.append('Missing handler type')
                
                if not handler.action:
                    handler_issues.append('Missing handler action')
                
                # Check if handler is properly configured
                if not handler.is_active:
                    handler_issues.append('Handler is marked as inactive')
                
                if not handler_issues:
                    healthy_handlers += 1
                else:
                    issues.append({
                        'handler_id': handler.id,
                        'handler_type': handler.handler_type,
                        'issues': handler_issues
                    })
            
            return {
                'healthy': len(issues) == 0,
                'message': 'Empty result handlers check completed',
                'handlers_count': handlers.count(),
                'healthy_handlers': healthy_handlers,
                'unhealthy_handlers': handlers.count() - healthy_handlers,
                'issues': issues,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking empty result handlers: {e}")
            return {
                'healthy': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _check_fallback_service(self) -> Dict[str, Any]:
        """Check overall fallback service health."""
        try:
            # Test fallback service
            service_health = self.fallback_service.health_check()
            
            # Test cache functionality
            cache_health = self._test_cache_functionality()
            
            # Test analytics service
            analytics_health = self.analytics_service.health_check()
            
            overall_healthy = all([
                service_health.get('status') == 'healthy',
                cache_health,
                analytics_health
            ])
            
            return {
                'healthy': overall_healthy,
                'service_health': service_health,
                'cache_health': cache_health,
                'analytics_health': analytics_health,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking fallback service: {e}")
            return {
                'healthy': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _update_task_stats(self, start_time):
        """Update task execution statistics."""
        try:
            execution_time = (timezone.now() - start_time).total_seconds() * 1000
            
            self.task_stats['total_health_checks'] += 1
            self.task_stats['successful_checks'] += 1
            
            # Update average time
            current_avg = self.task_stats['avg_check_time_ms']
            total_checks = self.task_stats['total_health_checks']
            self.task_stats['avg_check_time_ms'] = (
                (current_avg * (total_checks - 1) + execution_time) / total_checks
            )
            
        except Exception as e:
            logger.error(f"Error updating task stats: {e}")
    
    def _clear_fallback_cache(self):
        """Clear fallback-related cache entries."""
        try:
            # Clear fallback cache entries
            cache_patterns = [
                "fallback_rules:*",
                "default_pools:*",
                "empty_handlers:*",
                "fallback_service_health"
            ]
            
            for pattern in cache_patterns:
                # This would need pattern deletion support
                # For now, clear specific keys
                cache.delete("fallback_health:latest")
                cache.delete("fallback_rules:latest")
                cache.delete("default_pools:latest")
                cache.delete("empty_handlers:latest")
            
            logger.info("Cleared fallback cache entries")
            
        except Exception as e:
            logger.error(f"Error clearing fallback cache: {e}")
    
    def get_task_stats(self) -> Dict[str, Any]:
        """Get task execution statistics."""
        return self.task_stats
    
    def reset_task_stats(self) -> bool:
        """Reset task statistics."""
        try:
            self.task_stats = {
                'total_health_checks': 0,
                'successful_checks': 0,
                'failed_checks': 0,
                'issues_found': 0,
                'avg_check_time_ms': 0.0
            }
            
            logger.info("Reset fallback health check task statistics")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting task stats: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on fallback health check task."""
        try:
            # Test fallback service
            fallback_health = self._check_fallback_service()
            
            # Test cache functionality
            cache_health = self._test_cache_functionality()
            
            # Test health check functionality
            test_rules_health = self._check_fallback_rules()
            test_pools_health = self._check_default_offer_pools()
            test_handlers_health = self._check_empty_result_handlers()
            
            overall_healthy = all([
                fallback_health['healthy'],
                cache_health,
                test_rules_health['healthy'],
                test_pools_health['healthy'],
                test_handlers_health['healthy']
            ])
            
            return {
                'status': 'healthy' if overall_healthy else 'unhealthy',
                'fallback_service_health': fallback_health,
                'cache_health': cache_health,
                'test_rules_health': test_rules_health,
                'test_pools_health': test_pools_health,
                'test_handlers_health': test_handlers_health,
                'task_stats': self.task_stats,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in fallback health check task health check: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _test_cache_functionality(self) -> bool:
        """Test cache functionality."""
        try:
            # Test cache set and get
            test_key = "test_fallback_health_check"
            test_value = {"test": True, "version": "1.0"}
            
            self.cache_service.set(test_key, test_value, 60)
            cached_value = self.cache_service.get(test_key)
            
            # Clean up
            self.cache_service.delete(test_key)
            
            return cached_value and cached_value.get('test') == test_value.get('test')
            
        except Exception as e:
            logger.error(f"Error testing cache functionality: {e}")
            return False


# Task instance
fallback_health_task = FallbackHealthTask()
