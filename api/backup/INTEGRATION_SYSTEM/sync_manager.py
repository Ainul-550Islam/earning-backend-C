"""
Sync Manager
Comprehensive synchronization management for integration system
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict

from .integ_exceptions import IntegrationException, SyncManagerException

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Synchronization status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    RETRYING = "retrying"


class SyncDirection(Enum):
    """Synchronization direction"""
    UNIDIRECTIONAL = "unidirectional"
    BIDIRECTIONAL = "bidirectional"
    MULTIDIRECTIONAL = "multidirectional"


class SyncMode(Enum):
    """Synchronization mode"""
    FULL = "full"
    INCREMENTAL = "incremental"
    DELTA = "delta"
    REAL_TIME = "real_time"
    SCHEDULED = "scheduled"
    MANUAL = "manual"


class ConflictResolution(Enum):
    """Conflict resolution strategies"""
    SOURCE_WINS = "source_wins"
    TARGET_WINS = "target_wins"
    LATEST_WINS = "latest_wins"
    MANUAL = "manual"
    MERGE = "merge"
    TIMESTAMP = "timestamp"


@dataclass
class SyncConfiguration:
    """Synchronization configuration"""
    sync_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    source_system: str = ""
    target_system: str = ""
    direction: SyncDirection = SyncDirection.UNIDIRECTIONAL
    mode: SyncMode = SyncMode.INCREMENTAL
    conflict_resolution: ConflictResolution = ConflictResolution.SOURCE_WINS
    enabled: bool = True
    schedule: Optional[str] = None  # Cron expression
    batch_size: int = 100
    max_retries: int = 3
    retry_delay: int = 60
    timeout: int = 300
    filters: Dict[str, Any] = field(default_factory=dict)
    transformations: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SyncSession:
    """Synchronization session"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sync_id: str = ""
    status: SyncStatus = SyncStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    items_processed: int = 0
    items_total: int = 0
    items_failed: int = 0
    items_skipped: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    progress_percentage: float = 0.0
    last_checkpoint: Optional[datetime] = None
    checkpoint_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'session_id': self.session_id,
            'sync_id': self.sync_id,
            'status': self.status.value,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'items_processed': self.items_processed,
            'items_total': self.items_total,
            'items_failed': self.items_failed,
            'items_skipped': self.items_skipped,
            'errors': self.errors,
            'warnings': self.warnings,
            'progress_percentage': self.progress_percentage,
            'last_checkpoint': self.last_checkpoint.isoformat() if self.last_checkpoint else None,
            'checkpoint_data': self.checkpoint_data,
            'metadata': self.metadata
        }


