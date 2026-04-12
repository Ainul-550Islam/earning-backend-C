# management/commands/validate_translations.py
"""python manage.py validate_translations --language=bn"""
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'All translations QA check করে'

    def add_arguments(self, parser):
        parser.add_argument('--language', help='Language code (all if not specified)')
        parser.add_argument('--show-warnings', action='store_true')

    def handle(self, *args, **options):
        from localization.services.translation.TranslationQAService import TranslationQAService
        from localization.models.core import Language
        service = TranslationQAService()
        lang_code = options.get('language')
        show_warnings = options.get('show_warnings', False)
        if lang_code:
            langs = Language.objects.filter(code=lang_code, is_active=True)
        else:
            langs = Language.objects.filter(is_active=True, is_default=False)
        total_issues = 0
        for lang in langs:
            result = service.run_batch_qa(lang.code)
            failed = result.get('failed', 0)
            total = result.get('total', 0)
            self.stdout.write(f"[{lang.code}] {total} checked — {failed} issues, {result.get('warnings',0)} warnings")
            total_issues += failed
            if failed > 0:
                for issue in result.get('issues', [])[:5]:
                    self.stderr.write(f"  ✗ {issue['key']}: {issue['issues']}")
        if total_issues == 0:
            self.stdout.write(self.style.SUCCESS("All translations passed QA!"))
        else:
            self.stdout.write(self.style.WARNING(f"Total issues found: {total_issues}"))
