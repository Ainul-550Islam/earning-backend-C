"""
Management command to clean up old data in the offer routing system.

This command removes old decision logs, analytics data, and other
historical data to maintain database performance.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from offer_routing.models import (
    RoutingDecisionLog, RoutePerformanceStat, OfferExposureStat,
    RoutingInsight, UserOfferHistory
)
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Django management command to clean up old data."""
    
    help = 'Clean up old data to maintain database performance'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Delete data older than this many days (default: 90)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Clean up data only for specific tenant ID'
        )
        parser.add_argument(
            '--table',
            choices=['all', 'decisions', 'performance', 'exposure', 'insights', 'history'],
            default='all',
            help='Specific table to clean up (default: all)'
        )
    
    def handle(self, *args, **options):
        """Handle the command execution."""
        days = options['days']
        dry_run = options['dry_run']
        tenant_id = options['tenant_id']
        table = options['table']
        
        self.stdout.write(self.style.SUCCESS(f'Starting cleanup of data older than {days} days...'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            total_deleted = 0
            
            # Clean up each table type
            if table in ['all', 'decisions']:
                deleted = self._cleanup_decision_logs(cutoff_date, tenant_id, dry_run)
                total_deleted += deleted
                self.stdout.write(f'Decision logs: {"Would delete" if dry_run else "Deleted"} {deleted} records')
            
            if table in ['all', 'performance']:
                deleted = self._cleanup_performance_stats(cutoff_date, tenant_id, dry_run)
                total_deleted += deleted
                self.stdout.write(f'Performance stats: {"Would delete" if dry_run else "Deleted"} {deleted} records')
            
            if table in ['all', 'exposure']:
                deleted = self._cleanup_exposure_stats(cutoff_date, tenant_id, dry_run)
                total_deleted += deleted
                self.stdout.write(f'Exposure stats: {"Would delete" if dry_run else "Deleted"} {deleted} records')
            
            if table in ['all', 'insights']:
                deleted = self._cleanup_insights(cutoff_date, tenant_id, dry_run)
                total_deleted += deleted
                self.stdout.write(f'Insights: {"Would delete" if dry_run else "Deleted"} {deleted} records')
            
            if table in ['all', 'history']:
                deleted = self._cleanup_user_history(cutoff_date, tenant_id, dry_run)
                total_deleted += deleted
                self.stdout.write(f'User history: {"Would delete" if dry_run else "Deleted"} {deleted} records')
            
            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(f'DRY RUN: Would delete {total_deleted} total records')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully deleted {total_deleted} total records')
                )
            
            # Log completion
            logger.info(f'Data cleanup completed: {total_deleted} records deleted')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during cleanup: {e}')
            )
            logger.error(f'Data cleanup failed: {e}')
            raise
    
    def _cleanup_decision_logs(self, cutoff_date, tenant_id=None, dry_run=False):
        """Clean up old routing decision logs."""
        queryset = RoutingDecisionLog.objects.filter(created_at__lt=cutoff_date)
        
        if tenant_id:
            queryset = queryset.filter(user__tenant_id=tenant_id)
        
        if dry_run:
            return queryset.count()
        
        with transaction.atomic():
            deleted, _ = queryset.delete()
            return deleted
    
    def _cleanup_performance_stats(self, cutoff_date, tenant_id=None, dry_run=False):
        """Clean up old performance statistics."""
        queryset = RoutePerformanceStat.objects.filter(date__lt=cutoff_date)
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        if dry_run:
            return queryset.count()
        
        with transaction.atomic():
            deleted, _ = queryset.delete()
            return deleted
    
    def _cleanup_exposure_stats(self, cutoff_date, tenant_id=None, dry_run=False):
        """Clean up old exposure statistics."""
        queryset = OfferExposureStat.objects.filter(date__lt=cutoff_date)
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        if dry_run:
            return queryset.count()
        
        with transaction.atomic():
            deleted, _ = queryset.delete()
            return deleted
    
    def _cleanup_insights(self, cutoff_date, tenant_id=None, dry_run=False):
        """Clean up old routing insights."""
        queryset = RoutingInsight.objects.filter(
            created_at__lt=cutoff_date,
            is_resolved=True  # Only delete resolved insights
        )
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        if dry_run:
            return queryset.count()
        
        with transaction.atomic():
            deleted, _ = queryset.delete()
            return deleted
    
    def _cleanup_user_history(self, cutoff_date, tenant_id=None, dry_run=False):
        """Clean up old user offer history."""
        queryset = UserOfferHistory.objects.filter(created_at__lt=cutoff_date)
        
        if tenant_id:
            queryset = queryset.filter(user__tenant_id=tenant_id)
        
        if dry_run:
            return queryset.count()
        
        with transaction.atomic():
            deleted, _ = queryset.delete()
            return deleted
