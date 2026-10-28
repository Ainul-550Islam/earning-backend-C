# engagement/integration_system/sync_manager.py
"""
Data conflict resolver and synchronization manager.
Handles data consistency, conflict detection, and resolution strategies.
"""
import hashlib
import json
import time
import threading
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
import logging

from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from django.conf import settings

from .integ_constants import (
    ERROR_CODES, SUCCESS_CODES, DEFAULT_CONFIG, CACHE_KEYS
)
from .integ_exceptions import IntegrationException, DataValidationError


class ConflictType(Enum):
    """Types of data conflicts."""
    VERSION_MISMATCH = "version_mismatch"
    DATA_MISMATCH = "data_mismatch"
    TIMESTAMP_CONFLICT = "timestamp_conflict"
    REFERENCE_CONFLICT = "reference_conflict"
    BUSINESS_RULE_CONFLICT = "business_rule_conflict"
    CONCURRENT_MODIFICATION = "concurrent_modification"
    ORPHANED_DATA = "orphaned_data"
    SCHEMA_CONFLICT = "schema_conflict"


class ResolutionStrategy(Enum):
    """Conflict resolution strategies."""
    KEEP_SOURCE = "keep_source"
    KEEP_TARGET = "keep_target"
    MERGE = "merge"
    LATEST_WINS = "latest_wins"
    MANUAL_REVIEW = "manual_review"
    CUSTOM = "custom"
    SOURCE_PRIORITY = "source_priority"
    TARGET_PRIORITY = "target_priority"
    TIMESTAMP_WINS = "timestamp_wins"


