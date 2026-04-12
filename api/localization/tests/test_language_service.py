# tests/test_language_service.py
from django.test import TestCase
from .factories import make_language, make_translation_key, make_translation


class LanguageServiceTest(TestCase):
    def test_language_list(self):
        from localization.models.core import Language
        make_language(code='ls-en', name='LS English', is_default=True)
        make_language(code='ls-bn', name='LS Bengali', is_default=False)
        langs = Language.objects.filter(is_active=True, code__startswith='ls-')
        self.assertEqual(langs.count(), 2)

    def test_default_language_unique(self):
        from localization.models.core import Language
        l1 = make_language(code='ls-d1', name='Default 1', is_default=True)
        l2 = make_language(code='ls-d2', name='Default 2', is_default=False)
        l2.is_default = True
        l2.save()
        self.assertEqual(Language.objects.filter(is_default=True).count(), 1)

    def test_rtl_language(self):
        from localization.models.core import Language
        lang = make_language(code='ls-ar', name='Arabic RTL', is_default=False, is_rtl=True)
        self.assertTrue(lang.is_rtl)

    def test_language_coverage_update(self):
        lang = make_language(code='ls-cv', name='Coverage Test', is_default=False)
        key = make_translation_key(key='ls.cov.key')
        make_translation(key=key, language=lang, value='test')
        lang.update_coverage()
        lang.refresh_from_db()
        self.assertGreater(float(lang.coverage_percent), 0)

    def test_get_active_languages(self):
        from localization.models.core import Language
        make_language(code='ls-ac1', name='Active 1', is_default=False)
        make_language(code='ls-ac2', name='Active 2', is_default=False)
        active = Language.objects.filter(is_active=True, code__startswith='ls-ac')
        self.assertGreaterEqual(active.count(), 2)
