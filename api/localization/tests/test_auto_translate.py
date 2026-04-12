# tests/test_auto_translate.py
from django.test import TestCase
from .factories import make_language, make_translation_key, make_translation


class AutoTranslationServiceTest(TestCase):
    def setUp(self):
        self.src_lang = make_language(code='at-src', name='AutoTrans Source', is_default=True)
        self.tgt_lang = make_language(code='at-tgt', name='AutoTrans Target', is_default=False)
        for i in range(5):
            key = make_translation_key(key=f'auto.trans.key.{i}')
            make_translation(key=key, language=self.src_lang, value=f'Source text {i}')

    def test_translate_missing_dry_run(self):
        from localization.services.translation.AutoTranslationService import AutoTranslationService
        result = AutoTranslationService().translate_missing('at-tgt', limit=10, dry_run=True)
        self.assertTrue(result['success'])
        self.assertTrue(result['dry_run'])
        self.assertIn('total_missing', result)
        self.assertIn('translated', result)

    def test_dry_run_no_db_changes(self):
        from localization.services.translation.AutoTranslationService import AutoTranslationService
        from localization.models.core import Translation
        before = Translation.objects.filter(language=self.tgt_lang).count()
        AutoTranslationService().translate_missing('at-tgt', limit=10, dry_run=True)
        after = Translation.objects.filter(language=self.tgt_lang).count()
        self.assertEqual(before, after)

    def test_translate_missing_invalid_language(self):
        from localization.services.translation.AutoTranslationService import AutoTranslationService
        result = AutoTranslationService().translate_missing('xx-invalid', limit=5)
        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_missing_count_correct(self):
        from localization.services.translation.AutoTranslationService import AutoTranslationService
        result = AutoTranslationService().translate_missing('at-tgt', limit=100, dry_run=True)
        self.assertGreaterEqual(result.get('total_missing', 0), 5)

    def test_result_structure(self):
        from localization.services.translation.AutoTranslationService import AutoTranslationService
        result = AutoTranslationService().translate_missing('at-tgt', limit=5, dry_run=True)
        required = ['success', 'language', 'total_missing', 'translated', 'failed', 'dry_run']
        for field in required:
            self.assertIn(field, result)

    def test_limit_respected(self):
        from localization.services.translation.AutoTranslationService import AutoTranslationService
        result = AutoTranslationService().translate_missing('at-tgt', limit=2, dry_run=True)
        self.assertTrue(result['success'])
        # translated count should not exceed limit
        self.assertLessEqual(result.get('translated', 0), 2)
