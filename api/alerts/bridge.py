"""
Bridge for alerts app - Data bridge between different systems and formats
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable, Union
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
import logging
from .sql_utils import safe_identifier
import time
import asyncio
import json

logger = logging.getLogger(__name__)


class DataBridge(ABC):
    """Abstract base class for data bridges"""
    
    def __init__(self, source_config: Dict[str, Any], target_config: Dict[str, Any]):
        self.source_config = source_config
        self.target_config = target_config
        self.name = self.__class__.__name__
        self.enabled = True
        self.transformation_pipeline = []
        self.validation_pipeline = []
        
    @abstractmethod
    def connect_source(self) -> bool:
        """Connect to source system"""
        pass
    
    @abstractmethod
    def connect_target(self) -> bool:
        """Connect to target system"""
        pass
    
    @abstractmethod
    def transfer_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Transfer data from source to target"""
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check bridge health"""
        pass
    
    def add_transformation(self, transformation_func: Callable):
        """Add transformation to pipeline"""
        self.transformation_pipeline.append(transformation_func)
    
    def add_validation(self, validation_func: Callable):
        """Add validation to pipeline"""
        self.validation_pipeline.append(validation_func)
    
    def apply_transformations(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply transformation pipeline to data"""
        transformed_data = data
        
        for transformation in self.transformation_pipeline:
            try:
                transformed_data = transformation(transformed_data)
            except Exception as e:
                logger.error(f"Transformation error in {self.name}: {e}")
                return []
        
        return transformed_data
    
    def apply_validations(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply validation pipeline to data"""
        for validation in self.validation_pipeline:
            try:
                result = validation(data)
                if not result.get('valid', False):
                    return result
            except Exception as e:
                logger.error(f"Validation error in {self.name}: {e}")
                return {'valid': False, 'error': 'Operation failed'}
        
        return {'valid': True, 'errors': []}


class AlertBridge(DataBridge):
    """Bridge for alert data between systems"""
    
    def __init__(self, source_config: Dict[str, Any], target_config: Dict[str, Any]):
        super().__init__(source_config, target_config)
        self.batch_size = source_config.get('batch_size', 100)
        self.retry_count = source_config.get('retry_count', 3)
        self.retry_delay = source_config.get('retry_delay', 60)
        self.field_mappings = source_config.get('field_mappings', {})
        
    def connect_source(self) -> bool:
        """Connect to alert source"""
        try:
            source_type = self.source_config.get('type', 'database')
            
            if source_type == 'database':
                return self._connect_database_source()
            elif source_type == 'api':
                return self._connect_api_source()
            elif source_type == 'file':
                return self._connect_file_source()
            else:
                logger.error(f"Unsupported source type: {source_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to source: {e}")
            return False
    
    def connect_target(self) -> bool:
        """Connect to alert target"""
        try:
            target_type = self.target_config.get('type', 'database')
            
            if target_type == 'database':
                return self._connect_database_target()
            elif target_type == 'api':
                return self._connect_api_target()
            elif target_type == 'webhook':
                return self._connect_webhook_target()
            else:
                logger.error(f"Unsupported target type: {target_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to target: {e}")
            return False
    
    def transfer_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Transfer alert data from source to target"""
        try:
            # Apply transformations
            transformed_data = self.apply_transformations(data)
            
            # Apply validations
            validation_result = self.apply_validations(transformed_data)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': 'Validation failed',
                    'errors': validation_result['errors']
                }
            
            # Apply field mappings
            mapped_data = self._apply_field_mappings(transformed_data)
            
            # Transfer in batches
            total_transferred = 0
            total_failed = 0
            
            for i in range(0, len(mapped_data), self.batch_size):
                batch = mapped_data[i:i + self.batch_size]
                
                for attempt in range(self.retry_count):
                    result = self._transfer_batch(batch)
                    
                    if result['success']:
                        total_transferred += len(batch)
                        break
                    else:
                        if attempt == self.retry_count - 1:
                            total_failed += len(batch)
                            logger.error(f"Batch transfer failed after {self.retry_count} attempts")
                        else:
                            time.sleep(self.retry_delay)
            
            return {
                'success': total_failed == 0,
                'total_transferred': total_transferred,
                'total_failed': total_failed,
                'total_processed': len(data)
            }
            
        except Exception as e:
            logger.error(f"Error transferring data: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }
    
    def health_check(self) -> Dict[str, Any]:
        """Check bridge health"""
        try:
            source_healthy = self._check_source_health()
            target_healthy = self._check_target_health()
            
            return {
                'healthy': source_healthy and target_healthy,
                'source_healthy': source_healthy,
                'target_healthy': target_healthy,
                'last_check': timezone.now().isoformat(),
                'bridge_name': self.name
            }
            
        except Exception:
            logger.exception("Unhandled error in health_check")
            return {
                'healthy': False,
                'error': 'Operation failed',
                'last_check': timezone.now().isoformat()
            }
    
    def _connect_database_source(self) -> bool:
        """Connect to database source"""
        try:
            if self.source_config.get('database_type') == 'postgresql':
                import psycopg2
                self.source_connection = psycopg2.connect(
                    self.source_config['connection_string']
                )
            elif self.source_config.get('database_type') == 'mysql':
                import mysql.connector
                self.source_connection = mysql.connector.connect(
                    **self.source_config['connection_params']
                )
            else:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Database source connection failed: {e}")
            return False
    
    def _connect_api_source(self) -> bool:
        """Connect to API source"""
        try:
            import requests
            
            # Test connection
            response = requests.get(
                self.source_config['health_url'],
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"API source connection failed: {e}")
            return False
    
    def _connect_file_source(self) -> bool:
        """Connect to file source"""
        try:
            import os
            
            file_path = self.source_config['file_path']
            if not os.path.exists(file_path):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"File source connection failed: {e}")
            return False
    
    def _connect_database_target(self) -> bool:
        """Connect to database target"""
        return self._connect_database_source()  # Same logic as source
    
    def _connect_api_target(self) -> bool:
        """Connect to API target"""
        return self._connect_api_source()  # Same logic as source
    
    def _connect_webhook_target(self) -> bool:
        """Connect to webhook target"""
        try:
            import requests
            
            # Test webhook
            test_payload = {'type': 'health_check'}
            response = requests.post(
                self.target_config['webhook_url'],
                json=test_payload,
                timeout=10
            )
            
            return response.status_code in [200, 202]
            
        except Exception as e:
            logger.error(f"Webhook target connection failed: {e}")
            return False
    
    def _transfer_batch(self, batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Transfer a batch of data"""
        target_type = self.target_config.get('type', 'database')
        
        if target_type == 'database':
            return self._transfer_to_database(batch)
        elif target_type == 'api':
            return self._transfer_to_api(batch)
        elif target_type == 'webhook':
            return self._transfer_to_webhook(batch)
        else:
            return {'success': False, 'error': f'Unsupported target type: {target_type}'}
    
    def _transfer_to_database(self, batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Transfer batch to database"""
        try:
            cursor = self.source_connection.cursor()
            
            for item in batch:
                # Build INSERT query based on target config
                table_name = safe_identifier(self.target_config.get('table_name', 'alerts'), 'table name')
                columns = ', '.join(safe_identifier(key, 'column name') for key in item.keys())
                placeholders = ', '.join(['%s'] * len(item))
                
                query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"  # nosec B608 - identifiers validated via sql_utils; values are bound parameters
                cursor.execute(query, list(item.values()))
            
            self.source_connection.commit()
            return {'success': True, 'transferred': len(batch)}
            
        except Exception as e:
            logger.error(f"Database transfer failed: {e}")
            return {'success': False, 'error': 'Operation failed'}
    
    def _transfer_to_api(self, batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Transfer batch to API"""
        try:
            import requests
            
            url = self.target_config.get('api_url')
            headers = self.target_config.get('headers', {})
            
            for item in batch:
                response = requests.post(url, json=item, headers=headers, timeout=30)
                if response.status_code not in [200, 201]:
                    return {'success': False, 'error': f'API error: {response.status_code}'}
            
            return {'success': True, 'transferred': len(batch)}
            
        except Exception as e:
            logger.error(f"API transfer failed: {e}")
            return {'success': False, 'error': 'Operation failed'}
    
    def _transfer_to_webhook(self, batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Transfer batch to webhook"""
        try:
            import requests
            
            webhook_url = self.target_config.get('webhook_url')
            headers = self.target_config.get('headers', {})
            
            for item in batch:
                response = requests.post(webhook_url, json=item, headers=headers, timeout=30)
                if response.status_code not in [200, 202]:
                    return {'success': False, 'error': f'Webhook error: {response.status_code}'}
            
            return {'success': True, 'transferred': len(batch)}
            
        except Exception as e:
            logger.error(f"Webhook transfer failed: {e}")
            return {'success': False, 'error': 'Operation failed'}
    
    def _apply_field_mappings(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply field mappings to data"""
        if not self.field_mappings:
            return data
        
        mapped_data = []
        
        for item in data:
            mapped_item = {}
            
            for target_field, source_field in self.field_mappings.items():
                if source_field in item:
                    mapped_item[target_field] = item[source_field]
            
            # Keep unmapped fields
            for field, value in item.items():
                if field not in self.field_mappings.values():
                    mapped_item[field] = value
            
            mapped_data.append(mapped_item)
        
        return mapped_data
    
    def _check_source_health(self) -> bool:
        """Check source system health"""
        try:
            source_type = self.source_config.get('type', 'database')
            
            if source_type == 'database':
                cursor = self.source_connection.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                return True
            elif source_type == 'api':
                import requests
                response = requests.get(self.source_config['health_url'], timeout=5)
                return response.status_code == 200
            elif source_type == 'file':
                import os
                return os.path.exists(self.source_config['file_path'])
            
            return False
            
        except Exception as e:
            logger.error(f"Source health check failed: {e}")
            return False
    
    def _check_target_health(self) -> bool:
        """Check target system health"""
        try:
            target_type = self.target_config.get('type', 'database')
            
            if target_type == 'database':
                return self._check_database_target_health()
            elif target_type == 'api':
                return self._check_api_target_health()
            elif target_type == 'webhook':
                return self._check_webhook_target_health()
            
            return False
            
        except Exception as e:
            logger.error(f"Target health check failed: {e}")
            return False
    
    def _check_database_target_health(self) -> bool:
        """Check database target health"""
        # Similar to source health check
        return self._check_source_health()
    
    def _check_api_target_health(self) -> bool:
        """Check API target health"""
        try:
            import requests
            
            health_url = self.target_config.get('health_url')
            if not health_url:
                return True  # Assume healthy if no health URL
            
            response = requests.get(health_url, timeout=5)
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"API target health check failed: {e}")
            return False
    
    def _check_webhook_target_health(self) -> bool:
        """Check webhook target health"""
        try:
            import requests
            
            webhook_url = self.target_config.get('webhook_url')
            test_payload = {'type': 'health_check'}
            
            response = requests.post(webhook_url, json=test_payload, timeout=5)
            return response.status_code in [200, 202]
            
        except Exception as e:
            logger.error(f"Webhook target health check failed: {e}")
            return False


class RealTimeBridge(AlertBridge):
    """Real-time data bridge with streaming capabilities"""
    
    def __init__(self, source_config: Dict[str, Any], target_config: Dict[str, Any]):
        super().__init__(source_config, target_config)
        self.streaming_enabled = source_config.get('streaming', False)
        self.buffer_size = source_config.get('buffer_size', 1000)
        self.flush_interval = source_config.get('flush_interval', 5)
        self.data_buffer = []
        
    async def start_streaming(self):
        """Start real-time data streaming"""
        if not self.streaming_enabled:
            logger.warning("Streaming not enabled")
            return
        
        try:
            source_type = self.source_config.get('type', 'api')
            
            if source_type == 'websocket':
                await self._start_websocket_streaming()
            elif source_type == 'kafka':
                await self._start_kafka_streaming()
            elif source_type == 'redis':
                await self._start_redis_streaming()
            else:
                logger.error(f"Unsupported streaming source type: {source_type}")
                
        except Exception as e:
            logger.error(f"Error starting streaming: {e}")
    
    async def _start_websocket_streaming(self):
        """Start WebSocket streaming"""
        try:
            import websockets
            
            websocket_url = self.source_config['websocket_url']
            
            async with websockets.connect(websocket_url) as websocket:
                while self.enabled:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        
                        # Add to buffer
                        self.data_buffer.append(data)
                        
                        # Flush buffer if needed
                        if len(self.data_buffer) >= self.buffer_size:
                            await self._flush_buffer()
                        
                    except Exception as e:
                        logger.error(f"Error processing WebSocket message: {e}")
                        
        except Exception as e:
            logger.error(f"WebSocket streaming error: {e}")
    
    async def _start_kafka_streaming(self):
        """Start Kafka streaming"""
        try:
            import aiokafka
            
            consumer = aiokafka.AIOKafkaConsumer(
                self.source_config['topic'],
                bootstrap_servers=self.source_config['bootstrap_servers'],
                group_id=self.source_config.get('group_id', 'alert_bridge')
            )
            
            await consumer.start()
            
            try:
                async for message in consumer:
                    try:
                        data = json.loads(message.value.decode('utf-8'))
                        
                        # Add to buffer
                        self.data_buffer.append(data)
                        
                        # Flush buffer if needed
                        if len(self.data_buffer) >= self.buffer_size:
                            await self._flush_buffer()
                            
                    except Exception as e:
                        logger.error(f"Error processing Kafka message: {e}")
                        
            finally:
                await consumer.stop()
                
        except Exception as e:
            logger.error(f"Kafka streaming error: {e}")
    
    async def _start_redis_streaming(self):
        """Start Redis streaming"""
        try:
            import aioredis
            
            redis = aioredis.from_url(self.source_config['redis_url'])
            
            pubsub = redis.pubsub()
            await pubsub.subscribe(self.source_config['channel'])
            
        except Exception as e:
            logger.error(f"Redis streaming error: {e}")
    
    async def _flush_buffer(self):
        """Flush data buffer to target"""
        if not self.data_buffer:
            return
        
        try:
            # Transfer buffered data
            result = self.transfer_data(self.data_buffer)
            
            if result['success']:
                logger.info(f"Flushed {len(self.data_buffer)} items to target")
                self.data_buffer.clear()
            else:
                logger.error(f"Failed to flush buffer: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error flushing buffer: {e}")
    
    def stop_streaming(self):
        """Stop real-time streaming"""
        self.enabled = False
        logger.info("Streaming stopped")


class BridgeManager:
    """Manager for multiple data bridges"""
    
    def __init__(self):
        self.bridges = {}
        self.bridge_status = {}
        
    def register_bridge(self, bridge_name: str, bridge: DataBridge):
        """Register a data bridge"""
        self.bridges[bridge_name] = bridge
        logger.info(f"Registered bridge: {bridge_name}")
    
    def unregister_bridge(self, bridge_name: str):
        """Unregister a data bridge"""
        if bridge_name in self.bridges:
            del self.bridges[bridge_name]
            logger.info(f"Unregistered bridge: {bridge_name}")
    
    def start_bridge(self, bridge_name: str) -> bool:
        """Start a data bridge"""
        if bridge_name not in self.bridges:
            logger.error(f"Bridge {bridge_name} not found")
            return False
        
        bridge = self.bridges[bridge_name]
        
        try:
            # Connect to source
            source_connected = bridge.connect_source()
            if not source_connected:
                logger.error(f"Failed to connect source for {bridge_name}")
                return False
            
            # Connect to target
            target_connected = bridge.connect_target()
            if not target_connected:
                logger.error(f"Failed to connect target for {bridge_name}")
                return False
            
            # Update status
            self.bridge_status[bridge_name] = {
                'status': 'running',
                'source_connected': source_connected,
                'target_connected': target_connected,
                'started_at': timezone.now().isoformat()
            }
            
            logger.info(f"Bridge {bridge_name} started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error starting bridge {bridge_name}: {e}")
            return False
    
    def stop_bridge(self, bridge_name: str) -> bool:
        """Stop a data bridge"""
        if bridge_name not in self.bridges:
            logger.error(f"Bridge {bridge_name} not found")
            return False
        
        try:
            # Update status
            self.bridge_status[bridge_name] = {
                'status': 'stopped',
                'stopped_at': timezone.now().isoformat()
            }
            
            logger.info(f"Bridge {bridge_name} stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping bridge {bridge_name}: {e}")
            return False
    
    def get_bridge_status(self, bridge_name: str) -> Optional[Dict[str, Any]]:
        """Get bridge status"""
        return self.bridge_status.get(bridge_name)
    
    def get_all_bridge_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all bridges"""
        return self.bridge_status.copy()
    
    def perform_health_checks(self) -> Dict[str, Dict[str, Any]]:
        """Perform health checks on all bridges"""
        health_results = {}
        
        for bridge_name, bridge in self.bridges.items():
            try:
                health_results[bridge_name] = bridge.health_check()
            except Exception as e:
                health_results[bridge_name] = {
                    'healthy': False,
                    'error': str(e),
                    'last_check': timezone.now().isoformat()
                }
        
        return health_results


# Bridge factory
class BridgeFactory:
    """Factory for creating data bridges"""
    
    @staticmethod
    def create_bridge(bridge_type: str, source_config: Dict[str, Any], target_config: Dict[str, Any]) -> Optional[DataBridge]:
        """Create bridge by type"""
        if bridge_type == 'alert':
            return AlertBridge(source_config, target_config)
        elif bridge_type == 'realtime':
            return RealTimeBridge(source_config, target_config)
        else:
            logger.error(f"Unknown bridge type: {bridge_type}")
            return None
    
    @staticmethod
    def get_available_bridges() -> List[str]:
        """Get list of available bridge types"""
        return ['alert', 'realtime']


# Global bridge manager
bridge_manager = BridgeManager()


def get_bridge_manager() -> BridgeManager:
    """Get the global bridge manager"""
    return bridge_manager
