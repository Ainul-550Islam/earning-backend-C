from django.core.management.base import BaseCommand
from api.rate_limit.services.RateLimitService import RateLimitService
from api.rate_limit.models import RateLimitConfig, UserRateLimitProfile
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync rate limits from database to Redis cache'
    
    def add_arguments(self, parser):
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
            help='Sync all configs'
        )
    
    def handle(self, *args, **options):
        rate_limit_service = RateLimitService()
        
        user_id = options.get('user')
        config_id = options.get('config')
        sync_all = options.get('all')
        
        if user_id:
            # Sync for specific user
            self._sync_user_limits(user_id, rate_limit_service)
        elif config_id:
            # Sync specific config
            self._sync_config(config_id, rate_limit_service)
        elif sync_all:
            # Sync all active configs
            self._sync_all_limits(rate_limit_service)
        else:
            self.stdout.write(
                self.style.WARNING(
                    'Please specify --user, --config, or --all'
                )
            )
    
    def _sync_user_limits(self, user_id, rate_limit_service):
        """Sync rate limits for a specific user"""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            
            # Reset user limits
            rate_limit_service.reset_user_limits(user)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Rate limits synced for user: {user.username}'
                )
            )
            
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'User with ID {user_id} not found')
            )
    
    def _sync_config(self, config_id, rate_limit_service):
        """Sync specific rate limit config"""
        try:
            config = RateLimitConfig.objects.get(id=config_id)
            
            # Clear cache for this config
            rate_limit_service.redis_limiter.reset_rate_limit(
                f"config:{config.id}", config
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Config synced: {config.name}'
                )
            )
            
        except RateLimitConfig.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Config with ID {config_id} not found')
            )
    
    def _sync_all_limits(self, rate_limit_service):
        """Sync all active rate limit configs"""
        configs = RateLimitConfig.objects.filter(is_active=True)
        count = 0
        
        for config in configs:
            try:
                rate_limit_service.redis_limiter.reset_rate_limit(
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