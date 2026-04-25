"""
Management command to reset daily caps for offer routing system.

This command resets daily caps for all users and offers,
preparing them for the new day's routing operations.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from offer_routing.services.cap import cap_service
from offer_routing.models import UserOfferCap, OfferRoutingCap
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Django management command to reset daily caps."""
    
    help = 'Reset daily caps for all users and offers'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be reset without actually resetting'
        )
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Reset caps only for specific tenant ID'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reset even if caps were recently reset'
        )
    
    def handle(self, *args, **options):
        """Handle the command execution."""
        dry_run = options['dry_run']
        tenant_id = options['tenant_id']
        force = options['force']
        
        self.stdout.write(self.style.SUCCESS('Starting daily cap reset...'))
        
        try:
            if dry_run:
                self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
            
            # Reset caps
            reset_count = self._reset_daily_caps(tenant_id, force, dry_run)
            
            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(f'DRY RUN: Would reset {reset_count} caps')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully reset {reset_count} caps')
                )
            
            # Log completion
            logger.info(f'Daily cap reset completed: {reset_count} caps reset')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error resetting caps: {e}')
            )
            logger.error(f'Daily cap reset failed: {e}')
            raise
    
    def _reset_daily_caps(self, tenant_id=None, force=False, dry_run=False):
        """Reset daily caps with optional filtering."""
        reset_count = 0
        
        with transaction.atomic():
            # Get caps to reset
            queryset = UserOfferCap.objects.filter(cap_type='daily')
            
            if tenant_id:
                queryset = queryset.filter(user__tenant_id=tenant_id)
            
            if not force:
                # Only reset caps that haven't been reset today
                today = timezone.now().date()
                queryset = queryset.exclude(reset_at__date=today)
            
            caps_to_reset = queryset.select_for_update()
            
            if dry_run:
                reset_count = caps_to_reset.count()
            else:
                for cap in caps_to_reset:
                    cap.reset_daily_cap()
                    reset_count += 1
                    
                    if reset_count % 1000 == 0:
                        self.stdout.write(f'Reset {reset_count} caps...')
        
        return reset_count
