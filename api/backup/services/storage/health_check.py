"""
Storage Adapter Health Check Module
Provides health monitoring and status checking for storage adapters.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from .base import StorageAdapterInterface
from .factory import BackupStorageFactory

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a health check for a storage adapter."""
    adapter_type: str
    is_healthy: bool
    response_time_ms: float
    error_message: Optional[str] = None
    storage_stats: Optional[Dict[str, Any]] = None
    last_check: datetime = None
    
    def __post_init__(self):
        if self.last_check is None:
            self.last_check = datetime.now()


class StorageHealthChecker:
    """
    Health checker for storage adapters.
    Monitors adapter health and provides status reporting.
    """
    
    def __init__(self):
        """Initialize health checker."""
        self.factory = BackupStorageFactory()
        self.health_history: Dict[str, List[HealthCheckResult]] = {}
        self.max_history_size = 100
    
    def check_adapter_health(self, storage_type: str, config: Dict[str, Any] = None) -> HealthCheckResult:
        """
        Check health of a specific storage adapter.
        
        Args:
            storage_type: Type of storage adapter
            config: Storage configuration
            
        Returns:
            HealthCheckResult: Health check result
        """
        start_time = datetime.now()
        
        try:
            # Create adapter instance
            adapter = self.factory.get_adapter(storage_type, config or {})
            
            # Test connection
            connection_start = datetime.now()
            is_connected = adapter.test_connection()
            connection_time = (datetime.now() - connection_start).total_seconds() * 1000
            
            if not is_connected:
                return HealthCheckResult(
                    adapter_type=storage_type,
                    is_healthy=False,
                    response_time_ms=connection_time,
                    error_message="Connection test failed",
                    last_check=datetime.now()
                )
            
            # Get storage stats
            try:
                stats = adapter.get_storage_stats()
            except Exception as e:
                logger.warning(f"Failed to get storage stats for {storage_type}: {e}")
                stats = None
            
            # Calculate total response time
            total_time = (datetime.now() - start_time).total_seconds() * 1000
            
            result = HealthCheckResult(
                adapter_type=storage_type,
                is_healthy=True,
                response_time_ms=total_time,
                storage_stats=stats,
                last_check=datetime.now()
            )
            
            # Store in history
            self._store_health_result(result)
            
            return result
            
        except Exception as e:
            total_time = (datetime.now() - start_time).total_seconds() * 1000
            
            result = HealthCheckResult(
                adapter_type=storage_type,
                is_healthy=False,
                response_time_ms=total_time,
                error_message=str(e),
                last_check=datetime.now()
            )
            
            self._store_health_result(result)
            return result
    
    def check_all_adapters(self, configs: Dict[str, Dict[str, Any]] = None) -> List[HealthCheckResult]:
        """
        Check health of all registered storage adapters.
        
        Args:
            configs: Configuration for each adapter type
            
        Returns:
            List[HealthCheckResult]: Health check results for all adapters
        """
        results = []
        adapter_types = self.factory.get_available_types()
        
        for adapter_type in adapter_types:
            config = configs.get(adapter_type) if configs else None
            result = self.check_adapter_health(adapter_type, config)
            results.append(result)
        
        return results
    
    def get_adapter_history(self, storage_type: str, limit: int = 10) -> List[HealthCheckResult]:
        """
        Get health check history for a specific adapter.
        
        Args:
            storage_type: Type of storage adapter
            limit: Maximum number of results to return
            
        Returns:
            List[HealthCheckResult]: Historical health check results
        """
        history = self.health_history.get(storage_type, [])
        return history[-limit:] if len(history) > limit else history
    
    def get_adapter_uptime(self, storage_type: str, hours: int = 24) -> float:
        """
        Calculate uptime percentage for an adapter.
        
        Args:
            storage_type: Type of storage adapter
            hours: Time window in hours
            
        Returns:
            float: Uptime percentage (0-100)
        """
        history = self.get_adapter_history(storage_type)
        if not history:
            return 0.0
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_checks = [h for h in history if h.last_check >= cutoff_time]
        
        if not recent_checks:
            return 0.0
        
        healthy_checks = [h for h in recent_checks if h.is_healthy]
        uptime = (len(healthy_checks) / len(recent_checks)) * 100
        
        return round(uptime, 2)
    
    def get_average_response_time(self, storage_type: str, hours: int = 24) -> float:
        """
        Calculate average response time for an adapter.
        
        Args:
            storage_type: Type of storage adapter
            hours: Time window in hours
            
        Returns:
            float: Average response time in milliseconds
        """
        history = self.get_adapter_history(storage_type)
        if not history:
            return 0.0
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_checks = [h for h in history if h.last_check >= cutoff_time]
        
        if not recent_checks:
            return 0.0
        
        response_times = [h.response_time_ms for h in recent_checks]
        avg_time = sum(response_times) / len(response_times)
        
        return round(avg_time, 2)
    
    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get overall health summary of all adapters.
        
        Returns:
            Dict: Health summary including uptime, response times, etc.
        """
        adapter_types = self.factory.get_available_types()
        summary = {
            'total_adapters': len(adapter_types),
            'healthy_adapters': 0,
            'unhealthy_adapters': 0,
            'average_response_time': 0.0,
            'overall_uptime': 0.0,
            'last_check': None,
            'adapters': {}
        }
        
        total_response_time = 0.0
        total_uptime = 0.0
        adapter_count = 0
        
        for adapter_type in adapter_types:
            latest_result = self.get_latest_health_result(adapter_type)
            
            if latest_result:
                if latest_result.is_healthy:
                    summary['healthy_adapters'] += 1
                else:
                    summary['unhealthy_adapters'] += 1
                
                total_response_time += latest_result.response_time_ms
                total_uptime += self.get_adapter_uptime(adapter_type)
                adapter_count += 1
                
                summary['adapters'][adapter_type] = {
                    'is_healthy': latest_result.is_healthy,
                    'response_time_ms': latest_result.response_time_ms,
                    'uptime_24h': self.get_adapter_uptime(adapter_type),
                    'last_check': latest_result.last_check.isoformat(),
                    'error_message': latest_result.error_message
                }
        
        if adapter_count > 0:
            summary['average_response_time'] = round(total_response_time / adapter_count, 2)
            summary['overall_uptime'] = round(total_uptime / adapter_count, 2)
        
        return summary
    
    def get_latest_health_result(self, storage_type: str) -> Optional[HealthCheckResult]:
        """
        Get the latest health check result for an adapter.
        
        Args:
            storage_type: Type of storage adapter
            
        Returns:
            HealthCheckResult: Latest health check result or None
        """
        history = self.health_history.get(storage_type, [])
        return history[-1] if history else None
    
    def cleanup_old_history(self, hours: int = 168):  # 7 days
        """
        Clean up old health check history.
        
        Args:
            hours: Age threshold in hours
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        for storage_type in self.health_history:
            self.health_history[storage_type] = [
                h for h in self.health_history[storage_type] 
                if h.last_check >= cutoff_time
            ]
    
    def _store_health_result(self, result: HealthCheckResult):
        """
        Store health check result in history.
        
        Args:
            result: Health check result to store
        """
        storage_type = result.adapter_type
        
        if storage_type not in self.health_history:
            self.health_history[storage_type] = []
        
        self.health_history[storage_type].append(result)
        
        # Limit history size
        if len(self.health_history[storage_type]) > self.max_history_size:
            self.health_history[storage_type] = self.health_history[storage_type][-self.max_history_size:]
        
        logger.debug(f"Stored health result for {storage_type}: {result.is_healthy}")
    
    def run_continuous_health_check(self, interval_minutes: int = 5, configs: Dict[str, Dict[str, Any]] = None):
        """
        Run continuous health checks on all adapters.
        
        Args:
            interval_minutes: Interval between checks in minutes
            configs: Configuration for each adapter type
        """
        import time
        
        logger.info(f"Starting continuous health check with {interval_minutes} minute interval")
        
        try:
            while True:
                results = self.check_all_adapters(configs)
                
                # Log results
                for result in results:
                    status = "HEALTHY" if result.is_healthy else "UNHEALTHY"
                    logger.info(f"Health check {result.adapter_type}: {status} ({result.response_time_ms:.2f}ms)")
                    
                    if not result.is_healthy:
                        logger.error(f"Adapter {result.adapter_type} error: {result.error_message}")
                
                # Clean up old history periodically
                if datetime.now().minute % 30 == 0:  # Every 30 minutes
                    self.cleanup_old_history()
                
                # Wait for next check
                time.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            logger.info("Continuous health check stopped by user")
        except Exception as e:
            logger.error(f"Continuous health check error: {e}")
            raise


# Convenience functions
def create_health_checker() -> StorageHealthChecker:
    """Create a new health checker instance."""
    return StorageHealthChecker()


def quick_health_check(storage_type: str, config: Dict[str, Any] = None) -> HealthCheckResult:
    """
    Perform a quick health check on a storage adapter.
    
    Args:
        storage_type: Type of storage adapter
        config: Storage configuration
        
    Returns:
        HealthCheckResult: Health check result
    """
    checker = StorageHealthChecker()
    return checker.check_adapter_health(storage_type, config)


def get_all_adapter_health(configs: Dict[str, Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Get health status of all storage adapters.
    
    Args:
        configs: Configuration for each adapter type
        
    Returns:
        Dict: Health summary of all adapters
    """
    checker = StorageHealthChecker()
    return checker.get_health_summary()
