"""
Integration Bridge - Bridges external systems with alerts architecture
Provides safe bridging with existing alert models and validation
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timezone
from django.utils import timezone as django_tz
from django.db import transaction
from django.core.cache import cache

# Absolute imports to prevent ModuleNotFoundError
from api.alerts.models import AlertLog, AlertRule, Notification
from api.alerts.validators import (
    validate_alert_rule_condition, 
    validate_threshold_value, 
    validate_channel_config,
    validate_cron_expression,
    validate_webhook_url
)
from api.alerts.integration.integ_handler import integration_handler
from api.alerts.integration.integ_adapter import integration_adapter
from api.alerts.integration.integ_constants import (
    IntegrationStatus, 
    CircuitBreakerState,
    DEFAULT_TIMEOUTS,
    CACHE_KEYS,
    CACHE_TIMEOUTS
)

logger = logging.getLogger(__name__)


class IntegrationBridge:
    """
    Bridge between external systems and alerts architecture
    Maintains existing validation and security logic
    """
    
    def __init__(self):
        self.active_bridges = {}
        self.bridge_stats = {}
        self._initialize_bridge_stats()
    
    def _initialize_bridge_stats(self):
        """Initialize bridge statistics"""
        self.bridge_stats = {
            'total_bridges': 0,
            'active_bridges': 0,
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'last_activity': None
        }
    
    def create_bridge(self, bridge_id: str, source_system: str, 
                     target_system: str, config: Dict[str, Any]) -> bool:
        """
        Create bridge between systems
        Validates configuration using existing validators
        """
        try:
            # Validate bridge configuration
            validation_result = self._validate_bridge_config(config)
            if not validation_result['valid']:
                logger.error(f"Invalid bridge config for {bridge_id}: {validation_result['errors']}")
                return False
            
            # Create bridge data
            bridge_data = {
                'id': bridge_id,
                'source_system': source_system,
                'target_system': target_system,
                'config': config,
                'status': IntegrationStatus.ACTIVE.value,
                'created_at': django_tz.now().isoformat(),
                'stats': {
                    'total_requests': 0,
                    'successful_requests': 0,
                    'failed_requests': 0,
                    'last_request': None,
                    'last_success': None,
                    'last_failure': None
                }
            }
            
            self.active_bridges[bridge_id] = bridge_data
            self.bridge_stats['total_bridges'] += 1
            self.bridge_stats['active_bridges'] += 1
            
            # Cache bridge data
            cache.set(f"bridge:{bridge_id}", bridge_data, timeout=CACHE_TIMEOUTS['integration'])
            
            logger.info(f"Created bridge: {bridge_id} ({source_system} -> {target_system})")
            return True
            
        except Exception as e:
            logger.error(f"Error creating bridge {bridge_id}: {e}")
            return False
    
    def _validate_bridge_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate bridge configuration using existing validators
        """
        try:
            errors = []
            
            # Validate webhook configuration if present
            if 'webhook_url' in config:
                webhook_validation = validate_webhook_url(config['webhook_url'])
                if not webhook_validation['valid']:
                    errors.extend(webhook_validation['errors'])
            
            # Validate channel configuration if present
            if 'channel_config' in config and 'channel_type' in config:
                config_validation = validate_channel_config(config['channel_config'], config['channel_type'])
                if not config_validation['valid']:
                    errors.extend(config_validation['errors'])
            
            # Validate threshold if present
            if 'threshold' in config:
                threshold_validation = validate_threshold_value(config['threshold'])
                if not threshold_validation['valid']:
                    errors.extend(threshold_validation['errors'])
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error validating bridge config: {e}")
            return {
                'valid': False,
                'errors': ['Validation error']
            }
    
    def process_bridge_request(self, bridge_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process request through bridge
        """
        try:
            bridge = self.get_bridge(bridge_id)
            if not bridge:
                return {
                    'success': False,
                    'error': f'Bridge not found: {bridge_id}'
                }
            
            if bridge['status'] != IntegrationStatus.ACTIVE.value:
                return {
                    'success': False,
                    'error': f'Bridge not active: {bridge_id}'
                }
            
            # Update bridge stats
            self._update_bridge_stats(bridge_id, 'request')
            
            # Process data through adapter
            source_system = bridge['source_system']
            adapted_data = integration_adapter.adapt_external_alert(source_system, data)
            
            if not adapted_data.get('success', False):
                self._update_bridge_stats(bridge_id, 'failure', adapted_data.get('error'))
                return adapted_data
            
            # Process through integration handler
            result = integration_handler.process_alert_data(adapted_data)
            
            # Update bridge stats based on result
            if result.get('success', False):
                self._update_bridge_stats(bridge_id, 'success')
            else:
                self._update_bridge_stats(bridge_id, 'failure', result.get('error'))
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing bridge request {bridge_id}: {e}")
            self._update_bridge_stats(bridge_id, 'failure', str(e))
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def get_bridge(self, bridge_id: str) -> Optional[Dict[str, Any]]:
        """
        Get bridge by ID
        """
        try:
            # Try cache first
            cached_data = cache.get(f"bridge:{bridge_id}")
            if cached_data:
                return cached_data
            
            # Fallback to memory
            return self.active_bridges.get(bridge_id)
            
        except Exception as e:
            logger.error(f"Error getting bridge {bridge_id}: {e}")
            return None
    
    def update_bridge_status(self, bridge_id: str, status: IntegrationStatus) -> bool:
        """
        Update bridge status
        """
        try:
            bridge = self.get_bridge(bridge_id)
            if not bridge:
                return False
            
            old_status = bridge['status']
            bridge['status'] = status.value
            
            # Update active bridges count
            if old_status == IntegrationStatus.ACTIVE.value and status != IntegrationStatus.ACTIVE:
                self.bridge_stats['active_bridges'] -= 1
            elif old_status != IntegrationStatus.ACTIVE.value and status == IntegrationStatus.ACTIVE:
                self.bridge_stats['active_bridges'] += 1
            
            # Update cache
            cache.set(f"bridge:{bridge_id}", bridge, timeout=CACHE_TIMEOUTS['integration'])
            
            logger.info(f"Updated bridge {bridge_id} status: {old_status} -> {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating bridge status {bridge_id}: {e}")
            return False
    
    def _update_bridge_stats(self, bridge_id: str, stat_type: str, error: Optional[str] = None):
        """
        Update bridge statistics
        """
        try:
            bridge = self.get_bridge(bridge_id)
            if not bridge:
                return
            
            stats = bridge['stats']
            stats['last_request'] = django_tz.now().isoformat()
            
            if stat_type == 'request':
                stats['total_requests'] += 1
                self.bridge_stats['total_requests'] += 1
                self.bridge_stats['last_activity'] = django_tz.now().isoformat()
                
            elif stat_type == 'success':
                stats['successful_requests'] += 1
                stats['last_success'] = django_tz.now().isoformat()
                self.bridge_stats['successful_requests'] += 1
                
            elif stat_type == 'failure':
                stats['failed_requests'] += 1
                stats['last_failure'] = django_tz.now().isoformat()
                if error:
                    stats['last_error'] = error
                self.bridge_stats['failed_requests'] += 1
            
            # Update cache
            cache.set(f"bridge:{bridge_id}", bridge, timeout=CACHE_TIMEOUTS['integration'])
            
        except Exception as e:
            logger.error(f"Error updating bridge stats for {bridge_id}: {e}")
    
    def get_bridge_stats(self, bridge_id: str) -> Optional[Dict[str, Any]]:
        """
        Get bridge statistics
        """
        try:
            bridge = self.get_bridge(bridge_id)
            if bridge:
                return bridge.get('stats', {})
            return None
        except Exception as e:
            logger.error(f"Error getting bridge stats for {bridge_id}: {e}")
            return None
    
    def get_all_bridges(self) -> List[Dict[str, Any]]:
        """
        Get all active bridges
        """
        try:
            return list(self.active_bridges.values())
        except Exception as e:
            logger.error(f"Error getting all bridges: {e}")
            return []
    
    def get_bridges_by_system(self, source_system: str = None, target_system: str = None) -> List[Dict[str, Any]]:
        """
        Get bridges by source or target system
        """
        try:
            bridges = []
            for bridge in self.active_bridges.values():
                if source_system and bridge['source_system'] != source_system:
                    continue
                if target_system and bridge['target_system'] != target_system:
                    continue
                bridges.append(bridge)
            
            return bridges
        except Exception as e:
            logger.error(f"Error getting bridges by system: {e}")
            return []
    
    def delete_bridge(self, bridge_id: str) -> bool:
        """
        Delete bridge
        """
        try:
            if bridge_id in self.active_bridges:
                bridge = self.active_bridges[bridge_id]
                
                # Update stats
                if bridge['status'] == IntegrationStatus.ACTIVE.value:
                    self.bridge_stats['active_bridges'] -= 1
                self.bridge_stats['total_bridges'] -= 1
                
                # Remove from memory
                del self.active_bridges[bridge_id]
                
                # Remove from cache
                cache.delete(f"bridge:{bridge_id}")
                
                logger.info(f"Deleted bridge: {bridge_id}")
                return True
            else:
                logger.warning(f"Bridge not found: {bridge_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting bridge {bridge_id}: {e}")
            return False
    
    def get_bridge_performance_metrics(self) -> Dict[str, Any]:
        """
        Get bridge performance metrics
        """
        try:
            total_requests = self.bridge_stats['total_requests']
            total_success = self.bridge_stats['successful_requests']
            total_failures = self.bridge_stats['failed_requests']
            
            # Calculate success rate
            success_rate = (total_success / max(total_requests, 1)) * 100
            
            # Calculate failure rate
            failure_rate = (total_failures / max(total_requests, 1)) * 100
            
            # Get individual bridge metrics
            bridge_metrics = []
            for bridge_id, bridge in self.active_bridges.items():
                stats = bridge.get('stats', {})
                bridge_total = stats.get('total_requests', 0)
                bridge_success = stats.get('successful_requests', 0)
                bridge_success_rate = (bridge_success / max(bridge_total, 1)) * 100
                
                bridge_metrics.append({
                    'bridge_id': bridge_id,
                    'source_system': bridge['source_system'],
                    'target_system': bridge['target_system'],
                    'status': bridge['status'],
                    'total_requests': bridge_total,
                    'success_rate': bridge_success_rate,
                    'last_request': stats.get('last_request')
                })
            
            return {
                'overall_stats': {
                    'total_bridges': self.bridge_stats['total_bridges'],
                    'active_bridges': self.bridge_stats['active_bridges'],
                    'total_requests': total_requests,
                    'success_rate': success_rate,
                    'failure_rate': failure_rate,
                    'last_activity': self.bridge_stats['last_activity']
                },
                'bridge_metrics': bridge_metrics,
                'timestamp': django_tz.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting bridge performance metrics: {e}")
            return {
                'error': 'Operation failed',
                'timestamp': django_tz.now().isoformat()
            }
    
    def cleanup_inactive_bridges(self) -> int:
        """
        Cleanup inactive bridges
        """
        try:
            inactive_count = 0
            
            # Find inactive bridges
            inactive_bridges = []
            for bridge_id, bridge in self.active_bridges.items():
                if bridge['status'] != IntegrationStatus.ACTIVE.value:
                    inactive_bridges.append(bridge_id)
            
            # Remove inactive bridges
            for bridge_id in inactive_bridges:
                self.delete_bridge(bridge_id)
                inactive_count += 1
            
            logger.info(f"Cleaned up {inactive_count} inactive bridges")
            return inactive_count
            
        except Exception as e:
            logger.error(f"Error cleaning up inactive bridges: {e}")
            return 0


# Global bridge instance
integration_bridge = IntegrationBridge()


# Bridge management functions
def create_system_bridge(bridge_id: str, source_system: str, target_system: str, config: Dict[str, Any]) -> bool:
    """
    Create bridge between systems
    """
    return integration_bridge.create_bridge(bridge_id, source_system, target_system, config)


def process_bridge_alert(bridge_id: str, alert_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process alert through bridge
    """
    return integration_bridge.process_bridge_request(bridge_id, alert_data)


def get_bridge_metrics() -> Dict[str, Any]:
    """
    Get bridge performance metrics
    """
    return integration_bridge.get_bridge_performance_metrics()
