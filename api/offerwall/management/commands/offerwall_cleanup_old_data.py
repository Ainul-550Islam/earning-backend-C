"""
Management command: cleanup_old_data
Archive / delete old offer clicks, expired offers, and stale fraud logs.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Clean up old offerwall data to keep the database lean'

    def add_arguments(self, parser):
        parser.add_argument('--click-days', type=int, default=90,
                            help='Delete offer clicks older than N days')
        parser.add_argument('--expired-offer-days', type=int, default=180,
                            help='Delete expired offers older than N days')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from api.offerwall.models import OfferClick, Offer

        dry_run = options['dry_run']
        now     = timezone.now()
        tag     = '[DRY]' if dry_run else ''

        # 1. Old clicks (non-converted)
        click_cutoff = now - timedelta(days=options['click_days'])
        old_clicks   = OfferClick.objects.filter(
            clicked_at__lt=click_cutoff, is_converted=False)
        n_clicks = old_clicks.count()
        self.stdout.write(f'{tag} Old non-converted clicks to delete: {n_clicks}')
        if not dry_run:
            old_clicks.delete()

        # 2. Old expired offers
        offer_cutoff = now - timedelta(days=options['expired_offer_days'])
        old_offers   = Offer.objects.filter(
            status='expired', updated_at__lt=offer_cutoff)
        n_offers = old_offers.count()
        self.stdout.write(f'{tag} Old expired offers to delete: {n_offers}')
        if not dry_run:
            old_offers.delete()

        self.stdout.write(self.style.SUCCESS(
            f'Done — clicks_deleted={n_clicks if not dry_run else 0} '
            f'offers_deleted={n_offers if not dry_run else 0}'))
