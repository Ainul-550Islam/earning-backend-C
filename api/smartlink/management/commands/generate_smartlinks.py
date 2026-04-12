from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Bulk generate SmartLinks for one or all publishers'

    def add_arguments(self, parser):
        parser.add_argument('--publisher', type=str, help='Publisher username (default: all)')
        parser.add_argument('--count', type=int, default=10, help='Number of SmartLinks to generate per publisher')
        parser.add_argument('--type', type=str, default='general', help='SmartLink type')
        parser.add_argument('--dry-run', action='store_true', help='Preview without saving')

    def handle(self, *args, **options):
        from ...services.core.SmartLinkBuilderService import SmartLinkBuilderService
        builder = SmartLinkBuilderService()
        count = options['count']
        sl_type = options['type']
        dry_run = options['dry_run']

        if options['publisher']:
            try:
                publishers = [User.objects.get(username=options['publisher'])]
            except User.DoesNotExist:
                raise CommandError(f"Publisher '{options['publisher']}' not found.")
        else:
            publishers = list(User.objects.filter(is_active=True))

        total = 0
        for publisher in publishers:
            self.stdout.write(f"Generating {count} SmartLinks for {publisher.username}...")
            for i in range(count):
                if dry_run:
                    self.stdout.write(f"  [DRY RUN] Would create SmartLink #{i+1} for {publisher.username}")
                else:
                    try:
                        sl = builder.build(publisher, {'name': f'Auto-{i+1}', 'type': sl_type})
                        self.stdout.write(self.style.SUCCESS(f"  ✅ Created [{sl.slug}]"))
                        total += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"  ❌ Failed: {e}"))

        self.stdout.write(self.style.SUCCESS(f"\nDone! Total created: {total}"))
