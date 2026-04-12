# tests/test_translation_service.py
from django.test import TestCase
from .factories import make_language, make_translation_key, make_translation


class TranslationImportExportTest(TestCase):
    def setUp(self):
        self.lang = make_language(code='te-ie', name='Import Export Test', is_default=False)

    def test_import_json(self):
        from localization.services.translation.TranslationImportService import TranslationImportService
        service = TranslationImportService()
        data = {'hello': 'হ্যালো', 'goodbye': 'বিদায়'}
        result = service.import_json(data, 'te-ie')
        self.assertTrue(result['success'])
        self.assertGreaterEqual(result['created'] + result['updated'], 2)

    def test_export_json(self):
        from localization.services.translation.TranslationExportService import TranslationExportService
        key = make_translation_key(key='test.export.key')
        make_translation(key=key, language=self.lang, value='Export Test Value')
        service = TranslationExportService()
        result = service.export_json('te-ie')
        self.assertTrue(result['success'])
        self.assertIn('test.export.key', result['data'])

    def test_export_po(self):
        from localization.services.translation.TranslationExportService import TranslationExportService
        key = make_translation_key(key='test.po.key')
        make_translation(key=key, language=self.lang, value='PO Test Value')
        service = TranslationExportService()
        po_content = service.export_po('te-ie')
        self.assertIn('msgid', po_content)
        self.assertIn('msgstr', po_content)
