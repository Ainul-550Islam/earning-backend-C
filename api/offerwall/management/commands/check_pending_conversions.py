"""
Management command: check_pending_conversions
Polls each active provider for status updates on pending conversions.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Check and update status of pending conversions from providers'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=24,
                            help='Look back N hours for pending conversions')
        parser.add_argument('--provider', type=str, default=None,
                            help='Specific provider type to check')
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would change without changing it')

    def handle(self, *args, **options):
        from api.offerwall.models import OfferConversion, OfferProvider

        since    = timezone.now() - timedelta(hours=options['hours'])
        dry_run  = options['dry_run']
        provider_type = options.get('provider')

        qs = OfferConversion.objects.filter(
            status='pending',
            converted_at__gte=since,
        ).select_related('offer__provider')

        if provider_type:
            qs = qs.filter(offer__provider__provider_type=provider_type)

        total = qs.count()
        self.stdout.write(f'Found {total} pending conversions since {since:%Y-%m-%d %H:%M}')

        updated = approved = rejected = 0
        for conv in qs.iterator(chunk_size=100):
            ptype = conv.offer.provider.provider_type if conv.offer else 'unknown'
            if dry_run:
                self.stdout.write(f'  [DRY] would check {conv.conversion_id} ({ptype})')
                continue

            try:
                # Each provider's service can implement check_conversion_status()
                # For now we auto-approve after review window
                if (timezone.now() - conv.converted_at).total_seconds() > 24 * 3600:
                    conv.status = 'approved'
                    conv.approved_at = timezone.now()
                    conv.save(update_fields=['status', 'approved_at'])
                    approved += 1
                    updated  += 1
                    self.stdout.write(f'  ✅ Approved: {conv.conversion_id}')
            except Exception as exc:
                self.stdout.write(self.style.ERROR(
                    f'  ❌ Error on {conv.conversion_id}: {exc}'))

        self.stdout.write(self.style.SUCCESS(
            f'Done — updated={updated} approved={approved} rejected={rejected}'))
