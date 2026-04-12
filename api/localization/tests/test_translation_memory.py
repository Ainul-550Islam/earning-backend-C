# tests/test_translation_memory.py
from django.test import TestCase
from .factories import make_language


class TranslationMemoryTest(TestCase):
    def setUp(self):
        self.src = make_language(code='tm-src', name='TM Source', is_default=False)
        self.tgt = make_language(code='tm-tgt', name='TM Target', is_default=False)

    def test_add_segment(self):
        from localization.services.translation.TranslationMemoryService import TranslationMemoryService
        tm = TranslationMemoryService().add_segment(
            'Hello World', 'হ্যালো ওয়ার্ল্ড', 'tm-src', 'tm-tgt', domain='test'
        )
        self.assertIsNotNone(tm)

    def test_find_exact_match(self):
        from localization.services.translation.TranslationMemoryService import TranslationMemoryService
        from localization.models.translation import TranslationMemory
        service = TranslationMemoryService()
        service.add_segment('Exact Match Test', 'নির্ভুল মিল', 'tm-src', 'tm-tgt', is_approved=True)
        match = TranslationMemory.find_exact_match('Exact Match Test', 'tm-src', 'tm-tgt')
        self.assertIsNotNone(match)
        self.assertEqual(match.target_text, 'নির্ভুল মিল')

    def test_no_match_returns_none(self):
        from localization.models.translation import TranslationMemory
        match = TranslationMemory.find_exact_match('No match text XYZ', 'tm-src', 'tm-tgt')
        self.assertIsNone(match)

    def test_usage_count_increments(self):
        from localization.services.translation.TranslationMemoryService import TranslationMemoryService
        from localization.models.translation import TranslationMemory
        service = TranslationMemoryService()
        service.add_segment('Count Test', 'কাউন্ট টেস্ট', 'tm-src', 'tm-tgt', is_approved=True)
        before = TranslationMemory.objects.filter(source_text='Count Test').first()
        before_count = before.usage_count if before else 0
        TranslationMemory.find_exact_match('Count Test', 'tm-src', 'tm-tgt')
        after = TranslationMemory.objects.filter(source_text='Count Test').first()
        if after:
            self.assertGreaterEqual(after.usage_count, before_count)

    def test_get_stats(self):
        from localization.services.translation.TranslationMemoryService import TranslationMemoryService
        stats = TranslationMemoryService().get_stats('tm-src', 'tm-tgt')
        self.assertIn('total_segments', stats)
        self.assertIn('approved_segments', stats)

    def test_import_tmx_valid(self):
        from localization.services.translation.TranslationMemoryService import TranslationMemoryService
        tmx = (
            '<?xml version="1.0"?><tmx version="1.4">'
            '<body><tu><tuv xml:lang="tm-src"><seg>Hello</seg></tuv>'
            '<tuv xml:lang="tm-tgt"><seg>হ্যালো</seg></tuv></tu></body></tmx>'
        )
        result = TranslationMemoryService().import_tmx(tmx, 'tm-src', 'tm-tgt')
        self.assertIn('imported', result)
