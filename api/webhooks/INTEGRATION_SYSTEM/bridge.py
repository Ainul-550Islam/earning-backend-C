"""Bridge System

This module provides bridge components for integration system
with comprehensive event bus and data bridging capabilities.
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from abc import ABC, abstractmethod
from django.utils import timezone
from django.conf import settings

from .integ_constants import BridgeType, QueueType, HealthStatus
from .integ_exceptions import BridgeError
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class BaseBridge(ABC):
    """
    Abstract base class for bridge components.
    Defines the interface that all bridges must implement.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the bridge."""
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.monitor = PerformanceMonitor()
        
        # Load configuration
        self._load_configuration()
        
        # Initialize bridge
        self._initialize_bridge()
    
    def _load_configuration(self):
        """Load bridge configuration."""
        try:
            self.enabled = self.config.get('enabled', True)
            self.timeout = self.config.get('timeout', 30)
            self.retry_attempts = self.config.get('retry_attempts', 3)
            self.batch_size = self.config.get('batch_size', 100)
            self.enable_persistence = self.config.get('enable_persistence', True)
            
        except Exception as e:
            self.logger.error(f"Error loading bridge configuration: {str(e)}")
            self.enabled = True
            self.timeout = 30
            self.retry_attempts = 3
            self.batch_size = 100
            self.enable_persistence = True
    
    @abstractmethod
    def _initialize_bridge(self):
        """Initialize the bridge."""
        pass
    
    @abstractmethod
    def send(self, data: Dict[str, Any], destination: str = None) -> bool:
        """
        Send data through the bridge.
        
        Args:
            data: Data to send
            destination: Optional destination
            
        Returns:
            True if send successful
        """
        pass
    
    @abstractmethod
    def receive(self, source: str = None) -> Optional[Dict[str, Any]]:
        """
        Receive data from the bridge.
        
        Args:
            source: Optional source
            
        Returns:
            Received data or None
        """
        pass
    
    @abstractmethod
    def get_bridge_info(self) -> Dict[str, Any]:
        """
        Get bridge information.
        
        Returns:
            Bridge information
        """
        pass
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of bridge.
        
        Returns:
            Health check results
        """
        try:
            return {
                'status': HealthStatus.HEALTHY,
                'enabled': self.enabled,
                'timeout': self.timeout,
                'retry_attempts': self.retry_attempts,
                'batch_size': self.batch_size,
                'enable_persistence': self.enable_persistence,
                'checked_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'status': HealthStatus.UNHEALTHY,
                'error': str(e),
                'checked_at': timezone.now().isoformat()
            }


