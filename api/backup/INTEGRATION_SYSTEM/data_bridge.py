"""
Data Bridge
Advanced data bridging for complex data transformations and routing
"""

import logging
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
from collections import defaultdict

from .integ_adapter import BaseIntegrationAdapter
from .integ_registry import IntegrationRegistry
from .integ_exceptions import IntegrationException, DataBridgeException
from .transformer import DataTransformer
from .data_validator import DataValidator
from .event_bus import EventBus

logger = logging.getLogger(__name__)


class DataFlowType(Enum):
    """Data flow types"""
    UNIDIRECTIONAL = "unidirectional"
    BIDIRECTIONAL = "bidirectional"
    MULTICAST = "multicast"
    AGGREGATE = "aggregate"
    SPLIT = "split"
    ROUTE = "route"


class DataFormat(Enum):
    """Data format types"""
    JSON = "json"
    XML = "xml"
    CSV = "csv"
    YAML = "yaml"
    BINARY = "binary"
    CUSTOM = "custom"


class TransformationType(Enum):
    """Transformation types"""
    SCHEMA_MAPPING = "schema_mapping"
    DATA_FILTERING = "data_filtering"
    DATA_AGGREGATION = "data_aggregation"
    DATA_SPLITTING = "data_splitting"
    FORMAT_CONVERSION = "format_conversion"
    VALUE_MAPPING = "value_mapping"
    VALIDATION = "validation"
    ENRICHMENT = "enrichment"


@dataclass
class DataBridgeConfig:
    """Data bridge configuration"""
    bridge_id: str
    name: str
    source_system: str
    target_systems: List[str]
    flow_type: DataFlowType
    source_format: DataFormat
    target_format: DataFormat
    transformations: List[Dict[str, Any]] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    routing_rules: Dict[str, Any] = field(default_factory=dict)
    batch_size: int = 100
    timeout: float = 30.0
    retry_count: int = 3
    retry_delay: float = 5.0
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataPacket:
    """Data packet for bridging"""
    packet_id: str
    source_system: str
    target_systems: List[str]
    data: Any
    format: DataFormat
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    transformations_applied: List[str] = field(default_factory=list)


@dataclass
class TransformationRule:
    """Transformation rule definition"""
    rule_id: str
    transformation_type: TransformationType
    source_field: Optional[str] = None
    target_field: Optional[str] = None
    mapping: Dict[str, Any] = field(default_factory=dict)
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    priority: int = 5
    enabled: bool = True


@dataclass
class BridgeMetrics:
    """Bridge performance metrics"""
    total_packets: int = 0
    successful_packets: int = 0
    failed_packets: int = 0
    transformation_time: float = 0.0
    transfer_time: float = 0.0
    average_packet_size: float = 0.0
    throughput_per_second: float = 0.0
    error_rate: float = 0.0