@dataclass
class SyncConflict:
    """Synchronization conflict"""
    conflict_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    item_id: str = ""
    field_name: str = ""
    source_value: Any = None
    target_value: Any = None
    conflict_type: str = ""
    resolution: Optional[str] = None
    resolved_value: Any = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncCheckpoint:
    """Synchronization checkpoint"""
    checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    items_processed: int = 0
    position: Dict[str, Any] = field(default_factory=dict)
    state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseSyncProvider(ABC):
    """Abstract base class for sync providers"""
    
    @abstractmethod
    async def get_items(self, config: SyncConfiguration, 
                       checkpoint: Optional[SyncCheckpoint] = None) -> List[Dict[str, Any]]:
        """Get items to synchronize"""
        pass
    
    @abstractmethod
    async def put_items(self, config: SyncConfiguration, 
                       items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Put synchronized items"""
        pass
    
    @abstractmethod
    async def compare_items(self, source_item: Dict[str, Any], 
                          target_item: Dict[str, Any]) -> List[SyncConflict]:
        """Compare items for conflicts"""
        pass
    
    @abstractmethod
    def can_handle(self, system: str) -> bool:
        """Check if provider can handle system"""
        pass


class DatabaseSyncProvider(BaseSyncProvider):
    """Database synchronization provider"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
    
    def can_handle(self, system: str) -> bool:
        return system.startswith('database:')
    
    async def get_items(self, config: SyncConfiguration, 
                       checkpoint: Optional[SyncCheckpoint] = None) -> List[Dict[str, Any]]:
        """Get items from database"""
        # Mock implementation - would use actual database connection
        return [
            {'id': 1, 'name': 'Item 1', 'value': 'data1'},
            {'id': 2, 'name': 'Item 2', 'value': 'data2'},
        ]
    
    async def put_items(self, config: SyncConfiguration, 
                       items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Put items to database"""
        # Mock implementation - would use actual database operations
        return items
    
    async def compare_items(self, source_item: Dict[str, Any], 
                          target_item: Dict[str, Any]) -> List[SyncConflict]:
        """Compare database items"""
        conflicts = []
        
        for field in source_item:
            if field in target_item and source_item[field] != target_item[field]:
                conflict = SyncConflict(
                    field_name=field,
                    source_value=source_item[field],
                    target_value=target_item[field],
                    conflict_type='value_mismatch'
                )
                conflicts.append(conflict)
        
        return conflicts


class FileSystemSyncProvider(BaseSyncProvider):
    """File system synchronization provider"""
    
    def can_handle(self, system: str) -> bool:
        return system.startswith('filesystem:')
    
    async def get_items(self, config: SyncConfiguration, 
                       checkpoint: Optional[SyncCheckpoint] = None) -> List[Dict[str, Any]]:
        """Get items from file system"""
        # Mock implementation - would use actual file operations
        return [
            {'path': '/file1.txt', 'content': 'content1', 'modified': '2023-01-01'},
            {'path': '/file2.txt', 'content': 'content2', 'modified': '2023-01-02'},
        ]
    
    async def put_items(self, config: SyncConfiguration, 
                       items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Put items to file system"""
        # Mock implementation - would use actual file operations
        return items
    
    async def compare_items(self, source_item: Dict[str, Any], 
                          target_item: Dict[str, Any]) -> List[SyncConflict]:
        """Compare file system items"""
        conflicts = []
        
        # Compare modification times
        if 'modified' in source_item and 'modified' in target_item:
            if source_item['modified'] != target_item['modified']:
                conflict = SyncConflict(
                    field_name='modified',
                    source_value=source_item['modified'],
                    target_value=target_item['modified'],
                    conflict_type='timestamp_mismatch'
                )
                conflicts.append(conflict)
        
        return conflicts


class SyncManager:
    """
    Comprehensive synchronization manager for integration system
    """
    
    def __init__(self):
        self.sync_configs: Dict[str, SyncConfiguration] = {}
        self.sync_sessions: Dict[str, SyncSession] = {}
        self.sync_providers: Dict[str, BaseSyncProvider] = {}
        self.active_sessions: Dict[str, SyncSession] = {}
        self.is_running = False
        self._scheduler_task = None
        
        # Initialize default providers
        self._initialize_providers()
        
        # Statistics
        self.stats = {
            'total_syncs': 0,
            'successful_syncs': 0,
            'failed_syncs': 0,
            'total_items_synced': 0,
            'total_conflicts': 0,
            'average_sync_time': 0.0
        }
    
    def _initialize_providers(self):
        """Initialize default sync providers"""
        self.sync_providers['database'] = DatabaseSyncProvider('mock_connection')
        self.sync_providers['filesystem'] = FileSystemSyncProvider()
    
    def add_sync_configuration(self, config: SyncConfiguration):
        """Add a sync configuration"""
        self.sync_configs[config.sync_id] = config
    
    def remove_sync_configuration(self, sync_id: str):
        """Remove a sync configuration"""
        self.sync_configs.pop(sync_id, None)
    
    def add_provider(self, name: str, provider: BaseSyncProvider):
        """Add a sync provider"""
        self.sync_providers[name] = provider
    
    async def start_scheduler(self):
        """Start the sync scheduler"""
        if self.is_running:
            return
        
        try:
            self.is_running = True
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())
            logger.info("Sync scheduler started")
            
        except Exception as e:
            self.is_running = False
            logger.error(f"Failed to start sync scheduler: {e}")
            raise SyncManagerException(f"Failed to start scheduler: {e}")
    
    async def stop_scheduler(self):
        """Stop the sync scheduler"""
        if not self.is_running:
            return
        
        try:
            self.is_running = False
            
            if self._scheduler_task:
                self._scheduler_task.cancel()
                try:
                    await self._scheduler_task
                except asyncio.CancelledError:
                    pass
            
            # Cancel active sessions
            for session in self.active_sessions.values():
                session.status = SyncStatus.CANCELLED
            
            self.active_sessions.clear()
            logger.info("Sync scheduler stopped")
            
        except Exception as e:
            logger.error(f"Error stopping sync scheduler: {e}")
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.is_running:
            try:
                # Check for scheduled syncs
                for config in self.sync_configs.values():
                    if config.enabled and config.schedule:
                        if self._should_run_sync(config):
                            await self.start_sync(config.sync_id)
                
                # Wait for next check (every minute)
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sync scheduler loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    def _should_run_sync(self, config: SyncConfiguration) -> bool:
        """Check if sync should run based on schedule"""
        # Mock implementation - would parse cron expression
        # For now, run if no recent sessions exist
        recent_sessions = [
            s for s in self.sync_sessions.values()
            if s.sync_id == config.sync_id and 
            s.started_at and 
            s.started_at > datetime.utcnow() - timedelta(hours=1)
        ]
        
        return len(recent_sessions) == 0
    
    async def start_sync(self, sync_id: str, manual: bool = False) -> SyncSession:
        """Start a synchronization session"""
        config = self.sync_configs.get(sync_id)
        if not config:
            raise SyncManagerException(f"Sync configuration not found: {sync_id}")
        
        # Create session
        session = SyncSession(
            sync_id=sync_id,
            status=SyncStatus.PENDING,
            started_at=datetime.utcnow()
        )
        
        self.sync_sessions[session.session_id] = session
        self.active_sessions[session.session_id] = session
        
        # Start sync task
        task = asyncio.create_task(self._run_sync(session, config))
        
        return session
    
    async def _run_sync(self, session: SyncSession, config: SyncConfiguration):
        """Run synchronization session"""
        try:
            session.status = SyncStatus.RUNNING
            
            # Get providers
            source_provider = self._get_provider(config.source_system)
            target_provider = self._get_provider(config.target_system)
            
            if not source_provider or not target_provider:
                raise SyncManagerException("Providers not found for systems")
            
            # Get items from source
            source_items = await source_provider.get_items(config)
            session.items_total = len(source_items)
            
            # Process items in batches
            for i in range(0, len(source_items), config.batch_size):
                batch = source_items[i:i + config.batch_size]
                
                # Process batch
                await self._process_batch(session, config, batch, source_provider, target_provider)
                
                # Update progress
                session.progress_percentage = (i + len(batch)) / len(source_items) * 100
                
                # Create checkpoint
                if i % (config.batch_size * 10) == 0:
                    await self._create_checkpoint(session, i)
            
            # Complete session
            session.status = SyncStatus.COMPLETED
            session.completed_at = datetime.utcnow()
            session.duration_seconds = (session.completed_at - session.started_at).total_seconds()
            
            # Update statistics
            self._update_stats(session, True)
            
        except Exception as e:
            session.status = SyncStatus.FAILED
            session.completed_at = datetime.utcnow()
            session.duration_seconds = (session.completed_at - session.started_at).total_seconds() if session.started_at else 0
            session.errors.append({
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Update statistics
            self._update_stats(session, False)
            
            logger.error(f"Sync session failed: {e}")
        
        finally:
            # Remove from active sessions
            self.active_sessions.pop(session.session_id, None)
    
    async def _process_batch(self, session: SyncSession, config: SyncConfiguration,
                           batch: List[Dict[str, Any]], source_provider: BaseSyncProvider,
                           target_provider: BaseSyncProvider):
        """Process a batch of items"""
        for item in batch:
            try:
                # Check for conflicts if bidirectional
                if config.direction == SyncDirection.BIDIRECTIONAL:
                    target_items = await target_provider.get_items(config)
                    target_item = next((t for t in target_items if t.get('id') == item.get('id')), None)
                    
                    if target_item:
                        conflicts = await source_provider.compare_items(item, target_item)
                        if conflicts:
                            await self._handle_conflicts(session, config, conflicts)
                
                # Apply transformations
                transformed_item = await self._apply_transformations(item, config.transformations)
                
                # Put item to target
                await target_provider.put_items(config, [transformed_item])
                
                session.items_processed += 1
                
            except Exception as e:
                session.items_failed += 1
                session.errors.append({
                    'item_id': item.get('id'),
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                })
    
    async def _handle_conflicts(self, session: SyncSession, config: SyncConfiguration,
                              conflicts: List[SyncConflict]):
        """Handle synchronization conflicts"""
        for conflict in conflicts:
            conflict.session_id = session.session_id
            
            # Apply conflict resolution strategy
            if config.conflict_resolution == ConflictResolution.SOURCE_WINS:
                conflict.resolution = 'source_wins'
                conflict.resolved_value = conflict.source_value
            elif config.conflict_resolution == ConflictResolution.TARGET_WINS:
                conflict.resolution = 'target_wins'
                conflict.resolved_value = conflict.target_value
            elif config.conflict_resolution == ConflictResolution.LATEST_WINS:
                # Would compare timestamps
                conflict.resolution = 'latest_wins'
                conflict.resolved_value = conflict.source_value
            else:
                # Manual or other strategies
                conflict.resolution = 'manual'
            
            conflict.resolved_at = datetime.utcnow()
            
            # Update statistics
            self.stats['total_conflicts'] += 1
    
    async def _apply_transformations(self, item: Dict[str, Any], 
                                  transformations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply transformations to item"""
        transformed = item.copy()
        
        for transformation in transformations:
            transform_type = transformation.get('type')
            
            if transform_type == 'field_rename':
                old_name = transformation.get('old_name')
                new_name = transformation.get('new_name')
                if old_name in transformed:
                    transformed[new_name] = transformed.pop(old_name)
            
            elif transform_type == 'field_filter':
                fields = transformation.get('fields', [])
                transformed = {k: v for k, v in transformed.items() if k in fields}
            
            elif transform_type == 'field_map':
                field_map = transformation.get('mapping', {})
                for old_field, new_field in field_map.items():
                    if old_field in transformed:
                        transformed[new_field] = transformed.pop(old_field)
        
        return transformed
    
    async def _create_checkpoint(self, session: SyncSession, position: int):
        """Create synchronization checkpoint"""
        checkpoint = SyncCheckpoint(
            session_id=session.session_id,
            items_processed=position,
            position={'batch_position': position},
            state={'status': session.status.value}
        )
        
        session.last_checkpoint = checkpoint.timestamp
        session.checkpoint_data = checkpoint.__dict__
    
    def _get_provider(self, system: str) -> Optional[BaseSyncProvider]:
        """Get provider for system"""
        for provider in self.sync_providers.values():
            if provider.can_handle(system):
                return provider
        return None
    
    def _update_stats(self, session: SyncSession, success: bool):
        """Update synchronization statistics"""
        self.stats['total_syncs'] += 1
        
        if success:
            self.stats['successful_syncs'] += 1
        else:
            self.stats['failed_syncs'] += 1
        
        self.stats['total_items_synced'] += session.items_processed
        
        # Update average sync time
        if session.duration_seconds > 0:
            current_avg = self.stats['average_sync_time']
            total_syncs = self.stats['total_syncs']
            self.stats['average_sync_time'] = (
                (current_avg * (total_syncs - 1) + session.duration_seconds) / total_syncs
            )
    
    async def cancel_sync(self, session_id: str) -> bool:
        """Cancel a synchronization session"""
        session = self.active_sessions.get(session_id)
        if session:
            session.status = SyncStatus.CANCELLED
            session.completed_at = datetime.utcnow()
            self.active_sessions.pop(session_id, None)
            return True
        return False
    
    async def pause_sync(self, session_id: str) -> bool:
        """Pause a synchronization session"""
        session = self.active_sessions.get(session_id)
        if session and session.status == SyncStatus.RUNNING:
            session.status = SyncStatus.PAUSED
            return True
        return False
    
    async def resume_sync(self, session_id: str) -> bool:
        """Resume a paused synchronization session"""
        session = self.active_sessions.get(session_id)
        if session and session.status == SyncStatus.PAUSED:
            session.status = SyncStatus.RUNNING
            return True
        return False
    
    def get_sync_session(self, session_id: str) -> Optional[SyncSession]:
        """Get synchronization session"""
        return self.sync_sessions.get(session_id)
    
    def get_sync_sessions(self, sync_id: Optional[str] = None, 
                        status: Optional[SyncStatus] = None) -> List[SyncSession]:
        """Get synchronization sessions"""
        sessions = list(self.sync_sessions.values())
        
        if sync_id:
            sessions = [s for s in sessions if s.sync_id == sync_id]
        
        if status:
            sessions = [s for s in sessions if s.status == status]
        
        return sorted(sessions, key=lambda s: s.started_at or datetime.min, reverse=True)
    
    def get_active_sessions(self) -> List[SyncSession]:
        """Get active synchronization sessions"""
        return list(self.active_sessions.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get synchronization statistics"""
        stats = self.stats.copy()
        
        # Calculate success rate
        if stats['total_syncs'] > 0:
            stats['success_rate'] = (stats['successful_syncs'] / stats['total_syncs']) * 100
        else:
            stats['success_rate'] = 0
        
        # Add current counts
        stats['active_sessions'] = len(self.active_sessions)
        stats['total_sessions'] = len(self.sync_sessions)
        stats['configured_syncs'] = len(self.sync_configs)
        
        return stats


# Global sync manager instance
_sync_manager = None


def get_sync_manager() -> SyncManager:
    """Get the global sync manager instance"""
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = SyncManager()
    return _sync_manager


def initialize_sync_manager() -> SyncManager:
    """Initialize the global sync manager"""
    global _sync_manager
    _sync_manager = SyncManager()
    return _sync_manager


# Export main classes and functions
__all__ = [
    'SyncManager',
    'SyncConfiguration',
    'SyncSession',
    'SyncConflict',
    'SyncCheckpoint',
    'BaseSyncProvider',
    'DatabaseSyncProvider',
    'FileSystemSyncProvider',
    'SyncStatus',
    'SyncDirection',
    'SyncMode',
    'ConflictResolution',
    'get_sync_manager',
    'initialize_sync_manager',
]
