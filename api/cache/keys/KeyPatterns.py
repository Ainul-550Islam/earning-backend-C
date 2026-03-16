from typing import Dict, List, Pattern
import re

class KeyPatterns:
    """
    Centralized cache key patterns for Earnify application
    Provides pattern matching and validation
    """
    
    # Pattern definitions
    PATTERNS = {
        # User patterns
        'USER_PROFILE': r'^user:\d+:profile$',
        'USER_STATS': r'^user:\d+:stats$',
        'USER_BALANCE': r'^user:\d+:balance$',
        'USER_TASKS': r'^user:\d+:tasks(:\w+)?$',
        'USER_OFFERS': r'^user:\d+:offers(:\w+)?$',
        'USER_TRANSACTIONS': r'^user:\d+:transactions(:\w+)?$',
        'USER_WITHDRAWALS': r'^user:\d+:withdrawals(:\w+)?$',
        'USER_REFERRALS': r'^user:\d+:referrals(:\w+)?$',
        
        # Task patterns
        'TASK_DETAIL': r'^task:\d+:detail$',
        'TASK_LIST': r'^tasks:list:\d+:\d+:\w+$',
        'TASK_STATS': r'^tasks:stats:\d{4}-\d{2}-\d{2}$',
        
        # Offer patterns
        'OFFER_DETAIL': r'^offer:\d+:detail$',
        'OFFER_LIST': r'^offers:list:\w+:\d+:\d+$',
        'OFFER_ACTIVE': r'^offers:active:\d+$',
        'OFFER_STATS': r'^offers:stats:\d{4}-\d{2}-\d{2}$',
        
        # Transaction patterns
        'TRANSACTION_DETAIL': r'^transaction:\d+:detail$',
        'TRANSACTION_RECENT': r'^transactions:recent:\d+:\d+$',
        
        # Withdrawal patterns
        'WITHDRAWAL_DETAIL': r'^withdrawal:\d+:detail$',
        'WITHDRAWAL_PENDING': r'^withdrawals:pending:\w+$',
        
        # Referral patterns
        'REFERRAL_STATS': r'^referrals:stats:\d+$',
        'REFERRAL_LIST': r'^referrals:list:\d+:\d+$',
        
        # Leaderboard patterns
        'LEADERBOARD_DAILY': r'^leaderboard:daily:\d{4}-\d{2}-\d{2}$',
        'LEADERBOARD_WEEKLY': r'^leaderboard:weekly:\d{4}-W\d{2}$',
        'LEADERBOARD_MONTHLY': r'^leaderboard:monthly:\d{4}-\d{2}$',
        'LEADERBOARD_ALL_TIME': r'^leaderboard:all_time$',
        
        # System patterns
        'SYSTEM_STATS': r'^system:stats$',
        'SYSTEM_HEALTH': r'^system:health$',
        
        # Cache management patterns
        'CACHE_VERSION': r'^cache:version:.+$',
        
        # Wildcard patterns for invalidation
        'ALL_USER_KEYS': r'^user:\d+:.+$',
        'ALL_TASK_KEYS': r'^task:\d+:.+$',
        'ALL_OFFER_KEYS': r'^offer:\d+:.+$',
        'ALL_TRANSACTION_KEYS': r'^transaction:\d+:.+$',
        'ALL_WITHDRAWAL_KEYS': r'^withdrawal:\d+:.+$',
        
        # List patterns
        'ALL_LISTS': r'^.+:list:.+$',
        'ALL_STATS': r'^.+:stats:.+$',
    }
    
    # Compiled regex patterns
    _compiled_patterns = {}
    
    def __init__(self):
        # Compile all patterns
        for name, pattern in self.PATTERNS.items():
            self._compiled_patterns[name] = re.compile(pattern)
    
    def match(self, key: str, pattern_name: str) -> bool:
        """Check if key matches pattern"""
        if pattern_name not in self._compiled_patterns:
            raise ValueError(f"Unknown pattern: {pattern_name}")
        
        return bool(self._compiled_patterns[pattern_name].match(key))
    
    def find_matching_patterns(self, key: str) -> List[str]:
        """Find all patterns that match the key"""
        matches = []
        for name, pattern in self._compiled_patterns.items():
            if pattern.match(key):
                matches.append(name)
        return matches
    
    def extract_parameters(self, key: str, pattern_name: str) -> Dict[str, str]:
        """Extract parameters from key using pattern"""
        if pattern_name not in self.PATTERNS:
            raise ValueError(f"Unknown pattern: {pattern_name}")
        
        # Convert pattern to named group pattern
        pattern = self.PATTERNS[pattern_name]
        
        # Replace simple patterns with named groups
        pattern = pattern.replace(r'\d+', r'(?P<id>\d+)')
        pattern = pattern.replace(r'\w+', r'(?P<name>\w+)')
        pattern = pattern.replace(r'\d{4}-\d{2}-\d{2}', r'(?P<date>\d{4}-\d{2}-\d{2})')
        pattern = pattern.replace(r'\d{4}-W\d{2}', r'(?P<week>\d{4}-W\d{2})')
        pattern = pattern.replace(r'\d{4}-\d{2}', r'(?P<month>\d{4}-\d{2})')
        
        # Match and extract
        match = re.match(pattern, key)
        if match:
            return match.groupdict()
        return {}
    
    def generate_pattern(self, key_template: str) -> str:
        """Generate regex pattern from key template"""
        # Escape regex special characters
        pattern = re.escape(key_template)
        
        # Replace placeholders with appropriate patterns
        pattern = pattern.replace(r'\{user_id\}', r'\d+')
        pattern = pattern.replace(r'\{task_id\}', r'\d+')
        pattern = pattern.replace(r'\{offer_id\}', r'\d+')
        pattern = pattern.replace(r'\{transaction_id\}', r'\d+')
        pattern = pattern.replace(r'\{withdrawal_id\}', r'\d+')
        pattern = pattern.replace(r'\{referral_id\}', r'\d+')
        pattern = pattern.replace(r'\{page\}', r'\d+')
        pattern = pattern.replace(r'\{limit\}', r'\d+')
        pattern = pattern.replace(r'\{date\}', r'\d{4}-\d{2}-\d{2}')
        pattern = pattern.replace(r'\{week\}', r'\d{4}-W\d{2}')
        pattern = pattern.replace(r'\{month\}', r'\d{4}-\d{2}')
        pattern = pattern.replace(r'\{category\}', r'\w+')
        pattern = pattern.replace(r'\{status\}', r'\w+')
        
        return f'^{pattern}$'
    
    def validate_key(self, key: str) -> bool:
        """Validate cache key format"""
        # Basic validation
        if not key or len(key) > 250:
            return False
        
        # Check for invalid characters
        if re.search(r'[^\w:\-\{\}]', key):
            return False
        
        return True
    
    def get_keys_by_pattern(self, pattern_name: str) -> List[str]:
        """Get all keys matching pattern from cache"""
        if pattern_name not in self.PATTERNS:
            raise ValueError(f"Unknown pattern: {pattern_name}")
        
        # Get cache service
        from api.cache.manager import cache_manager
        cache_service = cache_manager.get_cache("default")
        
        # Get all keys (note: this might be expensive for large caches)
        all_keys = cache_service.keys("*")
        
        # Filter keys matching pattern
        pattern = self._compiled_patterns[pattern_name]
        matching_keys = [key for key in all_keys if pattern.match(key)]
        
        return matching_keys
    
    def invalidate_by_pattern(self, pattern_name: str) -> int:
        """Invalidate all keys matching pattern"""
        keys = self.get_keys_by_pattern(pattern_name)
        
        if keys:
            from api.cache.manager import cache_manager
            cache_service = cache_manager.get_cache("default")
            return cache_service.delete_many(keys)
        
        return 0
    
    # Convenience methods for common patterns
    def invalidate_user_keys(self, user_id: int) -> int:
        """Invalidate all cache keys for a user"""
        pattern = f"user:{user_id}:*"
        
        from api.cache.manager import cache_manager
        cache_service = cache_manager.get_cache("default")
        
        keys = cache_service.keys(pattern)
        if keys:
            return cache_service.delete_many(keys)
        
        return 0
    
    def invalidate_task_keys(self, task_id: int) -> int:
        """Invalidate all cache keys for a task"""
        pattern = f"task:{task_id}:*"
        
        from api.cache.manager import cache_manager
        cache_service = cache_manager.get_cache("default")
        
        keys = cache_service.keys(pattern)
        if keys:
            return cache_service.delete_many(keys)
        
        return 0
    
    def invalidate_offer_keys(self, offer_id: int) -> int:
        """Invalidate all cache keys for an offer"""
        pattern = f"offer:{offer_id}:*"
        
        from api.cache.manager import cache_manager
        cache_service = cache_manager.get_cache("default")
        
        keys = cache_service.keys(pattern)
        if keys:
            return cache_service.delete_many(keys)
        
        return 0
    
    def invalidate_all_lists(self) -> int:
        """Invalidate all list cache keys"""
        return self.invalidate_by_pattern('ALL_LISTS')
    
    def invalidate_all_stats(self) -> int:
        """Invalidate all stats cache keys"""
        return self.invalidate_by_pattern('ALL_STATS')

# Global instance
key_patterns = KeyPatterns()