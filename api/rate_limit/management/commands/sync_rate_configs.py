# api/rate_limit/management/commands/sync_rate_configs.py
"""
Django Management Command: Sync Rate Limit Configurations to Redis

This command synchronizes all RateLimitConfig data from database to Redis cache
with SHA-256 hash chaining for integrity verification and absolute imports.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from api.rate_limit.models import RateLimitConfig, RateLimitException, IPBlockList
from api.rate_limit.services import RateLimitService
from api.rate_limit.constants import get_redis_key_prefix, get_ttl_for_key_type
from api.rate_limit.exceptions import RateLimitServiceUnavailable, RateLimitCacheException

logger = logging.getLogger(__name__)


class RateLimitConfigSyncManager:
    """
    Manages synchronization of rate limit configurations to Redis with integrity verification.
    """
    
    def __init__(self):
        self.redis_key_prefix = get_redis_key_prefix()
        self.sync_stats = {
            'configs_synced': 0,
            'exceptions_synced': 0,
            'blocks_synced': 0,
            'errors': 0,
            'integrity_failures': 0,
            'start_time': None,
            'end_time': None
        }
        self.hash_chain = {}
    
    def _generate_config_hash(self, config_data: Dict[str, Any]) -> str:
        """
        Generate SHA-256 hash for configuration data.
        
        Args:
            config_data: Configuration data to hash
            
        Returns:
            SHA-256 hash string
        """
        # Sort keys for consistent hashing
        sorted_data = json.dumps(config_data, sort_keys=True, default=str)
        return hashlib.sha256(sorted_data.encode('utf-8')).hexdigest()
    
    def _serialize_config(self, config: RateLimitConfig) -> Dict[str, Any]:
        """
        Serialize RateLimitConfig to dictionary for Redis storage.
        
        Args:
            config: RateLimitConfig instance
            
        Returns:
            Serialized configuration data
        """
        return {
            'id': config.id,
            'name': config.name,
            'rate_limit_type': config.rate_limit_type,
            'requests_per_unit': config.requests_per_unit,
            'time_unit': config.time_unit,
            'time_value': config.time_value,
            'is_active': config.is_active,
            'user_id': config.user.id if config.user else None,
            'ip_address': str(config.ip_address) if config.ip_address else None,
            'endpoint': config.endpoint,
            'task_type': config.task_type,
            'offer_wall': config.offer_wall,
            'whitelist': config.whitelist or [],
            'blacklist': config.blacklist or [],
            'bypass_keys': config.bypass_keys or [],
            'hit_count': config.hit_count,
            'block_count': config.block_count,
            'last_hit_at': config.last_hit_at.isoformat() if config.last_hit_at else None,
            'created_at': config.created_at.isoformat(),
            'updated_at': config.updated_at.isoformat(),
            'tenant_id': config.tenant.id if config.tenant else None
        }
    
    def _serialize_exception(self, exception: RateLimitException) -> Dict[str, Any]:
        """
        Serialize RateLimitException to dictionary for Redis storage.
        
        Args:
            exception: RateLimitException instance
            
        Returns:
            Serialized exception data
        """
        return {
            'id': exception.id,
            'user_id': exception.user.id if exception.user else None,
            'ip_address': str(exception.ip_address) if exception.ip_address else None,
            'endpoint_pattern': exception.endpoint_pattern,
            'exception_type': exception.exception_type,
            'reason': exception.reason,
            'granted_by_id': exception.granted_by.id if exception.granted_by else None,
            'multiplier': exception.multiplier,
            'max_requests': exception.max_requests,
            'is_active': exception.is_active,
            'expires_at': exception.expires_at.isoformat() if exception.expires_at else None,
            'permanent': exception.permanent,
            'usage_count': exception.usage_count,
            'last_used_at': exception.last_used_at.isoformat() if exception.last_used_at else None,
            'created_at': exception.created_at.isoformat(),
            'updated_at': exception.updated_at.isoformat(),
            'tenant_id': exception.tenant.id if exception.tenant else None
        }
    
    def _serialize_block(self, block: IPBlockList) -> Dict[str, Any]:
        """
        Serialize IPBlockList to dictionary for Redis storage.
        
        Args:
            block: IPBlockList instance
            
        Returns:
            Serialized block data
        """
        return {
            'id': block.id,
            'ip_address': str(block.ip_address) if block.ip_address else None,
            'ip_range_start': str(block.ip_range_start) if block.ip_range_start else None,
            'ip_range_end': str(block.ip_range_end) if block.ip_range_end else None,
            'subnet': block.subnet,
            'block_type': block.block_type,
            'reason': block.reason,
            'blocked_by_id': block.blocked_by.id if block.blocked_by else None,
            'description': block.description,
            'is_active': block.is_active,
            'expires_at': block.expires_at.isoformat() if block.expires_at else None,
            'permanent': block.permanent,
            'block_count': block.block_count,
            'last_blocked_at': block.last_blocked_at.isoformat() if block.last_blocked_at else None,
            'integrity_hash': block.integrity_hash,
            'previous_hash': block.previous_hash,
            'created_at': block.created_at.isoformat(),
            'updated_at': block.updated_at.isoformat(),
            'tenant_id': block.tenant.id if block.tenant else None
        }
    
    def _store_config_with_hash(self, config_key: str, config_data: Dict[str, Any]) -> bool:
        """
        Store configuration in Redis with hash chaining for integrity.
        
        Args:
            config_key: Redis key for configuration
            config_data: Configuration data to store
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            # Generate hash for current config
            current_hash = self._generate_config_hash(config_data)
            
            # Get previous hash from chain
            previous_hash = self.hash_chain.get(config_key, '0' * 64)  # Start with zeros for first entry
            
            # Add hash chain to data
            config_data['integrity_hash'] = current_hash
            config_data['previous_hash'] = previous_hash
            
            # Store in Redis with TTL
            ttl = get_ttl_for_key_type('config')
            cache.set(config_key, config_data, timeout=ttl)
            
            # Update hash chain
            self.hash_chain[config_key] = current_hash
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store config {config_key} in Redis: {e}")
            return False
    
    def _verify_integrity(self, config_key: str, stored_data: Dict[str, Any]) -> bool:
        """
        Verify integrity of stored configuration data.
        
        Args:
            config_key: Redis key for configuration
            stored_data: Data retrieved from Redis
            
        Returns:
            True if integrity verified, False otherwise
        """
        try:
            # Extract hash information
            stored_hash = stored_data.get('integrity_hash')
            previous_hash = stored_data.get('previous_hash')
            
            if not stored_hash:
                logger.warning(f"No integrity hash found for {config_key}")
                return False
            
            # Remove hash fields before recalculating
            data_for_hash = stored_data.copy()
            data_for_hash.pop('integrity_hash', None)
            data_for_hash.pop('previous_hash', None)
            
            # Recalculate hash
            calculated_hash = self._generate_config_hash(data_for_hash)
            
            # Verify hash matches
            if calculated_hash != stored_hash:
                logger.error(f"Integrity check failed for {config_key}: stored={stored_hash}, calculated={calculated_hash}")
                return False
            
            # Verify hash chain continuity
            if previous_hash in self.hash_chain:
                if self.hash_chain[previous_hash] != stored_hash:
                    logger.error(f"Hash chain broken for {config_key}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error during integrity verification for {config_key}: {e}")
            return False
    
    def sync_rate_limit_configs(self) -> Dict[str, int]:
        """
        Synchronize all rate limit configurations to Redis.
        
        Returns:
            Dictionary with sync statistics
        """
        self.sync_stats['start_time'] = timezone.now()
        
        try:
            with transaction.atomic():
                # Sync RateLimitConfig
                configs = RateLimitConfig.objects.all()
                for config in configs:
                    try:
                        config_data = self._serialize_config(config)
                        config_key = f"{self.redis_key_prefix}config:{config.id}"
                        
                        if self._store_config_with_hash(config_key, config_data):
                            self.sync_stats['configs_synced'] += 1
                        else:
                            self.sync_stats['errors'] += 1
                            
                    except Exception as e:
                        logger.error(f"Failed to sync config {config.id}: {e}")
                        self.sync_stats['errors'] += 1
                
                # Sync RateLimitException
                exceptions = RateLimitException.objects.filter(is_active=True)
                for exception in exceptions:
                    try:
                        exception_data = self._serialize_exception(exception)
                        exception_key = f"{self.redis_key_prefix}exception:{exception.id}"
                        
                        if self._store_config_with_hash(exception_key, exception_data):
                            self.sync_stats['exceptions_synced'] += 1
                        else:
                            self.sync_stats['errors'] += 1
                            
                    except Exception as e:
                        logger.error(f"Failed to sync exception {exception.id}: {e}")
                        self.sync_stats['errors'] += 1
                
                # Sync IPBlockList
                blocks = IPBlockList.objects.filter(is_active=True)
                for block in blocks:
                    try:
                        block_data = self._serialize_block(block)
                        block_key = f"{self.redis_key_prefix}block:{block.id}"
                        
                        if self._store_config_with_hash(block_key, block_data):
                            self.sync_stats['blocks_synced'] += 1
                        else:
                            self.sync_stats['errors'] += 1
                            
                    except Exception as e:
                        logger.error(f"Failed to sync block {block.id}: {e}")
                        self.sync_stats['errors'] += 1
                
        except Exception as e:
            logger.error(f"Transaction failed during sync: {e}")
            self.sync_stats['errors'] += 1
        
        self.sync_stats['end_time'] = timezone.now()
        return self.sync_stats
    
    def verify_redis_sync(self) -> Dict[str, int]:
        """
        Verify integrity of all synchronized data in Redis.
        
        Returns:
            Dictionary with verification statistics
        """
        verification_stats = {
            'verified': 0,
            'failures': 0,
            'missing': 0
        }
        
        try:
            # Verify configs
            configs = RateLimitConfig.objects.all()
            for config in configs:
                config_key = f"{self.redis_key_prefix}config:{config.id}"
                stored_data = cache.get(config_key)
                
                if not stored_data:
                    verification_stats['missing'] += 1
                    continue
                
                if self._verify_integrity(config_key, stored_data):
                    verification_stats['verified'] += 1
                else:
                    verification_stats['failures'] += 1
                    self.sync_stats['integrity_failures'] += 1
            
            # Verify exceptions
            exceptions = RateLimitException.objects.filter(is_active=True)
            for exception in exceptions:
                exception_key = f"{self.redis_key_prefix}exception:{exception.id}"
                stored_data = cache.get(exception_key)
                
                if not stored_data:
                    verification_stats['missing'] += 1
                    continue
                
                if self._verify_integrity(exception_key, stored_data):
                    verification_stats['verified'] += 1
                else:
                    verification_stats['failures'] += 1
                    self.sync_stats['integrity_failures'] += 1
            
            # Verify blocks
            blocks = IPBlockList.objects.filter(is_active=True)
            for block in blocks:
                block_key = f"{self.redis_key_prefix}block:{block.id}"
                stored_data = cache.get(block_key)
                
                if not stored_data:
                    verification_stats['missing'] += 1
                    continue
                
                if self._verify_integrity(block_key, stored_data):
                    verification_stats['verified'] += 1
                else:
                    verification_stats['failures'] += 1
                    self.sync_stats['integrity_failures'] += 1
                    
        except Exception as e:
            logger.error(f"Error during verification: {e}")
            verification_stats['failures'] += 1
        
        return verification_stats
    
    def clear_redis_sync(self) -> int:
        """
        Clear all synchronized rate limit data from Redis.
        
        Returns:
            Number of keys cleared
        """
        cleared_count = 0
        
        try:
            # Clear configs
            configs = RateLimitConfig.objects.all()
            for config in configs:
                config_key = f"{self.redis_key_prefix}config:{config.id}"
                cache.delete(config_key)
                cleared_count += 1
            
            # Clear exceptions
            exceptions = RateLimitException.objects.all()
            for exception in exceptions:
                exception_key = f"{self.redis_key_prefix}exception:{exception.id}"
                cache.delete(exception_key)
                cleared_count += 1
            
            # Clear blocks
            blocks = IPBlockList.objects.all()
            for block in blocks:
                block_key = f"{self.redis_key_prefix}block:{block.id}"
                cache.delete(block_key)
                cleared_count += 1
            
            # Clear hash chain
            self.hash_chain.clear()
            
        except Exception as e:
            logger.error(f"Error clearing Redis sync: {e}")
        
        return cleared_count


