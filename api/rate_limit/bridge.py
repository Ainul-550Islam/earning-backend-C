# api/rate_limit/bridge.py
"""
Bridge system for rate limit module.

Provides bridge patterns for connecting different systems and modules.
"""

import logging
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache

from api.rate_limit.integ_handler import integration_handler
from api.rate_limit.integ_constants import IntegrationStatus, IntegrationEvent
from api.rate_limit.integ_exceptions import IntegrationError

logger = logging.getLogger(__name__)


class BaseBridge:
    """
    Base class for system bridges.
    """
    
    def __init__(self, name: str, source_system: str, target_system: str):
        self.name = name
        self.source_system = source_system
        self.target_system = target_system
        self.is_active = True
        self.last_activity = None
        self.transformers = {}
        self.error_count = 0
        self.max_errors = 10
    
    def connect(self) -> Dict[str, Any]:
        """
        Establish connection between systems.
        
        Returns:
            Connection result
        """
        raise NotImplementedError("Subclasses must implement connect()")
    
    def disconnect(self) -> Dict[str, Any]:
        """
        Disconnect systems.
        
        Returns:
            Disconnection result
        """
        raise NotImplementedError("Subclasses must implement disconnect()")
    
    def transform(self, data: Dict[str, Any], direction: str = 'source_to_target') -> Dict[str, Any]:
        """
        Transform data between systems.
        
        Args:
            data: Data to transform
            direction: Transformation direction
            
        Returns:
            Transformed data
        """
        transformer = self.transformers.get(direction)
        if transformer:
            return transformer(data)
        return data
    
    def send(self, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Send data to target system.
        
        Args:
            data: Data to send
            **kwargs: Additional parameters
            
        Returns:
            Send result
        """
        raise NotImplementedError("Subclasses must implement send()")
    
    def receive(self, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Receive data from source system.
        
        Args:
            data: Received data
            **kwargs: Additional parameters
            
        Returns:
            Receive result
        """
        raise NotImplementedError("Subclasses must implement receive()")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on bridge.
        
        Returns:
            Health check result
        """
        try:
            # Check error count
            if self.error_count >= self.max_errors:
                return {
                    'healthy': False,
                    'message': f"Too many errors: {self.error_count}/{self.max_errors}",
                    'details': {'error_count': self.error_count}
                }
            
            # Check last activity
            if self.last_activity:
                inactive_hours = (timezone.now() - self.last_activity).total_seconds() / 3600
                if inactive_hours > 24:
                    return {
                        'healthy': False,
                        'message': f"Inactive for {inactive_hours:.1f} hours",
                        'details': {'inactive_hours': inactive_hours}
                    }
            
            return {
                'healthy': True,
                'message': 'Bridge is healthy',
                'details': {
                    'name': self.name,
                    'source_system': self.source_system,
                    'target_system': self.target_system,
                    'is_active': self.is_active,
                    'last_activity': self.last_activity.isoformat() if self.last_activity else None
                }
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'message': f"Health check failed: {str(e)}",
                'details': {'error': str(e)}
            }
    
    def add_transformer(self, direction: str, transformer: Callable):
        """
        Add data transformer.
        
        Args:
            direction: Transformation direction
            transformer: Transformer function
        """
        self.transformers[direction] = transformer
        logger.info(f"Added transformer for {direction} in bridge {self.name}")
    
    def remove_transformer(self, direction: str):
        """
        Remove data transformer.
        
        Args:
            direction: Transformation direction
        """
        if direction in self.transformers:
            del self.transformers[direction]
            logger.info(f"Removed transformer for {direction} in bridge {self.name}")


class RateLimitToAnalyticsBridge(BaseBridge):
    """
    Bridge between rate limiting and analytics systems.
    """
    
    def __init__(self):
        super().__init__(
            name='rate_limit_to_analytics',
            source_system='rate_limit',
            target_system='analytics'
        )
        self._setup_transformers()
    
    def _setup_transformers(self):
        """Setup data transformers."""
        def transform_to_analytics(data):
            """Transform rate limit data to analytics format."""
            return {
                'event_type': data.get('event_type', 'unknown'),
                'timestamp': data.get('timestamp', timezone.now().isoformat()),
                'source': 'rate_limit',
                'data': {
                    'user_id': data.get('user_id'),
                    'ip_address': data.get('ip_address'),
                    'endpoint': data.get('endpoint'),
                    'status': data.get('status'),
                    'suspicion_score': data.get('suspicion_score', 0),
                    'metadata': data.get('metadata', {})
                }
            }
        
        self.add_transformer('source_to_target', transform_to_analytics)
    
    def connect(self) -> Dict[str, Any]:
        """Connect to analytics system."""
        try:
            # Check if analytics integration is available
            analytics_integration = integration_handler.active_integrations.get('analytics')
            
            if not analytics_integration:
                return {
                    'success': False,
                    'error': 'Analytics integration not active'
                }
            
            self.is_active = True
            logger.info("Connected rate limit to analytics bridge")
            
            return {
                'success': True,
                'connected_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to connect rate limit to analytics bridge: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def disconnect(self) -> Dict[str, Any]:
        """Disconnect from analytics system."""
        try:
            self.is_active = False
            logger.info("Disconnected rate limit to analytics bridge")
            
            return {
                'success': True,
                'disconnected_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to disconnect rate limit to analytics bridge: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def send(self, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Send rate limit data to analytics."""
        try:
            if not self.is_active:
                return {
                    'success': False,
                    'error': 'Bridge is not active'
                }
            
            # Transform data
            transformed_data = self.transform(data, 'source_to_target')
            
            # Send to analytics integration
            result = integration_handler.execute_integration(
                'analytics',
                'store_event',
                transformed_data
            )
            
            if result['success']:
                self.last_activity = timezone.now()
            else:
                self.error_count += 1
            
            return result
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Failed to send data to analytics: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def receive(self, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Receive analytics data."""
        try:
            # Store analytics data in cache for processing
            cache_key = f"analytics_bridge_data:{timezone.now().timestamp()}"
            cache.set(cache_key, data, timeout=300)  # 5 minutes
            
            self.last_activity = timezone.now()
            
            return {
                'success': True,
                'cached_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Failed to receive analytics data: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


class RateLimitToSecurityBridge(BaseBridge):
    """
    Bridge between rate limiting and security systems.
    """
    
    def __init__(self):
        super().__init__(
            name='rate_limit_to_security',
            source_system='rate_limit',
            target_system='security'
        )
        self._setup_transformers()
    
    def _setup_transformers(self):
        """Setup data transformers."""
        def transform_to_security(data):
            """Transform rate limit data to security format."""
            return {
                'alert_type': 'rate_limit_violation',
                'severity': self._calculate_severity(data),
                'timestamp': data.get('timestamp', timezone.now().isoformat()),
                'source': 'rate_limit',
                'data': {
                    'user_id': data.get('user_id'),
                    'ip_address': data.get('ip_address'),
                    'endpoint': data.get('endpoint'),
                    'event_type': data.get('event_type'),
                    'suspicion_score': data.get('suspicion_score', 0),
                    'metadata': data.get('metadata', {})
                }
            }
        
        self.add_transformer('source_to_target', transform_to_security)
    
    def _calculate_severity(self, data: Dict[str, Any]) -> str:
        """Calculate security severity."""
        suspicion_score = data.get('suspicion_score', 0)
        event_type = data.get('event_type', '')
        
        if event_type == 'abuse_detected' or suspicion_score >= 80:
            return 'critical'
        elif event_type == 'rate_limit_exceeded' or suspicion_score >= 60:
            return 'high'
        elif suspicion_score >= 40:
            return 'medium'
        else:
            return 'low'
    
    def connect(self) -> Dict[str, Any]:
        """Connect to security system."""
        try:
            # Check if security integration is available
            security_integration = integration_handler.active_integrations.get('security')
            
            if not security_integration:
                return {
                    'success': False,
                    'error': 'Security integration not active'
                }
            
            self.is_active = True
            logger.info("Connected rate limit to security bridge")
            
            return {
                'success': True,
                'connected_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to connect rate limit to security bridge: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def disconnect(self) -> Dict[str, Any]:
        """Disconnect from security system."""
        try:
            self.is_active = False
            logger.info("Disconnected rate limit to security bridge")
            
            return {
                'success': True,
                'disconnected_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to disconnect rate limit to security bridge: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def send(self, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Send rate limit data to security."""
        try:
            if not self.is_active:
                return {
                    'success': False,
                    'error': 'Bridge is not active'
                }
            
            # Transform data
            transformed_data = self.transform(data, 'source_to_target')
            
            # Send to security integration
            result = integration_handler.execute_integration(
                'security',
                'create_alert',
                transformed_data
            )
            
            if result['success']:
                self.last_activity = timezone.now()
            else:
                self.error_count += 1
            
            return result
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Failed to send data to security: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def receive(self, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Receive security data."""
        try:
            # Process security recommendations
            if data.get('type') == 'security_recommendation':
                recommendation = data.get('recommendation', '')
                
                # Apply security recommendation
                if recommendation == 'block_ip':
                    ip_address = data.get('ip_address')
                    if ip_address:
                        # Block IP through rate limit system
                        from api.rate_limit.services import RateLimitService
                        rate_limit_service = RateLimitService()
                        rate_limit_service._block_ip_address(ip_address, 'security_recommendation')
                
                self.last_activity = timezone.now()
            
            return {
                'success': True,
                'processed_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Failed to receive security data: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


class RateLimitToNotificationBridge(BaseBridge):
    """
    Bridge between rate limiting and notification systems.
    """
    
    def __init__(self):
        super().__init__(
            name='rate_limit_to_notification',
            source_system='rate_limit',
            target_system='notification'
        )
        self._setup_transformers()
    
    def _setup_transformers(self):
        """Setup data transformers."""
        def transform_to_notification(data):
            """Transform rate limit data to notification format."""
            return {
                'notification_type': self._get_notification_type(data),
                'priority': self._get_priority(data),
                'title': self._get_title(data),
                'message': self._get_message(data),
                'timestamp': data.get('timestamp', timezone.now().isoformat()),
                'data': {
                    'user_id': data.get('user_id'),
                    'ip_address': data.get('ip_address'),
                    'endpoint': data.get('endpoint'),
                    'event_type': data.get('event_type'),
                    'metadata': data.get('metadata', {})
                }
            }
        
        self.add_transformer('source_to_target', transform_to_notification)
    
    def _get_notification_type(self, data: Dict[str, Any]) -> str:
        """Get notification type."""
        event_type = data.get('event_type', '')
        
        if event_type == 'abuse_detected':
            return 'security_alert'
        elif event_type == 'rate_limit_exceeded':
            return 'rate_limit_alert'
        elif event_type == 'system_alert':
            return 'system_notification'
        else:
            return 'general_notification'
    
    def _get_priority(self, data: Dict[str, Any]) -> str:
        """Get notification priority."""
        suspicion_score = data.get('suspicion_score', 0)
        event_type = data.get('event_type', '')
        
        if event_type == 'abuse_detected' or suspicion_score >= 80:
            return 'high'
        elif event_type == 'rate_limit_exceeded' or suspicion_score >= 60:
            return 'medium'
        else:
            return 'low'
    
    def _get_title(self, data: Dict[str, Any]) -> str:
        """Get notification title."""
        event_type = data.get('event_type', '')
        
        titles = {
            'abuse_detected': 'Abuse Detected',
            'rate_limit_exceeded': 'Rate Limit Exceeded',
            'config_updated': 'Configuration Updated',
            'system_alert': 'System Alert'
        }
        
        return titles.get(event_type, 'Rate Limit Event')
    
    def _get_message(self, data: Dict[str, Any]) -> str:
        """Get notification message."""
        event_type = data.get('event_type', '')
        ip_address = data.get('ip_address', 'unknown')
        endpoint = data.get('endpoint', 'unknown')
        
        messages = {
            'abuse_detected': f'Abuse detected from IP {ip_address} on {endpoint}',
            'rate_limit_exceeded': f'Rate limit exceeded for IP {ip_address} on {endpoint}',
            'config_updated': f'Rate limit configuration has been updated',
            'system_alert': f'System alert: {data.get("message", "Unknown")}'
        }
        
        return messages.get(event_type, f'Rate limit event: {event_type}')
    
    def connect(self) -> Dict[str, Any]:
        """Connect to notification system."""
        try:
            # Check if notification integration is available
            notification_integration = integration_handler.active_integrations.get('notification')
            
            if not notification_integration:
                return {
                    'success': False,
                    'error': 'Notification integration not active'
                }
            
            self.is_active = True
            logger.info("Connected rate limit to notification bridge")
            
            return {
                'success': True,
                'connected_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to connect rate limit to notification bridge: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def disconnect(self) -> Dict[str, Any]:
        """Disconnect from notification system."""
        try:
            self.is_active = False
            logger.info("Disconnected rate limit to notification bridge")
            
            return {
                'success': True,
                'disconnected_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to disconnect rate limit to notification bridge: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def send(self, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Send rate limit data to notification."""
        try:
            if not self.is_active:
                return {
                    'success': False,
                    'error': 'Bridge is not active'
                }
            
            # Transform data
            transformed_data = self.transform(data, 'source_to_target')
            
            # Send to notification integration
            result = integration_handler.execute_integration(
                'notification',
                'send_notification',
                transformed_data
            )
            
            if result['success']:
                self.last_activity = timezone.now()
            else:
                self.error_count += 1
            
            return result
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Failed to send data to notification: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def receive(self, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Receive notification data."""
        try:
            # Process notification acknowledgments
            if data.get('type') == 'notification_acknowledgment':
                notification_id = data.get('notification_id')
                
                # Log acknowledgment
                logger.info(f"Notification {notification_id} acknowledged")
                
                self.last_activity = timezone.now()
            
            return {
                'success': True,
                'processed_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Failed to receive notification data: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


class BridgeManager:
    """
    Manager for system bridges.
    """
    
    def __init__(self):
        self.bridges: Dict[str, BaseBridge] = {}
        self._initialize_default_bridges()
    
    def _initialize_default_bridges(self):
        """Initialize default bridges."""
        # Add default bridges
        self.add_bridge(RateLimitToAnalyticsBridge())
        self.add_bridge(RateLimitToSecurityBridge())
        self.add_bridge(RateLimitToNotificationBridge())
    
    def add_bridge(self, bridge: BaseBridge):
        """
        Add a bridge.
        
        Args:
            bridge: Bridge instance
        """
        self.bridges[bridge.name] = bridge
        logger.info(f"Added bridge: {bridge.name}")
    
    def remove_bridge(self, name: str):
        """
        Remove a bridge.
        
        Args:
            name: Bridge name
        """
        if name in self.bridges:
            del self.bridges[name]
            logger.info(f"Removed bridge: {name}")
    
    def get_bridge(self, name: str) -> Optional[BaseBridge]:
        """
        Get a bridge by name.
        
        Args:
            name: Bridge name
            
        Returns:
            Bridge instance or None
        """
        return self.bridges.get(name)
    
    def list_bridges(self) -> List[Dict[str, Any]]:
        """
        List all bridges.
        
        Returns:
            List of bridge information
        """
        return [
            {
                'name': bridge.name,
                'source_system': bridge.source_system,
                'target_system': bridge.target_system,
                'is_active': bridge.is_active,
                'last_activity': bridge.last_activity.isoformat() if bridge.last_activity else None,
                'error_count': bridge.error_count
            }
            for bridge in self.bridges.values()
        ]
    
    def connect_all(self) -> Dict[str, Any]:
        """
        Connect all bridges.
        
        Returns:
            Connection results
        """
        results = {}
        
        for name, bridge in self.bridges.items():
            result = bridge.connect()
            results[name] = result
        
        return results
    
    def disconnect_all(self) -> Dict[str, Any]:
        """
        Disconnect all bridges.
        
        Returns:
            Disconnection results
        """
        results = {}
        
        for name, bridge in self.bridges.items():
            result = bridge.disconnect()
            results[name] = result
        
        return results
    
    def health_check_all(self) -> Dict[str, Any]:
        """
        Perform health check on all bridges.
        
        Returns:
            Health check results
        """
        results = {}
        
        for name, bridge in self.bridges.items():
            result = bridge.health_check()
            results[name] = result
        
        return results
    
    def send_to_all(self, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Send data to all active bridges.
        
        Args:
            data: Data to send
            **kwargs: Additional parameters
            
        Returns:
            Send results
        """
        results = {}
        
        for name, bridge in self.bridges.items():
            if bridge.is_active:
                result = bridge.send(data, **kwargs)
                results[name] = result
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get bridge statistics.
        
        Returns:
            Bridge statistics
        """
        total_bridges = len(self.bridges)
        active_bridges = len([
            bridge for bridge in self.bridges.values()
            if bridge.is_active
        ])
        
        total_errors = sum(bridge.error_count for bridge in self.bridges.values())
        
        return {
            'total_bridges': total_bridges,
            'active_bridges': active_bridges,
            'inactive_bridges': total_bridges - active_bridges,
            'total_errors': total_errors,
            'bridges': {
                name: {
                    'is_active': bridge.is_active,
                    'error_count': bridge.error_count,
                    'last_activity': bridge.last_activity.isoformat() if bridge.last_activity else None
                }
                for name, bridge in self.bridges.items()
            }
        }


# Global bridge manager instance
bridge_manager = BridgeManager()


# Export classes and functions
__all__ = [
    'BaseBridge',
    'RateLimitToAnalyticsBridge',
    'RateLimitToSecurityBridge',
    'RateLimitToNotificationBridge',
    'BridgeManager',
    'bridge_manager'
]
