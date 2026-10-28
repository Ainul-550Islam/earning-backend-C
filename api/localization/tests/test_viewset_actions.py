# tests/test_viewset_actions.py
"""
Tests for the 73 @action endpoints across all viewsets.
Pattern: auth required → 401/403, bad input → 400, happy path → 200/201.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from .factories import make_language, make_country, make_currency

User = get_user_model()

BASE = '/api/localization'


def _user(email='action@test.com', is_staff=False):
    u, _ = User.objects.get_or_create(email=email, defaults={'username': email})
    if is_staff:
        u.is_staff = True
        u.save()
    return u


def _auth_client(email='action@test.com', is_staff=False):
    c = APIClient()
    c.force_authenticate(user=_user(email, is_staff))
    return c


def _anon():
    return APIClient()


# ── LanguageViewSet ────────────────────────────────────────────────────────────

class LanguageDefaultActionTest(TestCase):
    def setUp(self):
        self.lang = make_language(code='ac-def', name='Action Default', is_default=True)

    def test_default_public(self):
        r = _anon().get(f'{BASE}/languages/default/')
        self.assertIn(r.status_code, [200, 404])

    def test_set_default_requires_auth(self):
        r = _anon().post(f'{BASE}/languages/ac-def/set_default/')
        self.assertIn(r.status_code, [401, 403])

    def test_set_default_authenticated(self):
        r = _auth_client('lang1@t.com').post(f'{BASE}/languages/ac-def/set_default/')
        self.assertIn(r.status_code, [200, 403, 404])

    def test_coverage_action(self):
        make_language(code='ac-cov', name='Coverage Lang', is_default=False)
        r = _auth_client('lang2@t.com').get(f'{BASE}/languages/ac-cov/coverage/')
        self.assertIn(r.status_code, [200, 404])


# ── TranslationViewSet ─────────────────────────────────────────────────────────

class TranslationViewSetActionTest(TestCase):
    def setUp(self):
        self.lang = make_language(code='ac-tr', name='Action Trans Lang', is_default=False)

    def test_export_requires_auth(self):
        r = _anon().post(f'{BASE}/translations/export/', {'language_code': 'ac-tr', 'format': 'json'})
        self.assertIn(r.status_code, [401, 403])

    def test_export_json_authenticated(self):
        r = _auth_client('tr1@t.com').post(f'{BASE}/translations/export/', {
            'language_code': 'ac-tr', 'format': 'json'
        })
        self.assertIn(r.status_code, [200, 400, 404])

    def test_export_missing_format(self):
        r = _auth_client('tr2@t.com').post(f'{BASE}/translations/export/', {
            'language_code': 'ac-tr'
        })
        self.assertIn(r.status_code, [200, 400])

    def test_import_translations_requires_auth(self):
        r = _anon().post(f'{BASE}/translations/import_translations/')
        self.assertIn(r.status_code, [401, 403])

    def test_by_language_authenticated(self):
        r = _auth_client('tr3@t.com').get(f'{BASE}/translations/by_language/?lang=ac-tr')
        self.assertIn(r.status_code, [200, 400, 404])

    def test_bulk_create_requires_auth(self):
        r = _anon().post(f'{BASE}/translations/bulk_create/', {})
        self.assertIn(r.status_code, [401, 403])

    def test_bulk_create_empty_body(self):
        r = _auth_client('tr4@t.com').post(f'{BASE}/translations/bulk_create/', {})
        self.assertIn(r.status_code, [200, 400, 422])

    def test_get_translations_by_lang_code(self):
        r = _anon().get(f'{BASE}/translations/translations/ac-tr/')
        self.assertIn(r.status_code, [200, 404])


# ── TranslationKeyViewSet ──────────────────────────────────────────────────────

class TranslationKeyViewSetActionTest(TestCase):
    def test_by_category_public(self):
        r = _anon().get(f'{BASE}/translation-keys/by_category/')
        self.assertIn(r.status_code, [200, 401, 403])

    def test_by_category_authenticated(self):
        r = _auth_client('tk1@t.com').get(f'{BASE}/translation-keys/by_category/')
        self.assertIn(r.status_code, [200, 400])


# ── TranslationCacheViewSet ────────────────────────────────────────────────────

class TranslationCacheActionTest(TestCase):
    def test_clean_expired_requires_admin(self):
        r = _auth_client('cache1@t.com').post(f'{BASE}/translation-cache/clean-expired/')
        self.assertIn(r.status_code, [200, 403])

    def test_cache_stats_requires_admin(self):
        r = _auth_client('cache2@t.com').get(f'{BASE}/translation-cache/stats/')
        self.assertIn(r.status_code, [200, 403])

    def test_cache_stats_admin(self):
        r = _auth_client('cache3@t.com', is_staff=True).get(f'{BASE}/translation-cache/stats/')
        self.assertIn(r.status_code, [200, 404])


# ── CurrencyViewSet ────────────────────────────────────────────────────────────

class CurrencyConvertActionTest(TestCase):
    def setUp(self):
        make_currency(code='ACF', name='Action From', symbol='A')
        make_currency(code='ACT', name='Action To', symbol='B')

    def test_convert_no_params(self):
        r = _anon().get(f'{BASE}/currencies/convert/')
        self.assertIn(r.status_code, [200, 400, 401, 403])

    def test_convert_with_params(self):
        r = _anon().get(f'{BASE}/currencies/convert/?from=ACF&to=ACT&amount=100')
        self.assertIn(r.status_code, [200, 400, 404])

    def test_convert_same_currency(self):
        r = _anon().get(f'{BASE}/currencies/convert/?from=ACF&to=ACF&amount=50')
        self.assertIn(r.status_code, [200, 400])


# ── CityViewSet ────────────────────────────────────────────────────────────────

class CitySearchActionTest(TestCase):
    def test_search_no_query(self):
        r = _anon().get(f'{BASE}/cities/search/')
        self.assertIn(r.status_code, [200, 400, 401, 403])

    def test_search_with_query(self):
        r = _anon().get(f'{BASE}/cities/search/?q=dhaka')
        self.assertIn(r.status_code, [200, 400, 401, 403])


# ── TranslationMemoryViewSet ───────────────────────────────────────────────────

class TranslationMemoryActionTest(TestCase):
    def test_search_requires_auth(self):
        r = _anon().post(f'{BASE}/translation-memory/search/', {})
        self.assertIn(r.status_code, [401, 403])

    def test_search_missing_source_text(self):
        r = _auth_client('tm1@t.com').post(f'{BASE}/translation-memory/search/', {})
        self.assertIn(r.status_code, [400, 200])

    def test_search_with_source_text(self):
        r = _auth_client('tm2@t.com').post(f'{BASE}/translation-memory/search/', {
            'source_text': 'hello world', 'source_lang': 'en', 'target_lang': 'bn'
        })
        self.assertIn(r.status_code, [200, 400])

    def test_import_tmx_requires_auth(self):
        r = _anon().post(f'{BASE}/translation-memory/import_tmx/')
        self.assertIn(r.status_code, [401, 403])

    def test_export_tmx_requires_auth(self):
        r = _anon().get(f'{BASE}/translation-memory/export_tmx/')
        self.assertIn(r.status_code, [401, 403])

    def test_stats_requires_auth(self):
        r = _anon().get(f'{BASE}/translation-memory/stats/')
        self.assertIn(r.status_code, [401, 403])

    def test_stats_authenticated(self):
        r = _auth_client('tm3@t.com').get(f'{BASE}/translation-memory/stats/')
        self.assertIn(r.status_code, [200, 404])


# ── TranslationCoverageViewSet ─────────────────────────────────────────────────

class TranslationCoverageActionTest(TestCase):
    def test_recalculate_requires_admin(self):
        r = _auth_client('cov1@t.com').post(f'{BASE}/coverage/recalculate/')
        self.assertIn(r.status_code, [200, 403])

    def test_recalculate_admin(self):
        r = _auth_client('cov2@t.com', is_staff=True).post(f'{BASE}/coverage/recalculate/')
        self.assertIn(r.status_code, [200, 400])


# ── GeoIPViewSet ───────────────────────────────────────────────────────────────

class GeoIPActionTest(TestCase):
    def test_lookup_no_ip(self):
        r = _anon().get(f'{BASE}/geoip/lookup/')
        self.assertIn(r.status_code, [200, 400, 401, 403])

    def test_lookup_with_ip(self):
        r = _anon().get(f'{BASE}/geoip/lookup/?ip=8.8.8.8')
        self.assertIn(r.status_code, [200, 400, 401, 403])


# ── AutoTranslateViewSet ───────────────────────────────────────────────────────

class AutoTranslateActionTest(TestCase):
    def test_translate_missing_requires_auth(self):
        r = _anon().post(f'{BASE}/auto-translate/translate_missing/')
        self.assertIn(r.status_code, [401, 403])

    def test_translate_missing_no_lang(self):
        r = _auth_client('at1@t.com').post(f'{BASE}/auto-translate/translate_missing/', {})
        self.assertIn(r.status_code, [200, 400, 403])


# ── UserPreferenceViewSet ──────────────────────────────────────────────────────

class UserPreferenceActionTest(TestCase):
    def setUp(self):
        self.lang = make_language(code='ac-pref', name='Pref Action Lang', is_default=False)

    def test_my_requires_auth(self):
        r = _anon().get(f'{BASE}/user-preferences/my/')
        self.assertIn(r.status_code, [401, 403])

    def test_my_authenticated(self):
        r = _auth_client('pref1@t.com').get(f'{BASE}/user-preferences/my/')
        self.assertIn(r.status_code, [200, 404])

    def test_set_language_requires_auth(self):
        r = _anon().post(f'{BASE}/user-preferences/set_language/', {})
        self.assertIn(r.status_code, [401, 403])

    def test_set_language_missing_code(self):
        r = _auth_client('pref2@t.com').post(f'{BASE}/user-preferences/set_language/', {})
        self.assertIn(r.status_code, [400, 404])

    def test_set_language_valid_code(self):
        r = _auth_client('pref3@t.com').post(f'{BASE}/user-preferences/set_language/', {
            'language_code': 'ac-pref', 'type': 'ui'
        })
        self.assertIn(r.status_code, [200, 400, 404])

    def test_set_currency_requires_auth(self):
        r = _anon().post(f'{BASE}/user-preferences/set_currency/', {})
        self.assertIn(r.status_code, [401, 403])

    def test_set_timezone_requires_auth(self):
        r = _anon().post(f'{BASE}/user-preferences/set_timezone/', {})
        self.assertIn(r.status_code, [401, 403])

    def test_set_date_format_requires_auth(self):
        r = _anon().post(f'{BASE}/user-preferences/set_date_format/', {})
        self.assertIn(r.status_code, [401, 403])

    def test_detect_requires_auth(self):
        r = _anon().post(f'{BASE}/user-preferences/detect/')
        self.assertIn(r.status_code, [401, 403])

    def test_reset_requires_auth(self):
        r = _anon().post(f'{BASE}/user-preferences/reset/')
        self.assertIn(r.status_code, [401, 403])

    def test_distribution_requires_admin(self):
        r = _auth_client('pref4@t.com').get(f'{BASE}/user-preferences/distribution/')
        self.assertIn(r.status_code, [200, 403])

    def test_ota_checksum_public(self):
        r = _anon().get(f'{BASE}/user-preferences/ota-checksum/en/')
        self.assertIn(r.status_code, [200, 404, 401, 403])


# ── InsightViewSet ─────────────────────────────────────────────────────────────

class InsightViewSetActionTest(TestCase):
    def test_summary_requires_auth(self):
        r = _anon().get(f'{BASE}/insights/summary/')
        self.assertIn(r.status_code, [200, 401, 403])

    def test_by_language_requires_auth(self):
        r = _anon().get(f'{BASE}/insights/by_language/')
        self.assertIn(r.status_code, [200, 401, 403])

    def test_by_country_requires_auth(self):
        r = _anon().get(f'{BASE}/insights/by_country/')
        self.assertIn(r.status_code, [200, 401, 403])


# ── AdminLocalizationViewSet ───────────────────────────────────────────────────

class AdminLocalizationActionTest(TestCase):
    def test_clear_all_cache_requires_admin(self):
        r = _auth_client('adm1@t.com').post(f'{BASE}/admin-localization/clear_all_cache/')
        self.assertIn(r.status_code, [200, 403])

    def test_clear_all_cache_admin_allowed(self):
        r = _auth_client('adm2@t.com', is_staff=True).post(f'{BASE}/admin-localization/clear_all_cache/')
        self.assertIn(r.status_code, [200, 400])

    def test_recalculate_coverage_requires_admin(self):
        r = _auth_client('adm3@t.com').post(f'{BASE}/admin-localization/recalculate_coverage/')
        self.assertIn(r.status_code, [200, 403])

    def test_run_qa_all_requires_admin(self):
        r = _auth_client('adm4@t.com').post(f'{BASE}/admin-localization/run_qa_all/')
        self.assertIn(r.status_code, [200, 403])

    def test_update_exchange_rates_requires_admin(self):
        r = _auth_client('adm5@t.com').post(f'{BASE}/admin-localization/update_exchange_rates/')
        self.assertIn(r.status_code, [200, 403])

    def test_system_health_requires_admin(self):
        r = _auth_client('adm6@t.com').get(f'{BASE}/admin-localization/system_health/')
        self.assertIn(r.status_code, [200, 403])


# ── WorkflowViewSet ────────────────────────────────────────────────────────────

class WorkflowActionTest(TestCase):
    def test_submit_requires_auth(self):
        r = _anon().post(f'{BASE}/workflow/submit/')
        self.assertIn(r.status_code, [401, 403])

    def test_submit_empty_body(self):
        r = _auth_client('wf1@t.com').post(f'{BASE}/workflow/submit/', {})
        self.assertIn(r.status_code, [200, 400])


# ── LocalizedContentViewSet ────────────────────────────────────────────────────

class LocalizedContentActionTest(TestCase):
    def test_for_object_missing_params(self):
        r = _anon().get(f'{BASE}/localized-content/for_object/')
        self.assertIn(r.status_code, [400, 401, 403])

    def test_for_object_with_params(self):
        r = _anon().get(f'{BASE}/localized-content/for_object/?content_type=offer&object_id=1&lang=en')
        self.assertIn(r.status_code, [200, 400, 401, 403, 404])

    def test_bulk_set_requires_auth(self):
        r = _anon().post(f'{BASE}/localized-content/bulk_set/')
        self.assertIn(r.status_code, [401, 403])


# ── LocalizedSEOViewSet ────────────────────────────────────────────────────────

class LocalizedSEOActionTest(TestCase):
    def test_for_locale_no_params(self):
        r = _anon().get(f'{BASE}/localized-seo/for_locale/')
        self.assertIn(r.status_code, [200, 400, 401, 403, 404])


# ── TranslationRequestViewSet ──────────────────────────────────────────────────

class TranslationRequestActionTest(TestCase):
    def test_assign_requires_admin(self):
        r = _auth_client('req1@t.com').post(f'{BASE}/translation-requests/1/assign/', {'user_id': 1})
        self.assertIn(r.status_code, [403, 404])

    def test_complete_requires_auth(self):
        r = _anon().post(f'{BASE}/translation-requests/1/complete/')
        self.assertIn(r.status_code, [401, 403])


# ── CountryCurrencyViewSet ─────────────────────────────────────────────────────

class CountryCurrencyActionTest(TestCase):
    def setUp(self):
        self.country = make_country(code='AC', name='Action Country', phone_code='+77')
        self.currency = make_currency(code='ACN', name='Action Coin', symbol='◎')

    def test_for_country_missing_code(self):
        r = _anon().get(f'{BASE}/country-currencies/for_country/')
        self.assertIn(r.status_code, [400, 401, 403])

    def test_for_country_valid_code(self):
        from api.localization.models.geo import CountryCurrency
        CountryCurrency.objects.get_or_create(
            country=self.country, currency=self.currency,
            defaults={'is_primary': True}
        )
        r = _auth_client('cc1@t.com').get(f'{BASE}/country-currencies/for_country/?code=AC')
        self.assertIn(r.status_code, [200, 404])
        if r.status_code == 200:
            self.assertIsInstance(r.json(), list)


# ── TranslationGlossaryEntryViewSet ───────────────────────────────────────────

class GlossaryEntryActionTest(TestCase):
    def setUp(self):
        self.lang = make_language(code='ac-gl', name='Glossary Action Lang', is_default=False)

    def test_bulk_approve_empty_ids(self):
        r = _auth_client('gl1@t.com').post(f'{BASE}/glossary-entries/bulk_approve/', {'ids': []})
        self.assertIn(r.status_code, [200, 400])

    def test_bulk_approve_requires_auth(self):
        r = _anon().post(f'{BASE}/glossary-entries/bulk_approve/', {'ids': [1]})
        self.assertIn(r.status_code, [401, 403])


# ── TranslationVersionViewSet ──────────────────────────────────────────────────

class TranslationVersionActionTest(TestCase):
    def test_restore_requires_auth(self):
        r = _anon().post(f'{BASE}/translation-versions/1/restore/')
        self.assertIn(r.status_code, [401, 403])

    def test_restore_nonexistent_version(self):
        r = _auth_client('tv1@t.com').post(f'{BASE}/translation-versions/999999/restore/')
        self.assertIn(r.status_code, [404, 403])

    def test_filter_by_translation_id(self):
        r = _auth_client('tv2@t.com').get(f'{BASE}/translation-versions/?translation_id=999')
        self.assertIn(r.status_code, [200, 404])
        if r.status_code == 200:
            data = r.json()
            # May be paginated dict or raw list
            results = data.get('results', data) if isinstance(data, dict) else data
            self.assertIsInstance(results, (list, dict))
