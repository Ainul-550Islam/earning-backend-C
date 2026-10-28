"""
Health Check for alerts app - System health monitoring and diagnostics
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from asgiref.sync import sync_to_async
import asyncio
import logging
import time
import psutil
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthCheck(ABC):
    """Abstract base class for health checks"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.enabled = config.get('enabled', True)
        self.timeout = config.get('timeout', 30)
        self.interval = config.get('interval', 60)  # seconds
        self.failure_threshold = config.get('failure_threshold', 3)
        self.success_threshold = config.get('success_threshold', 2)
        
        # State tracking
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.last_check = None
        self.last_result = None
        self.status = HealthStatus.UNKNOWN
        
    @abstractmethod
    async def check(self) -> Dict[str, Any]:
        """Perform the health check"""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get current health status"""
        return {
            'name': self.name,
            'status': self.status.value,
            'enabled': self.enabled,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'last_result': self.last_result,
            'consecutive_failures': self.consecutive_failures,
            'consecutive_successes': self.consecutive_successes,
            'timeout': self.timeout,
            'interval': self.interval
        }
    
    def _update_status(self, check_result: Dict[str, Any]):
        """Update health status based on check result"""
        self.last_check = timezone.now()
        self.last_result = check_result
        
        # Determine if check passed
        check_passed = check_result.get('healthy', False)
        
        if check_passed:
            self.consecutive_successes += 1
            self.consecutive_failures = 0
            
            # Check if we should mark as healthy
            if self.consecutive_successes >= self.success_threshold:
                if self.status != HealthStatus.HEALTHY:
                    logger.info(f"Health check {self.name} marked as healthy")
                self.status = HealthStatus.HEALTHY
        else:
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            
            # Check if we should mark as unhealthy
            if self.consecutive_failures >= self.failure_threshold:
                if self.status != HealthStatus.UNHEALTHY:
                    logger.warning(f"Health check {self.name} marked as unhealthy")
                self.status = HealthStatus.UNHEALTHY
            elif self.status == HealthStatus.HEALTHY:
                # Mark as degraded on first failure
                logger.warning(f"Health check {self.name} marked as degraded")
                self.status = HealthStatus.DEGRADED


class DatabaseHealthCheck(HealthCheck):
    """Database health check"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.max_connections = config.get('max_connections', 100)
        self.slow_query_threshold = config.get('slow_query_threshold', 1000)  # milliseconds
        
    def _check_sync(self) -> Dict[str, Any]:
        """Synchronous DB health check logic - run via sync_to_async from check()
        below, since raw connection.cursor() access is a synchronous-only Django
        ORM operation and cannot be called directly inside an async function."""
        start_time = time.time()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

                cursor.execute("SELECT count(*) FROM pg_stat_activity")
                connection_count = cursor.fetchone()[0]

                slow_queries = []
                try:
                    cursor.execute("""
                        SELECT query, mean_time, calls 
                        FROM pg_stat_statements 
                        WHERE mean_time > %s
                        ORDER BY mean_time DESC 
                        LIMIT 5
                    """, [self.slow_query_threshold])

                    for row in cursor.fetchall():
                        slow_queries.append({
                            'query': row[0][:100],  # Truncate long queries
                            'mean_time': row[1],
                            'calls': row[2]
                        })
                except Exception:
                    slow_queries = []

                cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
                db_size = cursor.fetchone()[0]

                result = {
                    'healthy': True,
                    'connection_test_ms': (time.time() - start_time) * 1000,
                    'connection_count': connection_count,
                    'max_connections': self.max_connections,
                    'slow_queries': slow_queries,
                    'slow_query_count': len(slow_queries),
                    'database_size': db_size,
                    'timestamp': timezone.now().isoformat()
                }

                issues = []
                if connection_count > self.max_connections * 0.8:
                    issues.append(f"High connection count: {connection_count}/{self.max_connections}")
                if len(slow_queries) > 0:
                    issues.append(f"Found {len(slow_queries)} slow queries")
                if issues:
                    result['healthy'] = False
                    result['issues'] = issues

                return result
        except Exception:
            logger.exception("Unhandled error in _check_sync")
            return {
                'healthy': False,
                'error': 'Operation failed',
                'timestamp': timezone.now().isoformat()
            }

    async def check(self) -> Dict[str, Any]:
        """Check database health"""
        result = await sync_to_async(self._check_sync, thread_sensitive=True)()
        self._update_status(result)
        return result


