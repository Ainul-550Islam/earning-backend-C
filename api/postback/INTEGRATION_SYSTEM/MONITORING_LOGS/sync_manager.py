"""
sync_manager.py – Data Conflict Resolution Manager for postback module.

Provides comprehensive data synchronization and conflict resolution functionality including:
- Data conflict detection
- Conflict resolution strategies
- Synchronization coordination
- Data consistency management
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import threading
import hashlib
import json
from collections import defaultdict

from django.utils import timezone
from django.core.cache import cache
from django.db import transaction, connection
from django.db.models import Q

from api.postback.INTEGRATION_SYSTEM.integ_exceptions import IntegrationException

logger = logging.getLogger(__name__)


class ConflictType(Enum):
    """Conflict type enumeration."""
    DUPLICATE = "duplicate"
    VERSION_MISMATCH = "version_mismatch"
    DATA_INCONSISTENCY = "data_inconsistency"
    CONCURRENT_MODIFICATION = "concurrent_modification"
    REFERENCE_VIOLATION = "reference_violation"
    CONSTRAINT_VIOLATION = "constraint_violation"
    BUSINESS_RULE_VIOLATION = "business_rule_violation"
    SCHEMA_MISMATCH = "schema_mismatch"


class ConflictResolutionStrategy(Enum):
    """Conflict resolution strategy enumeration."""
    LAST_WRITE_WINS = "last_write_wins"
    FIRST_WRITE_WINS = "first_write_wins"
    MERGE = "merge"
    MANUAL = "manual"
    IGNORE = "ignore"
    ERROR = "error"
    CUSTOM = "custom"


class SyncStatus(Enum):
    """Synchronization status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"
    CANCELLED = "cancelled"


@dataclass
class DataConflict:
    """Data conflict data structure."""
    id: str
    conflict_type: ConflictType
    resource_type: str
    resource_id: str
    conflicting_data: Dict[str, Any]
    existing_data: Dict[str, Any]
    conflict_fields: Set[str]
    detected_at: datetime = field(default_factory=timezone.now)
    resolved_at: Optional[datetime] = None
    resolution_strategy: Optional[ConflictResolutionStrategy] = None
    resolution_data: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'conflict_type': self.conflict_type.value,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'conflicting_data': self.conflicting_data,
            'existing_data': self.existing_data,
            'conflict_fields': list(self.conflict_fields),
            'detected_at': self.detected_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolution_strategy': self.resolution_strategy.value if self.resolution_strategy else None,
            'resolution_data': self.resolution_data,
            'metadata': self.metadata,
        }
    
    def is_resolved(self) -> bool:
        """Check if conflict is resolved."""
        return self.resolved_at is not None


@dataclass
class SyncOperation:
    """Synchronization operation data structure."""
    id: str
    operation_type: str
    source_system: str
    target_system: str
    resource_type: str
    resource_id: str
    sync_data: Dict[str, Any]
    status: SyncStatus = SyncStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    conflicts: List[DataConflict] = field(default_factory=list)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'operation_type': self.operation_type,
            'source_system': self.source_system,
            'target_system': self.target_system,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'sync_data': self.sync_data,
            'status': self.status.value,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'conflicts': [conflict.to_dict() for conflict in self.conflicts],
            'error_message': self.error_message,
            'metadata': self.metadata,
        }
    
    def has_conflicts(self) -> bool:
        """Check if operation has conflicts."""
        return len(self.conflicts) > 0
    
    def is_completed(self) -> bool:
        """Check if operation is completed."""
        return self.status in [SyncStatus.COMPLETED, SyncStatus.FAILED, SyncStatus.CANCELLED]


