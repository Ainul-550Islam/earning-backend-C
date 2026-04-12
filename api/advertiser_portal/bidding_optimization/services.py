"""
Bidding Optimization Services

This module handles bidding optimization strategies, automated bidding,
budget allocation, and performance-based bidding algorithms.
"""

from typing import Optional, List, Dict, Any, Union, Tuple
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json
import math
import random
import logging
import asyncio
import numpy as np
from scipy import stats
from dataclasses import dataclass
import time
import pickle

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.core.cache import cache
from django.db import connections
from asgiref.sync import sync_to_async

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.bidding_model import Bid, BidStrategy, BidOptimization, BudgetAllocation
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()

# Configure logging
logger = logging.getLogger(__name__)


# Async ORM wrappers
class AsyncORM:
    """Async wrapper for Django ORM operations."""
    
    @staticmethod
    @sync_to_async
    def get_campaign(campaign_id: UUID) -> Campaign:
        """Get campaign by ID asynchronously."""
        return Campaign.objects.get(id=campaign_id, is_deleted=False)
    
    @staticmethod
    @sync_to_async
    def get_bid(bid_id: UUID) -> Bid:
        """Get bid by ID asynchronously."""
        return Bid.objects.get(id=bid_id)
    
    @staticmethod
    @sync_to_async
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID asynchronously."""
        return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
    
    @staticmethod
    @sync_to_async
    def create_bid(bid_data: Dict[str, Any]) -> Bid:
        """Create bid asynchronously."""
        return Bid.objects.create(**bid_data)
    
    @staticmethod
    @sync_to_async
    def create_notification(notification_data: Dict[str, Any]) -> Notification:
        """Create notification asynchronously."""
        return Notification.objects.create(**notification_data)
    
    @staticmethod
    @sync_to_async
    def update_bid(bid: Bid, **fields) -> None:
        """Update bid asynchronously."""
        for field, value in fields.items():
            setattr(bid, field, value)
        bid.save(update_fields=list(fields.keys()))
    
    @staticmethod
    @sync_to_async
    def get_bid_performance(bid_id: UUID, days: int) -> Dict[str, Any]:
        """Get bid performance data asynchronously."""
        from ..database_models.analytics_model import BidPerformance
        
        return BidPerformance.objects.filter(
            bid_id=bid_id,
            date__gte=timezone.now() - timedelta(days=days)
        ).aggregate(
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            total_spend=Sum('spend'),
            avg_position=Avg('avg_position'),
            quality_score=Avg('quality_score')
        )
    
    @staticmethod
    @sync_to_async
    def get_bid_level_performance(bid_id: UUID, days: int) -> Dict[str, List[float]]:
        """Get bid level performance asynchronously."""
        from ..database_models.analytics_model import BidPerformance
        
        performances = BidPerformance.objects.filter(
            bid_id=bid_id,
            date__gte=timezone.now() - timedelta(days=days)
        ).values('bid_amount').annotate(
            avg_conversions=Avg('conversions'),
            total_spend=Sum('spend')
        ).order_by('bid_amount')
        
        bid_level_perf = {}
        for perf in performances:
            bid_amount = str(perf['bid_amount'])
            daily_conversions = BidPerformance.objects.filter(
                bid_id=bid_id,
                bid_amount=perf['bid_amount'],
                date__gte=timezone.now() - timedelta(days=days)
            ).values_list('conversions', flat=True)
            
            bid_level_perf[bid_amount] = list(daily_conversions)
        
        return bid_level_perf
    
    @staticmethod
    @sync_to_async
    def get_competition_data(bid_id: UUID) -> Dict[str, Any]:
        """Get competition data asynchronously."""
        from ..database_models.analytics_model import CompetitionAnalysis
        
        competition = CompetitionAnalysis.objects.filter(
            bid_id=bid_id
        ).order_by('-created_at').first()
        
        if not competition:
            return {
                'avg_competition_bid': 0.0,
                'market_share': 0.0,
                'win_rate': 0.0,
                'competition_level': 'low'
            }
        
        return {
            'avg_competition_bid': float(competition.avg_competitor_bid or 0),
            'market_share': float(competition.market_share or 0),
            'win_rate': float(competition.win_rate or 0),
            'competition_level': competition.competition_level or 'low'
        }


class EnterpriseCacheService:
    """Enterprise-grade Redis caching service with advanced optimization strategies."""
    
    # Cache TTL configurations
    TTL_PERFORMANCE_METRICS = 300  # 5 minutes for real-time data
    TTL_CAMPAIGN_CONFIG = 3600    # 1 hour for static configurations
    TTL_BID_METADATA = 1800       # 30 minutes for bid metadata
    TTL_USER_DATA = 900           # 15 minutes for user data
    TTL_IP_REPUTATION = 7200      # 2 hours for IP reputation data
    
    # Cache key patterns
    KEY_PATTERNS = {
        'bid_performance': 'bid:perf:{bid_id}',
        'campaign_config': 'campaign:config:{campaign_id}',
        'bid_metadata': 'bid:meta:{bid_id}',
        'user_activity': 'user:activity:{user_id}',
        'ip_reputation': 'ip:rep:{ip_hash}',
        'optimization_data': 'opt:data:{bid_id}',
        'fraud_check': 'fraud:check:{user_id}:{action}',
        'rate_limit': 'rate:limit:{user_id}:{action}',
        'request_collapsing': 'collapse:{cache_key}'
    }
    
    @staticmethod
    async def get_hash_field(hash_key: str, field: str) -> Any:
        """Get specific field from Redis hash."""
        try:
            import redis
            redis_client = redis.Redis.from_url(settings.REDIS_URL)
            result = await sync_to_async(redis_client.hget)(hash_key, field)
            if result:
                return pickle.loads(result)
            return None
        except Exception as e:
            logger.error(f"Error getting hash field {hash_key}.{field}: {str(e)}")
            return None
    
    @staticmethod
    async def set_hash_field(hash_key: str, field: str, value: Any, ttl: int = None) -> bool:
        """Set specific field in Redis hash with optional TTL."""
        try:
            import redis
            import pickle
            redis_client = redis.Redis.from_url(settings.REDIS_URL)
            
            serialized_value = pickle.dumps(value)
            success = await sync_to_async(redis_client.hset)(hash_key, field, serialized_value)
            
            if ttl:
                await sync_to_async(redis_client.expire)(hash_key, ttl)
            
            return success
        except Exception as e:
            logger.error(f"Error setting hash field {hash_key}.{field}: {str(e)}")
            return False
    
    @staticmethod
    async def get_hash_all(hash_key: str) -> Dict[str, Any]:
        """Get all fields from Redis hash."""
        try:
            import redis
            import pickle
            redis_client = redis.Redis.from_url(settings.REDIS_URL)
            
            result = await sync_to_async(redis_client.hgetall)(hash_key)
            if result:
                return {
                    field.decode('utf-8'): pickle.loads(value)
                    for field, value in result.items()
                }
            return {}
        except Exception as e:
            logger.error(f"Error getting hash all {hash_key}: {str(e)}")
            return {}
    
    @staticmethod
    async def set_hash_all(hash_key: str, data: Dict[str, Any], ttl: int = None) -> bool:
        """Set multiple fields in Redis hash with optional TTL."""
        try:
            import redis
            import pickle
            redis_client = redis.Redis.from_url(settings.REDIS_URL)
            
            serialized_data = {
                field: pickle.dumps(value)
                for field, value in data.items()
            }
            
            success = await sync_to_async(redis_client.hset)(hash_key, mapping=serialized_data)
            
            if ttl:
                await sync_to_async(redis_client.expire)(hash_key, ttl)
            
            return success
        except Exception as e:
            logger.error(f"Error setting hash all {hash_key}: {str(e)}")
            return False
    
    @staticmethod
    async def get_with_fallback(cache_key: str, fallback_func, ttl: int = 300, 
                              use_hash: bool = False, hash_field: str = None) -> Any:
        """Cache-Aside pattern with automatic fallback."""
        try:
            # Try cache first
            if use_hash and hash_field:
                cached_value = await EnterpriseCacheService.get_hash_field(cache_key, hash_field)
            else:
                cached_value = await EnterpriseCacheService.get(cache_key)
            
            if cached_value is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_value
            
            # Cache miss - check for request collapsing
            collapse_key = EnterpriseCacheService.KEY_PATTERNS['request_collapsing'].format(
                cache_key=cache_key
            )
            
            # Try to acquire collapse lock
            lock_acquired = await EnterpriseCacheService._acquire_collapse_lock(collapse_key)
            
            if not lock_acquired:
                # Another request is processing - wait and retry cache
                await asyncio.sleep(0.1)  # Brief wait
                if use_hash and hash_field:
                    cached_value = await EnterpriseCacheService.get_hash_field(cache_key, hash_field)
                else:
                    cached_value = await EnterpriseCacheService.get(cache_key)
                
                if cached_value is not None:
                    return cached_value
                
                # Still no data - wait for collapse lock to release
                await EnterpriseCacheService._wait_for_collapse_lock(collapse_key, timeout=5.0)
                
                # Final cache check
                if use_hash and hash_field:
                    return await EnterpriseCacheService.get_hash_field(cache_key, hash_field)
                else:
                    return await EnterpriseCacheService.get(cache_key)
            
            try:
                # Execute fallback function
                logger.debug(f"Cache miss, executing fallback for: {cache_key}")
                fresh_value = await fallback_func()
                
                # Cache the result
                if use_hash and hash_field:
                    await EnterpriseCacheService.set_hash_field(cache_key, hash_field, fresh_value, ttl)
                else:
                    await EnterpriseCacheService.set(cache_key, fresh_value, ttl)
                
                return fresh_value
                
            finally:
                # Release collapse lock
                await EnterpriseCacheService._release_collapse_lock(collapse_key)
                
        except Exception as e:
            logger.error(f"Error in cache-aside pattern for {cache_key}: {str(e)}")
            # Return fallback result even if caching fails
            return await fallback_func()
    
    @staticmethod
    async def invalidate_pattern(pattern: str) -> int:
        """Invalidate cache keys matching a pattern."""
        try:
            import redis
            redis_client = redis.Redis.from_url(settings.REDIS_URL)
            
            # Find all keys matching pattern
            keys = await sync_to_async(redis_client.keys)(pattern)
            
            if keys:
                # Delete all matching keys
                deleted_count = await sync_to_async(redis_client.delete)(*keys)
                logger.info(f"Invalidated {deleted_count} cache keys matching pattern: {pattern}")
                return deleted_count
            
            return 0
        except Exception as e:
            logger.error(f"Error invalidating cache pattern {pattern}: {str(e)}")
            return 0
    
    @staticmethod
    async def invalidate_bid_related(bid_id: UUID) -> int:
        """Invalidate all cache keys related to a bid."""
        try:
            patterns = [
                f"bid:perf:{bid_id}",
                f"bid:meta:{bid_id}",
                f"opt:data:{bid_id}",
                f"campaign:config:*"  # Will be filtered by bid's campaign
            ]
            
            total_deleted = 0
            for pattern in patterns:
                if ':' in pattern and '*' not in pattern:
                    # Direct key deletion
                    await EnterpriseCacheService.delete(pattern)
                    total_deleted += 1
                else:
                    # Pattern-based deletion
                    total_deleted += await EnterpriseCacheService.invalidate_pattern(pattern)
            
            logger.info(f"Invalidated {total_deleted} cache keys for bid {bid_id}")
            return total_deleted
            
        except Exception as e:
            logger.error(f"Error invalidating bid cache for {bid_id}: {str(e)}")
            return 0
    
    @staticmethod
    async def invalidate_campaign_related(campaign_id: UUID) -> int:
        """Invalidate all cache keys related to a campaign."""
        try:
            patterns = [
                f"campaign:config:{campaign_id}",
                "bid:perf:*",  # All bid performance (will be filtered)
                "bid:meta:*",  # All bid metadata (will be filtered)
            ]
            
            # Get all bids for this campaign to invalidate specific keys
            from ..database_models.bidding_model import Bid
            bid_ids = await sync_to_async()(
                lambda: list(Bid.objects.filter(
                    campaign_id=campaign_id
                ).values_list('id', flat=True))
            )()
            
            total_deleted = 0
            
            # Invalidate campaign config
            await EnterpriseCacheService.delete(f"campaign:config:{campaign_id}")
            total_deleted += 1
            
            # Invalidate specific bid keys
            for bid_id in bid_ids:
                await EnterpriseCacheService.delete(f"bid:perf:{bid_id}")
                await EnterpriseCacheService.delete(f"bid:meta:{bid_id}")
                await EnterpriseCacheService.delete(f"opt:data:{bid_id}")
                total_deleted += 3
            
            logger.info(f"Invalidated {total_deleted} cache keys for campaign {campaign_id}")
            return total_deleted
            
        except Exception as e:
            logger.error(f"Error invalidating campaign cache for {campaign_id}: {str(e)}")
            return 0
    
    @staticmethod
    async def _acquire_collapse_lock(lock_key: str, timeout: int = 10) -> bool:
        """Acquire request collapsing lock."""
        try:
            import redis
            redis_client = redis.Redis.from_url(settings.REDIS_URL)
            
            # Try to set lock with expiration
            lock_value = str(time.time())
            success = await sync_to_async(redis_client.set)(
                lock_key, lock_value, nx=True, ex=timeout
            )
            
            return success
        except Exception as e:
            logger.error(f"Error acquiring collapse lock {lock_key}: {str(e)}")
            return False
    
    @staticmethod
    async def _release_collapse_lock(lock_key: str) -> None:
        """Release request collapsing lock."""
        try:
            import redis
            redis_client = redis.Redis.from_url(settings.REDIS_URL)
            await sync_to_async(redis_client.delete)(lock_key)
        except Exception as e:
            logger.error(f"Error releasing collapse lock {lock_key}: {str(e)}")
    
    @staticmethod
    async def _wait_for_collapse_lock(lock_key: str, timeout: float = 5.0) -> None:
        """Wait for collapse lock to be released."""
        try:
            import redis
            redis_client = redis.Redis.from_url(settings.REDIS_URL)
            
            start_time = time.time()
            while time.time() - start_time < timeout:
                lock_exists = await sync_to_async(redis_client.exists)(lock_key)
                if not lock_exists:
                    break
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Error waiting for collapse lock {lock_key}: {str(e)}")
    
    @staticmethod
    async def get(cache_key: str) -> Any:
        """Get value from cache asynchronously."""
        try:
            import pickle
            cached_value = cache.get(cache_key)
            if cached_value:
                return pickle.loads(cached_value)
            return None
        except Exception as e:
            logger.error(f"Error getting cache key {cache_key}: {str(e)}")
            return None
    
    @staticmethod
    async def set(cache_key: str, value: Any, timeout: int = 300) -> None:
        """Set value in cache asynchronously."""
        try:
            import pickle
            serialized_value = pickle.dumps(value)
            cache.set(cache_key, serialized_value, timeout)
        except Exception as e:
            logger.error(f"Error setting cache key {cache_key}: {str(e)}")
    
    @staticmethod
    async def delete(cache_key: str) -> None:
        """Delete value from cache asynchronously."""
        try:
            cache.delete(cache_key)
        except Exception as e:
            logger.error(f"Error deleting cache key {cache_key}: {str(e)}")


class CacheManagementService:
    """Comprehensive cache management service for enterprise bidding system."""
    
    @staticmethod
    async def get_cache_statistics() -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        try:
            import redis
            redis_client = redis.Redis.from_url(settings.REDIS_URL)
            
            # Get Redis info
            info = await sync_to_async(redis_client.info)()
            
            # Get cache hit ratios
            keyspace_hits = info.get('keyspace_hits', 0)
            keyspace_misses = info.get('keyspace_misses', 0)
            total_requests = keyspace_hits + keyspace_misses
            hit_ratio = (keyspace_hits / total_requests * 100) if total_requests > 0 else 0
            
            # Get memory usage
            used_memory = info.get('used_memory', 0)
            max_memory = info.get('maxmemory', 0)
            memory_usage_pct = (used_memory / max_memory * 100) if max_memory > 0 else 0
            
            # Count keys by pattern
            bid_perf_keys = len(await sync_to_async(redis_client.keys)('bid:perf:*'))
            bid_meta_keys = len(await sync_to_async(redis_client.keys)('bid:meta:*'))
            campaign_config_keys = len(await sync_to_async(redis_client.keys)('campaign:config:*'))
            ip_rep_keys = len(await sync_to_async(redis_client.keys)('ip:rep:*'))
            
            return {
                'timestamp': timezone.now().isoformat(),
                'redis_info': {
                    'version': info.get('redis_version'),
                    'uptime_seconds': info.get('uptime_in_seconds'),
                    'connected_clients': info.get('connected_clients'),
                    'total_commands_processed': info.get('total_commands_processed')
                },
                'performance': {
                    'hit_ratio': round(hit_ratio, 2),
                    'total_requests': total_requests,
                    'keyspace_hits': keyspace_hits,
                    'keyspace_misses': keyspace_misses
                },
                'memory': {
                    'used_memory_mb': round(used_memory / 1024 / 1024, 2),
                    'max_memory_mb': round(max_memory / 1024 / 1024, 2) if max_memory > 0 else 'unlimited',
                    'usage_percentage': round(memory_usage_pct, 2)
                },
                'key_distribution': {
                    'bid_performance_keys': bid_perf_keys,
                    'bid_metadata_keys': bid_meta_keys,
                    'campaign_config_keys': campaign_config_keys,
                    'ip_reputation_keys': ip_rep_keys,
                    'total_keys': bid_perf_keys + bid_meta_keys + campaign_config_keys + ip_rep_keys
                },
                'ttl_config': {
                    'performance_metrics_seconds': EnterpriseCacheService.TTL_PERFORMANCE_METRICS,
                    'campaign_config_seconds': EnterpriseCacheService.TTL_CAMPAIGN_CONFIG,
                    'bid_metadata_seconds': EnterpriseCacheService.TTL_BID_METADATA,
                    'user_data_seconds': EnterpriseCacheService.TTL_USER_DATA,
                    'ip_reputation_seconds': EnterpriseCacheService.TTL_IP_REPUTATION
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting cache statistics: {str(e)}")
            return {'error': str(e), 'timestamp': timezone.now().isoformat()}
    
    @staticmethod
    async def warmup_cache(campaign_ids: List[UUID] = None) -> Dict[str, Any]:
        """Warm up cache with frequently accessed data."""
        try:
            start_time = time.time()
            warmed_keys = 0
            
            if not campaign_ids:
                # Get active campaigns
                from ..database_models.campaign_model import Campaign
                campaign_ids = await sync_to_async()(
                    lambda: list(Campaign.objects.filter(
                        is_active=True,
                        is_deleted=False
                    ).values_list('id', flat=True)[:100])  # Limit to 100 campaigns
                )()
            
            # Warm up campaign configurations
            for campaign_id in campaign_ids:
                try:
                    campaign = await AsyncORM.get_campaign(campaign_id)
                    
                    # Cache campaign config
                    cache_key = f"campaign:config:{campaign_id}"
                    campaign_data = {
                        'id': str(campaign.id),
                        'name': campaign.name,
                        'status': campaign.status,
                        'daily_budget': float(campaign.daily_budget or 0),
                        'targeting_criteria': campaign.targeting_criteria,
                        'is_active': campaign.is_active
                    }
                    
                    await EnterpriseCacheService.set(
                        cache_key, campaign_data, EnterpriseCacheService.TTL_CAMPAIGN_CONFIG
                    )
                    warmed_keys += 1
                    
                except Exception as e:
                    logger.warning(f"Error warming up cache for campaign {campaign_id}: {str(e)}")
            
            # Warm up bid performance for recent bids
            from ..database_models.bidding_model import Bid
            recent_bid_ids = await sync_to_async()(
                lambda: list(Bid.objects.filter(
                    created_at__gte=timezone.now() - timedelta(hours=24)
                ).values_list('id', flat=True)[:200])  # Limit to 200 recent bids
            )()
            
            for bid_id in recent_bid_ids:
                try:
                    # Trigger performance data caching
                    await AsyncRealTimeAnalyticsService.get_historical_performance(bid_id, days=7)
                    warmed_keys += 1
                    
                except Exception as e:
                    logger.warning(f"Error warming up performance cache for bid {bid_id}: {str(e)}")
            
            duration = time.time() - start_time
            
            return {
                'warmed_keys': warmed_keys,
                'duration_seconds': round(duration, 2),
                'campaigns_processed': len(campaign_ids),
                'bids_processed': len(recent_bid_ids),
                'keys_per_second': round(warmed_keys / duration, 2) if duration > 0 else 0,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in cache warmup: {str(e)}")
            return {'error': str(e), 'timestamp': timezone.now().isoformat()}
    
    @staticmethod
    async def cleanup_expired_cache() -> Dict[str, Any]:
        """Clean up expired cache entries and optimize Redis."""
        try:
            start_time = time.time()
            import redis
            redis_client = redis.Redis.from_url(settings.REDIS_URL)
            
            # Get all keys
            all_keys = await sync_to_async(redis_client.keys)('*')
            
            expired_keys = []
            optimized_keys = 0
            
            for key in all_keys:
                try:
                    key_str = key.decode('utf-8') if isinstance(key, bytes) else str(key)
                    
                    # Check TTL
                    ttl = await sync_to_async(redis_client.ttl)(key_str)
                    
                    if ttl == -1:  # No expiration set
                        # Set appropriate TTL based on key pattern
                        if 'bid:perf:' in key_str:
                            await sync_to_async(redis_client.expire)(key_str, EnterpriseCacheService.TTL_PERFORMANCE_METRICS)
                        elif 'campaign:config:' in key_str:
                            await sync_to_async(redis_client.expire)(key_str, EnterpriseCacheService.TTL_CAMPAIGN_CONFIG)
                        elif 'bid:meta:' in key_str:
                            await sync_to_async(redis_client.expire)(key_str, EnterpriseCacheService.TTL_BID_METADATA)
                        elif 'ip:rep:' in key_str:
                            await sync_to_async(redis_client.expire)(key_str, EnterpriseCacheService.TTL_IP_REPUTATION)
                        
                        optimized_keys += 1
                    
                    elif ttl == -2:  # Key doesn't exist
                        expired_keys.append(key_str)
                        
                except Exception as e:
                    logger.warning(f"Error processing key {key}: {str(e)}")
            
            # Remove expired keys
            if expired_keys:
                await sync_to_async(redis_client.delete)(*expired_keys)
            
            duration = time.time() - start_time
            
            return {
                'total_keys_checked': len(all_keys),
                'expired_keys_removed': len(expired_keys),
                'keys_optimized': optimized_keys,
                'duration_seconds': round(duration, 2),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in cache cleanup: {str(e)}")
            return {'error': str(e), 'timestamp': timezone.now().isoformat()}
    
    @staticmethod
    async def monitor_cache_performance() -> Dict[str, Any]:
        """Monitor cache performance and provide recommendations."""
        try:
            stats = await CacheManagementService.get_cache_statistics()
            
            recommendations = []
            
            # Performance recommendations
            if stats.get('performance', {}).get('hit_ratio', 0) < 80:
                recommendations.append({
                    'type': 'performance',
                    'severity': 'warning',
                    'message': f"Cache hit ratio ({stats['performance']['hit_ratio']}%) is below 80%. Consider increasing TTL or warming up cache."
                })
            
            # Memory recommendations
            memory_usage = stats.get('memory', {}).get('usage_percentage', 0)
            if memory_usage > 80:
                recommendations.append({
                    'type': 'memory',
                    'severity': 'critical',
                    'message': f"Memory usage ({memory_usage}%) is above 80%. Consider reducing TTL or adding more memory."
                })
            elif memory_usage > 60:
                recommendations.append({
                    'type': 'memory',
                    'severity': 'warning',
                    'message': f"Memory usage ({memory_usage}%) is above 60%. Monitor closely."
                })
            
            # Key distribution recommendations
            total_keys = stats.get('key_distribution', {}).get('total_keys', 0)
            if total_keys > 100000:
                recommendations.append({
                    'type': 'capacity',
                    'severity': 'info',
                    'message': f"High key count ({total_keys}). Consider implementing key expiration policies."
                })
            
            return {
                'statistics': stats,
                'recommendations': recommendations,
                'health_score': CacheManagementService._calculate_health_score(stats),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error monitoring cache performance: {str(e)}")
            return {'error': str(e), 'timestamp': timezone.now().isoformat()}
    
    @staticmethod
    def _calculate_health_score(stats: Dict[str, Any]) -> float:
        """Calculate overall cache health score (0-100)."""
        try:
            score = 100.0
            
            # Performance impact (40% weight)
            hit_ratio = stats.get('performance', {}).get('hit_ratio', 0)
            if hit_ratio < 80:
                score -= 40 * (80 - hit_ratio) / 80
            
            # Memory impact (30% weight)
            memory_usage = stats.get('memory', {}).get('usage_percentage', 0)
            if memory_usage > 80:
                score -= 30 * (memory_usage - 80) / 20
            elif memory_usage > 60:
                score -= 15 * (memory_usage - 60) / 20
            
            # Key distribution impact (20% weight)
            total_keys = stats.get('key_distribution', {}).get('total_keys', 0)
            if total_keys > 100000:
                score -= 20 * min(1, (total_keys - 100000) / 100000)
            
            # Connection impact (10% weight)
            connected_clients = stats.get('redis_info', {}).get('connected_clients', 0)
            if connected_clients > 1000:
                score -= 10 * min(1, (connected_clients - 1000) / 1000)
            
            return max(0, round(score, 1))
            
        except Exception:
            return 50.0  # Default to middle score on error


class AsyncCache:
    """Legacy async cache wrapper for backward compatibility."""
    
    @staticmethod
    async def get(cache_key: str) -> Any:
        """Get value from cache asynchronously."""
        return await EnterpriseCacheService.get(cache_key)
    
    @staticmethod
    async def set(cache_key: str, value: Any, timeout: int = 300) -> None:
        """Set value in cache asynchronously."""
        await EnterpriseCacheService.set(cache_key, value, timeout)
    
    @staticmethod
    async def delete(cache_key: str) -> None:
        """Delete value from cache asynchronously."""
        await EnterpriseCacheService.delete(cache_key)


@dataclass
class PIDController:
    """PID Controller for bid optimization with real-time feedback."""
    
    # PID gains - tuned for ad-tech bidding
    Kp: float = 0.1  # Proportional gain
    Ki: float = 0.01  # Integral gain  
    Kd: float = 0.05  # Derivative gain
    
    # State variables
    integral: float = 0.0
    previous_error: float = 0.0
    
    # Constraints
    min_output: float = -0.5  # Max 50% decrease
    max_output: float = 0.5   # Max 50% increase
    
    def update(self, setpoint: float, current_value: float, dt: float = 1.0) -> float:
        """Update PID controller and return adjustment factor."""
        # Calculate error
        error = setpoint - current_value
        
        # Proportional term
        proportional = self.Kp * error
        
        # Integral term with anti-windup
        self.integral += error * dt
        self.integral = max(-1.0, min(1.0, self.integral))  # Anti-windup
        integral_term = self.Ki * self.integral
        
        # Derivative term
        derivative = (error - self.previous_error) / dt if dt > 0 else 0
        derivative_term = self.Kd * derivative
        
        # Calculate output
        output = proportional + integral_term + derivative_term
        
        # Apply constraints
        output = max(self.min_output, min(self.max_output, output))
        
        # Update state
        self.previous_error = error
        
        return output
    
    def reset(self) -> None:
        """Reset PID controller state."""
        self.integral = 0.0
        self.previous_error = 0.0


@dataclass
class ThompsonSamplingBidder:
    """Thompson Sampling for multi-armed bandit bid optimization."""
    
    # Thompson Sampling parameters
    alpha_prior: float = 1.0  # Prior for success (conversions)
    beta_prior: float = 1.0   # Prior for failure (no conversion)
    
    # Exploration parameters
    exploration_rate: float = 0.1
    min_samples: int = 10
    
    def sample_bid_adjustment(self, historical_performance: Dict[str, List[float]]) -> float:
        """Sample bid adjustment using Thompson Sampling."""
        if not historical_performance:
            return 1.0
        
        # Extract conversion data for different bid levels
        bid_levels = list(historical_performance.keys())
        if len(bid_levels) < 2:
            return 1.0
        
        # Calculate posterior parameters for each bid level
        posteriors = []
        for bid_level in bid_levels:
            conversions = historical_performance[bid_level]
            if len(conversions) < self.min_samples:
                # Use prior if insufficient data
                alpha = self.alpha_prior
                beta = self.beta_prior
            else:
                # Update with observed data
                success_count = sum(1 for conv in conversions if conv > 0)
                failure_count = len(conversions) - success_count
                alpha = self.alpha_prior + success_count
                beta = self.beta_prior + failure_count
            
            posteriors.append((bid_level, alpha, beta))
        
        # Sample from posteriors and select best bid level
        samples = []
        for bid_level, alpha, beta in posteriors:
            sample = np.random.beta(alpha, beta)
            samples.append((bid_level, sample))
        
        # Select bid level with highest sample
        best_bid_level = max(samples, key=lambda x: x[1])[0]
        
        # Convert to adjustment factor
        try:
            base_bid = float(bid_levels[len(bid_levels)//2])  # Use median as base
            best_bid = float(best_bid_level)
            adjustment = best_bid / base_bid if base_bid > 0 else 1.0
            return max(0.5, min(2.0, adjustment))  # Clamp to reasonable range
        except:
            return 1.0


class AsyncRealTimeAnalyticsService:
    """Async real-time analytics service with enterprise caching and request collapsing."""
    
    @staticmethod
    async def get_historical_performance(bid_id: UUID, days: int = 7) -> Dict[str, Any]:
        """Get real historical performance data with enterprise caching and parallel fetching."""
        try:
            # Use enterprise cache with request collapsing
            cache_key = EnterpriseCacheService.KEY_PATTERNS['bid_performance'].format(bid_id=bid_id)
            hash_key = f"bid_perf:{bid_id}"
            
            # Define fallback function for cache-aside pattern
            async def fetch_performance_data():
                # Fetch data in parallel using asyncio.gather
                performance_tasks = [
                    AsyncORM.get_bid_performance(bid_id, days),
                    AsyncORM.get_bid_level_performance(bid_id, days),
                    AsyncORM.get_competition_data(bid_id)
                ]
                
                # Wait for all parallel operations to complete
                bid_perf, bid_level_performance, competition_data = await asyncio.gather(
                    *performance_tasks, return_exceptions=True
                )
                
                # Handle exceptions from parallel operations
                if isinstance(bid_perf, Exception):
                    logger.error(f"Error in bid performance fetch: {str(bid_perf)}")
                    bid_perf = {}
                if isinstance(bid_level_performance, Exception):
                    logger.error(f"Error in bid level performance fetch: {str(bid_level_performance)}")
                    bid_level_performance = {}
                if isinstance(competition_data, Exception):
                    logger.error(f"Error in competition data fetch: {str(competition_data)}")
                    competition_data = {}
                
                # Calculate derived metrics
                impressions = bid_perf.get('total_impressions', 0) or 0
                clicks = bid_perf.get('total_clicks', 0) or 0
                conversions = bid_perf.get('total_conversions', 0) or 0
                spend = float(bid_perf.get('total_spend', 0) or 0)
                
                ctr = (clicks / impressions * 100) if impressions > 0 else 0
                cpc = spend / clicks if clicks > 0 else 0
                cpa = spend / conversions if conversions > 0 else 0
                conversion_rate = (conversions / clicks * 100) if clicks > 0 else 0
                
                # Get data points count
                from ..database_models.analytics_model import BidPerformance
                data_points_count = await sync_to_async()(
                    lambda: BidPerformance.objects.filter(
                        bid_id=bid_id,
                        date__gte=timezone.now() - timedelta(days=days)
                    ).count()
                )()
                
                performance_data = {
                    'impressions': impressions,
                    'clicks': clicks,
                    'conversions': conversions,
                    'spend': spend,
                    'ctr': ctr,
                    'cpc': cpc,
                    'cpa': cpa,
                    'conversion_rate': conversion_rate,
                    'avg_position': bid_perf.get('avg_position', 1.0) or 1.0,
                    'quality_score': bid_perf.get('quality_score', 5.0) or 5.0,
                    'bid_level_performance': bid_level_performance,
                    'competition_data': competition_data,
                    'data_points': data_points_count
                }
                
                # Store in Redis Hash for granular access
                await EnterpriseCacheService.set_hash_all(
                    hash_key, 
                    {
                        'performance_data': performance_data,
                        'last_updated': timezone.now().isoformat(),
                        'days': days
                    },
                    ttl=EnterpriseCacheService.TTL_PERFORMANCE_METRICS
                )
                
                return performance_data
            
            # Use cache-aside pattern with request collapsing
            return await EnterpriseCacheService.get_with_fallback(
                cache_key=hash_key,
                fallback_func=fetch_performance_data,
                ttl=EnterpriseCacheService.TTL_PERFORMANCE_METRICS,
                use_hash=True,
                hash_field='performance_data'
            )
            
        except Exception as e:
            logger.error(f"Error getting historical performance for bid {bid_id}: {str(e)}")
            return {}
    
    @staticmethod
    async def get_performance_metrics(bid_id: UUID) -> Dict[str, Any]:
        """Get specific performance metrics using Redis Hash for granular access."""
        try:
            hash_key = f"bid_perf:{bid_id}"
            
            # Try to get specific metrics from hash
            metrics = await EnterpriseCacheService.get_hash_field(hash_key, 'performance_data')
            
            if metrics:
                return metrics
            
            # Fallback to full performance fetch
            return await AsyncRealTimeAnalyticsService.get_historical_performance(bid_id)
            
        except Exception as e:
            logger.error(f"Error getting performance metrics for bid {bid_id}: {str(e)}")
            return {}
    
    @staticmethod
    async def update_performance_metrics(bid_id: UUID, new_metrics: Dict[str, Any]) -> bool:
        """Update specific performance metrics in Redis Hash."""
        try:
            hash_key = f"bid_perf:{bid_id}"
            
            # Get existing data
            existing_data = await EnterpriseCacheService.get_hash_all(hash_key)
            
            if existing_data and 'performance_data' in existing_data:
                # Merge with existing data
                performance_data = existing_data['performance_data']
                performance_data.update(new_metrics)
                
                # Update hash
                success = await EnterpriseCacheService.set_hash_field(
                    hash_key, 
                    'performance_data', 
                    performance_data,
                    ttl=EnterpriseCacheService.TTL_PERFORMANCE_METRICS
                )
                
                return success
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating performance metrics for bid {bid_id}: {str(e)}")
            return False
    
    @staticmethod
    async def get_parallel_optimization_data(bid_id: UUID, days: int = 7) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """Fetch optimization data in parallel for maximum performance."""
        try:
            # Create parallel tasks for all data sources
            tasks = [
                AsyncORM.get_bid_performance(bid_id, days),
                AsyncORM.get_bid_level_performance(bid_id, days),
                AsyncORM.get_competition_data(bid_id)
            ]
            
            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results with error handling
            bid_perf = results[0] if not isinstance(results[0], Exception) else {}
            bid_level_performance = results[1] if not isinstance(results[1], Exception) else {}
            competition_data = results[2] if not isinstance(results[2], Exception) else {}
            
            return bid_perf, bid_level_performance, competition_data
            
        except Exception as e:
            logger.error(f"Error in parallel optimization data fetch: {str(e)}")
            return {}, {}, {}


class AsyncFraudDetectionService:
    """Async fraud detection service with real-time security checks."""
    
    @staticmethod
    async def device_fingerprinting(user: User, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Advanced device fingerprinting for fraud detection."""
        try:
            # Extract device characteristics
            user_agent = request_data.get('user_agent', '')
            ip_address = request_data.get('ip_address', '')
            screen_resolution = request_data.get('screen_resolution', '')
            timezone_offset = request_data.get('timezone_offset', '')
            language = request_data.get('language', '')
            
            # Generate device fingerprint
            import hashlib
            fingerprint_data = f"{user_agent}:{screen_resolution}:{timezone_offset}:{language}"
            device_fingerprint = hashlib.sha256(fingerprint_data.encode()).hexdigest()
            
            # Check against known fraudulent patterns
            suspicious_patterns = [
                'bot', 'crawler', 'spider', 'scraper', 'automated',
                'headless', 'phantom', 'selenium', 'puppeteer'
            ]
            
            risk_score = 0.0
            risk_factors = []
            
            # Check for suspicious user agents
            for pattern in suspicious_patterns:
                if pattern.lower() in user_agent.lower():
                    risk_score += 0.3
                    risk_factors.append(f"Suspicious user agent pattern: {pattern}")
            
            # Check for headless browsers
            if 'headless' in user_agent.lower():
                risk_score += 0.4
                risk_factors.append("Headless browser detected")
            
            # Check IP reputation
            ip_risk = await AsyncFraudDetectionService._check_ip_reputation(ip_address)
            risk_score += ip_risk['risk_score']
            risk_factors.extend(ip_risk['risk_factors'])
            
            # Check geolocation consistency
            geo_risk = await AsyncFraudDetectionService._check_geolocation_consistency(
                user, ip_address
            )
            risk_score += geo_risk['risk_score']
            risk_factors.extend(geo_risk['risk_factors'])
            
            return {
                'device_fingerprint': device_fingerprint,
                'risk_score': min(1.0, risk_score),
                'risk_factors': risk_factors,
                'is_suspicious': risk_score > 0.5,
                'recommendation': 'block' if risk_score > 0.7 else 'review' if risk_score > 0.3 else 'allow'
            }
            
        except Exception as e:
            logger.error(f"Error in device fingerprinting: {str(e)}")
            return {
                'device_fingerprint': '',
                'risk_score': 0.5,
                'risk_factors': ['Fingerprinting error'],
                'is_suspicious': True,
                'recommendation': 'review'
            }
    
    @staticmethod
    async def ip_intelligence(ip_address: str) -> Dict[str, Any]:
        """Advanced IP intelligence with enterprise caching and parallel analysis."""
        try:
            # Generate IP hash for cache key
            import hashlib
            ip_hash = hashlib.md5(ip_address.encode()).hexdigest()
            cache_key = EnterpriseCacheService.KEY_PATTERNS['ip_reputation'].format(ip_hash=ip_hash)
            
            # Define fallback function for IP intelligence
            async def fetch_ip_intelligence():
                # Check multiple IP intelligence sources in parallel
                ip_tasks = [
                    AsyncFraudDetectionService._check_ip_blacklist(ip_address),
                    AsyncFraudDetectionService._check_ip_geolocation(ip_address),
                    AsyncFraudDetectionService._check_ip_proxy_vpn(ip_address),
                    AsyncFraudDetectionService._check_ip_hosting(ip_address)
                ]
                
                # Execute all IP checks concurrently
                blacklist_result, geo_result, proxy_result, hosting_result = await asyncio.gather(
                    *ip_tasks, return_exceptions=True
                )
                
                risk_score = 0.0
                risk_factors = []
                
                # Process blacklist check
                if not isinstance(blacklist_result, Exception):
                    if blacklist_result['is_blacklisted']:
                        risk_score += 0.8
                        risk_factors.append("IP on blacklist")
                    elif blacklist_result['is_suspicious']:
                        risk_score += 0.4
                        risk_factors.append("IP on suspicious list")
                
                # Process geolocation check
                if not isinstance(geo_result, Exception):
                    if geo_result['is_high_risk_country']:
                        risk_score += 0.3
                        risk_factors.append(f"High risk country: {geo_result['country']}")
                    if geo_result['is_proxy_country']:
                        risk_score += 0.5
                        risk_factors.append("Proxy-friendly country")
                
                # Process proxy/VPN check
                if not isinstance(proxy_result, Exception):
                    if proxy_result['is_proxy']:
                        risk_score += 0.6
                        risk_factors.append("Proxy/VPN detected")
                    if proxy_result['is_tor']:
                        risk_score += 0.7
                        risk_factors.append("Tor exit node detected")
                
                # Process hosting check
                if not isinstance(hosting_result, Exception):
                    if hosting_result['is_datacenter']:
                        risk_score += 0.4
                        risk_factors.append("Datacenter IP")
                    if hosting_result['is_known_abuse']:
                        risk_score += 0.5
                        risk_factors.append("Known abuse IP")
                
                ip_intelligence_result = {
                    'ip_address': ip_address,
                    'risk_score': min(1.0, risk_score),
                    'risk_factors': risk_factors,
                    'is_blacklisted': blacklist_result.get('is_blacklisted', False) if not isinstance(blacklist_result, Exception) else False,
                    'is_proxy': proxy_result.get('is_proxy', False) if not isinstance(proxy_result, Exception) else False,
                    'is_tor': proxy_result.get('is_tor', False) if not isinstance(proxy_result, Exception) else False,
                    'country': geo_result.get('country', 'Unknown') if not isinstance(geo_result, Exception) else 'Unknown',
                    'is_suspicious': risk_score > 0.4,
                    'recommendation': 'block' if risk_score > 0.6 else 'review' if risk_score > 0.2 else 'allow'
                }
                
                # Cache IP intelligence for 2 hours
                await EnterpriseCacheService.set(
                    cache_key, ip_intelligence_result, EnterpriseCacheService.TTL_IP_REPUTATION
                )
                
                return ip_intelligence_result
            
            # Use enterprise cache with request collapsing
            return await EnterpriseCacheService.get_with_fallback(
                cache_key=cache_key,
                fallback_func=fetch_ip_intelligence,
                ttl=EnterpriseCacheService.TTL_IP_REPUTATION
            )
            
                        
            # Process proxy/VPN check
            if not isinstance(proxy_result, Exception):
                if proxy_result['is_proxy']:
                    risk_score += 0.6
                    risk_factors.append("Proxy/VPN detected")
                if proxy_result['is_tor']:
                    risk_score += 0.7
                    risk_factors.append("Tor exit node detected")
            
            # Process hosting check
            if not isinstance(hosting_result, Exception):
                if hosting_result['is_datacenter']:
                    risk_score += 0.4
                    risk_factors.append("Datacenter IP")
                if hosting_result['is_known_abuse']:
                    risk_score += 0.5
                    risk_factors.append("Known abuse IP")
            
            return {
                'ip_address': ip_address,
                'risk_score': min(1.0, risk_score),
                'risk_factors': risk_factors,
                'is_blacklisted': blacklist_result.get('is_blacklisted', False) if not isinstance(blacklist_result, Exception) else False,
                'is_proxy': proxy_result.get('is_proxy', False) if not isinstance(proxy_result, Exception) else False,
                'is_tor': proxy_result.get('is_tor', False) if not isinstance(proxy_result, Exception) else False,
                'country': geo_result.get('country', 'Unknown') if not isinstance(geo_result, Exception) else 'Unknown',
                'is_suspicious': risk_score > 0.4,
                'recommendation': 'block' if risk_score > 0.6 else 'review' if risk_score > 0.2 else 'allow'
            }
            
        except Exception as e:
            logger.error(f"Error in IP intelligence: {str(e)}")
            return {
                'ip_address': ip_address,
                'risk_score': 0.5,
                'risk_factors': ['IP intelligence error'],
                'is_suspicious': True,
                'recommendation': 'review'
            }
    
    @staticmethod
    async def velocity_check(user: User, action: str = 'bid_create') -> Dict[str, Any]:
        """Real-time velocity checking for fraud prevention."""
        try:
            current_time = timezone.now()
            time_window = timedelta(seconds=1)  # 1-second window
            
            # Check recent activity in parallel
            from ..database_models.analytics_model import UserActivityLog
            
            recent_bids = await sync_to_async()(
                lambda: list(UserActivityLog.objects.filter(
                    user=user,
                    action=action,
                    timestamp__gte=current_time - time_window
                ))
            )()
            
            recent_actions = await sync_to_async()(
                lambda: UserActivityLog.objects.filter(
                    user=user,
                    action=action,
                    timestamp__gte=current_time - time_window
                ).count()
            )()
            
            # Calculate velocity score
            velocity_score = 0.0
            risk_factors = []
            
            if recent_actions > 5:  # More than 5 actions in 1 second
                velocity_score += 0.8
                risk_factors.append(f"High velocity: {recent_actions} actions/second")
            elif recent_actions > 3:  # More than 3 actions in 1 second
                velocity_score += 0.5
                risk_factors.append(f"Medium velocity: {recent_actions} actions/second")
            elif recent_actions > 1:  # More than 1 action in 1 second
                velocity_score += 0.2
                risk_factors.append(f"Low velocity: {recent_actions} actions/second")
            
            # Check for burst patterns
            if len(recent_bids) > 0:
                time_diffs = []
                for i in range(1, len(recent_bids)):
                    diff = (recent_bids[i].timestamp - recent_bids[i-1].timestamp).total_seconds()
                    time_diffs.append(diff)
                
                if time_diffs and min(time_diffs) < 0.1:  # Actions less than 100ms apart
                    velocity_score += 0.4
                    risk_factors.append("Burst pattern detected")
            
            return {
                'user_id': str(user.id),
                'action': action,
                'recent_actions': recent_actions,
                'time_window_seconds': 1,
                'velocity_score': min(1.0, velocity_score),
                'risk_factors': risk_factors,
                'is_suspicious': velocity_score > 0.4,
                'recommendation': 'block' if velocity_score > 0.6 else 'review' if velocity_score > 0.2 else 'allow'
            }
            
        except Exception as e:
            logger.error(f"Error in velocity check: {str(e)}")
            return {
                'user_id': str(user.id),
                'action': action,
                'recent_actions': 0,
                'velocity_score': 0.5,
                'risk_factors': ['Velocity check error'],
                'is_suspicious': True,
                'recommendation': 'review'
            }
    
    @staticmethod
    async def balance_credit_check(user: User, bid_amount: Decimal) -> Dict[str, Any]:
        """Async balance and credit check before bid operations."""
        try:
            # Get user's financial data in parallel
            from ..database_models.advertiser_model import AdvertiserCredit, AdvertiserBillingProfile
            
            credit_task = sync_to_async()(
                lambda: AdvertiserCredit.objects.filter(
                    advertiser__user=user,
                    status='active'
                ).first()
            )()
            
            billing_task = sync_to_async()(
                lambda: AdvertiserBillingProfile.objects.filter(
                    advertiser__user=user,
                    is_active=True
                ).first()
            )()
            
            # Execute financial checks concurrently
            credit, billing = await asyncio.gather(credit_task, billing_task, return_exceptions=True)
            
            available_credit = Decimal('0.0')
            daily_limit = Decimal('0.0')
            current_spend = Decimal('0.0')
            
            # Process credit information
            if not isinstance(credit, Exception) and credit:
                available_credit = credit.available_credit or Decimal('0.0')
                daily_limit = credit.daily_limit or Decimal('0.0')
            
            # Process billing information
            if not isinstance(billing, Exception) and billing:
                current_spend = billing.current_spend or Decimal('0.0')
            
            # Calculate financial risk
            total_available = available_credit + (daily_limit - current_spend)
            bid_ratio = bid_amount / total_available if total_available > 0 else Decimal('1.0')
            
            risk_score = 0.0
            risk_factors = []
            
            # Check credit sufficiency
            if bid_amount > available_credit:
                risk_score += 0.6
                risk_factors.append("Insufficient credit")
            
            # Check daily limit
            if (current_spend + bid_amount) > daily_limit:
                risk_score += 0.4
                risk_factors.append("Exceeds daily limit")
            
            # Check for unusual bid size
            if bid_ratio > 0.5:  # Bid more than 50% of available balance
                risk_score += 0.3
                risk_factors.append("Unusually large bid")
            
            return {
                'user_id': str(user.id),
                'bid_amount': float(bid_amount),
                'available_credit': float(available_credit),
                'daily_limit': float(daily_limit),
                'current_spend': float(current_spend),
                'total_available': float(total_available),
                'bid_ratio': float(bid_ratio),
                'risk_score': min(1.0, risk_score),
                'risk_factors': risk_factors,
                'is_sufficient': total_available >= bid_amount,
                'is_suspicious': risk_score > 0.3,
                'recommendation': 'block' if risk_score > 0.5 else 'review' if risk_score > 0.2 else 'allow'
            }
            
        except Exception as e:
            logger.error(f"Error in balance/credit check: {str(e)}")
            return {
                'user_id': str(user.id),
                'bid_amount': float(bid_amount),
                'risk_score': 0.5,
                'risk_factors': ['Financial check error'],
                'is_sufficient': False,
                'is_suspicious': True,
                'recommendation': 'review'
            }
    
    @staticmethod
    async def comprehensive_fraud_check(user: User, bid_data: Dict[str, Any], 
                                     request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive fraud detection combining all security layers."""
        try:
            # Execute all fraud checks in parallel for maximum performance
            fraud_tasks = [
                AsyncFraudDetectionService.device_fingerprinting(user, request_data),
                AsyncFraudDetectionService.ip_intelligence(request_data.get('ip_address', '')),
                AsyncFraudDetectionService.velocity_check(user, 'bid_create'),
                AsyncFraudDetectionService.balance_credit_check(
                    user, Decimal(str(bid_data.get('bid_amount', 0)))
                )
            ]
            
            # Wait for all fraud checks to complete
            device_result, ip_result, velocity_result, financial_result = await asyncio.gather(
                *fraud_tasks, return_exceptions=True
            )
            
            # Handle exceptions in fraud checks
            if isinstance(device_result, Exception):
                logger.error(f"Device fingerprinting failed: {str(device_result)}")
                device_result = {'risk_score': 0.5, 'is_suspicious': True, 'risk_factors': ['Device check error']}
            
            if isinstance(ip_result, Exception):
                logger.error(f"IP intelligence failed: {str(ip_result)}")
                ip_result = {'risk_score': 0.5, 'is_suspicious': True, 'risk_factors': ['IP check error']}
            
            if isinstance(velocity_result, Exception):
                logger.error(f"Velocity check failed: {str(velocity_result)}")
                velocity_result = {'risk_score': 0.5, 'is_suspicious': True, 'risk_factors': ['Velocity check error']}
            
            if isinstance(financial_result, Exception):
                logger.error(f"Financial check failed: {str(financial_result)}")
                financial_result = {'risk_score': 0.5, 'is_suspicious': True, 'risk_factors': ['Financial check error']}
            
            # Calculate composite risk score
            risk_scores = [
                device_result.get('risk_score', 0),
                ip_result.get('risk_score', 0),
                velocity_result.get('risk_score', 0),
                financial_result.get('risk_score', 0)
            ]
            
            # Weight different risk factors
            weights = [0.25, 0.3, 0.25, 0.2]  # IP gets highest weight
            composite_risk_score = sum(score * weight for score, weight in zip(risk_scores, weights))
            
            # Combine all risk factors
            all_risk_factors = []
            for result in [device_result, ip_result, velocity_result, financial_result]:
                all_risk_factors.extend(result.get('risk_factors', []))
            
            # Determine final recommendation
            is_suspicious = (
                device_result.get('is_suspicious', False) or
                ip_result.get('is_suspicious', False) or
                velocity_result.get('is_suspicious', False) or
                financial_result.get('is_suspicious', False)
            )
            
            # Zero tolerance for fraud - block if any high-risk indicators
            high_risk_indicators = [
                ip_result.get('is_blacklisted', False),
                ip_result.get('is_tor', False),
                velocity_result.get('velocity_score', 0) > 0.6,
                financial_result.get('risk_score', 0) > 0.7
            ]
            
            recommendation = 'block' if any(high_risk_indicators) else 'review' if composite_risk_score > 0.4 else 'allow'
            
            # Log the fraud check asynchronously
            await AsyncFraudDetectionService._log_fraud_check_async(
                user, composite_risk_score, all_risk_factors, recommendation
            )
            
            return {
                'user_id': str(user.id),
                'composite_risk_score': min(1.0, composite_risk_score),
                'device_fingerprinting': device_result,
                'ip_intelligence': ip_result,
                'velocity_check': velocity_result,
                'financial_check': financial_result,
                'all_risk_factors': all_risk_factors,
                'is_suspicious': is_suspicious,
                'recommendation': recommendation,
                'check_timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in comprehensive fraud check: {str(e)}")
            return {
                'user_id': str(user.id),
                'composite_risk_score': 0.8,
                'all_risk_factors': ['Fraud check system error'],
                'is_suspicious': True,
                'recommendation': 'block'
            }
    
    @staticmethod
    async def _check_ip_reputation(ip_address: str) -> Dict[str, Any]:
        """Check IP reputation against multiple sources."""
        try:
            # Mock implementation - in production, integrate with real IP intelligence services
            risk_score = 0.0
            risk_factors = []
            
            # Check against internal blacklist
            blacklist_ips = ['192.168.1.100', '10.0.0.50']  # Example blacklisted IPs
            if ip_address in blacklist_ips:
                risk_score += 0.8
                risk_factors.append("IP on internal blacklist")
            
            # Check against known proxy/VPN ranges
            proxy_ranges = ['10.0.0.0/8', '172.16.0.0/12']  # Example proxy ranges
            if any(ip_address.startswith(prefix) for prefix in ['10.', '172.16.', '192.168.']):
                risk_score += 0.3
                risk_factors.append("IP in private range")
            
            return {
                'risk_score': min(1.0, risk_score),
                'risk_factors': risk_factors
            }
            
        except Exception as e:
            logger.error(f"Error checking IP reputation: {str(e)}")
            return {'risk_score': 0.5, 'risk_factors': ['IP reputation check error']}
    
    @staticmethod
    async def _check_ip_geolocation(ip_address: str) -> Dict[str, Any]:
        """Check IP geolocation for fraud detection."""
        try:
            # Mock implementation - in production, integrate with MaxMind or similar
            import geoip2.database
            
            # This would be replaced with actual GeoIP database lookup
            geo_data = {
                'country': 'US',
                'is_high_risk_country': False,
                'is_proxy_country': False
            }
            
            # High-risk countries for ad fraud
            high_risk_countries = ['CN', 'RU', 'IR', 'KP']
            if geo_data['country'] in high_risk_countries:
                geo_data['is_high_risk_country'] = True
            
            # Countries known for proxy services
            proxy_countries = ['SE', 'NL', 'DE', 'RO']
            if geo_data['country'] in proxy_countries:
                geo_data['is_proxy_country'] = True
            
            return geo_data
            
        except Exception as e:
            logger.error(f"Error checking IP geolocation: {str(e)}")
            return {
                'country': 'Unknown',
                'is_high_risk_country': False,
                'is_proxy_country': False
            }
    
    @staticmethod
    async def _check_ip_proxy_vpn(ip_address: str) -> Dict[str, Any]:
        """Check if IP is from proxy/VPN/Tor."""
        try:
            # Mock implementation - in production, integrate with real detection services
            # Check Tor exit nodes
            tor_exit_nodes = ['1.1.1.1', '2.2.2.2']  # Example Tor nodes
            is_tor = ip_address in tor_exit_nodes
            
            # Check for known VPN providers
            vpn_ranges = ['5.0.0.0/8']  # Example VPN ranges
            is_proxy = any(ip_address.startswith(prefix) for prefix in ['5.0.'])
            
            return {
                'is_proxy': is_proxy,
                'is_tor': is_tor,
                'is_vpn': is_proxy and not is_tor
            }
            
        except Exception as e:
            logger.error(f"Error checking IP proxy/VPN: {str(e)}")
            return {
                'is_proxy': False,
                'is_tor': False,
                'is_vpn': False
            }
    
    @staticmethod
    async def _check_ip_hosting(ip_address: str) -> Dict[str, Any]:
        """Check if IP is from datacenter/hosting provider."""
        try:
            # Mock implementation - in production, integrate with WHOIS and ASN databases
            hosting_asns = ['AS13335', 'AS8075']  # Example hosting provider ASNs
            
            # This would be replaced with actual ASN lookup
            is_datacenter = False
            is_known_abuse = False
            
            # Simple heuristic for datacenter IPs
            if any(ip_address.startswith(prefix) for prefix in ['8.8.8.', '208.67.']):
                is_datacenter = True
                is_known_abuse = True
            
            return {
                'is_datacenter': is_datacenter,
                'is_known_abuse': is_known_abuse
            }
            
        except Exception as e:
            logger.error(f"Error checking IP hosting: {str(e)}")
            return {
                'is_datacenter': False,
                'is_known_abuse': False
            }
    
    @staticmethod
    async def _check_geolocation_consistency(user: User, ip_address: str) -> Dict[str, Any]:
        """Check geolocation consistency with user's historical patterns."""
        try:
            # Get user's historical locations
            from ..database_models.analytics_model import UserActivityLog
            
            historical_locations = await sync_to_async()(
                lambda: list(UserActivityLog.objects.filter(
                    user=user,
                    action='login',
                    timestamp__gte=timezone.now() - timedelta(days=30)
                ).values_list('ip_address', flat=True).distinct())
            )()
            
            # Get current location
            current_geo = await AsyncFraudDetectionService._check_ip_geolocation(ip_address)
            current_country = current_geo['country']
            
            risk_score = 0.0
            risk_factors = []
            
            # Check for location inconsistency
            if len(historical_locations) > 0:
                # Get countries from historical IPs
                historical_countries = set()
                for hist_ip in historical_locations[:10]:  # Last 10 locations
                    hist_geo = await AsyncFraudDetectionService._check_ip_geolocation(hist_ip)
                    historical_countries.add(hist_geo['country'])
                
                # Check if current country is new
                if current_country not in historical_countries:
                    risk_score += 0.3
                    risk_factors.append(f"New location: {current_country}")
                
                # Check for impossible travel (multiple countries in short time)
                if len(historical_countries) > 2:
                    risk_score += 0.2
                    risk_factors.append("Multiple countries in short timeframe")
            
            return {
                'current_country': current_country,
                'historical_countries': list(historical_countries),
                'risk_score': min(1.0, risk_score),
                'risk_factors': risk_factors
            }
            
        except Exception as e:
            logger.error(f"Error checking geolocation consistency: {str(e)}")
            return {
                'risk_score': 0.3,
                'risk_factors': ['Geolocation check error']
            }
    
    @staticmethod
    async def _log_fraud_check_async(user: User, risk_score: float, 
                                risk_factors: List[str], recommendation: str) -> None:
        """Log fraud check results asynchronously."""
        try:
            from ..database_models.analytics_model import FraudCheckLog
            
            await sync_to_async()(
                lambda: FraudCheckLog.objects.create(
                    user=user,
                    risk_score=risk_score,
                    risk_factors=risk_factors,
                    recommendation=recommendation,
                    check_timestamp=timezone.now()
                )
            )()
            
        except Exception as e:
            logger.error(f"Error logging fraud check: {str(e)}")


class AsyncBiddingService:
    """Async service for managing bidding operations with comprehensive fraud detection."""
    
    @staticmethod
    async def create_bid(bid_data: Dict[str, Any], created_by: Optional[User] = None) -> Bid:
        """Create a new bid asynchronously with comprehensive fraud detection."""
        try:
            # Extract request data for fraud detection
            request_data = bid_data.get('request_data', {})
            
            # Step 1: Comprehensive fraud detection BEFORE any bid processing
            fraud_check = await AsyncFraudDetectionService.comprehensive_fraud_check(
                created_by, bid_data, request_data
            )
            
            # Zero tolerance for fraud - block immediately if high risk
            if fraud_check['recommendation'] == 'block':
                logger.warning(f"High-risk bid blocked for user {created_by.id}: {fraud_check['all_risk_factors']}")
                raise AdvertiserValidationError(
                    f"Bid blocked due to security concerns: {', '.join(fraud_check['all_risk_factors'][:3])}"
                )
            
            # Step 2: Additional review for medium risk
            if fraud_check['recommendation'] == 'review':
                logger.warning(f"Medium-risk bid flagged for review for user {created_by.id}: {fraud_check['all_risk_factors']}")
                # Create fraud review record
                await AsyncBiddingService._create_fraud_review_async(
                    created_by, bid_data, fraud_check
                )
                raise AdvertiserValidationError(
                    f"Bid requires manual review: {', '.join(fraud_check['all_risk_factors'][:2])}"
                )
            
            # Step 3: Validate bid data (only if fraud check passed)
            campaign_id = bid_data.get('campaign_id')
            if not campaign_id:
                raise AdvertiserValidationError("campaign_id is required")
            
            campaign = await AsyncORM.get_campaign(campaign_id)
            
            bid_amount = Decimal(str(bid_data.get('bid_amount', 0)))
            if bid_amount <= 0:
                raise AdvertiserValidationError("bid_amount must be positive")
            
            bid_type = bid_data.get('bid_type', 'cpc')
            if bid_type not in ['cpc', 'cpm', 'cpa', 'cpv']:
                raise AdvertiserValidationError("Invalid bid_type")
            
            # Step 4: Additional balance check before bid creation
            financial_check = await AsyncFraudDetectionService.balance_credit_check(
                created_by, bid_amount
            )
            
            if not financial_check['is_sufficient']:
                logger.warning(f"Insufficient funds for bid creation: {financial_check['risk_factors']}")
                raise AdvertiserValidationError(
                    f"Insufficient balance: {', '.join(financial_check['risk_factors'][:2])}"
                )
            
            # Step 5: Create bid data dictionary with fraud metadata
            bid_create_data = {
                'campaign': campaign,
                'bid_type': bid_type,
                'bid_amount': bid_amount,
                'bid_currency': bid_data.get('bid_currency', 'USD'),
                'targeting_criteria': bid_data.get('targeting_criteria', {}),
                'creative_ids': bid_data.get('creative_ids', []),
                'bid_strategy': bid_data.get('bid_strategy', 'manual'),
                'max_bid': Decimal(str(bid_data.get('max_bid', bid_amount))),
                'min_bid': Decimal(str(bid_data.get('min_bid', 0))),
                'bid_adjustments': bid_data.get('bid_adjustments', {}),
                'status': 'pending',
                'created_by': created_by,
                'fraud_check_metadata': {
                    'device_fingerprint': fraud_check.get('device_fingerprinting', {}).get('device_fingerprint', ''),
                    'ip_risk_score': fraud_check.get('ip_intelligence', {}).get('risk_score', 0),
                    'velocity_risk_score': fraud_check.get('velocity_check', {}).get('velocity_score', 0),
                    'financial_risk_score': fraud_check.get('financial_check', {}).get('risk_score', 0),
                    'composite_risk_score': fraud_check.get('composite_risk_score', 0),
                    'all_risk_factors': fraud_check.get('all_risk_factors', [])
                }
            }
            
            # Step 6: Create bid and notification in parallel
            bid_task = AsyncORM.create_bid(bid_create_data)
            notification_task = AsyncORM.create_notification({
                'advertiser': campaign.advertiser,
                'user': created_by,
                'title': 'Bid Created',
                'message': f'New {bid_type} bid of {bid_create_data["bid_currency"]} {bid_amount} created for campaign {campaign.name}.',
                'notification_type': 'bidding',
                'priority': 'medium',
                'channels': ['in_app']
            })
            
            # Step 7: Log user activity for velocity tracking
            activity_task = AsyncBiddingService._log_user_activity_async(
                created_by, 'bid_create', {
                    'campaign_id': str(campaign_id),
                    'bid_amount': float(bid_amount),
                    'bid_type': bid_type,
                    'fraud_check_passed': True,
                    'risk_score': fraud_check.get('composite_risk_score', 0)
                }
            )
            
            # Execute all operations concurrently
            bid, notification, activity_log = await asyncio.gather(
                bid_task, notification_task, activity_task, return_exceptions=True
            )
            
            # Step 8: Handle exceptions from parallel operations
            if isinstance(bid, Exception):
                logger.error(f"Bid creation failed: {str(bid)}")
                raise AdvertiserServiceError(f"Failed to create bid: {str(bid)}")
            
            # Step 9: Log successful creation with fraud metadata
            await AsyncBiddingService._log_creation_async(
                bid, created_by, 
                f"Created bid: {bid_type} {bid_amount} (Risk Score: {fraud_check.get('composite_risk_score', 0)})"
            )
            
            # Step 10: Cache bid metadata using Redis Hashes
            await EnterpriseCacheService.set_hash_all(
                f"bid_meta:{bid.id}",
                {
                    'bid_id': str(bid.id),
                    'campaign_id': str(campaign_id),
                    'bid_type': bid_type,
                    'bid_amount': float(bid_amount),
                    'created_by': str(created_by.id) if created_by else None,
                    'fraud_risk_score': fraud_check.get('composite_risk_score', 0),
                    'created_at': bid.created_at.isoformat(),
                    'status': bid.status
                },
                ttl=EnterpriseCacheService.TTL_BID_METADATA
            )
            
            return bid
                
        except Campaign.DoesNotExist:
            raise AdvertiserNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error creating bid: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create bid: {str(e)}")
    
    @staticmethod
    async def _create_fraud_review_async(user: User, bid_data: Dict[str, Any], 
                                      fraud_check: Dict[str, Any]) -> None:
        """Create fraud review record asynchronously."""
        try:
            from ..database_models.analytics_model import FraudReview
            
            await sync_to_async()(
                lambda: FraudReview.objects.create(
                    user=user,
                    bid_data=bid_data,
                    fraud_check_data=fraud_check,
                    review_status='pending',
                    created_at=timezone.now()
                )
            )()
            
        except Exception as e:
            logger.error(f"Error creating fraud review: {str(e)}")
    
    @staticmethod
    async def _log_user_activity_async(user: User, action: str, metadata: Dict[str, Any]) -> None:
        """Log user activity asynchronously for velocity tracking."""
        try:
            from ..database_models.analytics_model import UserActivityLog
            
            await sync_to_async()(
                lambda: UserActivityLog.objects.create(
                    user=user,
                    action=action,
                    metadata=metadata,
                    timestamp=timezone.now()
                )
            )()
            
        except Exception as e:
            logger.error(f"Error logging user activity: {str(e)}")
            
            bid_type = bid_data.get('bid_type', 'cpc')
            if bid_type not in ['cpc', 'cpm', 'cpa', 'cpv']:
                raise AdvertiserValidationError("Invalid bid_type")
            
            # Create bid and notification in parallel
            bid_task = AsyncORM.create_bid(bid_create_data)
            notification_task = AsyncORM.create_notification({
                'advertiser': campaign.advertiser,
                'user': created_by,
                'title': 'Bid Created',
                'message': f'New {bid_type} bid of {bid_create_data["bid_currency"]} {bid_amount} created for campaign {campaign.name}.',
                'notification_type': 'bidding',
                'priority': 'medium',
                'channels': ['in_app']
            })
            
            # Execute both operations concurrently
            bid, notification = await asyncio.gather(bid_task, notification_task)
            
            # Log creation asynchronously
            await AsyncBiddingService._log_creation_async(bid, created_by, f"Created bid: {bid_type} {bid_amount}")
            
            return bid
                
        except Campaign.DoesNotExist:
            raise AdvertiserNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error creating bid: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create bid: {str(e)}")
    
    @staticmethod
    async def optimize_bid(bid_id: UUID, optimization_data: Dict[str, Any],
                          optimized_by: Optional[User] = None) -> Bid:
        """Optimize existing bid asynchronously with comprehensive fraud detection."""
        try:
            # Step 1: Get bid and user data in parallel
            bid_task = AsyncORM.get_bid(bid_id)
            bid = await bid_task
            
            # Step 2: Comprehensive fraud detection BEFORE optimization
            fraud_check = await AsyncFraudDetectionService.comprehensive_fraud_check(
                optimized_by, {'bid_id': str(bid_id)}, {}
            )
            
            # Zero tolerance for fraud - block optimization if high risk
            if fraud_check['recommendation'] == 'block':
                logger.warning(f"High-risk bid optimization blocked for user {optimized_by.id}: {fraud_check['all_risk_factors']}")
                raise AdvertiserValidationError(
                    f"Bid optimization blocked due to security concerns: {', '.join(fraud_check['all_risk_factors'][:3])}"
                )
            
            # Step 3: Additional review for medium risk
            if fraud_check['recommendation'] == 'review':
                logger.warning(f"Medium-risk bid optimization flagged for review for user {optimized_by.id}: {fraud_check['all_risk_factors']}")
                await AsyncBiddingService._create_fraud_review_async(
                    optimized_by, {'optimization_data': optimization_data}, fraud_check
                )
                raise AdvertiserValidationError(
                    f"Bid optimization requires manual review: {', '.join(fraud_check['all_risk_factors'][:2])}"
                )
            
            # Step 4: Get optimization parameters
            optimization_type = optimization_data.get('optimization_type', 'performance')
            target_metric = optimization_data.get('target_metric', 'ctr')
            target_value = Decimal(str(optimization_data.get('target_value', 0)))
            
            # Step 5: Calculate optimized bid amount with parallel data fetching and fraud checks
            optimized_amount = await AsyncBiddingService._calculate_optimized_bid_async(
                bid, optimization_type, target_metric, target_value
            )
            
            # Step 6: Additional validation on optimized amount
            financial_check = await AsyncFraudDetectionService.balance_credit_check(
                optimized_by, optimized_amount
            )
            
            if not financial_check['is_sufficient']:
                logger.warning(f"Insufficient funds for bid optimization: {financial_check['risk_factors']}")
                raise AdvertiserValidationError(
                    f"Insufficient balance for optimization: {', '.join(financial_check['risk_factors'][:2])}"
                )
            
            # Step 7: Update bid with fraud metadata and parallel operations
            old_amount = bid.bid_amount
            update_data = {
                'bid_amount': optimized_amount,
                'optimized_at': timezone.now(),
                'optimized_by': optimized_by,
                'optimization_metadata': {
                    'optimization_type': optimization_type,
                    'target_metric': target_metric,
                    'target_value': float(target_value),
                    'old_amount': float(old_amount),
                    'new_amount': float(optimized_amount),
                    'change_percentage': float((optimized_amount - old_amount) / old_amount * 100) if old_amount > 0 else 0,
                    'fraud_check_passed': True,
                    'fraud_risk_score': fraud_check.get('composite_risk_score', 0),
                    'fraud_risk_factors': fraud_check.get('all_risk_factors', [])
                }
            }
            
            # Step 8: Execute update and notification in parallel
            update_task = AsyncORM.update_bid(bid, **update_data)
            notification_task = AsyncORM.create_notification({
                'advertiser': bid.campaign.advertiser,
                'user': optimized_by,
                'title': 'Bid Optimized',
                'message': f'Bid optimized from {old_amount} to {optimized_amount}.',
                'notification_type': 'bidding',
                'priority': 'medium',
                'channels': ['in_app']
            })
            
            # Step 9: Log optimization activity for velocity tracking
            activity_task = AsyncBiddingService._log_user_activity_async(
                optimized_by, 'bid_optimize', {
                    'bid_id': str(bid_id),
                    'old_amount': float(old_amount),
                    'new_amount': float(optimized_amount),
                    'optimization_type': optimization_type,
                    'fraud_check_passed': True,
                    'risk_score': fraud_check.get('composite_risk_score', 0)
                }
            )
            
            # Step 10: Execute all operations concurrently
            await asyncio.gather(update_task, notification_task, activity_task, return_exceptions=True)
            
            # Step 11: Log successful optimization with fraud metadata
            await AsyncBiddingService._log_action_async(
                'optimize_bid', 'Bid', str(bid.id), optimized_by, 
                bid.campaign.advertiser, f"Optimized bid: {old_amount} -> {optimized_amount} (Risk Score: {fraud_check.get('composite_risk_score', 0)})"
            )
            
            # Step 12: Invalidate relevant cache keys and update bid metadata
            await EnterpriseCacheService.invalidate_bid_related(bid_id)
            
            # Update bid metadata cache with new optimization data
            await EnterpriseCacheService.set_hash_all(
                f"bid_meta:{bid.id}",
                {
                    'bid_id': str(bid.id),
                    'campaign_id': str(bid.campaign.id),
                    'bid_type': bid.bid_type,
                    'bid_amount': float(optimized_amount),
                    'old_amount': float(old_amount),
                    'optimized_by': str(optimized_by.id) if optimized_by else None,
                    'fraud_risk_score': fraud_check.get('composite_risk_score', 0),
                    'optimized_at': timezone.now().isoformat(),
                    'status': bid.status,
                    'optimization_type': optimization_type,
                    'change_percentage': float((optimized_amount - old_amount) / old_amount * 100) if old_amount > 0 else 0
                },
                ttl=EnterpriseCacheService.TTL_BID_METADATA
            )
            
            return bid
                
        except Bid.DoesNotExist:
            raise AdvertiserNotFoundError(f"Bid {bid_id} not found")
        except Exception as e:
            logger.error(f"Error optimizing bid {bid_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to optimize bid: {str(e)}")
            
            # Get optimization parameters
            optimization_type = optimization_data.get('optimization_type', 'performance')
            target_metric = optimization_data.get('target_metric', 'ctr')
            target_value = Decimal(str(optimization_data.get('target_value', 0)))
            
            # Calculate optimized bid amount with parallel data fetching
            optimized_amount = await AsyncBiddingService._calculate_optimized_bid_async(
                bid, optimization_type, target_metric, target_value
            )
            
            # Update bid with parallel operations
            old_amount = bid.bid_amount
            update_data = {
                'bid_amount': optimized_amount,
                'optimized_at': timezone.now(),
                'optimized_by': optimized_by,
                'optimization_metadata': {
                    'optimization_type': optimization_type,
                    'target_metric': target_metric,
                    'target_value': float(target_value),
                    'old_amount': float(old_amount),
                    'new_amount': float(optimized_amount),
                    'change_percentage': float((optimized_amount - old_amount) / old_amount * 100) if old_amount > 0 else 0
                }
            }
            
            # Update bid and create notification in parallel
            update_task = AsyncORM.update_bid(bid, **update_data)
            notification_task = AsyncORM.create_notification({
                'advertiser': bid.campaign.advertiser,
                'user': optimized_by,
                'title': 'Bid Optimized',
                'message': f'Bid optimized from {old_amount} to {optimized_amount}.',
                'notification_type': 'bidding',
                'priority': 'medium',
                'channels': ['in_app']
            })
            
            # Execute both operations concurrently
            await asyncio.gather(update_task, notification_task)
            
            # Log optimization asynchronously
            await AsyncBiddingService._log_action_async(
                'optimize_bid', 'Bid', str(bid.id), optimized_by, 
                bid.campaign.advertiser, f"Optimized bid: {old_amount} -> {optimized_amount}"
            )
            
            return bid
                
        except Bid.DoesNotExist:
            raise AdvertiserNotFoundError(f"Bid {bid_id} not found")
        except Exception as e:
            logger.error(f"Error optimizing bid {bid_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to optimize bid: {str(e)}")
    
    @staticmethod
    async def get_bid_performance(bid_id: UUID) -> Dict[str, Any]:
        """Get bid performance metrics asynchronously with parallel data fetching."""
        try:
            # Get bid and performance data in parallel
            bid_task = AsyncORM.get_bid(bid_id)
            performance_task = AsyncRealTimeAnalyticsService.get_historical_performance(bid_id, days=7)
            
            # Execute both operations concurrently
            bid, performance_data = await asyncio.gather(bid_task, performance_task)
            
            # Get bid history asynchronously
            from ..database_models.bidding_model import BidOptimization
            bid_history = await sync_to_async()(
                lambda: list(BidOptimization.objects.filter(
                    bid=bid
                ).order_by('-created_at')[:10])
            )()
            
            return {
                'bid_id': str(bid_id),
                'campaign': {
                    'id': str(bid.campaign.id),
                    'name': bid.campaign.name
                },
                'bid_details': {
                    'bid_type': bid.bid_type,
                    'bid_amount': float(bid.bid_amount),
                    'max_bid': float(bid.max_bid),
                    'min_bid': float(bid.min_bid),
                    'bid_strategy': bid.bid_strategy
                },
                'performance_metrics': performance_data,
                'optimization_history': [
                    {
                        'id': str(opt.id),
                        'optimization_type': opt.optimization_type,
                        'old_amount': float(opt.old_amount),
                        'new_amount': float(opt.new_amount),
                        'created_at': opt.created_at.isoformat()
                    }
                    for opt in bid_history
                ],
                'generated_at': timezone.now().isoformat()
            }
            
        except Bid.DoesNotExist:
            raise AdvertiserNotFoundError(f"Bid {bid_id} not found")
        except Exception as e:
            logger.error(f"Error getting bid performance {bid_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get bid performance: {str(e)}")
    
    @staticmethod
    async def _log_creation_async(obj: Any, user: Optional[User], description: str) -> None:
        """Log creation asynchronously."""
        try:
            from ..database_models.audit_model import AuditLog
            await sync_to_async(AuditLog.log_creation)(obj, user, description)
        except Exception as e:
            logger.error(f"Error logging creation asynchronously: {str(e)}")
    
    @staticmethod
    async def _log_action_async(action: str, object_type: str, object_id: str, 
                            user: Optional[User], advertiser: Advertiser, description: str) -> None:
        """Log action asynchronously."""
        try:
            from ..database_models.audit_model import AuditLog
            await sync_to_async(AuditLog.log_action)(
                action, object_type, object_id, user, advertiser, description
            )
        except Exception as e:
            logger.error(f"Error logging action asynchronously: {str(e)}")
    
    @staticmethod
    async def _calculate_optimized_bid_async(bid: Bid, optimization_type: str, target_metric: str, target_value: Decimal) -> Decimal:
        """Calculate optimized bid amount using real-world ad-tech algorithms."""
        try:
            # Get real historical performance data asynchronously
            performance_data = await AsyncRealTimeAnalyticsService.get_historical_performance(bid.id, days=7)
            
            if not performance_data or performance_data.get('data_points', 0) < 5:
                # Insufficient data, return current bid with minimal adjustment
                return bid.bid_amount * Decimal('1.02')  # 2% exploration increase
            
            current_value = Decimal(str(performance_data.get(target_metric, 0)))
            
            if optimization_type == 'performance':
                # PID Controller-based optimization with async cache operations
                optimized_amount = await AsyncBiddingService._optimize_with_pid_async(
                    bid, current_value, target_value, performance_data
                )
                
            elif optimization_type == 'thompson_sampling':
                # Thompson Sampling for multi-armed bandit optimization
                optimized_amount = await AsyncBiddingService._optimize_with_thompson_sampling_async(
                    bid, performance_data
                )
                
            elif optimization_type == 'competition':
                # Competition-aware optimization
                optimized_amount = await AsyncBiddingService._optimize_with_competition_async(
                    bid, performance_data
                )
                
            elif optimization_type == 'hybrid':
                # Hybrid approach combining multiple algorithms with parallel execution
                optimized_amount = await AsyncBiddingService._optimize_hybrid_async(
                    bid, current_value, target_value, performance_data
                )
                
            else:
                optimized_amount = bid.bid_amount
            
            # Apply bid constraints
            optimized_amount = max(bid.min_bid, min(bid.max_bid, optimized_amount))
            
            # Apply budget constraints
            if bid.campaign.daily_budget:
                max_daily_bid = bid.campaign.daily_budget / Decimal('20')  # 5% of daily budget
                optimized_amount = min(optimized_amount, max_daily_bid)
            
            # Quality score adjustment
            quality_score = performance_data.get('quality_score', 5.0)
            if quality_score < 3.0:
                # Low quality score, reduce bid
                optimized_amount *= Decimal('0.8')
            elif quality_score > 8.0:
                # High quality score, can increase bid
                optimized_amount *= Decimal('1.1')
            
            return optimized_amount.quantize(Decimal('0.01'))
            
        except Exception as e:
            logger.error(f"Error calculating optimized bid: {str(e)}")
            return bid.bid_amount
    
    @staticmethod
    async def _optimize_with_pid_async(bid: Bid, current_value: Decimal, target_value: Decimal, 
                             performance_data: Dict[str, Any]) -> Decimal:
        """Optimize bid using PID Controller with async cache operations."""
        try:
            # Get or create PID controller for this bid asynchronously
            cache_key = f"pid_controller_{bid.id}"
            pid_controller = await AsyncCache.get(cache_key)
            
            if not pid_controller:
                pid_controller = PIDController()
                # Tune gains based on performance volatility
                volatility = AsyncBiddingService._calculate_volatility(performance_data)
                if volatility > 0.5:
                    # High volatility, more conservative gains
                    pid_controller.Kp = 0.05
                    pid_controller.Ki = 0.005
                    pid_controller.Kd = 0.02
                elif volatility < 0.1:
                    # Low volatility, more aggressive gains
                    pid_controller.Kp = 0.15
                    pid_controller.Ki = 0.02
                    pid_controller.Kd = 0.08
                
                await AsyncCache.set(cache_key, pid_controller, 3600)  # Cache for 1 hour
            
            # Calculate PID adjustment
            adjustment = pid_controller.update(
                float(target_value), 
                float(current_value),
                dt=1.0  # Daily adjustment
            )
            
            # Apply adjustment to bid
            optimized_bid = bid.bid_amount * Decimal(str(1 + adjustment))
            
            # Update cache
            await AsyncCache.set(cache_key, pid_controller, 3600)
            
            return optimized_bid
            
        except Exception as e:
            logger.error(f"Error in PID optimization: {str(e)}")
            return bid.bid_amount
    
    @staticmethod
    async def _optimize_with_thompson_sampling_async(bid: Bid, performance_data: Dict[str, Any]) -> Decimal:
        """Optimize bid using Thompson Sampling with async cache operations."""
        try:
            # Get or create Thompson Sampling bidder asynchronously
            cache_key = f"thompson_bidder_{bid.id}"
            thompson_bidder = await AsyncCache.get(cache_key)
            
            if not thompson_bidder:
                thompson_bidder = ThompsonSamplingBidder()
                await AsyncCache.set(cache_key, thompson_bidder, 3600)
            
            # Get bid level performance
            bid_level_perf = performance_data.get('bid_level_performance', {})
            
            if not bid_level_perf:
                return bid.bid_amount
            
            # Sample bid adjustment
            adjustment = thompson_bidder.sample_bid_adjustment(bid_level_perf)
            
            # Apply adjustment
            optimized_bid = bid.bid_amount * Decimal(str(adjustment))
            
            # Update cache
            await AsyncCache.set(cache_key, thompson_bidder, 3600)
            
            return optimized_bid
            
        except Exception as e:
            logger.error(f"Error in Thompson Sampling optimization: {str(e)}")
            return bid.bid_amount
    
    @staticmethod
    async def _optimize_with_competition_async(bid: Bid, performance_data: Dict[str, Any]) -> Decimal:
        """Optimize bid based on competition analysis."""
        try:
            competition_data = performance_data.get('competition_data', {})
            avg_competition_bid = competition_data.get('avg_competition_bid', 0.0)
            win_rate = competition_data.get('win_rate', 0.0)
            market_share = competition_data.get('market_share', 0.0)
            
            if avg_competition_bid == 0:
                return bid.bid_amount
            
            # Calculate target bid based on competition
            if win_rate < 0.3:
                # Low win rate, bid more aggressively
                target_bid = avg_competition_bid * 1.15
            elif win_rate > 0.7:
                # High win rate, can bid less aggressively
                target_bid = avg_competition_bid * 0.95
            else:
                # Moderate win rate, bid at competition level
                target_bid = avg_competition_bid
            
            # Adjust based on market share
            if market_share < 0.1:
                target_bid *= 1.1  # Increase to gain market share
            elif market_share > 0.5:
                target_bid *= 0.95  # Can reduce due to dominant position
            
            return Decimal(str(target_bid))
            
        except Exception as e:
            logger.error(f"Error in competition optimization: {str(e)}")
            return bid.bid_amount
    
    @staticmethod
    async def _optimize_hybrid_async(bid: Bid, current_value: Decimal, target_value: Decimal,
                           performance_data: Dict[str, Any]) -> Decimal:
        """Hybrid optimization combining multiple algorithms with parallel execution."""
        try:
            # Execute individual optimizations in parallel
            optimization_tasks = [
                AsyncBiddingService._optimize_with_pid_async(bid, current_value, target_value, performance_data),
                AsyncBiddingService._optimize_with_thompson_sampling_async(bid, performance_data),
                AsyncBiddingService._optimize_with_competition_async(bid, performance_data)
            ]
            
            # Wait for all optimizations to complete
            pid_bid, thompson_bid, competition_bid = await asyncio.gather(
                *optimization_tasks, return_exceptions=True
            )
            
            # Handle exceptions from parallel optimizations
            if isinstance(pid_bid, Exception):
                logger.error(f"Error in async PID optimization: {str(pid_bid)}")
                pid_bid = bid.bid_amount
            if isinstance(thompson_bid, Exception):
                logger.error(f"Error in async Thompson Sampling optimization: {str(thompson_bid)}")
                thompson_bid = bid.bid_amount
            if isinstance(competition_bid, Exception):
                logger.error(f"Error in async competition optimization: {str(competition_bid)}")
                competition_bid = bid.bid_amount
            
            # Calculate weights based on data quality and confidence
            data_points = performance_data.get('data_points', 0)
            volatility = AsyncBiddingService._calculate_volatility(performance_data)
            
            # Weight factors
            if data_points > 100 and volatility < 0.3:
                # High confidence in data, weight PID more
                pid_weight = 0.5
                thompson_weight = 0.3
                competition_weight = 0.2
            elif data_points > 50:
                # Medium confidence, balanced weights
                pid_weight = 0.35
                thompson_weight = 0.35
                competition_weight = 0.3
            else:
                # Low confidence, weight Thompson Sampling more (exploration)
                pid_weight = 0.2
                thompson_weight = 0.5
                competition_weight = 0.3
            
            # Calculate weighted average
            weighted_bid = (
                pid_bid * Decimal(str(pid_weight)) +
                thompson_bid * Decimal(str(thompson_weight)) +
                competition_bid * Decimal(str(competition_weight))
            )
            
            return weighted_bid
            
        except Exception as e:
            logger.error(f"Error in hybrid optimization: {str(e)}")
            return bid.bid_amount
        
        # Default fallback
            # optimization_amount=bid.bid_amount
            
             
            
            # Apply bid constraints
            optimized_amount = max(bid.min_bid, min(bid.max_bid, optimized_amount))
            
            # Apply budget constraints
            if bid.campaign.daily_budget:
                max_daily_bid = bid.campaign.daily_budget / Decimal('20')  # 5% of daily budget
                optimized_amount = min(optimized_amount, max_daily_bid)
            
            # Quality score adjustment
            quality_score = performance_data.get('quality_score', 5.0)
            if quality_score < 3.0:
                # Low quality score, reduce bid
                optimized_amount *= Decimal('0.8')
            elif quality_score > 8.0:
                # High quality score, can increase bid
                optimized_amount *= Decimal('1.1')
            
            return optimized_amount.quantize(Decimal('0.01'))
            
        except Exception as e:
            logger.error(f"Error calculating optimized bid: {str(e)}")
            return bid.bid_amount
    
    @staticmethod
    def _optimize_with_pid(bid: Bid, current_value: Decimal, target_value: Decimal, 
                         performance_data: Dict[str, Any]) -> Decimal:
        """Optimize bid using PID Controller."""
        try:
            # Get or create PID controller for this bid
            cache_key = f"pid_controller_{bid.id}"
            pid_controller = cache.get(cache_key)
            
            if not pid_controller:
                pid_controller = PIDController()
                # Tune gains based on performance volatility
                volatility = BiddingService._calculate_volatility(performance_data)
                if volatility > 0.5:
                    # High volatility, more conservative gains
                    pid_controller.Kp = 0.05
                    pid_controller.Ki = 0.005
                    pid_controller.Kd = 0.02
                elif volatility < 0.1:
                    # Low volatility, more aggressive gains
                    pid_controller.Kp = 0.15
                    pid_controller.Ki = 0.02
                    pid_controller.Kd = 0.08
                
                cache.set(cache_key, pid_controller, 3600)  # Cache for 1 hour
            
            # Calculate PID adjustment
            adjustment = pid_controller.update(
                float(target_value), 
                float(current_value),
                dt=1.0  # Daily adjustment
            )
            
            # Apply adjustment to bid
            optimized_bid = bid.bid_amount * Decimal(str(1 + adjustment))
            
            # Update cache
            cache.set(cache_key, pid_controller, 3600)
            
            return optimized_bid
            
        except Exception as e:
            logger.error(f"Error in PID optimization: {str(e)}")
            return bid.bid_amount
    
    @staticmethod
    def _optimize_with_thompson_sampling(bid: Bid, performance_data: Dict[str, Any]) -> Decimal:
        """Optimize bid using Thompson Sampling."""
        try:
            # Get or create Thompson Sampling bidder
            cache_key = f"thompson_bidder_{bid.id}"
            thompson_bidder = cache.get(cache_key)
            
            if not thompson_bidder:
                thompson_bidder = ThompsonSamplingBidder()
                cache.set(cache_key, thompson_bidder, 3600)
            
            # Get bid level performance
            bid_level_perf = performance_data.get('bid_level_performance', {})
            
            if not bid_level_perf:
                return bid.bid_amount
            
            # Sample bid adjustment
            adjustment = thompson_bidder.sample_bid_adjustment(bid_level_perf)
            
            # Apply adjustment
            optimized_bid = bid.bid_amount * Decimal(str(adjustment))
            
            # Update cache
            cache.set(cache_key, thompson_bidder, 3600)
            
            return optimized_bid
            
        except Exception as e:
            logger.error(f"Error in Thompson Sampling optimization: {str(e)}")
            return bid.bid_amount
    
    @staticmethod
    def _optimize_with_competition(bid: Bid, performance_data: Dict[str, Any]) -> Decimal:
        """Optimize bid based on competition analysis."""
        try:
            competition_data = performance_data.get('competition_data', {})
            avg_competition_bid = competition_data.get('avg_competition_bid', 0.0)
            win_rate = competition_data.get('win_rate', 0.0)
            market_share = competition_data.get('market_share', 0.0)
            
            if avg_competition_bid == 0:
                return bid.bid_amount
            
            # Calculate target bid based on competition
            if win_rate < 0.3:
                # Low win rate, bid more aggressively
                target_bid = avg_competition_bid * 1.15
            elif win_rate > 0.7:
                # High win rate, can bid less aggressively
                target_bid = avg_competition_bid * 0.95
            else:
                # Moderate win rate, bid at competition level
                target_bid = avg_competition_bid
            
            # Adjust based on market share
            if market_share < 0.1:
                target_bid *= 1.1  # Increase to gain market share
            elif market_share > 0.5:
                target_bid *= 0.95  # Can reduce due to dominant position
            
            return Decimal(str(target_bid))
            
        except Exception as e:
            logger.error(f"Error in competition optimization: {str(e)}")
            return bid.bid_amount
    
    @staticmethod
    def _optimize_hybrid(bid: Bid, current_value: Decimal, target_value: Decimal,
                       performance_data: Dict[str, Any]) -> Decimal:
        """Hybrid optimization combining multiple algorithms."""
        try:
            # Get individual optimizations
            pid_bid = BiddingService._optimize_with_pid(bid, current_value, target_value, performance_data)
            thompson_bid = BiddingService._optimize_with_thompson_sampling(bid, performance_data)
            competition_bid = BiddingService._optimize_with_competition(bid, performance_data)
            
            # Calculate weights based on data quality and confidence
            data_points = performance_data.get('data_points', 0)
            volatility = BiddingService._calculate_volatility(performance_data)
            
            # Weight factors
            if data_points > 100 and volatility < 0.3:
                # High confidence in data, weight PID more
                pid_weight = 0.5
                thompson_weight = 0.3
                competition_weight = 0.2
            elif data_points > 50:
                # Medium confidence, balanced weights
                pid_weight = 0.35
                thompson_weight = 0.35
                competition_weight = 0.3
            else:
                # Low confidence, weight Thompson Sampling more (exploration)
                pid_weight = 0.2
                thompson_weight = 0.5
                competition_weight = 0.3
            
            # Calculate weighted average
            weighted_bid = (
                pid_bid * Decimal(str(pid_weight)) +
                thompson_bid * Decimal(str(thompson_weight)) +
                competition_bid * Decimal(str(competition_weight))
            )
            
            return weighted_bid
            
        except Exception as e:
            logger.error(f"Error in hybrid optimization: {str(e)}")
            return bid.bid_amount
    
    @staticmethod
    def _calculate_volatility(performance_data: Dict[str, Any]) -> float:
        """Calculate performance volatility for PID tuning."""
        try:
            # Use coefficient of variation as volatility measure
            ctr = performance_data.get('ctr', 0)
            conversion_rate = performance_data.get('conversion_rate', 0)
            
            # Simple volatility calculation based on recent performance changes
            # In real implementation, this would use time-series analysis
            volatility = abs(ctr - 2.0) / 10.0 + abs(conversion_rate - 1.0) / 5.0
            return min(1.0, max(0.0, volatility))
            
        except Exception as e:
            logger.error(f"Error calculating volatility: {str(e)}")
            return 0.3  # Default medium volatility
    
    @staticmethod
    def _calculate_bid_metrics(bid: Bid) -> Dict[str, Any]:
        """Calculate performance metrics for bid using real analytics data."""
        try:
            # Get real performance data from analytics service
            performance_data = RealTimeAnalyticsService.get_historical_performance(bid.id, days=7)
            
            if not performance_data:
                # Return empty metrics if no data available
                return {}
            
            # Return real metrics
            metrics = {
                'impressions': performance_data.get('impressions', 0),
                'clicks': performance_data.get('clicks', 0),
                'conversions': performance_data.get('conversions', 0),
                'spend': performance_data.get('spend', 0.0),
                'ctr': performance_data.get('ctr', 0.0),
                'cpc': performance_data.get('cpc', 0.0),
                'cpa': performance_data.get('cpa', 0.0),
                'conversion_rate': performance_data.get('conversion_rate', 0.0),
                'roas': BiddingService._calculate_roas(performance_data),
                'quality_score': performance_data.get('quality_score', 5.0),
                'avg_position': performance_data.get('avg_position', 1.0),
                'data_points': performance_data.get('data_points', 0)
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating bid metrics: {str(e)}")
            return {}
    
    @staticmethod
    def _calculate_roas(performance_data: Dict[str, Any]) -> float:
        """Calculate Return on Ad Spend (ROAS)."""
        try:
            spend = performance_data.get('spend', 0.0)
            conversions = performance_data.get('conversions', 0)
            
            if spend <= 0 or conversions <= 0:
                return 0.0
            
            # Get average conversion value from campaign or use default
            # In real implementation, this would come from conversion tracking
            avg_conversion_value = 50.0  # Default value
            
            total_revenue = conversions * avg_conversion_value
            roas = total_revenue / spend if spend > 0 else 0.0
            
            return round(roas, 2)
            
        except Exception as e:
            logger.error(f"Error calculating ROAS: {str(e)}")
            return 0.0
    
    @staticmethod
    def get_campaign(campaign_id: UUID) -> Campaign:
        """Get campaign by ID."""
        try:
            return Campaign.objects.get(id=campaign_id, is_deleted=False)
        except Campaign.DoesNotExist:
            raise AdvertiserNotFoundError(f"Campaign {campaign_id} not found")
    
    @staticmethod
    def get_bid(bid_id: UUID) -> Bid:
        """Get bid by ID."""
        try:
            return Bid.objects.get(id=bid_id)
        except Bid.DoesNotExist:
            raise AdvertiserNotFoundError(f"Bid {bid_id} not found")


class BidStrategyService:
    """Service for managing bid strategies."""
    
    @staticmethod
    def create_strategy(strategy_data: Dict[str, Any], created_by: Optional[User] = None) -> BidStrategy:
        """Create a new bid strategy."""
        try:
            # Validate strategy data
            advertiser_id = strategy_data.get('advertiser_id')
            if not advertiser_id:
                raise AdvertiserValidationError("advertiser_id is required")
            
            advertiser = BidStrategyService.get_advertiser(advertiser_id)
            
            strategy_type = strategy_data.get('strategy_type', 'manual')
            if strategy_type not in ['manual', 'enhanced_cpc', 'target_cpa', 'maximize_conversions', 'target_roas']:
                raise AdvertiserValidationError("Invalid strategy_type")
            
            with transaction.atomic():
                # Create strategy
                strategy = BidStrategy.objects.create(
                    advertiser=advertiser,
                    strategy_type=strategy_type,
                    name=strategy_data.get('name', f'{strategy_type.title()} Strategy'),
                    description=strategy_data.get('description', ''),
                    configuration=strategy_data.get('configuration', {}),
                    target_metric=strategy_data.get('target_metric', 'conversions'),
                    target_value=Decimal(str(strategy_data.get('target_value', 0))),
                    bid_limits=strategy_data.get('bid_limits', {}),
                    optimization_rules=strategy_data.get('optimization_rules', []),
                    is_active=strategy_data.get('is_active', True),
                    created_by=created_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=created_by,
                    title='Bid Strategy Created',
                    message=f'New bid strategy "{strategy.name}" has been created.',
                    notification_type='bidding',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    strategy,
                    created_by,
                    description=f"Created bid strategy: {strategy.name}"
                )
                
                return strategy
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error creating bid strategy: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create bid strategy: {str(e)}")
    
    @staticmethod
    def apply_strategy(strategy_id: UUID, campaign_ids: List[UUID],
                       applied_by: Optional[User] = None) -> bool:
        """Apply bid strategy to campaigns."""
        try:
            strategy = BidStrategyService.get_strategy(strategy_id)
            
            with transaction.atomic():
                applied_count = 0
                
                for campaign_id in campaign_ids:
                    try:
                        campaign = BidStrategyService.get_campaign(campaign_id)
                        
                        # Apply strategy to campaign
                        campaign.bid_strategy = strategy.strategy_type
                        campaign.bid_configuration = strategy.configuration
                        campaign.save(update_fields=['bid_strategy', 'bid_configuration'])
                        
                        applied_count += 1
                        
                    except Campaign.DoesNotExist:
                        logger.warning(f"Campaign {campaign_id} not found, skipping")
                        continue
                
                # Send notification
                Notification.objects.create(
                    advertiser=strategy.advertiser,
                    user=applied_by,
                    title='Bid Strategy Applied',
                    message=f'Strategy "{strategy.name}" applied to {applied_count} campaigns.',
                    notification_type='bidding',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log application
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='apply_bid_strategy',
                    object_type='BidStrategy',
                    object_id=str(strategy.id),
                    user=applied_by,
                    advertiser=strategy.advertiser,
                    description=f"Applied strategy to {applied_count} campaigns"
                )
                
                return True
                
        except BidStrategy.DoesNotExist:
            raise AdvertiserNotFoundError(f"Bid strategy {strategy_id} not found")
        except Exception as e:
            logger.error(f"Error applying bid strategy {strategy_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def get_strategy(strategy_id: UUID) -> BidStrategy:
        """Get bid strategy by ID."""
        try:
            return BidStrategy.objects.get(id=strategy_id)
        except BidStrategy.DoesNotExist:
            raise AdvertiserNotFoundError(f"Bid strategy {strategy_id} not found")
    
    @staticmethod
    def get_campaign(campaign_id: UUID) -> Campaign:
        """Get campaign by ID."""
        try:
            return Campaign.objects.get(id=campaign_id, is_deleted=False)
        except Campaign.DoesNotExist:
            raise AdvertiserNotFoundError(f"Campaign {campaign_id} not found")


class BudgetOptimizationService:
    """Service for budget optimization."""
    
    @staticmethod
    def optimize_budget(campaign_id: UUID, optimization_data: Dict[str, Any],
                        optimized_by: Optional[User] = None) -> Dict[str, Any]:
        """Optimize campaign budget."""
        try:
            campaign = BudgetOptimizationService.get_campaign(campaign_id)
            
            # Get optimization parameters
            optimization_type = optimization_data.get('optimization_type', 'performance')
            target_metric = optimization_data.get('target_metric', 'roas')
            target_value = Decimal(str(optimization_data.get('target_value', 0)))
            
            # Calculate optimized budget
            optimized_budget = BudgetOptimizationService._calculate_optimized_budget(
                campaign, optimization_type, target_metric, target_value
            )
            
            # Create budget allocation record
            allocation = BudgetAllocation.objects.create(
                campaign=campaign,
                old_budget=campaign.daily_budget,
                new_budget=optimized_budget,
                optimization_type=optimization_type,
                target_metric=target_metric,
                target_value=target_value,
                created_by=optimized_by
            )
            
            # Update campaign budget
            campaign.daily_budget = optimized_budget
            campaign.save(update_fields=['daily_budget'])
            
            # Send notification
            Notification.objects.create(
                advertiser=campaign.advertiser,
                user=optimized_by,
                title='Budget Optimized',
                message=f'Campaign budget optimized to {optimized_budget}.',
                notification_type='bidding',
                priority='medium',
                channels=['in_app']
            )
            
            # Log optimization
            from ..database_models.audit_model import AuditLog
            AuditLog.log_action(
                action='optimize_budget',
                object_type='BudgetAllocation',
                object_id=str(allocation.id),
                user=optimized_by,
                advertiser=campaign.advertiser,
                description=f"Optimized budget for campaign {campaign.name}"
            )
            
            return {
                'campaign_id': str(campaign_id),
                'old_budget': float(allocation.old_budget),
                'new_budget': float(optimized_budget),
                'optimization_type': optimization_type,
                'target_metric': target_metric,
                'target_value': float(target_value),
                'allocation_id': str(allocation.id)
            }
            
        except Campaign.DoesNotExist:
            raise AdvertiserNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error optimizing budget {campaign_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to optimize budget: {str(e)}")
    
    @staticmethod
    def _calculate_optimized_budget(campaign: Campaign, optimization_type: str,
                                      target_metric: str, target_value: Decimal) -> Decimal:
        """Calculate optimized budget."""
        try:
            current_budget = campaign.daily_budget or Decimal('100.00')
            
            if optimization_type == 'performance':
                # Get current performance
                current_performance = BudgetOptimizationService._get_campaign_performance(campaign)
                current_value = Decimal(str(current_performance.get(target_metric, 0)))
                
                if current_value == 0:
                    return current_budget
                
                # Calculate budget adjustment
                performance_ratio = target_value / current_value
                max_adjustment = Decimal('0.3')  # Max 30% adjustment
                adjustment_factor = max(Decimal('0.7'), min(Decimal('1.3'), performance_ratio))
                
                optimized_budget = current_budget * adjustment_factor
                
            elif optimization_type == 'opportunity':
                # Opportunity-based optimization
                optimized_budget = current_budget * Decimal('1.2')  # 20% increase
                
            elif optimization_type == 'conservation':
                # Conservation-based optimization
                optimized_budget = current_budget * Decimal('0.8')  # 20% decrease
                
            else:
                optimized_budget = current_budget
            
            # Ensure budget is reasonable
            min_budget = Decimal('10.00')
            max_budget = Decimal('10000.00')
            optimized_budget = max(min_budget, min(max_budget, optimized_budget))
            
            return optimized_budget
            
        except Exception as e:
            logger.error(f"Error calculating optimized budget: {str(e)}")
            return campaign.daily_budget or Decimal('100.00')
    
    @staticmethod
    def _get_campaign_performance(campaign: Campaign) -> Dict[str, Any]:
        """Get campaign performance metrics."""
        try:
            # Mock performance data
            return {
                'impressions': 10000,
                'clicks': 500,
                'conversions': 25,
                'spend': float(campaign.current_spend or 0),
                'ctr': 5.0,
                'cpc': float(campaign.current_spend or 0) / 500 if 500 > 0 else 0,
                'cpa': float(campaign.current_spend or 0) / 25 if 25 > 0 else 0,
                'roas': 3.5
            }
            
        except Exception as e:
            logger.error(f"Error getting campaign performance: {str(e)}")
            return {}
    
    @staticmethod
    def get_campaign(campaign_id: UUID) -> Campaign:
        """Get campaign by ID."""
        try:
            return Campaign.objects.get(id=campaign_id, is_deleted=False)
        except Campaign.DoesNotExist:
            raise AdvertiserNotFoundError(f"Campaign {campaign_id} not found")


class PerformanceBiddingService:
    """Service for performance-based bidding."""
    
    @staticmethod
    def enable_performance_bidding(campaign_id: UUID, config: Dict[str, Any],
                                    enabled_by: Optional[User] = None) -> bool:
        """Enable performance-based bidding for campaign."""
        try:
            campaign = PerformanceBiddingService.get_campaign(campaign_id)
            
            with transaction.atomic():
                # Update campaign with performance bidding config
                campaign.performance_bidding_enabled = True
                campaign.performance_bidding_config = config
                campaign.save(update_fields=['performance_bidding_enabled', 'performance_bidding_config'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=campaign.advertiser,
                    user=enabled_by,
                    title='Performance Bidding Enabled',
                    message=f'Performance bidding enabled for campaign {campaign.name}.',
                    notification_type='bidding',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log enablement
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='enable_performance_bidding',
                    object_type='Campaign',
                    object_id=str(campaign.id),
                    user=enabled_by,
                    advertiser=campaign.advertiser,
                    description=f"Enabled performance bidding for campaign {campaign.name}"
                )
                
                return True
                
        except Campaign.DoesNotExist:
            raise AdvertiserNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error enabling performance bidding {campaign_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_campaign(campaign_id: UUID) -> Campaign:
        """Get campaign by ID."""
        try:
            return Campaign.objects.get(id=campaign_id, is_deleted=False)
        except Campaign.DoesNotExist:
            raise AdvertiserNotFoundError(f"Campaign {campaign_id} not found")


class AutomatedBiddingService:
    """Service for automated bidding."""
    
    @staticmethod
    def create_automated_rule(rule_data: Dict[str, Any], created_by: Optional[User] = None) -> Dict[str, Any]:
        """Create automated bidding rule."""
        try:
            # Validate rule data
            advertiser_id = rule_data.get('advertiser_id')
            if not advertiser_id:
                raise AdvertiserValidationError("advertiser_id is required")
            
            advertiser = AutomatedBiddingService.get_advertiser(advertiser_id)
            
            # Create rule (mock implementation)
            rule_id = str(uuid.uuid4())
            
            # Send notification
            Notification.objects.create(
                advertiser=advertiser,
                user=created_by,
                title='Automated Bidding Rule Created',
                message=f'New automated bidding rule has been created.',
                notification_type='bidding',
                priority='medium',
                channels=['in_app']
            )
            
            return {
                'rule_id': rule_id,
                'advertiser_id': str(advertiser_id),
                'status': 'created'
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error creating automated bidding rule: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create automated bidding rule: {str(e)}")
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
