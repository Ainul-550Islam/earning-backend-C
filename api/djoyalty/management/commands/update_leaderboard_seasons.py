# api/djoyalty/management/commands/update_leaderboard_seasons.py
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Update leaderboard seasons -- end old, start new।'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--force-end', type=int, help='Force-end season by ID')

    def handle(self, *args, **options):
        from django.utils import timezone
        from djoyalty.models.gamification import LeaderboardSeason

        dry = options['dry_run']
        if dry:
            self.stdout.write(self.style.WARNING('DRY RUN'))

        now = timezone.now()

        # End expired seasons
        expired = LeaderboardSeason.objects.filter(
            is_active=True,
            end_date__lt=now,
        )
        self.stdout.write(f'Expired seasons to close: {expired.count()}')

        for season in expired:
            self.stdout.write(f'  Closing: {season.name} (ended {season.end_date})')
            if not dry:
                season.is_active = False
                season.save(update_fields=['is_active'])
                # Award top participants
                self._award_top_participants(season)

        # Start upcoming seasons
        upcoming = LeaderboardSeason.objects.filter(
            is_active=False,
            start_date__lte=now,
            end_date__gt=now,
        )
        self.stdout.write(f'Seasons to activate: {upcoming.count()}')
        for season in upcoming:
            self.stdout.write(f'  Starting: {season.name}')
            if not dry:
                season.is_active = True
                season.save(update_fields=['is_active'])

        self.stdout.write(self.style.SUCCESS('Leaderboard seasons updated'))

    def _award_top_participants(self, season):
        """Award points/badges to top leaderboard finishers।"""
        try:
            from djoyalty.models.core import Customer
            from djoyalty.services.NotificationService import NotificationService

            # Top 3 get bonus points
            rewards = {1: 1000, 2: 500, 3: 200}
            for rank, bonus_pts in rewards.items():
                # This is placeholder -- actual rank calc depends on leaderboard entries
                self.stdout.write(f'    Rank #{rank}: +{bonus_pts} bonus pts')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'    Award error: {e}'))
