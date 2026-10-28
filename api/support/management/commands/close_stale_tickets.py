# api/support/management/commands/close_stale_tickets.py
"""Close stale waiting_user and old resolved tickets."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Close stale support tickets'

    def add_arguments(self, parser):
        parser.add_argument('--waiting-days', type=int, default=7)
        parser.add_argument('--resolved-days', type=int, default=30)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from api.support.models import SupportTicket
        from django.utils import timezone
        from datetime import timedelta

        now            = timezone.now()
        waiting_days   = options['waiting_days']
        resolved_days  = options['resolved_days']
        dry_run        = options['dry_run']

        # Stale waiting_user
        waiting_cutoff = now - timedelta(days=waiting_days)
        waiting_qs     = SupportTicket.objects.filter(
            status='waiting_user', updated_at__lte=waiting_cutoff
        )
        w_count = waiting_qs.count()
        self.stdout.write(f'Waiting >  {waiting_days}d: {w_count} tickets')
        if not dry_run:
            waiting_qs.update(status='closed')

        # Old resolved
        resolved_cutoff = now - timedelta(days=resolved_days)
        resolved_qs     = SupportTicket.objects.filter(
            status='resolved', resolved_at__lte=resolved_cutoff
        )
        r_count = resolved_qs.count()
        self.stdout.write(f'Resolved > {resolved_days}d: {r_count} tickets')
        if not dry_run:
            resolved_qs.update(status='closed')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes made'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Closed {w_count + r_count} stale tickets'
            ))