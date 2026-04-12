# tests/test_import_export.py
from django.test import TestCase
from .factories import make_language, make_translation_key, make_translation


class ImportServiceTest(TestCase):
    def setUp(self):
        self.lang = make_language(code='ti-ie', name='Import Export Test', is_default=False)

    def test_import_json_creates_translations(self):
        from localization.services.translation.TranslationImportService import TranslationImportService
        data = {
            'import.test.hello': 'হ্যালো',
            'import.test.bye': 'বিদায়',
            'import.test.yes': 'হ্যাঁ',
        }
        result = TranslationImportService().import_json(data, 'ti-ie')
        self.assertTrue(result['success'])
        self.assertEqual(result['created'] + result['updated'], 3)

    def test_import_json_invalid_language(self):
        from localization.services.translation.TranslationImportService import TranslationImportService
        result = TranslationImportService().import_json({'key': 'val'}, 'xx-invalid')
        self.assertFalse(result['success'])

    def test_import_json_duplicate_updates(self):
        from localization.services.translation.TranslationImportService import TranslationImportService
        data = {'dup.key': 'First Value'}
        TranslationImportService().import_json(data, 'ti-ie')
        data2 = {'dup.key': 'Second Value'}
        result = TranslationImportService().import_json(data2, 'ti-ie')
        self.assertTrue(result['success'])
        self.assertGreaterEqual(result['updated'], 1)

    def test_import_po_basic(self):
        from localization.services.translation.TranslationImportService import TranslationImportService
        po_content = (
            'msgid ""\nmsgstr ""\n'
            '"Language: ti-ie\\n"\n\n'
            'msgid "po.test.key"\nmsgstr "PO Value"\n'
        )
        result = TranslationImportService().import_po(po_content, 'ti-ie')
        self.assertTrue(result['success'])

    def test_import_xliff_basic(self):
        from localization.services.translation.TranslationImportService import TranslationImportService
        xliff = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">'
            '<file source-language="en" target-language="ti-ie" datatype="plaintext" original="test">'
            '<body>'
            '<trans-unit id="xliff.import.key">'
            '<source>Hello</source>'
            '<target>হ্যালো XLIFF</target>'
            '</trans-unit>'
            '</body></file></xliff>'
        )
        result = TranslationImportService().import_xliff(xliff, 'ti-ie')
        self.assertTrue(result['success'])


class ExportServiceTest(TestCase):
    def setUp(self):
        self.lang = make_language(code='te-exp', name='Export Test Lang', is_default=False)
        key = make_translation_key(key='export.test.key')
        make_translation(key=key, language=self.lang, value='Export Test Value')

    def test_export_json_returns_dict(self):
        from localization.services.translation.TranslationExportService import TranslationExportService
        result = TranslationExportService().export_json('te-exp')
        self.assertTrue(result['success'])
        self.assertIsInstance(result['data'], dict)
        self.assertIn('export.test.key', result['data'])

    def test_export_json_invalid_language(self):
        from localization.services.translation.TranslationExportService import TranslationExportService
        result = TranslationExportService().export_json('xx-invalid')
        self.assertFalse(result['success'])

    def test_export_po_contains_msgid(self):
        from localization.services.translation.TranslationExportService import TranslationExportService
        po = TranslationExportService().export_po('te-exp')
        self.assertIn('msgid', po)
        self.assertIn('msgstr', po)
        self.assertIn('export.test.key', po)

    def test_export_xliff_valid_xml(self):
        from localization.services.translation.TranslationExportService import TranslationExportService
        import xml.etree.ElementTree as ET
        xliff = TranslationExportService().export_xliff('te-exp')
        self.assertIn('trans-unit', xliff)
        try:
            root = ET.fromstring(xliff)
            self.assertIsNotNone(root)
        except ET.ParseError:
            self.fail("XLIFF output is not valid XML")

    def test_export_approved_only(self):
        from localization.services.translation.TranslationExportService import TranslationExportService
        from localization.models.core import Translation
        lang = make_language(code='te-ap', name='Approved Only', is_default=False)
        approved_key = make_translation_key(key='approved.key')
        unapproved_key = make_translation_key(key='unapproved.key')
        make_translation(key=approved_key, language=lang, value='Approved', is_approved=True)
        t = make_translation(key=unapproved_key, language=lang, value='Unapproved', is_approved=False)
        t.is_approved = False
        t.save()
        result = TranslationExportService().export_json('te-ap', approved_only=True)
        self.assertIn('approved.key', result['data'])
        self.assertNotIn('unapproved.key', result['data'])
