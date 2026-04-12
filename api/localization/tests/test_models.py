# tests/test_models.py
"""Model tests — fix bare pass from original tests.py"""
from django.test import TestCase
from .factories import make_language, make_country, make_currency, make_translation_key, make_translation


class LanguageModelTest(TestCase):
    def test_language_create(self):
        lang = make_language(code='te-en', name='Test English')
        self.assertEqual(lang.code, 'te-en')
        self.assertIsNotNone(lang.pk)

    def test_language_str(self):
        lang = make_language(code='te-str', name='Str Test')
        self.assertIn('te-str', str(lang))

    def test_language_default_unique(self):
        """Only one language can be default"""
        lang1 = make_language(code='te-d1', name='Default 1', is_default=True)
        lang2 = make_language(code='te-d2', name='Default 2', is_default=True)
        lang2.is_default = True
        lang2.save()
        from localization.models.core import Language
        self.assertEqual(Language.objects.filter(is_default=True).count(), 1)

    def test_language_coverage_update(self):
        lang = make_language(code='te-cov', name='Coverage Test', is_default=False)
        lang.update_coverage()
        self.assertIsNotNone(lang.coverage_percent)


class CountryModelTest(TestCase):
    def test_country_create(self):
        country = make_country(code='TX', name='Test Country', phone_code='+999')
        self.assertEqual(country.code, 'TX')

    def test_country_str(self):
        country = make_country(code='TY', name='Test Y')
        self.assertIn('TY', str(country))

    def test_get_active_countries(self):
        from localization.models.core import Country
        make_country(code='TZ', name='Test Z')
        qs = Country.get_active_countries()
        self.assertGreater(qs.count(), 0)


class CurrencyModelTest(TestCase):
    def test_currency_create(self):
        curr = make_currency(code='TST', name='Test Coin', symbol='T$')
        self.assertEqual(curr.code, 'TST')

    def test_format_amount(self):
        curr = make_currency(code='TS2', name='Test2', symbol='₹')
        formatted = curr.format_amount(1234.5)
        self.assertIn('₹', formatted)

    def test_needs_exchange_update_never_updated(self):
        curr = make_currency(code='TS3', name='Test3', symbol='$')
        curr.exchange_rate_updated_at = None
        self.assertTrue(curr.needs_exchange_update)


class TranslationModelTest(TestCase):
    def test_translation_create(self):
        key = make_translation_key(key='test.create.key')
        lang = make_language(code='te-tr', name='Trans Test', is_default=False)
        trans = make_translation(key=key, language=lang, value='Test Value')
        self.assertEqual(trans.value, 'Test Value')

    def test_translation_word_count(self):
        key = make_translation_key(key='test.wc.key')
        lang = make_language(code='te-wc', name='Word Count Test', is_default=False)
        trans = make_translation(key=key, language=lang, value='Hello World Test')
        self.assertEqual(trans.word_count, 3)

    def test_missing_translation_log(self):
        from localization.models.translation import MissingTranslation
        lang = make_language(code='te-mt', name='Missing Test', is_default=False)
        MissingTranslation.log_missing('test.missing.key', lang.code)
        self.assertTrue(MissingTranslation.objects.filter(key='test.missing.key', language=lang).exists())


class TranslationMemoryTest(TestCase):
    def test_tm_add_segment(self):
        from localization.services.translation.TranslationMemoryService import TranslationMemoryService
        make_language(code='te-tm', name='TM Source', is_default=False)
        make_language(code='te-tm2', name='TM Target', is_default=False)
        service = TranslationMemoryService()
        result = service.add_segment('Hello', 'নমস্কার', 'te-tm', 'te-tm2', domain='test')
        self.assertIsNotNone(result)

    def test_tm_find_exact(self):
        from localization.models.translation import TranslationMemory
        from localization.services.translation.TranslationMemoryService import TranslationMemoryService
        make_language(code='te-src', name='Src', is_default=False)
        make_language(code='te-tgt', name='Tgt', is_default=False)
        service = TranslationMemoryService()
        service.add_segment('Find me', 'আমাকে খোঁজো', 'te-src', 'te-tgt', is_approved=True)
        match = TranslationMemory.find_exact_match('Find me', 'te-src', 'te-tgt')
        self.assertIsNotNone(match)
