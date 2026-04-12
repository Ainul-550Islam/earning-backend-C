# management/commands/check_coverage.py
"""python manage.py check_coverage"""
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Translation coverage report print করে'

    def handle(self, *args, **options):
        from localization.services.translation.TranslationCoverageService import TranslationCoverageService
        service = TranslationCoverageService()
        results = service.calculate_all()
        self.stdout.write("=" * 60)
        self.stdout.write("TRANSLATION COVERAGE REPORT")
        self.stdout.write("=" * 60)
        for r in sorted(results, key=lambda x: x['coverage_percent'], reverse=True):
            bar_len = int(r['coverage_percent'] / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            self.stdout.write(f"[{r['language']:6}] {bar} {r['coverage_percent']:6.1f}%  ({r['translated']}/{r['total_keys']} keys, {r['missing']} missing)")
