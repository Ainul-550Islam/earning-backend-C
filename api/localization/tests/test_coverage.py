# tests/test_coverage.py
from django.test import TestCase
from .factories import make_language, make_translation_key, make_translation


class TranslationCoverageServiceTest(TestCase):
    def setUp(self):
        self.lang_en = make_language(code='tc-en', name='Coverage EN', is_default=True)
        self.lang_bn = make_language(code='tc-bn', name='Coverage BN', is_default=False)
        for i in range(10):
            key = make_translation_key(key=f'coverage.key.{i}', category='coverage_test')
            make_translation(key=key, language=self.lang_en, value=f'EN Value {i}')
            if i < 7:
                make_translation(key=key, language=self.lang_bn, value=f'BN Value {i}')

    def test_calculate_single_language(self):
        from localization.services.translation.TranslationCoverageService import TranslationCoverageService
        report = TranslationCoverageService().get_coverage_report('tc-bn')
        self.assertIn('coverage_percent', report)
        self.assertGreater(report['total_keys'], 0)

    def test_calculate_all(self):
        from localization.services.translation.TranslationCoverageService import TranslationCoverageService
        results = TranslationCoverageService().calculate_all()
        self.assertIsInstance(results, list)
        codes = [r['language'] for r in results]
        self.assertIn('tc-bn', codes)
        self.assertIn('tc-en', codes)

    def test_coverage_in_valid_range(self):
        from localization.services.translation.TranslationCoverageService import TranslationCoverageService
        report = TranslationCoverageService().get_coverage_report('tc-bn')
        pct = float(report.get('coverage_percent', 0))
        self.assertGreaterEqual(pct, 0)
        self.assertLessEqual(pct, 100)

    def test_report_has_required_fields(self):
        from localization.services.translation.TranslationCoverageService import TranslationCoverageService
        report = TranslationCoverageService().get_coverage_report('tc-en')
        for field in ['total_keys', 'translated', 'missing', 'coverage_percent']:
            self.assertIn(field, report)

    def test_invalid_language_returns_error(self):
        from localization.services.translation.TranslationCoverageService import TranslationCoverageService
        report = TranslationCoverageService().get_coverage_report('xx-notexist')
        self.assertIn('error', report)

    def test_all_languages_report(self):
        from localization.services.translation.TranslationCoverageService import TranslationCoverageService
        report = TranslationCoverageService().get_coverage_report()
        self.assertIn('languages', report)
        self.assertIsInstance(report['languages'], list)
