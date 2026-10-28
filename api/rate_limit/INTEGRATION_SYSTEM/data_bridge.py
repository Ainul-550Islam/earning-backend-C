"""
Data Bridge - Cross-System Data Synchronization

Data bridge implementation for synchronizing data between different systems
and services with support for real-time sync, conflict resolution, and data mapping.
"""

import logging
import asyncio
import threading
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction

from .integ_constants import IntegrationEvent, IntegrationStatus, IntegrationPriority
from .integ_exceptions import IntegrationError, DataBridgeError
from .transformer import DataTransformer, TransformationRule
from .event_bus import event_bus, Event
from .circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class SyncDirection(Enum):
    """Data synchronization directions."""
    ONE_WAY = "one_way"          # Source to target only
    TWO_WAY = "two_way"          # Bidirectional sync
    MASTER_SLAVE = "master_slave"  # Master to slave only


class ConflictResolution(Enum):
    """Conflict resolution strategies."""
    SOURCE_WINS = "source_wins"
    TARGET_WINS = "target_wins"
    LATEST_WINS = "latest_wins"
    MANUAL = "manual"
    MERGE = "merge"
    CUSTOM = "custom"


class SyncStatus(Enum):
    """Synchronization status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"
    CANCELLED = "cancelled"


@dataclass
class DataBridgeConfig:
    """Data bridge configuration."""
    name: str
    source_system: str
    target_system: str
    sync_direction: SyncDirection
    conflict_resolution: ConflictResolution
    sync_interval: int = 300  # seconds
    batch_size: int = 100
    max_retries: int = 3
    retry_delay: int = 60
    transformation_rules: List[TransformationRule] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    field_mappings: Dict[str, str] = field(default_factory=dict)
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncRecord:
    """Synchronization record."""
    sync_id: str
    bridge_name: str
    source_system: str
    target_system: str
    source_data: Dict[str, Any]
    target_data: Dict[str, Any]
    status: SyncStatus = SyncStatus.PENDING
    error_message: Optional[str] = None
    conflict_details: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=timezone.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConflictRecord:
    """Conflict resolution record."""
    conflict_id: str
    sync_id: str
    bridge_name: str
    field_name: str
    source_value: Any
    target_value: Any
    resolution: Optional[ConflictResolution] = None
    resolved_value: Optional[Any] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    created_at: datetime = field(default_factory=timezone.now)


class DataBridge:
    """Data bridge for cross-system synchronization."""
    
    def __init__(self, config: DataBridgeConfig):
        self.config = config
        self.transformer = DataTransformer()
        self.circuit_breaker = CircuitBreaker(
            integration_name=f"data_bridge_{config.name}",
            failure_threshold=3,
            recovery_timeout=60,
            expected_exception=DataBridgeError
        )
        self.sync_queue = Queue(maxsize=1000)
        self.conflict_queue = Queue(maxsize=500)
        self.statistics = {
            'total_syncs': 0,
            'successful_syncs': 0,
            'failed_syncs': 0,
            'conflicts_detected': 0,
            'conflicts_resolved': 0,
            'average_sync_time': 0.0,
            'last_sync_time': None
        }
        self._lock = threading.RLock()
        self._sync_thread: Optional[threading.Thread] = None
        self._conflict_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Register transformation rules
        for rule in config.transformation_rules:
            self.transformer.register_transformation_rule(rule)
        
        # Start background threads
        self._start_background_threads()
    
    def _start_background_threads(self):
        """Start background threads for sync and conflict resolution."""
        self._running = True
        
        # Sync thread
        self._sync_thread = threading.Thread(
            target=self._sync_worker_loop,
            name=f"DataBridgeSync-{self.config.name}",
            daemon=True
        )
        self._sync_thread.start()
        
        # Conflict resolution thread
        self._conflict_thread = threading.Thread(
            target=self._conflict_worker_loop,
            name=f"DataBridgeConflict-{self.config.name}",
            daemon=True
        )
        self._conflict_thread.start()
        
        logger.info(f"Started background threads for data bridge: {self.config.name}")
    
    def _sync_worker_loop(self):
        """Worker thread loop for processing sync operations."""
        while self._running:
            try:
                # Get sync record from queue
                sync_record = self.sync_queue.get(timeout=1)
                
                # Process sync
                self._process_sync_record(sync_record)
                
                # Mark task as done
                self.sync_queue.task_done()
                
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Sync worker error: {str(e)}")
    
    def _conflict_worker_loop(self):
        """Worker thread loop for processing conflicts."""
        while self._running:
            try:
                # Get conflict from queue
                conflict = self.conflict_queue.get(timeout=1)
                
                # Process conflict
                self._process_conflict(conflict)
                
                # Mark task as done
                self.conflict_queue.task_done()
                
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Conflict worker error: {str(e)}")
    
    def _process_sync_record(self, sync_record: SyncRecord):
        """Process sync record."""
        start_time = timezone.now()
        
        try:
            sync_record.status = SyncStatus.IN_PROGRESS
            sync_record.started_at = start_time
            
            # Apply filters
            if not self._passes_filters(sync_record.source_data):
                sync_record.status = SyncStatus.COMPLETED
                sync_record.completed_at = timezone.now()
                return
            
            # Transform data
            transformed_data = self._transform_data(sync_record.source_data)
            
            # Check for conflicts
            conflicts = self._detect_conflicts(transformed_data, sync_record.target_data)
            
            if conflicts:
                sync_record.status = SyncStatus.CONFLICT
                sync_record.conflict_details = conflicts
                
                # Add conflicts to queue
                for conflict in conflicts:
                    self.conflict_queue.put(conflict)
                
                self.statistics['conflicts_detected'] += len(conflicts)
                return
            
            # Perform sync
            success = self._perform_sync(transformed_data, sync_record.target_data)
            
            if success:
                sync_record.status = SyncStatus.COMPLETED
                sync_record.completed_at = timezone.now()
                self.statistics['successful_syncs'] += 1
            else:
                sync_record.status = SyncStatus.FAILED
                sync_record.error_message = "Sync operation failed"
                self.statistics['failed_syncs'] += 1
            
            # Update statistics
            sync_time = (timezone.now() - start_time).total_seconds()
            self._update_sync_statistics(sync_time)
            
            # Publish sync event
            self._publish_sync_event(sync_record)
            
        except Exception as e:
            logger.error(f"Sync processing failed: {str(e)}")
            sync_record.status = SyncStatus.FAILED
            sync_record.error_message = str(e)
            sync_record.completed_at = timezone.now()
            self.statistics['failed_syncs'] += 1
    
    def _process_conflict(self, conflict: ConflictRecord):
        """Process conflict resolution."""
        try:
            if self.config.conflict_resolution == ConflictResolution.SOURCE_WINS:
                conflict.resolution = ConflictResolution.SOURCE_WINS
                conflict.resolved_value = conflict.source_value
            elif self.config.conflict_resolution == ConflictResolution.TARGET_WINS:
                conflict.resolution = ConflictResolution.TARGET_WINS
                conflict.resolved_value = conflict.target_value
            elif self.config.conflict_resolution == ConflictResolution.LATEST_WINS:
                # Compare timestamps if available
                source_time = conflict.source_data.get('updated_at', timezone.now())
                target_time = conflict.target_data.get('updated_at', timezone.now())
                
                if source_time > target_time:
                    conflict.resolution = ConflictResolution.SOURCE_WINS
                    conflict.resolved_value = conflict.source_value
                else:
                    conflict.resolution = ConflictResolution.TARGET_WINS
                    conflict.resolved_value = conflict.target_value
            elif self.config.conflict_resolution == ConflictResolution.MERGE:
                conflict.resolution = ConflictResolution.MERGE
                conflict.resolved_value = self._merge_data(conflict.source_value, conflict.target_value)
            else:
                # Manual resolution - leave for manual intervention
                return
            
            conflict.resolved_at = timezone.now()
            conflict.resolved_by = "system"
            
            # Apply resolution
            self._apply_conflict_resolution(conflict)
            
            self.statistics['conflicts_resolved'] += 1
            
            # Publish conflict resolution event
            self._publish_conflict_event(conflict)
            
        except Exception as e:
            logger.error(f"Conflict processing failed: {str(e)}")
    
    def _passes_filters(self, data: Dict[str, Any]) -> bool:
        """Check if data passes filters."""
        if not self.config.filters:
            return True
        
        for field, filter_config in self.config.filters.items():
            if field not in data:
                continue
            
            value = data[field]
            
            # Apply filter logic
            if isinstance(filter_config, dict):
                filter_type = filter_config.get('type')
                filter_value = filter_config.get('value')
                
                if filter_type == 'equals':
                    if value != filter_value:
                        return False
                elif filter_type == 'not_equals':
                    if value == filter_value:
                        return False
                elif filter_type == 'contains':
                    if filter_value not in str(value):
                        return False
                elif filter_type == 'not_contains':
                    if filter_value in str(value):
                        return False
                elif filter_type == 'greater_than':
                    if not (isinstance(value, (int, float)) and value > filter_value):
                        return False
                elif filter_type == 'less_than':
                    if not (isinstance(value, (int, float)) and value < filter_value):
                        return False
        
        return True
    
    def _transform_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data using configured rules."""
        transformed_data = data.copy()
        
        # Apply transformation rules
        for rule in self.config.transformation_rules:
            result = self.transformer.transform(transformed_data, rule.name)
            if result.success:
                transformed_data = result.data
            else:
                logger.warning(f"Transformation failed: {rule.name} - {result.errors}")
        
        # Apply field mappings
        mapped_data = {}
        for source_field, target_field in self.config.field_mappings.items():
            if source_field in transformed_data:
                mapped_data[target_field] = transformed_data[source_field]
        
        # Add unmapped fields
        for field, value in transformed_data.items():
            if field not in self.config.field_mappings:
                mapped_data[field] = value
        
        return mapped_data
    
    def _detect_conflicts(self, source_data: Dict[str, Any], target_data: Dict[str, Any]) -> List[ConflictRecord]:
        """Detect conflicts between source and target data."""
        conflicts = []
        
        for field, source_value in source_data.items():
            if field in target_data:
                target_value = target_data[field]
                
                if source_value != target_value:
                    conflict = ConflictRecord(
                        conflict_id=f"conflict_{timezone.now().timestamp()}_{field}",
                        sync_id="",  # Will be set by caller
                        bridge_name=self.config.name,
                        field_name=field,
                        source_value=source_value,
                        target_value=target_value,
                        source_data=source_data,
                        target_data=target_data
                    )
                    conflicts.append(conflict)
        
        return conflicts
    
    def _perform_sync(self, source_data: Dict[str, Any], target_data: Dict[str, Any]) -> bool:
        """Perform actual data synchronization."""
        try:
            # This would integrate with the actual target system
            # For now, we'll simulate the sync operation
            
            if self.config.sync_direction == SyncDirection.ONE_WAY:
                # Update target with source data
                return self._update_target_system(source_data)
            elif self.config.sync_direction == SyncDirection.TWO_WAY:
                # Bidirectional sync
                return self._bidirectional_sync(source_data, target_data)
            elif self.config.sync_direction == SyncDirection.MASTER_SLAVE:
                # Master to slave sync
                return self._update_target_system(source_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Sync operation failed: {str(e)}")
            return False
    
    def _update_target_system(self, data: Dict[str, Any]) -> bool:
        """Update target system with data."""
        # This would integrate with the actual target system API
        # For now, we'll simulate the update
        return True
    
    def _bidirectional_sync(self, source_data: Dict[str, Any], target_data: Dict[str, Any]) -> bool:
        """Perform bidirectional synchronization."""
        # This would handle complex bidirectional sync logic
        # For now, we'll simulate the operation
        return True
    
    def _merge_data(self, source_value: Any, target_value: Any) -> Any:
        """Merge conflicting data values."""
        # Simple merge strategy - prefer source for new data, combine for lists
        if isinstance(source_value, list) and isinstance(target_value, list):
            return list(set(source_value + target_value))
        elif isinstance(source_value, dict) and isinstance(target_value, dict):
            merged = target_value.copy()
            merged.update(source_value)
            return merged
        else:
            return source_value
    
    def _apply_conflict_resolution(self, conflict: ConflictRecord):
        """Apply conflict resolution to target system."""
        # This would integrate with the actual target system
        # For now, we'll simulate the resolution
        pass
    
    def _update_sync_statistics(self, sync_time: float):
        """Update sync statistics."""
        with self._lock:
            self.statistics['total_syncs'] += 1
            self.statistics['last_sync_time'] = timezone.now()
            
            # Update average sync time
            total_syncs = self.statistics['total_syncs']
            if total_syncs == 1:
                self.statistics['average_sync_time'] = sync_time
            else:
                current_avg = self.statistics['average_sync_time']
                self.statistics['average_sync_time'] = (
                    (current_avg * (total_syncs - 1) + sync_time) / total_syncs
                )
    
    def _publish_sync_event(self, sync_record: SyncRecord):
        """Publish sync event to event bus."""
        try:
            import asyncio
            
            event_data = {
                'bridge_name': sync_record.bridge_name,
                'sync_id': sync_record.sync_id,
                'source_system': sync_record.source_system,
                'target_system': sync_record.target_system,
                'status': sync_record.status.value,
                'created_at': sync_record.created_at.isoformat(),
                'started_at': sync_record.started_at.isoformat() if sync_record.started_at else None,
                'completed_at': sync_record.completed_at.isoformat() if sync_record.completed_at else None,
                'retry_count': sync_record.retry_count
            }
            
            if sync_record.error_message:
                event_data['error_message'] = sync_record.error_message
            
            # Publish to event bus
            asyncio.create_task(event_bus.publish(
                Event(f"data_bridge.sync.{sync_record.status.value}", event_data)
            ))
            
        except Exception as e:
            logger.error(f"Failed to publish sync event: {str(e)}")
    
    def _publish_conflict_event(self, conflict: ConflictRecord):
        """Publish conflict event to event bus."""
        try:
            import asyncio
            
            event_data = {
                'bridge_name': conflict.bridge_name,
                'conflict_id': conflict.conflict_id,
                'field_name': conflict.field_name,
                'resolution': conflict.resolution.value if conflict.resolution else None,
                'created_at': conflict.created_at.isoformat(),
                'resolved_at': conflict.resolved_at.isoformat() if conflict.resolved_at else None,
                'resolved_by': conflict.resolved_by
            }
            
            # Publish to event bus
            asyncio.create_task(event_bus.publish(
                Event("data_bridge.conflict.resolved", event_data)
            ))
            
        except Exception as e:
            logger.error(f"Failed to publish conflict event: {str(e)}")
    
    def sync_data(self, source_data: Dict[str, Any], target_data: Dict[str, Any] = None) -> str:
        """Queue data for synchronization."""
        sync_record = SyncRecord(
            sync_id=f"sync_{self.config.name}_{timezone.now().timestamp()}",
            bridge_name=self.config.name,
            source_system=self.config.source_system,
            target_system=self.config.target_system,
            source_data=source_data,
            target_data=target_data or {}
        )
        
        self.sync_queue.put(sync_record)
        return sync_record.sync_id
    
    def get_sync_status(self, sync_id: str) -> Optional[SyncRecord]:
        """Get sync record status."""
        # This would typically query a database
        # For now, we'll return None
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get data bridge statistics."""
        with self._lock:
            stats = self.statistics.copy()
            stats.update({
                'queue_size': self.sync_queue.qsize(),
                'conflict_queue_size': self.conflict_queue.qsize(),
                'running': self._running,
                'config': {
                    'name': self.config.name,
                    'source_system': self.config.source_system,
                    'target_system': self.config.target_system,
                    'sync_direction': self.config.sync_direction.value,
                    'conflict_resolution': self.config.conflict_resolution.value,
                    'is_active': self.config.is_active
                }
            })
            return stats
    
    def shutdown(self):
        """Shutdown data bridge."""
        logger.info(f"Shutting down data bridge: {self.config.name}")
        
        self._running = False
        
        # Wait for threads to finish
        if self._sync_thread:
            self._sync_thread.join(timeout=5)
        
        if self._conflict_thread:
            self._conflict_thread.join(timeout=5)
        
        # Shutdown circuit breaker
        self.circuit_breaker.shutdown()
        
        logger.info(f"Data bridge shutdown complete: {self.config.name}")


class DataBridgeManager:
    """Manager for multiple data bridges."""
    
    def __init__(self):
        self.bridges: Dict[str, DataBridge] = {}
        self.bridge_configs: Dict[str, DataBridgeConfig] = {}
        self._lock = threading.RLock()
    
    def create_bridge(self, config: DataBridgeConfig) -> DataBridge:
        """Create a new data bridge."""
        with self._lock:
            if config.name in self.bridges:
                logger.warning(f"Data bridge already exists: {config.name}")
                return self.bridges[config.name]
            
            bridge = DataBridge(config)
            self.bridges[config.name] = bridge
            self.bridge_configs[config.name] = config
            
            logger.info(f"Created data bridge: {config.name}")
            return bridge
    
    def get_bridge(self, name: str) -> Optional[DataBridge]:
        """Get bridge by name."""
        return self.bridges.get(name)
    
    def remove_bridge(self, name: str) -> bool:
        """Remove bridge."""
        with self._lock:
            if name in self.bridges:
                bridge = self.bridges[name]
                bridge.shutdown()
                del self.bridges[name]
                del self.bridge_configs[name]
                logger.info(f"Removed data bridge: {name}")
                return True
            return False
    
    def get_all_bridges(self) -> Dict[str, DataBridge]:
        """Get all bridges."""
        return self.bridges.copy()
    
    def get_active_bridges(self) -> Dict[str, DataBridge]:
        """Get active bridges."""
        return {
            name: bridge for name, bridge in self.bridges.items()
            if bridge.config.is_active
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics for all bridges."""
        stats = {
            'total_bridges': len(self.bridges),
            'active_bridges': len(self.get_active_bridges()),
            'total_syncs': 0,
            'successful_syncs': 0,
            'failed_syncs': 0,
            'conflicts_detected': 0,
            'conflicts_resolved': 0,
            'bridges': {}
        }
        
        for name, bridge in self.bridges.items():
            bridge_stats = bridge.get_statistics()
            stats['bridges'][name] = bridge_stats
            stats['total_syncs'] += bridge_stats['total_syncs']
            stats['successful_syncs'] += bridge_stats['successful_syncs']
            stats['failed_syncs'] += bridge_stats['failed_syncs']
            stats['conflicts_detected'] += bridge_stats['conflicts_detected']
            stats['conflicts_resolved'] += bridge_stats['conflicts_resolved']
        
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all bridges."""
        health_status = {
            'total_bridges': len(self.bridges),
            'healthy_bridges': 0,
            'unhealthy_bridges': 0,
            'bridges': {}
        }
        
        for name, bridge in self.bridges.items():
            bridge_stats = bridge.get_statistics()
            
            # Determine health based on error rate and queue size
            error_rate = bridge_stats['failed_syncs'] / max(1, bridge_stats['total_syncs'])
            queue_size = bridge_stats['queue_size']
            
            is_healthy = (
                error_rate < 0.1 and  # Less than 10% error rate
                queue_size < 500 and   # Queue not too full
                bridge_stats['running']
            )
            
            if is_healthy:
                health_status['healthy_bridges'] += 1
            else:
                health_status['unhealthy_bridges'] += 1
            
            health_status['bridges'][name] = {
                'running': bridge_stats['running'],
                'healthy': is_healthy,
                'error_rate': error_rate,
                'queue_size': queue_size,
                'total_syncs': bridge_stats['total_syncs'],
                'successful_syncs': bridge_stats['successful_syncs'],
                'failed_syncs': bridge_stats['failed_syncs']
            }
        
        return health_status
    
    def shutdown(self):
        """Shutdown all bridges."""
        for bridge in self.bridges.values():
            bridge.shutdown()
        
        self.bridges.clear()
        self.bridge_configs.clear()
        logger.info("Shutdown all data bridges")


# Global data bridge manager
data_bridge_manager = DataBridgeManager()


# Convenience functions
def create_one_way_bridge(name: str, source_system: str, target_system: str,
                        conflict_resolution: ConflictResolution = ConflictResolution.SOURCE_WINS,
                        **config) -> DataBridge:
    """Create one-way data bridge."""
    bridge_config = DataBridgeConfig(
        name=name,
        source_system=source_system,
        target_system=target_system,
        sync_direction=SyncDirection.ONE_WAY,
        conflict_resolution=conflict_resolution,
        **config
    )
    
    return data_bridge_manager.create_bridge(bridge_config)


def create_two_way_bridge(name: str, source_system: str, target_system: str,
                         conflict_resolution: ConflictResolution = ConflictResolution.LATEST_WINS,
                         **config) -> DataBridge:
    """Create two-way data bridge."""
    bridge_config = DataBridgeConfig(
        name=name,
        source_system=source_system,
        target_system=target_system,
        sync_direction=SyncDirection.TWO_WAY,
        conflict_resolution=conflict_resolution,
        **config
    )
    
    return data_bridge_manager.create_bridge(bridge_config)


def create_master_slave_bridge(name: str, master_system: str, slave_system: str,
                              **config) -> DataBridge:
    """Create master-slave data bridge."""
    bridge_config = DataBridgeConfig(
        name=name,
        source_system=master_system,
        target_system=slave_system,
        sync_direction=SyncDirection.MASTER_SLAVE,
        conflict_resolution=ConflictResolution.SOURCE_WINS,
        **config
    )
    
    return data_bridge_manager.create_bridge(bridge_config)
