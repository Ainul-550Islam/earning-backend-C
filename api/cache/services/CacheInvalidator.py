import re
import time
from typing import List, Dict, Any, Optional, Callable, Union
from datetime import datetime, timedelta
import asyncio
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class CacheInvalidationStrategy(ABC):
    """Base class for cache invalidation strategies"""
    
    @abstractmethod
    def should_invalidate(self, key: str, operation: str, **kwargs) -> bool:
        """Determine if cache should be invalidated"""
        pass
    
    @abstractmethod
    def get_invalidation_keys(self, key: str, operation: str, **kwargs) -> List[str]:
        """Get list of keys to invalidate"""
        pass

class PatternBasedInvalidation(CacheInvalidationStrategy):
    """Invalidate keys based on patterns"""
    
    def __init__(self, patterns: Dict[str, List[str]]):
        """
        Args:
            patterns: Dict mapping operations to key patterns
                Example: {'user_update': ['user:{user_id}:*', 'users:list:*']}
        """
        self.patterns = patterns
        self.compiled_patterns = {}
        
        # Compile regex patterns
        for operation, pattern_list in patterns.items():
            compiled = []
            for pattern in pattern_list:
                # Convert wildcard patterns to regex
                regex_pattern = pattern.replace('*', '.*').replace('?', '.')
                compiled.append(re.compile(f'^{regex_pattern}$'))
            self.compiled_patterns[operation] = compiled
    
    def should_invalidate(self, key: str, operation: str, **kwargs) -> bool:
        """Check if operation requires invalidation for this key"""
        if operation not in self.compiled_patterns:
            return False
        
        for pattern in self.compiled_patterns[operation]:
            if pattern.match(key):
                return True
        
        return False
    
    def get_invalidation_keys(self, key: str, operation: str, **kwargs) -> List[str]:
        """Get keys to invalidate for this operation"""
        if operation not in self.patterns:
            return []
        
        # For pattern-based, we need to match existing keys
        # This is handled by CacheInvalidator
        return []

class DependencyBasedInvalidation(CacheInvalidationStrategy):
    """Invalidate keys based on dependencies"""
    
    def __init__(self):
        self.dependencies = {}  # key -> List[dependent_keys]
    
    def add_dependency(self, base_key: str, dependent_key: str):
        """Add dependency relationship"""
        if base_key not in self.dependencies:
            self.dependencies[base_key] = []
        
        if dependent_key not in self.dependencies[base_key]:
            self.dependencies[base_key].append(dependent_key)
    
    def remove_dependency(self, base_key: str, dependent_key: str):
        """Remove dependency relationship"""
        if base_key in self.dependencies:
            if dependent_key in self.dependencies[base_key]:
                self.dependencies[base_key].remove(dependent_key)
    
    def should_invalidate(self, key: str, operation: str, **kwargs) -> bool:
        """Always invalidate dependencies when base key changes"""
        return True
    
    def get_invalidation_keys(self, key: str, operation: str, **kwargs) -> List[str]:
        """Get all dependent keys to invalidate"""
        invalidate_keys = [key]
        
        # Recursively get all dependencies
        visited = set()
        stack = [key]
        
        while stack:
            current_key = stack.pop()
            if current_key in visited:
                continue
            
            visited.add(current_key)
            
            if current_key in self.dependencies:
                for dep_key in self.dependencies[current_key]:
                    if dep_key not in visited:
                        invalidate_keys.append(dep_key)
                        stack.append(dep_key)
        
        return invalidate_keys

class TimeBasedInvalidation(CacheInvalidationStrategy):
    """Invalidate keys based on time"""
    
    def __init__(self, ttl_map: Dict[str, int]):
        """
        Args:
            ttl_map: Dict mapping key patterns to TTL in seconds
        """
        self.ttl_map = ttl_map
        self.last_invalidated = {}
    
    def should_invalidate(self, key: str, operation: str, **kwargs) -> bool:
        """Check if key has expired based on TTL"""
        for pattern, ttl in self.ttl_map.items():
            if re.match(pattern.replace('*', '.*'), key):
                if key not in self.last_invalidated:
                    return True
                
                elapsed = time.time() - self.last_invalidated[key]
                return elapsed >= ttl
        
        return False
    
    def get_invalidation_keys(self, key: str, operation: str, **kwargs) -> List[str]:
        """Get keys that need time-based invalidation"""
        invalidate_keys = []
        
        for pattern in self.ttl_map:
            if re.match(pattern.replace('*', '.*'), key):
                invalidate_keys.append(key)
                self.last_invalidated[key] = time.time()
                break
        
        return invalidate_keys

