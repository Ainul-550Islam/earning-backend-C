"""
Integration Bridge
Bridge components for connecting different systems and handling data flow
"""

import logging
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json

from .integ_adapter import BaseIntegrationAdapter
from .integ_registry import IntegrationRegistry
from .integ_exceptions import IntegrationException, BridgeException
from .integ_signals import emit_pre_integration_signal, emit_post_integration_signal
from .transformer import DataTransformer
from .data_validator import DataValidator

logger = logging.getLogger(__name__)


class BridgeType(Enum):
    """Bridge type enumeration"""
    ONE_WAY = "one_way"
    TWO_WAY = "two_way"
    BROADCAST = "broadcast"
    AGGREGATE = "aggregate"
    FILTER = "filter"
    TRANSFORM = "transform"


class BridgeStatus(Enum):
    """Bridge status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    PAUSED = "paused"


@dataclass
class BridgeConfiguration:
    """Bridge configuration"""
    bridge_id: str
    bridge_type: BridgeType
    source_systems: List[str]
    target_systems: List[str]
    transformation_rules: Optional[Dict[str, Any]] = None
    filters: Optional[Dict[str, Any]] = None
    retry_count: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0
    batch_size: int = 100
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BridgeMetrics:
    """Bridge performance metrics"""
    total_processed: int = 0
    successful_processed: int = 0
    failed_processed: int = 0
    average_processing_time: float = 0.0
    last_processed_time: Optional[datetime] = None
    throughput_per_second: float = 0.0
    error_rate: float = 0.0


class BaseBridge:
    """
    Abstract base class for integration bridges
    """
    
    def __init__(self, config: BridgeConfiguration, registry: IntegrationRegistry):
        self.config = config
        self.registry = registry
        self.bridge_id = config.bridge_id
        self.bridge_type = config.bridge_type
        self.status = BridgeStatus.INACTIVE
        self.metrics = BridgeMetrics()
        self.transformer = DataTransformer()
        self.validator = DataValidator()
        self._processing = False
        self._last_activity = None
        
        # Get adapters for source and target systems
        self.source_adapters: Dict[str, BaseIntegrationAdapter] = {}
        self.target_adapters: Dict[str, BaseIntegrationAdapter] = {}
        
        self._initialize_adapters()
    
    def _initialize_adapters(self):
        """Initialize adapters for source and target systems"""
        for system_name in self.config.source_systems:
            adapter = self.registry.get_adapter(system_name)
            if adapter:
                self.source_adapters[system_name] = adapter
            else:
                logger.warning(f"Adapter not found for source system: {system_name}")
        
        for system_name in self.config.target_systems:
            adapter = self.registry.get_adapter(system_name)
            if adapter:
                self.target_adapters[system_name] = adapter
            else:
                logger.warning(f"Adapter not found for target system: {system_name}")
    
    async def start(self):
        """Start the bridge"""
        if self.status == BridgeStatus.ACTIVE:
            return
        
        try:
            # Validate adapters
            if not self.source_adapters:
                raise BridgeException("No valid source adapters found")
            
            if not self.target_adapters and self.bridge_type != BridgeType.BROADCAST:
                raise BridgeException("No valid target adapters found")
            
            self.status = BridgeStatus.ACTIVE
            logger.info(f"Bridge {self.bridge_id} started successfully")
            
        except Exception as e:
            self.status = BridgeStatus.ERROR
            logger.error(f"Failed to start bridge {self.bridge_id}: {e}")
            raise BridgeException(f"Failed to start bridge: {e}")
    
    async def stop(self):
        """Stop the bridge"""
        if self.status != BridgeStatus.ACTIVE:
            return
        
        try:
            # Wait for current processing to complete
            if self._processing:
                logger.info(f"Waiting for bridge {self.bridge_id} to complete processing")
                # In a real implementation, you'd wait for processing to complete
            
            self.status = BridgeStatus.INACTIVE
            logger.info(f"Bridge {self.bridge_id} stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping bridge {self.bridge_id}: {e}")
    
    async def process_data(self, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process data through the bridge
        
        Args:
            data: Data to process
            context: Processing context
            
        Returns:
            Processing results
        """
        if self.status != BridgeStatus.ACTIVE:
            raise BridgeException(f"Bridge {self.bridge_id} is not active")
        
        start_time = datetime.utcnow()
        self._processing = True
        
        try:
            # Emit pre-integration signal
            emit_pre_integration_signal(
                source_system="bridge",
                target_system="multiple",
                request_id=context.get('request_id', 'unknown') if context else 'unknown',
                data=data
            )
            
            # Process based on bridge type
            if self.bridge_type == BridgeType.ONE_WAY:
                result = await self._process_one_way(data, context)
            elif self.bridge_type == BridgeType.TWO_WAY:
                result = await self._process_two_way(data, context)
            elif self.bridge_type == BridgeType.BROADCAST:
                result = await self._process_broadcast(data, context)
            elif self.bridge_type == BridgeType.AGGREGATE:
                result = await self._process_aggregate(data, context)
            elif self.bridge_type == BridgeType.FILTER:
                result = await self._process_filter(data, context)
            elif self.bridge_type == BridgeType.TRANSFORM:
                result = await self._process_transform(data, context)
            else:
                raise BridgeException(f"Unsupported bridge type: {self.bridge_type}")
            
            # Update metrics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_metrics(True, processing_time)
            
            # Emit post-integration signal
            emit_post_integration_signal(
                source_system="bridge",
                target_system="multiple",
                request_id=context.get('request_id', 'unknown') if context else 'unknown',
                data=result
            )
            
            return result
            
        except Exception as e:
            # Update metrics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_metrics(False, processing_time)
            
            logger.error(f"Error processing data in bridge {self.bridge_id}: {e}")
            raise BridgeException(f"Failed to process data: {e}")
            
        finally:
            self._processing = False
            self._last_activity = datetime.utcnow()
    
    async def _process_one_way(self, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process one-way bridge"""
        results = {}
        
        for source_name, source_adapter in self.source_adapters.items():
            try:
                # Receive data from source
                source_data = await source_adapter.receive_data(**(context or {}))
                
                # Transform data if needed
                transformed_data = await self._transform_data(source_data, source_name)
                
                # Validate data
                validation_result = self.validator.validate(transformed_data, "bridge")
                if not validation_result.is_valid:
                    raise BridgeException(f"Data validation failed: {validation_result.errors}")
                
                # Send to all targets
                for target_name, target_adapter in self.target_adapters.items():
                    try:
                        target_result = await target_adapter.send_data(transformed_data, **(context or {}))
                        results[f"{source_name}_to_{target_name}"] = target_result
                    except Exception as e:
                        logger.error(f"Failed to send data from {source_name} to {target_name}: {e}")
                        results[f"{source_name}_to_{target_name}"] = {'error': str(e)}
                
            except Exception as e:
                logger.error(f"Failed to process data from source {source_name}: {e}")
                results[source_name] = {'error': str(e)}
        
        return results
    
    async def _process_two_way(self, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process two-way bridge"""
        results = {}
        
        # Process from source to target
        forward_results = await self._process_one_way(data, context)
        results['forward'] = forward_results
        
        # Process from target back to source (if applicable)
        reverse_results = {}
        for target_name, target_adapter in self.target_adapters.items():
            try:
                # Get response from target
                target_response = await target_adapter.receive_data(**(context or {}))
                
                # Send back to source
                for source_name, source_adapter in self.source_adapters.items():
                    try:
                        reverse_result = await source_adapter.send_data(target_response, **(context or {}))
                        reverse_results[f"{target_name}_to_{source_name}"] = reverse_result
                    except Exception as e:
                        logger.error(f"Failed to send data from {target_name} to {source_name}: {e}")
                        reverse_results[f"{target_name}_to_{source_name}"] = {'error': str(e)}
                
            except Exception as e:
                logger.error(f"Failed to get response from target {target_name}: {e}")
                reverse_results[target_name] = {'error': str(e)}
        
        results['reverse'] = reverse_results
        return results
    
    async def _process_broadcast(self, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process broadcast bridge"""
        results = {}
        
        for source_name, source_adapter in self.source_adapters.items():
            try:
                # Receive data from source
                source_data = await source_adapter.receive_data(**(context or {}))
                
                # Broadcast to all targets
                for target_name, target_adapter in self.target_adapters.items():
                    try:
                        target_result = await target_adapter.send_data(source_data, **(context or {}))
                        results[f"{source_name}_broadcast_to_{target_name}"] = target_result
                    except Exception as e:
                        logger.error(f"Failed to broadcast data from {source_name} to {target_name}: {e}")
                        results[f"{source_name}_broadcast_to_{target_name}"] = {'error': str(e)}
                
            except Exception as e:
                logger.error(f"Failed to receive data from source {source_name}: {e}")
                results[source_name] = {'error': str(e)}
        
        return results
    
    async def _process_aggregate(self, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process aggregate bridge"""
        aggregated_data = {
            'sources': [],
            'aggregated_at': datetime.utcnow().isoformat(),
            'total_count': 0
        }
        
        # Collect data from all sources
        for source_name, source_adapter in self.source_adapters.items():
            try:
                source_data = await source_adapter.receive_data(**(context or {}))
                aggregated_data['sources'].append({
                    'system': source_name,
                    'data': source_data
                })
                aggregated_data['total_count'] += 1
                
            except Exception as e:
                logger.error(f"Failed to receive data from source {source_name}: {e}")
                aggregated_data['sources'].append({
                    'system': source_name,
                    'error': str(e)
                })
        
        # Send aggregated data to all targets
        results = {}
        for target_name, target_adapter in self.target_adapters.items():
            try:
                target_result = await target_adapter.send_data(aggregated_data, **(context or {}))
                results[target_name] = target_result
            except Exception as e:
                logger.error(f"Failed to send aggregated data to {target_name}: {e}")
                results[target_name] = {'error': str(e)}
        
        return {
            'aggregated_data': aggregated_data,
            'target_results': results
        }
    
    async def _process_filter(self, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process filter bridge"""
        results = {}
        
        for source_name, source_adapter in self.source_adapters.items():
            try:
                # Receive data from source
                source_data = await source_adapter.receive_data(**(context or {}))
                
                # Apply filters
                filtered_data = await self._apply_filters(source_data)
                
                if filtered_data:
                    # Send filtered data to targets
                    for target_name, target_adapter in self.target_adapters.items():
                        try:
                            target_result = await target_adapter.send_data(filtered_data, **(context or {}))
                            results[f"{source_name}_to_{target_name}"] = target_result
                        except Exception as e:
                            logger.error(f"Failed to send filtered data from {source_name} to {target_name}: {e}")
                            results[f"{source_name}_to_{target_name}"] = {'error': str(e)}
                else:
                    # Data was filtered out
                    results[source_name] = {'filtered_out': True}
                
            except Exception as e:
                logger.error(f"Failed to process data from source {source_name}: {e}")
                results[source_name] = {'error': str(e)}
        
        return results
    
    async def _process_transform(self, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process transform bridge"""
        results = {}
        
        for source_name, source_adapter in self.source_adapters.items():
            try:
                # Receive data from source
                source_data = await source_adapter.receive_data(**(context or {}))
                
                # Apply transformations
                transformed_data = await self._apply_transformations(source_data, source_name)
                
                # Send transformed data to targets
                for target_name, target_adapter in self.target_adapters.items():
                    try:
                        target_result = await target_adapter.send_data(transformed_data, **(context or {}))
                        results[f"{source_name}_to_{target_name}"] = target_result
                    except Exception as e:
                        logger.error(f"Failed to send transformed data from {source_name} to {target_name}: {e}")
                        results[f"{source_name}_to_{target_name}"] = {'error': str(e)}
                
            except Exception as e:
                logger.error(f"Failed to process data from source {source_name}: {e}")
                results[source_name] = {'error': str(e)}
        
        return results
    
    async def _transform_data(self, data: Dict[str, Any], source_system: str) -> Dict[str, Any]:
        """Transform data based on bridge configuration"""
        if not self.config.transformation_rules:
            return data
        
        # Apply transformation rules
        return self.transformer.transform(data, self.config.transformation_rules)
    
    async def _apply_filters(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Apply filters to data"""
        if not self.config.filters:
            return data
        
        # Apply filter logic
        # This is a simplified implementation
        for filter_key, filter_value in self.config.filters.items():
            if filter_key in data:
                if isinstance(filter_value, list):
                    if data[filter_key] not in filter_value:
                        return None
                else:
                    if data[filter_key] != filter_value:
                        return None
        
        return data
    
    async def _apply_transformations(self, data: Dict[str, Any], source_system: str) -> Dict[str, Any]:
        """Apply transformations to data"""
        if not self.config.transformation_rules:
            return data
        
        # Apply transformation logic
        transformed_data = data.copy()
        
        for field, transformation in self.config.transformation_rules.items():
            if field in transformed_data:
                if transformation.get('type') == 'rename':
                    new_name = transformation['new_name']
                    transformed_data[new_name] = transformed_data.pop(field)
                elif transformation.get('type') == 'format':
                    format_type = transformation['format']
                    if format_type == 'upper':
                        transformed_data[field] = str(transformed_data[field]).upper()
                    elif format_type == 'lower':
                        transformed_data[field] = str(transformed_data[field]).lower()
                    elif format_type == 'date':
                        # Format date logic
                        pass
        
        return transformed_data
    
    def _update_metrics(self, success: bool, processing_time: float):
        """Update bridge metrics"""
        self.metrics.total_processed += 1
        self.metrics.last_processed_time = datetime.utcnow()
        
        if success:
            self.metrics.successful_processed += 1
        else:
            self.metrics.failed_processed += 1
        
        # Update average processing time
        total = self.metrics.total_processed
        current_avg = self.metrics.average_processing_time
        self.metrics.average_processing_time = ((current_avg * (total - 1)) + processing_time) / total
        
        # Update error rate
        if total > 0:
            self.metrics.error_rate = (self.metrics.failed_processed / total) * 100
        
        # Update throughput
        if self._last_activity:
            time_diff = (datetime.utcnow() - self._last_activity).total_seconds()
            if time_diff > 0:
                self.metrics.throughput_per_second = 1.0 / time_diff
    
    def get_status(self) -> Dict[str, Any]:
        """Get bridge status"""
        return {
            'bridge_id': self.bridge_id,
            'bridge_type': self.bridge_type.value,
            'status': self.status.value,
            'source_systems': list(self.source_adapters.keys()),
            'target_systems': list(self.target_adapters.keys()),
            'processing': self._processing,
            'last_activity': self._last_activity.isoformat() if self._last_activity else None,
            'metrics': {
                'total_processed': self.metrics.total_processed,
                'successful_processed': self.metrics.successful_processed,
                'failed_processed': self.metrics.failed_processed,
                'average_processing_time': self.metrics.average_processing_time,
                'error_rate': self.metrics.error_rate,
                'throughput_per_second': self.metrics.throughput_per_second
            }
        }


class BridgeManager:
    """
    Manager for integration bridges
    """
    
    def __init__(self, registry: IntegrationRegistry):
        self.registry = registry
        self.bridges: Dict[str, BaseBridge] = {}
        self._lock = None
    
    def create_bridge(self, config: BridgeConfiguration) -> BaseBridge:
        """
        Create a new bridge
        
        Args:
            config: Bridge configuration
            
        Returns:
            Created bridge instance
        """
        if config.bridge_id in self.bridges:
            raise BridgeException(f"Bridge {config.bridge_id} already exists")
        
        # Create bridge based on type
        bridge = BaseBridge(config, self.registry)
        
        # Store bridge
        self.bridges[config.bridge_id] = bridge
        
        logger.info(f"Created bridge: {config.bridge_id}")
        
        return bridge
    
    def get_bridge(self, bridge_id: str) -> Optional[BaseBridge]:
        """
        Get bridge by ID
        
        Args:
            bridge_id: Bridge ID
            
        Returns:
            Bridge instance or None
        """
        return self.bridges.get(bridge_id)
    
    def list_bridges(self, status: Optional[BridgeStatus] = None) -> List[BaseBridge]:
        """
        List bridges
        
        Args:
            status: Filter by status (optional)
            
        Returns:
            List of bridges
        """
        bridges = list(self.bridges.values())
        
        if status:
            bridges = [b for b in bridges if b.status == status]
        
        return bridges
    
    async def start_bridge(self, bridge_id: str) -> bool:
        """
        Start a bridge
        
        Args:
            bridge_id: Bridge ID
            
        Returns:
            True if successful, False otherwise
        """
        bridge = self.get_bridge(bridge_id)
        if not bridge:
            return False
        
        try:
            await bridge.start()
            return True
        except Exception as e:
            logger.error(f"Failed to start bridge {bridge_id}: {e}")
            return False
    
    async def stop_bridge(self, bridge_id: str) -> bool:
        """
        Stop a bridge
        
        Args:
            bridge_id: Bridge ID
            
        Returns:
            True if successful, False otherwise
        """
        bridge = self.get_bridge(bridge_id)
        if not bridge:
            return False
        
        try:
            await bridge.stop()
            return True
        except Exception as e:
            logger.error(f"Failed to stop bridge {bridge_id}: {e}")
            return False
    
    def delete_bridge(self, bridge_id: str) -> bool:
        """
        Delete a bridge
        
        Args:
            bridge_id: Bridge ID
            
        Returns:
            True if successful, False otherwise
        """
        bridge = self.get_bridge(bridge_id)
        if not bridge:
            return False
        
        try:
            # Stop bridge if active
            if bridge.status == BridgeStatus.ACTIVE:
                # In async context, this would be awaited
                pass  # await bridge.stop()
            
            # Remove from registry
            del self.bridges[bridge_id]
            
            logger.info(f"Deleted bridge: {bridge_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete bridge {bridge_id}: {e}")
            return False
    
    def get_all_status(self) -> Dict[str, Any]:
        """
        Get status of all bridges
        
        Returns:
            Status information for all bridges
        """
        return {
            'total_bridges': len(self.bridges),
            'bridges': {
                bridge_id: bridge.get_status()
                for bridge_id, bridge in self.bridges.items()
            }
        }


# Export main classes and functions
__all__ = [
    'BaseBridge',
    'BridgeManager',
    'BridgeConfiguration',
    'BridgeMetrics',
    'BridgeType',
    'BridgeStatus',
]
