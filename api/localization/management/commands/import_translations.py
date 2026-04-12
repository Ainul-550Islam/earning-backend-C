# management/commands/import_translations.py
"""python manage.py import_translations --file=trans.json --language=bn --format=json"""
from django.core.management.base import BaseCommand, CommandError
import os

class Command(BaseCommand):
    help = 'JSON/PO/XLIFF file থেকে translations import করে'

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Path to import file')
        parser.add_argument('--language', required=True, help='Target language code (e.g. bn)')
        parser.add_argument('--format', default='json', choices=['json','po','xliff'], help='File format')
        parser.add_argument('--namespace', default='', help='Namespace/category filter')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be imported without saving')

    def handle(self, *args, **options):
        file_path = options['file']
        language_code = options['language']
        fmt = options['format']
        namespace = options.get('namespace', '')
        dry_run = options.get('dry_run', False)
        if not os.path.exists(file_path):
            raise CommandError(f"File not found: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        from localization.services.translation.TranslationImportService import TranslationImportService
        service = TranslationImportService()
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be saved"))
        if fmt == 'json':
            import json
            data = json.loads(content)
            result = service.import_json(data, language_code, namespace)
        elif fmt == 'po':
            result = service.import_po(content, language_code)
        elif fmt == 'xliff':
            result = service.import_xliff(content, language_code)
        else:
            raise CommandError(f"Unknown format: {fmt}")
        if result.get('success'):
            self.stdout.write(self.style.SUCCESS(
                f"Import complete: {result.get('created',0)} created, {result.get('updated',0)} updated, {result.get('failed',0)} failed"
            ))
        else:
            raise CommandError(f"Import failed: {result.get('error')}")
