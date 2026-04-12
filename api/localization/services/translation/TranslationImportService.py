# services/translation/TranslationImportService.py
"""Import translations from JSON, PO, XLIFF formats"""
import json
import re
import logging
from typing import Dict, List
from django.utils import timezone

logger = logging.getLogger(__name__)


class TranslationImportService:

    def import_json(self, data: Dict, language_code: str, overwrite: bool = True) -> Dict:
        """JSON dict import করে — {'key': 'value', ...}"""
        try:
            from ...models.core import Language, Translation, TranslationKey
            if not isinstance(data, dict):
                return {'success': False, 'error': 'Data must be a dict'}
            lang = Language.objects.filter(code=language_code).first()
            if not lang:
                return {'success': False, 'error': f'Language {language_code} not found'}
            created = updated = skipped = 0
            for key_str, value in data.items():
                if not isinstance(key_str, str) or not isinstance(value, str):
                    skipped += 1
                    continue
                parts = key_str.split('.')
                category = parts[0] if len(parts) > 1 else 'common'
                tkey, _ = TranslationKey.objects.get_or_create(
                    key=key_str, defaults={'category': category, 'is_active': True}
                )
                trans, was_created = Translation.objects.get_or_create(
                    key=tkey, language=lang,
                    defaults={'value': value, 'source': 'import', 'is_approved': True}
                )
                if was_created:
                    created += 1
                elif overwrite and trans.value != value:
                    trans.value = value
                    trans.source = 'import'
                    trans.save(update_fields=['value', 'source'])
                    updated += 1
                else:
                    skipped += 1
            return {'success': True, 'created': created, 'updated': updated, 'skipped': skipped}
        except Exception as e:
            logger.error(f"import_json failed: {e}")
            return {'success': False, 'error': str(e)}

    def import_po(self, po_content: str, language_code: str) -> Dict:
        """Gettext PO format import করে"""
        try:
            from ...models.core import Language
            lang = Language.objects.filter(code=language_code).first()
            if not lang:
                return {'success': False, 'error': f'Language {language_code} not found'}

            # Parse PO entries
            data = {}
            # Pattern: msgid "key" followed by msgstr "value"
            pattern = re.compile(
                r'msgid\s+"([^"]+)"\s+msgstr\s+"([^"]*)"',
                re.DOTALL
            )
            for match in pattern.finditer(po_content):
                key = match.group(1).replace('\\n', '\n').replace('\\"', '"')
                value = match.group(2).replace('\\n', '\n').replace('\\"', '"')
                if key and value:
                    data[key] = value

            if not data:
                # Try multiline msgstr
                entries = re.split(r'\n\n+', po_content)
                for entry in entries:
                    msgid_m = re.search(r'msgid\s+"(.+?)"', entry, re.DOTALL)
                    msgstr_m = re.search(r'msgstr\s+"(.+?)"', entry, re.DOTALL)
                    if msgid_m and msgstr_m:
                        key = msgid_m.group(1).strip()
                        value = msgstr_m.group(1).strip()
                        if key:
                            data[key] = value

            return self.import_json(data, language_code)
        except Exception as e:
            logger.error(f"import_po failed: {e}")
            return {'success': False, 'error': str(e)}

    def import_xliff(self, xliff_content: str, language_code: str) -> Dict:
        """XLIFF format import করে"""
        try:
            import xml.etree.ElementTree as ET
            from ...models.core import Language
            lang = Language.objects.filter(code=language_code).first()
            if not lang:
                return {'success': False, 'error': f'Language {language_code} not found'}

            data = {}
            try:
                root = ET.fromstring(xliff_content)
                ns = {'x': 'urn:oasis:names:tc:xliff:document:1.2'}
                # Try with namespace
                units = root.findall('.//x:trans-unit', ns) or root.findall('.//trans-unit')
                for unit in units:
                    uid = unit.get('id', '')
                    target = unit.find('x:target', ns) or unit.find('target')
                    source = unit.find('x:source', ns) or unit.find('source')
                    if uid and target is not None and target.text:
                        data[uid] = target.text
                    elif uid and source is not None and source.text:
                        data[uid] = source.text  # Use source as fallback
            except ET.ParseError as e:
                return {'success': False, 'error': f'Invalid XLIFF XML: {e}'}

            return self.import_json(data, language_code)
        except Exception as e:
            logger.error(f"import_xliff failed: {e}")
            return {'success': False, 'error': str(e)}

    def import_csv(self, csv_content: str, language_code: str) -> Dict:
        """CSV format import করে — key,value columns"""
        try:
            import csv
            import io
            reader = csv.DictReader(io.StringIO(csv_content))
            data = {}
            for row in reader:
                key = row.get('key', '').strip()
                value = row.get('value', '').strip()
                if key and value:
                    data[key] = value
            return self.import_json(data, language_code)
        except Exception as e:
            logger.error(f"import_csv failed: {e}")
            return {'success': False, 'error': str(e)}
