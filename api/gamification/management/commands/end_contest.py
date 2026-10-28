"""
End Contest Management Command — Manually end contest cycles.

This command allows administrators to manually end active contest cycles,
generate final leaderboards, and transition cycles to completed status.
"""

from __future__ import annotations

import logging
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from api.gamification.models import ContestCycle, LeaderboardSnapshot
from api.gamification.choices import ContestCycleStatus, SnapshotStatus
from api.gamification.services import ContestCycleService, LeaderboardService
from api.gamification.exceptions import (
    ContestCycleNotFoundError,
    ContestCycleStateError,
    LeaderboardGenerationError,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to manually end contest cycles.
    
    Usage:
        python manage.py end_contest <contest_cycle_id>
        python manage.py end_contest <contest_cycle_id> --generate-leaderboard
        python manage.py end_contest <contest_cycle_id> --force
        python manage.py end_contest --list-active
        python manage.py end_contest --end-all-active
    """
    
    help = "Manually end contest cycles and optionally generate final leaderboards"
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            'contest_cycle_id',
            type=str,
            nargs='?',
            help='Contest cycle ID to end (UUID or name)'
        )
        
        parser.add_argument(
            '--generate-leaderboard',
            action='store_true',
            help='Generate final leaderboard before ending contest'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force end even if contest is not in proper state'
        )
        
        parser.add_argument(
            '--list-active',
            action='store_true',
            help='List all active contest cycles'
        )
        
        parser.add_argument(
            '--end-all-active',
            action='store_true',
            help='End all active contest cycles'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually ending contests'
        )
        
        parser.add_argument(
            '--top-n',
            type=int,
            default=100,
            help='Number of top entries for leaderboard (default: 100)'
        )
    
    def handle(self, *args, **options):
        """Handle the command execution."""
        self.setup_logging(options.get('verbosity', 1))
        
        if options['list_active']:
            self.list_active_contests()
            return
        
        if options['end_all_active']:
            self.end_all_active_contests(options)
            return
        
        contest_cycle_id = options.get('contest_cycle_id')
        if not contest_cycle_id:
            raise CommandError("Contest cycle ID is required unless using --list-active or --end-all-active")
        
        self.end_single_contest(contest_cycle_id, options)
    
    def setup_logging(self, verbosity):
        """Set up logging based on verbosity level."""
        if verbosity == 0:
            logging.getLogger().setLevel(logging.WARNING)
        elif verbosity == 1:
            logging.getLogger().setLevel(logging.INFO)
        elif verbosity >= 2:
            logging.getLogger().setLevel(logging.DEBUG)
    
    def list_active_contests(self):
        """List all active contest cycles."""
        active_cycles = ContestCycle.objects.filter(status=ContestCycleStatus.ACTIVE)
        
        if not active_cycles.exists():
            self.stdout.write(self.style.WARNING("No active contest cycles found."))
            return
        
        self.stdout.write(self.style.SUCCESS("Active Contest Cycles:"))
        self.stdout.write("-" * 80)
        
        for cycle in active_cycles.order_by('start_time'):
            self.stdout.write(
                f"ID: {cycle.id}\n"
                f"Name: {cycle.name}\n"
                f"Status: {cycle.status}\n"
                f"Start: {cycle.start_time}\n"
                f"End: {cycle.end_time}\n"
                f"Multipler: {cycle.points_multiplier}x\n"
                f"{'-' * 40}"
            )
    
    def end_all_active_contests(self, options):
        """End all active contest cycles."""
        active_cycles = ContestCycle.objects.filter(status=ContestCycleStatus.ACTIVE)
        
        if not active_cycles.exists():
            self.stdout.write(self.style.WARNING("No active contest cycles found."))
            return
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("DRY RUN - No contests will be ended:"))
            self.stdout.write("-" * 80)
            for cycle in active_cycles:
                self.stdout.write(f"Would end: {cycle.name} ({cycle.id})")
            return
        
        self.stdout.write(self.style.SUCCESS(f"Ending {active_cycles.count()} active contest cycles..."))
        
        success_count = 0
        error_count = 0
        
        for cycle in active_cycles.order_by('start_time'):
            try:
                self.stdout.write(f"Processing: {cycle.name}...")
                self.end_single_contest_internal(cycle.id, options)
                success_count += 1
                self.stdout.write(self.style.SUCCESS(f"✓ Ended: {cycle.name}"))
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f"✗ Failed to end {cycle.name}: {e}"))
        
        self.stdout.write("-" * 80)
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed: {success_count} ended, {error_count} failed"
            )
        )
    
    def end_single_contest(self, contest_cycle_id, options):
        """End a single contest cycle."""
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
                        f"DRY RUN - Would end contest: {cycle.name} ({cycle.id})"
                    )
                )
                return
            
            self.end_single_contest_internal(cycle.id, options)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully ended contest: {cycle.name}"
                )
            )
            
        except ContestCycle.DoesNotExist:
            raise CommandError(f"Contest cycle '{contest_cycle_id}' not found")
        except Exception as e:
            raise CommandError(f"Error ending contest: {e}")
    
    def end_single_contest_internal(self, contest_cycle_id, options):
        """Internal method to end a single contest cycle."""
        try:
            cycle = ContestCycle.objects.get(id=contest_cycle_id)
        except ContestCycle.DoesNotExist:
            raise ContestCycleNotFoundError(f"Contest cycle {contest_cycle_id} not found")
        
        # Validate contest state
        if not options['force'] and cycle.status != ContestCycleStatus.ACTIVE:
            raise ContestCycleStateError(
                f"Contest cycle {cycle.name} is not active (current status: {cycle.status})"
            )
        
        self.stdout.write(f"Processing contest: {cycle.name}")
        
        # Generate leaderboard if requested
        if options['generate_leaderboard']:
            self.generate_final_leaderboard(cycle, options['top_n'])
        
        # End the contest
        if not options['dry_run']:
            cycle.end_contest()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Contest '{cycle.name}' ended successfully"
                )
                )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN - Would end contest: {cycle.name}"
                )
            )
    
    def generate_final_leaderboard(self, cycle, top_n):
        """Generate final leaderboard for the contest."""
        self.stdout.write(f"Generating final leaderboard (top {top_n})...")
        
        try:
            # Generate leaderboard snapshot
            snapshot = LeaderboardService.generate_snapshot(
                contest_cycle_id=cycle.id,
                scope="ALL_USERS",
                top_n=top_n
            )
            
            # Finalize the snapshot
            snapshot.finalize()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Generated leaderboard with {len(snapshot.snapshot_data)} entries"
                )
            )
            
            # Display top 10 entries
            if snapshot.snapshot_data:
                self.stdout.write("\nTop 10 Entries:")
                self.stdout.write("-" * 60)
                for i, entry in enumerate(snapshot.snapshot_data[:10], 1):
                    username = entry.get('username', 'Unknown')
                    points = entry.get('total_points', 0)
                    rank = entry.get('rank', i)
                    self.stdout.write(
                        f"{rank:2d}. {username:<20} {points:>8} points"
                    )
                self.stdout.write("-" * 60)
            
        except LeaderboardGenerationError as e:
            if not options['force']:
                raise CommandError(f"Failed to generate leaderboard: {e}")
            
            self.stdout.write(
                self.style.WARNING(
                    f"⚠ Leaderboard generation failed, continuing anyway: {e}"
                )
            )
        except Exception as e:
            if not options['force']:
                raise CommandError(f"Unexpected error generating leaderboard: {e}")
            
            self.stdout.write(
                self.style.WARNING(
                    f"⚠ Unexpected error generating leaderboard, continuing anyway: {e}"
                )
            )
    
    def validate_contest_state(self, cycle, force=False):
        """Validate that contest is in a proper state to be ended."""
        if force:
            return True
        
        if cycle.status != ContestCycleStatus.ACTIVE:
            raise ContestCycleStateError(
                f"Contest cycle {cycle.name} is not active (current status: {cycle.status})"
            )
        
        # Check if contest has ended
        if cycle.end_time and cycle.end_time > timezone.now():
            raise ContestCycleStateError(
                f"Contest cycle {cycle.name} has not yet ended (end time: {cycle.end_time})"
            )
        
        return True
