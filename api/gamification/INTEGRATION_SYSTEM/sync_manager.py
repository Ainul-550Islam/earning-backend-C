"""
Sync Manager — Data conflict resolution and synchronization management.

This module provides comprehensive synchronization management for handling
data conflicts, resolution strategies, and coordinated data synchronization.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, Type, Set
from enum import Enum

from .integ_constants import ErrorCode
from .integ_exceptions import (
    IntegrationError, SyncConflictError, SyncTimeoutError,
    SyncFailedError
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sync Manager Types
# ---------------------------------------------------------------------------

class SyncType(Enum):
    """Synchronization type enumeration."""
    FULL_SYNC = "full_sync"
    INCREMENTAL_SYNC = "incremental_sync"
    REAL_TIME_SYNC = "real_time_sync"
    BATCH_SYNC = "batch_sync"
    MANUAL_SYNC = "manual_sync"


class ConflictType(Enum):
    """Conflict type enumeration."""
    VERSION_CONFLICT = "version_conflict"
    DATA_CONFLICT = "data_conflict"
    SCHEMA_CONFLICT = "schema_conflict"
    BUSINESS_RULE_CONFLICT = "business_rule_conflict"
    TIMESTAMP_CONFLICT = "timestamp_conflict"
    CUSTOM = "custom"


class ConflictResolution(Enum):
    """Conflict resolution strategy enumeration."""
    SOURCE_WINS = "source_wins"
    TARGET_WINS = "target_wins"
    LATEST_WINS = "latest_wins"
    MANUAL = "manual"
    MERGE = "merge"
    CUSTOM = "custom"
    IGNORE = "ignore"


class SyncStatus(Enum):
    """Synchronization status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CONFLICT = "conflict"


# ---------------------------------------------------------------------------
# Sync Manager Data Classes
# ---------------------------------------------------------------------------

@dataclass
class SyncConflict:
    """Data synchronization conflict."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conflict_type: ConflictType = ConflictType.DATA_CONFLICT
    resource_id: str = ""
    resource_type: str = ""
    source_data: Dict[str, Any] = field(default_factory=dict)
    target_data: Dict[str, Any] = field(default_factory=dict)
    source_version: Optional[int] = None
    target_version: Optional[int] = None
    source_timestamp: Optional[datetime] = None
    target_timestamp: Optional[datetime] = None
    conflicting_fields: List[str] = field(default_factory=list)
    description: str = ""
    severity: str = "medium"  # low, medium, high, critical
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    resolution_strategy: Optional[ConflictResolution] = None
    resolved_data: Optional[Dict[str, Any]] = None
    resolver_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_resolved(self) -> bool:
        """Check if conflict is resolved."""
        return self.resolved_at is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "conflict_type": self.conflict_type.value,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "source_data": self.source_data,
            "target_data": self.target_data,
            "source_version": self.source_version,
            "target_version": self.target_version,
            "source_timestamp": self.source_timestamp.isoformat() if self.source_timestamp else None,
            "target_timestamp": self.target_timestamp.isoformat() if self.target_timestamp else None,
            "conflicting_fields": self.conflicting_fields,
            "description": self.description,
            "severity": self.severity,
            "detected_at": self.detected_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_strategy": self.resolution_strategy.value if self.resolution_strategy else None,
            "resolved_data": self.resolved_data,
            "resolver_id": self.resolver_id,
            "is_resolved": self.is_resolved(),
            "metadata": self.metadata
        }


@dataclass
class SyncOperation:
    """Synchronization operation."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sync_type: SyncType = SyncType.INCREMENTAL_SYNC
    source_system: str = ""
    target_system: str = ""
    resource_type: str = ""
    resource_ids: List[str] = field(default_factory=list)
    status: SyncStatus = SyncStatus.PENDING
    priority: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    progress: float = 0.0
    total_items: int = 0
    processed_items: int = 0
    failed_items: int = 0
    conflicts: List[SyncConflict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_items == 0:
            return 1.0
        return (self.processed_items - self.failed_items) / self.total_items
    
    @property
    def is_complete(self) -> bool:
        """Check if operation is complete."""
        return self.status in [SyncStatus.COMPLETED, SyncStatus.FAILED, SyncStatus.CANCELLED]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "sync_type": self.sync_type.value,
            "source_system": self.source_system,
            "target_system": self.target_system,
            "resource_type": self.resource_type,
            "resource_ids": self.resource_ids,
            "status": self.status.value,
            "priority": self.priority,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "progress": self.progress,
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "failed_items": self.failed_items,
            "success_rate": self.success_rate,
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
            "is_complete": self.is_complete,
            "metadata": self.metadata
        }


