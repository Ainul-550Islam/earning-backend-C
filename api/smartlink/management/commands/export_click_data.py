import csv
import os
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Export click data to CSV file'

    def add_arguments(self, parser):
        parser.add_argument('--smartlink-slug', type=str, help='Export only for this slug')
        parser.add_argument('--days', type=int, default=30, help='Export last N days (default: 30)')
        parser.add_argument('--output', type=str, default='clicks_export.csv', help='Output file path')
        parser.add_argument('--include-fraud', action='store_true', help='Include fraud/bot clicks')

    def handle(self, *args, **options):
        import datetime
        from ...models import Click

        days = options['days']
        cutoff = timezone.now() - datetime.timedelta(days=days)
        qs = Click.objects.filter(created_at__gte=cutoff).select_related('smartlink', 'offer')

        if options['smartlink_slug']:
            qs = qs.filter(smartlink__slug=options['smartlink_slug'])

        if not options['include_fraud']:
            qs = qs.filter(is_fraud=False, is_bot=False)

        output_path = options['output']
        total = qs.count()
        self.stdout.write(f'Exporting {total} clicks to {output_path}...')

        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'id', 'smartlink_slug', 'offer_id', 'ip', 'country', 'region',
                'city', 'device_type', 'os', 'browser', 'is_unique',
                'is_fraud', 'is_bot', 'is_converted', 'fraud_score',
                'payout', 'referrer', 'created_at',
            ])
            for click in qs.iterator(chunk_size=1000):
                writer.writerow([
                    click.id, click.smartlink.slug, click.offer_id,
                    click.ip, click.country, click.region, click.city,
                    click.device_type, click.os, click.browser,
                    click.is_unique, click.is_fraud, click.is_bot,
                    click.is_converted, click.fraud_score, click.payout,
                    click.referrer, click.created_at.isoformat(),
                ])

        size_kb = os.path.getsize(output_path) / 1024
        self.stdout.write(self.style.SUCCESS(
            f'✅ Exported {total} clicks → {output_path} ({size_kb:.1f} KB)'
        ))
