"""
Management command: recalculate_rewards
Recalculate reward amounts for a batch of approved conversions.
Useful when revenue-share rates change or bonus rules are updated.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Recalculate reward amounts for approved conversions'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30,
                            help='Recalculate conversions from the last N days')
        parser.add_argument('--provider', type=str, default=None,
                            help='Restrict to a specific provider type')
        parser.add_argument('--dry-run', action='store_true',
                            help='Show changes without saving')

    def handle(self, *args, **options):
        from api.offerwall.models import OfferConversion
        from api.offerwall.utils.RewardCalculator import RewardCalculator

        since    = timezone.now() - timedelta(days=options['days'])
        dry_run  = options['dry_run']
        ptype    = options.get('provider')

        qs = OfferConversion.objects.filter(
            status='approved',
            converted_at__gte=since,
        ).select_related('offer', 'offer__provider')

        if ptype:
            qs = qs.filter(offer__provider__provider_type=ptype)

        total   = qs.count()
        changed = 0
        self.stdout.write(f'Recalculating rewards for {total} conversions…')

        for conv in qs.iterator(chunk_size=100):
            try:
                calc = RewardCalculator(conv.offer, conv.offer.provider)
                data = calc.calculate_total_reward(float(conv.payout_amount))
                new_reward = data.get('total_reward', float(conv.reward_amount))

                if abs(float(conv.reward_amount) - new_reward) > 0.0001:
                    changed += 1
                    self.stdout.write(
                        f'  {"[DRY]" if dry_run else ""} '
                        f'{conv.conversion_id}: '
                        f'{conv.reward_amount} → {new_reward:.6f}')
                    if not dry_run:
                        from decimal import Decimal
                        conv.reward_amount = Decimal(str(new_reward))
                        conv.save(update_fields=['reward_amount'])
            except Exception as exc:
                self.stdout.write(self.style.ERROR(
                    f'  ❌ Error on {conv.conversion_id}: {exc}'))

        self.stdout.write(self.style.SUCCESS(
            f'Done — total={total} changed={changed}'))
