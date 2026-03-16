# management/commands/cleanup_blacklist.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from api.ad_networks.models import BlacklistedIP
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Cleanup expired blacklisted IP entries'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of records to process per batch (default: 1000)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show statistics only'
        )
    
    def handle(self, *args, **options):
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        stats_only = options['stats']
        
        self.stdout.write(f"{timezone.now().strftime('%Y-%m-%d %H:%M:%S')} - Starting blacklist cleanup")
        
        if stats_only:
            stats = BlacklistedIP.get_statistics()
            self.stdout.write(self.style.SUCCESS("=== Blacklist Statistics ==="))
            self.stdout.write(f"Total entries: {stats['total_entries']}")
            self.stdout.write(f"Active entries: {stats['active_entries']}")
            self.stdout.write(f"Expired but still active: {stats['expired_but_still_active']}")
            self.stdout.write(f"Permanent blocks: {stats['permanent_blocks']}")
            self.stdout.write(f"Recent additions (7d): {stats['recent_additions_7d']}")
            
            self.stdout.write("\nActive entries by reason:")
            for item in stats['by_reason']:
                self.stdout.write(f"  {item['reason']}: {item['count']}")
            
            return
        
        if dry_run:
            now = timezone.now()
            expired_count = BlacklistedIP.objects.filter(
                is_active=True,
                expiry_date__lt=now
            ).count()
            
            self.stdout.write(self.style.WARNING("=== DRY RUN - No changes will be made ==="))
            self.stdout.write(f"Found {expired_count} expired entries that would be deactivated")
            
            if expired_count > 0:
                expired_ips = BlacklistedIP.objects.filter(
                    is_active=True,
                    expiry_date__lt=now
                ).values_list('ip_address', 'expiry_date')[:10]
                
                self.stdout.write("\nSample expired IPs:")
                for ip, expiry in expired_ips:
                    self.stdout.write(f"  {ip} (expired: {expiry.strftime('%Y-%m-%d')})")
            
            return
        
        # Actual cleanup
        self.stdout.write("Running blacklist cleanup...")
        
        try:
            result = BlacklistedIP.cleanup_expired_entries(batch_size=batch_size)
            
            if result['deactivated'] > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully deactivated {result['deactivated']} expired blacklist entries"
                    )
                )
            else:
                self.stdout.write("No expired entries found")
            
            # Show statistics after cleanup
            stats = BlacklistedIP.get_statistics()
            self.stdout.write("\n=== Post-cleanup Statistics ===")
            self.stdout.write(f"Active entries: {stats['active_entries']}")
            self.stdout.write(f"Expired but still active: {stats['expired_but_still_active']}")
            
            logger.info(f"Blacklist cleanup completed: {result}")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error during cleanup: {str(e)}")
            )
            logger.error(f"Blacklist cleanup failed: {str(e)}")
            raise