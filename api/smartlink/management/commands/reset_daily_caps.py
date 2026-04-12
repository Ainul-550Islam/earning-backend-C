from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Manually reset all daily offer caps (normally runs automatically at midnight)'

    def add_arguments(self, parser):
        parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')

    def handle(self, *args, **options):
        if not options['confirm']:
            confirm = input('Reset ALL daily caps? This cannot be undone. Type YES to confirm: ')
            if confirm != 'YES':
                self.stdout.write('Cancelled.')
                return

        from ...services.rotation.CapTrackerService import CapTrackerService
        svc = CapTrackerService()
        count = svc.reset_daily_caps()
        self.stdout.write(self.style.SUCCESS(f'✅ Reset daily caps for {count} offer pool entries.'))
