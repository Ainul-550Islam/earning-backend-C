from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Find and report SmartLinks with 0 active offers in their pool'

    def add_arguments(self, parser):
        parser.add_argument('--fix', action='store_true', help='Auto-pause broken SmartLinks')

    def handle(self, *args, **options):
        from ...models import SmartLink
        broken = SmartLink.objects.filter(
            is_active=True, is_archived=False
        ).exclude(offer_pool__entries__is_active=True).select_related('publisher')

        if not broken.exists():
            self.stdout.write(self.style.SUCCESS('✅ No broken SmartLinks found!'))
            return

        self.stdout.write(self.style.WARNING(f'⚠️  Found {broken.count()} broken SmartLinks:\n'))
        for sl in broken:
            self.stdout.write(f'  [{sl.slug}] "{sl.name}" — publisher: {sl.publisher.username}')

        if options['fix']:
            count = broken.update(is_active=False)
            self.stdout.write(self.style.SUCCESS(f'\n✅ Auto-paused {count} broken SmartLinks.'))
