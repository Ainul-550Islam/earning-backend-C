# earning_backend/api/notifications/management/commands/notification_maintenance.py
"""
Management command: python manage.py notification_maintenance

Runs all maintenance operations: cleanup, analytics, fatigue reset, token refresh.
Useful for testing and manual maintenance outside of Celery.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Run notification system maintenance tasks'

    def add_arguments(self, parser):
        parser.add_argument('--cleanup', action='store_true', help='Run cleanup tasks')
        parser.add_argument('--analytics', action='store_true', help='Generate daily analytics')
        parser.add_argument('--fatigue-reset', action='store_true', help='Reset fatigue counters')
        parser.add_argument('--token-refresh', action='store_true', help='Refresh stale FCM tokens')
        parser.add_argument('--create-fatigue-records', action='store_true', help='Create missing fatigue records')
        parser.add_argument('--all', action='store_true', help='Run all maintenance tasks')

    def handle(self, *args, **options):
        run_all = options['all']

        if run_all or options['cleanup']:
            self.stdout.write('Running cleanup...')
            from api.notifications.tasks.cleanup_tasks import run_all_cleanup
            run_all_cleanup()
            self.stdout.write(self.style.SUCCESS('Cleanup complete'))

        if run_all or options['analytics']:
            self.stdout.write('Generating analytics...')
            from api.notifications.tasks.insight_tasks import generate_daily_notification_insights
            generate_daily_notification_insights()
            self.stdout.write(self.style.SUCCESS('Analytics generated'))

        if run_all or options['fatigue_reset']:
            self.stdout.write('Resetting fatigue counters...')
            from api.notifications.services.FatigueService import fatigue_service
            result = fatigue_service.reset_daily_counters()
            self.stdout.write(self.style.SUCCESS(f'Fatigue reset: {result}'))

        if run_all or options['token_refresh']:
            self.stdout.write('Refreshing FCM tokens...')
            from api.notifications.tasks.token_refresh_tasks import refresh_stale_fcm_tokens
            result = refresh_stale_fcm_tokens()
            self.stdout.write(self.style.SUCCESS(f'Token refresh: {result}'))

        if run_all or options['create_fatigue_records']:
            self.stdout.write('Creating missing fatigue records...')
            from api.notifications.tasks.fatigue_check_tasks import create_missing_fatigue_records
            result = create_missing_fatigue_records()
            self.stdout.write(self.style.SUCCESS(f'Created: {result}'))

        if not any([run_all, options['cleanup'], options['analytics'],
                    options['fatigue_reset'], options['token_refresh'],
                    options['create_fatigue_records']]):
            self.stdout.write(self.style.WARNING('No option specified. Use --all or specific flags.'))
            self.print_help('manage.py', 'notification_maintenance')
