"""
Storage Adapter Failover Module
Provides automated failover between storage adapters with health monitoring.
"""

import logging
import threading
try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
import os
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from .base import StorageAdapterInterface, StorageError
from .health_check import StorageHealthChecker, HealthCheckResult
from .factory import BackupStorageFactory

logger = logging.getLogger(__name__)


class FailoverStrategy(Enum):
    """Failover strategy for storage adapters."""
    PRIMARY_ONLY = "primary_only"
    FAILOVER_ON_FAILURE = "failover_on_failure"
    ROUND_ROBIN = "round_robin"
    HEALTH_BASED = "health_based"


@dataclass
class FailoverConfig:
    """Configuration for storage failover."""
    primary_storage: str
    fallback_storages: List[str]
    strategy: FailoverStrategy = FailoverStrategy.FAILOVER_ON_FAILURE
    health_check_interval: int = 300  # 5 minutes
    max_consecutive_failures: int = 3
    auto_switch_back: bool = True
    health_threshold_score: float = 80.0  # Minimum health score to consider healthy


@dataclass
class FailoverStatus:
    """Current status of failover system."""
    active_adapter: str
    primary_adapter: str
    last_switch_time: Optional[str] = None
    switch_count: int = 0
    consecutive_failures: Dict[str, int] = None
    health_scores: Dict[str, float] = None
    
    def __post_init__(self):
        if self.consecutive_failures is None:
            self.consecutive_failures = {}
        if self.health_scores is None:
            self.health_scores = {}


