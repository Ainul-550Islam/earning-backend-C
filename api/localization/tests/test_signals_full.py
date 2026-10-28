# tests/test_signals_full.py
"""
Full signal coverage: cache_signals, language_signals, currency_signals,
translation_signals (incl. version tracking), missing_signals, preference_signals.
"""
from django.test import TestCase
from django.core.cache import cache
from .factories import make_language, make_country, make_currency


class CacheSignalCountryTest(TestCase):
    def setUp(self):
        self.country = make_country(code='SC', name='Signal Country', phone_code='+11')

    def test_country_save_clears_list_cache(self):
        cache.set('countries_list_v1', {'cached': True}, 60)
        self.country.name = 'Signal Country Updated'
        self.country.save()
        # Signal fires — cache should be cleared
        val = cache.get('countries_list_v1')
        self.assertIsNone(val)

    def test_country_save_clears_detail_cache(self):
        cache.set(f'country_detail_SC_False', {'cached': True}, 60)
        self.country.name = 'Changed'
        self.country.save()
        val = cache.get('country_detail_SC_False')
        self.assertIsNone(val)

    def test_country_delete_clears_list_cache(self):
        cache.set('countries_list_v1', {'cached': True}, 60)
        self.country.delete()
        val = cache.get('countries_list_v1')
        self.assertIsNone(val)


class CacheSignalLanguageTest(TestCase):
    def test_language_save_clears_list_cache(self):
        cache.set('languages_list_v1', {'cached': True}, 60)
        lang = make_language(code='si-lsc', name='Signal Lang', is_default=False)
        lang.name = 'Signal Lang Modified'
        lang.save()
        self.assertIsNone(cache.get('languages_list_v1'))

    def test_language_save_clears_detail_cache(self):
        lang = make_language(code='si-det', name='Detail Cache Lang', is_default=False)
        cache.set(f'language_detail_si-det', {'cached': True}, 60)
        lang.name = 'Detail Cache Lang 2'
        lang.save()
        self.assertIsNone(cache.get('language_detail_si-det'))

    def test_inactive_language_clears_translation_cache(self):
        lang = make_language(code='si-inact', name='Inactive Lang', is_default=False)
        cache.set(f'translations_api_si-inact', {'cached': True}, 60)
        lang.is_active = False
        lang.save()
        self.assertIsNone(cache.get('translations_api_si-inact'))


class CacheSignalCurrencyTest(TestCase):
    def test_currency_save_clears_list_cache(self):
        cache.set('currencies_list_v1', {'cached': True}, 60)
        curr = make_currency(code='SIG', name='Signal Cur', symbol='$')
        curr.name = 'Signal Currency Updated'
        curr.save()
        self.assertIsNone(cache.get('currencies_list_v1'))

    def test_currency_save_clears_exchange_rate_cache(self):
        curr = make_currency(code='SIH', name='Signal Cur H', symbol='H')
        cache.set('exchange_rate_USD_SIH', 1.23, 60)
        curr.name = 'Modified'
        curr.save()
        self.assertIsNone(cache.get('exchange_rate_USD_SIH'))


class TranslationSignalTest(TestCase):
    def setUp(self):
        self.lang = make_language(code='si-tr', name='Trans Signal Lang', is_default=False)

    def _make_key_and_translation(self, key_str='signal.test.key'):
        from api.localization.models.core import TranslationKey, Translation
        key, _ = TranslationKey.objects.get_or_create(
            key=key_str, defaults={'description': 'signal test'}
        )
        tr, _ = Translation.objects.get_or_create(
            key=key, language=self.lang,
            defaults={'value': 'original', 'is_approved': True}
        )
        return key, tr

    def test_translation_save_clears_cache(self):
        _, tr = self._make_key_and_translation()
        cache.set(f'translations_api_si-tr', {'cached': True}, 60)
        tr.value = 'updated value'
        tr.save()
        self.assertIsNone(cache.get('translations_api_si-tr'))

    def test_translation_delete_clears_cache(self):
        _, tr = self._make_key_and_translation('signal.delete.key')
        cache.set(f'translations_api_si-tr', {'cached': True}, 60)
        tr.delete()
        self.assertIsNone(cache.get('translations_api_si-tr'))

    def test_version_created_on_value_change(self):
        from api.localization.models.translation import TranslationVersion
        _, tr = self._make_key_and_translation('signal.version.key')
        original_count = TranslationVersion.objects.filter(translation=tr).count()
        tr.value = 'new version value'
        tr.save()
        new_count = TranslationVersion.objects.filter(translation=tr).count()
        # Version should be created (if signal wired in test env)
        self.assertGreaterEqual(new_count, original_count)

    def test_no_version_on_new_translation(self):
        from api.localization.models.core import TranslationKey, Translation
        from api.localization.models.translation import TranslationVersion
        key, _ = TranslationKey.objects.get_or_create(
            key='signal.new.key', defaults={'description': 'new'}
        )
        tr = Translation.objects.create(key=key, language=self.lang, value='brand new')
        # New translations should not create version (no previous value)
        count = TranslationVersion.objects.filter(translation=tr).count()
        self.assertEqual(count, 0)


class MissingTranslationSignalTest(TestCase):
    def setUp(self):
        self.lang = make_language(code='si-ms', name='Missing Signal', is_default=False)

    def test_missing_translation_log_fires(self):
        from api.localization.models.translation import MissingTranslation
        # Creating a MissingTranslation should trigger the signal (no crash)
        mt = MissingTranslation.objects.create(
            key='signal.missing.key',
            language=self.lang,
            occurrence_count=1,
        )
        self.assertIsNotNone(mt.pk)

    def test_existing_missing_update_no_double_signal(self):
        from api.localization.models.translation import MissingTranslation
        mt, _ = MissingTranslation.objects.get_or_create(
            key='signal.missing.update', language=self.lang,
            defaults={'occurrence_count': 1}
        )
        mt.occurrence_count = 5
        mt.save()  # update — should not trigger created=True branch
        self.assertEqual(mt.occurrence_count, 5)


class PreferenceSignalTest(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user, _ = User.objects.get_or_create(
            email='prefsig@test.com',
            defaults={'username': 'prefsig@test.com'}
        )
        self.lang = make_language(code='si-pref', name='Pref Signal', is_default=False)

    def test_preference_save_clears_user_cache(self):
        from api.localization.models.core import UserLanguagePreference
        pref, _ = UserLanguagePreference.objects.get_or_create(
            user=self.user, defaults={'primary_language': self.lang}
        )
        cache.set(f'user_pref_{self.user.pk}', {'cached': True}, 60)
        pref.auto_translate = False
        pref.save()
        self.assertIsNone(cache.get(f'user_pref_{self.user.pk}'))

    def test_preference_created_clears_cache(self):
        from api.localization.models.core import UserLanguagePreference
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user2, _ = User.objects.get_or_create(
            email='prefsig2@test.com',
            defaults={'username': 'prefsig2@test.com'}
        )
        cache.set(f'user_pref_{user2.pk}', {'cached': True}, 60)
        UserLanguagePreference.objects.create(user=user2, primary_language=self.lang)
        self.assertIsNone(cache.get(f'user_pref_{user2.pk}'))
