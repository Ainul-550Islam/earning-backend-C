"""
Sync Manager - Data Conflict Resolution System

Advanced synchronization manager for handling data conflicts,
resolving inconsistencies, and maintaining data integrity across systems.
"""
import time

import logging
import threading
from typing import Dict, Any, List, Optional, Callable, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty, PriorityQueue
from collections import defaultdict
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction

from .integ_constants import IntegrationEvent, IntegrationStatus
from .integ_exceptions import IntegrationError
from .data_bridge import DataBridge, SyncDirection, ConflictResolution
from .event_bus import event_bus, Event

logger = logging.getLogger(__name__)


class ConflictType(Enum):
    """Types of data conflicts."""
    VERSION_CONFLICT = "version_conflict"
    DATA_CONFLICT = "data_conflict"
    SCHEMA_CONFLICT = "schema_conflict"
    REFERENCE_CONFLICT = "reference_conflict"
    BUSINESS_RULE_CONFLICT = "business_rule_conflict"
    TIMESTAMP_CONFLICT = "timestamp_conflict"
    DUPLICATE_CONFLICT = "duplicate_conflict"


class ConflictSeverity(Enum):
    """Conflict severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResolutionStrategy(Enum):
    """Conflict resolution strategies."""
    SOURCE_WINS = "source_wins"
    TARGET_WINS = "target_wins"
    LATEST_WINS = "latest_wins"
    MANUAL = "manual"
    MERGE = "merge"
    CUSTOM = "custom"
    IGNORE = "ignore"
    DELETE = "delete"


@dataclass
class Conflict:
    """Data conflict representation."""
    conflict_id: str
    bridge_name: str
    conflict_type: ConflictType
    severity: ConflictSeverity
    source_data: Dict[str, Any]
    target_data: Dict[str, Any]
    field_name: str
    source_value: Any
    target_value: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    detected_at: datetime = field(default_factory=timezone.now)
    resolved_at: Optional[datetime] = None
    resolution_strategy: Optional[ResolutionStrategy] = None
    resolved_value: Optional[Any] = None
    resolved_by: Optional[str] = None
    auto_resolvable: bool = True
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class SyncConflict:
    """Synchronization conflict with context."""
    sync_id: str
    bridge_name: str
    conflicts: List[Conflict] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=timezone.now)
    resolved_at: Optional[datetime] = None
    resolution_summary: str = ""
    auto_resolved: bool = False
    requires_manual_intervention: bool = False


@dataclass
class ResolutionRule:
    """Conflict resolution rule."""
    name: str
    conflict_type: ConflictType
    field_patterns: List[str]
    strategy: ResolutionStrategy
    conditions: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    auto_apply: bool = True
    custom_resolver: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SyncManager:
    """Advanced synchronization manager with conflict resolution."""
    
    def __init__(self):
        self.conflicts: Dict[str, SyncConflict] = {}
        self.resolution_rules: Dict[str, ResolutionRule] = {}
        self.conflict_queue = PriorityQueue(maxsize=1000)
        self.manual_queue = Queue(maxsize=500)
        self.resolvers: Dict[str, Callable] = {}
        self.statistics = {
            'total_conflicts': 0,
            'auto_resolved': 0,
            'manually_resolved': 0,
            'failed_resolutions': 0,
            'conflicts_by_type': {},
            'conflicts_by_severity': {},
            'average_resolution_time': 0.0,
            'last_conflict_time': None
        }
        self._lock = threading.RLock()
        self._running = False
        self._resolver_thread: Optional[threading.Thread] = None
        self._manual_thread: Optional[threading.Thread] = None
        
        # Initialize default resolution rules
        self._initialize_resolution_rules()
        self._register_default_resolvers()
        
        # Start conflict resolution
        self._start_conflict_resolution()
    
    def _initialize_resolution_rules(self):
        """Initialize default conflict resolution rules."""
        default_rules = [
            # Timestamp conflicts - use latest
            ResolutionRule(
                name="timestamp_latest",
                conflict_type=ConflictType.TIMESTAMP_CONFLICT,
                field_patterns=["updated_at", "modified_at", "created_at"],
                strategy=ResolutionStrategy.LATEST_WINS,
                priority=100,
                auto_apply=True
            ),
            
            # Version conflicts - use higher version
            ResolutionRule(
                name="version_higher",
                conflict_type=ConflictType.VERSION_CONFLICT,
                field_patterns=["version", "revision", "v"],
                strategy=ResolutionStrategy.SOURCE_WINS,
                priority=90,
                auto_apply=True,
                conditions={"prefer": "source"}
            ),
            
            # Numeric conflicts - use higher value
            ResolutionRule(
                name="numeric_higher",
                conflict_type=ConflictType.DATA_CONFLICT,
                field_patterns=["count", "amount", "quantity", "score", "rating"],
                strategy=ResolutionStrategy.MERGE,
                priority=80,
                auto_apply=True
            ),
            
            # Text conflicts - prefer longer/more detailed
            ResolutionRule(
                name="text_longer",
                conflict_type=ConflictType.DATA_CONFLICT,
                field_patterns=["description", "notes", "comments", "content"],
                strategy=ResolutionStrategy.MERGE,
                priority=70,
                auto_apply=True
            ),
            
            # Boolean conflicts - conservative approach
            ResolutionRule(
                name="boolean_conservative",
                conflict_type=ConflictType.DATA_CONFLICT,
                field_patterns=["active", "enabled", "deleted", "archived"],
                strategy=ResolutionStrategy.TARGET_WINS,
                priority=60,
                auto_apply=True
            ),
            
            # Critical conflicts - require manual intervention
            ResolutionRule(
                name="critical_manual",
                conflict_type=ConflictType.BUSINESS_RULE_CONFLICT,
                field_patterns=["*"],
                strategy=ResolutionStrategy.MANUAL,
                priority=10,
                auto_apply=False
            )
        ]
        
        for rule in default_rules:
            self.resolution_rules[rule.name] = rule
    
    def _register_default_resolvers(self):
        """Register default conflict resolvers."""
        self.resolvers.update({
            'merge_resolver': self._merge_resolver,
            'latest_resolver': self._latest_resolver,
            'higher_value_resolver': self._higher_value_resolver,
            'concatenation_resolver': self._concatenation_resolver,
            'average_resolver': self._average_resolver,
            'union_resolver': self._union_resolver,
            'intersection_resolver': self._intersection_resolver
        })
    
    def _start_conflict_resolution(self):
        """Start conflict resolution threads."""
        self._running = True
        
        # Start automatic resolver thread
        self._resolver_thread = threading.Thread(
            target=self._auto_resolver_loop,
            name="SyncAutoResolver",
            daemon=True
        )
        self._resolver_thread.start()
        
        # Start manual intervention thread
        self._manual_thread = threading.Thread(
            target=self._manual_intervention_loop,
            name="SyncManualResolver",
            daemon=True
        )
        self._manual_thread.start()
        
        logger.info("Started sync manager conflict resolution")
    
    def _auto_resolver_loop(self):
        """Automatic conflict resolution loop."""
        while self._running:
            try:
                # Get conflict from queue
                try:
                    priority, conflict_id = self.conflict_queue.get(timeout=1)
                    sync_conflict = self.conflicts.get(conflict_id)
                    
                    if sync_conflict and not sync_conflict.requires_manual_intervention:
                        self._resolve_sync_conflict(sync_conflict)
                    
                    self.conflict_queue.task_done()
                    
                except Empty:
                    continue
                
            except Exception as e:
                logger.error(f"Auto resolver loop error: {str(e)}")
                time.sleep(1)
    
    def _manual_intervention_loop(self):
        """Manual intervention loop."""
        while self._running:
            try:
                # Get conflict requiring manual intervention
                try:
                    sync_conflict = self.manual_queue.get(timeout=5)
                    
                    # This would typically notify administrators
                    # For now, we'll just log it
                    logger.warning(f"Manual intervention required for conflict: {sync_conflict.sync_id}")
                    
                    self.manual_queue.task_done()
                    
                except Empty:
                    continue
                
            except Exception as e:
                logger.error(f"Manual intervention loop error: {str(e)}")
                time.sleep(5)
    
    def detect_conflicts(self, bridge_name: str, source_data: Dict[str, Any], 
                        target_data: Dict[str, Any], context: Dict[str, Any] = None) -> List[Conflict]:
        """Detect conflicts between source and target data."""
        conflicts = []
        
        try:
            # Compare data fields
            all_fields = set(source_data.keys()) | set(target_data.keys())
            
            for field in all_fields:
                source_value = source_data.get(field)
                target_value = target_data.get(field)
                
                # Skip if both values are the same
                if source_value == target_value:
                    continue
                
                # Determine conflict type and severity
                conflict_type, severity = self._classify_conflict(field, source_value, target_value, context)
                
                if conflict_type:
                    conflict = Conflict(
                        conflict_id=f"conflict_{bridge_name}_{field}_{timezone.now().timestamp()}",
                        bridge_name=bridge_name,
                        conflict_type=conflict_type,
                        severity=severity,
                        source_data=source_data,
                        target_data=target_data,
                        field_name=field,
                        source_value=source_value,
                        target_value=target_value,
                        metadata={'context': context or {}}
                    )
                    
                    conflicts.append(conflict)
            
            logger.debug(f"Detected {len(conflicts)} conflicts for bridge: {bridge_name}")
            
        except Exception as e:
            logger.error(f"Conflict detection failed: {str(e)}")
        
        return conflicts
    
    def _classify_conflict(self, field: str, source_value: Any, target_value: Any, 
                          context: Dict[str, Any]) -> Tuple[Optional[ConflictType], ConflictSeverity]:
        """Classify conflict type and severity."""
        # Timestamp conflicts
        if field in ['updated_at', 'modified_at', 'created_at', 'timestamp']:
            return ConflictType.TIMESTAMP_CONFLICT, ConflictSeverity.MEDIUM
        
        # Version conflicts
        if field in ['version', 'revision', 'v']:
            return ConflictType.VERSION_CONFLICT, ConflictSeverity.HIGH
        
        # ID conflicts
        if field in ['id', 'uuid', 'primary_key']:
            return ConflictType.DATA_CONFLICT, ConflictSeverity.CRITICAL
        
        # Business critical fields
        if field in ['status', 'state', 'amount', 'price', 'balance']:
            return ConflictType.BUSINESS_RULE_CONFLICT, ConflictSeverity.HIGH
        
        # Reference conflicts
        if field.endswith('_id') or field.endswith('_ref'):
            return ConflictType.REFERENCE_CONFLICT, ConflictSeverity.HIGH
        
        # Data type conflicts
        if type(source_value).__name__ != type(target_value).__name__:
            return ConflictType.SCHEMA_CONFLICT, ConflictSeverity.MEDIUM
        
        # General data conflict
        return ConflictType.DATA_CONFLICT, ConflictSeverity.MEDIUM
    
    def create_sync_conflict(self, bridge_name: str, conflicts: List[Conflict],
                           context: Dict[str, Any] = None) -> str:
        """Create a sync conflict record."""
        sync_id = f"sync_conflict_{bridge_name}_{timezone.now().timestamp()}"
        
        sync_conflict = SyncConflict(
            sync_id=sync_id,
            bridge_name=bridge_name,
            conflicts=conflicts,
            context=context or {},
            created_at=timezone.now()
        )
        
        # Determine if manual intervention is required
        sync_conflict.requires_manual_intervention = any(
            not conflict.auto_resolvable or conflict.severity == ConflictSeverity.CRITICAL
            for conflict in conflicts
        )
        
        # Store conflict
        with self._lock:
            self.conflicts[sync_id] = sync_conflict
            self.statistics['total_conflicts'] += len(conflicts)
            self.statistics['last_conflict_time'] = timezone.now()
            
            # Update conflict type statistics
            for conflict in conflicts:
                conflict_type = conflict.conflict_type.value
                if conflict_type not in self.statistics['conflicts_by_type']:
                    self.statistics['conflicts_by_type'][conflict_type] = 0
                self.statistics['conflicts_by_type'][conflict_type] += 1
                
                # Update severity statistics
                severity = conflict.severity.value
                if severity not in self.statistics['conflicts_by_severity']:
                    self.statistics['conflicts_by_severity'][severity] = 0
                self.statistics['conflicts_by_severity'][severity] += 1
        
        # Add to appropriate queue
        if sync_conflict.requires_manual_intervention:
            self.manual_queue.put(sync_conflict)
        else:
            # Priority based on severity and conflict count
            priority = self._calculate_conflict_priority(sync_conflict)
            self.conflict_queue.put((-priority, sync_id))  # Negative for max-heap
        
        logger.info(f"Created sync conflict: {sync_id} with {len(conflicts)} conflicts")
        return sync_id
    
    def _calculate_conflict_priority(self, sync_conflict: SyncConflict) -> int:
        """Calculate conflict priority for queue ordering."""
        priority = 0
        
        # Add priority for critical conflicts
        critical_count = sum(1 for c in sync_conflict.conflicts if c.severity == ConflictSeverity.CRITICAL)
        priority += critical_count * 1000
        
        # Add priority for high severity conflicts
        high_count = sum(1 for c in sync_conflict.conflicts if c.severity == ConflictSeverity.HIGH)
        priority += high_count * 100
        
        # Add priority for conflict count
        priority += len(sync_conflict.conflicts)
        
        return priority
    
    def _resolve_sync_conflict(self, sync_conflict: SyncConflict):
        """Resolve a sync conflict automatically."""
        start_time = timezone.now()
        
        try:
            resolved_conflicts = []
            failed_conflicts = []
            
            for conflict in sync_conflict.conflicts:
                try:
                    # Find applicable resolution rule
                    rule = self._find_resolution_rule(conflict)
                    
                    if rule and rule.auto_apply:
                        # Apply resolution strategy
                        resolved_value = self._apply_resolution_strategy(conflict, rule)
                        
                        # Update conflict
                        conflict.resolved_at = timezone.now()
                        conflict.resolution_strategy = rule.strategy
                        conflict.resolved_value = resolved_value
                        conflict.resolved_by = "auto_resolver"
                        
                        resolved_conflicts.append(conflict)
                        
                    else:
                        # No applicable rule or manual intervention required
                        failed_conflicts.append(conflict)
                        
                except Exception as e:
                    logger.error(f"Failed to resolve conflict {conflict.conflict_id}: {str(e)}")
                    failed_conflicts.append(conflict)
            
            # Update sync conflict
            sync_conflict.resolved_at = timezone.now()
            sync_conflict.auto_resolved = len(resolved_conflicts) > 0 and len(failed_conflicts) == 0
            
            if sync_conflict.auto_resolved:
                sync_conflict.resolution_summary = f"Auto-resolved {len(resolved_conflicts)} conflicts"
                self.statistics['auto_resolved'] += len(resolved_conflicts)
            else:
                sync_conflict.resolution_summary = f"Resolved {len(resolved_conflicts)} conflicts, {len(failed_conflicts)} failed"
                if len(resolved_conflicts) > 0:
                    self.statistics['auto_resolved'] += len(resolved_conflicts)
                if len(failed_conflicts) > 0:
                    self.statistics['failed_resolutions'] += len(failed_conflicts)
            
            # Update average resolution time
            resolution_time = (timezone.now() - start_time).total_seconds()
            total_resolved = self.statistics['auto_resolved'] + self.statistics['manually_resolved']
            if total_resolved == 1:
                self.statistics['average_resolution_time'] = resolution_time
            else:
                current_avg = self.statistics['average_resolution_time']
                self.statistics['average_resolution_time'] = (
                    (current_avg * (total_resolved - 1) + resolution_time) / total_resolved
                )
            
            # Publish conflict resolution event
            self._publish_conflict_resolution_event(sync_conflict)
            
            logger.info(f"Resolved sync conflict: {sync_conflict.sync_id}")
            
        except Exception as e:
            logger.error(f"Failed to resolve sync conflict {sync_conflict.sync_id}: {str(e)}")
            self.statistics['failed_resolutions'] += 1
    
    def _find_resolution_rule(self, conflict: Conflict) -> Optional[ResolutionRule]:
        """Find applicable resolution rule for conflict."""
        applicable_rules = []
        
        for rule in self.resolution_rules.values():
            if rule.conflict_type == conflict.conflict_type:
                # Check field pattern matching
                field_matches = any(
                    self._matches_field_pattern(conflict.field_name, pattern)
                    for pattern in rule.field_patterns
                )
                
                if field_matches:
                    # Check conditions
                    if self._meets_conditions(conflict, rule.conditions):
                        applicable_rules.append(rule)
        
        # Return highest priority rule
        if applicable_rules:
            return max(applicable_rules, key=lambda r: r.priority)
        
        return None
    
    def _matches_field_pattern(self, field_name: str, pattern: str) -> bool:
        """Check if field name matches pattern."""
        if pattern == "*":
            return True
        elif pattern in field_name:
            return True
        elif pattern.startswith("*") and field_name.endswith(pattern[1:]):
            return True
        elif pattern.endswith("*") and field_name.startswith(pattern[:-1]):
            return True
        else:
            return field_name == pattern
    
    def _meets_conditions(self, conflict: Conflict, conditions: Dict[str, Any]) -> bool:
        """Check if conflict meets resolution conditions."""
        if not conditions:
            return True
        
        # Check severity condition
        if 'severity' in conditions:
            required_severity = conditions['severity']
            if isinstance(required_severity, str):
                if conflict.severity.value != required_severity:
                    return False
            elif isinstance(required_severity, list):
                if conflict.severity.value not in required_severity:
                    return False
        
        # Check value type conditions
        if 'value_type' in conditions:
            required_type = conditions['value_type']
            source_type = type(conflict.source_value).__name__
            target_type = type(conflict.target_value).__name__
            
            if required_type == 'numeric':
                if not (isinstance(conflict.source_value, (int, float)) and 
                       isinstance(conflict.target_value, (int, float))):
                    return False
            elif required_type == 'string':
                if not (isinstance(conflict.source_value, str) and 
                       isinstance(conflict.target_value, str)):
                    return False
        
        return True
    
    def _apply_resolution_strategy(self, conflict: Conflict, rule: ResolutionRule) -> Any:
        """Apply resolution strategy to conflict."""
        if rule.strategy == ResolutionStrategy.SOURCE_WINS:
            return conflict.source_value
        elif rule.strategy == ResolutionStrategy.TARGET_WINS:
            return conflict.target_value
        elif rule.strategy == ResolutionStrategy.LATEST_WINS:
            return self._latest_resolver(conflict)
        elif rule.strategy == ResolutionStrategy.MERGE:
            return self._merge_resolver(conflict)
        elif rule.strategy == ResolutionStrategy.CUSTOM and rule.custom_resolver:
            resolver = self.resolvers.get(rule.custom_resolver)
            if resolver:
                return resolver(conflict)
            else:
                raise IntegrationError(f"Custom resolver not found: {rule.custom_resolver}")
        else:
            # Default to source wins
            return conflict.source_value
    
    # Default resolvers
    def _merge_resolver(self, conflict: Conflict) -> Any:
        """Merge conflicting values."""
        source_val = conflict.source_value
        target_val = conflict.target_value
        
        # Handle different data types
        if isinstance(source_val, dict) and isinstance(target_val, dict):
            merged = target_val.copy()
            merged.update(source_val)
            return merged
        elif isinstance(source_val, list) and isinstance(target_val, list):
            return list(set(source_val + target_val))
        elif isinstance(source_val, str) and isinstance(target_val, str):
            # Concatenate strings
            return f"{source_val} {target_val}"
        else:
            # Default to source
            return source_val
    
    def _latest_resolver(self, conflict: Conflict) -> Any:
        """Resolve by latest timestamp."""
        # This would need timestamp information from context
        # For now, default to source
        return conflict.source_value
    
    def _higher_value_resolver(self, conflict: Conflict) -> Any:
        """Resolve by higher value."""
        try:
            if isinstance(conflict.source_value, (int, float)) and isinstance(conflict.target_value, (int, float)):
                return max(conflict.source_value, conflict.target_value)
            else:
                return conflict.source_value
        except (ValueError, TypeError):
            return conflict.source_value
    
    def _concatenation_resolver(self, conflict: Conflict) -> Any:
        """Resolve by concatenating values."""
        if isinstance(conflict.source_value, str) and isinstance(conflict.target_value, str):
            return f"{conflict.source_value}, {conflict.target_value}"
        else:
            return conflict.source_value
    
    def _average_resolver(self, conflict: Conflict) -> Any:
        """Resolve by averaging values."""
        try:
            if isinstance(conflict.source_value, (int, float)) and isinstance(conflict.target_value, (int, float)):
                return (conflict.source_value + conflict.target_value) / 2
            else:
                return conflict.source_value
        except (ValueError, TypeError):
            return conflict.source_value
    
    def _union_resolver(self, conflict: Conflict) -> Any:
        """Resolve by union of sets/lists."""
        if isinstance(conflict.source_value, set) and isinstance(conflict.target_value, set):
            return conflict.source_value.union(conflict.target_value)
        elif isinstance(conflict.source_value, list) and isinstance(conflict.target_value, list):
            return list(set(conflict.source_value + conflict.target_value))
        else:
            return conflict.source_value
    
    def _intersection_resolver(self, conflict: Conflict) -> Any:
        """Resolve by intersection of sets/lists."""
        if isinstance(conflict.source_value, set) and isinstance(conflict.target_value, set):
            return conflict.source_value.intersection(conflict.target_value)
        elif isinstance(conflict.source_value, list) and isinstance(conflict.target_value, list):
            return list(set(conflict.source_value) & set(conflict.target_value))
        else:
            return conflict.source_value
    
    def manually_resolve_conflict(self, sync_id: str, conflict_id: str, 
                                resolution_strategy: ResolutionStrategy, resolved_value: Any,
                                resolved_by: str = "manual"):
        """Manually resolve a specific conflict."""
        with self._lock:
            sync_conflict = self.conflicts.get(sync_id)
            if not sync_conflict:
                raise IntegrationError(f"Sync conflict not found: {sync_id}")
            
            # Find the specific conflict
            conflict = None
            for c in sync_conflict.conflicts:
                if c.conflict_id == conflict_id:
                    conflict = c
                    break
            
            if not conflict:
                raise IntegrationError(f"Conflict not found: {conflict_id}")
            
            # Apply resolution
            conflict.resolved_at = timezone.now()
            conflict.resolution_strategy = resolution_strategy
            conflict.resolved_value = resolved_value
            conflict.resolved_by = resolved_by
            
            # Check if all conflicts are resolved
            all_resolved = all(c.resolved_at is not None for c in sync_conflict.conflicts)
            if all_resolved:
                sync_conflict.resolved_at = timezone.now()
                sync_conflict.resolution_summary = f"Manually resolved all conflicts"
                self.statistics['manually_resolved'] += len(sync_conflict.conflicts)
            
            logger.info(f"Manually resolved conflict: {conflict_id}")
    
    def get_conflict(self, sync_id: str) -> Optional[SyncConflict]:
        """Get sync conflict by ID."""
        return self.conflicts.get(sync_id)
    
    def get_conflicts(self, bridge_name: str = None, resolved: bool = None, 
                     severity: ConflictSeverity = None) -> List[SyncConflict]:
        """Get conflicts with filters."""
        conflicts = list(self.conflicts.values())
        
        # Apply filters
        if bridge_name:
            conflicts = [c for c in conflicts if c.bridge_name == bridge_name]
        
        if resolved is not None:
            if resolved:
                conflicts = [c for c in conflicts if c.resolved_at is not None]
            else:
                conflicts = [c for c in conflicts if c.resolved_at is None]
        
        if severity:
            conflicts = [
                c for c in conflicts 
                if any(conf.severity == severity for conf in c.conflicts)
            ]
        
        # Sort by creation time (newest first)
        conflicts.sort(key=lambda c: c.created_at, reverse=True)
        
        return conflicts
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get sync manager statistics."""
        with self._lock:
            stats = self.statistics.copy()
            stats.update({
                'total_sync_conflicts': len(self.conflicts),
                'unresolved_conflicts': len([c for c in self.conflicts.values() if c.resolved_at is None]),
                'manual_intervention_queue_size': self.manual_queue.qsize(),
                'auto_resolution_queue_size': self.conflict_queue.qsize(),
                'total_resolution_rules': len(self.resolution_rules),
                'total_resolvers': len(self.resolvers),
                'running': self._running
            })
            return stats
    
    def register_resolution_rule(self, rule: ResolutionRule):
        """Register a resolution rule."""
        self.resolution_rules[rule.name] = rule
        logger.info(f"Registered resolution rule: {rule.name}")
    
    def register_resolver(self, name: str, resolver: Callable):
        """Register a custom resolver."""
        self.resolvers[name] = resolver
        logger.info(f"Registered resolver: {name}")
    
    def _publish_conflict_resolution_event(self, sync_conflict: SyncConflict):
        """Publish conflict resolution event."""
        try:
            import asyncio
            
            event_data = {
                'sync_id': sync_conflict.sync_id,
                'bridge_name': sync_conflict.bridge_name,
                'conflict_count': len(sync_conflict.conflicts),
                'resolved_at': sync_conflict.resolved_at.isoformat() if sync_conflict.resolved_at else None,
                'auto_resolved': sync_conflict.auto_resolved,
                'requires_manual_intervention': sync_conflict.requires_manual_intervention,
                'resolution_summary': sync_conflict.resolution_summary
            }
            
            asyncio.create_task(event_bus.publish(
                Event("sync.conflict.resolved", event_data)
            ))
            
        except Exception as e:
            logger.error(f"Failed to publish conflict resolution event: {str(e)}")
    
    def cleanup_old_conflicts(self, older_than_days: int = 30) -> int:
        """Clean up old resolved conflicts."""
        cutoff_date = timezone.now() - timedelta(days=older_than_days)
        
        with self._lock:
            old_conflicts = [
                sync_id for sync_id, conflict in self.conflicts.items()
                if conflict.resolved_at and conflict.resolved_at < cutoff_date
            ]
            
            for sync_id in old_conflicts:
                del self.conflicts[sync_id]
            
            logger.info(f"Cleaned up {len(old_conflicts)} old conflicts")
            return len(old_conflicts)
    
    def shutdown(self):
        """Shutdown sync manager."""
        logger.info("Shutting down sync manager...")
        
        self._running = False
        
        # Wait for threads to finish
        if self._resolver_thread:
            self._resolver_thread.join(timeout=5)
        
        if self._manual_thread:
            self._manual_thread.join(timeout=5)
        
        logger.info("Sync manager shutdown complete")


# Global sync manager instance
sync_manager = SyncManager()


# Decorator for conflict detection
def detect_conflicts(bridge_name: str):
    """Decorator to detect conflicts in data operations."""
    def decorator(func):
        def wrapper(source_data, target_data, *args, **kwargs):
            # Detect conflicts
            conflicts = sync_manager.detect_conflicts(
                bridge_name, source_data, target_data, kwargs
            )
            
            if conflicts:
                # Create sync conflict
                sync_id = sync_manager.create_sync_conflict(
                    bridge_name, conflicts, kwargs
                )
                
                # This would typically wait for resolution or handle it
                logger.warning(f"Conflicts detected: {sync_id}")
            
            return func(source_data, target_data, *args, **kwargs)
        return wrapper
    return decorator


# Convenience functions
def create_resolution_rule(name: str, conflict_type: ConflictType, strategy: ResolutionStrategy,
                         field_patterns: List[str], **kwargs) -> ResolutionRule:
    """Create a resolution rule."""
    return ResolutionRule(
        name=name,
        conflict_type=conflict_type,
        strategy=strategy,
        field_patterns=field_patterns,
        **kwargs
    )
