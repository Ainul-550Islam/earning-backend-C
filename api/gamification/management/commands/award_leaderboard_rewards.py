"""
Award Leaderboard Rewards Management Command — Process top-N rewards distribution.

This command processes and distributes rewards for contest winners based on
leaderboard rankings. It supports both dry-run mode and actual reward distribution.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.gamification.models import ContestCycle, ContestReward, UserAchievement
from api.gamification.choices import ContestCycleStatus, RewardType
from api.gamification.services import LeaderboardRewardService
from api.gamification.exceptions import (
    ContestCycleNotFoundError,
    ContestCycleStateError,
    LeaderboardGenerationError,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to award leaderboard rewards to contest winners.
    
    Usage:
        python manage.py award_leaderboard_rewards <contest_cycle_id>
        python manage.py award_leaderboard_rewards <contest_cycle_id> --snapshot-id <snapshot_id>
        python manage.py award_leaderboard_rewards <contest_cycle_id> --dry-run
        python manage.py award_leaderboard_rewards --list-completed
        python manage.py award_leaderboard_rewards --process-all-completed
    """
    
    help = "Process and distribute rewards for contest leaderboard winners"
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            'contest_cycle_id',
            type=str,
            nargs='?',
            help='Contest cycle ID to process rewards for (UUID or name)'
        )
        
        parser.add_argument(
            '--snapshot-id',
            type=str,
            help='Specific leaderboard snapshot ID to use (UUID)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be awarded without actually distributing rewards'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force processing even if some validations fail'
        )
        
        parser.add_argument(
            '--list-completed',
            action='store_true',
            help='List all completed contest cycles available for reward processing'
        )
        
        parser.add_argument(
            '--process-all-completed',
            action='store_true',
            help='Process rewards for all completed contest cycles'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information about each reward distribution'
        )
        
        parser.add_argument(
            '--exclude-already-awarded',
            action='store_true',
            default=True,
            help='Skip users who have already received rewards (default: True)'
        )
    
    def handle(self, *args, **options):
        """Handle the command execution."""
        self.setup_logging(options.get('verbosity', 1))
        self.verbose = options.get('verbose', False)
        
        if options['list_completed']:
            self.list_completed_contests()
            return
        
        if options['process_all_completed']:
            self.process_all_completed_contests(options)
            return
        
        contest_cycle_id = options.get('contest_cycle_id')
        if not contest_cycle_id:
            raise CommandError(
                "Contest cycle ID is required unless using --list-completed or --process-all-completed"
            )
        
        self.process_contest_rewards(contest_cycle_id, options)
    
    def setup_logging(self, verbosity):
        """Set up logging based on verbosity level."""
        if verbosity == 0:
            logging.getLogger().setLevel(logging.WARNING)
        elif verbosity == 1:
            logging.getLogger().setLevel(logging.INFO)
        elif verbosity >= 2:
            logging.getLogger().setLevel(logging.DEBUG)
    
    def list_completed_contests(self):
        """List all completed contest cycles available for reward processing."""
        completed_cycles = ContestCycle.objects.filter(status=ContestCycleStatus.COMPLETED)
        
        if not completed_cycles.exists():
            self.stdout.write(self.style.WARNING("No completed contest cycles found."))
            return
        
        self.stdout.write(self.style.SUCCESS("Completed Contest Cycles Available for Reward Processing:"))
        self.stdout.write("-" * 80)
        
        for cycle in completed_cycles.order_by('-end_time'):
            # Check if rewards are already processed
            rewards_processed = self.check_rewards_processed(cycle)
            rewards_count = ContestReward.objects.filter(contest_cycle=cycle).count()
            
            status = "✓ Processed" if rewards_processed else "○ Pending"
            status_style = self.style.SUCCESS if rewards_processed else self.style.WARNING
            
            self.stdout.write(
                f"ID: {cycle.id}\n"
                f"Name: {cycle.name}\n"
                f"Status: {status_style(status)}\n"
                f"End: {cycle.end_time}\n"
                f"Rewards: {rewards_count} configured\n"
                f"{'-' * 40}"
            )
    
    def process_all_completed_contests(self, options):
        """Process rewards for all completed contest cycles."""
        completed_cycles = ContestCycle.objects.filter(status=ContestCycleStatus.COMPLETED)
        
        if not completed_cycles.exists():
            self.stdout.write(self.style.WARNING("No completed contest cycles found."))
            return
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("DRY RUN - No rewards will be distributed:"))
            self.stdout.write("-" * 80)
            for cycle in completed_cycles.order_by('-end_time'):
                self.stdout.write(f"Would process: {cycle.name} ({cycle.id})")
            return
        
        self.stdout.write(self.style.SUCCESS(f"Processing rewards for {completed_cycles.count()} completed contest cycles..."))
        
        success_count = 0
        error_count = 0
        skipped_count = 0
        
        for cycle in completed_cycles.order_by('-end_time'):
            try:
                # Skip if already processed
                if self.check_rewards_processed(cycle):
                    skipped_count += 1
                    if self.verbose:
                        self.stdout.write(f"Skipping already processed: {cycle.name}")
                    continue
                
                self.stdout.write(f"Processing: {cycle.name}...")
                self.process_contest_rewards_internal(cycle.id, options)
                success_count += 1
                self.stdout.write(self.style.SUCCESS(f"✓ Processed: {cycle.name}"))
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f"✗ Failed to process {cycle.name}: {e}"))
        
        self.stdout.write("-" * 80)
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed: {success_count} processed, {error_count} failed, {skipped_count} skipped"
            )
        )
    
    def process_contest_rewards(self, contest_cycle_id, options):
        """Process rewards for a single contest cycle."""
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
                        f"DRY RUN - Would process rewards for contest: {cycle.name} ({cycle.id})"
                    )
                )
                return
            
            self.process_contest_rewards_internal(cycle.id, options)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully processed rewards for contest: {cycle.name}"
                )
            )
            
        except ContestCycle.DoesNotExist:
            raise CommandError(f"Contest cycle '{contest_cycle_id}' not found")
        except Exception as e:
            raise CommandError(f"Error processing contest rewards: {e}")
    
    def process_contest_rewards_internal(self, contest_cycle_id, options):
        """Internal method to process rewards for a single contest cycle."""
        try:
            cycle = ContestCycle.objects.get(id=contest_cycle_id)
        except ContestCycle.DoesNotExist:
            raise ContestCycleNotFoundError(f"Contest cycle {contest_cycle_id} not found")
        
        # Validate contest state
        if not options['force'] and cycle.status != ContestCycleStatus.COMPLETED:
            raise ContestCycleStateError(
                f"Contest cycle {cycle.name} is not completed (current status: {cycle.status})"
            )
        
        # Check if rewards are already processed
        if self.check_rewards_processed(cycle) and not options['force']:
            raise CommandError(f"Rewards for contest {cycle.name} have already been processed")
        
        self.stdout.write(f"Processing rewards for contest: {cycle.name}")
        
        # Get rewards to distribute
        rewards = ContestReward.objects.filter(contest_cycle=cycle)
        
        if not rewards.exists():
            self.stdout.write(self.style.WARNING("No rewards configured for this contest"))
            return
        
        self.stdout.write(f"Found {rewards.count()} reward configurations")
        
        # Distribute rewards
        if not options['dry_run']:
            result = self.distribute_rewards(cycle, options['snapshot_id'], options['dry_run'])
            
            self.display_distribution_results(result, options['verbose'])
        else:
            # Show what would be distributed
            self.simulate_distribution(cycle, options['verbose'])
    
    def distribute_rewards(self, cycle, snapshot_id=None, dry_run=False):
        """Distribute rewards for the contest."""
        try:
            result = LeaderboardRewardService.distribute_rewards_for_cycle(
                contest_cycle_id=cycle.id,
                snapshot_id=snapshot_id,
                dry_run=dry_run
            )
            return result
        except Exception as e:
            raise CommandError(f"Failed to distribute rewards: {e}")
    
    def simulate_distribution(self, cycle, verbose=False):
        """Simulate reward distribution without actually distributing."""
        rewards = ContestReward.objects.filter(contest_cycle=cycle)
        
        self.stdout.write(self.style.WARNING("DRY RUN - Reward Distribution Simulation:"))
        self.stdout.write("-" * 60)
        
        for reward in rewards.order_by('rank_from'):
            # Estimate eligible users (simplified)
            eligible_count = self.estimate_eligible_users(reward)
            
            self.stdout.write(
                f"Reward: {reward.title}\n"
                f"  Rank Range: {reward.rank_from}-{reward.rank_to}\n"
                f"  Type: {reward.reward_type}\n"
                f"  Points: {reward.points_bonus}\n"
                f"  Budget: {reward.total_budget or 'Unlimited'}\n"
                f"  Estimated Eligible: {eligible_count}\n"
                f"  Would Award: {min(eligible_count, reward.total_budget or eligible_count)}\n"
                f"{'-' * 40}"
            )
    
    def display_distribution_results(self, result, verbose=False):
        """Display the results of reward distribution."""
        self.stdout.write(self.style.SUCCESS("Reward Distribution Results:"))
        self.stdout.write("-" * 60)
        
        self.stdout.write(
            f"Contest Cycle: {result['contest_cycle_id']}\n"
            f"Snapshot ID: {result['snapshot_id']}\n"
            f"Total Rewards: {result['total_rewards']}\n"
            f"Total Distributed: {result['total_distributed']}\n"
            f"Dry Run: {result['dry_run']}"
        )
        
        if verbose and result['distribution_results']:
            self.stdout.write("\nDetailed Results:")
            self.stdout.write("-" * 40)
            
            for reward_result in result['distribution_results']:
                self.stdout.write(
                    f"Reward: {reward_result['reward_title']}\n"
                    f"  Rank Range: {reward_result['rank_range']}\n"
                    f"  Eligible: {reward_result['eligible_users']}\n"
                    f"  Distributed: {reward_result['distributed_count']}\n"
                    f"  Skipped: {reward_result['skipped_count']}\n"
                    f"  Budget Exhausted: {reward_result['budget_exhausted']}\n"
                )
                
                if reward_result['errors']:
                    self.stdout.write("  Errors:")
                    for error in reward_result['errors']:
                        self.stdout.write(f"    - {error}")
                
                self.stdout.write("-" * 40)
    
    def estimate_eligible_users(self, reward):
        """Estimate number of eligible users for a reward."""
        # This is a simplified estimation - in practice, you'd query the actual snapshot
        rank_range = reward.rank_to - reward.rank_from + 1
        return rank_range  # Simplified estimation
    
    def check_rewards_processed(self, cycle):
        """Check if rewards have already been processed for this contest."""
        # Check if any UserAchievement exists for this contest cycle
        return UserAchievement.objects.filter(
            contest_cycle=cycle,
            achievement_type=RewardType.CONTEST_REWARD,
            is_awarded=True
        ).exists()
    
    def validate_rewards_configuration(self, cycle, force=False):
        """Validate that rewards are properly configured."""
        rewards = ContestReward.objects.filter(contest_cycle=cycle)
        
        if not rewards.exists():
            if not force:
                raise CommandError(f"No rewards configured for contest {cycle.name}")
            return False
        
        # Check for overlapping rank ranges
        rank_ranges = []
        for reward in rewards:
            rank_range = (reward.rank_from, reward.rank_to)
            rank_ranges.append(rank_range)
        
        # Simple overlap check
        for i, (start1, end1) in enumerate(rank_ranges):
            for j, (start2, end2) in enumerate(rank_ranges):
                if i != j and not (end1 < start2 or end2 < start1):
                    if not force:
                        raise CommandError(
                            f"Overlapping rank ranges detected between rewards {i+1} and {j+1}"
                        )
        
        return True
