"""
Export Contest Results Management Command — Export contest data and results.

This command exports contest cycle data, leaderboards, and results in various
formats including CSV, JSON, and Excel for reporting and analysis.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from api.gamification.models import ContestCycle, LeaderboardSnapshot, UserAchievement, ContestReward
from api.gamification.choices import ContestCycleStatus, SnapshotStatus
from api.gamification.exceptions import ContestCycleNotFoundError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to export contest results and data.
    
    Usage:
        python manage.py export_contest_results <contest_cycle_id>
        python manage.py export_contest_results <contest_cycle_id> --format json
        python manage.py export_contest_results <contest_cycle_id> --output /path/to/file.csv
        python manage.py export_contest_results --list-cycles
        python manage.py export_contest_results --export-all --format csv
    """
    
    help = "Export contest results and data in various formats"
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            'contest_cycle_id',
            type=str,
            nargs='?',
            help='Contest cycle ID to export (UUID or name)'
        )
        
        parser.add_argument(
            '--format',
            type=str,
            default='csv',
            choices=['csv', 'json', 'excel'],
            help='Export format (default: csv)'
        )
        
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path (default: auto-generated)'
        )
        
        parser.add_argument(
            '--snapshot-id',
            type=str,
            help='Specific leaderboard snapshot ID to export (UUID)'
        )
        
        parser.add_argument(
            '--include-rewards',
            action='store_true',
            help='Include reward distribution data in export'
        )
        
        parser.add_argument(
            '--include-achievements',
            action='store_true',
            help='Include all user achievements in export'
        )
        
        parser.add_argument(
            '--include-metadata',
            action='store_true',
            help='Include detailed metadata in export'
        )
        
        parser.add_argument(
            '--list-cycles',
            action='store_true',
            help='List all contest cycles available for export'
        )
        
        parser.add_argument(
            '--export-all',
            action='store_true',
            help='Export all completed contest cycles'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed export information'
        )
        
        parser.add_argument(
            '--compress',
            action='store_true',
            help='Compress output files (for JSON/Excel)'
        )
    
    def handle(self, *args, **options):
        """Handle the command execution."""
        self.setup_logging(options.get('verbosity', 1))
        self.verbose = options.get('verbose', False)
        
        if options['list_cycles']:
            self.list_contest_cycles()
            return
        
        if options['export_all']:
            self.export_all_cycles(options)
            return
        
        contest_cycle_id = options.get('contest_cycle_id')
        if not contest_cycle_id:
            raise CommandError(
                "Contest cycle ID is required unless using --list-cycles or --export-all"
            )
        
        self.export_single_cycle(contest_cycle_id, options)
    
    def setup_logging(self, verbosity):
        """Set up logging based on verbosity level."""
        if verbosity == 0:
            logging.getLogger().setLevel(logging.WARNING)
        elif verbosity == 1:
            logging.getLogger().setLevel(logging.INFO)
        elif verbosity >= 2:
            logging.getLogger().setLevel(logging.DEBUG)
    
    def list_contest_cycles(self):
        """List all contest cycles available for export."""
        cycles = ContestCycle.objects.all()
        
        if not cycles.exists():
            self.stdout.write(self.style.WARNING("No contest cycles found."))
            return
        
        self.stdout.write(self.style.SUCCESS("Contest Cycles Available for Export:"))
        self.stdout.write("-" * 80)
        
        for cycle in cycles.order_by('-start_time'):
            # Check for snapshots
            snapshots = LeaderboardSnapshot.objects.filter(contest_cycle=cycle)
            latest_snapshot = snapshots.order_by('-created_at').first()
            
            # Check for achievements
            achievements = UserAchievement.objects.filter(contest_cycle=cycle)
            
            status = cycle.status
            snapshot_info = f"Snapshots: {snapshots.count()}"
            achievement_info = f"Achievements: {achievements.count()}"
            
            if latest_snapshot:
                snapshot_info += f" (Latest: {latest_snapshot.created_at.date()})"
            
            self.stdout.write(
                f"ID: {cycle.id}\n"
                f"Name: {cycle.name}\n"
                f"Status: {status}\n"
                f"Start: {cycle.start_time}\n"
                f"End: {cycle.end_time}\n"
                f"{snapshot_info}\n"
                f"{achievement_info}\n"
                f"{'-' * 40}"
            )
    
    def export_all_cycles(self, options):
        """Export all completed contest cycles."""
        cycles = ContestCycle.objects.filter(status=ContestCycleStatus.COMPLETED)
        
        if not cycles.exists():
            self.stdout.write(self.style.WARNING("No completed contest cycles found."))
            return
        
        self.stdout.write(self.style.SUCCESS(f"Exporting {cycles.count()} completed contest cycles..."))
        
        success_count = 0
        error_count = 0
        
        for cycle in cycles.order_by('-end_time'):
            try:
                self.stdout.write(f"Exporting: {cycle.name}...")
                
                # Generate unique filename for each cycle
                base_filename = f"contest_export_{cycle.name}_{cycle.id}"
                filename = self.generate_filename(base_filename, options['format'])
                
                # Export the cycle
                self.export_single_cycle_internal(cycle.id, options, filename)
                success_count += 1
                self.stdout.write(self.style.SUCCESS(f"✓ Exported: {cycle.name} -> {filename}"))
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f"✗ Failed to export {cycle.name}: {e}"))
        
        self.stdout.write("-" * 80)
        self.stdout.write(
            self.style.SUCCESS(
                f"Export completed: {success_count} exported, {error_count} failed"
            )
        )
    
    def export_single_cycle(self, contest_cycle_id, options):
        """Export a single contest cycle."""
        try:
            # Try to find by UUID first
            try:
                cycle = ContestCycle.objects.get(id=contest_cycle_id)
            except (ContestCycle.DoesNotExist, ValueError):
                # Try to find by name
                cycle = ContestCycle.objects.get(name=contest_cycle_id)
            
            # Generate filename if not provided
            if not options.get('output'):
                base_filename = f"contest_export_{cycle.name}_{cycle.id}"
                filename = self.generate_filename(base_filename, options['format'])
            else:
                filename = options['output']
            
            self.export_single_cycle_internal(cycle.id, options, filename)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully exported contest: {cycle.name} -> {filename}"
                )
            )
            
        except ContestCycle.DoesNotExist:
            raise CommandError(f"Contest cycle '{contest_cycle_id}' not found")
        except Exception as e:
            raise CommandError(f"Error exporting contest: {e}")
    
    def export_single_cycle_internal(self, contest_cycle_id, options, filename):
        """Internal method to export a single contest cycle."""
        try:
            cycle = ContestCycle.objects.get(id=contest_cycle_id)
        except ContestCycle.DoesNotExist:
            raise ContestCycleNotFoundError(f"Contest cycle {contest_cycle_id} not found")
        
        self.stdout.write(f"Exporting contest: {cycle.name}")
        
        # Collect export data
        export_data = self.collect_export_data(cycle, options)
        
        # Export based on format
        if options['format'] == 'csv':
            self.export_to_csv(export_data, filename, options)
        elif options['format'] == 'json':
            self.export_to_json(export_data, filename, options)
        elif options['format'] == 'excel':
            self.export_to_excel(export_data, filename, options)
        else:
            raise CommandError(f"Unsupported export format: {options['format']}")
        
        if self.verbose:
            self.display_export_summary(export_data, filename)
    
    def collect_export_data(self, cycle, options):
        """Collect all data for export."""
        export_data = {
            'contest_info': self.get_contest_info(cycle),
            'leaderboard': self.get_leaderboard_data(cycle, options.get('snapshot_id')),
            'rewards': [],
            'achievements': [],
            'metadata': {
                'exported_at': timezone.now().isoformat(),
                'export_options': options
            }
        }
        
        # Include rewards if requested
        if options.get('include_rewards'):
            export_data['rewards'] = self.get_rewards_data(cycle)
        
        # Include achievements if requested
        if options.get('include_achievements'):
            export_data['achievements'] = self.get_achievements_data(cycle)
        
        return export_data
    
    def get_contest_info(self, cycle):
        """Get basic contest information."""
        return {
            'id': str(cycle.id),
            'name': cycle.name,
            'description': cycle.description,
            'status': cycle.status,
            'start_time': cycle.start_time.isoformat(),
            'end_time': cycle.end_time.isoformat() if cycle.end_time else None,
            'points_multiplier': float(cycle.points_multiplier),
            'metadata': cycle.metadata if hasattr(cycle, 'metadata') else {},
            'created_at': cycle.created_at.isoformat(),
            'updated_at': cycle.updated_at.isoformat(),
        }
    
    def get_leaderboard_data(self, cycle, snapshot_id=None):
        """Get leaderboard data for the contest."""
        if snapshot_id:
            try:
                snapshot = LeaderboardSnapshot.objects.get(id=snapshot_id, contest_cycle=cycle)
            except LeaderboardSnapshot.DoesNotExist:
                raise CommandError(f"Snapshot {snapshot_id} not found for contest {cycle.name}")
        else:
            # Get the latest finalized snapshot
            snapshot = LeaderboardSnapshot.objects.filter(
                contest_cycle=cycle,
                status=SnapshotStatus.FINALIZED
            ).order_by('-created_at').first()
            
            if not snapshot:
                # Try any snapshot if no finalized ones
                snapshot = LeaderboardSnapshot.objects.filter(
                    contest_cycle=cycle
                ).order_by('-created_at').first()
        
        if not snapshot:
            self.stdout.write(self.style.WARNING("No leaderboard snapshots found for this contest"))
            return []
        
        return {
            'snapshot_id': str(snapshot.id),
            'scope': snapshot.scope,
            'status': snapshot.status,
            'created_at': snapshot.created_at.isoformat(),
            'finalized_at': snapshot.finalized_at.isoformat() if snapshot.finalized_at else None,
            'entries': snapshot.snapshot_data or [],
            'metadata': snapshot.metadata if hasattr(snapshot, 'metadata') else {},
        }
    
    def get_rewards_data(self, cycle):
        """Get reward distribution data for the contest."""
        rewards = ContestReward.objects.filter(contest_cycle=cycle)
        
        rewards_data = []
        for reward in rewards:
            reward_data = {
                'id': str(reward.id),
                'title': reward.title,
                'description': reward.description,
                'rank_from': reward.rank_from,
                'rank_to': reward.rank_to,
                'reward_type': reward.reward_type,
                'points_bonus': reward.points_bonus,
                'total_budget': reward.total_budget,
                'issued_count': reward.issued_count,
                'is_active': reward.is_active,
                'metadata': reward.metadata if hasattr(reward, 'metadata') else {},
            }
            rewards_data.append(reward_data)
        
        return rewards_data
    
    def get_achievements_data(self, cycle):
        """Get achievement data for the contest."""
        achievements = UserAchievement.objects.filter(contest_cycle=cycle)
        
        achievements_data = []
        for achievement in achievements:
            achievement_data = {
                'id': str(achievement.id),
                'user_id': str(achievement.user.id),
                'username': achievement.user.username,
                'achievement_type': achievement.achievement_type,
                'points_awarded': achievement.points_awarded,
                'rank': achievement.rank,
                'is_awarded': achievement.is_awarded,
                'awarded_at': achievement.awarded_at.isoformat() if achievement.awarded_at else None,
                'metadata': achievement.metadata if hasattr(achievement, 'metadata') else {},
            }
            achievements_data.append(achievement_data)
        
        return achievements_data
    
    def export_to_csv(self, export_data, filename, options):
        """Export data to CSV format."""
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write contest info
            writer.writerow(['Contest Information'])
            for key, value in export_data['contest_info'].items():
                writer.writerow([key, value])
            writer.writerow([])
            
            # Write leaderboard
            if export_data['leaderboard']:
                writer.writerow(['Leaderboard'])
                writer.writerow(['Rank', 'Username', 'User ID', 'Total Points', 'Achievement Count'])
                
                for entry in export_data['leaderboard']['entries']:
                    writer.writerow([
                        entry.get('rank', ''),
                        entry.get('username', ''),
                        entry.get('user_id', ''),
                        entry.get('total_points', 0),
                        entry.get('achievement_count', 0)
                    ])
                writer.writerow([])
            
            # Write rewards
            if export_data['rewards']:
                writer.writerow(['Rewards'])
                writer.writerow(['Title', 'Rank Range', 'Type', 'Points', 'Budget', 'Issued'])
                
                for reward in export_data['rewards']:
                    writer.writerow([
                        reward['title'],
                        f"{reward['rank_from']}-{reward['rank_to']}",
                        reward['reward_type'],
                        reward['points_bonus'],
                        reward['total_budget'] or 'Unlimited',
                        reward['issued_count']
                    ])
                writer.writerow([])
            
            # Write achievements
            if export_data['achievements']:
                writer.writerow(['Achievements'])
                writer.writerow(['Username', 'Type', 'Points', 'Rank', 'Awarded At'])
                
                for achievement in export_data['achievements']:
                    writer.writerow([
                        achievement['username'],
                        achievement['achievement_type'],
                        achievement['points_awarded'],
                        achievement['rank'],
                        achievement['awarded_at'] or 'Not awarded'
                    ])
    
    def export_to_json(self, export_data, filename, options):
        """Export data to JSON format."""
        # Remove metadata if not requested
        if not options.get('include_metadata'):
            export_data.pop('metadata', None)
            for item in export_data.get('rewards', []):
                item.pop('metadata', None)
            for item in export_data.get('achievements', []):
                item.pop('metadata', None)
        
        with open(filename, 'w', encoding='utf-8') as jsonfile:
            json.dump(export_data, jsonfile, indent=2, ensure_ascii=False)
    
    def export_to_excel(self, export_data, filename, options):
        """Export data to Excel format."""
        try:
            import pandas as pd
        except ImportError:
            raise CommandError("pandas library is required for Excel export. Install with: pip install pandas openpyxl")
        
        # Create multiple sheets
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Contest info sheet
            contest_df = pd.DataFrame(list(export_data['contest_info'].items()), columns=['Field', 'Value'])
            contest_df.to_excel(writer, sheet_name='Contest Info', index=False)
            
            # Leaderboard sheet
            if export_data['leaderboard']:
                leaderboard_data = export_data['leaderboard']['entries']
                if leaderboard_data:
                    leaderboard_df = pd.DataFrame(leaderboard_data)
                    leaderboard_df.to_excel(writer, sheet_name='Leaderboard', index=False)
            
            # Rewards sheet
            if export_data['rewards']:
                rewards_df = pd.DataFrame(export_data['rewards'])
                rewards_df.to_excel(writer, sheet_name='Rewards', index=False)
            
            # Achievements sheet
            if export_data['achievements']:
                achievements_df = pd.DataFrame(export_data['achievements'])
                achievements_df.to_excel(writer, sheet_name='Achievements', index=False)
    
    def generate_filename(self, base_filename, format_type):
        """Generate output filename with timestamp and extension."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        extension = self.get_file_extension(format_type)
        return f"{base_filename}_{timestamp}{extension}"
    
    def get_file_extension(self, format_type):
        """Get file extension for format type."""
        extensions = {
            'csv': '.csv',
            'json': '.json',
            'excel': '.xlsx'
        }
        return extensions.get(format_type, '.csv')
    
    def display_export_summary(self, export_data, filename):
        """Display summary of exported data."""
        self.stdout.write(self.style.SUCCESS("Export Summary:"))
        self.stdout.write("-" * 40)
        
        contest_info = export_data['contest_info']
        self.stdout.write(f"Contest: {contest_info['name']}")
        self.stdout.write(f"Status: {contest_info['status']}")
        
        if export_data['leaderboard']:
            leaderboard = export_data['leaderboard']
            self.stdout.write(f"Leaderboard: {len(leaderboard.get('entries', []))} entries")
            self.stdout.write(f"Snapshot: {leaderboard.get('snapshot_id', 'N/A')}")
        
        if export_data['rewards']:
            self.stdout.write(f"Rewards: {len(export_data['rewards'])} configurations")
        
        if export_data['achievements']:
            self.stdout.write(f"Achievements: {len(export_data['achievements'])} records")
        
        self.stdout.write(f"Output file: {filename}")
        self.stdout.write(f"File size: {self.get_file_size(filename)}")
    
    def get_file_size(self, filename):
        """Get human-readable file size."""
        try:
            size = os.path.getsize(filename)
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024:
                    return f"{size:.1f} {unit}"
                size /= 1024
            return f"{size:.1f} TB"
        except OSError:
            return "Unknown"
