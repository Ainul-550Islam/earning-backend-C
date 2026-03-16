import hashlib
import json
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime, date
import inspect
import functools

class CacheKeyGenerator:
    """
    Advanced cache key generator
    Supports templates, hashing, and namespacing
    """
    
    def __init__(self, namespace: str = "earnify"):
        """
        Args:
            namespace: Global namespace for all keys
        """
        self.namespace = namespace
        self.separator = ":"
        self.key_templates = self._get_default_templates()
    
    def _get_default_templates(self) -> Dict[str, str]:
        """Get default key templates for Earnify app"""
        return {
            # User related
            'user_profile': 'user:{user_id}:profile',
            'user_stats': 'user:{user_id}:stats',
            'user_balance': 'user:{user_id}:balance',
            'user_tasks': 'user:{user_id}:tasks',
            'user_offers': 'user:{user_id}:offers',
            'user_transactions': 'user:{user_id}:transactions',
            'user_withdrawals': 'user:{user_id}:withdrawals',
            'user_referrals': 'user:{user_id}:referrals',
            
            # Task related
            'task_detail': 'task:{task_id}:detail',
            'task_list': 'tasks:list:{page}:{limit}:{status}',
            'task_stats': 'tasks:stats:{date}',
            
            # Offer related
            'offer_detail': 'offer:{offer_id}:detail',
            'offer_list': 'offers:list:{category}:{page}:{limit}',
            'offer_active': 'offers:active:{user_id}',
            'offer_stats': 'offers:stats:{date}',
            
            # Transaction related
            'transaction_detail': 'transaction:{transaction_id}:detail',
            'transaction_recent': 'transactions:recent:{user_id}:{limit}',
            
            # Withdrawal related
            'withdrawal_detail': 'withdrawal:{withdrawal_id}:detail',
            'withdrawal_pending': 'withdrawals:pending:{status}',
            
            # Referral related
            'referral_stats': 'referrals:stats:{user_id}',
            'referral_list': 'referrals:list:{user_id}:{page}',
            
            # Leaderboard
            'leaderboard_daily': 'leaderboard:daily:{date}',
            'leaderboard_weekly': 'leaderboard:weekly:{week}',
            'leaderboard_monthly': 'leaderboard:monthly:{month}',
            'leaderboard_all_time': 'leaderboard:all_time',
            
            # System stats
            'system_stats': 'system:stats',
            'system_health': 'system:health',
            
            # Cache version
            'cache_version': 'cache:version:{key}',
        }
    
    def generate(
        self,
        template_name: str,
        **kwargs
    ) -> str:
        """
        Generate cache key from template
        
        Args:
            template_name: Name of template to use
            **kwargs: Values to substitute in template
        
        Returns:
            Generated cache key
        """
        if template_name not in self.key_templates:
            raise ValueError(f"Unknown template: {template_name}")
        
        template = self.key_templates[template_name]
        
        # Substitute placeholders
        key = template
        for key_name, value in kwargs.items():
            placeholder = f"{{{key_name}}}"
            if placeholder in key:
                key = key.replace(placeholder, self._format_value(value))
        
        # Add namespace
        if self.namespace:
            key = f"{self.namespace}{self.separator}{key}"
        
        return key
    
    def generate_function_key(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        prefix: str = "",
        version: int = 1
    ) -> str:
        """
        Generate cache key for function call
        
        Args:
            func: Function object
            args: Function arguments
            kwargs: Function keyword arguments
            prefix: Optional prefix
            version: Cache version
        
        Returns:
            Generated cache key
        """
        key_parts = []
        
        # Add prefix if provided
        if prefix:
            key_parts.append(prefix)
        else:
            # Use function info
            key_parts.append(func.__module__.replace('.', ':'))
            key_parts.append(func.__name__)
        
        # Add version
        key_parts.append(f"v{version}")
        
        # Get function signature
        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        
        # Add arguments
        for param_name, param_value in bound_args.arguments.items():
            # Skip self for instance methods
            if param_name == 'self':
                continue
            
            # Format value
            formatted = self._format_value(param_value)
            key_parts.append(f"{param_name}:{formatted}")
        
        # Join parts
        key = self.separator.join(key_parts)
        
        # Add namespace
        if self.namespace:
            key = f"{self.namespace}{self.separator}{key}"
        
        return key
    
    def generate_model_key(
        self,
        model_class,
        instance_id: Any,
        fields: List[str] = None,
        related: List[str] = None
    ) -> str:
        """
        Generate cache key for model instance
        
        Args:
            model_class: Django/ORM model class
            instance_id: Model instance ID
            fields: Specific fields to cache
            related: Related objects to include
        
        Returns:
            Generated cache key
        """
        key_parts = [
            "model",
            model_class.__name__.lower(),
            str(instance_id)
        ]
        
        if fields:
            key_parts.append(f"fields:{','.join(sorted(fields))}")
        
        if related:
            key_parts.append(f"related:{','.join(sorted(related))}")
        
        key = self.separator.join(key_parts)
        
        # Add namespace
        if self.namespace:
            key = f"{self.namespace}{self.separator}{key}"
        
        return key
    
    def generate_query_key(
        self,
        model_class,
        filters: Dict[str, Any] = None,
        ordering: List[str] = None,
        limit: int = None,
        offset: int = None
    ) -> str:
        """
        Generate cache key for database query
        
        Args:
            model_class: Django/ORM model class
            filters: Query filters
            ordering: Ordering fields
            limit: Query limit
            offset: Query offset
        
        Returns:
            Generated cache key
        """
        key_parts = [
            "query",
            model_class.__name__.lower()
        ]
        
        # Add filters
        if filters:
            filter_parts = []
            for key, value in sorted(filters.items()):
                filter_parts.append(f"{key}:{self._format_value(value)}")
            key_parts.append(f"filters:{','.join(filter_parts)}")
        
        # Add ordering
        if ordering:
            key_parts.append(f"order:{','.join(ordering)}")
        
        # Add pagination
        if limit is not None:
            key_parts.append(f"limit:{limit}")
        
        if offset is not None:
            key_parts.append(f"offset:{offset}")
        
        key = self.separator.join(key_parts)
        
        # Add namespace
        if self.namespace:
            key = f"{self.namespace}{self.separator}{key}"
        
        return key
    
    def generate_api_key(
        self,
        endpoint: str,
        params: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        user_id: Optional[int] = None
    ) -> str:
        """
        Generate cache key for API endpoint
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            headers: Request headers
            user_id: User ID for user-specific caching
        
        Returns:
            Generated cache key
        """
        key_parts = ["api", endpoint.replace('/', ':')]
        
        # Add user ID if provided
        if user_id:
            key_parts.append(f"user:{user_id}")
        
        # Add parameters
        if params:
            param_parts = []
            for key, value in sorted(params.items()):
                param_parts.append(f"{key}:{self._format_value(value)}")
            key_parts.append(f"params:{','.join(param_parts)}")
        
        # Add headers (careful with sensitive data!)
        if headers:
            # Only include safe headers
            safe_headers = ['Accept', 'Accept-Language', 'Content-Type']
            header_parts = []
            for key, value in headers.items():
                if key in safe_headers:
                    header_parts.append(f"{key}:{value[:20]}")
            if header_parts:
                key_parts.append(f"headers:{','.join(header_parts)}")
        
        key = self.separator.join(key_parts)
        
        # Add namespace
        if self.namespace:
            key = f"{self.namespace}{self.separator}{key}"
        
        return key
    
    def generate_versioned_key(
        self,
        base_key: str,
        version: int = 1
    ) -> str:
        """
        Generate versioned cache key
        
        Args:
            base_key: Base cache key
            version: Version number
        
        Returns:
            Versioned cache key
        """
        version_key = f"{base_key}:v{version}"
        
        # Check if version exists in cache
        from api.cache.manager import cache_manager
        cache_service = cache_manager.get_cache("default")
        
        actual_version = cache_service.get(f"cache:version:{base_key}")
        if actual_version is None:
            # Set initial version
            cache_service.set(f"cache:version:{base_key}", version)
            actual_version = version
        
        # Use actual version
        return f"{base_key}:v{actual_version}"
    
    def increment_version(self, base_key: str) -> int:
        """
        Increment version for cache key
        
        Args:
            base_key: Base cache key
        
        Returns:
            New version number
        """
        version_key = f"cache:version:{base_key}"
        
        from api.cache.manager import cache_manager
        cache_service = cache_manager.get_cache("default")
        
        current_version = cache_service.get(version_key) or 1
        new_version = current_version + 1
        
        cache_service.set(version_key, new_version)
        
        # Invalidate old versioned keys
        old_key = f"{base_key}:v{current_version}"
        cache_service.delete(old_key)
        
        return new_version
    
    def add_template(self, name: str, template: str):
        """Add new key template"""
        self.key_templates[name] = template
    
    def remove_template(self, name: str):
        """Remove key template"""
        if name in self.key_templates:
            del self.key_templates[name]
    
    def get_template(self, name: str) -> Optional[str]:
        """Get key template by name"""
        return self.key_templates.get(name)
    
    def list_templates(self) -> List[str]:
        """List all available templates"""
        return list(self.key_templates.keys())
    
    def _format_value(self, value: Any) -> str:
        """Format value for cache key"""
        if value is None:
            return "null"
        elif isinstance(value, (int, float, bool)):
            return str(value)
        elif isinstance(value, str):
            # Truncate long strings
            if len(value) > 50:
                return hashlib.md5(value.encode()).hexdigest()[:12]
            return value.replace(':', '_').replace(' ', '_')
        elif isinstance(value, (datetime, date)):
            return value.isoformat().replace(':', '_')
        elif isinstance(value, (list, tuple, set)):
            # Hash collections
            return hashlib.md5(json.dumps(list(value), sort_keys=True).encode()).hexdigest()[:12]
        elif isinstance(value, dict):
            # Hash dictionaries
            return hashlib.md5(json.dumps(value, sort_keys=True).encode()).hexdigest()[:12]
        else:
            # Hash any other object
            return hashlib.md5(str(value).encode()).hexdigest()[:12]

# Global instance
cache_key_generator = CacheKeyGenerator()

# Helper functions
def generate_key(template_name: str, **kwargs) -> str:
    """Shortcut to generate key from template"""
    return cache_key_generator.generate(template_name, **kwargs)

def generate_function_key(func: Callable, *args, **kwargs) -> str:
    """Shortcut to generate key for function"""
    return cache_key_generator.generate_function_key(func, args, kwargs)

def increment_version(base_key: str) -> int:
    """Shortcut to increment cache version"""
    return cache_key_generator.increment_version(base_key)

def make_simple_key(prefix: str, identifier: str) -> str:
    """Simple key helper: prefix:identifier"""
    return f"{prefix}:{identifier}"