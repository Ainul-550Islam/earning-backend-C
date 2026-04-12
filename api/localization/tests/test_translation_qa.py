# tests/test_translation_qa.py
from django.test import TestCase


class TranslationQATest(TestCase):
    def setUp(self):
        from localization.services.translation.TranslationQAService import TranslationQAService
        self.service = TranslationQAService()

    def test_check_placeholders_ok(self):
        result = self.service.check_placeholders('Hello {name}', 'হ্যালো {name}')
        self.assertTrue(result['ok'])

    def test_check_placeholders_missing(self):
        result = self.service.check_placeholders('Hello {name}', 'হ্যালো')
        self.assertFalse(result['ok'])
        self.assertGreater(len(result['errors']), 0)

    def test_check_html_tags_ok(self):
        result = self.service.check_html_tags('<b>Hello</b>', '<b>হ্যালো</b>')
        self.assertTrue(result['ok'])

    def test_check_html_tags_mismatch(self):
        result = self.service.check_html_tags('<b>Hello</b>', 'হ্যালো')
        self.assertFalse(result['ok'])

    def test_check_all_passes(self):
        result = self.service.check_all('Hello world', 'হ্যালো ওয়ার্ল্ড', 'en', 'bn')
        self.assertIn('score', result)
        self.assertIn('issues', result)
        self.assertIn('warnings', result)

    def test_check_length_ratio_warning(self):
        result = self.service.check_length('Hi', 'This is an extremely long translation that is way too verbose compared to the source text', 'bn')
        self.assertIn('warning', result)
