# api/rate_limit/data_bridge.py
"""
Data bridge system for rate limit module.

Provides data synchronization and transformation between systems.
"""

import logging
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
import json
import threading
import queue
import time

from api.rate_limit.transformer import TransformerRegistry, transformer_registry
from api.rate_limit.bridge import BridgeManager, bridge_manager
from api.rate_limit.circuit_breaker import CircuitBreakerManager, circuit_breaker_manager

logger = logging.getLogger(__name__)


class DataSyncDirection:
    """Data synchronization direction constants."""
    
    UNIDIRECTIONAL = 'unidirectional'
    BIDIRECTIONAL = 'bidirectional'
    
    CHOICES = [
        (UNIDIRECTIONAL, 'Unidirectional'),
        (BIDIRECTIONAL, 'Bidirectional'),
    ]


class DataSyncMode:
    """Data synchronization mode constants."""
    
    REAL_TIME = 'real_time'
    BATCH = 'batch'
    SCHEDULED = 'scheduled'
    MANUAL = 'manual'
    
    CHOICES = [
        (REAL_TIME, 'Real-time'),
        (BATCH, 'Batch'),
        (SCHEDULED, 'Scheduled'),
        (MANUAL, 'Manual'),
    ]


class DataSyncStatus:
    """Data synchronization status constants."""
    
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    
    CHOICES = [
        (PENDING, 'Pending'),
        (RUNNING, 'Running'),
        (COMPLETED, 'Completed'),
        (FAILED, 'Failed'),
        (CANCELLED, 'Cancelled'),
    ]


