# =============================================================================
# INTEGRATION_SYSTEM/data_bridge.py
# =============================================================================
"""
Data Bridge for Cross-System Communication.

Provides seamless data synchronization and transformation
between different systems and data sources.
"""

from __future__ import annotations

import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Type, TypeVar
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from collections import defaultdict

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction

from .integ_constants import DataFormat, Priority
from .integ_exceptions import (
    DataBridgeError, DataBridgeConnectionError, DataBridgeTransformationError
)
from .transformer import JSONTransformer, TransformationRegistry
from .data_validator import ValidationEngine, ValidationResult

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BridgeDirection(Enum):
    """Data bridge direction."""
    UNIDIRECTIONAL = "unidirectional"
    BIDIRECTIONAL = "bidirectional"


class SyncMode(Enum):
    """Synchronization modes."""
    REAL_TIME = "real_time"
    BATCH = "batch"
    SCHEDULED = "scheduled"
    ON_DEMAND = "on_demand"


class DataConflictResolution(Enum):
    """Data conflict resolution strategies."""
    SOURCE_WINS = "source_wins"
    TARGET_WINS = "target_wins"
    MERGE = "merge"
    TIMESTAMP_WINS = "timestamp_wins"
    MANUAL = "manual"


@dataclass
class DataSource:
    """Data source configuration."""
    source_id: str
    name: str
    type: str  # database, api, file, etc.
    connection_config: Dict[str, Any]
    schema: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataMapping:
    """Field mapping configuration."""
    source_field: str
    target_field: str
    transform_func: Optional[Callable[[Any], Any]] = None
    default_value: Optional[Any] = None
    required: bool = True
    validation_rules: List[str] = field(default_factory=list)


@dataclass
class DataBridgeConfig:
    """Data bridge configuration."""
    bridge_id: str
    name: str
    source: DataSource
    target: DataSource
    direction: BridgeDirection
    sync_mode: SyncMode
    field_mappings: List[DataMapping]
    conflict_resolution: DataConflictResolution
    enabled: bool = True
    batch_size: int = 100
    sync_interval: int = 300  # 5 minutes
    retry_attempts: int = 3
    timeout: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=timezone.now)
    updated_at: datetime = field(default_factory=timezone.now)


@dataclass
class SyncResult:
    """Synchronization result."""
    bridge_id: str
    success: bool
    records_processed: int
    records_success: int
    records_failed: int
    records_skipped: int
    start_time: datetime
    end_time: datetime
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> timedelta:
        """Get sync duration."""
        return self.end_time - self.start_time
    
    @property
    def success_rate(self) -> float:
        """Get success rate percentage."""
        if self.records_processed == 0:
            return 0.0
        return (self.records_success / self.records_processed) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'bridge_id': self.bridge_id,
            'success': self.success,
            'records_processed': self.records_processed,
            'records_success': self.records_success,
            'records_failed': self.records_failed,
            'records_skipped': self.records_skipped,
            'success_rate': self.success_rate,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'duration_seconds': self.duration.total_seconds(),
            'errors': self.errors,
            'warnings': self.warnings,
            'metadata': self.metadata
        }


