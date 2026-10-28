"""
Integration Adapter
Base adapter and specific implementations for different system integrations
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import json
import asyncio

from .integ_exceptions import IntegrationException, AdapterException
from .integ_constants import AdapterTypes, DataFormats, ProtocolTypes
from .integ_signals import emit_pre_integration_signal, emit_post_integration_signal

logger = logging.getLogger(__name__)


class AdapterStatus(Enum):
    """Adapter status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    MAINTENANCE = "maintenance"


@dataclass
class AdapterConfig:
    """Adapter configuration"""
    adapter_type: AdapterTypes
    system_name: str
    endpoint: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None
    timeout: float = 30.0
    retry_count: int = 3
    retry_delay: float = 1.0
    data_format: DataFormats = DataFormats.JSON
    protocol: ProtocolTypes = ProtocolTypes.HTTP
    custom_settings: Optional[Dict[str, Any]] = None


@dataclass
class AdapterMetrics:
    """Adapter performance metrics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    last_request_time: Optional[datetime] = None
    error_rate: float = 0.0


class BaseIntegrationAdapter(ABC):
    """
    Abstract base class for integration adapters
    """
    
    def __init__(self, config: AdapterConfig):
        self.config = config
        self.system_name = config.system_name
        self.adapter_type = config.adapter_type
        self.status = AdapterStatus.INACTIVE
        self.metrics = AdapterMetrics()
        self.connection_pool = None
        self._last_health_check = None
        self._health_check_interval = 300  # 5 minutes
        
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the target system
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Close connection to the target system"""
        pass
    
    @abstractmethod
    async def send_data(self, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Send data to the target system
        
        Args:
            data: Data to send
            **kwargs: Additional parameters
            
        Returns:
            Response from the target system
        """
        pass
    
    @abstractmethod
    async def receive_data(self, **kwargs) -> Dict[str, Any]:
        """
        Receive data from the target system
        
        Args:
            **kwargs: Additional parameters
            
        Returns:
            Data received from the target system
        """
        pass
    
    @abstractmethod
    async def validate_connection(self) -> bool:
        """
        Validate connection to the target system
        
        Returns:
            True if connection is valid, False otherwise
        """
        pass
    
    async def initialize(self):
        """Initialize the adapter"""
        try:
            if await self.connect():
                self.status = AdapterStatus.ACTIVE
                logger.info(f"Adapter {self.system_name} initialized successfully")
                return True
            else:
                self.status = AdapterStatus.ERROR
                logger.error(f"Failed to initialize adapter {self.system_name}")
                return False
        except Exception as e:
            self.status = AdapterStatus.ERROR
            logger.error(f"Error initializing adapter {self.system_name}: {e}")
            raise AdapterException(f"Failed to initialize adapter: {e}")
    
    async def shutdown(self):
        """Shutdown the adapter"""
        try:
            await self.disconnect()
            self.status = AdapterStatus.INACTIVE
            logger.info(f"Adapter {self.system_name} shutdown successfully")
        except Exception as e:
            logger.error(f"Error shutting down adapter {self.system_name}: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the adapter
        
        Returns:
            Health check results
        """
        now = datetime.utcnow()
        
        # Check if we need to perform health check
        if (self._last_health_check and 
            (now - self._last_health_check).total_seconds() < self._health_check_interval):
            return {
                'status': self.status.value,
                'healthy': self.status == AdapterStatus.ACTIVE,
                'last_check': self._last_health_check.isoformat(),
                'cached': True
            }
        
        try:
            is_healthy = await self.validate_connection()
            self._last_health_check = now
            
            if is_healthy and self.status == AdapterStatus.ERROR:
                self.status = AdapterStatus.ACTIVE
            elif not is_healthy and self.status == AdapterStatus.ACTIVE:
                self.status = AdapterStatus.ERROR
            
            return {
                'status': self.status.value,
                'healthy': is_healthy,
                'last_check': now.isoformat(),
                'cached': False,
                'metrics': self.get_metrics()
            }
            
        except Exception as e:
            self.status = AdapterStatus.ERROR
            logger.error(f"Health check failed for adapter {self.system_name}: {e}")
            return {
                'status': self.status.value,
                'healthy': False,
                'last_check': now.isoformat(),
                'cached': False,
                'error': str(e)
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get adapter metrics
        
        Returns:
            Adapter metrics
        """
        total = self.metrics.total_requests
        if total > 0:
            self.metrics.error_rate = (self.metrics.failed_requests / total) * 100
        
        return {
            'total_requests': self.metrics.total_requests,
            'successful_requests': self.metrics.successful_requests,
            'failed_requests': self.metrics.failed_requests,
            'success_rate': ((self.metrics.successful_requests / total) * 100) if total > 0 else 0,
            'error_rate': self.metrics.error_rate,
            'average_response_time': self.metrics.average_response_time,
            'last_request_time': self.metrics.last_request_time.isoformat() if self.metrics.last_request_time else None
        }
    
    def _update_metrics(self, success: bool, response_time: float):
        """Update adapter metrics"""
        self.metrics.total_requests += 1
        self.metrics.last_request_time = datetime.utcnow()
        
        if success:
            self.metrics.successful_requests += 1
        else:
            self.metrics.failed_requests += 1
        
        # Update average response time
        total = self.metrics.total_requests
        current_avg = self.metrics.average_response_time
        self.metrics.average_response_time = ((current_avg * (total - 1)) + response_time) / total


class HTTPAdapter(BaseIntegrationAdapter):
    """
    HTTP-based integration adapter
    """
    
    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self.session = None
        self.base_url = config.endpoint
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    async def connect(self) -> bool:
        """Establish HTTP connection"""
        try:
            import aiohttp
            
            # Create session with timeout
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self.headers
            )
            
            # Test connection
            async with self.session.get(f"{self.base_url}/health") as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Failed to connect HTTP adapter {self.system_name}: {e}")
            return False
    
    async def disconnect(self):
        """Close HTTP connection"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def send_data(self, data: Dict[str, Any], endpoint: str = None, **kwargs) -> Dict[str, Any]:
        """Send data via HTTP POST"""
        if not self.session:
            raise AdapterException("HTTP session not established")
        
        start_time = datetime.utcnow()
        url = endpoint or f"{self.base_url}/api/data"
        
        try:
            # Emit pre-integration signal
            emit_pre_integration_signal(
                source_system="integration_system",
                target_system=self.system_name,
                request_id=kwargs.get('request_id', 'unknown'),
                data=data
            )
            
            async with self.session.post(url, json=data) as response:
                response_data = await response.json()
                
                success = response.status < 400
                response_time = (datetime.utcnow() - start_time).total_seconds()
                
                self._update_metrics(success, response_time)
                
                if not success:
                    raise AdapterException(f"HTTP request failed with status {response.status}")
                
                # Emit post-integration signal
                emit_post_integration_signal(
                    source_system="integration_system",
                    target_system=self.system_name,
                    request_id=kwargs.get('request_id', 'unknown'),
                    data=response_data
                )
                
                return response_data
                
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_metrics(False, response_time)
            raise AdapterException(f"Failed to send data via HTTP: {e}")
    
    async def receive_data(self, endpoint: str = None, **kwargs) -> Dict[str, Any]:
        """Receive data via HTTP GET"""
        if not self.session:
            raise AdapterException("HTTP session not established")
        
        start_time = datetime.utcnow()
        url = endpoint or f"{self.base_url}/api/data"
        
        try:
            async with self.session.get(url) as response:
                response_data = await response.json()
                
                success = response.status < 400
                response_time = (datetime.utcnow() - start_time).total_seconds()
                
                self._update_metrics(success, response_time)
                
                if not success:
                    raise AdapterException(f"HTTP request failed with status {response.status}")
                
                return response_data
                
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_metrics(False, response_time)
            raise AdapterException(f"Failed to receive data via HTTP: {e}")
    
    async def validate_connection(self) -> bool:
        """Validate HTTP connection"""
        if not self.session:
            return False
        
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                return response.status == 200
        except:
            return False


class DatabaseAdapter(BaseIntegrationAdapter):
    """
    Database-based integration adapter
    """
    
    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self.connection = None
        self.db_config = config.custom_settings or {}
    
    async def connect(self) -> bool:
        """Establish database connection"""
        try:
            import asyncpg  # PostgreSQL async driver
            
            self.connection = await asyncpg.connect(
                host=self.db_config.get('host', 'localhost'),
                port=self.db_config.get('port', 5432),
                database=self.db_config.get('database'),
                user=self.db_config.get('user'),
                password=self.db_config.get('password'),
                timeout=self.config.timeout
            )
            
            # Test connection
            await self.connection.fetchval("SELECT 1")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect database adapter {self.system_name}: {e}")
            return False
    
    async def disconnect(self):
        """Close database connection"""
        if self.connection:
            await self.connection.close()
            self.connection = None
    
    async def send_data(self, data: Dict[str, Any], table: str = None, **kwargs) -> Dict[str, Any]:
        """Send data to database (INSERT/UPDATE)"""
        if not self.connection:
            raise AdapterException("Database connection not established")
        
        start_time = datetime.utcnow()
        table_name = table or self.db_config.get('default_table', 'integration_data')
        
        try:
            # Convert data to SQL
            columns = list(data.keys())
            values = list(data.values())
            
            # Build INSERT query
            query = f"""
                INSERT INTO {table_name} ({', '.join(columns)})
                VALUES ({', '.join([f'${i+1}' for i in range(len(values))])})
                RETURNING id
            """
            
            result = await self.connection.fetchval(query, *values)
            
            success = True
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            self._update_metrics(success, response_time)
            
            return {'id': result, 'status': 'success'}
            
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_metrics(False, response_time)
            raise AdapterException(f"Failed to send data to database: {e}")
    
    async def receive_data(self, query: str = None, table: str = None, **kwargs) -> Dict[str, Any]:
        """Receive data from database (SELECT)"""
        if not self.connection:
            raise AdapterException("Database connection not established")
        
        start_time = datetime.utcnow()
        
        try:
            if query:
                # Use custom query
                results = await self.connection.fetch(query)
            else:
                # Use default table query
                table_name = table or self.db_config.get('default_table', 'integration_data')
                query = f"SELECT * FROM {table_name} LIMIT 100"
                results = await self.connection.fetch(query)
            
            # Convert to list of dicts
            data = [dict(row) for row in results]
            
            success = True
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            self._update_metrics(success, response_time)
            
            return {'data': data, 'count': len(data)}
            
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_metrics(False, response_time)
            raise AdapterException(f"Failed to receive data from database: {e}")
    
    async def validate_connection(self) -> bool:
        """Validate database connection"""
        if not self.connection:
            return False
        
        try:
            await self.connection.fetchval("SELECT 1")
            return True
        except:
            return False


class MessageQueueAdapter(BaseIntegrationAdapter):
    """
    Message queue-based integration adapter
    """
    
    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self.connection = None
        self.channel = None
        self.mq_config = config.custom_settings or {}
    
    async def connect(self) -> bool:
        """Establish message queue connection"""
        try:
            import aio_pika
            
            connection_params = aio_pika.URLParameters(
                host=self.mq_config.get('host', 'localhost'),
                port=self.mq_config.get('port', 5672),
                virtual_host=self.mq_config.get('virtual_host', '/'),
                credentials=aio_pika.PlainCredentials(
                    self.mq_config.get('user', 'guest'),
                    self.mq_config.get('password', 'guest')
                )
            )
            
            self.connection = await aio_pika.connect_robust(connection_params)
            self.channel = await self.connection.channel()
            
            # Test connection
            await self.channel.queue_declare(queue='test', durable=True)
            await self.channel.queue_delete(queue='test')
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect message queue adapter {self.system_name}: {e}")
            return False
    
    async def disconnect(self):
        """Close message queue connection"""
        if self.connection:
            await self.connection.close()
            self.connection = None
            self.channel = None
    
    async def send_data(self, data: Dict[str, Any], queue: str = None, **kwargs) -> Dict[str, Any]:
        """Send data to message queue"""
        if not self.channel:
            raise AdapterException("Message queue channel not established")
        
        start_time = datetime.utcnow()
        queue_name = queue or self.mq_config.get('default_queue', 'integration_queue')
        
        try:
            # Declare queue
            await self.channel.queue_declare(queue=queue_name, durable=True)
            
            # Publish message
            message = aio_pika.Message(
                json.dumps(data).encode('utf-8'),
                delivery_mode=2,  # Make message persistent
                content_type='application/json'
            )
            
            await self.channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                body=message
            )
            
            success = True
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            self._update_metrics(success, response_time)
            
            return {'status': 'sent', 'queue': queue_name}
            
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_metrics(False, response_time)
            raise AdapterException(f"Failed to send data to message queue: {e}")
    
    async def receive_data(self, queue: str = None, **kwargs) -> Dict[str, Any]:
        """Receive data from message queue"""
        if not self.channel:
            raise AdapterException("Message queue channel not established")
        
        start_time = datetime.utcnow()
        queue_name = queue or self.mq_config.get('default_queue', 'integration_queue')
        
        try:
            # Declare queue
            await self.channel.queue_declare(queue=queue_name, durable=True)
            
            # Get message
            method_frame, header_frame, body = await self.channel.basic_get(queue=queue_name)
            
            if method_frame:
                # Acknowledge message
                await self.channel.basic_ack(method_frame.delivery_tag)
                
                # Parse message
                data = json.loads(body.decode('utf-8'))
                
                success = True
                response_time = (datetime.utcnow() - start_time).total_seconds()
                
                self._update_metrics(success, response_time)
                
                return {'data': data, 'delivery_tag': method_frame.delivery_tag}
            else:
                return {'data': None, 'message': 'No messages available'}
                
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_metrics(False, response_time)
            raise AdapterException(f"Failed to receive data from message queue: {e}")
    
    async def validate_connection(self) -> bool:
        """Validate message queue connection"""
        if not self.connection or not self.channel:
            return False
        
        try:
            # Test with a temporary queue
            await self.channel.queue_declare(queue='test', durable=True)
            await self.channel.queue_delete(queue='test')
            return True
        except:
            return False


class AdapterFactory:
    """
    Factory for creating integration adapters
    """
    
    @staticmethod
    def create_adapter(config: AdapterConfig) -> BaseIntegrationAdapter:
        """
        Create an adapter based on configuration
        
        Args:
            config: Adapter configuration
            
        Returns:
            Integration adapter instance
        """
        adapter_mapping = {
            AdapterTypes.HTTP: HTTPAdapter,
            AdapterTypes.DATABASE: DatabaseAdapter,
            AdapterTypes.MESSAGE_QUEUE: MessageQueueAdapter,
        }
        
        adapter_class = adapter_mapping.get(config.adapter_type)
        if not adapter_class:
            raise AdapterException(f"Unsupported adapter type: {config.adapter_type}")
        
        return adapter_class(config)


# Export main classes and functions
__all__ = [
    'BaseIntegrationAdapter',
    'HTTPAdapter',
    'DatabaseAdapter',
    'MessageQueueAdapter',
    'AdapterFactory',
    'AdapterConfig',
    'AdapterMetrics',
    'AdapterStatus',
]
