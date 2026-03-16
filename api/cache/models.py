# api/cache/models.py
"""
Cacheable model mixin with built-in cache invalidation logic.
Models using this mixin automatically invalidate related cache keys on save/delete.
"""
import logging
from django.db import models

logger = logging.getLogger(__name__)


class CacheableModelMixin:
    """
    Mixin for models that need cache invalidation on save/delete.
    
    Usage:
        class MyModel(CacheableModelMixin, models.Model):
            cache_operation_map = {
                'create': 'user_create',
                'update': 'user_update',
                'delete': 'user_delete',
            }
            cache_key_template = 'user:{user_id}'  # Uses instance attr
    """
    
    # Override in subclass: map CRUD to CacheInvalidator operation names
    cache_operation_map = {
        'create': 'create',
        'update': 'update',
        'delete': 'delete',
    }
    
    # Override: template for cache key, e.g. 'user:{user_id}' - uses instance attrs
    cache_key_template = None
    
    # Override: list of (key_template, attr_map) for pattern invalidation
    cache_invalidate_patterns = []
    
    def get_cache_key(self) -> str:
        """Generate cache key for this instance using template."""
        if not self.cache_key_template:
            return f"{self.__class__.__name__.lower()}:{self.pk}"
        
        key = self.cache_key_template
        for attr in dir(self):
            if f"{{{attr}}}" in key and not attr.startswith('_'):
                try:
                    val = getattr(self, attr)
                    if callable(val):
                        val = val()
                    key = key.replace(f"{{{attr}}}", str(val))
                except (AttributeError, TypeError):
                    pass
        return key
    
    def invalidate_cache(self, operation: str):
        """Invalidate related cache keys using CacheInvalidator."""
        try:
            from api.cache.signals import invalidate_model_cache
            invalidate_model_cache(
                instance=self,
                operation=operation,
                key_template=self.cache_key_template,
            )
        except Exception as e:
            logger.warning(f"Cache invalidation failed for {self.__class__.__name__}: {e}")
    
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        op = self.cache_operation_map.get('create' if is_new else 'update')
        self.invalidate_cache(op)
    
    def delete(self, *args, **kwargs):
        op = self.cache_operation_map.get('delete')
        self.invalidate_cache(op)
        super().delete(*args, **kwargs)
