#!/usr/bin/env python
# api/publisher_tools/scripts/calculate_earnings.py
"""
Earnings Calculator Script।
Daily/Monthly earnings calculate ও update করার management command।

Usage:
    python manage.py calculate_publisher_earnings --date 2024-01-15
    python manage.py calculate_publisher_earnings --month 2024-01
    python manage.py calculate_publisher_earnings --publisher PUB000001
"""
from decimal import Decimal
from datetime import date, datetime
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Sum
from django.db import transaction


class Command(BaseCommand):
    help = 'Calculate and update publisher earnings for a given period'

    def add_arguments(self, parser):
        parser.add_argument('--date',      type=str, help='Specific date (YYYY-MM-DD)')
        parser.add_argument('--month',     type=str, help='Specific month (YYYY-MM)')
        parser.add_argument('--publisher', type=str, help='Specific publisher ID (e.g., PUB000001)')
        parser.add_argument('--dry-run',   action='store_true', help='Simulate without saving')
        parser.add_argument('--force',     action='store_true', help='Recalculate even if finalized')

    def handle(self, *args, **options):
        from api.publisher_tools.models import Publisher, PublisherEarning

        target_date  = options.get('date')
        target_month = options.get('month')
        publisher_id = options.get('publisher')
        dry_run      = options.get('dry_run')
        force        = options.get('force')

        self.stdout.write(self.style.SUCCESS(
            f'🚀 Starting earnings calculation...\n'
            f'   Date: {target_date or "all"}\n'
            f'   Month: {target_month or "all"}\n'
            f'   Publisher: {publisher_id or "all"}\n'
            f'   Dry Run: {dry_run}\n'
        ))

        # Get publishers
        publishers = Publisher.objects.filter(status='active')
        if publisher_id:
            publishers = publishers.filter(publisher_id=publisher_id)
            if not publishers.exists():
                raise CommandError(f'Publisher {publisher_id} not found.')

        processed = 0
        errors    = 0
        total_revenue = Decimal('0')

        for publisher in publishers:
            try:
                result = self._calculate_for_publisher(
                    publisher, target_date, target_month, dry_run, force
                )
                processed += 1
                total_revenue += result.get('total_revenue', Decimal('0'))
                self.stdout.write(
                    f'   ✅ {publisher.publisher_id}: ${result.get("total_revenue", 0):.4f}'
                )
            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(f'   ❌ {publisher.publisher_id}: {str(e)}')
                )

        self.stdout.write(self.style.SUCCESS(
            f'\n📊 Summary:\n'
            f'   Processed: {processed} publishers\n'
            f'   Errors: {errors}\n'
            f'   Total Revenue Calculated: ${total_revenue:.4f}\n'
            f'   {"[DRY RUN - No changes saved]" if dry_run else "Done!"}'
        ))

    @transaction.atomic
    def _calculate_for_publisher(
        self,
        publisher,
        target_date: Optional[str],
        target_month: Optional[str],
        dry_run: bool,
        force: bool,
    ) -> dict:
        """Publisher-এর earnings calculate করে"""
        from api.publisher_tools.models import PublisherEarning
        from api.publisher_tools.utils import calculate_ecpm, calculate_ctr, calculate_fill_rate

        # Determine date range
        if target_date:
            calc_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            qs = PublisherEarning.objects.filter(publisher=publisher, date=calc_date)
        elif target_month:
            year, month = map(int, target_month.split('-'))
            from calendar import monthrange
            last_day = monthrange(year, month)[1]
            from datetime import date as date_type
            start = date_type(year, month, 1)
            end   = date_type(year, month, last_day)
            qs = PublisherEarning.objects.filter(publisher=publisher, date__range=[start, end])
        else:
            # Today by default
            qs = PublisherEarning.objects.filter(
                publisher=publisher, date=timezone.now().date()
            )

        if not force:
            qs = qs.exclude(status='finalized')

        agg = qs.aggregate(
            total_gross=Sum('gross_revenue'),
            total_publisher=Sum('publisher_revenue'),
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_requests=Sum('ad_requests'),
        )

        total_revenue = agg.get('total_publisher') or Decimal('0')

        if not dry_run:
            # Update publisher totals
            all_confirmed = PublisherEarning.objects.filter(
                publisher=publisher,
                status__in=['confirmed', 'finalized'],
            ).aggregate(total=Sum('publisher_revenue'))

            publisher.total_revenue = all_confirmed.get('total') or Decimal('0')
            publisher.save(update_fields=['total_revenue', 'updated_at'])

            # Update derived metrics for each earning
            for earning in qs:
                earning.ecpm = calculate_ecpm(earning.publisher_revenue, earning.impressions)
                earning.ctr  = calculate_ctr(earning.clicks, earning.impressions)
                earning.fill_rate = calculate_fill_rate(earning.impressions, earning.ad_requests)
                if earning.status == 'estimated':
                    earning.status = 'confirmed'
                earning.save(update_fields=['ecpm', 'ctr', 'fill_rate', 'status', 'updated_at'])

        return {
            'publisher_id':  publisher.publisher_id,
            'total_revenue': total_revenue,
            'impressions':   agg.get('total_impressions') or 0,
            'records_updated': qs.count(),
        }


def run_earnings_calculation(
    publisher_id: str = None,
    target_date: date = None,
    dry_run: bool = False,
) -> dict:
    """
    Programmatic interface — code থেকে call করার জন্য।
    """
    from api.publisher_tools.models import Publisher, PublisherEarning
    from api.publisher_tools.utils import calculate_ecpm, calculate_ctr, calculate_fill_rate

    results = []

    publishers = Publisher.objects.filter(status='active')
    if publisher_id:
        publishers = publishers.filter(publisher_id=publisher_id)

    if not target_date:
        target_date = timezone.now().date()

    for publisher in publishers:
        earnings = PublisherEarning.objects.filter(
            publisher=publisher,
            date=target_date,
            status='estimated',
        )

        total = Decimal('0')
        for earning in earnings:
            earning.ecpm = calculate_ecpm(earning.publisher_revenue, earning.impressions)
            earning.ctr  = calculate_ctr(earning.clicks, earning.impressions)
            earning.fill_rate = calculate_fill_rate(earning.impressions, earning.ad_requests)
            earning.status = 'confirmed'
            total += earning.publisher_revenue

            if not dry_run:
                earning.save()

        results.append({
            'publisher_id':  publisher.publisher_id,
            'date':          str(target_date),
            'total_revenue': float(total),
            'records':       earnings.count(),
        })

    return {
        'date':       str(target_date),
        'publishers': results,
        'dry_run':    dry_run,
    }
