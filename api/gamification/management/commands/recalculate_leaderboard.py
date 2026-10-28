"""
Recalculate Leaderboard Management Command — Recalculate contest leaderboards.

This command recalculates leaderboard snapshots for contest cycles, supporting
full recalculation, incremental updates, and data correction scenarios.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from api.gamification.models import ContestCycle, LeaderboardSnapshot
from api.gamification.choices import ContestCycleStatus, SnapshotStatus, LeaderboardScope
from api.gamification.services import LeaderboardService
from api.gamification.exceptions import (
    ContestCycleNotFoundError,
    LeaderboardGenerationError,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to recalculate contest leaderboards.
    
    Usage:
        python manage.py recalculate_leaderboard <contest_cycle_id>
        python manage.py recalculate_leaderboard <contest_cycle_id> --scope ALL_USERS
        python manage.py recalculate_leaderboard <contest_cycle_id> --top-n 50
        python manage.py recalculate_leaderboard --list-cycles
        python manage.py recalculate_leaderboard --recalculate-all
        python manage.py recalculate_leaderboard <contest_cycle_id> --replace-existing
    """
    
    help = "Recalculate leaderboard snapshots for contest cycles"
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            'contest_cycle_id',
            type=str,
            nargs='?',
            help='Contest cycle ID to recalculate (UUID or name)'
        )
        
        parser.add_argument(
            '--scope',
            type=str,
            default='ALL_USERS',
            choices=['ALL_USERS', 'ACTIVE_USERS', 'TOP_N'],
            help='Leaderboard scope (default: ALL_USERS)'
        )
        
        parser.add_argument(
            '--top-n',
            type=int,
            default=100,
            help='Number of top entries for TOP_N scope (default: 100)'
        )
        
        parser.add_argument(
            '--replace-existing',
            action='store_true',
            help='Replace existing snapshots instead of creating new ones'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be recalculated without actually doing it'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recalculation even if validations fail'
        )
        
        parser.add_argument(
            '--list-cycles',
            action='store_true',
            help='List all contest cycles available for recalculation'
        )
        
        parser.add_argument(
            '--recalculate-all',
            action='store_true',
            help='Recalculate leaderboards for all contest cycles'
        )
        
        parser.add_argument(
            '--include-inactive',
            action='store_true',
            help='Include inactive users in recalculation'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information about the recalculation process'
        )
    
    def handle(self, *args, **options):
        """Handle the command execution."""
        self.setup_logging(options.get('verbosity', 1))
        self.verbose = options.get('verbose', False)
        
        if options['list_cycles']:
            self.list_contest_cycles()
            return
        
        if options['recalculate_all']:
            self.recalculate_all_cycles(options)
            return
        
        contest_cycle_id = options.get('contest_cycle_id')
        if not contest_cycle_id:
            raise CommandError(
                "Contest cycle ID is required unless using --list-cycles or --recalculate-all"
            )
        
        self.recalculate_single_cycle(contest_cycle_id, options)
    
    def setup_logging(self, verbosity):
        """Set up logging based on verbosity level."""
        if verbosity == 0:
            logging.getLogger().setLevel(logging.WARNING)
        elif verbosity == 1:
            logging.getLogger().setLevel(logging.INFO)
        elif verbosity >= 2:
            logging.getLogger().setLevel(logging.DEBUG)
    
    def list_contest_cycles(self):
        """List all contest cycles available for recalculation."""
        cycles = ContestCycle.objects.all()
        
        if not cycles.exists():
            self.stdout.write(self.style.WARNING("No contest cycles found."))
            return
        
        self.stdout.write(self.style.SUCCESS("Contest Cycles Available for Recalculation:"))
        self.stdout.write("-" * 80)
        
        for cycle in cycles.order_by('-start_time'):
            # Check existing snapshots
            snapshots = LeaderboardSnapshot.objects.filter(contest_cycle=cycle)
            latest_snapshot = snapshots.order_by('-created_at').first()
            
            status = cycle.status
            snapshot_info = f"Snapshots: {snapshots.count()}"
            
            if latest_snapshot:
                snapshot_info += f" (Latest: {latest_snapshot.created_at})"
            
            self.stdout.write(
                f"ID: {cycle.id}\n"
                f"Name: {cycle.name}\n"
                f"Status: {status}\n"
                f"Start: {cycle.start_time}\n"
                f"End: {cycle.end_time}\n"
                f"{snapshot_info}\n"
                f"{'-' * 40}"
            )
    
    def recalculate_all_cycles(self, options):
        """Recalculate leaderboards for all contest cycles."""
        cycles = ContestCycle.objects.all()
        
        if not cycles.exists():
            self.stdout.write(self.style.WARNING("No contest cycles found."))
            return
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("DRY RUN - No leaderboards will be recalculated:"))
            self.stdout.write("-" * 80)
            for cycle in cycles.order_by('-start_time'):
                self.stdout.write(f"Would recalculate: {cycle.name} ({cycle.id})")
            return
        
        self.stdout.write(self.style.SUCCESS(f"Recalculating leaderboards for {cycles.count()} contest cycles..."))
        
        success_count = 0
        error_count = 0
        
        for cycle in cycles.order_by('-start_time'):
            try:
                self.stdout.write(f"Processing: {cycle.name}...")
                self.recalculate_single_cycle_internal(cycle.id, options)
                success_count += 1
                self.stdout.write(self.style.SUCCESS(f"✓ Recalculated: {cycle.name}"))
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f"✗ Failed to recalculate {cycle.name}: {e}"))
        
        self.stdout.write("-" * 80)
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed: {success_count} recalculated, {error_count} failed"
            )
        )
    
    def recalculate_single_cycle(self, contest_cycle_id, options):
        """Recalculate leaderboard for a single contest cycle."""
        try:
            # Try to find by UUID first
            try:
                cycle = ContestCycle.objects.get(id=contest_cycle_id)
            except (ContestCycle.DoesNotExist, ValueError):
                # Try to find by name
                cycle = ContestCycle.objects.get(name=contest_cycle_id)
            
            if options['dry_run']:
                self.stdout.write(
                    self.style.WARNING(
                        f"DRY RUN - Would recalculate leaderboard for: {cycle.name} ({cycle.id})"
                    )
                )
                return
            
            self.recalculate_single_cycle_internal(cycle.id, options)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully recalculated leaderboard for: {cycle.name}"
                )
            )
            
        except ContestCycle.DoesNotExist:
            raise CommandError(f"Contest cycle '{contest_cycle_id}' not found")
        except Exception as e:
            raise CommandError(f"Error recalculating leaderboard: {e}")
    
    def recalculate_single_cycle_internal(self, contest_cycle_id, options):
        """Internal method to recalculate leaderboard for a single contest cycle."""
        try:
            cycle = ContestCycle.objects.get(id=contest_cycle_id)
        except ContestCycle.DoesNotExist:
            raise ContestCycleNotFoundError(f"Contest cycle {contest_cycle_id} not found")
        
        self.stdout.write(f"Recalculating leaderboard for contest: {cycle.name}")
        
        # Prepare recalculation options
        scope = options['scope']
        top_n = options['top_n']
        replace_existing = options['replace_existing']
        include_inactive = options['include_inactive']
        
        # Handle existing snapshots if replacing
        if replace_existing:
            self.replace_existing_snapshots(cycle, scope)
        
        # Generate new leaderboard
        if not options['dry_run']:
            snapshot = self.generate_leaderboard_snapshot(
                cycle, scope, top_n, include_inactive
            )
            
            self.display_recalculation_results(snapshot, options['verbose'])
        else:
            # Show what would be recalculated
            self.simulate_recalculation(cycle, scope, top_n, options['verbose'])
    
    def generate_leaderboard_snapshot(self, cycle, scope, top_n, include_inactive):
        """Generate a new leaderboard snapshot."""
        try:
            # Convert scope string to enum
            try:
                scope_enum = LeaderboardScope(scope)
            except ValueError:
                raise CommandError(f"Invalid scope: {scope}")
            
            # Generate snapshot
            snapshot = LeaderboardService.generate_snapshot(
                contest_cycle_id=cycle.id,
                scope=scope_enum,
                top_n=top_n if scope == 'TOP_N' else None,
                include_inactive=include_inactive
            )
            
            # Finalize the snapshot
            snapshot.finalize()
            
            return snapshot
            
        except LeaderboardGenerationError as e:
            raise CommandError(f"Failed to generate leaderboard snapshot: {e}")
        except Exception as e:
            raise CommandError(f"Unexpected error generating snapshot: {e}")
    
    def replace_existing_snapshots(self, cycle, scope):
        """Replace existing snapshots for the given scope."""
        existing_snapshots = LeaderboardSnapshot.objects.filter(
            contest_cycle=cycle,
            scope=scope
        )
        
        if existing_snapshots.exists():
            if self.verbose:
                self.stdout.write(f"Removing {existing_snapshots.count()} existing snapshots for scope {scope}")
            
            existing_snapshots.delete()
    
    def simulate_recalculation(self, cycle, scope, top_n, verbose=False):
        """Simulate leaderboard recalculation without actually doing it."""
        self.stdout.write(self.style.WARNING("DRY RUN - Leaderboard Recalculation Simulation:"))
        self.stdout.write("-" * 60)
        
        self.stdout.write(
            f"Contest: {cycle.name}\n"
            f"Scope: {scope}\n"
            f"Top N: {top_n if scope == 'TOP_N' else 'N/A'}\n"
            f"Replace Existing: Yes\n"
        )
        
        # Estimate number of entries (simplified)
        estimated_entries = self.estimate_leaderboard_entries(cycle, scope, top_n)
        
        self.stdout.write(
            f"Estimated Entries: {estimated_entries}\n"
            f"Would Create: 1 new snapshot\n"
            f"Would Replace: {self.count_existing_snapshots(cycle, scope)} existing snapshots"
        )
        
        if verbose:
            self.stdout.write("\nEstimated Top 10 Entries:")
            self.stdout.write("-" * 40)
            # This would normally query actual data, but we'll simulate
            for i in range(1, min(11, estimated_entries + 1)):
                self.stdout.write(f"{i:2d}. User_{i:03d}                {1000 - i * 10:8} points")
    
    def display_recalculation_results(self, snapshot, verbose=False):
        """Display the results of leaderboard recalculation."""
        self.stdout.write(self.style.SUCCESS("Leaderboard Recalculation Results:"))
        self.stdout.write("-" * 60)
        
        self.stdout.write(
            f"Contest Cycle: {snapshot.contest_cycle.name}\n"
            f"Snapshot ID: {snapshot.id}\n"
            f"Scope: {snapshot.scope}\n"
            f"Status: {snapshot.status}\n"
            f"Entries: {len(snapshot.snapshot_data)}\n"
            f"Created: {snapshot.created_at}\n"
            f"Finalized: {snapshot.finalized_at}"
        )
        
        if verbose and snapshot.snapshot_data:
            self.stdout.write("\nTop 10 Entries:")
            self.stdout.write("-" * 40)
            
            for i, entry in enumerate(snapshot.snapshot_data[:10], 1):
                username = entry.get('username', 'Unknown')
                points = entry.get('total_points', 0)
                rank = entry.get('rank', i)
                user_id = entry.get('user_id', 'N/A')
                
                self.stdout.write(
                    f"{rank:2d}. {username:<20} {points:>8} points (ID: {user_id})"
                )
            
            if len(snapshot.snapshot_data) > 10:
                self.stdout.write(f"... and {len(snapshot.snapshot_data) - 10} more entries")
    
    def estimate_leaderboard_entries(self, cycle, scope, top_n):
        """Estimate number of entries for the leaderboard."""
        # This is a simplified estimation - in practice, you'd query actual data
        if scope == 'TOP_N':
            return top_n
        elif scope == 'ALL_USERS':
            return 1000  # Simplified estimation
        elif scope == 'ACTIVE_USERS':
            return 500  # Simplified estimation
        return 100
    
    def count_existing_snapshots(self, cycle, scope):
        """Count existing snapshots for the given scope."""
        return LeaderboardSnapshot.objects.filter(
            contest_cycle=cycle,
            scope=scope
        ).count()
    
    def validate_recalculation_request(self, cycle, scope, force=False):
        """Validate that the recalculation request is valid."""
        # Check if contest is in a valid state
        if not force and cycle.status not in [
            ContestCycleStatus.ACTIVE,
            ContestCycleStatus.COMPLETED
        ]:
            raise CommandError(
                f"Contest cycle {cycle.name} is not in a valid state for recalculation "
                f"(status: {cycle.status})"
            )
        
        # Check if scope is valid
        valid_scopes = ['ALL_USERS', 'ACTIVE_USERS', 'TOP_N']
        if scope not in valid_scopes:
            raise CommandError(f"Invalid scope: {scope}. Valid scopes: {', '.join(valid_scopes)}")
        
        return True
    
    def get_recalculation_summary(self, cycle, scope, top_n):
        """Get a summary of what will be recalculated."""
        existing_count = self.count_existing_snapshots(cycle, scope)
        estimated_entries = self.estimate_leaderboard_entries(cycle, scope, top_n)
        
        return {
            'contest_name': cycle.name,
            'scope': scope,
            'top_n': top_n if scope == 'TOP_N' else None,
            'existing_snapshots': existing_count,
            'estimated_entries': estimated_entries,
            'will_replace': existing_count > 0,
        }