class Command(BaseCommand):
    """
    Django management command to sync rate limit configurations to Redis.
    """
    
    help = 'Synchronize rate limit configurations from database to Redis with integrity verification'
    
    def add_arguments(self, parser):
        """
        Add command arguments.
        """
        parser.add_argument(
            '--verify',
            action='store_true',
            help='Verify integrity of existing sync instead of syncing'
        )
        
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all synchronized data from Redis'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force sync even if verification fails'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually syncing'
        )
        
        parser.add_argument(
            '--config-type',
            choices=['all', 'configs', 'exceptions', 'blocks'],
            default='all',
            help='Type of configurations to sync'
        )
    
    def handle(self, *args, **options):
        """
        Handle command execution.
        """
        sync_manager = RateLimitConfigSyncManager()
        
        if options['clear']:
            cleared_count = sync_manager.clear_redis_sync()
            self.stdout.write(
                self.style.SUCCESS(f'Cleared {cleared_count} keys from Redis')
            )
            return
        
        if options['verify']:
            self.stdout.write('Verifying Redis sync integrity...')
            verification_stats = sync_manager.verify_redis_sync()
            
            self.stdout.write(
                f'Verification Results:\n'
                f'  Verified: {verification_stats["verified"]}\n'
                f'  Failed: {verification_stats["failures"]}\n'
                f'  Missing: {verification_stats["missing"]}'
            )
            
            if verification_stats['failures'] > 0 and not options['force']:
                raise CommandError('Integrity verification failed. Use --force to proceed anyway.')
            
            return
        
        if options['dry_run']:
            self.stdout.write('DRY RUN - No actual syncing will be performed')
        
        # Perform sync
        self.stdout.write('Starting rate limit configuration sync to Redis...')
        
        if options['dry_run']:
            # Just count what would be synced
            config_count = RateLimitConfig.objects.count()
            exception_count = RateLimitException.objects.filter(is_active=True).count()
            block_count = IPBlockList.objects.filter(is_active=True).count()
            
            self.stdout.write(
                f'Would sync:\n'
                f'  Configs: {config_count}\n'
                f'  Exceptions: {exception_count}\n'
                f'  Blocks: {block_count}'
            )
            return
        
        # Actual sync
        stats = sync_manager.sync_rate_limit_configs()
        
        # Display results
        duration = (stats['end_time'] - stats['start_time']).total_seconds()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Sync completed in {duration:.2f} seconds:\n'
                f'  Configs synced: {stats["configs_synced"]}\n'
                f'  Exceptions synced: {stats["exceptions_synced"]}\n'
                f'  Blocks synced: {stats["blocks_synced"]}\n'
                f'  Errors: {stats["errors"]}\n'
                f'  Integrity failures: {stats["integrity_failures"]}'
            )
        )
        
        if stats['errors'] > 0 or stats['integrity_failures'] > 0:
            self.stdout.write(
                self.style.WARNING('Some issues occurred during sync. Check logs for details.')
            )
