"""
Network Performance Cache Model for Offer Routing System

This module provides comprehensive network performance caching,
including performance metrics, cache management,
and optimization strategies.
"""

import logging
import json
from typing import Optional
from datetime import datetime, timedelta
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()
logger = logging.getLogger(__name__)


class NetworkPerformanceCache(models.Model):
    """
    Model for caching network performance data.
    
    Stores cached performance metrics for quick access,
    reducing database load and improving response times.
    """
    
    # Core relationships
    network = models.ForeignKey(
        'offer_inventory.OfferNetwork',
        on_delete=models.CASCADE,
        related_name='performance_cache',
        verbose_name=_('Network'),
        help_text=_('Network this cache entry belongs to')
    )
    
    offer = models.ForeignKey(
        'OfferRoute',
        on_delete=models.CASCADE,
        related_name='performance_cache',
        null=True,
        blank=True,
        verbose_name=_('Offer'),
        help_text=_('Offer this cache entry belongs to')
    )
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='performance_cache',
        verbose_name=_('tenants.Tenant'),
        help_text=_('Tenant this cache entry belongs to')
    )
    
    # Cache identification
    cache_key = models.CharField(
        _('Cache Key'),
        max_length=255,
        db_index=True,
        help_text=_('Unique cache key for this entry')
    )
    
    cache_type = models.CharField(
        _('Cache Type'),
        max_length=50,
        choices=[
            ('performance_metrics', _('Performance Metrics')),
            ('response_times', _('Response Times')),
            ('conversion_rates', _('Conversion Rates')),
            ('revenue_data', _('Revenue Data')),
            ('quality_scores', _('Quality Scores')),
            ('user_behavior', _('User Behavior')),
            ('geographic_data', _('Geographic Data')),
            ('device_data', _('Device Data')),
            ('time_series', _('Time Series')),
            ('aggregated_stats', _('Aggregated Statistics')),
            ('predictions', _('Predictions')),
            ('benchmarks', _('Benchmarks')),
        ],
        db_index=True,
        help_text=_('Type of cached data')
    )
    
    # Cache data
    cache_data = models.JSONField(
        _('Cache Data'),
        default=dict,
        help_text=_('Cached performance data')
    )
    
    cache_value = models.TextField(
        _('Cache Value'),
        null=True,
        blank=True,
        help_text=_('Serialized cache value')
    )
    
    # Cache metadata
    data_version = models.IntegerField(
        _('Data Version'),
        default=1,
        help_text=_('Version of the cached data')
    )
    
    data_source = models.CharField(
        _('Data Source'),
        max_length=100,
        choices=[
            ('database', _('Database')),
            ('api', _('API')),
            ('calculation', _('Calculation')),
            ('aggregation', _('Aggregation')),
            ('ml_model', _('ML Model')),
            ('external', _('External Service')),
        ],
        default='calculation',
        help_text=_('Source of the cached data')
    )
    
    # Cache timing
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        db_index=True,
        help_text=_('When this cache entry was created')
    )
    
    expires_at = models.DateTimeField(
        _('Expires At'),
        db_index=True,
        help_text=_('When this cache entry expires')
    )
    
    last_accessed = models.DateTimeField(
        _('Last Accessed'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('When this cache entry was last accessed')
    )
    
    access_count = models.IntegerField(
        _('Access Count'),
        default=0,
        help_text=_('Number of times this cache entry has been accessed')
    )
    
    # Cache configuration
    ttl_seconds = models.IntegerField(
        _('TTL (seconds)'),
        default=300,
        help_text=_('Time to live in seconds')
    )
    
    max_size_bytes = models.IntegerField(
        _('Max Size (bytes)'),
        null=True,
        blank=True,
        help_text=_('Maximum size of cached data in bytes')
    )
    
    current_size_bytes = models.IntegerField(
        _('Current Size (bytes)'),
        default=0,
        help_text=_('Current size of cached data in bytes')
    )
    
    # Cache status
    is_valid = models.BooleanField(
        _('Is Valid'),
        default=True,
        db_index=True,
        help_text=_('Whether this cache entry is valid')
    )
    
    is_warm = models.BooleanField(
        _('Is Warm'),
        default=False,
        help_text=_('Whether this cache entry is warm (frequently accessed)')
    )
    
    is_stale = models.BooleanField(
        _('Is Stale'),
        default=False,
        db_index=True,
        help_text=_('Whether this cache entry is stale')
    )
    
    # Performance metrics
    hit_rate = models.DecimalField(
        _('Hit Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Cache hit rate percentage')
    )
    
    miss_rate = models.DecimalField(
        _('Miss Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Cache miss rate percentage')
    )
    
    avg_access_time_ms = models.IntegerField(
        _('Avg Access Time (ms)'),
        default=0,
        help_text=_('Average access time in milliseconds')
    )
    
    # Cache optimization
    priority = models.IntegerField(
        _('Priority'),
        default=5,
        choices=[
            (1, _('Critical')),
            (2, _('High')),
            (3, _('Medium-High')),
            (4, _('Medium')),
            (5, _('Medium-Low')),
            (6, _('Low')),
            (7, _('Very Low')),
        ],
        help_text=_('Cache priority for eviction')
    )
    
    compression_enabled = models.BooleanField(
        _('Compression Enabled'),
        default=False,
        help_text=_('Whether data compression is enabled')
    )
    
    compression_ratio = models.DecimalField(
        _('Compression Ratio'),
        max_digits=5,
        decimal_places=2,
        default=1.00,
        help_text=_('Compression ratio (compressed/uncompressed)')
    )
    
    # Additional metadata
    tags = models.JSONField(
        _('Tags'),
        default=list,
        blank=True,
        help_text=_('Tags for cache categorization')
    )
    
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional metadata about cache entry')
    )
    
    # Updated timestamp
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this cache entry was last updated')
    )
    
    class Meta:
        db_table = 'offer_routing_network_performance_cache'
        verbose_name = _('Network Performance Cache')
        verbose_name_plural = _('Network Performance Caches')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['network', 'cache_type'], name='idx_network_cache_type_1273'),
            models.Index(fields=['offer', 'cache_type'], name='idx_offer_cache_type_1274'),
            models.Index(fields=['tenant', 'cache_type'], name='idx_tenant_cache_type_1275'),
            models.Index(fields=['cache_key'], name='idx_cache_key_1276'),
            models.Index(fields=['expires_at'], name='idx_expires_at_1277'),
            models.Index(fields=['is_valid', 'expires_at'], name='idx_is_valid_expires_at_1278'),
            models.Index(fields=['is_stale', 'last_accessed'], name='idx_is_stale_last_accessed_f1a'),
            models.Index(fields=['priority', 'access_count'], name='idx_priority_access_count_1280'),
            models.Index(fields=['cache_type', 'created_at'], name='idx_cache_type_created_at_1281'),
            models.Index(fields=['data_source', 'created_at'], name='idx_data_source_created_at_fcd'),
        ]
        unique_together = [
            ['cache_key', 'data_version'],
        ]
    
    def __str__(self):
        return f"Cache: {self.cache_key} - {self.cache_type}"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate cache key
        if not self.cache_key.strip():
            raise ValidationError(_('Cache key cannot be empty'))
        
        # Validate TTL
        if self.ttl_seconds <= 0:
            raise ValidationError(_('TTL must be positive'))
        
        # Validate max size
        if self.max_size_bytes and self.max_size_bytes <= 0:
            raise ValidationError(_('Max size must be positive'))
        
        # Validate current size
        if self.current_size_bytes < 0:
            raise ValidationError(_('Current size cannot be negative'))
        
        # Validate compression ratio
        if self.compression_ratio <= 0:
            raise ValidationError(_('Compression ratio must be positive'))
        
        # Validate hit/miss rates
        for field_name in ['hit_rate', 'miss_rate']:
            rate = getattr(self, field_name)
            if rate < 0 or rate > 100:
                raise ValidationError(_(f'{field_name} must be between 0 and 100'))
    
    def save(self, *args, **kwargs):
        """Override save to add additional logic."""
        # Set expiration if not provided
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(seconds=self.ttl_seconds)
        
        # Calculate current size if not provided
        if self.current_size_bytes == 0:
            self.current_size_bytes = self._calculate_data_size()
        
        # Check if stale
        self.is_stale = timezone.now() > self.expires_at
        
        # Update access time if accessed
        if self.access_count > 0 and not self.last_accessed:
            self.last_accessed = timezone.now()
        
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return timezone.now() > self.expires_at
    
    @property
    def is_cold(self) -> bool:
        """Check if cache entry is cold (rarely accessed)."""
        return (
            self.access_count < 10 or
            (self.last_accessed and 
             (timezone.now() - self.last_accessed).total_seconds() > 3600)  # 1 hour
        )
    
    @property
    def age_seconds(self) -> int:
        """Get age of cache entry in seconds."""
        if self.created_at:
            return int((timezone.now() - self.created_at).total_seconds())
        return 0
    
    @property
    def time_until_expiry(self) -> int:
        """Get seconds until cache expires."""
        if self.expires_at:
            return max(0, int((self.expires_at - timezone.now()).total_seconds()))
        return 0
    
    @property
    def efficiency_score(self) -> float:
        """Calculate cache efficiency score."""
        if self.access_count == 0:
            return 0.0
        
        # Factors: hit rate, access frequency, age, size efficiency
        hit_rate_score = float(self.hit_rate)
        access_frequency = self.access_count / max(self.age_seconds, 1)
        age_score = max(0, 100 - (self.age_seconds / self.ttl_seconds * 100))
        
        if self.max_size_bytes and self.max_size_bytes > 0:
            size_efficiency = (self.max_size_bytes - self.current_size_bytes) / self.max_size_bytes * 100
        else:
            size_efficiency = 50.0
        
        return (hit_rate_score * 0.4 + access_frequency * 0.3 + age_score * 0.2 + size_efficiency * 0.1)
    
    def get_cache_data(self) -> dict:
        """Get cached data with decompression if needed."""
        try:
            if self.compression_enabled and self.cache_value:
                # Decompress data
                import gzip
                import json
                
                decompressed = gzip.decompress(self.cache_value.encode()).decode()
                return json.loads(decompressed)
            elif self.cache_data:
                return self.cache_data
            elif self.cache_value:
                return json.loads(self.cache_value)
            else:
                return {}
                
        except Exception as e:
            logger.error(f"Error getting cache data: {e}")
            return {}
    
    def set_cache_data(self, data: dict):
        """Set cached data with compression if needed."""
        try:
            import json
            
            if self.compression_enabled:
                # Compress data
                import gzip
                
                serialized = json.dumps(data)
                compressed = gzip.compress(serialized.encode())
                
                self.cache_value = compressed.decode()
                self.compression_ratio = len(serialized) / len(compressed)
                self.current_size_bytes = len(compressed)
            else:
                self.cache_data = data
                self.cache_value = json.dumps(data)
                self.current_size_bytes = len(self.cache_value.encode())
                self.compression_ratio = 1.0
            
        except Exception as e:
            logger.error(f"Error setting cache data: {e}")
    
    def access(self) -> dict:
        """Access cache entry and update statistics."""
        try:
            # Update access statistics
            self.access_count += 1
            self.last_accessed = timezone.now()
            
            # Mark as warm if accessed frequently
            if self.access_count >= 50:
                self.is_warm = True
            
            # Update hit/miss rates
            self._update_hit_miss_rates()
            
            # Save updates
            self.save(update_fields=['access_count', 'last_accessed', 'is_warm', 'hit_rate', 'miss_rate'])
            
            # Return cached data
            return self.get_cache_data()
            
        except Exception as e:
            logger.error(f"Error accessing cache entry: {e}")
            return {}
    
    def invalidate(self):
        """Invalidate cache entry."""
        try:
            self.is_valid = False
            self.is_stale = True
            self.save(update_fields=['is_valid', 'is_stale'])
            
            logger.info(f"Cache entry invalidated: {self.cache_key}")
            
        except Exception as e:
            logger.error(f"Error invalidating cache entry: {e}")
    
    def refresh(self, new_data: dict = None):
        """Refresh cache entry with new data."""
        try:
            if new_data:
                self.set_cache_data(new_data)
            
            # Reset expiration
            self.expires_at = timezone.now() + timedelta(seconds=self.ttl_seconds)
            self.is_valid = True
            self.is_stale = False
            self.data_version += 1
            
            self.save()
            
            logger.info(f"Cache entry refreshed: {self.cache_key}")
            
        except Exception as e:
            logger.error(f"Error refreshing cache entry: {e}")
    
    def _calculate_data_size(self) -> int:
        """Calculate size of cached data."""
        try:
            if self.cache_data:
                return len(json.dumps(self.cache_data).encode())
            elif self.cache_value:
                return len(self.cache_value.encode())
            else:
                return 0
                
        except Exception:
            return 0
    
    def _update_hit_miss_rates(self):
        """Update hit and miss rates."""
        try:
            # This would implement hit/miss rate calculation
            # For now, use placeholder logic
            total_requests = self.access_count + 100  # Assume 100 misses
            self.hit_rate = (self.access_count / total_requests) * 100
            self.miss_rate = (100 / total_requests) * 100
            
        except Exception as e:
            logger.error(f"Error updating hit/miss rates: {e}")
    
    @classmethod
    def get_cache_entry(cls, cache_key: str, cache_type: str = None) -> Optional['NetworkPerformanceCache']:
        """Get cache entry by key and type."""
        try:
            query = cls.objects.filter(
                cache_key=cache_key,
                is_valid=True
            ).filter(
                models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
            )
            
            if cache_type:
                query = query.filter(cache_type=cache_type)
            
            return query.first()
            
        except Exception as e:
            logger.error(f"Error getting cache entry: {e}")
            return None
    
    @classmethod
    def set_cache_entry(cls, cache_key: str, data: dict, ttl_seconds: int = 300, 
                        cache_type: str = 'performance_metrics', **kwargs) -> 'NetworkPerformanceCache':
        """Set cache entry with data."""
        try:
            # Check if entry exists
            existing = cls.get_cache_entry(cache_key, cache_type)
            
            if existing:
                existing.refresh(data)
                return existing
            
            # Create new entry
            cache_entry = cls(
                cache_key=cache_key,
                cache_type=cache_type,
                ttl_seconds=ttl_seconds,
                expires_at=timezone.now() + timedelta(seconds=ttl_seconds),
                **kwargs
            )
            
            cache_entry.set_cache_data(data)
            cache_entry.save()
            
            logger.info(f"Cache entry created: {cache_key}")
            
            return cache_entry
            
        except Exception as e:
            logger.error(f"Error setting cache entry: {e}")
            return None
    
    @classmethod
    def invalidate_by_pattern(cls, pattern: str, cache_type: str = None):
        """Invalidate cache entries matching pattern."""
        try:
            query = cls.objects.filter(
                cache_key__icontains=pattern,
                is_valid=True
            )
            
            if cache_type:
                query = query.filter(cache_type=cache_type)
            
            count = query.update(is_valid=False, is_stale=True)
            
            logger.info(f"Invalidated {count} cache entries matching pattern: {pattern}")
            
            return count
            
        except Exception as e:
            logger.error(f"Error invalidating cache entries: {e}")
            return 0
    
    @classmethod
    def cleanup_expired_entries(cls):
        """Clean up expired cache entries."""
        try:
            cutoff_time = timezone.now()
            
            deleted_count = cls.objects.filter(
                expires_at__lt=cutoff_time
            ).delete()[0]
            
            logger.info(f"Cleaned up {deleted_count} expired cache entries")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired cache entries: {e}")
            return 0
    
    @classmethod
    def cleanup_stale_entries(cls, days: int = 7):
        """Clean up stale cache entries."""
        try:
            cutoff_time = timezone.now() - timedelta(days=days)
            
            deleted_count = cls.objects.filter(
                is_stale=True,
                last_accessed__lt=cutoff_time
            ).delete()[0]
            
            logger.info(f"Cleaned up {deleted_count} stale cache entries")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up stale cache entries: {e}")
            return 0
    
    @classmethod
    def get_cache_statistics(cls, tenant_id: int = None) -> dict:
        """Get cache statistics."""
        try:
            query = cls.objects.all()
            
            if tenant_id:
                query = query.filter(tenant_id=tenant_id)
            
            total_entries = query.count()
            valid_entries = query.filter(is_valid=True).count()
            expired_entries = query.filter(is_stale=True).count()
            warm_entries = query.filter(is_warm=True).count()
            
            # Calculate average metrics
            avg_hit_rate = query.aggregate(
                avg_hit_rate=models.Avg('hit_rate')
            )['avg_hit_rate'] or 0
            
            avg_access_time = query.aggregate(
                avg_access_time=models.Avg('avg_access_time_ms')
            )['avg_access_time'] or 0
            
            # Cache size statistics
            total_size = query.aggregate(
                total_size=models.Sum('current_size_bytes')
            )['total_size'] or 0
            
            # Distribution by type
            type_distribution = dict(
                query.values('cache_type').annotate(
                    count=models.Count('id')
                ).values_list('cache_type', 'count')
            )
            
            return {
                'total_entries': total_entries,
                'valid_entries': valid_entries,
                'expired_entries': expired_entries,
                'warm_entries': warm_entries,
                'cold_entries': total_entries - warm_entries,
                'validity_rate': (valid_entries / total_entries * 100) if total_entries > 0 else 0,
                'avg_hit_rate': float(avg_hit_rate),
                'avg_access_time_ms': avg_access_time,
                'total_size_bytes': total_size,
                'type_distribution': type_distribution,
                'expiring_soon': query.filter(
                    expires_at__lte=timezone.now() + timedelta(hours=1),
                    is_valid=True
                ).count(),
                'high_priority_entries': query.filter(priority__in=[1, 2]).count(),
            }
            
        except Exception as e:
            logger.error(f"Error getting cache statistics: {e}")
            return {}
    
    @classmethod
    def optimize_cache(cls, tenant_id: int = None):
        """Optimize cache performance."""
        try:
            query = cls.objects.all()
            
            if tenant_id:
                query = query.filter(tenant_id=tenant_id)
            
            optimizations = []
            
            # Remove expired entries
            expired_count = cls.cleanup_expired_entries()
            if expired_count > 0:
                optimizations.append(f"Removed {expired_count} expired entries")
            
            # Remove stale cold entries
            stale_cutoff = timezone.now() - timedelta(days=3)
            cold_stale_count = query.filter(
                is_stale=True,
                is_warm=False,
                last_accessed__lt=stale_cutoff
            ).delete()[0]
            
            if cold_stale_count > 0:
                optimizations.append(f"Removed {cold_stale_count} cold stale entries")
            
            # Promote frequently accessed entries
            query.filter(
                access_count__gte=100,
                is_warm=False
            ).update(is_warm=True)
            
            # Compress large entries if not compressed
            large_uncompressed = query.filter(
                current_size_bytes__gt=10000,  # > 10KB
                compression_enabled=False
            )
            
            for entry in large_uncompressed:
                entry.compression_enabled = True
                entry.save()
                optimizations.append(f"Compressed entry: {entry.cache_key}")
            
            logger.info(f"Cache optimization completed: {len(optimizations)} optimizations")
            
            return {
                'optimizations': optimizations,
                'expired_removed': expired_count,
                'cold_stale_removed': cold_stale_count,
                'entries_compressed': large_uncompressed.count(),
            }
            
        except Exception as e:
            logger.error(f"Error optimizing cache: {e}")
            return {'error': str(e)}


# Signal handlers for cache management
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=NetworkPerformanceCache)
def cache_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for cache entries."""
    if created:
        logger.info(f"New cache entry created: {instance.cache_key} - {instance.cache_type}")
        
        # Trigger cache analysis tasks
        from ..tasks.cache import analyze_cache_entry
        analyze_cache_entry.delay(instance.id)

@receiver(post_delete, sender=NetworkPerformanceCache)
def cache_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for cache entries."""
    logger.info(f"Cache entry deleted: {instance.cache_key} - {instance.cache_type}")
