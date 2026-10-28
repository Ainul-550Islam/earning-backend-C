"""
🎯 Comprehensive Event Management Module

This module provides comprehensive event management capabilities for the backup system.
It includes event sourcing, event streaming, event aggregation, and event processing
to support complex event-driven architectures and audit trails.

Features:
- Event sourcing with persistence
- Event streaming and real-time processing
- Event aggregation and analytics
- Event replay and reconstruction
- Event filtering and routing
- Event versioning and migration
- Event security and access control
- Event monitoring and metrics
"""

import logging
import json
import time
import threading
from typing import Dict, List, Any, Optional, Union, Callable, TypeVar, Generic
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from django.contrib.auth import get_user_model
import uuid
import hashlib
import pickle
from concurrent.futures import ThreadPoolExecutor
import queue

# Import backup models
from .models import Backup, BackupLog, BackupAlert
from .utils import TimeUtils

logger = logging.getLogger(__name__)

T = TypeVar('T')
User = get_user_model()


class EventType(Enum):
    """Enumeration of event types."""
    BACKUP_CREATED = "backup_created"
    BACKUP_STARTED = "backup_started"
    BACKUP_COMPLETED = "backup_completed"
    BACKUP_FAILED = "backup_failed"
    BACKUP_VERIFIED = "backup_verified"
    BACKUP_RESTORED = "backup_restored"
    BACKUP_DELETED = "backup_deleted"
    BACKUP_ENCRYPTED = "backup_encrypted"
    BACKUP_DECRYPTED = "backup_decrypted"
    BACKUP_COMPRESSED = "backup_compressed"
    BACKUP_UPLOADED = "backup_uploaded"
    BACKUP_DOWNLOADED = "backup_downloaded"
    SCHEDULE_CREATED = "schedule_created"
    SCHEDULE_UPDATED = "schedule_updated"
    SCHEDULE_DELETED = "schedule_deleted"
    SCHEDULE_EXECUTED = "schedule_executed"
    SCHEDULE_FAILED = "schedule_failed"
    ALERT_CREATED = "alert_created"
    ALERT_RESOLVED = "alert_resolved"
    SYSTEM_STARTED = "system_started"
    SYSTEM_SHUTDOWN = "system_shutdown"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    CONFIG_CHANGED = "config_changed"
    SECURITY_EVENT = "security_event"
    PERFORMANCE_EVENT = "performance_event"
    CUSTOM = "custom"


class EventSeverity(Enum):
    """Enumeration of event severities."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventStatus(Enum):
    """Enumeration of event statuses."""
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    IGNORED = "ignored"


@dataclass
class EventMetadata:
    """Event metadata."""
    event_id: str
    event_type: EventType
    severity: EventSeverity = EventSeverity.MEDIUM
    source: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    timestamp: datetime = field(default_factory=timezone.now)
    version: int = 1
    tags: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    timeout: Optional[float] = None


@dataclass
class Event:
    """Base event class."""
    metadata: EventMetadata
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            'metadata': asdict(self.metadata),
            'data': self.data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create event from dictionary."""
        metadata = EventMetadata(**data['metadata'])
        return cls(metadata=metadata, data=data.get('data', {}))
    
    def get_hash(self) -> str:
        """Get event hash for deduplication."""
        event_str = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(event_str.encode()).hexdigest()


@dataclass
class EventSnapshot:
    """Event snapshot for state reconstruction."""
    snapshot_id: str
    aggregate_id: str
    aggregate_type: str
    version: int
    data: Dict[str, Any]
    created_at: datetime = field(default_factory=timezone.now)
    event_ids: List[str] = field(default_factory=list)


