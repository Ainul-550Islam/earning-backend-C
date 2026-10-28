# engagement/integration_system/data_bridge.py
"""
Data bridge system for integration data flow.
Provides bidirectional data synchronization and transformation.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable, Iterator
from dataclasses import dataclass, field
from enum import Enum
import logging
import threading
import time
from datetime import datetime, timedelta
from collections import defaultdict

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.db import transaction
from django.db.models import Q

from .integ_constants import (
    IntegrationType, DataType, ERROR_CODES, SUCCESS_CODES,
    DEFAULT_CONFIG, CACHE_KEYS
)
from .transformer import transformer_manager, TransformationContext
from .event_bus import event_bus, Event, EventType, EventBuilder

logger = logging.getLogger(__name__)


class BridgeDirection(Enum):
    """Bridge direction types."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    BIDIRECTIONAL = "bidirectional"


class SyncMode(Enum):
    """Synchronization modes."""
    REAL_TIME = "real_time"
    BATCH = "batch"
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    EVENT_DRIVEN = "event_driven"


class DataStatus(Enum):
    """Data status types."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"
    SYNCHRONIZED = "synchronized"


@dataclass
class DataBridgeConfig:
    """Data bridge configuration."""
    id: str
    name: str
    source_system: str
    target_system: str
    direction: BridgeDirection
    sync_mode: SyncMode
    source_config: Dict[str, Any] = field(default_factory=dict)
    target_config: Dict[str, Any] = field(default_factory=dict)
    transformation_rules: List[Dict[str, Any]] = field(default_factory=list)
    validation_rules: List[Dict[str, Any]] = field(default_factory=list)
    conflict_resolution: str = "source_wins"  # source_wins, target_wins, manual, timestamp
    batch_size: int = 100
    sync_interval: int = 300  # seconds
    retry_count: int = 3
    retry_delay: int = 60
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=timezone.now)
    updated_at: datetime = field(default_factory=timezone.now)
    last_sync: Optional[datetime] = None
    sync_count: int = 0
    error_count: int = 0


@dataclass
class DataRecord:
    """Data record for bridging."""
    id: str
    source_id: str
    target_id: Optional[str]
    data: Dict[str, Any]
    status: DataStatus = DataStatus.PENDING
    created_at: datetime = field(default_factory=timezone.now)
    updated_at: datetime = field(default_factory=timezone.now)
    synced_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncResult:
    """Synchronization result."""
    success: bool
    records_processed: int = 0
    records_synchronized: int = 0
    records_failed: int = 0
    records_conflicted: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duration_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseDataBridge(ABC):
    """Base data bridge class."""
    
    def __init__(self, config: DataBridgeConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{config.name}")
        self._is_running = False
        self._lock = threading.RLock()
        self._sync_thread = None
        self._records: Dict[str, DataRecord] = {}
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to source and target systems."""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from systems."""
        pass
    
    @abstractmethod
    def fetch_data(self, since: Optional[datetime] = None) -> Iterator[DataRecord]:
        """Fetch data from source system."""
        pass
    
    @abstractmethod
    def push_data(self, records: List[DataRecord]) -> SyncResult:
        """Push data to target system."""
        pass
    
    @abstractmethod
    def detect_conflicts(self, records: List[DataRecord]) -> List[DataRecord]:
        """Detect data conflicts."""
        pass
    
    @abstractmethod
    def resolve_conflicts(self, records: List[DataRecord]) -> List[DataRecord]:
        """Resolve data conflicts."""
        pass
    
    def start_sync(self) -> bool:
        """Start synchronization."""
        try:
            with self._lock:
                if self._is_running:
                    return False
                
                self._is_running = True
                self._sync_thread = threading.Thread(target=self._sync_worker, daemon=True)
                self._sync_thread.start()
                
                self.logger.info(f"Started synchronization for bridge {self.config.name}")
                return True
                
        except Exception as exc:
            self.logger.error(f"Failed to start synchronization: {exc}")
            return False
    
    def stop_sync(self) -> bool:
        """Stop synchronization."""
        try:
            with self._lock:
                self._is_running = False
                if self._sync_thread:
                    self._sync_thread.join(timeout=10)
                
                self.logger.info(f"Stopped synchronization for bridge {self.config.name}")
                return True
                
        except Exception as exc:
            self.logger.error(f"Failed to stop synchronization: {exc}")
            return False
    
    def sync_now(self) -> SyncResult:
        """Perform immediate synchronization."""
        start_time = time.time()
        
        try:
            # Fetch data
            records = list(self.fetch_data(self.config.last_sync))
            
            if not records:
                return SyncResult(
                    success=True,
                    records_processed=0,
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            # Transform data
            transformed_records = self._transform_records(records)
            
            # Detect conflicts
            conflicted_records = self.detect_conflicts(transformed_records)
            
            # Resolve conflicts
            resolved_records = self.resolve_conflicts(conflicted_records)
            
            # Push data
            result = self.push_data(resolved_records)
            
            # Update sync time
            self.config.last_sync = timezone.now()
            self.config.sync_count += 1
            
            result.duration_ms = int((time.time() - start_time) * 1000)
            
            return result
            
        except Exception as exc:
            self.logger.error(f"Synchronization failed: {exc}")
            self.config.error_count += 1
            
            return SyncResult(
                success=False,
                errors=[str(exc)],
                duration_ms=int((time.time() - start_time) * 1000)
            )
    
    def _sync_worker(self):
        """Worker thread for scheduled synchronization."""
        while self._is_running:
            try:
                if self.config.sync_mode == SyncMode.SCHEDULED:
                    result = self.sync_now()
                    
                    if not result.success:
                        self.logger.error(f"Scheduled sync failed: {result.errors}")
                
                # Wait for next sync
                time.sleep(self.config.sync_interval)
                
            except Exception as exc:
                self.logger.error(f"Sync worker error: {exc}")
                time.sleep(self.config.retry_delay)
    
    def _transform_records(self, records: List[DataRecord]) -> List[DataRecord]:
        """Transform records using transformation rules."""
        if not self.config.transformation_rules:
            return records
        
        transformed_records = []
        
        for record in records:
            try:
                # Create transformation context
                context = TransformationContext(
                    source_format=DataType.JSON,
                    target_format=DataType.JSON,
                    rules=[],
                    metadata={'record_id': record.id}
                )
                
                # Transform data
                transform_result = transformer_manager.transform(
                    record.data,
                    DataType.JSON,
                    DataType.JSON,
                    rules=self.config.transformation_rules
                )
                
                if transform_result['success']:
                    record.data = transform_result['data']
                    transformed_records.append(record)
                else:
                    self.logger.warning(f"Failed to transform record {record.id}: {transform_result.get('error')}")
                    record.status = DataStatus.FAILED
                    record.error_message = transform_result.get('error', 'Transformation failed')
                    transformed_records.append(record)
                    
            except Exception as exc:
                self.logger.error(f"Error transforming record {record.id}: {exc}")
                record.status = DataStatus.FAILED
                record.error_message = str(exc)
                transformed_records.append(record)
        
        return transformed_records
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        with self._lock:
            total_records = len(self._records)
            status_counts = defaultdict(int)
            
            for record in self._records.values():
                status_counts[record.status.value] += 1
            
            return {
                'bridge_id': self.config.id,
                'bridge_name': self.config.name,
                'is_running': self._is_running,
                'total_records': total_records,
                'status_counts': dict(status_counts),
                'sync_count': self.config.sync_count,
                'error_count': self.config.error_count,
                'last_sync': self.config.last_sync.isoformat() if self.config.last_sync else None,
                'last_updated': timezone.now().isoformat()
            }


class DatabaseToApiBridge(BaseDataBridge):
    """Bridge from database to API."""
    
    def connect(self) -> bool:
        """Connect to database and API."""
        try:
            # Test database connection
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            # Test API connection
            import requests
            test_url = self.config.source_config.get('test_url')
            if test_url:
                response = requests.get(test_url, timeout=10)
                if response.status_code >= 400:
                    raise Exception(f"API test failed: {response.status_code}")
            
            return True
            
        except Exception as exc:
            self.logger.error(f"DatabaseToApiBridge connection failed: {exc}")
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from systems."""
        return True
    
    def fetch_data(self, since: Optional[datetime] = None) -> Iterator[DataRecord]:
        """Fetch data from database."""
        try:
            from django.db import models
            
            # Get model class from config
            model_path = self.config.source_config.get('model')
            if not model_path:
                raise ValueError("Model not specified in source config")
            
            module_path, model_name = model_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[model_name])
            model_class = getattr(module, model_name)
            
            # Build query
            queryset = model_class.objects.all()
            
            if since:
                queryset = queryset.filter(updated_at__gte=since)
            
            # Apply filters
            filters = self.config.source_config.get('filters', {})
            for field, value in filters.items():
                if hasattr(model_class, field):
                    queryset = queryset.filter(**{field: value})
            
            # Order by updated_at
            if hasattr(model_class, 'updated_at'):
                queryset = queryset.order_by('updated_at')
            
            # Yield records
            for obj in queryset:
                data = {}
                for field in obj._meta.fields:
                    value = getattr(obj, field.name, None)
                    if value is not None:
                        if hasattr(value, 'isoformat'):
                            data[field.name] = value.isoformat()
                        else:
                            data[field.name] = str(value)
                
                yield DataRecord(
                    id=f"db_{obj.pk}",
                    source_id=str(obj.pk),
                    data=data,
                    metadata={'model': model_path, 'pk': obj.pk}
                )
                
        except Exception as exc:
            self.logger.error(f"Failed to fetch data from database: {exc}")
            raise
    
    def push_data(self, records: List[DataRecord]) -> SyncResult:
        """Push data to API."""
        result = SyncResult(success=True)
        start_time = time.time()
        
        try:
            import requests
            
            api_url = self.config.target_config.get('url')
            api_method = self.config.target_config.get('method', 'POST')
            api_headers = self.config.target_config.get('headers', {})
            
            # Process records in batches
            batch_size = self.config.batch_size
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                
                try:
                    # Prepare batch data
                    batch_data = {
                        'records': [record.data for record in batch],
                        'metadata': {
                            'bridge_id': self.config.id,
                            'timestamp': timezone.now().isoformat()
                        }
                    }
                    
                    # Send to API
                    if api_method == 'POST':
                        response = requests.post(
                            api_url,
                            json=batch_data,
                            headers=api_headers,
                            timeout=self.config.retry_delay
                        )
                    elif api_method == 'PUT':
                        response = requests.put(
                            api_url,
                            json=batch_data,
                            headers=api_headers,
                            timeout=self.config.retry_delay
                        )
                    else:
                        raise ValueError(f"Unsupported API method: {api_method}")
                    
                    if response.status_code >= 400:
                        raise Exception(f"API request failed: {response.status_code}")
                    
                    # Update records
                    for record in batch:
                        record.status = DataStatus.COMPLETED
                        record.synced_at = timezone.now()
                        result.records_synchronized += 1
                    
                    result.records_processed += len(batch)
                    
                except Exception as exc:
                    self.logger.error(f"Failed to push batch {i//batch_size + 1}: {exc}")
                    
                    for record in batch:
                        record.status = DataStatus.FAILED
                        record.error_message = str(exc)
                        result.records_failed += 1
                    
                    result.errors.append(f"Batch {i//batch_size + 1} failed: {exc}")
            
            result.duration_ms = int((time.time() - start_time) * 1000)
            return result
            
        except Exception as exc:
            self.logger.error(f"Failed to push data to API: {exc}")
            result.success = False
            result.errors.append(str(exc))
            result.duration_ms = int((time.time() - start_time) * 1000)
            return result
    
    def detect_conflicts(self, records: List[DataRecord]) -> List[DataRecord]:
        """Detect conflicts in records."""
        conflicted_records = []
        
        try:
            import requests
            
            conflict_check_url = self.config.target_config.get('conflict_check_url')
            if not conflict_check_url:
                return conflicted_records
            
            for record in records:
                try:
                    # Check for existing record
                    check_data = {
                        'source_id': record.source_id,
                        'bridge_id': self.config.id
                    }
                    
                    response = requests.post(
                        conflict_check_url,
                        json=check_data,
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        conflict_data = response.json()
                        if conflict_data.get('exists', False):
                            record.status = DataStatus.CONFLICT
                            record.metadata['conflict_data'] = conflict_data
                            conflicted_records.append(record)
                    
                except Exception as exc:
                    self.logger.warning(f"Conflict check failed for record {record.id}: {exc}")
            
        except Exception as exc:
            self.logger.error(f"Conflict detection failed: {exc}")
        
        return conflicted_records
    
    def resolve_conflicts(self, records: List[DataRecord]) -> List[DataRecord]:
        """Resolve conflicts in records."""
        resolved_records = []
        
        for record in records:
            if record.status != DataStatus.CONFLICT:
                resolved_records.append(record)
                continue
            
            try:
                resolution_strategy = self.config.conflict_resolution
                
                if resolution_strategy == 'source_wins':
                    # Keep source data
                    record.status = DataStatus.COMPLETED
                    record.metadata['conflict_resolution'] = 'source_wins'
                elif resolution_strategy == 'target_wins':
                    # Skip source data
                    record.status = DataStatus.COMPLETED
                    record.metadata['conflict_resolution'] = 'target_wins'
                elif resolution_strategy == 'timestamp':
                    # Use timestamp comparison
                    conflict_data = record.metadata.get('conflict_data', {})
                    target_timestamp = conflict_data.get('updated_at')
                    source_timestamp = record.data.get('updated_at')
                    
                    if target_timestamp and source_timestamp:
                        try:
                            target_dt = datetime.fromisoformat(target_timestamp)
                            source_dt = datetime.fromisoformat(source_timestamp)
                            
                            if source_dt > target_dt:
                                record.status = DataStatus.COMPLETED
                                record.metadata['conflict_resolution'] = 'source_newer'
                            else:
                                record.status = DataStatus.COMPLETED
                                record.metadata['conflict_resolution'] = 'target_newer'
                        except Exception:
                            record.status = DataStatus.COMPLETED
                            record.metadata['conflict_resolution'] = 'timestamp_error'
                    else:
                        record.status = DataStatus.COMPLETED
                        record.metadata['conflict_resolution'] = 'no_timestamp'
                else:
                    # Default to source_wins
                    record.status = DataStatus.COMPLETED
                    record.metadata['conflict_resolution'] = 'default_source_wins'
                
                resolved_records.append(record)
                
            except Exception as exc:
                self.logger.error(f"Failed to resolve conflict for record {record.id}: {exc}")
                record.status = DataStatus.FAILED
                record.error_message = str(exc)
                resolved_records.append(record)
        
        return resolved_records


class ApiToDatabaseBridge(BaseDataBridge):
    """Bridge from API to database."""
    
    def connect(self) -> bool:
        """Connect to API and database."""
        try:
            # Test API connection
            import requests
            test_url = self.config.source_config.get('test_url')
            if test_url:
                response = requests.get(test_url, timeout=10)
                if response.status_code >= 400:
                    raise Exception(f"API test failed: {response.status_code}")
            
            # Test database connection
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            return True
            
        except Exception as exc:
            self.logger.error(f"ApiToDatabaseBridge connection failed: {exc}")
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from systems."""
        return True
    
    def fetch_data(self, since: Optional[datetime] = None) -> Iterator[DataRecord]:
        """Fetch data from API."""
        try:
            import requests
            
            api_url = self.config.source_config.get('url')
            api_method = self.config.source_config.get('method', 'GET')
            api_headers = self.config.source_config.get('headers', {})
            
            # Prepare request parameters
            params = {}
            if since:
                params['since'] = since.isoformat()
            
            # Add filters
            filters = self.config.source_config.get('filters', {})
            params.update(filters)
            
            # Make request
            if api_method == 'GET':
                response = requests.get(
                    api_url,
                    params=params,
                    headers=api_headers,
                    timeout=30
                )
            else:
                response = requests.post(
                    api_url,
                    json=params,
                    headers=api_headers,
                    timeout=30
                )
            
            if response.status_code >= 400:
                raise Exception(f"API request failed: {response.status_code}")
            
            # Parse response
            data = response.json()
            records = data.get('records', data) if isinstance(data, dict) else data
            
            for record_data in records:
                yield DataRecord(
                    id=f"api_{record_data.get('id', hash(str(record_data)))}",
                    source_id=str(record_data.get('id', '')),
                    data=record_data,
                    metadata={'source': 'api'}
                )
                
        except Exception as exc:
            self.logger.error(f"Failed to fetch data from API: {exc}")
            raise
    
    def push_data(self, records: List[DataRecord]) -> SyncResult:
        """Push data to database."""
        result = SyncResult(success=True)
        start_time = time.time()
        
        try:
            # Get model class from config
            model_path = self.config.target_config.get('model')
            if not model_path:
                raise ValueError("Model not specified in target config")
            
            module_path, model_name = model_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[model_name])
            model_class = getattr(module, model_name)
            
            # Process records
            for record in records:
                try:
                    # Find existing record
                    existing_obj = None
                    if record.source_id:
                        filter_field = self.config.target_config.get('source_id_field', 'source_id')
                        existing_obj = model_class.objects.filter(**{filter_field: record.source_id}).first()
                    
                    if existing_obj:
                        # Update existing record
                        for field, value in record.data.items():
                            if hasattr(existing_obj, field):
                                setattr(existing_obj, field, value)
                        existing_obj.updated_at = timezone.now()
                        existing_obj.save()
                        
                        record.target_id = str(existing_obj.pk)
                    else:
                        # Create new record
                        obj_data = record.data.copy()
                        obj_data[self.config.target_config.get('source_id_field', 'source_id')] = record.source_id
                        
                        obj = model_class(**obj_data)
                        obj.save()
                        
                        record.target_id = str(obj.pk)
                    
                    record.status = DataStatus.COMPLETED
                    record.synced_at = timezone.now()
                    result.records_synchronized += 1
                    
                except Exception as exc:
                    self.logger.error(f"Failed to save record {record.id}: {exc}")
                    record.status = DataStatus.FAILED
                    record.error_message = str(exc)
                    result.records_failed += 1
                    result.errors.append(f"Record {record.id} failed: {exc}")
                
                result.records_processed += 1
            
            result.duration_ms = int((time.time() - start_time) * 1000)
            return result
            
        except Exception as exc:
            self.logger.error(f"Failed to push data to database: {exc}")
            result.success = False
            result.errors.append(str(exc))
            result.duration_ms = int((time.time() - start_time) * 1000)
            return result
    
    def detect_conflicts(self, records: List[DataRecord]) -> List[DataRecord]:
        """Detect conflicts in records."""
        conflicted_records = []
        
        try:
            # Get model class from config
            model_path = self.config.target_config.get('model')
            if not model_path:
                return conflicted_records
            
            module_path, model_name = model_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[model_name])
            model_class = getattr(module, model_name)
            
            source_id_field = self.config.target_config.get('source_id_field', 'source_id')
            
            for record in records:
                if record.source_id:
                    existing_obj = model_class.objects.filter(**{source_id_field: record.source_id}).first()
                    
                    if existing_obj:
                        # Check if data has changed
                        has_changes = False
                        for field, value in record.data.items():
                            if hasattr(existing_obj, field):
                                existing_value = getattr(existing_obj, field)
                                if str(existing_value) != str(value):
                                    has_changes = True
                                    break
                        
                        if has_changes:
                            record.status = DataStatus.CONFLICT
                            record.metadata['existing_data'] = {
                                field: str(getattr(existing_obj, field))
                                for field in record.data.keys()
                                if hasattr(existing_obj, field)
                            }
                            conflicted_records.append(record)
            
        except Exception as exc:
            self.logger.error(f"Conflict detection failed: {exc}")
        
        return conflicted_records
    
    def resolve_conflicts(self, records: List[DataRecord]) -> List[DataRecord]:
        """Resolve conflicts in records."""
        resolved_records = []
        
        for record in records:
            if record.status != DataStatus.CONFLICT:
                resolved_records.append(record)
                continue
            
            try:
                resolution_strategy = self.config.conflict_resolution
                
                if resolution_strategy == 'source_wins':
                    # Keep source data
                    record.status = DataStatus.COMPLETED
                    record.metadata['conflict_resolution'] = 'source_wins'
                elif resolution_strategy == 'target_wins':
                    # Skip source data
                    record.status = DataStatus.COMPLETED
                    record.metadata['conflict_resolution'] = 'target_wins'
                elif resolution_strategy == 'merge':
                    # Merge data (simplified)
                    existing_data = record.metadata.get('existing_data', {})
                    merged_data = record.data.copy()
                    
                    for field, value in existing_data.items():
                        if field not in merged_data:
                            merged_data[field] = value
                    
                    record.data = merged_data
                    record.status = DataStatus.COMPLETED
                    record.metadata['conflict_resolution'] = 'merged'
                else:
                    # Default to source_wins
                    record.status = DataStatus.COMPLETED
                    record.metadata['conflict_resolution'] = 'default_source_wins'
                
                resolved_records.append(record)
                
            except Exception as exc:
                self.logger.error(f"Failed to resolve conflict for record {record.id}: {exc}")
                record.status = DataStatus.FAILED
                record.error_message = str(exc)
                resolved_records.append(record)
        
        return resolved_records


class DataBridgeManager:
    """Manager for data bridges."""
    
    def __init__(self):
        self.bridges: Dict[str, BaseDataBridge] = {}
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.DataBridgeManager")
    
    def register_bridge(self, bridge: BaseDataBridge) -> bool:
        """Register a data bridge."""
        try:
            with self._lock:
                if bridge.config.id in self.bridges:
                    self.logger.warning(f"Bridge {bridge.config.id} already registered, updating...")
                    self.unregister_bridge(bridge.config.id)
                
                # Connect bridge
                if not bridge.connect():
                    self.logger.error(f"Failed to connect bridge {bridge.config.id}")
                    return False
                
                self.bridges[bridge.config.id] = bridge
                
                self.logger.info(f"Registered data bridge: {bridge.config.id}")
                return True
                
        except Exception as exc:
            self.logger.error(f"Failed to register bridge {bridge.config.id}: {exc}")
            return False
    
    def unregister_bridge(self, bridge_id: str) -> bool:
        """Unregister a data bridge."""
        try:
            with self._lock:
                if bridge_id in self.bridges:
                    bridge = self.bridges[bridge_id]
                    bridge.stop_sync()
                    bridge.disconnect()
                    del self.bridges[bridge_id]
                    
                    self.logger.info(f"Unregistered data bridge: {bridge_id}")
                    return True
        except Exception as exc:
            self.logger.error(f"Failed to unregister bridge {bridge_id}: {exc}")
        return False
    
    def start_bridge(self, bridge_id: str) -> bool:
        """Start bridge synchronization."""
        bridge = self.bridges.get(bridge_id)
        if not bridge:
            return False
        
        return bridge.start_sync()
    
    def stop_bridge(self, bridge_id: str) -> bool:
        """Stop bridge synchronization."""
        bridge = self.bridges.get(bridge_id)
        if not bridge:
            return False
        
        return bridge.stop_sync()
    
    def sync_bridge(self, bridge_id: str) -> SyncResult:
        """Synchronize bridge immediately."""
        bridge = self.bridges.get(bridge_id)
        if not bridge:
            return SyncResult(success=False, errors=[f"Bridge {bridge_id} not found"])
        
        return bridge.sync_now()
    
    def get_bridge(self, bridge_id: str) -> Optional[BaseDataBridge]:
        """Get bridge by ID."""
        return self.bridges.get(bridge_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics for all bridges."""
        with self._lock:
            total_bridges = len(self.bridges)
            running_bridges = sum(1 for b in self.bridges.values() if b._is_running)
            
            bridge_stats = {}
            for bridge_id, bridge in self.bridges.items():
                bridge_stats[bridge_id] = bridge.get_statistics()
            
            return {
                'total_bridges': total_bridges,
                'running_bridges': running_bridges,
                'bridge_statistics': bridge_stats,
                'last_updated': timezone.now().isoformat()
            }
    
    def start_all(self) -> int:
        """Start all bridges."""
        started_count = 0
        
        for bridge_id, bridge in self.bridges.items():
            if bridge.start_sync():
                started_count += 1
        
        self.logger.info(f"Started {started_count} bridges")
        return started_count
    
    def stop_all(self) -> int:
        """Stop all bridges."""
        stopped_count = 0
        
        for bridge_id, bridge in self.bridges.items():
            if bridge.stop_sync():
                stopped_count += 1
        
        self.logger.info(f"Stopped {stopped_count} bridges")
        return stopped_count


class DataBridgeFactory:
    """Factory for creating data bridges."""
    
    @staticmethod
    def create_database_to_api_bridge(config: DataBridgeConfig) -> DatabaseToApiBridge:
        """Create database to API bridge."""
        return DatabaseToApiBridge(config)
    
    @staticmethod
    def create_api_to_database_bridge(config: DataBridgeConfig) -> ApiToDatabaseBridge:
        """Create API to database bridge."""
        return ApiToDatabaseBridge(config)
    
    @staticmethod
    def create_bridge(config: DataBridgeConfig) -> BaseDataBridge:
        """Create bridge based on configuration."""
        if config.source_system == 'database' and config.target_system == 'api':
            return DatabaseToApiBridge(config)
        elif config.source_system == 'api' and config.target_system == 'database':
            return ApiToDatabaseBridge(config)
        else:
            raise ValueError(f"Unsupported bridge type: {config.source_system} -> {config.target_system}")


# Global data bridge manager instance
data_bridge_manager = DataBridgeManager()
