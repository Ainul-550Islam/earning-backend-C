import threading
import time
from typing import Any, Optional, Dict, List, Callable, Union
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class WriteThroughCache:
    """
    Write-Through Cache implementation
    Writes to cache and backing store simultaneously
    """
    
    def __init__(
        self,
        cache_service: Any,
        backing_store: Any,
        write_async: bool = False,
        max_queue_size: int = 1000,
        batch_size: int = 100,
        batch_interval: float = 1.0
    ):
        """
        Args:
            cache_service: Primary cache service (Redis, Memcached, etc.)
            backing_store: Backing store (database, file, etc.)
            write_async: Whether to write to backing store asynchronously
            max_queue_size: Maximum size of async write queue
            batch_size: Batch size for async writes
            batch_interval: Interval for batch processing in seconds
        """
        self.cache = cache_service
        self.backing_store = backing_store
        self.write_async = write_async
        
        # Async write queue
        self._write_queue = []
        self._queue_lock = threading.RLock()
        self._max_queue_size = max_queue_size
        
        # Batch processing
        self._batch_size = batch_size
        self._batch_interval = batch_interval
        self._batch_thread = None
        self._running = False
        
        # Statistics
        self._cache_hits = 0
        self._cache_misses = 0
        self._write_hits = 0
        self._write_misses = 0
        self._async_writes = 0
        self._sync_writes = 0
        
        # Start batch processor if async
        if self.write_async:
            self.start_batch_processor()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache, fall back to backing store"""
        # Try cache first
        value = self.cache.get(key)
        if value is not None:
            self._cache_hits += 1
            return value
        
        # Cache miss - try backing store
        self._cache_misses += 1
        value = self._read_from_backing_store(key)
        
        if value is not None:
            # Write to cache for future reads
            self.cache.set(key, value)
            self._write_hits += 1
        else:
            self._write_misses += 1
        
        return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Write to cache and backing store"""
        # Always write to cache
        cache_success = self.cache.set(key, value, ttl)
        
        if not cache_success:
            logger.error(f"Failed to write to cache: {key}")
            return False
        
        # Write to backing store
        if self.write_async:
            # Queue for async write
            success = self._queue_write(key, value)
            if success:
                self._async_writes += 1
        else:
            # Sync write
            success = self._write_to_backing_store(key, value)
            if success:
                self._sync_writes += 1
        
        return success
    
    def delete(self, key: str) -> bool:
        """Delete from cache and backing store"""
        # Delete from cache
        cache_success = self.cache.delete(key)
        
        # Delete from backing store
        if self.write_async:
            # Queue delete
            self._queue_delete(key)
        else:
            self._delete_from_backing_store(key)
        
        return cache_success
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache or backing store"""
        # Check cache first
        if self.cache.exists(key):
            return True
        
        # Check backing store
        return self._exists_in_backing_store(key)
    
    def _read_from_backing_store(self, key: str) -> Optional[Any]:
        """Read from backing store (to be implemented)"""
        # This should be implemented based on backing store type
        # Example for database:
        # return self.backing_store.get(key)
        return None
    
    def _write_to_backing_store(self, key: str, value: Any) -> bool:
        """Write to backing store (to be implemented)"""
        # This should be implemented based on backing store type
        # Example for database:
        # return self.backing_store.set(key, value)
        return True
    
    def _delete_from_backing_store(self, key: str) -> bool:
        """Delete from backing store (to be implemented)"""
        # This should be implemented based on backing store type
        # Example for database:
        # return self.backing_store.delete(key)
        return True
    
    def _exists_in_backing_store(self, key: str) -> bool:
        """Check if key exists in backing store (to be implemented)"""
        # This should be implemented based on backing store type
        # Example for database:
        # return self.backing_store.exists(key)
        return False
    
    def _queue_write(self, key: str, value: Any) -> bool:
        """Queue write operation for async processing"""
        with self._queue_lock:
            if len(self._write_queue) >= self._max_queue_size:
                logger.warning(f"Write queue full, dropping write for {key}")
                return False
            
            self._write_queue.append(('write', key, value, time.time()))
            return True
    
    def _queue_delete(self, key: str):
        """Queue delete operation for async processing"""
        with self._queue_lock:
            if len(self._write_queue) < self._max_queue_size:
                self._write_queue.append(('delete', key, None, time.time()))
    
    def _process_batch(self):
        """Process batch of queued operations"""
        with self._queue_lock:
            if not self._write_queue:
                return
            
            # Get batch
            batch = self._write_queue[:self._batch_size]
            self._write_queue = self._write_queue[self._batch_size:]
        
        # Process operations
        for operation in batch:
            op_type, key, value, timestamp = operation
            
            try:
                if op_type == 'write':
                    self._write_to_backing_store(key, value)
                elif op_type == 'delete':
                    self._delete_from_backing_store(key)
                
                logger.debug(f"Processed {op_type} for {key}")
                
            except Exception as e:
                logger.error(f"Failed to process {op_type} for {key}: {str(e)}")
                # Re-queue failed operation (with limit)
                if timestamp > time.time() - 300:  # Don't retry old failures
                    with self._queue_lock:
                        self._write_queue.append(operation)
    
    def start_batch_processor(self):
        """Start batch processing thread"""
        if self._batch_thread and self._batch_thread.is_alive():
            return
        
        self._running = True
        
        def batch_worker():
            while self._running:
                time.sleep(self._batch_interval)
                try:
                    self._process_batch()
                except Exception as e:
                    logger.error(f"Error in batch processor: {str(e)}")
        
        self._batch_thread = threading.Thread(target=batch_worker, daemon=True)
        self._batch_thread.start()
        logger.info("Started write-through batch processor")
    
    def stop_batch_processor(self):
        """Stop batch processing thread"""
        self._running = False
        if self._batch_thread:
            # Process remaining items
            self._process_batch()
            self._batch_thread.join(timeout=5)
            self._batch_thread = None
            logger.info("Stopped write-through batch processor")
    
    def flush_queue(self):
        """Flush all queued operations"""
        logger.info("Flushing write queue")
        while self._write_queue:
            self._process_batch()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        cache_stats = self.cache.get_stats() if hasattr(self.cache, 'get_stats') else {}
        
        stats = {
            'type': 'WriteThroughCache',
            'write_async': self.write_async,
            'queue_size': len(self._write_queue),
            'max_queue_size': self._max_queue_size,
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'write_hits': self._write_hits,
            'write_misses': self._write_misses,
            'async_writes': self._async_writes,
            'sync_writes': self._sync_writes,
            'batch_size': self._batch_size,
            'batch_interval': self._batch_interval,
            'batch_processor_running': self._running
        }
        
        stats.update(cache_stats)
        return stats
    
    def health_check(self) -> bool:
        """Health check for write-through cache"""
        try:
            # Check cache
            if hasattr(self.cache, 'health_check'):
                cache_healthy = self.cache.health_check()
            else:
                cache_healthy = True
            
            # Check backing store (implement based on store type)
            backing_healthy = True
            
            return cache_healthy and backing_healthy
        
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False
    
    def close(self):
        """Close cache and backing store connections"""
        if self.write_async:
            self.stop_batch_processor()
            self.flush_queue()
        
        if hasattr(self.cache, 'close'):
            self.cache.close()
        
        if hasattr(self.backing_store, 'close'):
            self.backing_store.close()
        
        logger.info("Write-through cache closed")

# Database-backed write-through cache implementation
class DatabaseWriteThroughCache(WriteThroughCache):
    """
    Write-through cache with database backing store
    """
    
    def __init__(
        self,
        cache_service: Any,
        db_session,
        model_class,
        cache_key_field: str = 'id',
        **kwargs
    ):
        """
        Args:
            cache_service: Cache service
            db_session: Database session
            model_class: SQLAlchemy model class
            cache_key_field: Field to use as cache key
        """
        super().__init__(cache_service, None, **kwargs)
        self.db_session = db_session
        self.model_class = model_class
        self.cache_key_field = cache_key_field
    
    def _read_from_backing_store(self, key: str) -> Optional[Any]:
        """Read from database"""
        try:
            query = self.db_session.query(self.model_class)
            instance = query.filter_by(**{self.cache_key_field: key}).first()
            
            if instance:
                return self._serialize_instance(instance)
        
        except Exception as e:
            logger.error(f"Error reading from database: {str(e)}")
        
        return None
    
    def _write_to_backing_store(self, key: str, value: Any) -> bool:
        """Write to database"""
        try:
            # Check if exists
            exists = self.db_session.query(
                self.model_class.query.filter_by(**{self.cache_key_field: key}).exists()
            ).scalar()
            
            if exists:
                # Update
                self.db_session.query(self.model_class).filter_by(
                    **{self.cache_key_field: key}
                ).update(self._deserialize_for_update(value))
            else:
                # Insert
                instance = self.model_class(
                    **{self.cache_key_field: key},
                    **self._deserialize_for_insert(value)
                )
                self.db_session.add(instance)
            
            self.db_session.commit()
            return True
        
        except Exception as e:
            logger.error(f"Error writing to database: {str(e)}")
            self.db_session.rollback()
            return False
    
    def _delete_from_backing_store(self, key: str) -> bool:
        """Delete from database"""
        try:
            deleted = self.db_session.query(self.model_class).filter_by(
                **{self.cache_key_field: key}
            ).delete()
            
            self.db_session.commit()
            return deleted > 0
        
        except Exception as e:
            logger.error(f"Error deleting from database: {str(e)}")
            self.db_session.rollback()
            return False
    
    def _exists_in_backing_store(self, key: str) -> bool:
        """Check if exists in database"""
        try:
            exists = self.db_session.query(
                self.model_class.query.filter_by(**{self.cache_key_field: key}).exists()
            ).scalar()
            return exists
        
        except Exception as e:
            logger.error(f"Error checking existence in database: {str(e)}")
            return False
    
    def _serialize_instance(self, instance) -> Dict[str, Any]:
        """Serialize database instance for cache"""
        # Convert to dict
        result = {}
        for column in instance.__table__.columns:
            result[column.name] = getattr(instance, column.name)
        return result
    
    def _deserialize_for_update(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize cache value for database update"""
        # Remove key field from update dict
        result = value.copy()
        result.pop(self.cache_key_field, None)
        return result
    
    def _deserialize_for_insert(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize cache value for database insert"""
        return value