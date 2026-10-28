"""
api/offerwall/management/commands/expire_offers.py

Auto-pause offers whose end_date has passed.

Usage::

    python manage.py expire_offers
    python manage.py expire_offers --dry-run
    python manage.py expire_offers --batch-size 200

Schedule via cron / Celery beat every 15 minutes.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Auto-pause offers whose end_date has passed'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would be expired without changing anything',
        )
        parser.add_argument(
            '--batch-size', type=int, default=100,
            help='Number of offers to update per DB query (default 100)',
        )

    def handle(self, *args, **options):
        from api.offerwall.models import Offer

        dry_run    = options['dry_run']
        batch_size = options['batch_size']
        now        = timezone.now()

        # Offers that have an end_date in the past and are still active
        expired_qs = Offer.objects.filter(
            status='active',
            end_date__lt=now,
        )

        count = expired_qs.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('No offers to expire.'))
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'[dry-run] Would expire {count} offer(s):'
                )
            )
            for o in expired_qs[:20]:
                self.stdout.write(f'  • {o.title} (end_date: {o.end_date})')
            if count > 20:
                self.stdout.write(f'  … and {count - 20} more')
            return

        # Process in batches to avoid long DB locks
        expired   = 0
        batch_ids = list(
            expired_qs.values_list('id', flat=True)[:batch_size]
        )

        while batch_ids:
            updated = Offer.objects.filter(id__in=batch_ids).update(
                status='expired',
                updated_at=now,
            )
            expired += updated

            # Audit each expired offer
            for offer_id in batch_ids:
                try:
                    self._audit_expire(offer_id, now)
                except Exception:
                    pass

            # Next batch
            batch_ids = list(
                expired_qs.exclude(id__in=batch_ids)
                          .values_list('id', flat=True)[:batch_size]
            )

        self.stdout.write(
            self.style.SUCCESS(f'Expired {expired} offer(s) at {now}')
        )

    @staticmethod
    def _audit_expire(offer_id, now):
        try:
            from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory
            OfferwallAdapterFactory.get('audit').send({
                'user_id': None,
                'action':  'OFFER_EXPIRED',
                'message': f'Offer auto-expired: {offer_id}',
                'metadata': {'offer_id': str(offer_id), 'expired_at': now.isoformat()},
            })
        except Exception:
            pass
