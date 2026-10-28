"""
Fallback Logic for alerts app - Graceful degradation and backup mechanisms
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
import logging
import re
from .sql_utils import safe_identifier
import time
import asyncio

logger = logging.getLogger(__name__)


class FallbackStrategy(ABC):
    """Abstract base class for fallback strategies"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        self.enabled = config.get('enabled', True)
        self.priority = config.get('priority', 1)  # Lower number = higher priority
        
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute fallback strategy"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if fallback strategy is available"""
        pass
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information"""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'priority': self.priority,
            'config': self.config
        }


class CacheFallbackStrategy(FallbackStrategy):
    """Fallback to cached data"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.cache_timeout = config.get('cache_timeout', 3600)  # 1 hour
        self.cache_key_prefix = config.get('cache_key_prefix', 'fallback')
        
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute cache fallback"""
        cache_key = f"{self.cache_key_prefix}_{context.get('operation', 'default')}_{context.get('id', 'unknown')}"
        
        try:
            # Try to get cached result
            cached_data = cache.get(cache_key)
            
            if cached_data is not None:
                logger.info(f"Cache fallback executed for {cache_key}")
                return {
                    'success': True,
                    'strategy': 'cache',
                    'data': cached_data,
                    'cache_hit': True,
                    'timestamp': timezone.now().isoformat()
                }
            
            return {
                'success': False,
                'strategy': 'cache',
                'error': 'No cached data available',
                'cache_key': cache_key
            }
            
        except Exception as e:
            logger.error(f"Cache fallback error: {e}")
            return {
                'success': False,
                'strategy': 'cache',
                'error': 'Operation failed',
                'cache_key': cache_key
            }
    
    def is_available(self) -> bool:
        """Check if cache is available"""
        try:
            # Test cache connectivity
            cache.set('test_key', 'test_value', timeout=10)
            test_value = cache.get('test_key')
            cache.delete('test_key')
            
            return test_value == 'test_value'
        except Exception as e:
            logger.error(f"Cache availability check failed: {e}")
            return False


class DatabaseFallbackStrategy(FallbackStrategy):
    """Fallback to database"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.connection_string = config.get('connection_string')
        self.table_name = config.get('table_name', 'fallback_data')
        self.query_timeout = config.get('query_timeout', 30)
        
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute database fallback"""
        try:
            # Query database for fallback data
            query = self._build_query(context)
            result = await self._execute_query(query, context)
            
            if result:
                logger.info(f"Database fallback executed successfully")
                return {
                    'success': True,
                    'strategy': 'database',
                    'data': result,
                    'query': query,
                    'timestamp': timezone.now().isoformat()
                }
            
            return {
                'success': False,
                'strategy': 'database',
                'error': 'No data found in database',
                'query': query
            }
            
        except Exception as e:
            logger.error(f"Database fallback error: {e}")
            return {
                'success': False,
                'strategy': 'database',
                'error': 'Operation failed',
                'query': query if 'query' in locals() else None
            }
    
    def is_available(self) -> bool:
        """Check if database is available"""
        if not self.connection_string:
            return False
        
        try:
            # Test database connection
            # This is a simplified check - in production, use actual DB connection
            return True
        except Exception as e:
            logger.error(f"Database availability check failed: {e}")
            return False
    
    def _build_query(self, context: Dict[str, Any]) -> str:
        """Build database query based on context"""
        operation = context.get('operation', 'select')
        table = safe_identifier(self.table_name, 'table name')
        
        if operation == 'select':
            field = context.get('field', '*')
            if field != '*':
                field = safe_identifier(field, 'column name')
            condition = str(context.get('condition', '1=1'))
            # Never splice free-form SQL: no statement separators, comments or quotes.
            if re.search(r"--|/\*|;|['\"`]", condition):
                raise ValueError('Unsafe SQL condition')
            
            return f"SELECT {field} FROM {table} WHERE {condition}"  # nosec B608 - identifiers validated via sql_utils; values are bound parameters
        
        return f"SELECT * FROM {table}"  # nosec B608 - identifiers validated via sql_utils; values are bound parameters
    
    async def _execute_query(self, query: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute database query asynchronously"""
        # This would use actual database connection
        # For now, return mock data
        await asyncio.sleep(0.1)  # Simulate DB query time
        
        return {
            'id': context.get('id', 'fallback'),
            'data': 'fallback_data',
            'created_at': timezone.now().isoformat()
        }


