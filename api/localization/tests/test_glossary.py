# tests/test_glossary.py
from django.test import TestCase
from .factories import make_language


class GlossaryServiceTest(TestCase):
    def setUp(self):
        self.src = make_language(code='gl-src', name='Glossary Source', is_default=False)
        self.tgt = make_language(code='gl-tgt', name='Glossary Target', is_default=False)

    def test_add_term(self):
        from localization.services.translation.TranslationGlossaryService import TranslationGlossaryService
        term = TranslationGlossaryService().add_term(
            'CPAlead', 'gl-src', domain='brand', is_brand_term=True, is_do_not_translate=True
        )
        self.assertIsNotNone(term)

    def test_add_term_with_translation(self):
        from localization.services.translation.TranslationGlossaryService import TranslationGlossaryService
        term = TranslationGlossaryService().add_term(
            'Earnings', 'gl-src', translations={'gl-tgt': 'আয়'}, domain='finance'
        )
        self.assertIsNotNone(term)
        from localization.models.translation import TranslationGlossaryEntry
        entry = TranslationGlossaryEntry.objects.filter(glossary=term, language__code='gl-tgt').first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.translated_term, 'আয়')

    def test_get_for_language(self):
        from localization.services.translation.TranslationGlossaryService import TranslationGlossaryService
        service = TranslationGlossaryService()
        service.add_term('GetTest', 'gl-src', translations={'gl-tgt': 'গেটটেস্ট'})
        result = service.get_for_language('gl-src', 'gl-tgt')
        self.assertIsInstance(result, list)
        terms = [r['source'] for r in result]
        self.assertIn('GetTest', terms)

    def test_dnt_term(self):
        from localization.services.translation.TranslationGlossaryService import TranslationGlossaryService
        service = TranslationGlossaryService()
        service.add_term('BrandName', 'gl-src', is_do_not_translate=True, is_brand_term=True)
        result = service.get_for_language('gl-src', 'gl-tgt')
        dnt = [r for r in result if r['source'] == 'BrandName']
        self.assertTrue(len(dnt) > 0)
        self.assertTrue(dnt[0]['do_not_translate'])

    def test_invalid_language_returns_empty(self):
        from localization.services.translation.TranslationGlossaryService import TranslationGlossaryService
        result = TranslationGlossaryService().get_for_language('xx-invalid', 'xx-other')
        self.assertIsInstance(result, list)
