# api/djoyalty/management/commands/cleanup_expired_offers.py
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Cleanup expired offers, vouchers, personalized offers।'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from django.utils import timezone
        dry = options['dry_run']

        if dry:
            self.stdout.write(self.style.WARNING('DRY RUN'))

        now = timezone.now()
        results = {}

        # Expire offers
        try:
            from djoyalty.models.offerwall import Offer
            qs = Offer.objects.filter(status='active', valid_until__lt=now)
            results['offers'] = qs.count()
            if not dry:
                qs.update(status='ended')
        except Exception as e:
            results['offers_error'] = str(e)

        # Expire vouchers
        try:
            from djoyalty.models.redemption import Voucher
            qs = Voucher.objects.filter(status='active', expires_at__lt=now)
            results['vouchers'] = qs.count()
            if not dry:
                qs.update(status='expired')
        except Exception as e:
            results['vouchers_error'] = str(e)

        # Expire AI offers
        try:
            from djoyalty.models.ai_personalization import PersonalizedOffer
            qs = PersonalizedOffer.objects.filter(status='active', valid_until__lt=now)
            results['ai_offers'] = qs.count()
            if not dry:
                qs.update(status='expired')
        except Exception as e:
            results['ai_offers_error'] = str(e)

        # Expire scratch cards
        try:
            from djoyalty.models.gamification import ScratchCard
            qs = ScratchCard.objects.filter(status='unscratched', expires_at__lt=now)
            results['scratch_cards'] = qs.count()
            if not dry:
                qs.update(status='expired')
        except Exception as e:
            results['scratch_cards_error'] = str(e)

        for key, val in results.items():
            self.stdout.write(f'  {key}: {val}')

        action = 'Would expire' if dry else 'Expired'
        self.stdout.write(self.style.SUCCESS(
            f'\n{action}: '
            f'{results.get("offers", 0)} offers, '
            f'{results.get("vouchers", 0)} vouchers, '
            f'{results.get("ai_offers", 0)} AI offers, '
            f'{results.get("scratch_cards", 0)} scratch cards'
        ))