class SyncStatus(Enum):
    """Synchronization status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"
    RETRY = "retry"
    CANCELLED = "cancelled"


@dataclass
class DataVersion:
    """Data version information."""
    version: int
    timestamp: datetime
    checksum: str
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if isinstance(self.timestamp, str):
            self.timestamp = datetime.fromisoformat(self.timestamp)


@dataclass
class Conflict:
    """Data conflict information."""
    id: str
    type: ConflictType
    source_data: Dict[str, Any]
    target_data: Dict[str, Any]
    source_version: DataVersion
    target_version: DataVersion
    field_path: str = ""
    description: str = ""
    severity: str = "medium"  # low, medium, high, critical
    auto_resolvable: bool = True
    resolution_strategy: Optional[ResolutionStrategy] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_data: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=timezone.now)


@dataclass
class SyncOperation:
    """Synchronization operation."""
    id: str
    source: str
    target: str
    operation_type: str  # create, update, delete, merge
    data: Dict[str, Any]
    status: SyncStatus = SyncStatus.PENDING
    priority: int = 0
    max_retries: int = 3
    retry_count: int = 0
    conflicts: List[Conflict] = field(default_factory=list)
    created_at: datetime = field(default_factory=timezone.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncResult:
    """Synchronization result."""
    success: bool
    operation_id: str
    conflicts_resolved: int = 0
    conflicts_remaining: int = 0
    data_merged: bool = False
    execution_time_ms: float = 0.0
    message: str = ""
    resolved_data: Optional[Dict[str, Any]] = None
    applied_strategies: List[ResolutionStrategy] = field(default_factory=list)


class BaseConflictResolver(ABC):
    """Base conflict resolver interface."""
    
    @abstractmethod
    def detect_conflicts(self, source_data: Dict[str, Any], target_data: Dict[str, Any],
                        source_version: DataVersion, target_version: DataVersion) -> List[Conflict]:
        """Detect conflicts between data versions."""
        pass
    
    @abstractmethod
    def resolve_conflict(self, conflict: Conflict, strategy: ResolutionStrategy = None) -> SyncResult:
        """Resolve a specific conflict."""
        pass


class VersionConflictResolver(BaseConflictResolver):
    """Resolver for version-based conflicts."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.VersionConflictResolver")
    
    def detect_conflicts(self, source_data: Dict[str, Any], target_data: Dict[str, Any],
                        source_version: DataVersion, target_version: DataVersion) -> List[Conflict]:
        """Detect version conflicts."""
        conflicts = []
        
        # Check version mismatch
        if source_version.version != target_version.version:
            conflict = Conflict(
                id=self._generate_conflict_id(),
                type=ConflictType.VERSION_MISMATCH,
                source_data=source_data,
                target_data=target_data,
                source_version=source_version,
                target_version=target_version,
                description=f"Version mismatch: source={source_version.version}, target={target_version.version}",
                auto_resolvable=True,
                resolution_strategy=ResolutionStrategy.LATEST_WINS
            )
            conflicts.append(conflict)
        
        # Check checksum mismatch
        if source_version.checksum != target_version.checksum:
            conflict = Conflict(
                id=self._generate_conflict_id(),
                type=ConflictType.DATA_MISMATCH,
                source_data=source_data,
                target_data=target_data,
                source_version=source_version,
                target_version=target_version,
                description="Data checksum mismatch",
                auto_resolvable=True,
                resolution_strategy=ResolutionStrategy.MERGE
            )
            conflicts.append(conflict)
        
        # Check timestamp conflicts
        time_diff = abs((source_version.timestamp - target_version.timestamp).total_seconds())
        if time_diff < 1:  # Less than 1 second difference
            conflict = Conflict(
                id=self._generate_conflict_id(),
                type=ConflictType.TIMESTAMP_CONFLICT,
                source_data=source_data,
                target_data=target_data,
                source_version=source_version,
                target_version=target_version,
                description="Concurrent modification detected",
                auto_resolvable=True,
                resolution_strategy=ResolutionStrategy.LATEST_WINS
            )
            conflicts.append(conflict)
        
        return conflicts
    
    def resolve_conflict(self, conflict: Conflict, strategy: ResolutionStrategy = None) -> SyncResult:
        """Resolve version conflict."""
        start_time = time.time()
        strategy = strategy or conflict.resolution_strategy or ResolutionStrategy.LATEST_WINS
        
        try:
            if strategy == ResolutionStrategy.LATEST_WINS:
                resolved_data = self._resolve_latest_wins(conflict)
            elif strategy == ResolutionStrategy.MERGE:
                resolved_data = self._merge_data(conflict)
            elif strategy == ResolutionStrategy.KEEP_SOURCE:
                resolved_data = conflict.source_data
            elif strategy == ResolutionStrategy.KEEP_TARGET:
                resolved_data = conflict.target_data
            else:
                raise IntegrationException(f"Unsupported resolution strategy: {strategy}")
            
            conflict.resolved = True
            conflict.resolved_at = timezone.now()
            conflict.resolution_data = resolved_data
            conflict.resolution_strategy = strategy
            
            return SyncResult(
                success=True,
                operation_id=conflict.id,
                conflicts_resolved=1,
                data_merged=(strategy == ResolutionStrategy.MERGE),
                execution_time_ms=(time.time() - start_time) * 1000,
                message=f"Conflict resolved using {strategy.value}",
                resolved_data=resolved_data,
                applied_strategies=[strategy]
            )
            
        except Exception as exc:
            self.logger.error(f"Failed to resolve conflict {conflict.id}: {exc}")
            return SyncResult(
                success=False,
                operation_id=conflict.id,
                execution_time_ms=(time.time() - start_time) * 1000,
                message=f"Conflict resolution failed: {str(exc)}"
            )
    
    def _resolve_latest_wins(self, conflict: Conflict) -> Dict[str, Any]:
        """Resolve by keeping the latest version."""
        if conflict.source_version.timestamp > conflict.target_version.timestamp:
            return conflict.source_data
        else:
            return conflict.target_data
    
    def _merge_data(self, conflict: Conflict) -> Dict[str, Any]:
        """Merge source and target data."""
        merged = conflict.source_data.copy()
        
        # Simple merge strategy - target overrides source for conflicts
        for key, value in conflict.target_data.items():
            if key in merged and merged[key] != value:
                # Conflict detected - keep target value
                merged[key] = value
            else:
                merged[key] = value
        
        return merged
    
    def _generate_conflict_id(self) -> str:
        """Generate unique conflict ID."""
        import uuid
        return str(uuid.uuid4())


