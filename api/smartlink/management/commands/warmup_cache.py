from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Pre-warm Redis cache for all active SmartLinks'

    def add_arguments(self, parser):
        parser.add_argument('--slugs', nargs='+', type=str, help='Warm only specific slugs')

    def handle(self, *args, **options):
        from ...services.core.SmartLinkCacheService import SmartLinkCacheService
        svc = SmartLinkCacheService()

        if options['slugs']:
            count = svc.warmup(options['slugs'])
            self.stdout.write(self.style.SUCCESS(f'✅ Warmed {count}/{len(options["slugs"])} specified slugs.'))
        else:
            self.stdout.write('Warming cache for all active SmartLinks...')
            count = svc.warmup_all_active()
            self.stdout.write(self.style.SUCCESS(f'✅ Cache warmed for {count} SmartLinks.'))