class StorageFailoverManager:
    """
    Manages automated failover between storage adapters.
    Provides intelligent switching based on health monitoring.
    """
    
    def __init__(self, config: FailoverConfig):
        """Initialize failover manager."""
        self.config = config
        self.factory = BackupStorageFactory()
        self.health_checker = StorageHealthChecker()
        self.adapters: Dict[str, StorageAdapterInterface] = {}
        self.status = FailoverStatus(
            active_adapter=config.primary_storage,
            primary_adapter=config.primary_storage
        )
        
        # Initialize failover lock for concurrent protection
        self._failover_lock = threading.RLock()
        self._operation_locks = {}  # Per-backup operation locks
        
        # Initialize adapters
        self._initialize_adapters()
        
        logger.info(f"Failover manager initialized with primary: {config.primary_storage}")
    
    def _initialize_adapters(self):
        """Initialize all configured storage adapters."""
        all_storage_types = [self.config.primary_storage] + self.config.fallback_storages
        
        for storage_type in all_storage_types:
            try:
                adapter = self.factory.get_adapter(storage_type)
                self.adapters[storage_type] = adapter
                logger.info(f"Initialized storage adapter: {storage_type}")
            except Exception as e:
                logger.error(f"Failed to initialize adapter {storage_type}: {e}")
    
    def get_active_adapter(self) -> StorageAdapterInterface:
        """
        Get the currently active storage adapter.
        
        Returns:
            StorageAdapterInterface: Active adapter
        """
        return self.adapters.get(self.status.active_adapter)
    
    def save_backup_with_failover(self, file_obj, backup) -> bool:
        """
        Save backup with automatic failover on failure.
        
        Args:
            file_obj: File-like object containing backup data
            backup: Backup model instance
            
        Returns:
            bool: True if successful, False otherwise
        """
        backup_id = str(backup.backup_id) if hasattr(backup, 'backup_id') else str(id(backup))
        
        # Acquire backup-specific operation lock for concurrent protection
        operation_lock = self._get_operation_lock(backup_id)
        
        with operation_lock:
            adapters_to_try = self._get_adapter_priority_list()
            
            for adapter_type in adapters_to_try:
                try:
                    adapter = self.adapters.get(adapter_type)
                    if not adapter:
                        logger.warning(f"Adapter {adapter_type} not available")
                        continue
                    
                    # Check adapter health before attempting save
                    if not self._is_adapter_healthy(adapter_type):
                        logger.warning(f"Adapter {adapter_type} is unhealthy, skipping")
                        continue
                    
                    logger.info(f"Attempting to save backup using {adapter_type}")
                    
                    # Reset file pointer for each attempt
                    file_obj.seek(0)
                    
                    success = adapter.save_backup(file_obj, backup)
                    
                    if success:
                        # Update backup with storage type
                        backup.storage_type = adapter_type
                        backup.save()
                        
                        # Update active adapter if different
                        if adapter_type != self.status.active_adapter:
                            self._switch_active_adapter(adapter_type, "successful_save")
                        
                        logger.info(f"Successfully saved backup using {adapter_type}")
                        return True
                    else:
                        logger.warning(f"Failed to save backup using {adapter_type}")
                        self._record_failure(adapter_type)
                        
                except Exception as e:
                    logger.error(f"Error saving backup with {adapter_type}: {e}")
                    self._record_failure(adapter_type)
            
            # All adapters failed
            logger.error("All storage adapters failed to save backup")
            return False
    
    def retrieve_backup_with_failover(self, backup) -> Optional:
        """
        Retrieve backup with automatic failover on failure.
        
        Args:
            backup: Backup model instance
            
        Returns:
            File-like object or None if not found
        """
        adapters_to_try = self._get_adapter_priority_list()
        
        for adapter_type in adapters_to_try:
            try:
                adapter = self.adapters.get(adapter_type)
                if not adapter:
                    continue
                
                # Check adapter health before attempting retrieval
                if not self._is_adapter_healthy(adapter_type):
                    logger.warning(f"Adapter {adapter_type} is unhealthy, skipping")
                    continue
                
                logger.info(f"Attempting to retrieve backup using {adapter_type}")
                
                result = adapter.retrieve_backup(backup)
                
                if result:
                    logger.info(f"Successfully retrieved backup using {adapter_type}")
                    return result
                else:
                    logger.warning(f"Failed to retrieve backup using {adapter_type}")
                    self._record_failure(adapter_type)
                    
            except Exception as e:
                logger.error(f"Error retrieving backup with {adapter_type}: {e}")
                self._record_failure(adapter_type)
        
        logger.error("All storage adapters failed to retrieve backup")
        return None
    
    def check_and_maintain_failover(self) -> Dict[str, Any]:
        """
        Check health of all adapters and maintain failover status.
        
        Returns:
            Dict: Failover maintenance results
        """
        results = {
            'health_checks': {},
            'switches_made': [],
            'current_status': self.status.__dict__
        }
        
        # Check health of all adapters
        for adapter_type in self.adapters.keys():
            try:
                health_result = self.health_checker.check_adapter_health(adapter_type)
                results['health_checks'][adapter_type] = health_result.__dict__
                
                # Update health score
                self.status.health_scores[adapter_type] = self._calculate_health_score(health_result)
                
            except Exception as e:
                logger.error(f"Health check failed for {adapter_type}: {e}")
                results['health_checks'][adapter_type] = {
                    'is_healthy': False,
                    'error_message': str(e)
                }
                self.status.health_scores[adapter_type] = 0.0
        
        # Determine if failover is needed
        if self.config.strategy == FailoverStrategy.FAILOVER_ON_FAILURE:
            self._handle_failover_on_failure(results)
        elif self.config.strategy == FailoverStrategy.HEALTH_BASED:
            self._handle_health_based_failover(results)
        elif self.config.strategy == FailoverStrategy.ROUND_ROBIN:
            self._handle_round_robin_failover(results)
        
        return results
    
    def get_failover_status(self) -> Dict[str, Any]:
        """
        Get current failover status and statistics.
        
        Returns:
            Dict: Failover status information
        """
        return {
            'active_adapter': self.status.active_adapter,
            'primary_adapter': self.status.primary_adapter,
            'last_switch_time': self.status.last_switch_time,
            'switch_count': self.status.switch_count,
            'consecutive_failures': self.status.consecutive_failures,
            'health_scores': self.status.health_scores,
            'config': {
                'strategy': self.config.strategy.value,
                'primary_storage': self.config.primary_storage,
                'fallback_storages': self.config.fallback_storages,
                'max_consecutive_failures': self.config.max_consecutive_failures,
                'auto_switch_back': self.config.auto_switch_back
            },
            'available_adapters': list(self.adapters.keys())
        }
    
    def force_switch_adapter(self, target_adapter: str, reason: str = "manual") -> bool:
        """
        Force switch to a specific adapter.
        
        Args:
            target_adapter: Target adapter type
            reason: Reason for switching
            
        Returns:
            bool: True if successful, False otherwise
        """
        if target_adapter not in self.adapters:
            logger.error(f"Target adapter {target_adapter} not available")
            return False
        
        if target_adapter == self.status.active_adapter:
            logger.info(f"Already using adapter {target_adapter}")
            return True
        
        self._switch_active_adapter(target_adapter, reason)
        logger.info(f"Force switched to adapter {target_adapter} (reason: {reason})")
        return True
    
    def reset_failover_state(self):
        """Reset failover state to primary adapter."""
        if self.config.primary_adapter in self.adapters:
            self._switch_active_adapter(self.config.primary_adapter, "reset")
            self.status.consecutive_failures.clear()
            logger.info("Reset failover state to primary adapter")
    
    def _get_adapter_priority_list(self) -> List[str]:
        """
        Get ordered list of adapters based on strategy.
        
        Returns:
            List[str]: Ordered adapter types
        """
        if self.config.strategy == FailoverStrategy.FAILOVER_ON_FAILURE:
            # Start with active, then fallbacks
            priority = [self.status.active_adapter]
            for fallback in self.config.fallback_storages:
                if fallback not in priority:
                    priority.append(fallback)
            if self.config.primary_storage not in priority:
                priority.append(self.config.primary_storage)
            
        elif self.config.strategy == FailoverStrategy.HEALTH_BASED:
            # Order by health score
            adapters = list(self.adapters.keys())
            adapters.sort(key=lambda x: self.status.health_scores.get(x, 0), reverse=True)
            priority = adapters
            
        elif self.config.strategy == FailoverStrategy.ROUND_ROBIN:
            # Rotate through adapters
            adapters = [self.config.primary_storage] + self.config.fallback_storages
            current_index = adapters.index(self.status.active_adapter)
            priority = adapters[current_index:] + adapters[:current_index]
            
        else:  # PRIMARY_ONLY
            priority = [self.config.primary_storage]
        
        return [a for a in priority if a in self.adapters]
    
    def _is_adapter_healthy(self, adapter_type: str) -> bool:
        """
        Check if adapter is healthy based on recent health checks.
        
        Args:
            adapter_type: Type of storage adapter
            
        Returns:
            bool: True if healthy, False otherwise
        """
        consecutive_failures = self.status.consecutive_failures.get(adapter_type, 0)
        health_score = self.status.health_scores.get(adapter_type, 0.0)
        
        return (consecutive_failures < self.config.max_consecutive_failures and
                health_score >= self.config.health_threshold_score)
    
    def _handle_failover_on_failure(self, results: Dict[str, Any]):
        """
        Handle failover based on consecutive failures.
        
        Args:
            results: Health check results
        """
        current_adapter = self.status.active_adapter
        consecutive_failures = self.status.consecutive_failures.get(current_adapter, 0)
        
        # Check if current adapter has too many failures
        if consecutive_failures >= self.config.max_consecutive_failures:
            # Find next healthy adapter
            for fallback in self.config.fallback_storages:
                if (fallback in self.adapters and 
                    self._is_adapter_healthy(fallback)):
                    self._switch_active_adapter(fallback, "consecutive_failures")
                    results['switches_made'].append({
                        'from': current_adapter,
                        'to': fallback,
                        'reason': 'consecutive_failures'
                    })
                    break
    
    def _handle_health_based_failover(self, results: Dict[str, Any]):
        """
        Handle failover based on health scores.
        
        Args:
            results: Health check results
        """
        # Find best adapter based on health score
        best_adapter = None
        best_score = -1
        
        for adapter_type, score in self.status.health_scores.items():
            if score > best_score and self._is_adapter_healthy(adapter_type):
                best_score = score
                best_adapter = adapter_type
        
        # Switch if different and better
        if (best_adapter and best_adapter != self.status.active_adapter and
            best_score > self.status.health_scores.get(self.status.active_adapter, 0)):
            self._switch_active_adapter(best_adapter, "health_based")
            results['switches_made'].append({
                'from': self.status.active_adapter,
                'to': best_adapter,
                'reason': 'health_score'
            })
    
    def _handle_round_robin_failover(self, results: Dict[str, Any]):
        """
        Handle failover using round-robin strategy.
        
        Args:
            results: Health check results
        """
        if not self._is_adapter_healthy(self.status.active_adapter):
            # Move to next adapter in round-robin
            adapters = [self.config.primary_storage] + self.config.fallback_storages
            current_index = adapters.index(self.status.active_adapter)
            
            for i in range(1, len(adapters)):
                next_index = (current_index + i) % len(adapters)
                next_adapter = adapters[next_index]
                
                if (next_adapter in self.adapters and 
                    self._is_adapter_healthy(next_adapter)):
                    self._switch_active_adapter(next_adapter, "round_robin")
                    results['switches_made'].append({
                        'from': self.status.active_adapter,
                        'to': next_adapter,
                        'reason': 'round_robin'
                    })
                    break
    
    def _switch_active_adapter(self, new_adapter: str, reason: str):
        """
        Switch to a new active adapter.
        
        Args:
            new_adapter: New adapter type
            reason: Reason for switching
        """
        from datetime import datetime
        
        old_adapter = self.status.active_adapter
        self.status.active_adapter = new_adapter
        self.status.last_switch_time = datetime.now().isoformat()
        self.status.switch_count += 1
        
        logger.info(f"Switched storage adapter: {old_adapter} -> {new_adapter} (reason: {reason})")
    
    def _record_failure(self, adapter_type: str):
        """
        Record a failure for an adapter.
        
        Args:
            adapter_type: Type of storage adapter
        """
        self.status.consecutive_failures[adapter_type] = self.status.consecutive_failures.get(adapter_type, 0) + 1
        logger.debug(f"Recorded failure for {adapter_type}: {self.status.consecutive_failures[adapter_type]}")
    
    def _calculate_health_score(self, health_result: HealthCheckResult) -> float:
        """
        Calculate health score from health check result.
        
        Args:
            health_result: Health check result
            
        Returns:
            float: Health score (0-100)
        """
        if not health_result.is_healthy:
            return 0.0
        
        # Base score from health status
        base_score = 50.0
        
        # Add points for fast response time (under 1 second = +50, over 5 seconds = 0)
        response_time_score = max(0, 50 - (health_result.response_time_ms / 100))
        
        # Add points for having storage stats
        stats_score = 20.0 if health_result.storage_stats else 0.0
        
        total_score = base_score + response_time_score + stats_score
        return min(100.0, max(0.0, total_score))
    
    def _get_operation_lock(self, backup_id: str):
        """
        Get or create a backup-specific operation lock.
        
        Args:
            backup_id: Unique backup identifier
            
        Returns:
            threading.RLock: Lock for this specific backup operation
        """
        with self._failover_lock:
            if backup_id not in self._operation_locks:
                self._operation_locks[backup_id] = threading.RLock()
            return self._operation_locks[backup_id]


# Convenience functions
def create_failover_manager(primary_storage: str, fallback_storages: List[str], 
                        strategy: FailoverStrategy = FailoverStrategy.FAILOVER_ON_FAILURE) -> StorageFailoverManager:
    """
    Create a failover manager with default configuration.
    
    Args:
        primary_storage: Primary storage type
        fallback_storages: List of fallback storage types
        strategy: Failover strategy
        
    Returns:
        StorageFailoverManager: Configured failover manager
    """
    config = FailoverConfig(
        primary_storage=primary_storage,
        fallback_storages=fallback_storages,
        strategy=strategy
    )
    
    return StorageFailoverManager(config)