class DataFieldResolver(BaseConflictResolver):
    """Resolver for field-level conflicts."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.DataFieldResolver")
        self.field_mergers: Dict[str, Callable] = {}
        
        # Register default field mergers
        self._register_default_mergers()
    
    def _register_default_mergers(self):
        """Register default field merging strategies."""
        self.field_mergers.update({
            'string': self._merge_strings,
            'number': self._merge_numbers,
            'list': self._merge_lists,
            'dict': self._merge_dicts,
            'timestamp': self._merge_timestamps,
            'boolean': self._merge_booleans
        })
    
    def detect_conflicts(self, source_data: Dict[str, Any], target_data: Dict[str, Any],
                        source_version: DataVersion, target_version: DataVersion) -> List[Conflict]:
        """Detect field-level conflicts."""
        conflicts = []
        
        # Find all fields
        all_fields = set(source_data.keys()) | set(target_data.keys())
        
        for field in all_fields:
            source_value = source_data.get(field)
            target_value = target_data.get(field)
            
            if source_value != target_value:
                field_type = type(source_value).__name__ if source_value is not None else type(target_value).__name__
                
                conflict = Conflict(
                    id=self._generate_conflict_id(),
                    type=ConflictType.DATA_MISMATCH,
                    source_data={field: source_value},
                    target_data={field: target_value},
                    source_version=source_version,
                    target_version=target_version,
                    field_path=field,
                    description=f"Field '{field}' conflict: {source_value} vs {target_value}",
                    auto_resolvable=field_type in self.field_mergers,
                    resolution_strategy=ResolutionStrategy.MERGE if field_type in self.field_mergers else ResolutionStrategy.MANUAL_REVIEW
                )
                conflicts.append(conflict)
        
        return conflicts
    
    def resolve_conflict(self, conflict: Conflict, strategy: ResolutionStrategy = None) -> SyncResult:
        """Resolve field conflict."""
        start_time = time.time()
        strategy = strategy or conflict.resolution_strategy or ResolutionStrategy.MERGE
        
        try:
            if strategy == ResolutionStrategy.MERGE and conflict.auto_resolvable:
                resolved_data = self._merge_field(conflict)
            elif strategy == ResolutionStrategy.KEEP_SOURCE:
                resolved_data = conflict.source_data
            elif strategy == ResolutionStrategy.KEEP_TARGET:
                resolved_data = conflict.target_data
            else:
                raise IntegrationException(f"Cannot resolve conflict with strategy: {strategy}")
            
            conflict.resolved = True
            conflict.resolved_at = timezone.now()
            conflict.resolution_data = resolved_data
            conflict.resolution_strategy = strategy
            
            return SyncResult(
                success=True,
                operation_id=conflict.id,
                conflicts_resolved=1,
                data_merged=True,
                execution_time_ms=(time.time() - start_time) * 1000,
                message=f"Field conflict resolved using {strategy.value}",
                resolved_data=resolved_data,
                applied_strategies=[strategy]
            )
            
        except Exception as exc:
            self.logger.error(f"Failed to resolve field conflict {conflict.id}: {exc}")
            return SyncResult(
                success=False,
                operation_id=conflict.id,
                execution_time_ms=(time.time() - start_time) * 1000,
                message=f"Field conflict resolution failed: {str(exc)}"
            )
    
    def _merge_field(self, conflict: Conflict) -> Dict[str, Any]:
        """Merge field values."""
        field = conflict.field_path
        source_value = list(conflict.source_data.values())[0]
        target_value = list(conflict.target_data.values())[0]
        
        field_type = type(source_value).__name__ if source_value is not None else type(target_value).__name__
        merger = self.field_mergers.get(field_type)
        
        if merger:
            return {field: merger(source_value, target_value)}
        else:
            # Default to target value
            return {field: target_value}
    
    def _merge_strings(self, source: str, target: str) -> str:
        """Merge string values."""
        if len(source) > len(target):
            return source
        return target
    
    def _merge_numbers(self, source: Union[int, float], target: Union[int, float]) -> Union[int, float]:
        """Merge numeric values."""
        return max(source, target)
    
    def _merge_lists(self, source: List[Any], target: List[Any]) -> List[Any]:
        """Merge list values."""
        merged = list(source)
        for item in target:
            if item not in merged:
                merged.append(item)
        return merged
    
    def _merge_dicts(self, source: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
        """Merge dictionary values."""
        merged = source.copy()
        merged.update(target)
        return merged
    
    def _merge_timestamps(self, source: datetime, target: datetime) -> datetime:
        """Merge timestamp values."""
        return max(source, target)
    
    def _merge_booleans(self, source: bool, target: bool) -> bool:
        """Merge boolean values."""
        return source or target  # True if either is True
    
    def _generate_conflict_id(self) -> str:
        """Generate unique conflict ID."""
        import uuid
        return str(uuid.uuid4())


class SyncManager:
    """Data synchronization and conflict resolution manager."""
    
    def __init__(self):
        self.resolvers: List[BaseConflictResolver] = []
        self.operations: Dict[str, SyncOperation] = {}
        self.conflicts: Dict[str, Conflict] = {}
        self.strategies: Dict[ConflictType, ResolutionStrategy] = {}
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.SyncManager")
        
        # Register default resolvers
        self._register_default_resolvers()
        
        # Register default strategies
        self._register_default_strategies()
    
    def _register_default_resolvers(self):
        """Register default conflict resolvers."""
        self.resolvers.append(VersionConflictResolver())
        self.resolvers.append(DataFieldResolver())
    
    def _register_default_strategies(self):
        """Register default resolution strategies."""
        self.strategies.update({
            ConflictType.VERSION_MISMATCH: ResolutionStrategy.LATEST_WINS,
            ConflictType.DATA_MISMATCH: ResolutionStrategy.MERGE,
            ConflictType.TIMESTAMP_CONFLICT: ResolutionStrategy.LATEST_WINS,
            ConflictType.CONCURRENT_MODIFICATION: ResolutionStrategy.MANUAL_REVIEW,
            ConflictType.SCHEMA_CONFLICT: ResolutionStrategy.MANUAL_REVIEW
        })
    
    def add_resolver(self, resolver: BaseConflictResolver):
        """Add custom conflict resolver."""
        self.resolvers.append(resolver)
        self.logger.info(f"Added conflict resolver: {resolver.__class__.__name__}")
    
    def set_strategy(self, conflict_type: ConflictType, strategy: ResolutionStrategy):
        """Set resolution strategy for conflict type."""
        self.strategies[conflict_type] = strategy
        self.logger.info(f"Set strategy for {conflict_type}: {strategy}")
    
    def sync_data(self, source: str, target: str, source_data: Dict[str, Any],
                  target_data: Dict[str, Any] = None, source_version: DataVersion = None,
                  target_version: DataVersion = None, **kwargs) -> SyncResult:
        """Synchronize data between source and target."""
        start_time = time.time()
        
        try:
            # Create sync operation
            operation = SyncOperation(
                id=self._generate_operation_id(),
                source=source,
                target=target,
                operation_type="sync",
                data=source_data,
                **kwargs
            )
            
            with self._lock:
                self.operations[operation.id] = operation
            
            # Detect conflicts
            conflicts = self._detect_all_conflicts(
                source_data, target_data or {}, source_version, target_version
            )
            
            operation.conflicts = conflicts
            
            if conflicts:
                operation.status = SyncStatus.CONFLICT
                
                # Resolve conflicts
                resolved_data = source_data.copy()
                conflicts_resolved = 0
                applied_strategies = []
                
                for conflict in conflicts:
                    strategy = self.strategies.get(conflict.type, ResolutionStrategy.MANUAL_REVIEW)
                    
                    if conflict.auto_resolvable and strategy != ResolutionStrategy.MANUAL_REVIEW:
                        result = self._resolve_conflict(conflict, strategy)
                        if result.success:
                            resolved_data.update(result.resolved_data or {})
                            conflicts_resolved += 1
                            applied_strategies.append(strategy)
                        else:
                            self.logger.error(f"Failed to resolve conflict {conflict.id}")
                
                operation.status = SyncStatus.COMPLETED if conflicts_resolved == len(conflicts) else SyncStatus.CONFLICT
                
                return SyncResult(
                    success=conflicts_resolved == len(conflicts),
                    operation_id=operation.id,
                    conflicts_resolved=conflicts_resolved,
                    conflicts_remaining=len(conflicts) - conflicts_resolved,
                    data_merged=conflicts_resolved > 0,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    message=f"Sync completed: {conflicts_resolved}/{len(conflicts)} conflicts resolved",
                    resolved_data=resolved_data,
                    applied_strategies=applied_strategies
                )
            else:
                # No conflicts - direct sync
                operation.status = SyncStatus.COMPLETED
                
                return SyncResult(
                    success=True,
                    operation_id=operation.id,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    message="Sync completed: no conflicts detected",
                    resolved_data=source_data
                )
                
        except Exception as exc:
            self.logger.error(f"Sync operation failed: {exc}")
            return SyncResult(
                success=False,
                operation_id=operation.id if 'operation' in locals() else "unknown",
                execution_time_ms=(time.time() - start_time) * 1000,
                message=f"Sync failed: {str(exc)}"
            )
    
    def resolve_conflict(self, conflict_id: str, strategy: ResolutionStrategy = None) -> SyncResult:
        """Resolve specific conflict."""
        with self._lock:
            conflict = self.conflicts.get(conflict_id)
            if not conflict:
                raise IntegrationException(f"Conflict not found: {conflict_id}")
            
            return self._resolve_conflict(conflict, strategy)
    
    def get_conflicts(self, operation_id: str = None, resolved: bool = None) -> List[Conflict]:
        """Get conflicts."""
        with self._lock:
            conflicts = list(self.conflicts.values())
            
            if operation_id:
                conflicts = [c for c in conflicts if c.id.startswith(operation_id)]
            
            if resolved is not None:
                conflicts = [c for c in conflicts if c.resolved == resolved]
            
            return conflicts
    
    def get_operations(self, status: SyncStatus = None) -> List[SyncOperation]:
        """Get sync operations."""
        with self._lock:
            operations = list(self.operations.values())
            
            if status:
                operations = [op for op in operations if op.status == status]
            
            return operations
    
    def _detect_all_conflicts(self, source_data: Dict[str, Any], target_data: Dict[str, Any],
                             source_version: DataVersion, target_version: DataVersion) -> List[Conflict]:
        """Detect all conflicts using registered resolvers."""
        all_conflicts = []
        
        for resolver in self.resolvers:
            try:
                conflicts = resolver.detect_conflicts(source_data, target_data, source_version, target_version)
                all_conflicts.extend(conflicts)
                
                # Store conflicts
                for conflict in conflicts:
                    self.conflicts[conflict.id] = conflict
                    
            except Exception as exc:
                self.logger.error(f"Resolver {resolver.__class__.__name__} failed: {exc}")
        
        return all_conflicts
    
    def _resolve_conflict(self, conflict: Conflict, strategy: ResolutionStrategy = None) -> SyncResult:
        """Resolve conflict using appropriate resolver."""
        strategy = strategy or self.strategies.get(conflict.type, ResolutionStrategy.MANUAL_REVIEW)
        
        for resolver in self.resolvers:
            try:
                # Try to resolve with this resolver
                result = resolver.resolve_conflict(conflict, strategy)
                if result.success:
                    return result
            except Exception as exc:
                self.logger.error(f"Resolver {resolver.__class__.__name__} failed: {exc}")
                continue
        
        # No resolver could handle the conflict
        return SyncResult(
            success=False,
            operation_id=conflict.id,
            message=f"No resolver available for conflict type: {conflict.type}"
        )
    
    def _generate_operation_id(self) -> str:
        """Generate unique operation ID."""
        import uuid
        return str(uuid.uuid4())
    
    def calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate data checksum."""
        data_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def create_version(self, data: Dict[str, Any], source: str, version: int = None) -> DataVersion:
        """Create data version."""
        return DataVersion(
            version=version or int(time.time()),
            timestamp=timezone.now(),
            checksum=self.calculate_checksum(data),
            source=source
        )


