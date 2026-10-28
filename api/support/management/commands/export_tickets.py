# api/support/management/commands/export_tickets.py
"""Export tickets to CSV file."""
import os
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Export support tickets to CSV'

    def add_arguments(self, parser):
        parser.add_argument('--days',   type=int,   default=30,           help='Export last N days')
        parser.add_argument('--output', type=str,   default='tickets.csv',help='Output file path')
        parser.add_argument('--status', type=str,   default='',           help='Filter by status')

    def handle(self, *args, **options):
        from api.support.resources import ticket_export
        from api.support.models import SupportTicket
        from django.utils import timezone
        from datetime import timedelta

        days   = options['days']
        since  = timezone.now() - timedelta(days=days)
        qs     = SupportTicket.objects.filter(created_at__gte=since)
        if options['status']:
            qs = qs.filter(status=options['status'])

        output = options['output']
        data   = ticket_export.export_csv(qs)

        with open(output, 'wb') as f:
            f.write(data)

        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {qs.count()} tickets to {os.path.abspath(output)}"
            )
        )