from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Evaluate all publisher quality tiers (Gold/Silver/Bronze/Standard)'

    def add_arguments(self, parser):
        parser.add_argument('--publisher', type=str, help='Evaluate specific publisher only')
        parser.add_argument('--dry-run', action='store_true', help='Show results without saving')

    def handle(self, *args, **options):
        from ...services.publisher.PublisherTierService import PublisherTierService
        svc = PublisherTierService()

        if options['publisher']:
            try:
                publishers = [User.objects.get(username=options['publisher'])]
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Publisher not found."))
                return
        else:
            publishers = list(User.objects.filter(is_active=True, smartlinks__isnull=False).distinct())

        self.stdout.write(f"Evaluating {len(publishers)} publishers...\n")
        tier_counts = {}

        for pub in publishers:
            try:
                result = svc.evaluate_publisher(pub)
                tier   = result['tier']
                tier_counts[tier] = tier_counts.get(tier, 0) + 1

                emoji = {'gold': '🥇', 'silver': '🥈', 'bronze': '🥉',
                         'standard': '⚪', 'under_review': '🔴'}.get(tier, '⚪')

                self.stdout.write(
                    f"  {emoji} {pub.username:30s} → {tier:15s} "
                    f"quality={result['quality_rate']:.1f}% "
                    f"unique={result['unique_rate']:.1f}%"
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ❌ {pub.username}: {e}"))

        self.stdout.write(f"\n=== Summary ===")
        for tier, count in sorted(tier_counts.items()):
            self.stdout.write(f"  {tier}: {count}")