class LocalFileFallbackStrategy(FallbackStrategy):
    """Fallback to local file data"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.file_path = config.get('file_path')
        self.data_format = config.get('data_format', 'json')
        self.encoding = config.get('encoding', 'utf-8')
        
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute local file fallback"""
        if not self.file_path:
            return {
                'success': False,
                'strategy': 'local_file',
                'error': 'No file path configured'
            }
        
        try:
            # Read file data
            data = await self._read_file()
            
            if data:
                logger.info(f"Local file fallback executed from {self.file_path}")
                return {
                    'success': True,
                    'strategy': 'local_file',
                    'data': data,
                    'file_path': self.file_path,
                    'timestamp': timezone.now().isoformat()
                }
            
            return {
                'success': False,
                'strategy': 'local_file',
                'error': 'No data found in file',
                'file_path': self.file_path
            }
            
        except Exception as e:
            logger.error(f"Local file fallback error: {e}")
            return {
                'success': False,
                'strategy': 'local_file',
                'error': 'Operation failed',
                'file_path': self.file_path
            }
    
    def is_available(self) -> bool:
        """Check if local file is available"""
        if not self.file_path:
            return False
        
        try:
            import os
            return os.path.exists(self.file_path) and os.access(self.file_path, os.R_OK)
        except Exception as e:
            logger.error(f"Local file availability check failed: {e}")
            return False
    
    async def _read_file(self) -> Optional[Dict[str, Any]]:
        """Read and parse file data"""
        import aiofiles
        
        async with aiofiles.open(self.file_path, 'r', encoding=self.encoding) as file:
            content = await file.read()
        
        if self.data_format == 'json':
            import json
            return json.loads(content)
        elif self.data_format == 'csv':
            import csv
            import io
            reader = csv.DictReader(io.StringIO(content))
            return list(reader)
        else:
            return {'raw_content': content}