@dataclass
class SyncPolicy:
    """Synchronization policy configuration."""
    
    id: str
    name: str
    source_system: str
    target_system: str
    resource_type: str
    sync_type: SyncType = SyncType.INCREMENTAL_SYNC
    conflict_resolution: ConflictResolution = ConflictResolution.SOURCE_WINS
    enabled: bool = True
    priority: int = 0
    sync_interval: Optional[float] = None  # seconds
    batch_size: int = 100
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 300.0
    filters: Dict[str, Any] = field(default_factory=dict)
    transformations: List[Dict[str, Any]] = field(default_factory=list)
    validation_rules: List[Dict[str, Any]] = field(default_factory=dict)
    conflict_handlers: Dict[ConflictType, Callable] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "source_system": self.source_system,
            "target_system": self.target_system,
            "resource_type": self.resource_type,
            "sync_type": self.sync_type.value,
            "conflict_resolution": self.conflict_resolution.value,
            "enabled": self.enabled,
            "priority": self.priority,
            "sync_interval": self.sync_interval,
            "batch_size": self.batch_size,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "timeout": self.timeout,
            "filters": self.filters,
            "transformations": self.transformations,
            "validation_rules": self.validation_rules,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


# ---------------------------------------------------------------------------
# Abstract Conflict Resolver
# ---------------------------------------------------------------------------

class BaseConflictResolver(ABC):
    """Abstract base class for conflict resolvers."""
    
    @abstractmethod
    def resolve_conflict(self, conflict: SyncConflict, policy: SyncPolicy) -> Optional[Dict[str, Any]]:
        """Resolve a conflict."""
        pass
    
    @abstractmethod
    def get_supported_types(self) -> List[ConflictType]:
        """Get supported conflict types."""
        pass


# ---------------------------------------------------------------------------
# Built-in Conflict Resolvers
# ---------------------------------------------------------------------------

class SourceWinsResolver(BaseConflictResolver):
    """Resolver that always chooses source data."""
    
    def resolve_conflict(self, conflict: SyncConflict, policy: SyncPolicy) -> Optional[Dict[str, Any]]:
        """Resolve conflict by choosing source data."""
        return conflict.source_data.copy()
    
    def get_supported_types(self) -> List[ConflictType]:
        return list(ConflictType)


class TargetWinsResolver(BaseConflictResolver):
    """Resolver that always chooses target data."""
    
    def resolve_conflict(self, conflict: SyncConflict, policy: SyncPolicy) -> Optional[Dict[str, Any]]:
        """Resolve conflict by choosing target data."""
        return conflict.target_data.copy()
    
    def get_supported_types(self) -> List[ConflictType]:
        return list(ConflictType)


class LatestWinsResolver(BaseConflictResolver):
    """Resolver that chooses the most recent data."""
    
    def resolve_conflict(self, conflict: SyncConflict, policy: SyncPolicy) -> Optional[Dict[str, Any]]:
        """Resolve conflict by choosing latest data."""
        if conflict.source_timestamp and conflict.target_timestamp:
            if conflict.source_timestamp > conflict.target_timestamp:
                return conflict.source_data.copy()
            else:
                return conflict.target_data.copy()
        else:
            # Fallback to source if timestamps are missing
            return conflict.source_data.copy()
    
    def get_supported_types(self) -> List[ConflictType]:
        return list(ConflictType)


