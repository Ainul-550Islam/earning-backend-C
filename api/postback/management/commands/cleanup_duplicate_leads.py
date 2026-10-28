"""
cleanup_duplicate_leads.py – Management command to clean up duplicate leads.

This command provides comprehensive cleanup functionality for duplicate lead entries
with various filtering options, batch processing, and safety mechanisms.
"""
import logging
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from api.postback.models import DuplicateLeadCheck, NetworkPostbackConfig, PostbackLog
from api.postback.choices import DeduplicationWindow

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Management command to clean up duplicate leads."""

    help = "Clean up duplicate lead entries with various filtering options"

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--network',
            type=str,
            help='Network key to filter duplicates (optional)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Clean up duplicates older than N days (default: 30)'
        )
        parser.add_argument(
            '--hours',
            type=int,
            help='Clean up duplicates older than N hours (overrides --days)'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Maximum number of duplicates to delete (optional)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Process in batches of N duplicates (default: 1000)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force cleanup without confirmation prompts'
        )
        parser.add_argument(
            '--keep-recent',
            type=int,
            help='Keep the most recent N duplicates per lead (default: 1)'
        )
        parser.add_argument(
            '--network-status',
            type=str,
            choices=['ACTIVE', 'INACTIVE', 'ALL'],
            default='ALL',
            help='Filter by network status (default: ALL)'
        )
        parser.add_argument(
            '--exclude-networks',
            type=str,
            help='Comma-separated list of network keys to exclude'
        )
        parser.add_argument(
            '--include-networks',
            type=str,
            help='Comma-separated list of network keys to include only'
        )
        parser.add_argument(
            '--backup',
            action='store_true',
            help='Create backup of duplicates before deletion'
        )
        parser.add_argument(
            '--stats-only',
            action='store_true',
            help='Show statistics only, no cleanup'
        )

    def handle(self, *args, **options):
        """Handle the command execution."""
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        
        # Parse time range
        if options['hours']:
            cutoff_time = timezone.now() - timedelta(hours=options['hours'])
        else:
            cutoff_time = timezone.now() - timedelta(days=options['days'])
        
        # Build queryset
        queryset = self._build_queryset(options, cutoff_time)
        
        # Get statistics
        stats = self._get_statistics(queryset, cutoff_time)
        
        if options['stats_only']:
            self._print_statistics(stats, options)
            return
        
        if stats['total_duplicates'] == 0:
            self.stdout.write(
                self.style.SUCCESS("No duplicate leads found matching the criteria.")
            )
            return
        
        # Show statistics and get confirmation
        self._print_statistics(stats, options)
        
        if not options['dry_run'] and not options['force']:
            if not self._confirm_cleanup(stats):
                self.stdout.write("Cleanup cancelled.")
                return
        
        # Perform cleanup
        self._perform_cleanup(queryset, options, stats)

    def _build_queryset(self, options, cutoff_time):
        """Build the queryset for duplicate leads to clean up."""
        queryset = DuplicateLeadCheck.objects.filter(
            first_seen_at__lt=cutoff_time
        ).select_related('network', 'postback_log')
        
        # Filter by network
        if options['network']:
            try:
                network = NetworkPostbackConfig.objects.get(network_key=options['network'])
                queryset = queryset.filter(network=network)
            except NetworkPostbackConfig.DoesNotExist:
                raise CommandError(f"Network with key '{options['network']}' not found")
        
        # Filter by network status
        if options['network_status'] != 'ALL':
            from api.postback.choices import ValidatorStatus
            status = ValidatorStatus(options['network_status'])
            queryset = queryset.filter(network__status=status)
        
        # Exclude networks
        if options['exclude_networks']:
            exclude_keys = [k.strip() for k in options['exclude_networks'].split(',')]
            queryset = queryset.exclude(network__network_key__in=exclude_keys)
        
        # Include only specific networks
        if options['include_networks']:
            include_keys = [k.strip() for k in options['include_networks'].split(',')]
            queryset = queryset.filter(network__network_key__in=include_keys)
        
        # Order by first_seen_at (oldest first)
        queryset = queryset.order_by('first_seen_at')
        
        return queryset

    def _get_statistics(self, queryset, cutoff_time):
        """Get statistics about duplicate leads."""
        total_duplicates = queryset.count()
        
        # Group by network
        network_stats = {}
        for duplicate in queryset[:1000]:  # Sample for performance
            key = duplicate.network.network_key
            if key not in network_stats:
                network_stats[key] = {
                    'count': 0,
                    'oldest': duplicate.first_seen_at,
                    'newest': duplicate.first_seen_at,
                    'network_name': duplicate.network.name
                }
            network_stats[key]['count'] += 1
            if duplicate.first_seen_at < network_stats[key]['oldest']:
                network_stats[key]['oldest'] = duplicate.first_seen_at
            if duplicate.first_seen_at > network_stats[key]['newest']:
                network_stats[key]['newest'] = duplicate.first_seen_at
        
        # Get lead_id statistics
        lead_stats = {}
        for duplicate in queryset[:1000]:  # Sample for performance
            lead_id = duplicate.lead_id
            if lead_id not in lead_stats:
                lead_stats[lead_id] = 0
            lead_stats[lead_id] += 1
        
        # Calculate duplicates per lead
        duplicates_per_lead = {}
        for lead_id, count in lead_stats.items():
            if count not in duplicates_per_lead:
                duplicates_per_lead[count] = 0
            duplicates_per_lead[count] += 1
        
        return {
            'total_duplicates': total_duplicates,
            'cutoff_time': cutoff_time,
            'network_stats': network_stats,
            'unique_leads': len(lead_stats),
            'duplicates_per_lead': duplicates_per_lead,
            'sample_size': min(total_duplicates, 1000)
        }

    def _print_statistics(self, stats, options):
        """Print duplicate statistics."""
        self.stdout.write("\n" + "="*60)
        self.stdout.write("DUPLICATE LEADS STATISTICS")
        self.stdout.write("="*60)
        
        self.stdout.write(f"Total duplicates: {stats['total_duplicates']}")
        self.stdout.write(f"Unique leads: {stats['unique_leads']}")
        self.stdout.write(f"Cutoff time: {stats['cutoff_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        if stats['network_stats']:
            self.stdout.write("\nBreakdown by network:")
            for network_key, data in sorted(stats['network_stats'].items()):
                self.stdout.write(
                    f"  {network_key} ({data['network_name']}): "
                    f"{data['count']} duplicates"
                )
                self.stdout.write(
                    f"    Oldest: {data['oldest'].strftime('%Y-%m-%d %H:%M:%S')}"
                )
                self.stdout.write(
                    f"    Newest: {data['newest'].strftime('%Y-%m-%d %H:%M:%S')}"
                )
        
        if stats['duplicates_per_lead']:
            self.stdout.write("\nDuplicates per lead:")
            for count, leads in sorted(stats['duplicates_per_lead'].items()):
                self.stdout.write(f"  {count} duplicates: {leads} leads")
        
        if stats['total_duplicates'] > stats['sample_size']:
            self.stdout.write(f"\nNote: Statistics based on sample of {stats['sample_size']} duplicates")

    def _confirm_cleanup(self, stats):
        """Get user confirmation for cleanup."""
        self.stdout.write("\n" + "="*50)
        self.stdout.write("CLEANUP CONFIRMATION")
        self.stdout.write("="*50)
        
        self.stdout.write(
            self.style.WARNING(
                f"This will delete {stats['total_duplicates']} duplicate lead entries."
            )
        )
        self.stdout.write("This action cannot be undone!")
        
        if stats['network_stats']:
            self.stdout.write("\nNetworks affected:")
            for network_key, data in stats['network_stats'].items():
                self.stdout.write(f"  - {network_key}: {data['count']} duplicates")
        
        response = input("\nAre you sure you want to continue? (yes/no): ")
        return response.lower().startswith('y')

    def _perform_cleanup(self, queryset, options, stats):
        """Perform the actual cleanup."""
        batch_size = options['batch_size']
        total_count = stats['total_duplicates']
        deleted_count = 0
        backup_count = 0
        
        # Apply limit if specified
        if options['limit'] and total_count > options['limit']:
            queryset = queryset[:options['limit']]
            total_count = options['limit']
        
        self.stdout.write(f"\nDeleting {total_count} duplicate leads in batches of {batch_size}...")
        
        # Create backup if requested
        backup_data = []
        if options['backup']:
            self.stdout.write("Creating backup...")
            for duplicate in queryset:
                backup_data.append({
                    'id': str(duplicate.id),
                    'network_key': duplicate.network.network_key,
                    'lead_id': duplicate.lead_id,
                    'first_seen_at': duplicate.first_seen_at.isoformat(),
                    'postback_log_id': str(duplicate.postback_log.id) if duplicate.postback_log else None
                })
        
            # Save backup to file
            import json
            backup_filename = f"duplicate_leads_backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(backup_filename, 'w') as f:
                json.dump(backup_data, f, indent=2)
            self.stdout.write(f"Backup saved to {backup_filename}")
            backup_count = len(backup_data)
        
        # Process in batches
        for i in range(0, total_count, batch_size):
            batch = queryset[i:i + batch_size]
            batch_ids = [duplicate.id for duplicate in batch]
            
            if options['dry_run']:
                self.stdout.write(f"DRY RUN: Would delete {len(batch_ids)} duplicates")
                deleted_count += len(batch_ids)
            else:
                with transaction.atomic():
                    deleted, _ = DuplicateLeadCheck.objects.filter(id__in=batch_ids).delete()
                    deleted_count += deleted
                
                self.stdout.write(
                    f"Deleted batch {i//batch_size + 1}/{(total_count + batch_size - 1)//batch_size} "
                    f"({deleted} duplicates)"
                )
        
        # Final summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write("CLEANUP SUMMARY")
        self.stdout.write("="*50)
        
        if options['dry_run']:
            self.stdout.write(f"DRY RUN: Would have deleted {deleted_count} duplicate leads")
        else:
            self.stdout.write(f"Deleted: {deleted_count} duplicate leads")
            if backup_count > 0:
                self.stdout.write(f"Backed up: {backup_count} entries")
        
        # Show remaining duplicates
        remaining = DuplicateLeadCheck.objects.count()
        self.stdout.write(f"Remaining duplicates in system: {remaining}")
        
        if not options['dry_run'] and deleted_count > 0:
            self.stdout.write(
                self.style.SUCCESS("\nCleanup completed successfully!")
            )

    def _cleanup_by_keep_recent(self, queryset, keep_recent):
        """Clean up duplicates while keeping the most recent N per lead."""
        # Group by lead_id and keep only the most recent
        lead_groups = {}
        for duplicate in queryset:
            if duplicate.lead_id not in lead_groups:
                lead_groups[duplicate.lead_id] = []
            lead_groups[duplicate.lead_id].append(duplicate)
        
        # Determine which to delete (keep most recent N)
        to_delete = []
        for lead_id, duplicates in lead_groups.items():
            # Sort by first_seen_at (newest first)
            duplicates.sort(key=lambda x: x.first_seen_at, reverse=True)
            
            # Keep the most recent N, mark others for deletion
            if len(duplicates) > keep_recent:
                to_delete.extend(duplicates[keep_recent:])
        
        return to_delete

    def _cleanup_by_deduplication_window(self, queryset):
        """Clean up duplicates based on network deduplication windows."""
        to_delete = []
        
        for duplicate in queryset:
            network = duplicate.network
            
            # Check if duplicate is outside the deduplication window
            if network.dedup_window == DeduplicationWindow.FOREVER:
                continue  # Never delete FOREVER duplicates
            elif network.dedup_window == DeduplicationWindow.TWENTY_FOUR_HOURS:
                cutoff = timezone.now() - timedelta(hours=24)
            elif network.dedup_window == DeduplicationWindow.SEVEN_DAYS:
                cutoff = timezone.now() - timedelta(days=7)
            elif network.deduplication_window == DeduplicationWindow.THIRTY_DAYS:
                cutoff = timezone.now() - timedelta(days=30)
            else:
                continue  # Unknown window type, skip
            
            if duplicate.first_seen_at < cutoff:
                to_delete.append(duplicate)
        
        return to_delete

    def _generate_cleanup_report(self, stats, options):
        """Generate a detailed cleanup report."""
        report = {
            'timestamp': timezone.now().isoformat(),
            'cleanup_options': {
                'dry_run': options['dry_run'],
                'days': options['days'],
                'hours': options['hours'],
                'limit': options['limit'],
                'batch_size': options['batch_size'],
                'backup': options['backup']
            },
            'statistics': stats,
            'recommendations': []
        }
        
        # Add recommendations
        if stats['total_duplicates'] > 10000:
            report['recommendations'].append(
                "Consider reducing deduplication window to improve performance"
            )
        
        if stats['duplicates_per_lead']:
            max_duplicates = max(stats['duplicates_per_lead'].keys())
            if max_duplicates > 10:
                report['recommendations'].append(
                    f"Some leads have {max_duplicates} duplicates - investigate potential integration issues"
                )
        
        # Save report
        import json
        report_filename = f"cleanup_report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.stdout.write(f"Detailed report saved to {report_filename}")
        return report