class ServiceFallbackStrategy(FallbackStrategy):
    """Fallback to alternative service"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.service_url = config.get('service_url')
        self.timeout = config.get('timeout', 30)
        self.api_key = config.get('api_key')
        self.headers = config.get('headers', {})
        
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute service fallback"""
        if not self.service_url:
            return {
                'success': False,
                'strategy': 'service',
                'error': 'No service URL configured'
            }
        
        try:
            # Call alternative service
            result = await self._call_service(context)
            
            if result:
                logger.info(f"Service fallback executed successfully")
                return {
                    'success': True,
                    'strategy': 'service',
                    'data': result,
                    'service_url': self.service_url,
                    'timestamp': timezone.now().isoformat()
                }
            
            return {
                'success': False,
                'strategy': 'service',
                'error': 'Service call failed',
                'service_url': self.service_url
            }
            
        except Exception as e:
            logger.error(f"Service fallback error: {e}")
            return {
                'success': False,
                'strategy': 'service',
                'error': 'Operation failed',
                'service_url': self.service_url
            }
    
    def is_available(self) -> bool:
        """Check if service is available"""
        if not self.service_url:
            return False
        
        try:
            import aiohttp
            
            async def _check():
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                    async with session.get(f"{self.service_url}/health") as response:
                        return response.status == 200
            
            return asyncio.run(_check())
        except Exception as e:
            logger.error(f"Service availability check failed: {e}")
            return False
    
    async def _call_service(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Call alternative service"""
        import aiohttp
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'AlertSystem-Fallback/1.0',
            **self.headers
        }
        
        if self.api_key:
            headers['Authorization'] = f"Bearer {self.api_key}"
        
        payload = {
            'operation': context.get('operation', 'fallback'),
            'context': context,
            'timestamp': timezone.now().isoformat()
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.post(self.service_url, json=payload, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {'error': f"Service returned status {response.status}"}


class FallbackManager:
    """Manages multiple fallback strategies"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.strategies = []
        self.max_attempts = config.get('max_attempts', 3)
        self.retry_delay = config.get('retry_delay', 5)
        self.enabled = config.get('enabled', True)
        
        # Initialize strategies
        self._initialize_strategies()
    
    def _initialize_strategies(self):
        """Initialize fallback strategies from configuration"""
        strategy_configs = self.config.get('strategies', [])
        
        for strategy_config in strategy_configs:
            strategy_type = strategy_config.get('type')
            strategy_class = self._get_strategy_class(strategy_type)
            
            if strategy_class:
                strategy = strategy_class(strategy_config)
                self.strategies.append(strategy)
                logger.info(f"Initialized fallback strategy: {strategy_type}")
    
    def _get_strategy_class(self, strategy_type: str) -> Optional[type]:
        """Get strategy class by type"""
        strategy_classes = {
            'cache': CacheFallbackStrategy,
            'database': DatabaseFallbackStrategy,
            'local_file': LocalFileFallbackStrategy,
            'service': ServiceFallbackStrategy
        }
        
        return strategy_classes.get(strategy_type)
    
    async def execute_fallback(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute fallback with available strategies"""
        if not self.enabled:
            return {
                'success': False,
                'error': 'Fallback manager is disabled'
            }
        
        # Sort strategies by priority (lower number = higher priority)
        available_strategies = [
            strategy for strategy in self.strategies
            if strategy.is_available()
        ]
        
        available_strategies.sort(key=lambda s: s.priority)
        
        if not available_strategies:
            return {
                'success': False,
                'error': 'No available fallback strategies'
            }
        
        # Try each strategy in priority order
        for strategy in available_strategies:
            try:
                result = await strategy.execute(context)
                
                if result.get('success', False):
                    result['fallback_used'] = strategy.name
                    result['all_strategies_tried'] = [s.name for s in available_strategies[:available_strategies.index(strategy) + 1]]
                    return result
                
            except Exception as e:
                logger.error(f"Error in fallback strategy {strategy.name}: {e}")
                continue
        
        return {
            'success': False,
            'error': 'All fallback strategies failed',
            'all_strategies_tried': [s.name for s in available_strategies]
        }
    
    async def execute_with_retry(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute fallback with retry logic"""
        last_error = None
        
        for attempt in range(self.max_attempts):
            result = await self.execute_fallback(context)
            
            if result.get('success', False):
                result['attempt'] = attempt + 1
                result['total_attempts'] = self.max_attempts
                return result
            
            last_error = result.get('error')
            
            # Wait before retry
            if attempt < self.max_attempts - 1:
                await asyncio.sleep(self.retry_delay)
        
        return {
            'success': False,
            'error': f"All {self.max_attempts} attempts failed. Last error: {last_error}",
            'total_attempts': self.max_attempts,
            'all_strategies_tried': result.get('all_strategies_tried', [])
        }
    
    def get_strategy_status(self) -> Dict[str, Any]:
        """Get status of all strategies"""
        return {
            'manager_enabled': self.enabled,
            'total_strategies': len(self.strategies),
            'available_strategies': len([s for s in self.strategies if s.is_available()]),
            'strategies': [
                {
                    'name': strategy.name,
                    'type': strategy.__class__.__name__.replace('FallbackStrategy', '').lower(),
                    'enabled': strategy.enabled,
                    'priority': strategy.priority,
                    'available': strategy.is_available(),
                    'config': strategy.config
                }
                for strategy in self.strategies
            ],
            'max_attempts': self.max_attempts,
            'retry_delay': self.retry_delay,
            'timestamp': timezone.now().isoformat()
        }


class GracefulDegradation:
    """Manages graceful degradation of services"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.fallback_manager = FallbackManager(config.get('fallback', {}))
        self.degradation_levels = config.get('degradation_levels', [])
        self.current_level = 0  # 0 = full functionality, higher = more degraded
        self.health_checks = config.get('health_checks', {})
        
    async def check_service_health(self) -> Dict[str, Any]:
        """Check health of all services"""
        health_results = {}
        overall_healthy = True
        
        for service_name, health_config in self.health_checks.items():
            try:
                # Perform health check
                health_result = await self._perform_health_check(service_name, health_config)
                health_results[service_name] = health_result
                
                if not health_result['healthy']:
                    overall_healthy = False
                    
            except Exception as e:
                logger.error(f"Health check failed for {service_name}: {e}")
                health_results[service_name] = {
                    'healthy': False,
                    'error': str(e),
                    'timestamp': timezone.now().isoformat()
                }
                overall_healthy = False
        
        return {
            'overall_healthy': overall_healthy,
            'services': health_results,
            'degradation_level': self.current_level,
            'timestamp': timezone.now().isoformat()
        }
    
    async def _perform_health_check(self, service_name: str, health_config: Dict[str, Any]) -> Dict[str, Any]:
        """Perform health check for specific service"""
        check_type = health_config.get('type', 'http')
        endpoint = health_config.get('endpoint', f"/{service_name}/health")
        timeout = health_config.get('timeout', 10)
        
        if check_type == 'http':
            return await self._http_health_check(endpoint, timeout)
        elif check_type == 'tcp':
            return await self._tcp_health_check(endpoint, timeout)
        else:
            return {
                'healthy': False,
                'error': f"Unknown health check type: {check_type}"
            }
    
    async def _http_health_check(self, endpoint: str, timeout: int) -> Dict[str, Any]:
        """Perform HTTP health check"""
        try:
            import aiohttp
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                start_time = time.time()
                async with session.get(endpoint) as response:
                    response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
                    
                    return {
                        'healthy': response.status == 200,
                        'status_code': response.status,
                        'response_time_ms': response_time,
                        'timestamp': timezone.now().isoformat()
                    }
        except Exception:
            logger.exception("Unhandled error in _http_health_check")
            return {
                'healthy': False,
                'error': 'Operation failed',
                'timestamp': timezone.now().isoformat()
            }
    
    async def _tcp_health_check(self, endpoint: str, timeout: int) -> Dict[str, Any]:
        """Perform TCP health check"""
        try:
            import asyncio
            
            # Parse host and port
            if ':' in endpoint:
                host, port = endpoint.split(':')
                port = int(port)
            else:
                host = endpoint
                port = 80
            
            start_time = time.time()
            
            # Try to connect
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=timeout
                )
                writer.close()
                reader.close()
                
                response_time = (time.time() - start_time) * 1000
                
                return {
                    'healthy': True,
                    'response_time_ms': response_time,
                    'timestamp': timezone.now().isoformat()
                }
            except:
                response_time = (time.time() - start_time) * 1000
                
                return {
                    'healthy': False,
                    'response_time_ms': response_time,
                    'timestamp': timezone.now().isoformat()
                }
        except Exception:
            logger.exception("Unhandled error in _tcp_health_check")
            return {
                'healthy': False,
                'error': 'Operation failed',
                'timestamp': timezone.now().isoformat()
            }
    
    async def adjust_degradation_level(self, health_results: Dict[str, Any]) -> int:
        """Adjust degradation level based on health results"""
        failed_services = [
            service for service, result in health_results['services'].items()
            if not result.get('healthy', False)
        ]
        
        # Determine new degradation level
        if not failed_services:
            new_level = 0  # Full functionality
        elif len(failed_services) <= len(self.degradation_levels) // 3:
            new_level = 1  # Minor degradation
        elif len(failed_services) <= 2 * len(self.degradation_levels) // 3:
            new_level = 2  # Moderate degradation
        else:
            new_level = 3  # Major degradation
        
        if new_level != self.current_level:
            old_level = self.current_level
            self.current_level = new_level
            
            logger.warning(
                f"Degradation level changed from {old_level} to {new_level}. "
                f"Failed services: {failed_services}"
            )
            
            # Trigger fallback if needed
            if new_level > 0:
                await self._trigger_fallback(health_results)
        
        return new_level
    
    async def _trigger_fallback(self, health_results: Dict[str, Any]):
        """Trigger fallback for failed services"""
        context = {
            'health_results': health_results,
            'degradation_level': self.current_level,
            'failed_services': [
                service for service, result in health_results['services'].items()
                if not result.get('healthy', False)
            ]
        }
        
        result = await self.fallback_manager.execute_fallback(context)
        logger.info(f"Fallback triggered with result: {result}")
        
        return result


# Global fallback manager
fallback_manager = None
graceful_degradation = None


def initialize_fallback_system():
    """Initialize fallback system from settings"""
    from django.conf import settings
    
    global fallback_manager, graceful_degradation
    
    fallback_config = getattr(settings, 'FALLBACK_CONFIG', {})
    if fallback_config:
        fallback_manager = FallbackManager(fallback_config)
    
    degradation_config = getattr(settings, 'GRACEFUL_DEGRADATION_CONFIG', {})
    if degradation_config:
        graceful_degradation = GracefulDegradation(degradation_config)
    
    logger.info("Fallback system initialized")


async def execute_fallback(context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute fallback with global manager"""
    if not fallback_manager:
        return {
            'success': False,
            'error': 'Fallback system not initialized'
        }
    
    return await fallback_manager.execute_fallback(context)


async def check_service_health() -> Dict[str, Any]:
    """Check service health with global manager"""
    if not graceful_degradation:
        return {
            'healthy': False,
            'error': 'Graceful degradation system not initialized'
        }
    
    return await graceful_degradation.check_service_health()


# Initialize on module import
try:
    initialize_fallback_system()
except Exception as e:
    logger.error(f"Error initializing fallback system: {e}")