class MergeResolver(BaseConflictResolver):
    """Resolver that merges data from both sources."""
    
    def resolve_conflict(self, conflict: SyncConflict, policy: SyncPolicy) -> Optional[Dict[str, Any]]:
        """Resolve conflict by merging data."""
        merged_data = conflict.target_data.copy()
        
        # Merge source data into target data
        for key, value in conflict.source_data.items():
            if key not in merged_data:
                merged_data[key] = value
            elif isinstance(value, dict) and isinstance(merged_data[key], dict):
                # Recursively merge dictionaries
                merged_data[key].update(value)
            else:
                # Use source value for conflicts
                merged_data[key] = value
        
        return merged_data
    
    def get_supported_types(self) -> List[ConflictType]:
        return list(ConflictType)


# ---------------------------------------------------------------------------
# Sync Manager Implementation
# ---------------------------------------------------------------------------

class SyncManager:
    """Main synchronization management system."""
    
    def __init__(self):
        self.policies: Dict[str, SyncPolicy] = None
        self.operations: Dict[str, SyncOperation] = {}
        self.conflicts: Dict[str, SyncConflict] = {}
        self.resolvers: Dict[ConflictType, BaseConflictResolver] = {}
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
        self._running = False
        self._sync_thread: Optional[threading.Thread] = None
        
        # Initialize data structures
        self.policies = {}
        
        # Register built-in resolvers
        self._register_builtin_resolvers()
    
    def _register_builtin_resolvers(self) -> None:
        """Register built-in conflict resolvers."""
        resolvers = [
            SourceWinsResolver(),
            TargetWinsResolver(),
            LatestWinsResolver(),
            MergeResolver()
        ]
        
        for resolver in resolvers:
            for conflict_type in resolver.get_supported_types():
                self.resolvers[conflict_type] = resolver
    
    def register_resolver(self, conflict_type: ConflictType, resolver: BaseConflictResolver) -> None:
        """Register a conflict resolver."""
        self.resolvers[conflict_type] = resolver
        self.logger.info(f"Registered conflict resolver for type: {conflict_type.value}")
    
    def register_policy(self, policy: SyncPolicy) -> None:
        """Register a synchronization policy."""
        with self._lock:
            self.policies[policy.id] = policy
            self.logger.info(f"Registered sync policy: {policy.id}")
    
    def unregister_policy(self, policy_id: str) -> bool:
        """Unregister a synchronization policy."""
        with self._lock:
            if policy_id in self.policies:
                del self.policies[policy_id]
                self.logger.info(f"Unregistered sync policy: {policy_id}")
                return True
            return False
    
    def start_sync(self, policy_id: str, resource_ids: Optional[List[str]] = None) -> str:
        """Start a synchronization operation."""
        policy = self.policies.get(policy_id)
        if not policy:
            raise IntegrationError(f"Sync policy '{policy_id}' not found")
        
        if not policy.enabled:
            raise IntegrationError(f"Sync policy '{policy_id}' is disabled")
        
        import uuid
        operation = SyncOperation(
            id=str(uuid.uuid4()),
            sync_type=policy.sync_type,
            source_system=policy.source_system,
            target_system=policy.target_system,
            resource_type=policy.resource_type,
            resource_ids=resource_ids or [],
            priority=policy.priority,
            metadata={"policy_id": policy_id}
        )
        
        with self._lock:
            self.operations[operation.id] = operation
        
        # Start the sync operation
        self._execute_sync_operation(operation)
        
        return operation.id
    
    def cancel_sync(self, operation_id: str) -> bool:
        """Cancel a synchronization operation."""
        with self._lock:
            operation = self.operations.get(operation_id)
            if not operation:
                return False
            
            if operation.status == SyncStatus.RUNNING:
                operation.status = SyncStatus.CANCELLED
                operation.completed_at = datetime.now(timezone.utc)
                self.logger.info(f"Cancelled sync operation: {operation_id}")
                return True
            
            return False
    
    def get_operation(self, operation_id: str) -> Optional[SyncOperation]:
        """Get a synchronization operation."""
        with self._lock:
            return self.operations.get(operation_id)
    
    def list_operations(
        self,
        status: Optional[SyncStatus] = None,
        source_system: Optional[str] = None,
        target_system: Optional[str] = None
    ) -> List[SyncOperation]:
        """List synchronization operations with optional filtering."""
        with self._lock:
            operations = list(self.operations.values())
            
            if status:
                operations = [op for op in operations if op.status == status]
            
            if source_system:
                operations = [op for op in operations if op.source_system == source_system]
            
            if target_system:
                operations = [op for op in operations if op.target_system == target_system]
            
            return sorted(operations, key=lambda x: x.priority, reverse=True)
    
    def get_conflict(self, conflict_id: str) -> Optional[SyncConflict]:
        """Get a conflict by ID."""
        with self._lock:
            return self.conflicts.get(conflict_id)
    
    def list_conflicts(
        self,
        resolved: Optional[bool] = None,
        conflict_type: Optional[ConflictType] = None
    ) -> List[SyncConflict]:
        """List conflicts with optional filtering."""
        with self._lock:
            conflicts = list(self.conflicts.values())
            
            if resolved is not None:
                conflicts = [c for c in conflicts if c.is_resolved() == resolved]
            
            if conflict_type:
                conflicts = [c for c in conflicts if c.conflict_type == conflict_type]
            
            return sorted(conflicts, key=lambda x: x.detected_at, reverse=True)
    
    def resolve_conflict(
        self,
        conflict_id: str,
        resolution_strategy: ConflictResolution,
        resolved_data: Optional[Dict[str, Any]] = None,
        resolver_id: Optional[str] = None
    ) -> bool:
        """Resolve a conflict."""
        with self._lock:
            conflict = self.conflicts.get(conflict_id)
            if not conflict:
                return False
            
            if conflict.is_resolved():
                return True
            
            # Apply resolution strategy
            if resolution_strategy == ConflictResolution.MANUAL and resolved_data:
                conflict.resolved_data = resolved_data
            elif resolution_strategy == ConflictResolution.IGNORE:
                conflict.resolved_data = conflict.target_data.copy()
            else:
                # Use resolver
                resolver = self.resolvers.get(conflict.conflict_type)
                if resolver:
                    policy = self.policies.get(conflict.metadata.get("policy_id", ""))
                    resolved_data = resolver.resolve_conflict(conflict, policy)
                    conflict.resolved_data = resolved_data
                else:
                    self.logger.error(f"No resolver found for conflict type: {conflict.conflict_type.value}")
                    return False
            
            conflict.resolution_strategy = resolution_strategy
            conflict.resolved_at = datetime.now(timezone.utc)
            conflict.resolver_id = resolver_id
            
            self.logger.info(f"Resolved conflict: {conflict_id}")
            return True
    
    def auto_resolve_conflicts(self, operation_id: str) -> int:
        """Automatically resolve conflicts for an operation."""
        operation = self.get_operation(operation_id)
        if not operation:
            return 0
        
        resolved_count = 0
        
        for conflict in operation.conflicts:
            if not conflict.is_resolved():
                policy = self.policies.get(operation.metadata.get("policy_id", ""))
                if policy:
                    if self.resolve_conflict(conflict.id, policy.conflict_resolution):
                        resolved_count += 1
        
        return resolved_count
    
    def get_sync_statistics(self) -> Dict[str, Any]:
        """Get synchronization statistics."""
        with self._lock:
            total_operations = len(self.operations)
            completed_operations = len([op for op in self.operations.values() if op.status == SyncStatus.COMPLETED])
            failed_operations = len([op for op in self.operations.values() if op.status == SyncStatus.FAILED])
            running_operations = len([op for op in self.operations.values() if op.status == SyncStatus.RUNNING])
            
            total_conflicts = len(self.conflicts)
            resolved_conflicts = len([c for c in self.conflicts.values() if c.is_resolved()])
            
            return {
                "total_operations": total_operations,
                "completed_operations": completed_operations,
                "failed_operations": failed_operations,
                "running_operations": running_operations,
                "total_conflicts": total_conflicts,
                "resolved_conflicts": resolved_conflicts,
                "unresolved_conflicts": total_conflicts - resolved_conflicts,
                "active_policies": len([p for p in self.policies.values() if p.enabled]),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def _execute_sync_operation(self, operation: SyncOperation) -> None:
        """Execute a synchronization operation."""
        try:
            operation.status = SyncStatus.RUNNING
            operation.started_at = datetime.now(timezone.utc)
            
            policy_id = operation.metadata.get("policy_id")
            policy = self.policies.get(policy_id) if policy_id else None
            
            if not policy:
                operation.status = SyncStatus.FAILED
                operation.error = "Policy not found"
                operation.completed_at = datetime.now(timezone.utc)
                return
            
            # Simulate sync execution
            self._simulate_sync_execution(operation, policy)
            
        except Exception as e:
            operation.status = SyncStatus.FAILED
            operation.error = str(e)
            operation.completed_at = datetime.now(timezone.utc)
            self.logger.error(f"Sync operation {operation.id} failed: {e}")
    
    def _simulate_sync_execution(self, operation: SyncOperation, policy: SyncPolicy) -> None:
        """Simulate sync execution (placeholder implementation)."""
        # This would implement actual synchronization logic
        # For now, we'll simulate the process
        
        operation.total_items = len(operation.resource_ids) or 100
        
        for i in range(operation.total_items):
            # Simulate processing an item
            time.sleep(0.01)  # Simulate processing time
            
            operation.processed_items += 1
            operation.progress = (operation.processed_items / operation.total_items) * 100
            
            # Simulate occasional conflicts
            if i % 20 == 0:  # Conflict every 20 items
                conflict = SyncConflict(
                    resource_id=f"resource_{i}",
                    resource_type=operation.resource_type,
                    source_data={"field1": "source_value", "field2": f"source_{i}"},
                    target_data={"field1": "target_value", "field2": f"target_{i}"},
                    conflicting_fields=["field1", "field2"],
                    description=f"Conflict in resource_{i}",
                    metadata={"operation_id": operation.id}
                )
                
                operation.conflicts.append(conflict)
                self.conflicts[conflict.id] = conflict
                operation.failed_items += 1
        
        # Auto-resolve conflicts if policy allows
        if policy.conflict_resolution != ConflictResolution.MANUAL:
            self.auto_resolve_conflicts(operation.id)
        
        # Complete operation
        operation.status = SyncStatus.COMPLETED
        operation.completed_at = datetime.now(timezone.utc)
        
        self.logger.info(f"Completed sync operation: {operation.id}")


# Global sync manager instance
sync_manager = SyncManager()


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def create_sync_policy(
    policy_id: str,
    name: str,
    source_system: str,
    target_system: str,
    resource_type: str,
    **kwargs: Any
) -> SyncPolicy:
    """Create a synchronization policy."""
    policy = SyncPolicy(
        id=policy_id,
        name=name,
        source_system=source_system,
        target_system=target_system,
        resource_type=resource_type,
        **kwargs
    )
    
    sync_manager.register_policy(policy)
    return policy


def start_sync(policy_id: str, resource_ids: Optional[List[str]] = None) -> str:
    """Start a synchronization operation."""
    return sync_manager.start_sync(policy_id, resource_ids)


def resolve_conflict(
    conflict_id: str,
    resolution_strategy: ConflictResolution,
    resolved_data: Optional[Dict[str, Any]] = None
) -> bool:
    """Resolve a synchronization conflict."""
    return sync_manager.resolve_conflict(conflict_id, resolution_strategy, resolved_data)


# Initialize logging
logger.info("Sync manager module initialized")