class CacheHealthCheck(HealthCheck):
    """Cache health check"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.cache_backend = config.get('cache_backend', 'default')
        
    async def check(self) -> Dict[str, Any]:
        """Check cache health"""
        start_time = time.time()
        
        try:
            # Test cache write
            test_key = f"health_check_{int(time.time())}"
            test_value = {'test': True, 'timestamp': timezone.now().isoformat()}
            
            cache.set(test_key, test_value, timeout=60)
            
            # Test cache read
            start_read = time.time()
            cached_value = cache.get(test_key)
            read_time = (time.time() - start_read) * 1000
            
            # Clean up
            cache.delete(test_key)
            
            total_time = (time.time() - start_time) * 1000
            
            result = {
                'healthy': True,
                'write_time_ms': (time.time() - start_time) * 1000,
                'read_time_ms': read_time,
                'total_time_ms': total_time,
                'cache_backend': self.cache_backend,
                'test_passed': cached_value == test_value,
                'timestamp': timezone.now().isoformat()
            }
            
            # Check for issues
            issues = []
            
            if total_time > 1000:  # 1 second
                issues.append(f"Cache operation slow: {total_time:.2f}ms")
            
            if cached_value != test_value:
                issues.append("Cache read/write test failed")
                result['healthy'] = False
            
            if issues:
                result['issues'] = issues
            
            self._update_status(result)
            return result
            
        except Exception as e:
            result = {
                'healthy': False,
                'error': str(e),
                'cache_backend': self.cache_backend,
                'timestamp': timezone.now().isoformat()
            }
            
            self._update_status(result)
            return result


class ExternalServiceHealthCheck(HealthCheck):
    """External service health check"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.service_url = config.get('service_url')
        self.expected_status = config.get('expected_status', 200)
        self.headers = config.get('headers', {})
        self.method = config.get('method', 'GET')
        
    async def check(self) -> Dict[str, Any]:
        """Check external service health"""
        start_time = time.time()
        
        try:
            import aiohttp
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                if self.method.upper() == 'GET':
                    async with session.get(self.service_url, headers=self.headers) as response:
                        response_time = (time.time() - start_time) * 1000
                        response_text = await response.text()
                        
                        result = {
                            'healthy': response.status == self.expected_status,
                            'status_code': response.status,
                            'response_time_ms': response_time,
                            'service_url': self.service_url,
                            'response_length': len(response_text),
                            'timestamp': timezone.now().isoformat()
                        }
                elif self.method.upper() == 'POST':
                    async with session.post(self.service_url, headers=self.headers) as response:
                        response_time = (time.time() - start_time) * 1000
                        response_text = await response.text()
                        
                        result = {
                            'healthy': response.status == self.expected_status,
                            'status_code': response.status,
                            'response_time_ms': response_time,
                            'service_url': self.service_url,
                            'response_length': len(response_text),
                            'timestamp': timezone.now().isoformat()
                        }
                else:
                    result = {
                        'healthy': False,
                        'error': f"Unsupported method: {self.method}",
                        'service_url': self.service_url,
                        'timestamp': timezone.now().isoformat()
                    }
                
                # Check for issues
                if not result['healthy']:
                    result['issues'] = [f"Service returned status {response.status}"]
                
                self._update_status(result)
                return result
                
        except Exception as e:
            result = {
                'healthy': False,
                'error': str(e),
                'service_url': self.service_url,
                'timestamp': timezone.now().isoformat()
            }
            
            self._update_status(result)
            return result