class DataSyncTask:
    """Represents a data synchronization task."""
    
    def __init__(self, task_id: str, source_system: str, target_system: str,
                 sync_direction: str, sync_mode: str, data_filter: Dict[str, Any] = None,
                 transformer_chain: List[str] = None, priority: str = 'normal'):
        self.task_id = task_id
        self.source_system = source_system
        self.target_system = target_system
        self.sync_direction = sync_direction
        self.sync_mode = sync_mode
        self.data_filter = data_filter or {}
        self.transformer_chain = transformer_chain or []
        self.priority = priority
        self.status = DataSyncStatus.PENDING
        self.created_at = timezone.now()
        self.started_at = None
        self.completed_at = None
        self.progress = 0
        self.total_records = 0
        self.processed_records = 0
        self.failed_records = 0
        self.error_message = None
        self.result_data = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary."""
        return {
            'task_id': self.task_id,
            'source_system': self.source_system,
            'target_system': self.target_system,
            'sync_direction': self.sync_direction,
            'sync_mode': self.sync_mode,
            'data_filter': self.data_filter,
            'transformer_chain': self.transformer_chain,
            'priority': self.priority,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'progress': self.progress,
            'total_records': self.total_records,
            'processed_records': self.processed_records,
            'failed_records': self.failed_records,
            'error_message': self.error_message,
            'result_data': self.result_data
        }
    
    def update_progress(self, processed: int, total: int = None):
        """Update task progress."""
        self.processed_records = processed
        if total is not None:
            self.total_records = total
        
        if self.total_records > 0:
            self.progress = (self.processed_records / self.total_records) * 100
    
    def mark_started(self):
        """Mark task as started."""
        self.status = DataSyncStatus.RUNNING
        self.started_at = timezone.now()
    
    def mark_completed(self, result_data: Dict[str, Any] = None):
        """Mark task as completed."""
        self.status = DataSyncStatus.COMPLETED
        self.completed_at = timezone.now()
        self.progress = 100
        if result_data:
            self.result_data = result_data
    
    def mark_failed(self, error_message: str):
        """Mark task as failed."""
        self.status = DataSyncStatus.FAILED
        self.completed_at = timezone.now()
        self.error_message = error_message
    
    def mark_cancelled(self):
        """Mark task as cancelled."""
        self.status = DataSyncStatus.CANCELLED
        self.completed_at = timezone.now()


class DataBridge:
    """
    Bridge for data synchronization between systems.
    """
    
    def __init__(self, name: str, source_system: str, target_system: str):
        self.name = name
        self.source_system = source_system
        self.target_system = target_system
        self.is_active = True
        self.sync_direction = DataSyncDirection.UNIDIRECTIONAL
        self.sync_mode = DataSyncMode.BATCH
        self.transformer_chain = []
        self.data_filter = {}
        self.sync_interval = 300  # 5 minutes
        self.batch_size = 100
        self.max_retries = 3
        self.last_sync = None
        self.sync_count = 0
        self.error_count = 0
        self.total_records_synced = 0
    
    def configure(self, sync_direction: str = None, sync_mode: str = None,
                 transformer_chain: List[str] = None, data_filter: Dict[str, Any] = None,
                 sync_interval: int = None, batch_size: int = None,
                 max_retries: int = None):
        """
        Configure data bridge.
        
        Args:
            sync_direction: Sync direction
            sync_mode: Sync mode
            transformer_chain: List of transformer names
            data_filter: Data filter criteria
            sync_interval: Sync interval in seconds
            batch_size: Batch size for processing
            max_retries: Maximum retry attempts
        """
        if sync_direction:
            self.sync_direction = sync_direction
        
        if sync_mode:
            self.sync_mode = sync_mode
        
        if transformer_chain:
            self.transformer_chain = transformer_chain
        
        if data_filter:
            self.data_filter = data_filter
        
        if sync_interval:
            self.sync_interval = sync_interval
        
        if batch_size:
            self.batch_size = batch_size
        
        if max_retries:
            self.max_retries = max_retries
        
        logger.info(f"Configured data bridge: {self.name}")
    
    def extract_data(self, source_system: str, filter_criteria: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Extract data from source system.
        
        Args:
            source_system: Source system name
            filter_criteria: Filter criteria
            
        Returns:
            Extracted data records
        """
        try:
            # This would be implemented based on the specific source system
            # For now, return mock data
            mock_data = [
                {
                    'id': 1,
                    'user_id': 123,
                    'ip_address': '192.168.1.1',
                    'endpoint': '/api/v1/data',
                    'timestamp': timezone.now().isoformat(),
                    'status': 'active'
                },
                {
                    'id': 2,
                    'user_id': 456,
                    'ip_address': '192.168.1.2',
                    'endpoint': '/api/v1/users',
                    'timestamp': timezone.now().isoformat(),
                    'status': 'inactive'
                }
            ]
            
            # Apply filter
            if filter_criteria:
                filtered_data = []
                for record in mock_data:
                    match = True
                    for field, value in filter_criteria.items():
                        if field in record and record[field] != value:
                            match = False
                            break
                    if match:
                        filtered_data.append(record)
                mock_data = filtered_data
            
            logger.info(f"Extracted {len(mock_data)} records from {source_system}")
            return mock_data
            
        except Exception as e:
            logger.error(f"Failed to extract data from {source_system}: {str(e)}")
            raise
    
    def transform_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform data using transformer chain.
        
        Args:
            data: Data to transform
            
        Returns:
            Transformed data
        """
        try:
            transformed_data = data.copy()
            
            for transformer_name in self.transformer_chain:
                transformer = transformer_registry.get_transformer(transformer_name)
                if not transformer:
                    logger.warning(f"Transformer not found: {transformer_name}")
                    continue
                
                # Apply transformer to each record
                for i, record in enumerate(transformed_data):
                    try:
                        transformed_record = transformer.transform(record)
                        transformed_data[i] = transformed_record
                    except Exception as e:
                        logger.error(f"Failed to transform record {i}: {str(e)}")
                        # Keep original record if transformation fails
                        pass
            
            logger.info(f"Transformed {len(transformed_data)} records")
            return transformed_data
            
        except Exception as e:
            logger.error(f"Failed to transform data: {str(e)}")
            raise
    
    def load_data(self, target_system: str, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Load data into target system.
        
        Args:
            target_system: Target system name
            data: Data to load
            
        Returns:
            Load result
        """
        try:
            # This would be implemented based on the specific target system
            # For now, return mock result
            loaded_count = len(data)
            failed_count = 0
            
            logger.info(f"Loaded {loaded_count} records into {target_system}")
            
            return {
                'success': True,
                'loaded_count': loaded_count,
                'failed_count': failed_count,
                'target_system': target_system
            }
            
        except Exception as e:
            logger.error(f"Failed to load data into {target_system}: {str(e)}")
            raise
    
    def sync_data(self, task: DataSyncTask) -> Dict[str, Any]:
        """
        Perform data synchronization.
        
        Args:
            task: Sync task
            
        Returns:
            Sync result
        """
        try:
            task.mark_started()
            
            # Extract data
            source_data = self.extract_data(self.source_system, self.data_filter)
            task.total_records = len(source_data)
            
            # Transform data
            if self.transformer_chain:
                transformed_data = self.transform_data(source_data)
            else:
                transformed_data = source_data
            
            # Load data
            load_result = self.load_data(self.target_system, transformed_data)
            
            if load_result['success']:
                task.update_progress(load_result['loaded_count'], task.total_records)
                task.mark_completed(load_result)
                
                # Update bridge statistics
                self.last_sync = timezone.now()
                self.sync_count += 1
                self.total_records_synced += load_result['loaded_count']
                
                return {
                    'success': True,
                    'task_id': task.task_id,
                    'loaded_count': load_result['loaded_count'],
                    'failed_count': load_result['failed_count']
                }
            else:
                task.mark_failed(f"Load failed: {load_result}")
                self.error_count += 1
                
                return {
                    'success': False,
                    'task_id': task.task_id,
                    'error': load_result
                }
                
        except Exception as e:
            task.mark_failed(str(e))
            self.error_count += 1
            logger.error(f"Data sync failed: {str(e)}")
            
            return {
                'success': False,
                'task_id': task.task_id,
                'error': str(e)
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        return {
            'name': self.name,
            'source_system': self.source_system,
            'target_system': self.target_system,
            'is_active': self.is_active,
            'sync_direction': self.sync_direction,
            'sync_mode': self.sync_mode,
            'sync_count': self.sync_count,
            'error_count': self.error_count,
            'total_records_synced': self.total_records_synced,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'transformer_chain': self.transformer_chain,
            'sync_interval': self.sync_interval,
            'batch_size': self.batch_size
        }


class DataBridgeManager:
    """
    Manager for data bridges and synchronization tasks.
    """
    
    def __init__(self):
        self.bridges: Dict[str, DataBridge] = {}
        self.sync_tasks: Dict[str, DataSyncTask] = {}
        self.task_queue = queue.Queue()
        self.worker_thread = None
        self.is_running = False
        self.max_queue_size = 1000
        self._initialize_default_bridges()
    
    def _initialize_default_bridges(self):
        """Initialize default data bridges."""
        # Rate limit to analytics bridge
        analytics_bridge = DataBridge(
            name='rate_limit_to_analytics',
            source_system='rate_limit',
            target_system='analytics'
        )
        analytics_bridge.configure(
            sync_direction=DataSyncDirection.UNIDIRECTIONAL,
            sync_mode=DataSyncMode.BATCH,
            transformer_chain=['rate_limit_to_analytics'],
            sync_interval=300,
            batch_size=100
        )
        self.register_bridge(analytics_bridge)
        
        # Rate limit to security bridge
        security_bridge = DataBridge(
            name='rate_limit_to_security',
            source_system='rate_limit',
            target_system='security'
        )
        security_bridge.configure(
            sync_direction=DataSyncDirection.UNIDIRECTIONAL,
            sync_mode=DataSyncMode.REAL_TIME,
            transformer_chain=['rate_limit_to_security'],
            sync_interval=60,
            batch_size=50
        )
        self.register_bridge(security_bridge)
        
        # Rate limit to notification bridge
        notification_bridge = DataBridge(
            name='rate_limit_to_notification',
            source_system='rate_limit',
            target_system='notification'
        )
        notification_bridge.configure(
            sync_direction=DataSyncDirection.UNIDIRECTIONAL,
            sync_mode=DataSyncMode.REAL_TIME,
            transformer_chain=['rate_limit_to_notification'],
            sync_interval=120,
            batch_size=25
        )
        self.register_bridge(notification_bridge)
    
    def register_bridge(self, bridge: DataBridge):
        """
        Register a data bridge.
        
        Args:
            bridge: Data bridge instance
        """
        self.bridges[bridge.name] = bridge
        logger.info(f"Registered data bridge: {bridge.name}")
    
    def unregister_bridge(self, name: str):
        """
        Unregister a data bridge.
        
        Args:
            name: Bridge name
        """
        if name in self.bridges:
            del self.bridges[name]
            logger.info(f"Unregistered data bridge: {name}")
    
    def get_bridge(self, name: str) -> Optional[DataBridge]:
        """
        Get a bridge by name.
        
        Args:
            name: Bridge name
            
        Returns:
            Bridge instance or None
        """
        return self.bridges.get(name)
    
    def create_sync_task(self, bridge_name: str, sync_direction: str = None,
                        sync_mode: str = None, data_filter: Dict[str, Any] = None,
                        transformer_chain: List[str] = None, priority: str = 'normal') -> str:
        """
        Create a synchronization task.
        
        Args:
            bridge_name: Bridge name
            sync_direction: Sync direction
            sync_mode: Sync mode
            data_filter: Data filter
            transformer_chain: Transformer chain
            priority: Task priority
            
        Returns:
            Task ID
        """
        bridge = self.get_bridge(bridge_name)
        if not bridge:
            raise ValueError(f"Bridge not found: {bridge_name}")
        
        task_id = f"sync_{bridge_name}_{timezone.now().timestamp()}"
        
        task = DataSyncTask(
            task_id=task_id,
            source_system=bridge.source_system,
            target_system=bridge.target_system,
            sync_direction=sync_direction or bridge.sync_direction,
            sync_mode=sync_mode or bridge.sync_mode,
            data_filter=data_filter or bridge.data_filter,
            transformer_chain=transformer_chain or bridge.transformer_chain,
            priority=priority
        )
        
        self.sync_tasks[task_id] = task
        
        # Add to queue
        try:
            self.task_queue.put(task, timeout=1)
        except queue.Full:
            logger.error(f"Task queue is full, dropping task: {task_id}")
        
        return task_id
    
    def start_worker(self):
        """Start the worker thread."""
        if self.is_running:
            logger.warning("Data bridge worker is already running")
            return
        
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        logger.info("Data bridge worker started")
    
    def stop_worker(self):
        """Stop the worker thread."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        
        logger.info("Data bridge worker stopped")
    
    def _worker_loop(self):
        """Main worker loop for processing sync tasks."""
        while self.is_running:
            try:
                # Get task from queue
                task = self.task_queue.get(timeout=1)
                
                # Process task
                self._process_task(task)
                
                # Mark task done
                self.task_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in data bridge worker: {str(e)}")
    
    def _process_task(self, task: DataSyncTask):
        """Process a sync task."""
        try:
            # Find appropriate bridge
            bridge = None
            for bridge_instance in self.bridges.values():
                if (bridge_instance.source_system == task.source_system and
                    bridge_instance.target_system == task.target_system):
                    bridge = bridge_instance
                    break
            
            if not bridge:
                task.mark_failed(f"No bridge found for {task.source_system} -> {task.target_system}")
                return
            
            # Use circuit breaker for protection
            breaker_name = f"data_bridge_{bridge.name}"
            
            def sync_operation():
                return bridge.sync_data(task)
            
            result = circuit_breaker_manager.call_with_breaker(breaker_name, sync_operation)
            
            logger.info(f"Completed sync task: {task.task_id}")
            
        except Exception as e:
            task.mark_failed(str(e))
            logger.error(f"Failed to process sync task {task.task_id}: {str(e)}")
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task status.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task status or None
        """
        task = self.sync_tasks.get(task_id)
        return task.to_dict() if task else None
    
    def get_all_tasks(self, status: str = None) -> List[Dict[str, Any]]:
        """
        Get all tasks.
        
        Args:
            status: Filter by status
            
        Returns:
            List of task data
        """
        tasks = []
        
        for task in self.sync_tasks.values():
            if status is None or task.status == status:
                tasks.append(task.to_dict())
        
        # Sort by created time (most recent first)
        tasks.sort(key=lambda t: t['created_at'], reverse=True)
        
        return tasks
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task.
        
        Args:
            task_id: Task ID
            
        Returns:
            True if cancelled
        """
        task = self.sync_tasks.get(task_id)
        if task and task.status == DataSyncStatus.PENDING:
            task.mark_cancelled()
            logger.info(f"Cancelled task: {task_id}")
            return True
        
        return False
    
    def retry_failed_tasks(self) -> Dict[str, Any]:
        """
        Retry failed tasks.
        
        Returns:
            Retry results
        """
        retry_count = 0
        success_count = 0
        
        for task in self.sync_tasks.values():
            if task.status == DataSyncStatus.FAILED:
                # Reset task for retry
                task.status = DataSyncStatus.PENDING
                task.started_at = None
                task.completed_at = None
                task.error_message = None
                task.progress = 0
                
                # Add back to queue
                try:
                    self.task_queue.put(task, timeout=1)
                    retry_count += 1
                except queue.Full:
                    logger.error(f"Task queue is full, cannot retry task: {task.task_id}")
        
        return {
            'retry_count': retry_count,
            'success_count': success_count
        }
    
    def get_bridge_statistics(self) -> Dict[str, Any]:
        """Get statistics for all bridges."""
        stats = {}
        
        for name, bridge in self.bridges.items():
            stats[name] = bridge.get_statistics()
        
        return stats
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get task queue status."""
        task_stats = {
            'pending': 0,
            'running': 0,
            'completed': 0,
            'failed': 0,
            'cancelled': 0
        }
        
        for task in self.sync_tasks.values():
            task_stats[task.status] = task_stats.get(task.status, 0) + 1
        
        return {
            'is_running': self.is_running,
            'queue_size': self.task_queue.qsize(),
            'max_queue_size': self.max_queue_size,
            'total_tasks': len(self.sync_tasks),
            'task_status_counts': task_stats
        }
    
    def cleanup_old_tasks(self, days: int = 7) -> Dict[str, Any]:
        """
        Clean up old completed tasks.
        
        Args:
            days: Age threshold in days
            
        Returns:
            Cleanup results
        """
        cutoff_time = timezone.now() - timedelta(days=days)
        removed_count = 0
        
        tasks_to_remove = []
        
        for task_id, task in self.sync_tasks.items():
            if (task.status in [DataSyncStatus.COMPLETED, DataSyncStatus.FAILED, DataSyncStatus.CANCELLED] and
                task.completed_at and task.completed_at < cutoff_time):
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.sync_tasks[task_id]
            removed_count += 1
        
        logger.info(f"Cleaned up {removed_count} old tasks")
        
        return {
            'removed_count': removed_count,
            'cutoff_days': days
        }


# Global data bridge manager instance
data_bridge_manager = DataBridgeManager()

# Start worker thread
data_bridge_manager.start_worker()


# Export classes and functions
__all__ = [
    'DataSyncDirection',
    'DataSyncMode',
    'DataSyncStatus',
    'DataSyncTask',
    'DataBridge',
    'DataBridgeManager',
    'data_bridge_manager'
]