class EventBusBridge(BaseBridge):
    """
    Event bus bridge for integration system.
    Handles event broadcasting and subscription management.
    """
    
    def _initialize_bridge(self):
        """Initialize the event bus bridge."""
        try:
            self.subscribers = {}
            self.event_history = []
            self.max_history = self.config.get('max_history', 1000)
            
            # Initialize event bus
            self._initialize_event_bus()
            
            self.logger.info("Event bus bridge initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing event bus bridge: {str(e)}")
            raise
    
    def _initialize_event_bus(self):
        """Initialize the event bus."""
        try:
            # Load event bus configuration
            self.event_bus_config = self.config.get('event_bus', {})
            self.enable_persistence = self.event_bus_config.get('enable_persistence', True)
            self.max_subscribers = self.event_bus_config.get('max_subscribers', 100)
            
        except Exception as e:
            self.logger.error(f"Error initializing event bus: {str(e)}")
            raise
    
    def send(self, data: Dict[str, Any], destination: str = None) -> bool:
        """
        Send event through the event bus.
        
        Args:
            data: Event data
            destination: Optional destination (event type)
            
        Returns:
            True if send successful
        """
        try:
            with self.monitor.measure_bridge('event_bus') as measurement:
                # Validate event data
                if not self._validate_event_data(data):
                    raise BridgeError("Invalid event data")
                
                # Get event type
                event_type = destination or data.get('event_type')
                if not event_type:
                    raise BridgeError("Event type not specified")
                
                # Add metadata
                event_data = {
                    'event_type': event_type,
                    'payload': data,
                    'timestamp': timezone.now().isoformat(),
                    'bridge_type': BridgeType.EVENT_BUS
                }
                
                # Add to history
                self._add_to_history(event_data)
                
                # Notify subscribers
                notified_count = self._notify_subscribers(event_type, event_data)
                
                # Persist if enabled
                if self.enable_persistence:
                    self._persist_event(event_data)
                
                self.logger.info(f"Event {event_type} sent to {notified_count} subscribers")
                return True
                
        except Exception as e:
            self.logger.error(f"Error sending event: {str(e)}")
            return False
    
    def receive(self, source: str = None) -> Optional[Dict[str, Any]]:
        """
        Receive event from the event bus.
        
        Args:
            source: Optional source (event type)
            
        Returns:
            Received event or None
        """
        try:
            # Get recent events
            if source:
                events = [e for e in self.event_history if e['event_type'] == source]
            else:
                events = self.event_history
            
            if not events:
                return None
            
            # Return most recent event
            return events[-1]
            
        except Exception as e:
            self.logger.error(f"Error receiving event: {str(e)}")
            return None
    
    def subscribe(self, event_type: str, callback: Callable) -> bool:
        """
        Subscribe to event type.
        
        Args:
            event_type: Event type to subscribe to
            callback: Callback function
            
        Returns:
            True if subscription successful
        """
        try:
            # Check subscriber limit
            if len(self.subscribers) >= self.max_subscribers:
                raise BridgeError(f"Maximum subscribers limit reached: {self.max_subscribers}")
            
            # Add subscriber
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
            
            self.subscribers[event_type].append({
                'callback': callback,
                'subscribed_at': timezone.now()
            })
            
            self.logger.info(f"Subscribed to event type: {event_type}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error subscribing to {event_type}: {str(e)}")
            return False
    
    def unsubscribe(self, event_type: str, callback: Callable) -> bool:
        """
        Unsubscribe from event type.
        
        Args:
            event_type: Event type to unsubscribe from
            callback: Callback function
            
        Returns:
            True if unsubscription successful
        """
        try:
            if event_type in self.subscribers:
                self.subscribers[event_type] = [
                    sub for sub in self.subscribers[event_type]
                    if sub['callback'] != callback
                ]
                
                # Remove empty subscription lists
                if not self.subscribers[event_type]:
                    del self.subscribers[event_type]
                
                self.logger.info(f"Unsubscribed from event type: {event_type}")
                return True
            else:
                self.logger.warning(f"No subscribers for event type: {event_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error unsubscribing from {event_type}: {str(e)}")
            return False
    
    def get_subscribers(self, event_type: str = None) -> Dict[str, Any]:
        """
        Get subscriber information.
        
        Args:
            event_type: Optional event type filter
            
        Returns:
            Subscriber information
        """
        try:
            if event_type:
                if event_type in self.subscribers:
                    return {
                        'event_type': event_type,
                        'subscriber_count': len(self.subscribers[event_type]),
                        'subscribers': [
                            {
                                'subscribed_at': sub['subscribed_at'].isoformat()
                            }
                            for sub in self.subscribers[event_type]
                        ]
                    }
                else:
                    return {'error': f'No subscribers for event type: {event_type}'}
            else:
                return {
                    'total_events': len(self.subscribers),
                    'events': {
                        event_type: {
                            'subscriber_count': len(subscribers)
                        }
                        for event_type, subscribers in self.subscribers.items()
                    }
                }
                
        except Exception as e:
            self.logger.error(f"Error getting subscribers: {str(e)}")
            return {'error': str(e)}
    
    def _validate_event_data(self, data: Dict[str, Any]) -> bool:
        """Validate event data."""
        try:
            if not isinstance(data, dict):
                return False
            
            # Basic validation
            if not data:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating event data: {str(e)}")
            return False
    
    def _add_to_history(self, event_data: Dict[str, Any]):
        """Add event to history."""
        try:
            self.event_history.append(event_data)
            
            # Limit history size
            if len(self.event_history) > self.max_history:
                self.event_history = self.event_history[-self.max_history:]
                
        except Exception as e:
            self.logger.error(f"Error adding to history: {str(e)}")
    
    def _notify_subscribers(self, event_type: str, event_data: Dict[str, Any]) -> int:
        """Notify subscribers of event."""
        try:
            notified_count = 0
            
            if event_type in self.subscribers:
                for subscriber in self.subscribers[event_type]:
                    try:
                        callback = subscriber['callback']
                        callback(event_data)
                        notified_count += 1
                    except Exception as e:
                        self.logger.error(f"Error notifying subscriber: {str(e)}")
                        continue
            
            return notified_count
            
        except Exception as e:
            self.logger.error(f"Error notifying subscribers: {str(e)}")
            return 0
    
    def _persist_event(self, event_data: Dict[str, Any]):
        """Persist event to storage."""
        try:
            # This would integrate with your persistence layer
            # For now, just log the event
            self.logger.debug(f"Persisting event: {event_data['event_type']}")
            
        except Exception as e:
            self.logger.error(f"Error persisting event: {str(e)}")
    
    def get_bridge_info(self) -> Dict[str, Any]:
        """
        Get event bus bridge information.
        
        Returns:
            Bridge information
        """
        return {
            'type': BridgeType.EVENT_BUS,
            'name': 'EventBusBridge',
            'description': 'Bridge for event bus integration',
            'version': '1.0.0',
            'supported_event_types': list(self.subscribers.keys()),
            'total_subscribers': sum(len(subs) for subs in self.subscribers.values()),
            'event_history_size': len(self.event_history),
            'max_history': self.max_history,
            'enabled': self.enabled,
            'config': self.config
        }