class DataBridge:
    """
    Advanced data bridge for complex data transformations and routing
    """
    
    def __init__(self, config: DataBridgeConfig, registry: IntegrationRegistry):
        self.config = config
        self.registry = registry
        self.bridge_id = config.bridge_id
        self.name = config.name
        
        # Components
        self.transformer = DataTransformer()
        self.validator = DataValidator()
        self.event_bus = EventBus()
        
        # State
        self.is_active = False
        self._processing = False
        
        # Metrics
        self.metrics = BridgeMetrics()
        
        # Transformation rules
        self.transformation_rules: List[TransformationRule] = []
        self._load_transformation_rules()
        
        # Adapters
        self.source_adapter: Optional[BaseIntegrationAdapter] = None
        self.target_adapters: Dict[str, BaseIntegrationAdapter] = {}
        self._initialize_adapters()
    
    def _load_transformation_rules(self):
        """Load transformation rules from configuration"""
        for i, trans_config in enumerate(self.config.transformations):
            rule = TransformationRule(
                rule_id=f"{self.bridge_id}_rule_{i}",
                transformation_type=TransformationType(trans_config.get('type', 'schema_mapping')),
                source_field=trans_config.get('source_field'),
                target_field=trans_config.get('target_field'),
                mapping=trans_config.get('mapping', {}),
                conditions=trans_config.get('conditions', []),
                priority=trans_config.get('priority', 5),
                enabled=trans_config.get('enabled', True)
            )
            self.transformation_rules.append(rule)
        
        # Sort rules by priority
        self.transformation_rules.sort(key=lambda r: r.priority)
    
    def _initialize_adapters(self):
        """Initialize source and target adapters"""
        # Get source adapter
        self.source_adapter = self.registry.get_adapter(self.config.source_system)
        
        # Get target adapters
        for target_system in self.config.target_systems:
            adapter = self.registry.get_adapter(target_system)
            if adapter:
                self.target_adapters[target_system] = adapter
            else:
                logger.warning(f"Adapter not found for target system: {target_system}")
    
    async def start(self):
        """Start the data bridge"""
        if self.is_active:
            return
        
        try:
            # Validate adapters
            if not self.source_adapter:
                raise DataBridgeException(f"Source adapter not found: {self.config.source_system}")
            
            if not self.target_adapters:
                raise DataBridgeException("No valid target adapters found")
            
            # Start event bus
            await self.event_bus.start()
            
            self.is_active = True
            logger.info(f"Data bridge started: {self.name} ({self.bridge_id})")
            
        except Exception as e:
            self.is_active = False
            logger.error(f"Failed to start data bridge {self.bridge_id}: {e}")
            raise DataBridgeException(f"Failed to start data bridge: {e}")
    
    async def stop(self):
        """Stop the data bridge"""
        if not self.is_active:
            return
        
        try:
            # Wait for current processing to complete
            if self._processing:
                logger.info(f"Waiting for data bridge {self.bridge_id} to complete processing")
            
            # Stop event bus
            await self.event_bus.stop()
            
            self.is_active = False
            logger.info(f"Data bridge stopped: {self.name} ({self.bridge_id})")
            
        except Exception as e:
            logger.error(f"Error stopping data bridge {self.bridge_id}: {e}")
    
    async def process_data(self, data: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process data through the bridge
        
        Args:
            data: Data to process
            context: Processing context
            
        Returns:
            Processing results
        """
        if not self.is_active:
            raise DataBridgeException(f"Data bridge {self.bridge_id} is not active")
        
        if self._processing:
            raise DataBridgeException(f"Data bridge {self.bridge_id} is already processing")
        
        start_time = datetime.utcnow()
        self._processing = True
        
        try:
            # Create data packet
            packet = DataPacket(
                packet_id=f"pkt_{self.bridge_id}_{int(start_time.timestamp())}",
                source_system=self.config.source_system,
                target_systems=self.config.target_systems.copy(),
                data=data,
                format=self.config.source_format,
                metadata=context or {}
            )
            
            # Update metrics
            self.metrics.total_packets += 1
            
            # Process based on flow type
            if self.config.flow_type == DataFlowType.UNIDIRECTIONAL:
                results = await self._process_unidirectional(packet)
            elif self.config.flow_type == DataFlowType.BIDIRECTIONAL:
                results = await self._process_bidirectional(packet)
            elif self.config.flow_type == DataFlowType.MULTICAST:
                results = await self._process_multicast(packet)
            elif self.config.flow_type == DataFlowType.AGGREGATE:
                results = await self._process_aggregate(packet)
            elif self.config.flow_type == DataFlowType.SPLIT:
                results = await self._process_split(packet)
            elif self.config.flow_type == DataFlowType.ROUTE:
                results = await self._process_route(packet)
            else:
                raise DataBridgeException(f"Unsupported flow type: {self.config.flow_type}")
            
            # Update metrics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_metrics(True, processing_time, len(str(data)))
            
            return results
            
        except Exception as e:
            # Update metrics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_metrics(False, processing_time, len(str(data)))
            
            logger.error(f"Error processing data in bridge {self.bridge_id}: {e}")
            raise DataBridgeException(f"Failed to process data: {e}")
            
        finally:
            self._processing = False
    
    async def _process_unidirectional(self, packet: DataPacket) -> Dict[str, Any]:
        """Process unidirectional data flow"""
        results = {}
        
        try:
            # Apply transformations
            transformed_packet = await self._apply_transformations(packet)
            
            # Convert format if needed
            if packet.format != self.config.target_format:
                transformed_packet = await self._convert_format(
                    transformed_packet, 
                    packet.format, 
                    self.config.target_format
                )
            
            # Send to all targets
            for target_system, adapter in self.target_adapters.items():
                try:
                    # Send data
                    await adapter.send_data(transformed_packet.data)
                    results[target_system] = {'status': 'success', 'packet_id': transformed_packet.packet_id}
                    
                except Exception as e:
                    results[target_system] = {'status': 'error', 'error': str(e)}
                    logger.error(f"Failed to send data to {target_system}: {e}")
            
            return results
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def _process_bidirectional(self, packet: DataPacket) -> Dict[str, Any]:
        """Process bidirectional data flow"""
        results = {}
        
        try:
            # Process forward direction
            forward_results = await self._process_unidirectional(packet)
            results['forward'] = forward_results
            
            # Process reverse direction (if applicable)
            reverse_results = {}
            for target_system, adapter in self.target_adapters.items():
                try:
                    # Get response from target
                    response_data = await adapter.receive_data()
                    
                    # Create reverse packet
                    reverse_packet = DataPacket(
                        packet_id=f"rev_{packet.packet_id}_{target_system}",
                        source_system=target_system,
                        target_systems=[self.config.source_system],
                        data=response_data,
                        format=self.config.target_format,
                        metadata={'reverse_of': packet.packet_id}
                    )
                    
                    # Apply reverse transformations
                    transformed_reverse = await self._apply_reverse_transformations(reverse_packet)
                    
                    # Send back to source
                    await self.source_adapter.send_data(transformed_reverse.data)
                    reverse_results[target_system] = {'status': 'success'}
                    
                except Exception as e:
                    reverse_results[target_system] = {'status': 'error', 'error': str(e)}
                    logger.error(f"Failed to process reverse flow for {target_system}: {e}")
            
            results['reverse'] = reverse_results
            return results
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def _process_multicast(self, packet: DataPacket) -> Dict[str, Any]:
        """Process multicast data flow"""
        results = {}
        
        try:
            # Apply transformations once
            transformed_packet = await self._apply_transformations(packet)
            
            # Convert format if needed
            if packet.format != self.config.target_format:
                transformed_packet = await self._convert_format(
                    transformed_packet, 
                    packet.format, 
                    self.config.target_format
                )
            
            # Send to all targets concurrently
            tasks = []
            for target_system, adapter in self.target_adapters.items():
                task = asyncio.create_task(
                    self._send_to_target(adapter, transformed_packet, target_system)
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, (target_system, _) in enumerate(self.target_adapters.items()):
                result = task_results[i]
                if isinstance(result, Exception):
                    results[target_system] = {'status': 'error', 'error': str(result)}
                else:
                    results[target_system] = result
            
            return results
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def _process_aggregate(self, packet: DataPacket) -> Dict[str, Any]:
        """Process aggregate data flow"""
        results = {}
        
        try:
            # Collect data from source
            source_data = await self.source_adapter.receive_data()
            
            # Aggregate with packet data
            aggregated_data = {
                'source_data': source_data,
                'packet_data': packet.data,
                'aggregated_at': datetime.utcnow().isoformat(),
                'source_system': self.config.source_system
            }
            
            # Create aggregated packet
            aggregated_packet = DataPacket(
                packet_id=f"agg_{packet.packet_id}",
                source_system=self.config.source_system,
                target_systems=self.config.target_systems.copy(),
                data=aggregated_data,
                format=DataFormat.JSON,
                metadata={'aggregation': True}
            )
            
            # Apply transformations
            transformed_packet = await self._apply_transformations(aggregated_packet)
            
            # Send to all targets
            for target_system, adapter in self.target_adapters.items():
                try:
                    await adapter.send_data(transformed_packet.data)
                    results[target_system] = {'status': 'success'}
                except Exception as e:
                    results[target_system] = {'status': 'error', 'error': str(e)}
            
            return results
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def _process_split(self, packet: DataPacket) -> Dict[str, Any]:
        """Process split data flow"""
        results = {}
        
        try:
            # Split data based on routing rules
            split_packets = await self._split_data(packet)
            
            # Send each split packet to appropriate targets
            for split_packet in split_packets:
                for target_system in split_packet.target_systems:
                    if target_system in self.target_adapters:
                        try:
                            adapter = self.target_adapters[target_system]
                            await adapter.send_data(split_packet.data)
                            
                            if target_system not in results:
                                results[target_system] = []
                            results[target_system].append({
                                'status': 'success',
                                'packet_id': split_packet.packet_id
                            })
                            
                        except Exception as e:
                            if target_system not in results:
                                results[target_system] = []
                            results[target_system].append({
                                'status': 'error',
                                'error': str(e),
                                'packet_id': split_packet.packet_id
                            })
            
            return results
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def _process_route(self, packet: DataPacket) -> Dict[str, Any]:
        """Process routed data flow"""
        results = {}
        
        try:
            # Determine target systems based on routing rules
            target_systems = await self._determine_targets(packet)
            
            # Apply transformations
            transformed_packet = await self._apply_transformations(packet)
            transformed_packet.target_systems = target_systems
            
            # Send to determined targets
            for target_system in target_systems:
                if target_system in self.target_adapters:
                    try:
                        adapter = self.target_adapters[target_system]
                        await adapter.send_data(transformed_packet.data)
                        results[target_system] = {'status': 'success'}
                    except Exception as e:
                        results[target_system] = {'status': 'error', 'error': str(e)}
            
            return results
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def _apply_transformations(self, packet: DataPacket) -> DataPacket:
        """Apply transformation rules to packet"""
        transformed_data = packet.data
        applied_transformations = []
        
        for rule in self.transformation_rules:
            if not rule.enabled:
                continue
            
            try:
                # Apply transformation based on type
                if rule.transformation_type == TransformationType.SCHEMA_MAPPING:
                    transformed_data = self._apply_schema_mapping(transformed_data, rule)
                    applied_transformations.append(f"schema_mapping_{rule.rule_id}")
                
                elif rule.transformation_type == TransformationType.DATA_FILTERING:
                    transformed_data = self._apply_data_filtering(transformed_data, rule)
                    applied_transformations.append(f"data_filtering_{rule.rule_id}")
                
                elif rule.transformation_type == TransformationType.VALUE_MAPPING:
                    transformed_data = self._apply_value_mapping(transformed_data, rule)
                    applied_transformations.append(f"value_mapping_{rule.rule_id}")
                
                elif rule.transformation_type == TransformationType.DATA_AGGREGATION:
                    transformed_data = self._apply_data_aggregation(transformed_data, rule)
                    applied_transformations.append(f"data_aggregation_{rule.rule_id}")
                
                elif rule.transformation_type == TransformationType.DATA_SPLITTING:
                    transformed_data = self._apply_data_splitting(transformed_data, rule)
                    applied_transformations.append(f"data_splitting_{rule.rule_id}")
                
                elif rule.transformation_type == TransformationType.VALIDATION:
                    self._apply_validation(transformed_data, rule)
                    applied_transformations.append(f"validation_{rule.rule_id}")
                
                elif rule.transformation_type == TransformationType.ENRICHMENT:
                    transformed_data = self._apply_enrichment(transformed_data, rule)
                    applied_transformations.append(f"enrichment_{rule.rule_id}")
                
            except Exception as e:
                logger.error(f"Failed to apply transformation {rule.rule_id}: {e}")
                continue
        
        # Create transformed packet
        transformed_packet = DataPacket(
            packet_id=packet.packet_id,
            source_system=packet.source_system,
            target_systems=packet.target_systems.copy(),
            data=transformed_data,
            format=packet.format,
            metadata=packet.metadata.copy(),
            transformations_applied=packet.transformations_applied + applied_transformations,
            processed_at=datetime.utcnow()
        )
        
        return transformed_packet
    
    async def _apply_reverse_transformations(self, packet: DataPacket) -> DataPacket:
        """Apply reverse transformations for bidirectional flow"""
        # This would implement reverse transformation logic
        # For now, just return the packet as-is
        return packet
    
    async def _convert_format(self, packet: DataPacket, source_format: DataFormat, 
                           target_format: DataFormat) -> DataPacket:
        """Convert data format"""
        try:
            if source_format == target_format:
                return packet
            
            # Convert based on format types
            if source_format == DataFormat.JSON and target_format == DataFormat.XML:
                converted_data = self._json_to_xml(packet.data)
            elif source_format == DataFormat.XML and target_format == DataFormat.JSON:
                converted_data = self._xml_to_json(packet.data)
            elif source_format == DataFormat.JSON and target_format == DataFormat.CSV:
                converted_data = self._json_to_csv(packet.data)
            elif source_format == DataFormat.CSV and target_format == DataFormat.JSON:
                converted_data = self._csv_to_json(packet.data)
            else:
                # For unsupported conversions, keep original
                converted_data = packet.data
            
            # Create new packet with converted data
            converted_packet = DataPacket(
                packet_id=packet.packet_id,
                source_system=packet.source_system,
                target_systems=packet.target_systems.copy(),
                data=converted_data,
                format=target_format,
                metadata=packet.metadata.copy(),
                transformations_applied=packet.transformations_applied + [f"format_conversion_{source_format.value}_to_{target_format.value}"],
                processed_at=datetime.utcnow()
            )
            
            return converted_packet
            
        except Exception as e:
            logger.error(f"Failed to convert format from {source_format} to {target_format}: {e}")
            return packet
    
    def _apply_schema_mapping(self, data: Any, rule: TransformationRule) -> Any:
        """Apply schema mapping transformation"""
        if not isinstance(data, dict):
            return data
        
        mapped_data = {}
        
        for field, mapping in rule.mapping.items():
            if field in data:
                if isinstance(mapping, str):
                    mapped_data[mapping] = data[field]
                elif isinstance(mapping, dict):
                    target_field = mapping.get('target', field)
                    transform_func = mapping.get('transform')
                    value = data[field]
                    
                    if transform_func:
                        # Apply transformation function
                        if transform_func == 'upper':
                            value = str(value).upper()
                        elif transform_func == 'lower':
                            value = str(value).lower()
                        elif transform_func == 'int':
                            value = int(value)
                        elif transform_func == 'float':
                            value = float(value)
                    
                    mapped_data[target_field] = value
        
        return mapped_data
    
    def _apply_data_filtering(self, data: Any, rule: TransformationRule) -> Any:
        """Apply data filtering transformation"""
        if not isinstance(data, dict):
            return data
        
        filtered_data = {}
        
        for field, value in data.items():
            # Check if field should be included
            include_field = True
            
            for condition in rule.conditions:
                if condition.get('field') == field:
                    operator = condition.get('operator', 'equals')
                    expected = condition.get('value')
                    
                    if operator == 'equals':
                        include_field = value == expected
                    elif operator == 'not_equals':
                        include_field = value != expected
                    elif operator == 'greater_than':
                        include_field = value > expected
                    elif operator == 'less_than':
                        include_field = value < expected
                    elif operator == 'contains':
                        include_field = expected in str(value)
                    elif operator == 'not_contains':
                        include_field = expected not in str(value)
                    
                    break
            
            if include_field:
                filtered_data[field] = value
        
        return filtered_data
    
    def _apply_value_mapping(self, data: Any, rule: TransformationRule) -> Any:
        """Apply value mapping transformation"""
        if not isinstance(data, dict):
            return data
        
        mapped_data = data.copy()
        
        if rule.source_field and rule.source_field in mapped_data:
            value = mapped_data[rule.source_field]
            
            # Apply mapping
            if value in rule.mapping:
                mapped_data[rule.source_field] = rule.mapping[value]
            
            # Set target field if specified
            if rule.target_field:
                mapped_data[rule.target_field] = mapped_data.pop(rule.source_field)
        
        return mapped_data
    
    def _apply_data_aggregation(self, data: Any, rule: TransformationRule) -> Any:
        """Apply data aggregation transformation"""
        # This would implement aggregation logic
        # For now, return data as-is
        return data
    
    def _apply_data_splitting(self, data: Any, rule: TransformationRule) -> Any:
        """Apply data splitting transformation"""
        # This would implement splitting logic
        # For now, return data as-is
        return data
    
    def _apply_validation(self, data: Any, rule: TransformationRule):
        """Apply validation transformation"""
        # This would implement validation logic
        # For now, just pass
        pass
    
    def _apply_enrichment(self, data: Any, rule: TransformationRule) -> Any:
        """Apply enrichment transformation"""
        if not isinstance(data, dict):
            return data
        
        enriched_data = data.copy()
        
        # Add enrichment fields
        for field, value in rule.mapping.items():
            if field not in enriched_data:
                enriched_data[field] = value
        
        # Add metadata
        enriched_data['_enriched_at'] = datetime.utcnow().isoformat()
        enriched_data['_enriched_by'] = self.bridge_id
        
        return enriched_data
    
    async def _split_data(self, packet: DataPacket) -> List[DataPacket]:
        """Split data packet based on rules"""
        split_packets = []
        
        # This would implement splitting logic
        # For now, return original packet
        split_packets.append(packet)
        
        return split_packets
    
    async def _determine_targets(self, packet: DataPacket) -> List[str]:
        """Determine target systems based on routing rules"""
        target_systems = self.config.target_systems.copy()
        
        # Apply routing rules
        for rule_name, rule_config in self.config.routing_rules.items():
            if self._evaluate_routing_condition(packet, rule_config.get('conditions', [])):
                # Apply rule
                if 'include_targets' in rule_config:
                    target_systems = [t for t in target_systems if t in rule_config['include_targets']]
                if 'exclude_targets' in rule_config:
                    target_systems = [t for t in target_systems if t not in rule_config['exclude_targets']]
                if 'add_targets' in rule_config:
                    target_systems.extend(rule_config['add_targets'])
        
        return target_systems
    
    def _evaluate_routing_condition(self, packet: DataPacket, conditions: List[Dict[str, Any]]) -> bool:
        """Evaluate routing conditions"""
        if not conditions:
            return True
        
        for condition in conditions:
            field = condition.get('field')
            operator = condition.get('operator', 'equals')
            expected = condition.get('value')
            
            if field in packet.metadata:
                actual = packet.metadata[field]
                
                if operator == 'equals':
                    if actual != expected:
                        return False
                elif operator == 'not_equals':
                    if actual == expected:
                        return False
                elif operator == 'contains':
                    if expected not in str(actual):
                        return False
                elif operator == 'not_contains':
                    if expected in str(actual):
                        return False
        
        return True
    
    async def _send_to_target(self, adapter: BaseIntegrationAdapter, packet: DataPacket, 
                             target_system: str) -> Dict[str, Any]:
        """Send packet to target system"""
        try:
            await adapter.send_data(packet.data)
            return {'status': 'success', 'packet_id': packet.packet_id}
        except Exception as e:
            return {'status': 'error', 'error': str(e), 'packet_id': packet.packet_id}
    
    def _json_to_xml(self, data: Any) -> str:
        """Convert JSON to XML"""
        # Simplified JSON to XML conversion
        if isinstance(data, dict):
            xml_parts = ['<root>']
            for key, value in data.items():
                xml_parts.append(f"<{key}>{value}</{key}>")
            xml_parts.append('</root>')
            return ''.join(xml_parts)
        return str(data)
    
    def _xml_to_json(self, xml_data: str) -> Dict[str, Any]:
        """Convert XML to JSON"""
        # Simplified XML to JSON conversion
        import re
        
        # Extract key-value pairs
        pattern = r'<(\w+)>(.*?)</\1>'
        matches = re.findall(pattern, xml_data)
        
        return {key: value for key, value in matches}
    
    def _json_to_csv(self, data: Any) -> str:
        """Convert JSON to CSV"""
        if isinstance(data, list) and data and isinstance(data[0], dict):
            # Convert list of dicts to CSV
            headers = list(data[0].keys())
            csv_lines = [','.join(headers)]
            
            for item in data:
                values = [str(item.get(header, '')) for header in headers]
                csv_lines.append(','.join(values))
            
            return '\n'.join(csv_lines)
        elif isinstance(data, dict):
            # Convert single dict to CSV
            headers = list(data.keys())
            values = [str(data[header]) for header in headers]
            return ','.join(headers) + '\n' + ','.join(values)
        
        return str(data)
    
    def _csv_to_json(self, csv_data: str) -> List[Dict[str, Any]]:
        """Convert CSV to JSON"""
        lines = csv_data.strip().split('\n')
        if len(lines) < 2:
            return [{'data': csv_data}]
        
        headers = [h.strip() for h in lines[0].split(',')]
        json_data = []
        
        for line in lines[1:]:
            values = [v.strip() for v in line.split(',')]
            if len(values) == len(headers):
                json_data.append(dict(zip(headers, values)))
        
        return json_data
    
    def _update_metrics(self, success: bool, processing_time: float, data_size: int):
        """Update bridge metrics"""
        if success:
            self.metrics.successful_packets += 1
        else:
            self.metrics.failed_packets += 1
        
        # Update average processing time
        total = self.metrics.total_packets
        current_avg = self.metrics.transformation_time
        self.metrics.transformation_time = ((current_avg * (total - 1)) + processing_time) / total
        
        # Update average packet size
        current_avg_size = self.metrics.average_packet_size
        self.metrics.average_packet_size = ((current_avg_size * (total - 1)) + data_size) / total
        
        # Update error rate
        if total > 0:
            self.metrics.error_rate = (self.metrics.failed_packets / total) * 100
        
        # Update throughput
        if processing_time > 0:
            self.metrics.throughput_per_second = data_size / processing_time
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get bridge metrics"""
        return {
            'bridge_id': self.bridge_id,
            'name': self.name,
            'is_active': self.is_active,
            'is_processing': self._processing,
            'total_packets': self.metrics.total_packets,
            'successful_packets': self.metrics.successful_packets,
            'failed_packets': self.metrics.failed_packets,
            'transformation_time': self.metrics.transformation_time,
            'transfer_time': self.metrics.transfer_time,
            'average_packet_size': self.metrics.average_packet_size,
            'throughput_per_second': self.metrics.throughput_per_second,
            'error_rate': self.metrics.error_rate,
            'source_system': self.config.source_system,
            'target_systems': self.config.target_systems,
            'flow_type': self.config.flow_type.value,
            'source_format': self.config.source_format.value,
            'target_format': self.config.target_format.value
        }


# Export main classes and functions
__all__ = [
    'DataBridge',
    'DataBridgeConfig',
    'DataPacket',
    'TransformationRule',
    'BridgeMetrics',
    'DataFlowType',
    'DataFormat',
    'TransformationType',
]
