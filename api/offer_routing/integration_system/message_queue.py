"""
Message Queue Integration

High traffic manager for integration system
with publish-subscribe pattern.
"""

import logging
import json
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.conf import settings
from .integ_adapter import BaseIntegrationAdapter
from .integ_constants import IntegrationType, IntegrationStatus
from ..exceptions import IntegrationError

logger = logging.getLogger(__name__)


class MessageQueueIntegration(BaseIntegrationAdapter):
    """Message queue integration adapter."""
    
    def _initialize(self):
        """Initialize message queue integration."""
        self.queue_name = self.config.get('queue_name', 'routing_integrations')
        self.connection = None
        self.channel = None
        self.consumer_tag = f"routing_integration_{self.integration_id}"
        
        logger.info(f"Initialized message queue integration {self.integration_id}")
    
    def execute(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute message queue action."""
        try:
            if action == 'publish_message':
                return self._publish_message(data)
            elif action == 'create_queue':
                return self._create_queue(data)
            elif action == 'delete_queue':
                return self._delete_queue(data)
            else:
                return {
                    'success': False,
                    'error': f'Unknown action: {action}'
                }
                
        except Exception as e:
            logger.error(f"Error executing message queue action {action}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _publish_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Publish message to queue."""
        try:
            if not self.connection:
                self._connect()
            
            message = {
                'id': self._generate_message_id(),
                'content': data,
                'timestamp': timezone.now().isoformat(),
                'integration_id': self.integration_id,
                'message_type': data.get('message_type', 'generic')
            }
            
            # Serialize message
            serialized_message = json.dumps(message)
            
            # Publish to queue
            self.channel.basic_publish(
                exchange=self.config.get('exchange', 'routing_integrations'),
                routing_key=self.config.get('routing_key', 'routing.integration'),
                body=serialized_message,
                properties={
                    'delivery_mode': 2,
                    'message_id': message['id'],
                    'timestamp': str(timezone.now().timestamp())
                }
            )
            
            return {
                'success': True,
                'message_id': message['id'],
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_queue(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create message queue."""
        try:
            queue_name = data.get('queue_name', self.queue_name)
            durable = data.get('durable', True)
            auto_delete = data.get('auto_delete', False)
            
            # Declare queue
            self.channel.queue_declare(
                queue=queue_name,
                durable=durable,
                auto_delete=auto_delete
            )
            
            return {
                'success': True,
                'queue_name': queue_name,
                'durable': durable,
                'auto_delete': auto_delete,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error creating queue: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _delete_queue(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Delete message queue."""
        try:
            queue_name = data.get('queue_name', self.queue_name)
            
            # Delete queue
            self.channel.queue_delete(queue=queue_name)
            
            return {
                'success': True,
                'queue_name': queue_name,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error deleting queue: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _connect(self):
        """Connect to message queue."""
        try:
            import pika
            
            credentials = pika.PlainCredentials(
                username=self.config.get('username', ''),
                password=self.config.get('password', '')
            )
            
            connection = pika.BlockingConnection(
                host=self.config.get('host', 'localhost'),
                port=self.config.get('port', 5672),
                virtual_host=self.config.get('virtual_host', '/'),
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            
            self.connection = connection
            self.channel = connection.channel()
            
            # Declare exchange
            self.channel.exchange_declare(
                exchange=self.config.get('exchange', 'routing_integrations'),
                exchange_type='topic',
                durable=True
            )
            
            logger.info(f"Connected to message queue: {self.config.get('host')}")
            
        except Exception as e:
            logger.error(f"Error connecting to message queue: {e}")
            raise IntegrationError(f"Failed to connect to message queue: {e}")
    
    def _generate_message_id(self) -> str:
        """Generate unique message ID."""
        import uuid
        return str(uuid.uuid4())
    
    def get_status(self) -> Dict[str, Any]:
        """Get message queue integration status."""
        try:
            connection_status = 'connected' if self.connection and self.connection.is_open else 'disconnected'
            channel_status = 'open' if self.channel and self.channel.is_open else 'closed'
            
            return {
                'integration_id': self.integration_id,
                'type': IntegrationType.MESSAGE_QUEUE.value,
                'status': self.status,
                'connection_status': connection_status,
                'channel_status': channel_status,
                'queue_name': self.queue_name,
                'config': self.get_safe_config(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting message queue status: {e}")
            return {
                'status': IntegrationStatus.ERROR.value,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def get_config(self) -> Dict[str, Any]:
        """Get message queue configuration."""
        return self.config
    
    def get_safe_config(self) -> Dict[str, Any]:
        """Get safe configuration (without credentials)."""
        safe_config = self.config.copy()
        
        # Remove sensitive fields
        safe_config.pop('password', None)
        safe_config.pop('api_key', None)
        
        return safe_config
    
    def _enable(self) -> bool:
        """Enable message queue integration."""
        try:
            if not self.connection:
                self._connect()
            
            return True
            
        except Exception as e:
            logger.error(f"Error enabling message queue integration: {e}")
            return False
    
    def _disable(self) -> bool:
        """Disable message queue integration."""
        try:
            if self.connection:
                self.connection.close()
                self.connection = None
                self.channel = None
            
            logger.info(f"Disabled message queue integration {self.integration_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error disabling message queue integration: {e}")
            return False
    
    def _sync(self) -> Dict[str, Any]:
        """Sync message queue integration."""
        try:
            # Check connection status
            if not self.connection or not self.connection.is_open:
                self._connect()
            
            # Test publishing
            test_message = {
                'test': True,
                'timestamp': timezone.now().isoformat()
            }
            
            test_result = self._publish_message(test_message)
            
            return {
                'success': test_result['success'],
                'message': 'Message queue integration is operational',
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error syncing message queue integration: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _health_check(self) -> Dict[str, Any]:
        """Health check for message queue integration."""
        try:
            # Check connection
            connection_healthy = self.connection and self.connection.is_open
            
            # Check channel
            channel_healthy = self.channel and self.channel.is_open
            
            # Test queue operations
            queue_healthy = True
            if self.channel:
                try:
                    # Test queue declaration
                    self.channel.queue_declare(
                        queue=self.queue_name,
                        durable=True,
                        passive=True  # Don't create, just check
                    )
                except Exception as e:
                    queue_healthy = False
                    logger.error(f"Queue health check failed: {e}")
            
            overall_healthy = connection_healthy and channel_healthy and queue_healthy
            
            return {
                'status': 'healthy' if overall_healthy else 'unhealthy',
                'connection_healthy': connection_healthy,
                'channel_healthy': channel_healthy,
                'queue_healthy': queue_healthy,
                'queue_name': self.queue_name,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in message queue health check: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _get_metrics(self) -> Dict[str, Any]:
        """Get message queue metrics."""
        try:
            metrics = {
                'queue_name': self.queue_name,
                'connection_status': 'connected' if self.connection and self.connection.is_open else 'disconnected',
                'channel_status': 'open' if self.channel and self.channel.is_open else 'closed',
                'exchange': self.config.get('exchange', 'routing_integrations'),
                'routing_key': self.config.get('routing_key', 'routing.integration'),
                'host': self.config.get('host', 'localhost'),
                'port': self.config.get('port', 5672),
                'virtual_host': self.config.get('virtual_host', '/')
            }
            
            # This would collect actual metrics from the message queue
            # For now, return basic metrics
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting message queue metrics: {e}")
            return {
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