class MessageQueueBridge(BaseBridge):
    """
    Message queue bridge for integration system.
    Handles message queuing and processing.
    """
    
    def _initialize_bridge(self):
        """Initialize the message queue bridge."""
        try:
            self.queue_type = self.config.get('queue_type', QueueType.REDIS)
            self.queue_name = self.config.get('queue_name', 'webhook_queue')
            self.max_queue_size = self.config.get('max_queue_size', 10000)
            
            # Initialize queue
            self._initialize_queue()
            
            self.logger.info("Message queue bridge initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing message queue bridge: {str(e)}")
            raise
    
    def _initialize_queue(self):
        """Initialize the message queue."""
        try:
            if self.queue_type == QueueType.REDIS:
                self._initialize_redis_queue()
            elif self.queue_type == QueueType.RABBITMQ:
                self._initialize_rabbitmq_queue()
            elif self.queue_type == QueueType.KAFKA:
                self._initialize_kafka_queue()
            else:
                raise BridgeError(f"Unsupported queue type: {self.queue_type}")
                
        except Exception as e:
            self.logger.error(f"Error initializing queue: {str(e)}")
            raise
    
    def _initialize_redis_queue(self):
        """Initialize Redis queue."""
        try:
            import redis
            
            redis_config = self.config.get('redis', {})
            self.redis_client = redis.Redis(
                host=redis_config.get('host', 'localhost'),
                port=redis_config.get('port', 6379),
                db=redis_config.get('db', 0),
                password=redis_config.get('password'),
                decode_responses=True
            )
            
            # Test connection
            self.redis_client.ping()
            
        except Exception as e:
            self.logger.error(f"Error initializing Redis queue: {str(e)}")
            raise
    
    def _initialize_rabbitmq_queue(self):
        """Initialize RabbitMQ queue."""
        try:
            import pika
            
            rabbitmq_config = self.config.get('rabbitmq', {})
            credentials = pika.PlainCredentials(
                rabbitmq_config.get('username', 'guest'),
                rabbitmq_config.get('password', 'guest')
            )
            
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=rabbitmq_config.get('host', 'localhost'),
                    port=rabbitmq_config.get('port', 5672),
                    virtual_host=rabbitmq_config.get('virtual_host', '/'),
                    credentials=credentials
                )
            )
            
            self.rabbitmq_connection = connection
            self.rabbitmq_channel = connection.channel()
            
            # Declare queue
            self.rabbitmq_channel.queue_declare(
                queue=self.queue_name,
                durable=True
            )
            
        except Exception as e:
            self.logger.error(f"Error initializing RabbitMQ queue: {str(e)}")
            raise
    
    def _initialize_kafka_queue(self):
        """Initialize Kafka queue."""
        try:
            from kafka import KafkaProducer, KafkaConsumer
            
            kafka_config = self.config.get('kafka', {})
            
            self.kafka_producer = KafkaProducer(
                bootstrap_servers=kafka_config.get('bootstrap_servers', ['localhost:9092']),
                value_serializer=lambda v: str(v).encode('utf-8')
            )
            
            self.kafka_consumer = KafkaConsumer(
                self.queue_name,
                bootstrap_servers=kafka_config.get('bootstrap_servers', ['localhost:9092']),
                value_deserializer=lambda v: v.decode('utf-8')
            )
            
        except Exception as e:
            self.logger.error(f"Error initializing Kafka queue: {str(e)}")
            raise
    
    def send(self, data: Dict[str, Any], destination: str = None) -> bool:
        """
        Send message to queue.
        
        Args:
            data: Message data
            destination: Optional destination (queue name)
            
        Returns:
            True if send successful
        """
        try:
            with self.monitor.measure_bridge('message_queue') as measurement:
                # Validate message data
                if not self._validate_message_data(data):
                    raise BridgeError("Invalid message data")
                
                # Prepare message
                message = {
                    'payload': data,
                    'timestamp': timezone.now().isoformat(),
                    'bridge_type': BridgeType.MESSAGE_QUEUE,
                    'queue_type': self.queue_type
                }
                
                # Send to appropriate queue
                if self.queue_type == QueueType.REDIS:
                    return self._send_to_redis(message, destination)
                elif self.queue_type == QueueType.RABBITMQ:
                    return self._send_to_rabbitmq(message, destination)
                elif self.queue_type == QueueType.KAFKA:
                    return self._send_to_kafka(message, destination)
                else:
                    raise BridgeError(f"Unsupported queue type: {self.queue_type}")
                
        except Exception as e:
            self.logger.error(f"Error sending message: {str(e)}")
            return False
    
    def receive(self, source: str = None) -> Optional[Dict[str, Any]]:
        """
        Receive message from queue.
        
        Args:
            source: Optional source (queue name)
            
        Returns:
            Received message or None
        """
        try:
            # Receive from appropriate queue
            if self.queue_type == QueueType.REDIS:
                return self._receive_from_redis(source)
            elif self.queue_type == QueueType.RABBITMQ:
                return self._receive_from_rabbitmq(source)
            elif self.queue_type == QueueType.KAFKA:
                return self._receive_from_kafka(source)
            else:
                raise BridgeError(f"Unsupported queue type: {self.queue_type}")
                
        except Exception as e:
            self.logger.error(f"Error receiving message: {str(e)}")
            return None
    
    def _validate_message_data(self, data: Dict[str, Any]) -> bool:
        """Validate message data."""
        try:
            if not isinstance(data, dict):
                return False
            
            # Basic validation
            if not data:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating message data: {str(e)}")
            return False
    
    def _send_to_redis(self, message: Dict[str, Any], destination: str = None) -> bool:
        """Send message to Redis queue."""
        try:
            import json
            
            queue_name = destination or self.queue_name
            message_json = json.dumps(message)
            
            # Check queue size
            queue_size = self.redis_client.llen(queue_name)
            if queue_size >= self.max_queue_size:
                raise BridgeError(f"Queue size limit reached: {self.max_queue_size}")
            
            # Push to queue
            self.redis_client.lpush(queue_name, message_json)
            
            self.logger.info(f"Message sent to Redis queue: {queue_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending to Redis: {str(e)}")
            return False
    
    def _send_to_rabbitmq(self, message: Dict[str, Any], destination: str = None) -> bool:
        """Send message to RabbitMQ queue."""
        try:
            import json
            
            queue_name = destination or self.queue_name
            message_json = json.dumps(message)
            
            # Publish to queue
            self.rabbitmq_channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                body=message_json,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                )
            )
            
            self.logger.info(f"Message sent to RabbitMQ queue: {queue_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending to RabbitMQ: {str(e)}")
            return False
    
    def _send_to_kafka(self, message: Dict[str, Any], destination: str = None) -> bool:
        """Send message to Kafka queue."""
        try:
            import json
            
            topic = destination or self.queue_name
            message_json = json.dumps(message)
            
            # Send to Kafka
            self.kafka_producer.send(topic, message_json)
            self.kafka_producer.flush()
            
            self.logger.info(f"Message sent to Kafka topic: {topic}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending to Kafka: {str(e)}")
            return False
    
    def _receive_from_redis(self, source: str = None) -> Optional[Dict[str, Any]]:
        """Receive message from Redis queue."""
        try:
            import json
            
            queue_name = source or self.queue_name
            
            # Pop from queue
            message_json = self.redis_client.rpop(queue_name)
            
            if message_json:
                return json.loads(message_json)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error receiving from Redis: {str(e)}")
            return None
    
    def _receive_from_rabbitmq(self, source: str = None) -> Optional[Dict[str, Any]]:
        """Receive message from RabbitMQ queue."""
        try:
            import json
            
            queue_name = source or self.queue_name
            
            # Consume message
            method_frame, header_frame, body = self.rabbitmq_channel.basic_get(queue=queue_name)
            
            if method_frame:
                message_json = body.decode('utf-8')
                self.rabbitmq_channel.basic_ack(method_frame.delivery_tag)
                return json.loads(message_json)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error receiving from RabbitMQ: {str(e)}")
            return None
    
    def _receive_from_kafka(self, source: str = None) -> Optional[Dict[str, Any]]:
        """Receive message from Kafka queue."""
        try:
            import json
            
            topic = source or self.queue_name
            
            # Poll for message
            message = next(self.kafka_consumer)
            
            if message:
                return json.loads(message.value)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error receiving from Kafka: {str(e)}")
            return None
    
    def get_bridge_info(self) -> Dict[str, Any]:
        """
        Get message queue bridge information.
        
        Returns:
            Bridge information
        """
        return {
            'type': BridgeType.MESSAGE_QUEUE,
            'name': 'MessageQueueBridge',
            'description': 'Bridge for message queue integration',
            'version': '1.0.0',
            'queue_type': self.queue_type,
            'queue_name': self.queue_name,
            'max_queue_size': self.max_queue_size,
            'enabled': self.enabled,
            'config': self.config
        }


