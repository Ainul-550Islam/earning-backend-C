# services/translation/TranslationExportService.py
"""Export translations in JSON, PO, XLIFF, CSV formats"""
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TranslationExportService:

    def export_json(self, language_code: str, approved_only: bool = True) -> Dict:
        """Export translations as JSON dict"""
        try:
            from ...models.core import Language, Translation
            lang = Language.objects.filter(code=language_code).first()
            if not lang:
                return {'success': False, 'error': f'Language {language_code} not found'}
            qs = Translation.objects.filter(language=lang).select_related('key')
            if approved_only:
                qs = qs.filter(is_approved=True)
            data = {}
            for trans in qs.exclude(value=''):
                data[trans.key.key] = trans.value
            return {'success': True, 'language': language_code, 'data': data, 'count': len(data)}
        except Exception as e:
            logger.error(f"export_json failed: {e}")
            return {'success': False, 'error': str(e)}

    def export_po(self, language_code: str, approved_only: bool = True) -> str:
        """Export translations as Gettext PO format"""
        try:
            from ...models.core import Language, Translation
            lang = Language.objects.filter(code=language_code).first()
            if not lang:
                return ''
            lines = [
                '# Translation file',
                f'# Language: {language_code}',
                'msgid ""',
                'msgstr ""',
                f'"Language: {language_code}\\n"',
                '"Content-Type: text/plain; charset=UTF-8\\n"',
                '',
            ]
            qs = Translation.objects.filter(language=lang).select_related('key')
            if approved_only:
                qs = qs.filter(is_approved=True)
            for trans in qs.exclude(value=''):
                if trans.key.description:
                    lines.append(f'# {trans.key.description}')
                # Escape properly without f-string multiline issues
                msgid = trans.key.key.replace('"', '\\"').replace('\n', '\\n')
                msgstr = (trans.value or '').replace('"', '\\"').replace('\n', '\\n')
                lines.extend([f'msgid "{msgid}"', f'msgstr "{msgstr}"', ''])
            return '\n'.join(lines)
        except Exception as e:
            logger.error(f"export_po failed: {e}")
            return ''

    def export_xliff(self, language_code: str, source_language: str = 'en',
                     approved_only: bool = True) -> str:
        """Export translations as XLIFF 1.2 format"""
        try:
            from ...models.core import Language, Translation
            lang = Language.objects.filter(code=language_code).first()
            if not lang:
                return ''
            qs = Translation.objects.filter(language=lang).select_related('key')
            if approved_only:
                qs = qs.filter(is_approved=True)

            def esc(s):
                return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

            lines = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                f'<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">',
                f'  <file source-language="{source_language}" target-language="{language_code}"'
                f' datatype="plaintext" original="translations">',
                '  <body>',
            ]
            for trans in qs.exclude(value=''):
                lines.append(f'    <trans-unit id="{esc(trans.key.key)}">')
                lines.append(f'      <source>{esc(trans.key.key)}</source>')
                lines.append(f'      <target>{esc(trans.value)}</target>')
                lines.append('    </trans-unit>')
            lines.extend(['  </body>', '  </file>', '</xliff>'])
            return '\n'.join(lines)
        except Exception as e:
            logger.error(f"export_xliff failed: {e}")
            return ''

    def export_csv(self, language_code: str, approved_only: bool = True) -> str:
        """Export translations as CSV"""
        try:
            from ...models.core import Language, Translation
            import csv
            import io
            lang = Language.objects.filter(code=language_code).first()
            if not lang:
                return ''
            qs = Translation.objects.filter(language=lang).select_related('key')
            if approved_only:
                qs = qs.filter(is_approved=True)
            output = io.StringIO()
            writer = csv.writer(output, quoting=csv.QUOTE_ALL)
            writer.writerow(['key', 'value', 'category', 'approved'])
            for trans in qs.exclude(value=''):
                writer.writerow([
                    trans.key.key, trans.value or '',
                    trans.key.category or '', trans.is_approved,
                ])
            return output.getvalue()
        except Exception as e:
            logger.error(f"export_csv failed: {e}")
            return ''
