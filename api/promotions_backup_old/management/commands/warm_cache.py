from django.core.management.base import BaseCommand
import logging
logger = logging.getLogger('management.warm_cache')

class Command(BaseCommand):
    help = 'Warm up all application caches'

    def add_arguments(self, parser):
        parser.add_argument('--tier', type=int, default=2, help='Min tier (1=critical only, 2=all important)')

    def handle(self, *args, **options):
        from api.promotions.optimization.cache_warmer import cache_warmer
        cache_warmer.warm_all(min_tier=options['tier'])
        self.stdout.write(self.style.SUCCESS(f'Cache warmed (tier≥{options["tier"]})'))