class SystemResourceHealthCheck(HealthCheck):
    """System resource health check"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.cpu_threshold = config.get('cpu_threshold', 80)
        self.memory_threshold = config.get('memory_threshold', 85)
        self.disk_threshold = config.get('disk_threshold', 90)
        
    async def check(self) -> Dict[str, Any]:
        """Check system resource health"""
        try:
            # CPU check
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_healthy = cpu_percent < self.cpu_threshold
            
            # Memory check
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_healthy = memory_percent < self.memory_threshold
            
            # Disk check
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            disk_healthy = disk_percent < self.disk_threshold
            
            # Overall health
            overall_healthy = cpu_healthy and memory_healthy and disk_healthy
            
            result = {
                'healthy': overall_healthy,
                'cpu': {
                    'percent': cpu_percent,
                    'healthy': cpu_healthy,
                    'threshold': self.cpu_threshold
                },
                'memory': {
                    'percent': memory_percent,
                    'healthy': memory_healthy,
                    'threshold': self.memory_threshold,
                    'total_gb': memory.total / (1024**3),
                    'used_gb': memory.used / (1024**3),
                    'available_gb': memory.available / (1024**3)
                },
                'disk': {
                    'percent': disk_percent,
                    'healthy': disk_healthy,
                    'threshold': self.disk_threshold,
                    'total_gb': disk.total / (1024**3),
                    'used_gb': disk.used / (1024**3),
                    'free_gb': disk.free / (1024**3)
                },
                'timestamp': timezone.now().isoformat()
            }
            
            # Add issues if any
            issues = []
            
            if not cpu_healthy:
                issues.append(f"High CPU usage: {cpu_percent}%")
            
            if not memory_healthy:
                issues.append(f"High memory usage: {memory_percent}%")
            
            if not disk_healthy:
                issues.append(f"High disk usage: {disk_percent}%")
            
            if issues:
                result['issues'] = issues
            
            self._update_status(result)
            return result
            
        except Exception as e:
            result = {
                'healthy': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
            
            self._update_status(result)
            return result


class IntegrationHealthCheck(HealthCheck):
    """Integration-specific health check"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.integration_name = config.get('integration_name')
        self.check_function = config.get('check_function')
        
    async def check(self) -> Dict[str, Any]:
        """Check integration health"""
        try:
            if self.check_function and callable(self.check_function):
                result = await self.check_function()
            else:
                # Default integration check
                result = {
                    'healthy': False,
                    'error': 'No check function configured',
                    'integration_name': self.integration_name,
                    'timestamp': timezone.now().isoformat()
                }
            
            # Add integration info
            result['integration_name'] = self.integration_name
            
            self._update_status(result)
            return result
            
        except Exception as e:
            result = {
                'healthy': False,
                'error': str(e),
                'integration_name': self.integration_name,
                'timestamp': timezone.now().isoformat()
            }
            
            self._update_status(result)
            return result