class CacheInvalidator:
    """
    Main cache invalidation service
    Supports multiple invalidation strategies
    """
    
    def __init__(self, cache_service, strategies: List[CacheInvalidationStrategy] = None):
        """
        Args:
            cache_service: Instance of CacheService
            strategies: List of invalidation strategies
        """
        self.cache_service = cache_service
        self.strategies = strategies or []
        
        # Default strategies
        if not self.strategies:
            self.strategies = [
                PatternBasedInvalidation(self._get_default_patterns()),
                DependencyBasedInvalidation(),
                TimeBasedInvalidation(self._get_default_ttl_map())
            ]
        
        # Invalidation queue for async processing
        self.invalidation_queue = asyncio.Queue()
        self.is_processing = False
    
    def _get_default_patterns(self) -> Dict[str, List[str]]:
        """Get default invalidation patterns"""
        return {
            'user_create': ['users:list:*', 'stats:users:*'],
            'user_update': ['user:{user_id}:*', 'users:list:*'],
            'user_delete': ['user:{user_id}:*', 'users:list:*', 'stats:users:*'],
            
            'task_create': ['tasks:list:*', 'user:{user_id}:tasks:*', 'stats:tasks:*'],
            'task_update': ['task:{task_id}:*', 'tasks:list:*', 'user:{user_id}:tasks:*'],
            'task_delete': ['task:{task_id}:*', 'tasks:list:*', 'user:{user_id}:tasks:*', 'stats:tasks:*'],
            
            'offer_create': ['offers:list:*', 'offers:active:*', 'stats:offers:*'],
            'offer_update': ['offer:{offer_id}:*', 'offers:list:*', 'offers:active:*'],
            'offer_delete': ['offer:{offer_id}:*', 'offers:list:*', 'offers:active:*', 'stats:offers:*'],
            
            'transaction_create': ['user:{user_id}:transactions:*', 'transactions:recent:*', 'stats:transactions:*'],
            'withdrawal_create': ['user:{user_id}:withdrawals:*', 'withdrawals:pending:*', 'stats:withdrawals:*'],
            'withdrawal_update': ['withdrawal:{withdrawal_id}:*', 'user:{user_id}:withdrawals:*', 'withdrawals:*'],
            
            'wallet_update': ['user:{user_id}:wallet:*', 'user:{user_id}:balance'],
            
            'referral_create': ['user:{user_id}:referrals:*', 'stats:referrals:*'],
            'referral_update': ['referral:{referral_id}:*', 'user:{user_id}:referrals:*']
        }
    
    def _get_default_ttl_map(self) -> Dict[str, int]:
        """Get default TTL map for time-based invalidation"""
        return {
            'users:list:*': 300,  # 5 minutes
            'tasks:list:*': 60,   # 1 minute
            'offers:list:*': 300, # 5 minutes
            'offers:active:*': 60,
            'transactions:recent:*': 30,
            'withdrawals:pending:*': 30,
            'stats:*': 300,
            'leaderboard:*': 60
        }
    
    def register_strategy(self, strategy: CacheInvalidationStrategy):
        """Register new invalidation strategy"""
        self.strategies.append(strategy)
    
    def invalidate(self, key: str, operation: str, **kwargs) -> int:
        """
        Invalidate cache for a key/operation
        Returns number of keys invalidated
        """
        invalidate_keys = set()
        
        # Collect keys to invalidate from all strategies
        for strategy in self.strategies:
            if strategy.should_invalidate(key, operation, **kwargs):
                keys = strategy.get_invalidation_keys(key, operation, **kwargs)
                invalidate_keys.update(keys)
        
        # Also get pattern-based matches from cache
        pattern_keys = self._get_pattern_matches(key, operation)
        invalidate_keys.update(pattern_keys)
        
        # Perform invalidation
        deleted_count = 0
        if invalidate_keys:
            deleted_count = self.cache_service.delete_many(list(invalidate_keys))
            logger.info(f"Invalidated {deleted_count} keys for operation '{operation}' on key '{key}'")
        
        return deleted_count
    
    def invalidate_async(self, key: str, operation: str, **kwargs):
        """Queue invalidation for async processing"""
        asyncio.create_task(self._process_invalidation(key, operation, **kwargs))
    
    async def _process_invalidation(self, key: str, operation: str, **kwargs):
        """Process invalidation asynchronously"""
        await self.invalidation_queue.put((key, operation, kwargs))
        
        if not self.is_processing:
            self.is_processing = True
            await self._process_queue()
    
    async def _process_queue(self):
        """Process invalidation queue"""
        while not self.invalidation_queue.empty():
            try:
                key, operation, kwargs = await self.invalidation_queue.get()
                self.invalidate(key, operation, **kwargs)
                self.invalidation_queue.task_done()
            except Exception as e:
                logger.error(f"Error processing invalidation: {str(e)}")
        
        self.is_processing = False
    
    def _get_pattern_matches(self, key: str, operation: str) -> List[str]:
        """Get keys matching invalidation patterns"""
        if not isinstance(self.strategies[0], PatternBasedInvalidation):
            return []
        
        pattern_strategy = self.strategies[0]
        if operation not in pattern_strategy.patterns:
            return []
        
        # Extract parameters from key for pattern substitution
        # Example: key="user:123:profile", pattern="user:{user_id}:*"
        key_parts = key.split(':')
        matches = []
        
        for pattern in pattern_strategy.patterns[operation]:
            # Replace placeholders with actual values
            if '{' in pattern:
                # Simple substitution (for basic cases)
                # In production, use a more robust template system
                substituted = pattern
                for i, part in enumerate(key_parts):
                    substituted = substituted.replace(f'{{{i}}}', part)
                
                # Get keys matching the substituted pattern
                cache_keys = self.cache_service.keys(substituted.replace('{', '').replace('}', ''))
                matches.extend(cache_keys or [])
            else:
                # Direct pattern match
                cache_keys = self.cache_service.keys(pattern)
                matches.extend(cache_keys or [])
        
        return list(set(matches))
    
    def add_dependency(self, base_key: str, dependent_key: str):
        """Add dependency between cache keys"""
        for strategy in self.strategies:
            if isinstance(strategy, DependencyBasedInvalidation):
                strategy.add_dependency(base_key, dependent_key)
                logger.debug(f"Added dependency: {base_key} -> {dependent_key}")
                break
    
    def remove_dependency(self, base_key: str, dependent_key: str):
        """Remove dependency between cache keys"""
        for strategy in self.strategies:
            if isinstance(strategy, DependencyBasedInvalidation):
                strategy.remove_dependency(base_key, dependent_key)
                logger.debug(f"Removed dependency: {base_key} -> {dependent_key}")
                break
    
    def bulk_invalidate(self, operations: List[Dict[str, Any]]):
        """Bulk invalidate multiple operations"""
        total_deleted = 0
        
        for op in operations:
            key = op.get('key')
            operation = op.get('operation')
            kwargs = op.get('kwargs', {})
            
            if key and operation:
                deleted = self.invalidate(key, operation, **kwargs)
                total_deleted += deleted
        
        logger.info(f"Bulk invalidation completed: {total_deleted} keys deleted")
        return total_deleted
    
    def schedule_invalidation(self, key: str, operation: str, delay_seconds: int, **kwargs):
        """Schedule invalidation after delay"""
        import threading
        
        def delayed_invalidate():
            time.sleep(delay_seconds)
            self.invalidate(key, operation, **kwargs)
        
        thread = threading.Thread(target=delayed_invalidate, daemon=True)
        thread.start()
        logger.debug(f"Scheduled invalidation for '{key}' after {delay_seconds} seconds")
    
    def get_invalidation_stats(self) -> Dict[str, Any]:
        """Get invalidation statistics"""
        stats = {
            'timestamp': datetime.utcnow().isoformat(),
            'strategies': [str(s.__class__.__name__) for s in self.strategies],
            'queue_size': self.invalidation_queue.qsize() if hasattr(self.invalidation_queue, 'qsize') else 0
        }
        
        # Get stats from each strategy
        for strategy in self.strategies:
            if isinstance(strategy, DependencyBasedInvalidation):
                stats['dependency_count'] = sum(len(deps) for deps in strategy.dependencies.values())
            elif isinstance(strategy, TimeBasedInvalidation):
                stats['ttl_entries'] = len(strategy.ttl_map)
                stats['last_invalidated_count'] = len(strategy.last_invalidated)
        
        return stats
    
    def clear_all(self) -> int:
        """Clear all cache (use with caution!)"""
        all_keys = self.cache_service.keys("*")
        deleted = self.cache_service.delete_many(all_keys)
        logger.warning(f"Cleared all cache: {deleted} keys deleted")
        return deleted

# Factory function
def create_cache_invalidator(cache_service, strategy_config: Dict[str, Any] = None):
    """Factory function to create cache invalidator"""
    strategies = []
    
    if strategy_config:
        if 'patterns' in strategy_config:
            strategies.append(PatternBasedInvalidation(strategy_config['patterns']))
        
        if 'ttl_map' in strategy_config:
            strategies.append(TimeBasedInvalidation(strategy_config['ttl_map']))
    
    # Always include dependency-based strategy
    strategies.append(DependencyBasedInvalidation())
    
    return CacheInvalidator(cache_service, strategies)