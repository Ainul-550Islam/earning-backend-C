from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Archive click records older than N days to cold storage'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=90, help='Archive clicks older than this many days (default: 90)')
        parser.add_argument('--dry-run', action='store_true', help='Show count without deleting')

    def handle(self, *args, **options):
        import datetime
        from django.utils import timezone
        from ...models import Click

        days = options['days']
        cutoff = timezone.now() - datetime.timedelta(days=days)
        qs = Click.objects.filter(created_at__lt=cutoff)
        count = qs.count()

        if options['dry_run']:
            self.stdout.write(f'[DRY RUN] Would archive {count} clicks older than {days} days (before {cutoff.date()})')
            return

        confirm = input(f'Archive {count} clicks older than {days} days? Type YES: ')
        if confirm != 'YES':
            self.stdout.write('Cancelled.')
            return

        deleted, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(f'✅ Archived (deleted) {deleted} old click records.'))