class ConflictDetector:
    """
    Conflict detector for data synchronization.
    
    Identifies conflicts between different data sources.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def detect_conflicts(self, existing_data: Dict[str, Any], new_data: Dict[str, Any],
                         resource_type: str, resource_id: str) -> List[DataConflict]:
        """
        Detect conflicts between existing and new data.
        
        Args:
            existing_data: Existing data
            new_data: New data
            resource_type: Resource type
            resource_id: Resource ID
            
        Returns:
            List of detected conflicts
        """
        conflicts = []
        
        # Check for duplicate data
        duplicate_conflict = self._check_duplicate(existing_data, new_data, resource_type, resource_id)
        if duplicate_conflict:
            conflicts.append(duplicate_conflict)
        
        # Check for version mismatch
        version_conflict = self._check_version_mismatch(existing_data, new_data, resource_type, resource_id)
        if version_conflict:
            conflicts.append(version_conflict)
        
        # Check for data inconsistency
        inconsistency_conflict = self._check_data_inconsistency(existing_data, new_data, resource_type, resource_id)
        if inconsistency_conflict:
            conflicts.append(inconsistency_conflict)
        
        # Check for concurrent modification
        concurrent_conflict = self._check_concurrent_modification(existing_data, new_data, resource_type, resource_id)
        if concurrent_conflict:
            conflicts.append(concurrent_conflict)
        
        return conflicts
    
    def _check_duplicate(self, existing_data: Dict[str, Any], new_data: Dict[str, Any],
                          resource_type: str, resource_id: str) -> Optional[DataConflict]:
        """Check for duplicate data."""
        import uuid
        
        # Simple duplicate check - if data is identical
        if existing_data == new_data:
            return DataConflict(
                id=f"conflict_{uuid.uuid4().hex[:12]}",
                conflict_type=ConflictType.DUPLICATE,
                resource_type=resource_type,
                resource_id=resource_id,
                conflicting_data=new_data,
                existing_data=existing_data,
                conflict_fields=set(existing_data.keys())
            )
        
        return None
    
    def _check_version_mismatch(self, existing_data: Dict[str, Any], new_data: Dict[str, Any],
                                resource_type: str, resource_id: str) -> Optional[DataConflict]:
        """Check for version mismatch."""
        import uuid
        
        existing_version = existing_data.get('version')
        new_version = new_data.get('version')
        
        if existing_version and new_version and existing_version != new_version:
            return DataConflict(
                id=f"conflict_{uuid.uuid4().hex[:12]}",
                conflict_type=ConflictType.VERSION_MISMATCH,
                resource_type=resource_type,
                resource_id=resource_id,
                conflicting_data=new_data,
                existing_data=existing_data,
                conflict_fields={'version'},
                metadata={
                    'existing_version': existing_version,
                    'new_version': new_version,
                }
            )
        
        return None
    
    def _check_data_inconsistency(self, existing_data: Dict[str, Any], new_data: Dict[str, Any],
                                   resource_type: str, resource_id: str) -> Optional[DataConflict]:
        """Check for data inconsistency."""
        import uuid
        
        # Check for inconsistent data types
        conflicting_fields = set()
        
        for field, existing_value in existing_data.items():
            if field in new_data:
                new_value = new_data[field]
                
                # Type inconsistency
                if type(existing_value) != type(new_value):
                    conflicting_fields.add(field)
                    continue
                
                # Value inconsistency for certain fields
                if self._is_value_inconsistent(field, existing_value, new_value):
                    conflicting_fields.add(field)
        
        if conflicting_fields:
            return DataConflict(
                id=f"conflict_{uuid.uuid4().hex[:12]}",
                conflict_type=ConflictType.DATA_INCONSISTENCY,
                resource_type=resource_type,
                resource_id=resource_id,
                conflicting_data=new_data,
                existing_data=existing_data,
                conflict_fields=conflicting_fields
            )
        
        return None
    
    def _check_concurrent_modification(self, existing_data: Dict[str, Any], new_data: Dict[str, Any],
                                      resource_type: str, resource_id: str) -> Optional[DataConflict]:
        """Check for concurrent modification."""
        import uuid
        
        # Check if existing data was modified after new data was created
        existing_modified = existing_data.get('modified_at')
        new_created = new_data.get('created_at')
        
        if existing_modified and new_created and existing_modified > new_created:
            return DataConflict(
                id=f"conflict_{uuid.uuid4().hex[:12]}",
                conflict_type=ConflictType.CONCURRENT_MODIFICATION,
                resource_type=resource_type,
                resource_id=resource_id,
                conflicting_data=new_data,
                existing_data=existing_data,
                conflict_fields={'modified_at', 'created_at'},
                metadata={
                    'existing_modified': existing_modified.isoformat(),
                    'new_created': new_created.isoformat(),
                }
            )
        
        return None
    
    def _is_value_inconsistent(self, field: str, existing_value: Any, new_value: Any) -> bool:
        """Check if field values are inconsistent."""
        # Business logic for inconsistency detection
        if field in ['email', 'phone', 'identifier']:
            # These should be exact matches
            return str(existing_value).lower() != str(new_value).lower()
        elif field in ['amount', 'price', 'quantity']:
            # These should be numeric equality
            try:
                return float(existing_value) != float(new_value)
            except (ValueError, TypeError):
                return True
        elif field in ['status', 'state']:
            # These should be exact matches
            return existing_value != new_value
        
        return False


class ConflictResolver:
    """
    Conflict resolver for data synchronization.
    
    Handles conflict resolution using various strategies.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.resolution_strategies = {
            ConflictResolutionStrategy.LAST_WRITE_WINS: self._resolve_last_write_wins,
            ConflictResolutionStrategy.FIRST_WRITE_WINS: self._resolve_first_write_wins,
            ConflictResolutionStrategy.MERGE: self._resolve_merge,
            ConflictResolutionStrategy.IGNORE: self._resolve_ignore,
            ConflictResolutionStrategy.ERROR: self._resolve_error,
        }
        self.custom_resolvers: Dict[str, Callable] = {}
    
    def register_custom_resolver(self, strategy_name: str, resolver: Callable):
        """Register custom conflict resolver."""
        self.custom_resolvers[strategy_name] = resolver
        self.logger.info(f"Custom resolver registered: {strategy_name}")
    
    def resolve_conflict(self, conflict: DataConflict, strategy: ConflictResolutionStrategy,
                         context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Resolve conflict using specified strategy.
        
        Args:
            conflict: Data conflict
            strategy: Resolution strategy
            context: Resolution context
            
        Returns:
            Resolved data
        """
        context = context or {}
        
        try:
            if strategy == ConflictResolutionStrategy.CUSTOM:
                resolver_name = context.get('custom_resolver')
                if resolver_name and resolver_name in self.custom_resolvers:
                    resolver = self.custom_resolvers[resolver_name]
                    return resolver(conflict, context)
                else:
                    raise IntegrationException(f"Custom resolver not found: {resolver_name}")
            
            resolver = self.resolution_strategies.get(strategy)
            if not resolver:
                raise IntegrationException(f"Unknown resolution strategy: {strategy}")
            
            resolved_data = resolver(conflict, context)
            
            # Mark conflict as resolved
            conflict.resolved_at = timezone.now()
            conflict.resolution_strategy = strategy
            conflict.resolution_data = resolved_data
            
            return resolved_data
        
        except Exception as e:
            self.logger.error(f"Conflict resolution failed: {str(e)}")
            raise
    
    def _resolve_last_write_wins(self, conflict: DataConflict, context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict with last write wins strategy."""
        # Use the newer (conflicting) data
        return conflict.conflicting_data.copy()
    
    def _resolve_first_write_wins(self, conflict: DataConflict, context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict with first write wins strategy."""
        # Use the existing data
        return conflict.existing_data.copy()
    
    def _resolve_merge(self, conflict: DataConflict, context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict with merge strategy."""
        merged_data = conflict.existing_data.copy()
        
        # Merge conflicting data
        for field, value in conflict.conflicting_data.items():
            if field in conflict.conflict_fields:
                # For conflicting fields, use newer data
                merged_data[field] = value
            else:
                # For non-conflicting fields, add if not present
                if field not in merged_data:
                    merged_data[field] = value
        
        # Add merge metadata
        merged_data['_merge_conflict'] = True
        merged_data['_merge_timestamp'] = timezone.now().isoformat()
        
        return merged_data
    
    def _resolve_ignore(self, conflict: DataConflict, context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict by ignoring (keep existing data)."""
        return conflict.existing_data.copy()
    
    def _resolve_error(self, conflict: DataConflict, context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict with error (raise exception)."""
        raise IntegrationException(f"Data conflict detected: {conflict.conflict_type.value} for {conflict.resource_type}:{conflict.resource_id}")


class SyncManager:
    """
    Data synchronization manager.
    
    Orchestrates data synchronization between
    different systems and handles conflict resolution.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.conflict_detector = ConflictDetector()
        self.conflict_resolver = ConflictResolver()
        self.active_operations: Dict[str, SyncOperation] = {}
        self.operation_history: List[SyncOperation] = []
        self.lock = threading.Lock()
        self.default_strategy = ConflictResolutionStrategy.LAST_WRITE_WINS
        self.max_retry_attempts = 3
        self.retry_delay = 1.0
        self._setup_default_resolvers()
    
    def _setup_default_resolvers(self):
        """Setup default conflict resolvers."""
        # Register custom resolvers for specific scenarios
        self.conflict_resolver.register_custom_resolver(
            "business_priority",
            self._resolve_business_priority
        )
        
        self.conflict_resolver.register_custom_resolver(
            "data_integrity",
            self._resolve_data_integrity
        )
    
    def _resolve_business_priority(self, conflict: DataConflict, context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict based on business priority."""
        # Business logic for priority-based resolution
        priority_fields = context.get('priority_fields', [])
        merged_data = conflict.existing_data.copy()
        
        for field in priority_fields:
            if field in conflict.conflicting_data:
                merged_data[field] = conflict.conflicting_data[field]
        
        # Add metadata
        merged_data['_business_priority_resolution'] = True
        merged_data['_resolution_timestamp'] = timezone.now().isoformat()
        
        return merged_data
    
    def _resolve_data_integrity(self, conflict: DataConflict, context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict ensuring data integrity."""
        merged_data = conflict.existing_data.copy()
        
        # Ensure data integrity by validating relationships
        for field, value in conflict.conflicting_data.items():
            if field in conflict.conflict_fields:
                # Validate data integrity before merging
                if self._validate_field_integrity(field, value, merged_data):
                    merged_data[field] = value
        
        # Add metadata
        merged_data['_data_integrity_resolution'] = True
        merged_data['_resolution_timestamp'] = timezone.now().isoformat()
        
        return merged_data
    
    def _validate_field_integrity(self, field: str, value: Any, existing_data: Dict[str, Any]) -> bool:
        """Validate field integrity."""
        # Business logic for field validation
        if field == 'email':
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            return re.match(email_pattern, str(value)) is not None
        elif field == 'phone':
            # Basic phone validation
            return len(str(value).replace('-', '').replace(' ', '')) >= 10
        elif field in ['amount', 'price']:
            try:
                return float(value) >= 0
            except (ValueError, TypeError):
                return False
        
        return True
    
    def synchronize_data(self, source_system: str, target_system: str,
                       resource_type: str, resource_id: str,
                       sync_data: Dict[str, Any], strategy: ConflictResolutionStrategy = None,
                       context: Dict[str, Any] = None) -> SyncOperation:
        """
        Synchronize data between systems.
        
        Args:
            source_system: Source system identifier
            target_system: Target system identifier
            resource_type: Resource type
            resource_id: Resource ID
            sync_data: Data to synchronize
            strategy: Conflict resolution strategy
            context: Synchronization context
            
        Returns:
            Synchronization operation
        """
        import uuid
        
        operation = SyncOperation(
            id=f"sync_{uuid.uuid4().hex[:12]}",
            operation_type="data_sync",
            source_system=source_system,
            target_system=target_system,
            resource_type=resource_type,
            resource_id=resource_id,
            sync_data=sync_data,
            status=SyncStatus.PENDING
        )
        
        with self.lock:
            self.active_operations[operation.id] = operation
            self.operation_history.append(operation)
        
        try:
            # Start operation
            operation.status = SyncStatus.IN_PROGRESS
            operation.started_at = timezone.now()
            
            # Get existing data
            existing_data = self._get_existing_data(target_system, resource_type, resource_id)
            
            # Detect conflicts
            if existing_data:
                conflicts = self.conflict_detector.detect_conflicts(
                    existing_data, sync_data, resource_type, resource_id
                )
                
                if conflicts:
                    operation.conflicts = conflicts
                    operation.status = SyncStatus.CONFLICT
                    
                    # Resolve conflicts
                    for conflict in conflicts:
                        resolution_strategy = strategy or self.default_strategy
                        resolved_data = self.conflict_resolver.resolve_conflict(
                            conflict, resolution_strategy, context
                        )
                        # Update sync data with resolved data
                        sync_data = resolved_data
            
            # Perform synchronization
            self._perform_sync(operation, sync_data)
            
            # Mark as completed
            operation.status = SyncStatus.COMPLETED
            operation.completed_at = timezone.now()
            
            self.logger.info(f"Synchronization completed: {operation.id}")
            return operation
        
        except Exception as e:
            operation.status = SyncStatus.FAILED
            operation.error_message = str(e)
            operation.completed_at = timezone.now()
            
            self.logger.error(f"Synchronization failed: {operation.id} - {str(e)}")
            return operation
        
        finally:
            with self.lock:
                if operation.id in self.active_operations:
                    del self.active_operations[operation.id]
    
    def _get_existing_data(self, system: str, resource_type: str, resource_id: str) -> Optional[Dict[str, Any]]:
        """Get existing data from target system."""
        # This would typically query the target system
        # For now, check cache first
        cache_key = f"sync_data_{system}_{resource_type}_{resource_id}"
        return cache.get(cache_key)
    
    def _perform_sync(self, operation: SyncOperation, sync_data: Dict[str, Any]):
        """Perform actual synchronization."""
        # Update cache
        cache_key = f"sync_data_{operation.target_system}_{operation.resource_type}_{operation.resource_id}"
        cache.set(cache_key, sync_data, timeout=3600)
        
        # This would typically update the target system database
        # For now, just log the sync
        self.logger.info(f"Synced data to {operation.target_system}: {operation.resource_type}:{operation.resource_id}")
    
    def resolve_operation_conflicts(self, operation_id: str, strategy: ConflictResolutionStrategy,
                                 context: Dict[str, Any] = None) -> bool:
        """
        Resolve conflicts for a specific operation.
        
        Args:
            operation_id: Operation ID
            strategy: Resolution strategy
            context: Resolution context
            
        Returns:
            True if conflicts resolved
        """
        with self.lock:
            operation = self.active_operations.get(operation_id)
            if not operation:
                return False
            
            if not operation.has_conflicts():
                return True
            
            try:
                # Resolve each conflict
                for conflict in operation.conflicts:
                    resolved_data = self.conflict_resolver.resolve_conflict(
                        conflict, strategy, context
                    )
                    # Update sync data with resolved data
                    operation.sync_data = resolved_data
                
                # Clear conflicts
                operation.conflicts.clear()
                operation.status = SyncStatus.IN_PROGRESS
                
                self.logger.info(f"Conflicts resolved for operation: {operation_id}")
                return True
            
            except Exception as e:
                self.logger.error(f"Failed to resolve conflicts for {operation_id}: {str(e)}")
                return False
    
    def retry_operation(self, operation_id: str) -> bool:
        """
        Retry failed synchronization operation.
        
        Args:
            operation_id: Operation ID
            
        Returns:
            True if retry initiated
        """
        with self.lock:
            operation = self.active_operations.get(operation_id)
            if not operation:
                return False
            
            if operation.status != SyncStatus.FAILED:
                return False
            
            try:
                # Reset operation status
                operation.status = SyncStatus.PENDING
                operation.error_message = None
                operation.started_at = None
                operation.completed_at = None
                
                # Retry synchronization
                return self.synchronize_data(
                    operation.source_system,
                    operation.target_system,
                    operation.resource_type,
                    operation.resource_id,
                    operation.sync_data
                )
            
            except Exception as e:
                self.logger.error(f"Failed to retry operation {operation_id}: {str(e)}")
                return False
    
    def cancel_operation(self, operation_id: str) -> bool:
        """
        Cancel synchronization operation.
        
        Args:
            operation_id: Operation ID
            
        Returns:
            True if cancelled
        """
        with self.lock:
            operation = self.active_operations.get(operation_id)
            if not operation:
                return False
            
            operation.status = SyncStatus.CANCELLED
            operation.completed_at = timezone.now()
            
            if operation_id in self.active_operations:
                del self.active_operations[operation_id]
            
            self.logger.info(f"Operation cancelled: {operation_id}")
            return True
    
    def get_operation(self, operation_id: str) -> Optional[SyncOperation]:
        """Get synchronization operation."""
        with self.lock:
            return self.active_operations.get(operation_id)
    
    def get_operations(self, status: SyncStatus = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get synchronization operations."""
        with self.lock:
            operations = list(self.active_operations.values())
        
        # Filter by status
        if status:
            operations = [op for op in operations if op.status == status]
        
        # Sort by timestamp
        operations.sort(key=lambda op: op.started_at or timezone.now(), reverse=True)
        
        # Limit results
        operations = operations[:limit]
        
        # Include recent history
        recent_history = [
            op for op in self.operation_history[-limit:]
            if op.id not in [active_op.id for active_op in self.active_operations.values()]
        ]
        
        operations.extend(recent_history)
        operations.sort(key=lambda op: op.started_at or timezone.now(), reverse=True)
        
        return [op.to_dict() for op in operations[:limit]]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get synchronization statistics."""
        with self.lock:
            total_operations = len(self.operation_history)
            active_operations = len(self.active_operations)
            
            # Count by status
            status_counts = {}
            for operation in self.operation_history:
                status = operation.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
            
            for operation in self.active_operations.values():
                status = operation.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Count by conflict type
            conflict_counts = {}
            for operation in self.operation_history:
                for conflict in operation.conflicts:
                    conflict_type = conflict.conflict_type.value
                    conflict_counts[conflict_type] = conflict_counts.get(conflict_type, 0) + 1
            
            for operation in self.active_operations.values():
                for conflict in operation.conflicts:
                    conflict_type = conflict.conflict_type.value
                    conflict_counts[conflict_type] = conflict_counts.get(conflict_type, 0) + 1
        
            return {
                'total_operations': total_operations,
                'active_operations': active_operations,
                'status_counts': status_counts,
                'conflict_counts': conflict_counts,
                'default_strategy': self.default_strategy.value,
            }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        with self.lock:
            active_count = len(self.active_operations)
            failed_count = len([op for op in self.active_operations.values() if op.status == SyncStatus.FAILED])
            conflict_count = len([op for op in self.active_operations.values() if op.has_conflicts()])
            
            health_status = 'healthy'
            issues = []
            
            if failed_count > 0:
                health_status = 'unhealthy'
                issues.append(f"{failed_count} operations failed")
            
            if conflict_count > 0:
                health_status = 'degraded'
                issues.append(f"{conflict_count} operations have conflicts")
            
            if active_count > 100:
                health_status = 'degraded'
                issues.append(f"High number of active operations: {active_count}")
            
            return {
                'overall': health_status,
                'active_operations': active_count,
                'failed_operations': failed_count,
                'conflict_operations': conflict_count,
                'issues': issues,
                'timestamp': timezone.now().isoformat(),
            }


# Global sync manager instance
sync_manager = SyncManager()


# Convenience functions
def synchronize_data(source_system: str, target_system: str, resource_type: str, resource_id: str,
                  sync_data: Dict[str, Any], strategy: ConflictResolutionStrategy = None,
                  context: Dict[str, Any] = None) -> SyncOperation:
    """Synchronize data between systems."""
    return sync_manager.synchronize_data(
        source_system, target_system, resource_type, resource_id,
        sync_data, strategy, context
    )


def resolve_conflicts(operation_id: str, strategy: ConflictResolutionStrategy,
                       context: Dict[str, Any] = None) -> bool:
    """Resolve conflicts for operation."""
    return sync_manager.resolve_operation_conflicts(operation_id, strategy, context)


def get_sync_statistics() -> Dict[str, Any]:
    """Get synchronization statistics."""
    return sync_manager.get_statistics()


def perform_sync_health_check() -> Dict[str, Any]:
    """Perform synchronization health check."""
    return sync_manager.health_check()
