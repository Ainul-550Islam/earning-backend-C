# management/commands/export_translations.py
"""python manage.py export_translations --language=bn --format=json --output=bn.json"""
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Translations JSON/PO/XLIFF format-এ export করে'

    def add_arguments(self, parser):
        parser.add_argument('--language', required=True, help='Language code to export')
        parser.add_argument('--format', default='json', choices=['json','po','xliff'])
        parser.add_argument('--output', help='Output file path (default: stdout)')
        parser.add_argument('--namespace', default='', help='Filter by namespace')
        parser.add_argument('--all', action='store_true', help='Include unapproved translations')

    def handle(self, *args, **options):
        language_code = options['language']
        fmt = options['format']
        output_file = options.get('output')
        namespace = options.get('namespace', '')
        approved_only = not options.get('all', False)
        from localization.services.translation.TranslationExportService import TranslationExportService
        service = TranslationExportService()
        if fmt == 'json':
            result = service.export_json(language_code, namespace, approved_only)
            import json
            content = json.dumps(result.get('data', {}), ensure_ascii=False, indent=2)
        elif fmt == 'po':
            content = service.export_po(language_code)
        elif fmt == 'xliff':
            content = service.export_xliff(language_code)
        else:
            raise CommandError(f"Unknown format: {fmt}")
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            self.stdout.write(self.style.SUCCESS(f"Exported to: {output_file}"))
        else:
            self.stdout.write(content)
