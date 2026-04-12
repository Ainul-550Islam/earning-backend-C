# management/commands/warm_cache.py
"""python manage.py warm_cache — pre-warm all localization caches"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Pre-warm localization caches for better performance'

    def add_arguments(self, parser):
        parser.add_argument('--languages', nargs='+', help='Language codes to warm')
        parser.add_argument('--namespaces', nargs='+', default=['global'], help='Namespaces to warm')
        parser.add_argument('--all-languages', action='store_true', help='Warm all active languages')

    def handle(self, *args, **options):
        from localization.utils.cache_warming import (
            warm_languages, warm_countries, warm_currencies,
            warm_exchange_rates, warm_translations, get_cache_stats,
        )
        self.stdout.write("Warming localization caches...")

        # Always warm stable data
        ok = warm_languages()
        self.stdout.write(f"  Languages: {'OK' if ok else 'FAILED'}")
        ok = warm_countries()
        self.stdout.write(f"  Countries: {'OK' if ok else 'FAILED'}")
        ok = warm_currencies()
        self.stdout.write(f"  Currencies: {'OK' if ok else 'FAILED'}")
        ok = warm_exchange_rates()
        self.stdout.write(f"  Exchange rates: {'OK' if ok else 'FAILED'}")

        # Translation packs
        from localization.models.core import Language
        languages = options.get('languages') or []
        if options.get('all_languages'):
            languages = list(Language.objects.filter(is_active=True).values_list('code', flat=True))

        namespaces = options.get('namespaces', ['global'])
        for lang_code in languages:
            for ns in namespaces:
                ok = warm_translations(lang_code, ns)
                self.stdout.write(f"  Translation pack [{lang_code}/{ns}]: {'OK' if ok else 'FAILED'}")

        stats = get_cache_stats()
        self.stdout.write(self.style.SUCCESS(f"\nCache warming complete. Stats: {stats}"))