class DataConnector(ABC):
    """
    Abstract base class for data connectors.
    """
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to data source."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to data source."""
        pass
    
    @abstractmethod
    async def read_data(self, query: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Read data from source."""
        pass
    
    @abstractmethod
    async def write_data(self, data: List[Dict[str, Any]]) -> int:
        """Write data to target."""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test connection to data source."""
        pass


class DatabaseConnector(DataConnector):
    """Database connector implementation."""
    
    def __init__(self, connection_config: Dict[str, Any]):
        """Initialize database connector."""
        self.connection_config = connection_config
        self.connection = None
    
    async def connect(self) -> bool:
        """Establish database connection."""
        try:
            # This would implement actual database connection
            # For now, simulate successful connection
            logger.info("Database connection established")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Close database connection."""
        if self.connection:
            # Close actual database connection
            self.connection = None
        logger.info("Database connection closed")
    
    async def read_data(self, query: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Read data from database."""
        # This would implement actual database reading
        # For now, return mock data
        return [
            {'id': 1, 'name': 'Test Record 1', 'created_at': timezone.now()},
            {'id': 2, 'name': 'Test Record 2', 'created_at': timezone.now()}
        ]
    
    async def write_data(self, data: List[Dict[str, Any]]) -> int:
        """Write data to database."""
        # This would implement actual database writing
        logger.info(f"Writing {len(data)} records to database")
        return len(data)
    
    async def test_connection(self) -> bool:
        """Test database connection."""
        return await self.connect()


class APIConnector(DataConnector):
    """API connector implementation."""
    
    def __init__(self, connection_config: Dict[str, Any]):
        """Initialize API connector."""
        self.connection_config = connection_config
        self.session = None
    
    async def connect(self) -> bool:
        """Establish API connection."""
        try:
            import aiohttp
            
            # Create session with authentication
            headers = self.connection_config.get('headers', {})
            timeout = aiohttp.ClientTimeout(total=self.connection_config.get('timeout', 30))
            
            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=timeout
            )
            
            # Test connection
            test_url = self.connection_config.get('base_url')
            if test_url:
                async with self.session.get(test_url) as response:
                    if response.status < 400:
                        logger.info("API connection established")
                        return True
                    else:
                        logger.error(f"API connection test failed: HTTP {response.status}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"API connection failed: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Close API connection."""
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("API connection closed")
    
    async def read_data(self, query: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Read data from API."""
        if not self.session:
            raise DataBridgeConnectionError("API session not established")
        
        base_url = self.connection_config.get('base_url')
        endpoint = self.connection_config.get('read_endpoint', '/data')
        url = f"{base_url}{endpoint}"
        
        params = {}
        if query:
            params['query'] = query
        if limit:
            params['limit'] = limit
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('records', [])
                else:
                    raise DataBridgeError(f"API read failed: HTTP {response.status}")
                    
        except Exception as e:
            logger.error(f"API read error: {e}")
            raise
    
    async def write_data(self, data: List[Dict[str, Any]]) -> int:
        """Write data to API."""
        if not self.session:
            raise DataBridgeConnectionError("API session not established")
        
        base_url = self.connection_config.get('base_url')
        endpoint = self.connection_config.get('write_endpoint', '/data')
        url = f"{base_url}{endpoint}"
        
        try:
            async with self.session.post(url, json={'records': data}) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    return result.get('written_count', len(data))
                else:
                    raise DataBridgeError(f"API write failed: HTTP {response.status}")
                    
        except Exception as e:
            logger.error(f"API write error: {e}")
            raise
    
    async def test_connection(self) -> bool:
        """Test API connection."""
        return await self.connect()


class FileConnector(DataConnector):
    """File connector implementation."""
    
    def __init__(self, connection_config: Dict[str, Any]):
        """Initialize file connector."""
        self.connection_config = connection_config
        self.file_path = connection_config.get('file_path')
        self.file_format = connection_config.get('format', 'json')
    
    async def connect(self) -> bool:
        """Establish file connection."""
        try:
            # Check if file exists and is accessible
            import os
            if os.path.exists(self.file_path) and os.access(self.file_path, os.R_OK):
                logger.info(f"File connection established: {self.file_path}")
                return True
            else:
                logger.error(f"File not accessible: {self.file_path}")
                return False
        except Exception as e:
            logger.error(f"File connection failed: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Close file connection."""
        logger.info("File connection closed")
    
    async def read_data(self, query: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Read data from file."""
        try:
            if self.file_format == 'json':
                with open(self.file_path, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data[:limit] if limit else data
                    elif isinstance(data, dict) and 'records' in data:
                        records = data['records']
                        return records[:limit] if limit else records
                    else:
                        return [data]
            
            elif self.file_format == 'csv':
                import csv
                records = []
                with open(self.file_path, 'r') as f:
                    reader = csv.DictReader(f)
                    for i, row in enumerate(reader):
                        if limit and i >= limit:
                            break
                        records.append(row)
                return records
            
            else:
                raise DataBridgeError(f"Unsupported file format: {self.file_format}")
                
        except Exception as e:
            logger.error(f"File read error: {e}")
            raise
    
    async def write_data(self, data: List[Dict[str, Any]]) -> int:
        """Write data to file."""
        try:
            if self.file_format == 'json':
                with open(self.file_path, 'w') as f:
                    json.dump(data, f, indent=2, default=str)
            
            elif self.file_format == 'csv':
                import csv
                if data:
                    with open(self.file_path, 'w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=data[0].keys())
                        writer.writeheader()
                        writer.writerows(data)
            
            else:
                raise DataBridgeError(f"Unsupported file format: {self.file_format}")
            
            logger.info(f"Written {len(data)} records to file")
            return len(data)
            
        except Exception as e:
            logger.error(f"File write error: {e}")
            raise
    
    async def test_connection(self) -> bool:
        """Test file connection."""
        return await self.connect()


class DataBridge:
    """
    Data bridge for cross-system communication.
    
    Provides seamless data synchronization and transformation
    between different systems and data sources.
    """
    
    def __init__(self):
        """Initialize data bridge."""
        self.bridges: Dict[str, DataBridgeConfig] = {}
        self.connectors: Dict[str, DataConnector] = {}
        self.sync_results: List[SyncResult] = []
        
        # Components
        self.transformer = JSONTransformer()
        self.validator = ValidationEngine()
        
        # Configuration
        self.enable_caching = getattr(settings, 'DATA_BRIDGE_ENABLE_CACHING', True)
        self.cache_ttl = getattr(settings, 'DATA_BRIDGE_CACHE_TTL', 3600)
        self.max_sync_results = getattr(settings, 'DATA_BRIDGE_MAX_RESULTS', 1000)
        
        # Statistics
        self.total_syncs = 0
        self.successful_syncs = 0
        self.failed_syncs = 0
        self.total_records_synced = 0
        
        logger.info("DataBridge initialized")
    
    def register_bridge(self, config: DataBridgeConfig) -> None:
        """Register data bridge configuration."""
        self.bridges[config.bridge_id] = config
        
        # Create connectors
        self.connectors[f"{config.bridge_id}_source"] = self._create_connector(config.source)
        self.connectors[f"{config.bridge_id}_target"] = self._create_connector(config.target)
        
        logger.info(f"Registered data bridge: {config.name}")
    
    def unregister_bridge(self, bridge_id: str) -> bool:
        """Unregister data bridge."""
        if bridge_id in self.bridges:
            del self.bridges[bridge_id]
            
            # Clean up connectors
            self.connectors.pop(f"{bridge_id}_source", None)
            self.connectors.pop(f"{bridge_id}_target", None)
            
            logger.info(f"Unregistered data bridge: {bridge_id}")
            return True
        return False
    
    def _create_connector(self, data_source: DataSource) -> DataConnector:
        """Create appropriate connector for data source."""
        if data_source.type == 'database':
            return DatabaseConnector(data_source.connection_config)
        elif data_source.type == 'api':
            return APIConnector(data_source.connection_config)
        elif data_source.type == 'file':
            return FileConnector(data_source.connection_config)
        else:
            raise DataBridgeError(f"Unsupported data source type: {data_source.type}")
    
    async def sync_data(self, bridge_id: str, query: Optional[str] = None) -> SyncResult:
        """
        Synchronize data between source and target.
        
        Args:
            bridge_id: Bridge identifier
            query: Optional query filter
            
        Returns:
            Synchronization result
        """
        bridge = self.bridges.get(bridge_id)
        if not bridge:
            raise DataBridgeError(f"Bridge not found: {bridge_id}")
        
        if not bridge.enabled:
            raise DataBridgeError(f"Bridge is disabled: {bridge_id}")
        
        start_time = timezone.now()
        self.total_syncs += 1
        
        # Initialize result
        result = SyncResult(
            bridge_id=bridge_id,
            success=False,
            records_processed=0,
            records_success=0,
            records_failed=0,
            records_skipped=0,
            start_time=start_time,
            end_time=start_time
        )
        
        try:
            # Get connectors
            source_connector = self.connectors.get(f"{bridge_id}_source")
            target_connector = self.connectors.get(f"{bridge_id}_target")
            
            if not source_connector or not target_connector:
                raise DataBridgeError(f"Connectors not available for bridge: {bridge_id}")
            
            # Connect to both data sources
            source_connected = await source_connector.connect()
            target_connected = await target_connector.connect()
            
            if not source_connected:
                raise DataBridgeConnectionError(f"Failed to connect to source: {bridge.source.name}")
            
            if not target_connected:
                raise DataBridgeConnectionError(f"Failed to connect to target: {bridge.target.name}")
            
            try:
                # Read data from source
                source_data = await source_connector.read_data(query, bridge.batch_size)
                result.records_processed = len(source_data)
                
                if not source_data:
                    result.warnings.append("No data found to sync")
                    result.success = True
                    return result
                
                # Transform and validate data
                transformed_data = []
                for record in source_data:
                    try:
                        # Apply field mappings
                        mapped_record = self._apply_field_mappings(record, bridge.field_mappings)
                        
                        # Validate data
                        validation_results = self.validator.validate_data(mapped_record, DataFormat.JSON)
                        
                        # Check for validation errors
                        validation_errors = [r for r in validation_results if not r.is_valid and r.severity.value == 'error']
                        if validation_errors:
                            result.records_failed += 1
                            result.errors.extend([f"Validation failed for record: {error.message}" for error in validation_errors])
                            continue
                        
                        transformed_data.append(mapped_record)
                        
                    except Exception as e:
                        result.records_failed += 1
                        result.errors.append(f"Record transformation failed: {str(e)}")
                
                # Write data to target
                if transformed_data:
                    written_count = await target_connector.write_data(transformed_data)
                    result.records_success = written_count
                    result.records_skipped = len(transformed_data) - written_count
                else:
                    result.warnings.append("No valid records to write")
                
                # Update statistics
                self.total_records_synced += result.records_success
                result.success = True
                self.successful_syncs += 1
                
                logger.info(f"Sync completed for {bridge_id}: {result.records_success}/{result.records_processed} records")
                
            finally:
                # Disconnect from data sources
                await source_connector.disconnect()
                await target_connector.disconnect()
                
        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            self.failed_syncs += 1
            logger.error(f"Sync failed for {bridge_id}: {e}")
        
        finally:
            result.end_time = timezone.now()
            
            # Store result
            self.sync_results.append(result)
            if len(self.sync_results) > self.max_sync_results:
                self.sync_results = self.sync_results[-self.max_sync_results:]
        
        return result
    
    def _apply_field_mappings(self, record: Dict[str, Any], mappings: List[DataMapping]) -> Dict[str, Any]:
        """Apply field mappings to record."""
        mapped_record = {}
        
        for mapping in mappings:
            source_value = record.get(mapping.source_field)
            
            # Check if required field is missing
            if mapping.required and source_value is None:
                if mapping.default_value is not None:
                    source_value = mapping.default_value
                else:
                    raise DataBridgeError(f"Required field missing: {mapping.source_field}")
            
            # Skip if field is None and not required
            if source_value is None and not mapping.required:
                continue
            
            # Apply transformation function
            if mapping.transform_func:
                try:
                    source_value = mapping.transform_func(source_value)
                except Exception as e:
                    raise DataBridgeTransformationError(f"Transformation failed for {mapping.source_field}: {e}")
            
            mapped_record[mapping.target_field] = source_value
        
        return mapped_record
    
    async def test_bridge(self, bridge_id: str) -> Dict[str, bool]:
        """Test bridge connections."""
        bridge = self.bridges.get(bridge_id)
        if not bridge:
            raise DataBridgeError(f"Bridge not found: {bridge_id}")
        
        source_connector = self.connectors.get(f"{bridge_id}_source")
        target_connector = self.connectors.get(f"{bridge_id}_target")
        
        results = {}
        
        if source_connector:
            results['source'] = await source_connector.test_connection()
        
        if target_connector:
            results['target'] = await target_connector.test_connection()
        
        return results
    
    def get_bridge(self, bridge_id: str) -> Optional[DataBridgeConfig]:
        """Get bridge configuration."""
        return self.bridges.get(bridge_id)
    
    def list_bridges(self, enabled_only: bool = False) -> List[DataBridgeConfig]:
        """List bridge configurations."""
        bridges = list(self.bridges.values())
        
        if enabled_only:
            bridges = [b for b in bridges if b.enabled]
        
        return bridges
    
    def get_sync_results(self, bridge_id: Optional[str] = None, limit: int = 50) -> List[SyncResult]:
        """Get synchronization results."""
        results = self.sync_results
        
        if bridge_id:
            results = [r for r in results if r.bridge_id == bridge_id]
        
        # Sort by end time (newest first)
        results.sort(key=lambda r: r.end_time, reverse=True)
        
        return results[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get data bridge statistics."""
        # Bridge status distribution
        status_counts = defaultdict(int)
        for bridge in self.bridges.values():
            status_counts['enabled' if bridge.enabled else 'disabled'] += 1
        
        # Sync results summary
        recent_results = self.sync_results[-100:]  # Last 100 results
        recent_success_rate = sum(1 for r in recent_results if r.success) / max(len(recent_results), 1) * 100
        
        return {
            'total_bridges': len(self.bridges),
            'enabled_bridges': len([b for b in self.bridges.values() if b.enabled]),
            'disabled_bridges': len([b for b in self.bridges.values() if not b.enabled]),
            'bridge_status_distribution': dict(status_counts),
            'total_syncs': self.total_syncs,
            'successful_syncs': self.successful_syncs,
            'failed_syncs': self.failed_syncs,
            'success_rate': (self.successful_syncs / max(self.total_syncs, 1)) * 100,
            'recent_success_rate': recent_success_rate,
            'total_records_synced': self.total_records_synced,
            'average_records_per_sync': self.total_records_synced / max(self.successful_syncs, 1),
            'sync_results_stored': len(self.sync_results)
        }
    
    def enable_bridge(self, bridge_id: str) -> bool:
        """Enable bridge."""
        bridge = self.bridges.get(bridge_id)
        if bridge:
            bridge.enabled = True
            bridge.updated_at = timezone.now()
            logger.info(f"Enabled bridge: {bridge_id}")
            return True
        return False
    
    def disable_bridge(self, bridge_id: str) -> bool:
        """Disable bridge."""
        bridge = self.bridges.get(bridge_id)
        if bridge:
            bridge.enabled = False
            bridge.updated_at = timezone.now()
            logger.info(f"Disabled bridge: {bridge_id}")
            return True
        return False
    
    async def cleanup(self) -> None:
        """Cleanup data bridge resources."""
        # Disconnect all connectors
        for connector in self.connectors.values():
            await connector.disconnect()
        
        # Clear data structures
        self.bridges.clear()
        self.connectors.clear()
        self.sync_results.clear()
        
        # Reset statistics
        self.total_syncs = 0
        self.successful_syncs = 0
        self.failed_syncs = 0
        self.total_records_synced = 0
        
        logger.info("DataBridge cleanup completed")


# Global data bridge instance
_data_bridge = None


def get_data_bridge() -> DataBridge:
    """Get global data bridge instance."""
    global _data_bridge
    if _data_bridge is None:
        _data_bridge = DataBridge()
    return _data_bridge


# Convenience functions
async def sync_bridge_data(bridge_id: str, query: Optional[str] = None) -> SyncResult:
    """
    Convenience function for synchronizing bridge data.
    
    Args:
        bridge_id: Bridge identifier
        query: Optional query filter
        
    Returns:
        Synchronization result
    """
    bridge = get_data_bridge()
    return await bridge.sync_data(bridge_id, query)


def register_data_bridge(name: str, source: DataSource, target: DataSource,
                      field_mappings: List[DataMapping], **kwargs) -> DataBridgeConfig:
    """
    Convenience function for registering data bridges.
    
    Args:
        name: Bridge name
        source: Data source
        target: Target data source
        field_mappings: Field mappings
        **kwargs: Additional configuration
        
    Returns:
        Bridge configuration
    """
    import uuid
    
    config = DataBridgeConfig(
        bridge_id=str(uuid.uuid4()),
        name=name,
        source=source,
        target=target,
        field_mappings=field_mappings,
        **kwargs
    )
    
    bridge = get_data_bridge()
    bridge.register_bridge(config)
    
    return config


def get_bridge_statistics() -> Dict[str, Any]:
    """
    Convenience function for getting bridge statistics.
    
    Returns:
        Bridge statistics
    """
    bridge = get_data_bridge()
    return bridge.get_statistics()
