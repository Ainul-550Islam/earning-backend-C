# tests/test_integration.py
"""Full flow integration tests"""
from django.test import TestCase
from .factories import make_language, make_country, make_currency, make_translation_key, make_translation


class FullLocalizationFlowTest(TestCase):
    def setUp(self):
        self.en = make_language(code='te-int-en', name='Integration English', is_default=True)
        self.bn = make_language(code='te-int-bn', name='Integration Bengali', is_default=False)
        self.key = make_translation_key(key='integration.test.key', category='integration')
        self.en_trans = make_translation(key=self.key, language=self.en, value='Integration Test')
        self.bn_trans = make_translation(key=self.key, language=self.bn, value='ইন্টিগ্রেশন টেস্ট')

    def test_full_translation_flow(self):
        from localization.models.core import Translation
        trans = Translation.objects.filter(key=self.key, language=self.bn, is_approved=True).first()
        self.assertIsNotNone(trans)
        self.assertEqual(trans.value, 'ইন্টিগ্রেশন টেস্ট')

    def test_missing_translation_fallback(self):
        new_key = make_translation_key(key='integration.missing.key')
        from localization.models.core import Translation
        # No translation for bn — should not exist
        trans = Translation.objects.filter(key=new_key, language=self.bn).first()
        self.assertIsNone(trans)

    def test_import_then_export(self):
        from localization.services.translation.TranslationImportService import TranslationImportService
        from localization.services.translation.TranslationExportService import TranslationExportService
        # Import
        importer = TranslationImportService()
        result = importer.import_json({'flow.test.hello': 'হ্যালো ফ্লো'}, 'te-int-bn')
        self.assertTrue(result['success'])
        # Export
        exporter = TranslationExportService()
        export = exporter.export_json('te-int-bn')
        self.assertIn('flow.test.hello', export['data'])