class HealthCheckManager:
    """Manages multiple health checks"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.checks = {}
        self.enabled = config.get('enabled', True)
        self.global_timeout = config.get('global_timeout', 60)
        
        # Initialize health checks
        self._initialize_checks()
    
    def _initialize_checks(self):
        """Initialize health checks from configuration"""
        check_configs = self.config.get('checks', {})
        
        for check_name, check_config in check_configs.items():
            check_type = check_config.get('type', 'database')
            
            if check_type == 'database':
                check = DatabaseHealthCheck(check_name, check_config)
            elif check_type == 'cache':
                check = CacheHealthCheck(check_name, check_config)
            elif check_type == 'external_service':
                check = ExternalServiceHealthCheck(check_name, check_config)
            elif check_type == 'system_resources':
                check = SystemResourceHealthCheck(check_name, check_config)
            elif check_type == 'integration':
                check = IntegrationHealthCheck(check_name, check_config)
            else:
                logger.error(f"Unknown health check type: {check_type}")
                continue
            
            self.checks[check_name] = check
            logger.info(f"Initialized health check: {check_name}")
    
    async def run_check(self, check_name: str) -> Dict[str, Any]:
        """Run specific health check"""
        check = self.checks.get(check_name)
        if not check:
            return {
                'healthy': False,
                'error': f'Health check {check_name} not found'
            }
        
        if not check.enabled:
            return {
                'healthy': False,
                'error': f'Health check {check_name} is disabled'
            }
        
        try:
            # Run with timeout
            result = await asyncio.wait_for(check.check(), timeout=check.timeout)
            return result
        except asyncio.TimeoutError:
            return {
                'healthy': False,
                'error': f'Health check {check_name} timed out',
                'timeout': check.timeout
            }
        except Exception:
            logger.exception("Unhandled error in run_check")
            return {
                'healthy': False,
                'error': 'Operation failed'
            }
    
    async def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks"""
        if not self.enabled:
            return {
                'healthy': False,
                'error': 'Health check manager is disabled'
            }
        
        start_time = time.time()
        
        # Run all checks concurrently
        tasks = []
        for check_name in self.checks:
            task = asyncio.create_task(self.run_check(check_name))
            tasks.append((check_name, task))
        
        # Wait for all checks to complete
        results = {}
        for check_name, task in tasks:
            try:
                result = await task
                results[check_name] = result
            except Exception as e:
                results[check_name] = {
                    'healthy': False,
                    'error': str(e)
                }
        
        # Calculate overall health
        total_checks = len(results)
        healthy_checks = sum(1 for r in results.values() if r.get('healthy', False))
        
        overall_status = HealthStatus.HEALTHY
        if healthy_checks == 0:
            overall_status = HealthStatus.UNHEALTHY
        elif healthy_checks < total_checks:
            overall_status = HealthStatus.DEGRADED
        
        total_time = (time.time() - start_time) * 1000
        
        return {
            'healthy': overall_status == HealthStatus.HEALTHY,
            'status': overall_status.value,
            'total_checks': total_checks,
            'healthy_checks': healthy_checks,
            'unhealthy_checks': total_checks - healthy_checks,
            'total_time_ms': total_time,
            'checks': results,
            'timestamp': timezone.now().isoformat()
        }
    
    def get_check_status(self, check_name: str = None) -> Dict[str, Any]:
        """Get status of specific check or all checks"""
        if check_name:
            check = self.checks.get(check_name)
            if check:
                return check.get_status()
            else:
                return {'error': f'Health check {check_name} not found'}
        
        # Return all check statuses
        all_statuses = {}
        for name, check in self.checks.items():
            all_statuses[name] = check.get_status()
        
        return {
            'manager_enabled': self.enabled,
            'total_checks': len(self.checks),
            'enabled_checks': len([c for c in self.checks.values() if c.enabled]),
            'checks': all_statuses,
            'timestamp': timezone.now().isoformat()
        }
    
    def add_check(self, check_name: str, check: HealthCheck):
        """Add health check"""
        self.checks[check_name] = check
        logger.info(f"Added health check: {check_name}")
    
    def remove_check(self, check_name: str):
        """Remove health check"""
        if check_name in self.checks:
            del self.checks[check_name]
            logger.info(f"Removed health check: {check_name}")
    
    def enable_check(self, check_name: str):
        """Enable health check"""
        check = self.checks.get(check_name)
        if check:
            check.enabled = True
            logger.info(f"Enabled health check: {check_name}")
    
    def disable_check(self, check_name: str):
        """Disable health check"""
        check = self.checks.get(check_name)
        if check:
            check.enabled = False
            logger.info(f"Disabled health check: {check_name}")


