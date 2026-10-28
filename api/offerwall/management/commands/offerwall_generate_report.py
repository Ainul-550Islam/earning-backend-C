"""
Management command: generate_report
Generate analytics reports for the offerwall module.
"""
import json
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Generate offerwall analytics report'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7,
                            help='Report period in days')
        parser.add_argument('--format', choices=['text', 'json'],
                            default='text')
        parser.add_argument('--output', type=str, default=None,
                            help='Output file path (default: stdout)')

    def handle(self, *args, **options):
        from api.offerwall.models import Offer, OfferConversion, OfferClick
        from django.db.models import Count, Sum, Avg

        since = timezone.now() - timedelta(days=options['days'])

        report = {
            'period_days': options['days'],
            'generated_at': timezone.now().isoformat(),
            'offers': {
                'total':   Offer.objects.count(),
                'active':  Offer.objects.filter(status='active').count(),
                'expired': Offer.objects.filter(status='expired').count(),
                'paused':  Offer.objects.filter(status='paused').count(),
            },
            'conversions': {
                'total':     OfferConversion.objects.filter(converted_at__gte=since).count(),
                'approved':  OfferConversion.objects.filter(
                                 converted_at__gte=since, status='approved').count(),
                'pending':   OfferConversion.objects.filter(
                                 converted_at__gte=since, status='pending').count(),
                'rejected':  OfferConversion.objects.filter(
                                 converted_at__gte=since, status='rejected').count(),
                'revenue':   str(OfferConversion.objects.filter(
                                 converted_at__gte=since, status='approved'
                             ).aggregate(t=Sum('payout_amount'))['t'] or 0),
                'rewards':   str(OfferConversion.objects.filter(
                                 converted_at__gte=since, status='approved'
                             ).aggregate(t=Sum('reward_amount'))['t'] or 0),
            },
            'clicks': {
                'total':     OfferClick.objects.filter(clicked_at__gte=since).count(),
                'converted': OfferClick.objects.filter(
                                 clicked_at__gte=since, is_converted=True).count(),
            },
        }

        # click-to-conversion rate
        clicks = report['clicks']['total']
        convs  = report['conversions']['total']
        report['metrics'] = {
            'ctr': round(convs / clicks * 100, 2) if clicks else 0,
        }

        if options['format'] == 'json':
            output = json.dumps(report, indent=2)
        else:
            output = self._format_text(report)

        if options['output']:
            with open(options['output'], 'w') as f:
                f.write(output)
            self.stdout.write(self.style.SUCCESS(
                f'Report written to {options["output"]}'))
        else:
            self.stdout.write(output)

    def _format_text(self, r):
        lines = [
            f"OFFERWALL ANALYTICS REPORT",
            f"Period: {r['period_days']} days | Generated: {r['generated_at']}",
            f"",
            f"OFFERS",
            f"  Total:   {r['offers']['total']}",
            f"  Active:  {r['offers']['active']}",
            f"  Expired: {r['offers']['expired']}",
            f"",
            f"CONVERSIONS",
            f"  Total:    {r['conversions']['total']}",
            f"  Approved: {r['conversions']['approved']}",
            f"  Pending:  {r['conversions']['pending']}",
            f"  Rejected: {r['conversions']['rejected']}",
            f"  Revenue:  ${r['conversions']['revenue']}",
            f"  Rewards:  ${r['conversions']['rewards']}",
            f"",
            f"CLICKS",
            f"  Total:     {r['clicks']['total']}",
            f"  Converted: {r['clicks']['converted']}",
            f"",
            f"METRICS",
            f"  Click-to-Conversion: {r['metrics']['ctr']}%",
        ]
        return '\n'.join(lines)
