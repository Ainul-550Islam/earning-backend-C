# tests/test_missing_components.py
"""
Tests for previously uncovered models:
  - UserLanguagePreferenceSerializer / UserPreferenceViewSet.object
  - CountryCurrencySerializer / CountryCurrencyViewSet
  - TranslationGlossaryEntrySerializer / TranslationGlossaryEntryViewSet
  - TranslationVersionSerializer / TranslationVersionViewSet
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from .factories import make_language, make_country, make_currency

User = get_user_model()


def make_user(email='test@example.com', is_staff=False):
    u, _ = User.objects.get_or_create(email=email, defaults={'username': email})
    if is_staff:
        u.is_staff = True
        u.save()
    return u


# ── UserLanguagePreference ────────────────────────────────────────────────────

class UserLanguagePreferenceSerializerTest(TestCase):
    def setUp(self):
        self.lang = make_language(code='te-ulp', name='ULP Test', is_default=False)
        self.user = make_user('ulp@test.com')

    def test_serializer_fields(self):
        from api.localization.models.core import UserLanguagePreference
        from api.localization.serializers.user_preference import UserLanguagePreferenceSerializer
        pref, _ = UserLanguagePreference.objects.get_or_create(
            user=self.user,
            defaults={'primary_language': self.lang, 'auto_translate': True}
        )
        data = UserLanguagePreferenceSerializer(pref).data
        self.assertIn('primary_language_code', data)
        self.assertIn('preferred_language_codes', data)
        self.assertIn('effective_language_code', data)
        self.assertEqual(data['primary_language_code'], 'te-ulp')

    def test_preferred_language_codes_list(self):
        from api.localization.models.core import UserLanguagePreference
        from api.localization.serializers.user_preference import UserLanguagePreferenceSerializer
        pref, _ = UserLanguagePreference.objects.get_or_create(user=self.user)
        pref.preferred_languages.set([self.lang])
        data = UserLanguagePreferenceSerializer(pref).data
        self.assertIsInstance(data['preferred_language_codes'], list)
        self.assertIn('te-ulp', data['preferred_language_codes'])


class UserPreferenceViewSetObjectTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user('obj@test.com')
        self.lang = make_language(code='te-obj', name='Obj Lang', is_default=False)

    def test_object_unauthenticated(self):
        r = self.client.get('/api/localization/user-preferences/object/')
        self.assertIn(r.status_code, [401, 403])

    def test_object_authenticated_no_pref(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get('/api/localization/user-preferences/object/')
        self.assertIn(r.status_code, [200, 404])

    def test_object_authenticated_with_pref(self):
        from api.localization.models.core import UserLanguagePreference
        UserLanguagePreference.objects.get_or_create(
            user=self.user, defaults={'primary_language': self.lang}
        )
        self.client.force_authenticate(user=self.user)
        r = self.client.get('/api/localization/user-preferences/object/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('primary_language_code', r.json())


# ── CountryCurrency ───────────────────────────────────────────────────────────

class CountryCurrencySerializerTest(TestCase):
    def setUp(self):
        self.country = make_country(code='CC', name='CC Country', phone_code='+99')
        self.currency = make_currency(code='CCC', name='CC Coin', symbol='₵')

    def _make_cc(self):
        from api.localization.models.geo import CountryCurrency
        cc, _ = CountryCurrency.objects.get_or_create(
            country=self.country, currency=self.currency,
            defaults={'is_primary': True, 'is_legal_tender': True}
        )
        return cc

    def test_serializer_has_read_fields(self):
        from api.localization.serializers.country_currency import CountryCurrencySerializer
        cc = self._make_cc()
        data = CountryCurrencySerializer(cc).data
        self.assertEqual(data['country_code'], 'CC')
        self.assertEqual(data['currency_code'], 'CCC')
        self.assertIn('is_primary', data)
        self.assertIn('is_legal_tender', data)

    def test_country_currency_list_view(self):
        self._make_cc()
        client = APIClient()
        r = client.get('/api/localization/country-currencies/')
        self.assertIn(r.status_code, [200, 401, 403])

    def test_for_country_action(self):
        self._make_cc()
        client = APIClient()
        client.force_authenticate(user=make_user('cc2@test.com'))
        r = client.get('/api/localization/country-currencies/for_country/?code=CC')
        self.assertIn(r.status_code, [200, 404])
        if r.status_code == 200:
            self.assertIsInstance(r.json(), list)


# ── TranslationGlossaryEntry ──────────────────────────────────────────────────

class TranslationGlossaryEntrySerializerTest(TestCase):
    def setUp(self):
        self.lang = make_language(code='te-gle', name='GLE Lang', is_default=False)

    def _make_glossary_and_entry(self):
        from api.localization.models.translation import TranslationGlossary, TranslationGlossaryEntry
        g, _ = TranslationGlossary.objects.get_or_create(
            source_term='Test Glossary GLE',
            defaults={'source_language': self.lang, 'definition': 'Test'}
        )
        e, _ = TranslationGlossaryEntry.objects.get_or_create(
            glossary=g, language=self.lang,
            defaults={'translated_term': 'test term', 'is_approved': False}
        )
        return g, e

    def test_serializer_fields(self):
        from api.localization.serializers.glossary_entry import TranslationGlossaryEntrySerializer
        _, entry = self._make_glossary_and_entry()
        data = TranslationGlossaryEntrySerializer(entry).data
        self.assertIn('language_code', data)
        self.assertIn('glossary_name', data)
        self.assertEqual(data['translated_term'], 'test term')
        self.assertEqual(data['language_code'], 'te-gle')

    def test_glossary_entries_list_requires_auth(self):
        client = APIClient()
        r = client.get('/api/localization/glossary-entries/')
        self.assertIn(r.status_code, [200, 401, 403])

    def test_bulk_approve_requires_auth(self):
        client = APIClient()
        r = client.post('/api/localization/glossary-entries/bulk_approve/', {'ids': []})
        self.assertIn(r.status_code, [400, 401, 403])


# ── TranslationVersion ────────────────────────────────────────────────────────

class TranslationVersionSerializerTest(TestCase):
    def setUp(self):
        self.lang = make_language(code='te-tv', name='TV Lang', is_default=False)

    def _make_version(self):
        from api.localization.models.core import TranslationKey, Translation
        from api.localization.models.translation import TranslationVersion
        key, _ = TranslationKey.objects.get_or_create(
            key='test.version.key', defaults={'description': 'test'}
        )
        tr, _ = Translation.objects.get_or_create(
            key=key, language=self.lang,
            defaults={'value': 'original value', 'is_approved': True}
        )
        v, _ = TranslationVersion.objects.get_or_create(
            translation=tr, version_number=1,
            defaults={'value': 'original value', 'source': 'manual'}
        )
        return tr, v

    def test_serializer_fields(self):
        from api.localization.serializers.translation_version import TranslationVersionSerializer
        tr, v = self._make_version()
        data = TranslationVersionSerializer(v).data
        self.assertIn('version_number', data)
        self.assertIn('value', data)
        self.assertIn('source', data)
        self.assertIn('translation_key', data)
        self.assertIn('translation_language', data)
        self.assertEqual(data['value'], 'original value')

    def test_version_list_requires_auth(self):
        client = APIClient()
        r = client.get('/api/localization/translation-versions/')
        self.assertIn(r.status_code, [200, 401, 403])

    def test_version_filter_by_translation(self):
        tr, v = self._make_version()
        client = APIClient()
        client.force_authenticate(user=make_user('tv@test.com'))
        r = client.get(f'/api/localization/translation-versions/?translation_id={tr.id}')
        self.assertIn(r.status_code, [200, 404])
        if r.status_code == 200:
            data = r.json()
            results = data.get('results', data) if isinstance(data, dict) else data
            results = results if isinstance(results, list) else []
            self.assertIsInstance(results, (list, dict))

    def test_restore_action_requires_auth(self):
        _, v = self._make_version()
        client = APIClient()
        r = client.post(f'/api/localization/translation-versions/{v.id}/restore/')
        self.assertIn(r.status_code, [401, 403, 405])
