# api/rate_limit/integ_handler.py
"""
Integration handler for rate limit module.

Provides centralized integration management and coordination.
"""

import logging
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache

from api.rate_limit.integ_registry import IntegrationRegistry
from api.rate_limit.integ_adapter import IntegrationAdapter
from api.rate_limit.integ_constants import IntegrationStatus, IntegrationType
from api.rate_limit.integ_exceptions import IntegrationError, IntegrationTimeoutError

logger = logging.getLogger(__name__)


class IntegrationHandler:
    """
    Central handler for managing all rate limit integrations.
    """
    
    def __init__(self):
        self.registry = IntegrationRegistry()
        self.adapters: Dict[str, IntegrationAdapter] = {}
        self.active_integrations: Dict[str, Dict[str, Any]] = {}
        self.performance_stats = {}
        self.error_counts = {}
        self.last_health_check = None
    
    def register_adapter(self, name: str, adapter: IntegrationAdapter):
        """
        Register an integration adapter.
        
        Args:
            name: Adapter name
            adapter: Adapter instance
        """
        self.adapters[name] = adapter
        self.registry.register_adapter(name, adapter)
        logger.info(f"Registered integration adapter: {name}")
    
    def unregister_adapter(self, name: str):
        """
        Unregister an integration adapter.
        
        Args:
            name: Adapter name
        """
        if name in self.adapters:
            del self.adapters[name]
            self.registry.unregister_adapter(name)
            logger.info(f"Unregistered integration adapter: {name}")
    
    def activate_integration(self, integration_id: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Activate an integration.
        
        Args:
            integration_id: Integration identifier
            config: Integration configuration
            
        Returns:
            Activation result
        """
        try:
            # Get integration from registry
            integration = self.registry.get_integration(integration_id)
            if not integration:
                return {
                    'success': False,
                    'error': f'Integration not found: {integration_id}'
                }
            
            # Create adapter instance
            adapter_class = integration['adapter_class']
            adapter = adapter_class(config or integration.get('default_config', {}))
            
            # Test connection
            test_result = adapter.test_connection()
            if not test_result.get('success', False):
                return {
                    'success': False,
                    'error': f'Connection test failed: {test_result.get("error", "Unknown error")}'
                }
            
            # Store active integration
            self.active_integrations[integration_id] = {
                'adapter': adapter,
                'config': config or {},
                'activated_at': timezone.now(),
                'status': IntegrationStatus.ACTIVE,
                'last_activity': timezone.now()
            }
            
            # Initialize performance tracking
            self.performance_stats[integration_id] = {
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'avg_response_time': 0,
                'last_request_time': None
            }
            
            self.error_counts[integration_id] = 0
            
            logger.info(f"Activated integration: {integration_id}")
            
            return {
                'success': True,
                'integration_id': integration_id,
                'status': IntegrationStatus.ACTIVE,
                'activated_at': self.active_integrations[integration_id]['activated_at'].isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to activate integration {integration_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def deactivate_integration(self, integration_id: str) -> Dict[str, Any]:
        """
        Deactivate an integration.
        
        Args:
            integration_id: Integration identifier
            
        Returns:
            Deactivation result
        """
        try:
            if integration_id not in self.active_integrations:
                return {
                    'success': False,
                    'error': f'Integration not active: {integration_id}'
                }
            
            # Clean up adapter
            adapter_info = self.active_integrations[integration_id]
            adapter = adapter_info['adapter']
            
            if hasattr(adapter, 'cleanup'):
                adapter.cleanup()
            
            # Remove from active integrations
            del self.active_integrations[integration_id]
            
            # Clean up stats
            if integration_id in self.performance_stats:
                del self.performance_stats[integration_id]
            
            if integration_id in self.error_counts:
                del self.error_counts[integration_id]
            
            logger.info(f"Deactivated integration: {integration_id}")
            
            return {
                'success': True,
                'integration_id': integration_id,
                'deactivated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to deactivate integration {integration_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def execute_integration(self, integration_id: str, action: str, 
                           data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """
        Execute an integration action.
        
        Args:
            integration_id: Integration identifier
            action: Action to execute
            data: Action data
            **kwargs: Additional parameters
            
        Returns:
            Execution result
        """
        try:
            # Check if integration is active
            if integration_id not in self.active_integrations:
                return {
                    'success': False,
                    'error': f'Integration not active: {integration_id}'
                }
            
            adapter_info = self.active_integrations[integration_id]
            adapter = adapter_info['adapter']
            
            # Update last activity
            adapter_info['last_activity'] = timezone.now()
            
            # Track performance
            start_time = timezone.now()
            self.performance_stats[integration_id]['total_requests'] += 1
            self.performance_stats[integration_id]['last_request_time'] = start_time
            
            try:
                # Execute action
                result = adapter.execute(action, data or {}, **kwargs)
                
                # Update performance stats
                if result.get('success', False):
                    self.performance_stats[integration_id]['successful_requests'] += 1
                else:
                    self.performance_stats[integration_id]['failed_requests'] += 1
                    self.error_counts[integration_id] += 1
                
                # Update response time
                response_time = (timezone.now() - start_time).total_seconds()
                current_avg = self.performance_stats[integration_id]['avg_response_time']
                total_requests = self.performance_stats[integration_id]['total_requests']
                
                self.performance_stats[integration_id]['avg_response_time'] = (
                    (current_avg * (total_requests - 1) + response_time) / total_requests
                )
                
                return result
                
            except Exception as e:
                # Update error stats
                self.performance_stats[integration_id]['failed_requests'] += 1
                self.error_counts[integration_id] += 1
                
                # Check if we should deactivate due to errors
                if self.error_counts[integration_id] >= 10:  # Error threshold
                    logger.warning(f"Deactivating integration {integration_id} due to excessive errors")
                    self.deactivate_integration(integration_id)
                
                raise
            
        except Exception as e:
            logger.error(f"Failed to execute integration {integration_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'integration_id': integration_id,
                'action': action
            }
    
    def get_integration_status(self, integration_id: str = None) -> Dict[str, Any]:
        """
        Get integration status.
        
        Args:
            integration_id: Specific integration ID (None for all)
            
        Returns:
            Integration status
        """
        try:
            if integration_id:
                if integration_id not in self.active_integrations:
                    return {'status': IntegrationStatus.INACTIVE}
                
                adapter_info = self.active_integrations[integration_id]
                stats = self.performance_stats.get(integration_id, {})
                
                return {
                    'integration_id': integration_id,
                    'status': adapter_info['status'],
                    'activated_at': adapter_info['activated_at'].isoformat(),
                    'last_activity': adapter_info['last_activity'].isoformat(),
                    'performance': stats,
                    'error_count': self.error_counts.get(integration_id, 0)
                }
            else:
                # Return all integrations status
                all_status = {}
                
                for int_id in self.active_integrations:
                    all_status[int_id] = self.get_integration_status(int_id)
                
                return all_status
                
        except Exception as e:
            logger.error(f"Failed to get integration status: {str(e)}")
            return {'error': str(e)}
    
    def health_check(self, integration_id: str = None) -> Dict[str, Any]:
        """
        Perform health check on integrations.
        
        Args:
            integration_id: Specific integration ID (None for all)
            
        Returns:
            Health check results
        """
        try:
            self.last_health_check = timezone.now()
            results = {}
            
            integrations_to_check = [integration_id] if integration_id else list(self.active_integrations.keys())
            
            for int_id in integrations_to_check:
                if int_id not in self.active_integrations:
                    results[int_id] = {
                        'healthy': False,
                        'status': IntegrationStatus.INACTIVE,
                        'message': 'Integration not active'
                    }
                    continue
                
                adapter_info = self.active_integrations[int_id]
                adapter = adapter_info['adapter']
                
                try:
                    # Perform health check
                    health_result = adapter.health_check()
                    
                    results[int_id] = {
                        'healthy': health_result.get('healthy', False),
                        'status': adapter_info['status'],
                        'message': health_result.get('message', 'OK'),
                        'details': health_result.get('details', {}),
                        'checked_at': timezone.now().isoformat()
                    }
                    
                    # Update status based on health
                    if not health_result.get('healthy', False):
                        adapter_info['status'] = IntegrationStatus.DEGRADED
                    else:
                        adapter_info['status'] = IntegrationStatus.ACTIVE
                
                except Exception as e:
                    results[int_id] = {
                        'healthy': False,
                        'status': IntegrationStatus.ERROR,
                        'message': f'Health check failed: {str(e)}',
                        'checked_at': timezone.now().isoformat()
                    }
                    
                    adapter_info['status'] = IntegrationStatus.ERROR
            
            return {
                'success': True,
                'results': results,
                'checked_at': self.last_health_check.isoformat(),
                'total_integrations': len(integrations_to_check),
                'healthy_count': len([r for r in results.values() if r.get('healthy', False)])
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_performance_metrics(self, integration_id: str = None) -> Dict[str, Any]:
        """
        Get performance metrics for integrations.
        
        Args:
            integration_id: Specific integration ID (None for all)
            
        Returns:
            Performance metrics
        """
        try:
            if integration_id:
                return self.performance_stats.get(integration_id, {})
            else:
                return self.performance_stats
                
        except Exception as e:
            logger.error(f"Failed to get performance metrics: {str(e)}")
            return {'error': str(e)}
    
    def reset_error_counts(self, integration_id: str = None):
        """
        Reset error counts for integrations.
        
        Args:
            integration_id: Specific integration ID (None for all)
        """
        try:
            if integration_id:
                if integration_id in self.error_counts:
                    self.error_counts[integration_id] = 0
            else:
                for int_id in self.error_counts:
                    self.error_counts[int_id] = 0
            
            logger.info(f"Reset error counts for {integration_id or 'all integrations'}")
            
        except Exception as e:
            logger.error(f"Failed to reset error counts: {str(e)}")
    
    def cleanup_inactive_integrations(self, inactive_hours: int = 24) -> Dict[str, Any]:
        """
        Clean up inactive integrations.
        
        Args:
            inactive_hours: Hours of inactivity before cleanup
            
        Returns:
            Cleanup results
        """
        try:
            cutoff_time = timezone.now() - timedelta(hours=inactive_hours)
            cleaned_up = []
            
            for int_id, adapter_info in list(self.active_integrations.items()):
                if adapter_info['last_activity'] < cutoff_time:
                    # Deactivate inactive integration
                    result = self.deactivate_integration(int_id)
                    if result['success']:
                        cleaned_up.append(int_id)
            
            return {
                'success': True,
                'cleaned_up': cleaned_up,
                'count': len(cleaned_up),
                'cutoff_hours': inactive_hours
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup inactive integrations: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_integration_summary(self) -> Dict[str, Any]:
        """
        Get summary of all integrations.
        
        Returns:
            Integration summary
        """
        try:
            total_integrations = len(self.active_integrations)
            active_count = len([
                int_id for int_id, info in self.active_integrations.items()
                if info['status'] == IntegrationStatus.ACTIVE
            ])
            degraded_count = len([
                int_id for int_id, info in self.active_integrations.items()
                if info['status'] == IntegrationStatus.DEGRADED
            ])
            error_count = len([
                int_id for int_id, info in self.active_integrations.items()
                if info['status'] == IntegrationStatus.ERROR
            ])
            
            # Calculate overall performance
            total_requests = sum(
                stats.get('total_requests', 0) 
                for stats in self.performance_stats.values()
            )
            successful_requests = sum(
                stats.get('successful_requests', 0) 
                for stats in self.performance_stats.values()
            )
            
            success_rate = (successful_requests / max(total_requests, 1)) * 100
            
            avg_response_time = 0
            if self.performance_stats:
                avg_response_time = sum(
                    stats.get('avg_response_time', 0) 
                    for stats in self.performance_stats.values()
                ) / len(self.performance_stats)
            
            return {
                'total_integrations': total_integrations,
                'active_count': active_count,
                'degraded_count': degraded_count,
                'error_count': error_count,
                'total_requests': total_requests,
                'successful_requests': successful_requests,
                'success_rate': success_rate,
                'avg_response_time': avg_response_time,
                'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
                'registered_adapters': list(self.adapters.keys())
            }
            
        except Exception as e:
            logger.error(f"Failed to get integration summary: {str(e)}")
            return {'error': str(e)}


# Global integration handler instance
integration_handler = IntegrationHandler()


# Export classes and functions
__all__ = [
    'IntegrationHandler',
    'integration_handler'
]
