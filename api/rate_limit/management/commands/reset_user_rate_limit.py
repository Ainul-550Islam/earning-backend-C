"""
reset_user_rate_limit.py - Management command to reset user rate limit manually.

This command allows administrators to reset rate limit counters for specific users,
clear their rate limit history, and reset their user profile statistics.
"""
import logging
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone

from api.rate_limit.models import UserRateLimitProfile, RateLimitLog
from api.rate_limit.services.RedisRateLimiter import RedisRateLimiter

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Reset rate limit counters and statistics for specific users'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='Reset rate limit for specific user ID'
        )
        parser.add_argument(
            '--username',
            type=str,
            help='Reset rate limit for specific username'
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Reset rate limit for specific email address'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Reset rate limit for all users (USE WITH CAUTION)'
        )
        parser.add_argument(
            '--clear-redis',
            action='store_true',
            help='Clear Redis rate limit keys for the user(s)'
        )
        parser.add_argument(
            '--reset-profile',
            action='store_true',
            default=True,
            help='Reset user rate limit profile statistics'
        )
        parser.add_argument(
            '--delete-logs',
            action='store_true',
            help='Delete all rate limit logs for the user(s)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be reset without actually doing it'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skip confirmation prompt'
        )
    
    def handle(self, *args, **options):
        """Execute the reset command."""
        users = []
        
        # Find target users
        if options['all']:
            users = User.objects.all()
            self.stdout.write(
                self.style.WARNING(f"Found {users.count()} users to reset")
            )
        elif options['user_id']:
            try:
                user = User.objects.get(id=options['user_id'])
                users = [user]
                self.stdout.write(
                    self.style.SUCCESS(f"Found user: {user.username} (ID: {user.id})")
                )
            except User.DoesNotExist:
                raise CommandError(f"User with ID {options['user_id']} not found")
        elif options['username']:
            try:
                user = User.objects.get(username=options['username'])
                users = [user]
                self.stdout.write(
                    self.style.SUCCESS(f"Found user: {user.username} (ID: {user.id})")
                )
            except User.DoesNotExist:
                raise CommandError(f"User with username '{options['username']}' not found")
        elif options['email']:
            try:
                user = User.objects.get(email=options['email'])
                users = [user]
                self.stdout.write(
                    self.style.SUCCESS(f"Found user: {user.username} (ID: {user.id})")
                )
            except User.DoesNotExist:
                raise CommandError(f"User with email '{options['email']}' not found")
        else:
            raise CommandError(
                "Please specify --user-id, --username, --email, or --all"
            )
        
        # Show what will be reset
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.WARNING("RESET OPERATIONS TO PERFORM:"))
        self.stdout.write("="*60)
        
        for user in users:
            self.stdout.write(f"\n👤 User: {user.username} (ID: {user.id})")
            
            # Check rate limit profile
            try:
                profile = UserRateLimitProfile.objects.get(user=user)
                self.stdout.write(f"   📊 Profile: {profile.total_requests} requests, {profile.blocked_requests} blocked")
            except UserRateLimitProfile.DoesNotExist:
                self.stdout.write("   📊 Profile: Not found")
            
            # Count rate limit logs
            log_count = RateLimitLog.objects.filter(user=user).count()
            self.stdout.write(f"   📝 Logs: {log_count} entries")
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.WARNING("ACTIONS:"))
        self.stdout.write("="*60)
        
        if options['reset_profile']:
            self.stdout.write("   ✅ Reset user rate limit profile statistics")
        if options['clear_redis']:
            self.stdout.write("   ✅ Clear Redis rate limit keys")
        if options['delete_logs']:
            self.stdout.write("   ✅ Delete rate limit logs")
        
        # Confirmation
        if not options['confirm'] and not options['dry_run']:
            self.stdout.write("\n" + "="*60)
            confirm = input(
                self.style.WARNING(
                    "Are you sure you want to proceed? Type 'yes' to continue: "
                )
            )
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR("Operation cancelled."))
                return
        
        # Execute operations
        if options['dry_run']:
            self.stdout.write("\n" + self.style.SUCCESS("DRY RUN - No changes made"))
            return
        
        redis_limiter = RedisRateLimiter()
        reset_count = 0
        
        for user in users:
            self.stdout.write(f"\n🔄 Resetting user: {user.username}")
            
            try:
                # Reset rate limit profile
                if options['reset_profile']:
                    profile, created = UserRateLimitProfile.objects.get_or_create(user=user)
                    profile.total_requests = 0
                    profile.blocked_requests = 0
                    profile.api_health_score = 100.0
                    profile.suspicion_score = 0.0
                    profile.save()
                    self.stdout.write(f"   ✅ Profile reset")
                
                # Clear Redis keys
                if options['clear_redis']:
                    self._clear_redis_keys(redis_limiter, user)
                    self.stdout.write(f"   ✅ Redis keys cleared")
                
                # Delete logs
                if options['delete_logs']:
                    deleted_count = RateLimitLog.objects.filter(user=user).delete()[0]
                    self.stdout.write(f"   ✅ Deleted {deleted_count} log entries")
                
                reset_count += 1
                self.stdout.write(f"   ✅ User reset completed")
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"   ❌ Error resetting user: {e}")
                )
                logger.error(f"Error resetting user {user.id}: {e}")
        
        # Summary
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS(f"✅ Successfully reset {reset_count} user(s)"))
        self.stdout.write("="*60)
        
        if options['clear_redis']:
            self.stdout.write(
                self.style.WARNING(
                    "Note: Some Redis keys may persist until their natural expiration."
                )
            )
    
    def _clear_redis_keys(self, redis_limiter, user):
        """Clear all Redis rate limit keys for a user."""
        try:
            # Common rate limit key patterns
            patterns = [
                f"user:{user.id}:*",
                f"rate_limit:user:{user.id}:*",
                f"token_bucket:user:{user.id}:*",
                f"leaky_bucket:user:{user.id}:*",
                f"fixed_window:user:{user.id}:*",
                f"withdrawal_requests:{user.id}:*",
            ]
            
            cleared_count = 0
            for pattern in patterns:
                try:
                    keys = redis_limiter.redis_client.keys(pattern)
                    if keys:
                        redis_limiter.redis_client.delete(*keys)
                        cleared_count += len(keys)
                except Exception as e:
                    logger.warning(f"Error clearing Redis pattern {pattern}: {e}")
            
            return cleared_count
            
        except Exception as e:
            logger.error(f"Error clearing Redis keys for user {user.id}: {e}")
            return 0