class EventStore:
    """Event store for persistence and retrieval."""
    
    def __init__(self):
        self.events: Dict[str, Event] = {}
        self.snapshots: Dict[str, EventSnapshot] = {}
        self.streams: Dict[str, List[str]] = {}  # stream_id -> event_ids
        self.lock = threading.Lock()
        self.max_events = getattr(settings, 'BACKUP_EVENT_MAX_EVENTS', 10000)
        self.enable_persistence = getattr(settings, 'BACKUP_EVENT_PERSISTENCE', True)
    
    def append_event(self, event: Event, stream_id: Optional[str] = None) -> bool:
        """Append event to store."""
        with self.lock:
            # Check for duplicates
            event_hash = event.get_hash()
            if event_hash in self.events:
                return False
            
            # Add to events
            self.events[event.metadata.event_id] = event
            
            # Add to stream
            if stream_id:
                if stream_id not in self.streams:
                    self.streams[stream_id] = []
                self.streams[stream_id].append(event.metadata.event_id)
            
            # Persist if enabled
            if self.enable_persistence:
                self._persist_event(event, stream_id)
            
            # Cleanup old events
            self._cleanup_old_events()
            
            return True
    
    def get_event(self, event_id: str) -> Optional[Event]:
        """Get event by ID."""
        with self.lock:
            return self.events.get(event_id)
    
    def get_stream(self, stream_id: str, from_version: Optional[int] = None,
                  to_version: Optional[int] = None) -> List[Event]:
        """Get events from stream."""
        with self.lock:
            event_ids = self.streams.get(stream_id, [])
            events = []
            
            for event_id in event_ids:
                event = self.events.get(event_id)
                if event:
                    if from_version is not None and event.metadata.version < from_version:
                        continue
                    if to_version is not None and event.metadata.version > to_version:
                        continue
                    events.append(event)
            
            return events
    
    def create_snapshot(self, aggregate_id: str, aggregate_type: str,
                       version: int, data: Dict[str, Any]) -> EventSnapshot:
        """Create event snapshot."""
        snapshot = EventSnapshot(
            snapshot_id=str(uuid.uuid4()),
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            version=version,
            data=data
        )
        
        with self.lock:
            self.snapshots[snapshot.snapshot_id] = snapshot
            
            if self.enable_persistence:
                self._persist_snapshot(snapshot)
        
        return snapshot
    
    def get_latest_snapshot(self, aggregate_id: str) -> Optional[EventSnapshot]:
        """Get latest snapshot for aggregate."""
        with self.lock:
            latest = None
            for snapshot in self.snapshots.values():
                if snapshot.aggregate_id == aggregate_id:
                    if latest is None or snapshot.version > latest.version:
                        latest = snapshot
            return latest
    
    def _persist_event(self, event: Event, stream_id: Optional[str] = None) -> None:
        """Persist event to database."""
        try:
            # Create backup log entry for event
            BackupLog.objects.create(
                action='event_occurred',
                category='system',
                level='info',
                message=f"Event {event.metadata.event_type.value} occurred",
                metadata={
                    'event_id': event.metadata.event_id,
                    'event_type': event.metadata.event_type.value,
                    'severity': event.metadata.severity.value,
                    'stream_id': stream_id,
                    'event_data': event.data
                }
            )
        except Exception as e:
            logger.error(f"Failed to persist event {event.metadata.event_id}: {e}")
    
    def _persist_snapshot(self, snapshot: EventSnapshot) -> None:
        """Persist snapshot to database."""
        try:
            # Create backup log entry for snapshot
            BackupLog.objects.create(
                action='snapshot_created',
                category='system',
                level='info',
                message=f"Snapshot created for {snapshot.aggregate_type} {snapshot.aggregate_id}",
                metadata={
                    'snapshot_id': snapshot.snapshot_id,
                    'aggregate_id': snapshot.aggregate_id,
                    'aggregate_type': snapshot.aggregate_type,
                    'version': snapshot.version,
                    'snapshot_data': snapshot.data
                }
            )
        except Exception as e:
            logger.error(f"Failed to persist snapshot {snapshot.snapshot_id}: {e}")
    
    def _cleanup_old_events(self) -> None:
        """Clean up old events."""
        if len(self.events) > self.max_events:
            # Remove oldest events
            sorted_events = sorted(self.events.items(), 
                                 key=lambda x: x[1].metadata.timestamp)
            events_to_remove = len(self.events) - self.max_events
            
            for i in range(events_to_remove):
                event_id, event = sorted_events[i]
                del self.events[event_id]
                
                # Remove from streams
                for stream_event_ids in self.streams.values():
                    if event_id in stream_event_ids:
                        stream_event_ids.remove(event_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event store statistics."""
        with self.lock:
            return {
                'total_events': len(self.events),
                'total_snapshots': len(self.snapshots),
                'total_streams': len(self.streams),
                'event_types': self._get_event_type_distribution(),
                'severity_distribution': self._get_severity_distribution()
            }
    
    def _get_event_type_distribution(self) -> Dict[str, int]:
        """Get event type distribution."""
        distribution = {}
        for event in self.events.values():
            event_type = event.metadata.event_type.value
            distribution[event_type] = distribution.get(event_type, 0) + 1
        return distribution
    
    def _get_severity_distribution(self) -> Dict[str, int]:
        """Get severity distribution."""
        distribution = {}
        for event in self.events.values():
            severity = event.metadata.severity.value
            distribution[severity] = distribution.get(severity, 0) + 1
        return distribution


class EventProcessor:
    """Event processor for handling event logic."""
    
    def __init__(self):
        self.handlers: Dict[EventType, List[Callable]] = {}
        self.global_handlers: List[Callable] = []
        self.filters: List[Callable] = []
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.processing_stats = {
            'total_processed': 0,
            'total_failed': 0,
            'processing_times': []
        }
    
    def register_handler(self, event_type: EventType, handler: Callable) -> None:
        """Register event handler."""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
        logger.info(f"Registered handler for {event_type.value}")
    
    def register_global_handler(self, handler: Callable) -> None:
        """Register global event handler."""
        self.global_handlers.append(handler)
        logger.info("Registered global event handler")
    
    def register_filter(self, filter_func: Callable) -> None:
        """Register event filter."""
        self.filters.append(filter_func)
        logger.info("Registered event filter")
    
    def process_event(self, event: Event, stream_id: Optional[str] = None) -> bool:
        """Process a single event."""
        start_time = time.time()
        
        try:
            # Apply filters
            for filter_func in self.filters:
                if not filter_func(event):
                    return False
            
            # Get handlers
            handlers = self.handlers.get(event.metadata.event_type, [])
            all_handlers = self.global_handlers + handlers
            
            # Process handlers
            results = []
            for handler in all_handlers:
                try:
                    result = handler(event, stream_id)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Handler failed for event {event.metadata.event_id}: {e}")
                    self.processing_stats['total_failed'] += 1
                    return False
            
            # Update stats
            processing_time = (time.time() - start_time) * 1000
            self.processing_stats['total_processed'] += 1
            self.processing_stats['processing_times'].append(processing_time)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process event {event.metadata.event_id}: {e}")
            self.processing_stats['total_failed'] += 1
            return False
    
    def process_events_async(self, events: List[Event], stream_id: Optional[str] = None) -> List[bool]:
        """Process events asynchronously."""
        futures = []
        
        for event in events:
            future = self.executor.submit(self.process_event, event, stream_id)
            futures.append(future)
        
        results = []
        for future in futures:
            try:
                result = future.result(timeout=30)  # 30 second timeout
                results.append(result)
            except Exception as e:
                logger.error(f"Async event processing failed: {e}")
                results.append(False)
        
        return results
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        stats = self.processing_stats.copy()
        
        if stats['processing_times']:
            stats['avg_processing_time'] = sum(stats['processing_times']) / len(stats['processing_times'])
            stats['min_processing_time'] = min(stats['processing_times'])
            stats['max_processing_time'] = max(stats['processing_times'])
        else:
            stats['avg_processing_time'] = 0
            stats['min_processing_time'] = 0
            stats['max_processing_time'] = 0
        
        return stats


class EventAggregator:
    """Event aggregator for analytics and reporting."""
    
    def __init__(self):
        self.aggregations: Dict[str, Dict[str, Any]] = {}
        self.time_windows = {
            '1m': timedelta(minutes=1),
            '5m': timedelta(minutes=5),
            '15m': timedelta(minutes=15),
            '1h': timedelta(hours=1),
            '1d': timedelta(days=1)
        }
        self.lock = threading.Lock()
    
    def add_event(self, event: Event) -> None:
        """Add event to aggregations."""
        with self.lock:
            event_type = event.metadata.event_type.value
            timestamp = event.metadata.timestamp
            
            for window_name, window_delta in self.time_windows.items():
                window_start = timestamp - (timestamp - timezone.now().replace(second=0, microsecond=0)) % window_delta
                
                key = f"{event_type}:{window_name}:{window_start.isoformat()}"
                
                if key not in self.aggregations:
                    self.aggregations[key] = {
                        'event_type': event_type,
                        'window': window_name,
                        'start_time': window_start,
                        'count': 0,
                        'severity_counts': {s.value: 0 for s in EventSeverity},
                        'latest_timestamp': timestamp
                    }
                
                agg = self.aggregations[key]
                agg['count'] += 1
                agg['severity_counts'][event.metadata.severity.value] += 1
                
                if timestamp > agg['latest_timestamp']:
                    agg['latest_timestamp'] = timestamp
    
    def get_aggregation(self, event_type: str, window: str, 
                       start_time: Optional[datetime] = None,
                       end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get aggregation data."""
        with self.lock:
            results = []
            
            for key, agg in self.aggregations.items():
                if agg['event_type'] != event_type or agg['window'] != window:
                    continue
                
                if start_time and agg['start_time'] < start_time:
                    continue
                
                if end_time and agg['start_time'] > end_time:
                    continue
                
                results.append(agg.copy())
            
            return sorted(results, key=lambda x: x['start_time'])
    
    def get_event_counts(self, hours: int = 24) -> Dict[str, int]:
        """Get event counts for the last N hours."""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        with self.lock:
            counts = {}
            
            for agg in self.aggregations.values():
                if agg['latest_timestamp'] < cutoff_time:
                    continue
                
                event_type = agg['event_type']
                counts[event_type] = counts.get(event_type, 0) + agg['count']
            
            return counts
    
    def get_severity_trends(self, hours: int = 24) -> Dict[str, List[Dict[str, Any]]]:
        """Get severity trends over time."""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        trends = {s.value: [] for s in EventSeverity}
        
        with self.lock:
            for agg in self.aggregations.values():
                if agg['latest_timestamp'] < cutoff_time:
                    continue
                
                trend_data = {
                    'timestamp': agg['start_time'],
                    'count': agg['count'],
                    'severity_counts': agg['severity_counts'].copy()
                }
                
                trends[agg['event_type']].append(trend_data)
        
        return trends


class EventReplayer:
    """Event replayer for state reconstruction."""
    
    def __init__(self, event_store: EventStore):
        self.event_store = event_store
        self.replay_stats = {
            'total_replayed': 0,
            'replay_times': []
        }
    
    def replay_stream(self, stream_id: str, from_version: Optional[int] = None,
                     to_version: Optional[int] = None,
                     target_time: Optional[datetime] = None) -> List[Event]:
        """Replay events from stream."""
        start_time = time.time()
        
        # Get events
        events = self.event_store.get_stream(stream_id, from_version, to_version)
        
        # Filter by time if specified
        if target_time:
            events = [e for e in events if e.metadata.timestamp <= target_time]
        
        # Sort by version
        events.sort(key=lambda e: e.metadata.version)
        
        # Update stats
        replay_time = (time.time() - start_time) * 1000
        self.replay_stats['total_replayed'] += len(events)
        self.replay_stats['replay_times'].append(replay_time)
        
        return events
    
    def replay_to_snapshot(self, aggregate_id: str, target_version: int) -> Optional[EventSnapshot]:
        """Replay events to create snapshot at specific version."""
        # Get events up to target version
        events = []
        for stream_id, event_ids in self.event_store.streams.items():
            stream_events = self.event_store.get_stream(stream_id, to_version=target_version)
            events.extend(stream_events)
        
        # Sort events
        events.sort(key=lambda e: e.metadata.timestamp)
        
        # Apply events to reconstruct state
        state = {}
        for event in events:
            # This would integrate with actual aggregate logic
            state.update(event.data)
        
        # Create snapshot
        snapshot = self.event_store.create_snapshot(
            aggregate_id=aggregate_id,
            aggregate_type='reconstructed',
            version=target_version,
            data=state
        )
        
        return snapshot
    
    def get_replay_stats(self) -> Dict[str, Any]:
        """Get replay statistics."""
        stats = self.replay_stats.copy()
        
        if stats['replay_times']:
            stats['avg_replay_time'] = sum(stats['replay_times']) / len(stats['replay_times'])
            stats['min_replay_time'] = min(stats['replay_times'])
            stats['max_replay_time'] = max(stats['replay_times'])
        else:
            stats['avg_replay_time'] = 0
            stats['min_replay_time'] = 0
            stats['max_replay_time'] = 0
        
        return stats


class EventManager:
    """Main event manager orchestrating all event operations."""
    
    def __init__(self):
        self.event_store = EventStore()
        self.event_processor = EventProcessor()
        self.event_aggregator = EventAggregator()
        self.event_replayer = EventReplayer(self.event_store)
        self.streams: Dict[str, str] = {}  # aggregate_id -> stream_id
        self.lock = threading.Lock()
        
        # Register default handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self) -> None:
        """Register default event handlers."""
        
        def backup_event_handler(event: Event, stream_id: Optional[str] = None) -> None:
            """Handle backup events."""
            if event.metadata.event_type in [EventType.BACKUP_CREATED, EventType.BACKUP_COMPLETED]:
                logger.info(f"Backup event: {event.metadata.event_type.value}")
                # Additional backup event logic
        
        def alert_event_handler(event: Event, stream_id: Optional[str] = None) -> None:
            """Handle alert events."""
            if event.metadata.event_type == EventType.ALERT_CREATED:
                logger.warning(f"Alert created: {event.data.get('message', 'Unknown')}")
                # Additional alert logic
        
        def security_event_handler(event: Event, stream_id: Optional[str] = None) -> None:
            """Handle security events."""
            if event.metadata.event_type == EventType.SECURITY_EVENT:
                logger.error(f"Security event: {event.data.get('description', 'Unknown')}")
                # Additional security logic
        
        # Register handlers
        self.event_processor.register_handler(EventType.BACKUP_CREATED, backup_event_handler)
        self.event_processor.register_handler(EventType.BACKUP_COMPLETED, backup_event_handler)
        self.event_processor.register_handler(EventType.ALERT_CREATED, alert_event_handler)
        self.event_processor.register_handler(EventType.SECURITY_EVENT, security_event_handler)
        
        # Register global handler for aggregation
        self.event_processor.register_global_handler(self.event_aggregator.add_event)
    
    def publish_event(self, event_type: EventType, data: Dict[str, Any],
                     severity: EventSeverity = EventSeverity.MEDIUM,
                     aggregate_id: Optional[str] = None,
                     user_id: Optional[str] = None,
                     context: Optional[Dict[str, Any]] = None) -> str:
        """Publish an event."""
        # Create event
        event_id = str(uuid.uuid4())
        metadata = EventMetadata(
            event_id=event_id,
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            context=context or {}
        )
        
        event = Event(metadata=metadata, data=data)
        
        # Get or create stream
        stream_id = None
        if aggregate_id:
            with self.lock:
                if aggregate_id not in self.streams:
                    self.streams[aggregate_id] = str(uuid.uuid4())
                stream_id = self.streams[aggregate_id]
        
        # Store event
        self.event_store.append_event(event, stream_id)
        
        # Process event
        self.event_processor.process_event(event, stream_id)
        
        logger.info(f"Published event {event_id} ({event_type.value})")
        return event_id
    
    def create_stream(self, aggregate_id: str) -> str:
        """Create event stream for aggregate."""
        stream_id = str(uuid.uuid4())
        
        with self.lock:
            self.streams[aggregate_id] = stream_id
        
        return stream_id
    
    def get_events(self, aggregate_id: Optional[str] = None,
                  event_type: Optional[EventType] = None,
                  from_time: Optional[datetime] = None,
                  to_time: Optional[datetime] = None) -> List[Event]:
        """Get events with filtering."""
        events = []
        
        if aggregate_id:
            # Get events from specific stream
            with self.lock:
                stream_id = self.streams.get(aggregate_id)
                if stream_id:
                    events = self.event_store.get_stream(stream_id)
        else:
            # Get all events
            events = list(self.event_store.events.values())
        
        # Filter by event type
        if event_type:
            events = [e for e in events if e.metadata.event_type == event_type]
        
        # Filter by time range
        if from_time:
            events = [e for e in events if e.metadata.timestamp >= from_time]
        
        if to_time:
            events = [e for e in events if e.metadata.timestamp <= to_time]
        
        # Sort by timestamp
        events.sort(key=lambda e: e.metadata.timestamp)
        
        return events
    
    def get_aggregate_state(self, aggregate_id: str, at_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Get aggregate state at specific time."""
        # Check for snapshot
        snapshot = self.event_store.get_latest_snapshot(aggregate_id)
        
        if snapshot and (not at_time or snapshot.created_at <= at_time):
            return snapshot.data
        
        # Replay events
        with self.lock:
            stream_id = self.streams.get(aggregate_id)
            if stream_id:
                events = self.event_replayer.replay_stream(stream_id, target_time=at_time)
                
                # Reconstruct state
                state = {}
                for event in events:
                    state.update(event.data)
                
                return state
        
        return {}
    
    def create_snapshot(self, aggregate_id: str, version: int, data: Dict[str, Any]) -> EventSnapshot:
        """Create snapshot for aggregate."""
        return self.event_store.create_snapshot(aggregate_id, 'backup', version, data)
    
    def get_analytics(self, hours: int = 24) -> Dict[str, Any]:
        """Get event analytics."""
        return {
            'event_counts': self.event_aggregator.get_event_counts(hours),
            'severity_trends': self.event_aggregator.get_severity_trends(hours),
            'store_stats': self.event_store.get_stats(),
            'processing_stats': self.event_processor.get_processing_stats(),
            'replay_stats': self.event_replayer.get_replay_stats()
        }


# Global event manager instance
_event_manager: Optional[EventManager] = None


def get_event_manager() -> EventManager:
    """Get the global event manager instance."""
    global _event_manager
    if _event_manager is None:
        _event_manager = EventManager()
    return _event_manager


def publish_event(event_type: EventType, data: Dict[str, Any],
                 severity: EventSeverity = EventSeverity.MEDIUM,
                 aggregate_id: Optional[str] = None,
                 user_id: Optional[str] = None,
                 **kwargs) -> str:
    """Publish an event."""
    manager = get_event_manager()
    return manager.publish_event(event_type, data, severity, aggregate_id, user_id, kwargs)


def get_events(aggregate_id: Optional[str] = None,
               event_type: Optional[EventType] = None,
               **kwargs) -> List[Event]:
    """Get events with filtering."""
    manager = get_event_manager()
    return manager.get_events(aggregate_id, event_type, **kwargs)


def get_analytics(hours: int = 24) -> Dict[str, Any]:
    """Get event analytics."""
    manager = get_event_manager()
    return manager.get_analytics(hours)


# Decorators for event handling
def event_handler(event_type: EventType):
    """Decorator for event handlers."""
    def decorator(func):
        manager = get_event_manager()
        manager.event_processor.register_handler(event_type, func)
        return func
    return decorator


def global_event_handler():
    """Decorator for global event handlers."""
    def decorator(func):
        manager = get_event_manager()
        manager.event_processor.register_global_handler(func)
        return func
    return decorator


# Example event handlers
@event_handler(EventType.BACKUP_COMPLETED)
def handle_backup_completed(event: Event, stream_id: Optional[str] = None) -> None:
    """Handle backup completed event."""
    backup_id = event.data.get('backup_id')
    logger.info(f"Backup completed: {backup_id}")
    
    # Create alert if backup size is unusual
    size = event.data.get('size', 0)
    if size > 10 * 1024 * 1024 * 1024:  # 10GB
        publish_event(
            EventType.ALERT_CREATED,
            {'message': f'Large backup created: {backup_id}', 'size': size},
            severity=EventSeverity.MEDIUM,
            aggregate_id=backup_id
        )


@global_event_handler()
def log_all_events(event: Event, stream_id: Optional[str] = None) -> None:
    """Log all events for debugging."""
    logger.debug(f"Event: {event.metadata.event_type.value} - {event.metadata.event_id}")
