from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import logging

from api.rate_limit.services.RateLimitService import RateLimitService
from api.rate_limit.services.IPBlockService import IPBlockService
from api.rate_limit.services.AbuseDetectionService import AbuseDetectionService
from api.rate_limit.services.RateLimitInsightService import RateLimitInsightService
from api.rate_limit.models import (
    RateLimitConfig, UserRateLimitProfile, IPBlockList, 
    AbuseReport, RateLimitInsight, RateLimitException
)
from api.rate_limit.models import RateLimitLog

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Comprehensive sync of rate limits, IP blocks, abuse reports, and insights'
    
    def add_arguments(self, parser):
        # Basic sync options
        parser.add_argument(
            '--user',
            type=int,
            help='User ID to sync limits for'
        )
        parser.add_argument(
            '--config',
            type=int,
            help='Config ID to sync'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Sync all rate limit configs'
        )
        
        # Advanced sync options
        parser.add_argument(
            '--ip-blocks',
            action='store_true',
            help='Sync IP blocks to Redis cache'
        )
        parser.add_argument(
            '--abuse-reports',
            action='store_true',
            help='Sync abuse reports and update patterns'
        )
        parser.add_argument(
            '--insights',
            action='store_true',
            help='Generate and sync rate limit insights'
        )
        parser.add_argument(
            '--exceptions',
            action='store_true',
            help='Sync rate limit exceptions'
        )
        
        # Time-based options
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to analyze for insights (default: 7)'
        )
        parser.add_argument(
            '--since',
            type=str,
            help='Sync data since specific date (YYYY-MM-DD format)'
        )
        
        # Performance options
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Batch size for bulk operations (default: 100)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force sync even if cache is fresh'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without making changes'
        )
        
        # Cleanup options
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up expired blocks and old data'
        )
        parser.add_argument(
            '--vacuum',
            action='store_true',
            help='Vacuum and optimize Redis cache'
        )
    
    def handle(self, *args, **options):
        self.rate_limit_service = RateLimitService()
        self.ip_block_service = IPBlockService()
        self.abuse_detection_service = AbuseDetectionService()
        self.insight_service = RateLimitInsightService()
        
        self.batch_size = options.get('batch_size', 100)
        self.dry_run = options.get('dry_run', False)
        self.force = options.get('force', False)
        
        if self.dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Determine what to sync
        sync_all = options.get('all')
        sync_ip_blocks = options.get('ip_blocks')
        sync_abuse_reports = options.get('abuse_reports')
        sync_insights = options.get('insights')
        sync_exceptions = options.get('exceptions')
        cleanup = options.get('cleanup')
        vacuum = options.get('vacuum')
        
        total_synced = 0
        
        # Basic rate limit syncing
        user_id = options.get('user')
        config_id = options.get('config')
        
        if user_id:
            total_synced += self._sync_user_limits(user_id)
        elif config_id:
            total_synced += self._sync_config(config_id)
        elif sync_all:
            total_synced += self._sync_all_limits()
        
        # Advanced syncing
        if sync_ip_blocks:
            total_synced += self._sync_ip_blocks()
        
        if sync_abuse_reports:
            total_synced += self._sync_abuse_reports()
        
        if sync_insights:
            days = options.get('days', 7)
            since_date = options.get('since')
            total_synced += self._sync_insights(days, since_date)
        
        if sync_exceptions:
            total_synced += self._sync_exceptions()
        
        # Cleanup operations
        if cleanup:
            total_synced += self._cleanup_expired_data()
        
        if vacuum:
            total_synced += self._vacuum_cache()
        
        # Summary
        if total_synced > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Sync completed successfully. Total items synced: {total_synced}'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    'No items were synced. Use --help for available options.'
                )
            )
    
    def _sync_user_limits(self, user_id):
        """Sync rate limits for a specific user"""
        try:
            user = User.objects.get(id=user_id)
            
            if not self.dry_run:
                # Reset user limits
                self.rate_limit_service.reset_user_limits(user)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Rate limits synced for user: {user.username}'
                )
            )
            return 1
            
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'User with ID {user_id} not found')
            )
            return 0
    
    def _sync_config(self, config_id):
        """Sync specific rate limit config"""
        try:
            config = RateLimitConfig.objects.get(id=config_id)
            
            if not self.dry_run:
                # Clear cache for this config
                self.rate_limit_service.redis_limiter.reset_rate_limit(
                    f"config:{config.id}", config
                )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Config synced: {config.name}'
                )
            )
            return 1
            
        except RateLimitConfig.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Config with ID {config_id} not found')
            )
            return 0
    
    def _sync_all_limits(self):
        """Sync all active rate limit configs"""
        configs = RateLimitConfig.objects.filter(is_active=True)
        count = 0
        
        for config in configs:
            try:
                if not self.dry_run:
                    self.rate_limit_service.redis_limiter.reset_rate_limit(
                        f"config:{config.id}", config
                    )
                count += 1
            except Exception as e:
                logger.error(f"Failed to sync config {config.name}: {e}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Synced {count} rate limit configs'
            )
        )
        return count
    
    def _sync_ip_blocks(self):
        """Sync IP blocks to Redis cache"""
        self.stdout.write('Syncing IP blocks to cache...')
        
        blocks = IPBlockList.objects.filter(is_active=True)
        count = 0
        
        for block in blocks:
            try:
                if not self.dry_run:
                    # Cache IP block for quick lookup
                    cache_key = f"ip_block:{block.ip_address or block.subnet}"
                    cache.set(cache_key, {
                        'block_type': block.block_type,
                        'reason': block.reason,
                        'expires_at': block.expires_at.isoformat() if block.expires_at else None,
                        'permanent': block.permanent
                    }, timeout=3600)  # 1 hour cache
                
                count += 1
            except Exception as e:
                logger.error(f"Failed to sync IP block {block.id}: {e}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Synced {count} IP blocks to cache'
            )
        )
        return count
    
    def _sync_abuse_reports(self):
        """Sync abuse reports and update patterns"""
        self.stdout.write('Syncing abuse reports and updating patterns...')
        
        # Get recent abuse reports
        since = timezone.now() - timedelta(days=7)
        reports = AbuseReport.objects.filter(created_at__gte=since)
        count = 0
        
        for report in reports:
            try:
                if not self.dry_run:
                    # Update abuse patterns
                    patterns = self.abuse_detection_service.detect_abuse_patterns(
                        ip_address=report.ip_address,
                        user=report.user,
                        endpoint=report.endpoint,
                        time_window=3600
                    )
                    
                    # Cache patterns for quick lookup
                    cache_key = f"abuse_pattern:{report.ip_address}"
                    cache.set(cache_key, patterns, timeout=1800)  # 30 min cache
                
                count += 1
            except Exception as e:
                logger.error(f"Failed to sync abuse report {report.id}: {e}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Synced {count} abuse reports and patterns'
            )
        )
        return count
    
    def _sync_insights(self, days=7, since_date=None):
        """Generate and sync rate limit insights"""
        self.stdout.write(f'Generating insights for last {days} days...')
        
        if since_date:
            try:
                analysis_date = timezone.datetime.strptime(since_date, '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(
                    self.style.ERROR('Invalid date format. Use YYYY-MM-DD')
                )
                return 0
        else:
            analysis_date = timezone.now().date() - timedelta(days=1)
        
        count = 0
        
        # Generate insights for each day
        for i in range(days):
            date = analysis_date - timedelta(days=i)
            
            try:
                if not self.dry_run:
                    insight = self.insight_service.generate_daily_insights(date)
                    
                    # Cache insight data
                    cache_key = f"insight:{date.isoformat()}"
                    cache.set(cache_key, {
                        'total_requests': insight.total_requests,
                        'blocked_requests': insight.blocked_requests,
                        'health_score': insight.get_health_score(),
                        'abuse_reports_count': insight.abuse_reports_count
                    }, timeout=86400)  # 24 hour cache
                
                count += 1
            except Exception as e:
                logger.error(f"Failed to generate insights for {date}: {e}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Generated and synced {count} daily insights'
            )
        )
        return count
    
    def _sync_exceptions(self):
        """Sync rate limit exceptions"""
        self.stdout.write('Syncing rate limit exceptions...')
        
        exceptions = RateLimitException.objects.filter(is_active=True)
        count = 0
        
        for exception in exceptions:
            try:
                if not self.dry_run:
                    # Cache exception for quick lookup
                    target_key = exception.user.id if exception.user else (
                        exception.ip_address or exception.endpoint_pattern
                    )
                    cache_key = f"rate_limit_exception:{target_key}"
                    cache.set(cache_key, {
                        'exception_type': exception.exception_type,
                        'multiplier': exception.multiplier,
                        'max_requests': exception.max_requests,
                        'expires_at': exception.expires_at.isoformat() if exception.expires_at else None,
                        'permanent': exception.permanent
                    }, timeout=3600)  # 1 hour cache
                
                count += 1
            except Exception as e:
                logger.error(f"Failed to sync exception {exception.id}: {e}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Synced {count} rate limit exceptions'
            )
        )
        return count
    
    def _cleanup_expired_data(self):
        """Clean up expired blocks and old data"""
        self.stdout.write('Cleaning up expired data...')
        
        count = 0
        
        # Clean up expired IP blocks
        try:
            if not self.dry_run:
                expired_blocks = IPBlockList.objects.filter(
                    is_active=True,
                    permanent=False,
                    expires_at__lt=timezone.now()
                )
                
                for block in expired_blocks:
                    block.is_active = False
                    block.save()
                    
                    # Remove from cache
                    cache_key = f"ip_block:{block.ip_address or block.subnet}"
                    cache.delete(cache_key)
                
                count += expired_blocks.count()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Deactivated {expired_blocks.count()} expired IP blocks'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING('DRY RUN: Would clean up expired IP blocks')
                )
        except Exception as e:
            logger.error(f"Failed to cleanup expired IP blocks: {e}")
        
        # Clean up old rate limit logs
        try:
            if not self.dry_run:
                cutoff_date = timezone.now() - timedelta(days=30)
                old_logs = RateLimitLog.objects.filter(timestamp__lt=cutoff_date)
                
                # Delete in batches
                deleted_count = 0
                for i in range(0, old_logs.count(), self.batch_size):
                    batch = old_logs[i:i+self.batch_size]
                    deleted_count += batch.count()
                    batch.delete()
                
                count += deleted_count
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Deleted {deleted_count} old rate limit logs'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING('DRY RUN: Would clean up old rate limit logs')
                )
        except Exception as e:
            logger.error(f"Failed to cleanup old logs: {e}")
        
        return count
    
    def _vacuum_cache(self):
        """Vacuum and optimize Redis cache"""
        self.stdout.write('Optimizing Redis cache...')
        
        count = 0
        
        try:
            if not self.dry_run:
                # Get Redis client
                from django.core.cache import cache
                redis_client = cache.client.get_client()
                
                # Get cache stats
                info = redis_client.info()
                
                # Clean up expired keys
                cursor = '0'
                deleted_count = 0
                
                while cursor != 0:
                    cursor, keys = redis_client.scan(cursor=cursor, match='rate_limit:*', count=1000)
                    
                    if keys:
                        # Check TTL and delete expired keys
                        for key in keys:
                            ttl = redis_client.ttl(key)
                            if ttl == -2:  # Key exists but has no TTL (expired)
                                redis_client.delete(key)
                                deleted_count += 1
                
                count = deleted_count
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Vacuumed cache: deleted {deleted_count} expired keys'
                    )
                )
                
                # Show cache stats
                self.stdout.write(
                    self.style.NOTICE(
                        f'Redis stats - Used memory: {info.get("used_memory_human", "N/A")}, '
                        f'Keyspace hits: {info.get("keyspace_hits", 0)}, '
                        f'Keyspace misses: {info.get("keyspace_misses", 0)}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING('DRY RUN: Would vacuum Redis cache')
                )
        except Exception as e:
            logger.error(f"Failed to vacuum cache: {e}")
        
        return count