# Global sync manager instance
sync_manager = SyncManager()


# Decorator for automatic conflict resolution
def with_conflict_resolution(source: str, target: str, strategy: ResolutionStrategy = None):
    """Decorator to add automatic conflict resolution to function."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                
                # If result is a dict, sync it
                if isinstance(result, dict):
                    sync_result = sync_manager.sync_data(
                        source=source,
                        target=target,
                        source_data=result
                    )
                    
                    if sync_result.success:
                        return sync_result.resolved_data
                    else:
                        raise IntegrationException(f"Conflict resolution failed: {sync_result.message}")
                
                return result
                
            except Exception as exc:
                # Try to resolve conflicts in exception context
                if hasattr(exc, 'source_data') and hasattr(exc, 'target_data'):
                    sync_result = sync_manager.sync_data(
                        source=source,
                        target=target,
                        source_data=exc.source_data,
                        target_data=exc.target_data,
                        strategy=strategy
                    )
                    
                    if sync_result.success:
                        return sync_result.resolved_data
                
                raise exc
        
        return wrapper
    return decorator


# Utility functions
class SyncUtils:
    """Utilities for synchronization management."""
    
    @staticmethod
    def create_data_version(data: Dict[str, Any], source: str, version: int = None) -> DataVersion:
        """Create data version."""
        return sync_manager.create_version(data, source, version)
    
    @staticmethod
    def compare_versions(version1: DataVersion, version2: DataVersion) -> int:
        """Compare two versions (-1, 0, 1)."""
        if version1.version < version2.version:
            return -1
        elif version1.version > version2.version:
            return 1
        else:
            return 0
    
    @staticmethod
    def merge_multiple_sources(sources: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, Any]:
        """Merge data from multiple sources."""
        if not sources:
            return {}
        
        merged = {}
        conflicts = []
        
        # Start with first source
        _, merged = sources[0]
        
        # Merge remaining sources
        for source_name, source_data in sources[1:]:
            sync_result = sync_manager.sync_data(
                source=source_name,
                target="merged",
                source_data=source_data,
                target_data=merged
            )
            
            if sync_result.success:
                merged = sync_result.resolved_data
            else:
                conflicts.append(f"Failed to merge {source_name}: {sync_result.message}")
        
        if conflicts:
            raise IntegrationException(f"Merge conflicts: {'; '.join(conflicts)}")
        
        return merged
    
    @staticmethod
    def validate_data_consistency(data: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
        """Validate data consistency against schema."""
        errors = []
        
        for field, field_schema in schema.items():
            if field not in data:
                if field_schema.get('required', False):
                    errors.append(f"Missing required field: {field}")
                continue
            
            value = data[field]
            expected_type = field_schema.get('type')
            
            if expected_type and not isinstance(value, eval(expected_type)):
                errors.append(f"Field {field} has wrong type: expected {expected_type}, got {type(value).__name__}")
        
        return errors