class BridgeManager:
    """
    Main bridge manager for integration system.
    Coordinates multiple bridges and provides unified interface.
    """
    
    def __init__(self):
        """Initialize the bridge manager."""
        self.logger = logger
        self.bridges = {}
        self.monitor = PerformanceMonitor()
        
        # Load configuration
        self._load_configuration()
        
        # Initialize bridges
        self._initialize_bridges()
    
    def _load_configuration(self):
        """Load bridge configuration from settings."""
        try:
            self.config = getattr(settings, 'WEBHOOK_BRIDGE_CONFIG', {})
            self.enabled_bridges = self.config.get('enabled_bridges', ['event_bus', 'message_queue'])
            
            self.logger.info("Bridge configuration loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading bridge configuration: {str(e)}")
            self.config = {}
            self.enabled_bridges = ['event_bus', 'message_queue']
    
    def _initialize_bridges(self):
        """Initialize enabled bridges."""
        try:
            # Initialize event bus bridge
            if 'event_bus' in self.enabled_bridges:
                event_bus_config = self.config.get('event_bus', {})
                self.bridges['event_bus'] = EventBusBridge(event_bus_config)
            
            # Initialize message queue bridge
            if 'message_queue' in self.enabled_bridges:
                message_queue_config = self.config.get('message_queue', {})
                self.bridges['message_queue'] = MessageQueueBridge(message_queue_config)
            
            self.logger.info(f"Initialized {len(self.bridges)} bridges")
            
        except Exception as e:
            self.logger.error(f"Error initializing bridges: {str(e)}")
    
    def send(self, bridge_type: str, data: Dict[str, Any], destination: str = None) -> bool:
        """
        Send data through specified bridge.
        
        Args:
            bridge_type: Type of bridge to use
            data: Data to send
            destination: Optional destination
            
        Returns:
            True if send successful
        """
        try:
            if bridge_type not in self.bridges:
                raise BridgeError(f"Bridge {bridge_type} not found")
            
            bridge = self.bridges[bridge_type]
            return bridge.send(data, destination)
            
        except Exception as e:
            self.logger.error(f"Error sending data through {bridge_type}: {str(e)}")
            return False
    
    def receive(self, bridge_type: str, source: str = None) -> Optional[Dict[str, Any]]:
        """
        Receive data from specified bridge.
        
        Args:
            bridge_type: Type of bridge to use
            source: Optional source
            
        Returns:
            Received data or None
        """
        try:
            if bridge_type not in self.bridges:
                raise BridgeError(f"Bridge {bridge_type} not found")
            
            bridge = self.bridges[bridge_type]
            return bridge.receive(source)
            
        except Exception as e:
            self.logger.error(f"Error receiving data from {bridge_type}: {str(e)}")
            return None
    
    def get_bridge_status(self, bridge_type: str = None) -> Dict[str, Any]:
        """
        Get bridge status.
        
        Args:
            bridge_type: Optional specific bridge type
            
        Returns:
            Bridge status information
        """
        try:
            if bridge_type:
                if bridge_type in self.bridges:
                    return self.bridges[bridge_type].health_check()
                else:
                    return {'error': f'Bridge {bridge_type} not found'}
            else:
                return {
                    'total_bridges': len(self.bridges),
                    'enabled_bridges': self.enabled_bridges,
                    'bridges': {
                        name: bridge.health_check()
                        for name, bridge in self.bridges.items()
                    }
                }
                
        except Exception as e:
            self.logger.error(f"Error getting bridge status: {str(e)}")
            return {'error': str(e)}
    
    def register_bridge(self, bridge_type: str, bridge: BaseBridge) -> bool:
        """
        Register a custom bridge.
        
        Args:
            bridge_type: Type of bridge
            bridge: Bridge instance
            
        Returns:
            True if registration successful
        """
        try:
            if not isinstance(bridge, BaseBridge):
                raise BridgeError("Bridge must inherit from BaseBridge")
            
            self.bridges[bridge_type] = bridge
            self.logger.info(f"Bridge {bridge_type} registered successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error registering bridge {bridge_type}: {str(e)}")
            return False
    
    def unregister_bridge(self, bridge_type: str) -> bool:
        """
        Unregister a bridge.
        
        Args:
            bridge_type: Type of bridge to unregister
            
        Returns:
            True if unregistration successful
        """
        try:
            if bridge_type in self.bridges:
                del self.bridges[bridge_type]
                self.logger.info(f"Bridge {bridge_type} unregistered successfully")
                return True
            else:
                self.logger.warning(f"Bridge {bridge_type} not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error unregistering bridge {bridge_type}: {str(e)}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of bridge system.
        
        Returns:
            Health check results
        """
        try:
            health_status = {
                'overall': HealthStatus.HEALTHY,
                'components': {},
                'checks': []
            }
            
            # Check bridges
            for bridge_type, bridge in self.bridges.items():
                bridge_health = bridge.health_check()
                health_status['components'][bridge_type] = bridge_health
                
                if bridge_health['status'] != HealthStatus.HEALTHY:
                    health_status['overall'] = HealthStatus.UNHEALTHY
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Error performing health check: {str(e)}")
            return {
                'overall': HealthStatus.UNHEALTHY,
                'error': str(e)
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get bridge system status.
        
        Returns:
            System status
        """
        try:
            return {
                'bridge_manager': {
                    'status': 'running',
                    'total_bridges': len(self.bridges),
                    'enabled_bridges': self.enabled_bridges,
                    'uptime': self.monitor.get_uptime(),
                    'performance_metrics': self.monitor.get_system_metrics()
                },
                'bridges': {
                    name: bridge.get_bridge_info()
                    for name, bridge in self.bridges.items()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting bridge status: {str(e)}")
            return {'error': str(e)}
