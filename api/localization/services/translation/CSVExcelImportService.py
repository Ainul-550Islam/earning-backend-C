# services/translation/CSVExcelImportService.py
"""CSV and Excel import for non-technical translators."""
import csv
import io
import logging
from typing import Dict, List
logger = logging.getLogger(__name__)


class CSVExcelImportService:
    """Import translations from CSV/Excel — translator-friendly format."""

    def import_csv(self, csv_content: str, language_code: str, has_header: bool = True) -> Dict:
        """
        CSV format: key,value (or key,source,translated for context)
        """
        try:
            from ..models.core import Translation, TranslationKey, Language
            lang = Language.objects.filter(code=language_code, is_active=True).first()
            if not lang:
                return {"success": False, "error": f"Language {language_code} not found"}

            reader = csv.reader(io.StringIO(csv_content))
            rows = list(reader)
            if has_header and rows:
                rows = rows[1:]  # Skip header

            created = updated = failed = 0
            for row in rows:
                if not row or len(row) < 2:
                    continue
                try:
                    key_str = row[0].strip()
                    # Support: key,value OR key,source,translated
                    value = row[-1].strip()  # Always last column = translated value
                    if not key_str or not value:
                        continue
                    key_obj, _ = TranslationKey.objects.get_or_create(
                        key=key_str,
                        defaults={"description": f"Imported from CSV for {language_code}"}
                    )
                    _, was_created = Translation.objects.update_or_create(
                        key=key_obj, language=lang,
                        defaults={"value": value, "source": "import", "is_approved": False}
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1
                except Exception as row_err:
                    logger.warning(f"CSV row failed: {row}: {row_err}")
                    failed += 1

            return {"success": True, "created": created, "updated": updated, "failed": failed}
        except Exception as e:
            logger.error(f"import_csv failed: {e}")
            return {"success": False, "error": str(e)}

    def export_csv(self, language_code: str, include_source: bool = True) -> str:
        """Translator-friendly CSV export।"""
        try:
            from ..models.core import Translation, Language
            lang = Language.objects.filter(code=language_code).first()
            default_lang = Language.objects.filter(is_default=True).first()
            if not lang:
                return ""
            output = io.StringIO()
            writer = csv.writer(output)
            if include_source:
                writer.writerow(["key", "source (en)", f"translation ({language_code})", "status"])
            else:
                writer.writerow(["key", f"translation ({language_code})", "status"])

            source_map = {}
            if default_lang and include_source:
                for t in Translation.objects.filter(language=default_lang).select_related("key"):
                    source_map[t.key_id] = t.value

            for trans in Translation.objects.filter(language=lang).select_related("key").order_by("key__category", "key__key"):
                status = "approved" if trans.is_approved else "draft"
                if include_source:
                    writer.writerow([trans.key.key, source_map.get(trans.key_id, ""), trans.value, status])
                else:
                    writer.writerow([trans.key.key, trans.value, status])

            return output.getvalue()
        except Exception as e:
            logger.error(f"export_csv failed: {e}")
            return ""

    def import_excel(self, file_bytes: bytes, language_code: str) -> Dict:
        """Excel (.xlsx) import।"""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes))
            ws = wb.active
            rows = list(ws.iter_rows(min_row=2, values_only=True))
            csv_data = "\n".join(
                ",".join(f'"{str(cell or "").replace(chr(34), chr(39))}"' for cell in row)
                for row in rows if any(row)
            )
            return self.import_csv(csv_data, language_code, has_header=False)
        except ImportError:
            return {"success": False, "error": "openpyxl not installed. Run: pip install openpyxl"}
        except Exception as e:
            logger.error(f"import_excel failed: {e}")
            return {"success": False, "error": str(e)}