class HealthCheckScheduler:
    """Scheduler for running health checks periodically"""
    
    def __init__(self, health_manager: HealthCheckManager, config: Dict[str, Any]):
        self.health_manager = health_manager
        self.config = config
        self.enabled = config.get('enabled', True)
        self.default_interval = config.get('default_interval', 300)  # 5 minutes
        self.scheduled_checks = {}
        self.running = False
        self.scheduler_task = None
        
    async def start(self):
        """Start the health check scheduler"""
        if self.running:
            logger.warning("Health check scheduler is already running")
            return
        
        self.running = True
        
        # Schedule checks
        for check_name, check in self.health_manager.checks.items():
            if check.enabled:
                interval = check.interval or self.default_interval
                self.scheduled_checks[check_name] = {
                    'interval': interval,
                    'last_run': None,
                    'task': None
                }
        
        # Start scheduler loop
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Health check scheduler started")
    
    async def stop(self):
        """Stop the health check scheduler"""
        self.running = False
        
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all scheduled tasks
        for check_name in self.scheduled_checks:
            if self.scheduled_checks[check_name]['task']:
                self.scheduled_checks[check_name]['task'].cancel()
        
        self.scheduled_checks.clear()
        logger.info("Health check scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                current_time = time.time()
                
                for check_name, schedule_info in self.scheduled_checks.items():
                    last_run = schedule_info['last_run']
                    interval = schedule_info['interval']
                    
                    # Check if it's time to run
                    if not last_run or (current_time - last_run) >= interval:
                        # Run the health check
                        task = asyncio.create_task(self.health_manager.run_check(check_name))
                        schedule_info['task'] = task
                        schedule_info['last_run'] = current_time
                        
                        logger.debug(f"Scheduled health check: {check_name}")
                
                # Wait before next iteration
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get scheduler status"""
        return {
            'running': self.running,
            'enabled': self.enabled,
            'default_interval': self.default_interval,
            'scheduled_checks': {
                name: {
                    'interval': info['interval'],
                    'last_run': info['last_run'],
                    'next_run': info['last_run'] + info['interval'] if info['last_run'] else None,
                    'task_running': info['task'] and info['task'].done() == False
                }
                for name, info in self.scheduled_checks.items()
            },
            'timestamp': timezone.now().isoformat()
        }


# Global health check manager
health_check_manager = None
health_check_scheduler = None


def get_health_check_manager() -> Optional[HealthCheckManager]:
    """Get the global health check manager"""
    return health_check_manager


def get_health_check_scheduler() -> Optional[HealthCheckScheduler]:
    """Get the global health check scheduler"""
    return health_check_scheduler


async def initialize_health_checks():
    """Initialize health checks from settings"""
    from django.conf import settings
    
    global health_check_manager, health_check_scheduler
    
    config = getattr(settings, 'HEALTH_CHECK_CONFIG', {
        'enabled': True,
        'global_timeout': 60,
        'checks': {
            'database': {
                'type': 'database',
                'enabled': True,
                'timeout': 30,
                'max_connections': 100,
                'slow_query_threshold': 1000
            },
            'cache': {
                'type': 'cache',
                'enabled': True,
                'timeout': 10,
                'cache_backend': 'default'
            },
            'system_resources': {
                'type': 'system_resources',
                'enabled': True,
                'timeout': 15,
                'cpu_threshold': 80,
                'memory_threshold': 85,
                'disk_threshold': 90
            }
        }
    })
    
    try:
        health_check_manager = HealthCheckManager(config)
        
        scheduler_config = getattr(settings, 'HEALTH_CHECK_SCHEDULER_CONFIG', {
            'enabled': True,
            'default_interval': 300
        })
        
        health_check_scheduler = HealthCheckScheduler(health_check_manager, scheduler_config)
        
        # Auto-start scheduler if enabled
        if scheduler_config.get('auto_start', True):
            await health_check_scheduler.start()
        
        logger.info("Health check system initialized")
        
    except Exception as e:
        logger.error(f"Error initializing health checks: {e}")


def start_health_checks():
    """Start the health-check manager/scheduler explicitly (ASGI startup hook or management command).

    Not run at import: ``asyncio.create_task`` at import time needs a running event loop (it failed
    with 'no running event loop' on every WSGI start) and would start one scheduler per worker.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(initialize_health_checks())
    return asyncio.ensure_future(initialize_health_checks())
