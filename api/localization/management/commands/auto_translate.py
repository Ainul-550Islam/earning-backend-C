# management/commands/auto_translate.py
"""python manage.py auto_translate --language=bn --limit=100"""
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Missing translations auto-translate করে'

    def add_arguments(self, parser):
        parser.add_argument('--language', help='Target language code (all if not specified)')
        parser.add_argument('--limit', type=int, default=100, help='Max translations per language')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from localization.services.translation.AutoTranslationService import AutoTranslationService
        from localization.models.core import Language
        service = AutoTranslationService()
        lang_code = options.get('language')
        limit = options.get('limit', 100)
        dry_run = options.get('dry_run', False)
        if lang_code:
            langs = Language.objects.filter(code=lang_code, is_active=True)
        else:
            langs = Language.objects.filter(is_active=True, is_default=False)
        for lang in langs:
            result = service.translate_missing(lang.code, limit=limit, dry_run=dry_run)
            self.stdout.write(f"[{lang.code}] translated={result.get('translated',0)} failed={result.get('failed',0)}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes saved"))
