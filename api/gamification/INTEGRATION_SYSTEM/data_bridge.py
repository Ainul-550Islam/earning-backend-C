"""
Data Bridge — Bridge for data synchronization and transfer.

This module provides data bridge capabilities for synchronizing
and transferring data between different systems and storage mechanisms.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Type
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future

from .integ_constants import ErrorCode, DEFAULT_BATCH_SIZE
from .integ_exceptions import (
    IntegrationError, ValidationError, TimeoutError,
    ConnectionError, DataCorruptionError
)
from .integ_signals import (
    sync_started, sync_completed, sync_failed,
    data_received, data_sent
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Bridge Types
# ---------------------------------------------------------------------------

class BridgeDirection(Enum):
    """Bridge direction enumeration."""
    UNIDIRECTIONAL = "unidirectional"
    BIDIRECTIONAL = "bidirectional"
    MULTI_DIRECTIONAL = "multi_directional"


class SyncMode(Enum):
    """Synchronization mode enumeration."""
    FULL_SYNC = "full_sync"
    INCREMENTAL_SYNC = "incremental_sync"
    REAL_TIME_SYNC = "real_time_sync"
    SCHEDULED_SYNC = "scheduled_sync"


class ConflictResolution(Enum):
    """Conflict resolution strategy enumeration."""
    SOURCE_WINS = "source_wins"
    TARGET_WINS = "target_wins"
    LATEST_WINS = "latest_wins"
    MANUAL_RESOLUTION = "manual_resolution"
    MERGE = "merge"


class DataFormat(Enum):
    """Data format enumeration."""
    JSON = "json"
    XML = "xml"
    CSV = "csv"
    BINARY = "binary"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Data Bridge Data Classes
# ---------------------------------------------------------------------------

@dataclass
class DataSource:
    """Data source configuration."""
    
    id: str
    name: str
    type: str  # database, file, api, etc.
    connection_config: Dict[str, Any]
    data_format: DataFormat = DataFormat.JSON
    read_only: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "connection_config": self.connection_config,
            "data_format": self.data_format.value,
            "read_only": self.read_only,
            "metadata": self.metadata
        }


@dataclass
class DataSink:
    """Data sink configuration."""
    
    id: str
    name: str
    type: str  # database, file, api, etc.
    connection_config: Dict[str, Any]
    data_format: DataFormat = DataFormat.JSON
    write_only: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "connection_config": self.connection_config,
            "data_format": self.data_format.value,
            "write_only": self.write_only,
            "metadata": self.metadata
        }


@dataclass
class DataBridgeConfig:
    """Data bridge configuration."""
    
    id: str
    name: str
    source: DataSource
    sink: DataSink
    direction: BridgeDirection = BridgeDirection.UNIDIRECTIONAL
    sync_mode: SyncMode = SyncMode.INCREMENTAL_SYNC
    conflict_resolution: ConflictResolution = ConflictResolution.SOURCE_WINS
    batch_size: int = DEFAULT_BATCH_SIZE
    sync_interval: Optional[float] = None  # seconds
    transformation_rules: List[Dict[str, Any]] = field(default_factory=list)
    filters: List[Dict[str, Any]] = field(default_factory=list)
    validation_rules: List[Dict[str, Any]] = field(default_factory=list)
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source.to_dict(),
            "sink": self.sink.to_dict(),
            "direction": self.direction.value,
            "sync_mode": self.sync_mode.value,
            "conflict_resolution": self.conflict_resolution.value,
            "batch_size": self.batch_size,
            "sync_interval": self.sync_interval,
            "transformation_rules": self.transformation_rules,
            "filters": self.filters,
            "validation_rules": self.validation_rules,
            "enabled": self.enabled,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class SyncResult:
    """Result of a synchronization operation."""
    
    bridge_id: str
    sync_id: str
    success: bool
    records_processed: int = 0
    records_transferred: int = 0
    records_failed: int = 0
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    execution_time: float = 0.0
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.records_processed == 0:
            return 1.0
        return self.records_transferred / self.records_processed
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "bridge_id": self.bridge_id,
            "sync_id": self.sync_id,
            "success": self.success,
            "records_processed": self.records_processed,
            "records_transferred": self.records_transferred,
            "records_failed": self.records_failed,
            "conflicts_detected": self.conflicts_detected,
            "conflicts_resolved": self.conflicts_resolved,
            "success_rate": self.success_rate,
            "execution_time": self.execution_time,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata
        }


@dataclass
class DataRecord:
    """Data record representation."""
    
    id: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    checksum: Optional[str] = None
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "checksum": self.checksum,
            "version": self.version,
            "metadata": self.metadata
        }
    
    def calculate_checksum(self) -> str:
        """Calculate SHA-256 checksum."""
        import hashlib
        import json
        
        # Create canonical JSON representation
        canonical_data = json.dumps(self.data, sort_keys=True, separators=(',', ':'))
        self.checksum = hashlib.sha256(canonical_data.encode('utf-8')).hexdigest()
        return self.checksum
    
    def verify_checksum(self) -> bool:
        """Verify data integrity."""
        if not self.checksum:
            return True
        
        original_checksum = self.checksum
        calculated_checksum = self.calculate_checksum()
        return original_checksum == calculated_checksum


# ---------------------------------------------------------------------------
# Abstract Data Connector
# ---------------------------------------------------------------------------

class BaseDataConnector(ABC):
    """Abstract base class for data connectors."""
    
    def __init__(self, config: Union[DataSource, DataSink]):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._connected = False
        self._lock = threading.RLock()
    
    @abstractmethod
    def connect(self) -> None:
        """Establish connection."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close connection."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected."""
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        pass


class SourceConnector(BaseDataConnector):
    """Abstract base class for source connectors."""
    
    @abstractmethod
    def read_records(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[DataRecord]:
        """Read records from source."""
        pass
    
    @abstractmethod
    def get_record_count(self) -> int:
        """Get total record count."""
        pass
    
    @abstractmethod
    def get_last_sync_time(self) -> Optional[datetime]:
        """Get last synchronization time."""
        pass
    
    @abstractmethod
    def update_last_sync_time(self, timestamp: datetime) -> None:
        """Update last synchronization time."""
        pass


class SinkConnector(BaseDataConnector):
    """Abstract base class for sink connectors."""
    
    @abstractmethod
    def write_records(self, records: List[DataRecord]) -> List[bool]:
        """Write records to sink."""
        pass
    
    @abstractmethod
    def update_records(self, records: List[DataRecord]) -> List[bool]:
        """Update records in sink."""
        pass
    
    @abstractmethod
    def delete_records(self, record_ids: List[str]) -> List[bool]:
        """Delete records from sink."""
        pass
    
    @abstractmethod
    def find_conflicts(self, records: List[DataRecord]) -> List[Dict[str, Any]]:
        """Find conflicting records."""
        pass


# ---------------------------------------------------------------------------
# Data Bridge Implementation
# ---------------------------------------------------------------------------

class DataBridge:
    """Data bridge for synchronizing data between sources and sinks."""
    
    def __init__(self, config: DataBridgeConfig):
        self.config = config
        self.source_connector: Optional[SourceConnector] = None
        self.sink_connector: Optional[SinkConnector] = None
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._lock = threading.RLock()
        self._sync_thread: Optional[threading.Thread] = None
        self._running = False
        self._last_sync: Optional[datetime] = None
    
    def initialize(self) -> None:
        """Initialize the data bridge."""
        try:
            # Create connectors
            self.source_connector = self._create_source_connector()
            self.sink_connector = self._create_sink_connector()
            
            # Connect to source and sink
            self.source_connector.connect()
            self.sink_connector.connect()
            
            self.logger.info(f"Data bridge initialized: {self.config.id}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize data bridge {self.config.id}: {e}")
            raise IntegrationError(f"Data bridge initialization failed: {e}")
    
    def start(self) -> None:
        """Start the data bridge."""
        if self._running:
            return
        
        self._running = True
        
        # Start scheduled sync if configured
        if self.config.sync_interval:
            self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
            self._sync_thread.start()
        
        self.logger.info(f"Data bridge started: {self.config.id}")
    
    def stop(self) -> None:
        """Stop the data bridge."""
        self._running = False
        
        if self._sync_thread:
            self._sync_thread.join(timeout=5.0)
        
        # Disconnect connectors
        if self.source_connector:
            self.source_connector.disconnect()
        
        if self.sink_connector:
            self.sink_connector.disconnect()
        
        self.logger.info(f"Data bridge stopped: {self.config.id}")
    
    def sync_data(self, sync_mode: Optional[SyncMode] = None) -> SyncResult:
        """Synchronize data between source and sink."""
        import uuid
        sync_id = str(uuid.uuid4())
        start_time = time.time()
        
        result = SyncResult(
            bridge_id=self.config.id,
            sync_id=sync_id,
            start_time=datetime.now(timezone.utc)
        )
        
        try:
            # Emit sync started signal
            sync_started.send(
                sender=self,
                integration_id=self.config.id,
                sync_type=sync_mode.value if sync_mode else self.config.sync_mode.value,
                sync_scope={"source": self.config.source.id, "sink": self.config.sink.id},
                timestamp=result.start_time
            )
            
            # Perform synchronization
            if self.config.direction == BridgeDirection.UNIDIRECTIONAL:
                result = self._sync_unidirectional(result, sync_mode)
            elif self.config.direction == BridgeDirection.BIDIRECTIONAL:
                result = self._sync_bidirectional(result, sync_mode)
            else:
                raise IntegrationError(f"Unsupported bridge direction: {self.config.direction}")
            
            # Update end time and execution time
            result.end_time = datetime.now(timezone.utc)
            result.execution_time = time.time() - start_time
            self._last_sync = result.end_time
            
            # Emit sync completed signal
            sync_completed.send(
                sender=self,
                integration_id=self.config.id,
                sync_type=sync_mode.value if sync_mode else self.config.sync_mode.value,
                sync_scope={"source": self.config.source.id, "sink": self.config.sink.id},
                result=result.to_dict(),
                timestamp=result.end_time
            )
            
            return result
            
        except Exception as e:
            result.end_time = datetime.now(timezone.utc)
            result.execution_time = time.time() - start_time
            result.success = False
            result.errors.append(str(e))
            
            # Emit sync failed signal
            sync_failed.send(
                sender=self,
                integration_id=self.config.id,
                sync_type=sync_mode.value if sync_mode else self.config.sync_mode.value,
                sync_scope={"source": self.config.source.id, "sink": self.config.sink.id},
                error=e,
                timestamp=result.end_time
            )
            
            self.logger.error(f"Sync failed for bridge {self.config.id}: {e}")
            return result
    
    def _sync_unidirectional(self, result: SyncResult, sync_mode: Optional[SyncMode]) -> SyncResult:
        """Perform unidirectional synchronization."""
        if not self.source_connector or not self.sink_connector:
            raise IntegrationError("Connectors not initialized")
        
        # Determine sync mode
        mode = sync_mode or self.config.sync_mode
        
        # Read records from source
        if mode == SyncMode.FULL_SYNC:
            records = self.source_connector.read_records()
        elif mode == SyncMode.INCREMENTAL_SYNC:
            last_sync = self.source_connector.get_last_sync_time()
            records = self._read_incremental_records(last_sync)
        else:
            raise IntegrationError(f"Unsupported sync mode: {mode}")
        
        result.records_processed = len(records)
        
        if not records:
            self.logger.info(f"No records to sync for bridge {self.config.id}")
            return result
        
        # Apply transformations
        transformed_records = self._apply_transformations(records)
        
        # Apply filters
        filtered_records = self._apply_filters(transformed_records)
        
        # Validate records
        validation_errors = self._validate_records(filtered_records)
        if validation_errors:
            result.errors.extend(validation_errors)
        
        # Find conflicts
        conflicts = self.sink_connector.find_conflicts(filtered_records)
        result.conflicts_detected = len(conflicts)
        
        # Resolve conflicts
        if conflicts:
            resolved_records = self._resolve_conflicts(filtered_records, conflicts)
            result.conflicts_resolved = len([c for c in conflicts if c.get("resolved", False)])
        else:
            resolved_records = filtered_records
        
        # Write records to sink
        batch_size = self.config.batch_size
        for i in range(0, len(resolved_records), batch_size):
            batch = resolved_records[i:i + batch_size]
            success_flags = self.sink_connector.write_records(batch)
            
            for j, success in enumerate(success_flags):
                if success:
                    result.records_transferred += 1
                else:
                    result.records_failed += 1
        
        # Update last sync time
        self.source_connector.update_last_sync_time(datetime.now(timezone.utc))
        
        result.success = result.records_failed == 0
        return result
    
    def _sync_bidirectional(self, result: SyncResult, sync_mode: Optional[SyncMode]) -> SyncResult:
        """Perform bidirectional synchronization."""
        # For bidirectional sync, we sync in both directions
        # This is a simplified implementation
        
        # Sync source to sink
        result1 = self._sync_unidirectional(result, sync_mode)
        
        # Swap connectors and sync sink to source
        temp_source = self.source_connector
        temp_sink = self.sink_connector
        
        self.source_connector = temp_sink  # type: ignore
        self.sink_connector = temp_source  # type: ignore
        
        try:
            result2 = self._sync_unidirectional(result1, sync_mode)
            
            # Combine results
            result.records_processed += result2.records_processed
            result.records_transferred += result2.records_transferred
            result.records_failed += result2.records_failed
            result.conflicts_detected += result2.conflicts_detected
            result.conflicts_resolved += result2.conflicts_resolved
            result.errors.extend(result2.errors)
            result.warnings.extend(result2.warnings)
            
        finally:
            # Restore original connectors
            self.source_connector = temp_source
            self.sink_connector = temp_sink
        
        result.success = result.records_failed == 0
        return result
    
    def _read_incremental_records(self, since: Optional[datetime]) -> List[DataRecord]:
        """Read incremental records since last sync."""
        if not since:
            return self.source_connector.read_records()
        
        # This would implement incremental reading based on timestamp
        # For now, we'll read all records and filter
        all_records = self.source_connector.read_records()
        return [record for record in all_records if record.timestamp > since]
    
    def _apply_transformations(self, records: List[DataRecord]) -> List[DataRecord]:
        """Apply transformation rules to records."""
        transformed_records = []
        
        for record in records:
            transformed_record = DataRecord(
                id=record.id,
                data=record.data.copy(),
                timestamp=record.timestamp,
                checksum=record.checksum,
                version=record.version,
                metadata=record.metadata.copy()
            )
            
            # Apply transformation rules
            for rule in self.config.transformation_rules:
                transformed_record = self._apply_transformation(transformed_record, rule)
            
            transformed_records.append(transformed_record)
        
        return transformed_records
    
    def _apply_transformation(self, record: DataRecord, rule: Dict[str, Any]) -> DataRecord:
        """Apply a single transformation rule."""
        transformation_type = rule.get("type")
        
        if transformation_type == "field_rename":
            old_field = rule.get("old_field")
            new_field = rule.get("new_field")
            if old_field in record.data:
                record.data[new_field] = record.data.pop(old_field)
        
        elif transformation_type == "field_add":
            field = rule.get("field")
            value = rule.get("value")
            record.data[field] = value
        
        elif transformation_type == "field_remove":
            field = rule.get("field")
            record.data.pop(field, None)
        
        elif transformation_type == "value_transform":
            field = rule.get("field")
            transform_func = rule.get("function")
            if field in record.data and callable(transform_func):
                record.data[field] = transform_func(record.data[field])
        
        return record
    
    def _apply_filters(self, records: List[DataRecord]) -> List[DataRecord]:
        """Apply filters to records."""
        filtered_records = []
        
        for record in records:
            include_record = True
            
            for filter_rule in self.config.filters:
                filter_type = filter_rule.get("type")
                
                if filter_type == "field_equals":
                    field = filter_rule.get("field")
                    value = filter_rule.get("value")
                    if record.data.get(field) != value:
                        include_record = False
                        break
                
                elif filter_type == "field_contains":
                    field = filter_rule.get("field")
                    value = filter_rule.get("value")
                    if value not in str(record.data.get(field, "")):
                        include_record = False
                        break
                
                elif filter_type == "timestamp_range":
                    start_time = filter_rule.get("start_time")
                    end_time = filter_rule.get("end_time")
                    if start_time and record.timestamp < start_time:
                        include_record = False
                        break
                    if end_time and record.timestamp > end_time:
                        include_record = False
                        break
            
            if include_record:
                filtered_records.append(record)
        
        return filtered_records
    
    def _validate_records(self, records: List[DataRecord]) -> List[str]:
        """Validate records."""
        errors = []
        
        for record in records:
            # Apply validation rules
            for validation_rule in self.config.validation_rules:
                validation_type = validation_rule.get("type")
                
                if validation_type == "required_field":
                    field = validation_rule.get("field")
                    if field not in record.data:
                        errors.append(f"Record {record.id}: Missing required field '{field}'")
                
                elif validation_type == "field_type":
                    field = validation_rule.get("field")
                    expected_type = validation_rule.get("expected_type")
                    if field in record.data and not isinstance(record.data[field], eval(expected_type)):
                        errors.append(f"Record {record.id}: Field '{field}' has wrong type")
                
                elif validation_type == "checksum":
                    if not record.verify_checksum():
                        errors.append(f"Record {record.id}: Checksum verification failed")
        
        return errors
    
    def _resolve_conflicts(self, records: List[DataRecord], conflicts: List[Dict[str, Any]]) -> List[DataRecord]:
        """Resolve conflicts between records."""
        resolved_records = []
        
        for record in records:
            conflict = next((c for c in conflicts if c.get("record_id") == record.id), None)
            
            if conflict:
                resolution = self._resolve_single_conflict(record, conflict)
                if resolution:
                    resolved_records.append(resolution)
                    conflict["resolved"] = True
                else:
                    conflict["resolved"] = False
            else:
                resolved_records.append(record)
        
        return resolved_records
    
    def _resolve_single_conflict(self, record: DataRecord, conflict: Dict[str, Any]) -> Optional[DataRecord]:
        """Resolve a single conflict."""
        resolution_strategy = self.config.conflict_resolution
        
        if resolution_strategy == ConflictResolution.SOURCE_WINS:
            return record
        
        elif resolution_strategy == ConflictResolution.TARGET_WINS:
            # Return the existing record from sink
            return None
        
        elif resolution_strategy == ConflictResolution.LATEST_WINS:
            existing_timestamp = conflict.get("existing_timestamp")
            if existing_timestamp and record.timestamp > existing_timestamp:
                return record
            else:
                return None
        
        elif resolution_strategy == ConflictResolution.MERGE:
            # Merge data (simplified implementation)
            existing_data = conflict.get("existing_data", {})
            merged_data = existing_data.copy()
            merged_data.update(record.data)
            
            merged_record = DataRecord(
                id=record.id,
                data=merged_data,
                timestamp=max(record.timestamp, existing_timestamp),
                version=record.version + 1
            )
            return merged_record
        
        return record
    
    def _sync_loop(self) -> None:
        """Main synchronization loop for scheduled sync."""
        while self._running:
            try:
                # Check if it's time to sync
                if self._should_sync():
                    self.sync_data()
                
                # Wait for next sync interval
                time.sleep(self.config.sync_interval or 60)
                
            except Exception as e:
                self.logger.error(f"Error in sync loop: {e}")
                time.sleep(10)  # Wait before retrying
    
    def _should_sync(self) -> bool:
        """Check if synchronization should run."""
        if not self._last_sync:
            return True
        
        if self.config.sync_interval:
            time_since_last_sync = (datetime.now(timezone.utc) - self._last_sync).total_seconds()
            return time_since_last_sync >= self.config.sync_interval
        
        return False
    
    def _create_source_connector(self) -> SourceConnector:
        """Create source connector based on configuration."""
        # This would create actual connectors based on source type
        # For now, we'll return a mock connector
        
        class MockSourceConnector(SourceConnector):
            def connect(self):
                self._connected = True
            
            def disconnect(self):
                self._connected = False
            
            def is_connected(self):
                return self._connected
            
            def health_check(self):
                return {"status": "healthy"}
            
            def read_records(self, limit=None, offset=None):
                return []
            
            def get_record_count(self):
                return 0
            
            def get_last_sync_time(self):
                return None
            
            def update_last_sync_time(self, timestamp):
                pass
        
        return MockSourceConnector(self.config.source)
    
    def _create_sink_connector(self) -> SinkConnector:
        """Create sink connector based on configuration."""
        # This would create actual connectors based on sink type
        # For now, we'll return a mock connector
        
        class MockSinkConnector(SinkConnector):
            def connect(self):
                self._connected = True
            
            def disconnect(self):
                self._connected = False
            
            def is_connected(self):
                return self._connected
            
            def health_check(self):
                return {"status": "healthy"}
            
            def write_records(self, records):
                return [True] * len(records)
            
            def update_records(self, records):
                return [True] * len(records)
            
            def delete_records(self, record_ids):
                return [True] * len(record_ids)
            
            def find_conflicts(self, records):
                return []
        
        return MockSinkConnector(self.config.sink)
    
    def get_status(self) -> Dict[str, Any]:
        """Get bridge status."""
        return {
            "bridge_id": self.config.id,
            "name": self.config.name,
            "enabled": self.config.enabled,
            "running": self._running,
            "source_connected": self.source_connector.is_connected() if self.source_connector else False,
            "sink_connected": self.sink_connector.is_connected() if self.sink_connector else False,
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "config": self.config.to_dict()
        }


# ---------------------------------------------------------------------------
# Data Bridge Manager
# ---------------------------------------------------------------------------

class DataBridgeManager:
    """Manager for multiple data bridges."""
    
    def __init__(self):
        self.bridges: Dict[str, DataBridge] = {}
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
    
    def register_bridge(self, bridge: DataBridge) -> None:
        """Register a data bridge."""
        with self._lock:
            if bridge.config.id in self.bridges:
                raise IntegrationError(f"Data bridge with ID '{bridge.config.id}' already exists")
            
            self.bridges[bridge.config.id] = bridge
            self.logger.info(f"Registered data bridge: {bridge.config.id}")
    
    def unregister_bridge(self, bridge_id: str) -> bool:
        """Unregister a data bridge."""
        with self._lock:
            if bridge_id in self.bridges:
                bridge = self.bridges[bridge_id]
                if bridge._running:
                    bridge.stop()
                del self.bridges[bridge_id]
                self.logger.info(f"Unregistered data bridge: {bridge_id}")
                return True
            return False
    
    def get_bridge(self, bridge_id: str) -> Optional[DataBridge]:
        """Get a bridge by ID."""
        with self._lock:
            return self.bridges.get(bridge_id)
    
    def list_bridges(self) -> List[DataBridge]:
        """List all bridges."""
        with self._lock:
            return list(self.bridges.values())
    
    def start_bridge(self, bridge_id: str) -> bool:
        """Start a bridge."""
        bridge = self.get_bridge(bridge_id)
        if not bridge:
            raise IntegrationNotFoundError(f"Data bridge '{bridge_id}' not found")
        
        try:
            bridge.start()
            return True
        except Exception as e:
            self.logger.error(f"Failed to start bridge {bridge_id}: {e}")
            return False
    
    def stop_bridge(self, bridge_id: str) -> bool:
        """Stop a bridge."""
        bridge = self.get_bridge(bridge_id)
        if not bridge:
            raise IntegrationNotFoundError(f"Data bridge '{bridge_id}' not found")
        
        try:
            bridge.stop()
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop bridge {bridge_id}: {e}")
            return False
    
    def sync_bridge(self, bridge_id: str, sync_mode: Optional[SyncMode] = None) -> SyncResult:
        """Synchronize a specific bridge."""
        bridge = self.get_bridge(bridge_id)
        if not bridge:
            raise IntegrationNotFoundError(f"Data bridge '{bridge_id}' not found")
        
        return bridge.sync_data(sync_mode)
    
    def sync_all_bridges(self, sync_mode: Optional[SyncMode] = None) -> Dict[str, SyncResult]:
        """Synchronize all bridges."""
        results = {}
        
        for bridge_id, bridge in self.bridges.items():
            try:
                results[bridge_id] = bridge.sync_data(sync_mode)
            except Exception as e:
                results[bridge_id] = SyncResult(
                    bridge_id=bridge_id,
                    sync_id="",
                    success=False,
                    errors=[str(e)]
                )
        
        return results
    
    def get_all_status(self) -> Dict[str, Any]:
        """Get status of all bridges."""
        status = {}
        
        for bridge_id, bridge in self.bridges.items():
            try:
                status[bridge_id] = bridge.get_status()
            except Exception as e:
                status[bridge_id] = {"error": str(e)}
        
        return {
            "bridges": status,
            "total_bridges": len(self.bridges),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def shutdown_all(self) -> None:
        """Shutdown all bridges."""
        for bridge_id, bridge in self.bridges.items():
            try:
                if bridge._running:
                    bridge.stop()
            except Exception as e:
                self.logger.error(f"Error stopping bridge '{bridge_id}': {e}")
        
        self.logger.info("All data bridges shutdown")


# Global data bridge manager instance
data_bridge_manager = DataBridgeManager()


# Initialize logging
logger.info("Data bridge module initialized")
