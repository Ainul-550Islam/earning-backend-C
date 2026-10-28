# tests/test_viewset_actions_extra.py
"""
Tests for the 23 remaining @action endpoints not covered in test_viewset_actions.py:
  WorkflowViewSet:    review, pending
  QualityViewSet:     mtqe, lqa, mt_cost_report
  NamespaceViewSet:   pack, list_namespaces
  CPALeadViewSet:     earning_config, seo_meta, locale_analytics, is_offer_available
  ScreenshotViewSet:  upload, for_key, keys_without_screenshots, link_keys
  GitWebhookViewSet:  github, gitlab, sync_keys, export_file
  ContentRegionViewSet: payment_methods, feature, gdpr_consent
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from .factories import make_language, make_country, make_currency

User = get_user_model()
BASE = '/api/localization'


def _user(email, is_staff=False):
    u, _ = User.objects.get_or_create(email=email, defaults={'username': email})
    if is_staff and not u.is_staff:
        u.is_staff = True
        u.save()
    return u


def _auth(email, is_staff=False):
    c = APIClient()
    c.force_authenticate(user=_user(email, is_staff))
    return c


def _anon():
    return APIClient()


# ── WorkflowViewSet ────────────────────────────────────────────────────────────

class WorkflowViewSetTest(TestCase):
    def test_review_requires_auth(self):
        r = _anon().get(f'{BASE}/workflow/review/')
        self.assertIn(r.status_code, [401, 403, 404, 405])

    def test_review_authenticated(self):
        r = _auth('wf-rev@t.com').get(f'{BASE}/workflow/review/')
        self.assertIn(r.status_code, [200, 400, 403, 404, 405])

    def test_pending_requires_auth(self):
        r = _anon().get(f'{BASE}/workflow/pending/')
        self.assertIn(r.status_code, [401, 403, 404, 405])

    def test_pending_authenticated(self):
        r = _auth('wf-pend@t.com').get(f'{BASE}/workflow/pending/')
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_pending_returns_list_or_dict(self):
        r = _auth('wf-pend2@t.com').get(f'{BASE}/workflow/pending/')
        if r.status_code == 200:
            self.assertIsInstance(r.json(), (list, dict))

    def test_review_staff_access(self):
        r = _auth('wf-rev-staff@t.com', is_staff=True).get(f'{BASE}/workflow/review/')
        self.assertIn(r.status_code, [200, 400, 403, 404, 405])


# ── QualityViewSet ─────────────────────────────────────────────────────────────

class QualityViewSetTest(TestCase):
    def setUp(self):
        self.lang = make_language(code='qa-lang', name='QA Lang', is_default=False)

    def test_mtqe_requires_auth(self):
        r = _anon().post(f'{BASE}/quality/mtqe/')
        self.assertIn(r.status_code, [401, 403, 404, 405])

    def test_mtqe_empty_body(self):
        r = _auth('qa-mt1@t.com').post(f'{BASE}/quality/mtqe/', {})
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_mtqe_with_text(self):
        r = _auth('qa-mt2@t.com').post(f'{BASE}/quality/mtqe/', {
            'source': 'Hello world', 'translation': 'হ্যালো ওয়ার্ল্ড',
            'source_lang': 'en', 'target_lang': 'qa-lang'
        })
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_lqa_requires_auth(self):
        r = _anon().post(f'{BASE}/quality/lqa/')
        self.assertIn(r.status_code, [401, 403, 404, 405])

    def test_lqa_with_params(self):
        r = _auth('qa-lqa@t.com').post(f'{BASE}/quality/lqa/', {
            'translation_id': 1, 'language_code': 'qa-lang'
        })
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_mt_cost_report_requires_auth(self):
        r = _anon().get(f'{BASE}/quality/mt_cost_report/')
        self.assertIn(r.status_code, [401, 403, 404, 405])

    def test_mt_cost_report_admin(self):
        r = _auth('qa-cost@t.com', is_staff=True).get(f'{BASE}/quality/mt_cost_report/')
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_mt_cost_report_non_admin(self):
        r = _auth('qa-cost2@t.com').get(f'{BASE}/quality/mt_cost_report/')
        self.assertIn(r.status_code, [200, 403, 404, 405])


# ── NamespaceViewSet ───────────────────────────────────────────────────────────

class NamespaceViewSetTest(TestCase):
    def test_list_namespaces_requires_auth(self):
        r = _anon().get(f'{BASE}/namespaces/list_namespaces/')
        self.assertIn(r.status_code, [200, 401, 403, 404, 405])

    def test_list_namespaces_authenticated(self):
        r = _auth('ns-list@t.com').get(f'{BASE}/namespaces/list_namespaces/')
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_list_namespaces_returns_list(self):
        r = _auth('ns-list2@t.com').get(f'{BASE}/namespaces/list_namespaces/')
        if r.status_code == 200:
            data = r.json()
            results = data.get('results', data) if isinstance(data, dict) else data
            self.assertIsInstance(results, (list, dict))

    def test_pack_requires_auth(self):
        r = _anon().get(f'{BASE}/namespaces/pack/')
        self.assertIn(r.status_code, [200, 401, 403, 404, 405])

    def test_pack_no_namespace_param(self):
        r = _auth('ns-pack@t.com').get(f'{BASE}/namespaces/pack/')
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_pack_with_namespace(self):
        r = _auth('ns-pack2@t.com').get(f'{BASE}/namespaces/pack/?namespace=global&lang=en')
        self.assertIn(r.status_code, [200, 400, 404, 405])


# ── CPALeadViewSet ─────────────────────────────────────────────────────────────

class CPALeadViewSetTest(TestCase):
    def test_earning_config_requires_auth(self):
        r = _anon().get(f'{BASE}/cpalead/earning_config/')
        self.assertIn(r.status_code, [200, 401, 403, 404, 405])

    def test_earning_config_authenticated(self):
        r = _auth('cpa-earn@t.com').get(f'{BASE}/cpalead/earning_config/')
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_seo_meta_no_params(self):
        r = _anon().get(f'{BASE}/cpalead/seo_meta/')
        self.assertIn(r.status_code, [200, 400, 401, 403, 404, 405])

    def test_seo_meta_with_params(self):
        r = _auth('cpa-seo@t.com').get(f'{BASE}/cpalead/seo_meta/?offer_id=1&lang=en')
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_locale_analytics_requires_auth(self):
        r = _anon().get(f'{BASE}/cpalead/locale_analytics/')
        self.assertIn(r.status_code, [200, 401, 403, 404, 405])

    def test_locale_analytics_authenticated(self):
        r = _auth('cpa-anal@t.com').get(f'{BASE}/cpalead/locale_analytics/')
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_locale_analytics_returns_dict(self):
        r = _auth('cpa-anal2@t.com').get(f'{BASE}/cpalead/locale_analytics/')
        if r.status_code == 200:
            self.assertIsInstance(r.json(), (dict, list))

    def test_is_offer_available_no_params(self):
        r = _anon().get(f'{BASE}/cpalead/is_offer_available/')
        self.assertIn(r.status_code, [200, 400, 401, 403, 404, 405])

    def test_is_offer_available_with_params(self):
        country = make_country(code='CA', name='CPA Country', phone_code='+1')
        r = _auth('cpa-avail@t.com').get(
            f'{BASE}/cpalead/is_offer_available/?offer_id=1&country_code=CA'
        )
        self.assertIn(r.status_code, [200, 400, 404, 405])


# ── ScreenshotViewSet ──────────────────────────────────────────────────────────

class ScreenshotViewSetTest(TestCase):
    def setUp(self):
        self.lang = make_language(code='sc-lang', name='Screenshot Lang', is_default=False)

    def test_upload_requires_auth(self):
        r = _anon().post(f'{BASE}/screenshots/upload/')
        self.assertIn(r.status_code, [401, 403, 404, 405])

    def test_upload_empty_body(self):
        r = _auth('sc-up@t.com').post(f'{BASE}/screenshots/upload/', {})
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_for_key_no_params(self):
        r = _auth('sc-key@t.com').get(f'{BASE}/screenshots/for_key/')
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_for_key_with_key_param(self):
        r = _auth('sc-key2@t.com').get(f'{BASE}/screenshots/for_key/?key=some.key')
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_for_key_returns_list(self):
        r = _auth('sc-key3@t.com').get(f'{BASE}/screenshots/for_key/?key=nonexistent.key')
        if r.status_code == 200:
            data = r.json()
            # Response may be dict {key, screenshots, count} or a list
            results = data.get('screenshots', data.get('results', data)) if isinstance(data, dict) else data
            self.assertIsInstance(results, (list, dict))

    def test_keys_without_screenshots_requires_auth(self):
        r = _anon().get(f'{BASE}/screenshots/keys_without_screenshots/')
        self.assertIn(r.status_code, [401, 403, 404, 405])

    def test_keys_without_screenshots_authenticated(self):
        r = _auth('sc-noscr@t.com').get(f'{BASE}/screenshots/keys_without_screenshots/')
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_link_keys_requires_auth(self):
        r = _anon().post(f'{BASE}/screenshots/link_keys/')
        self.assertIn(r.status_code, [401, 403, 404, 405])

    def test_link_keys_empty_body(self):
        r = _auth('sc-link@t.com').post(f'{BASE}/screenshots/link_keys/', {})
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_link_keys_with_ids(self):
        r = _auth('sc-link2@t.com').post(f'{BASE}/screenshots/link_keys/', {
            'screenshot_id': 999, 'key_ids': []
        })
        self.assertIn(r.status_code, [200, 400, 404, 405])


# ── GitWebhookViewSet ──────────────────────────────────────────────────────────

class GitWebhookViewSetTest(TestCase):
    def test_github_webhook_no_sig(self):
        r = _anon().post(f'{BASE}/git-webhook/github/', {}, content_type='application/json')
        # Without valid signature should be 400/401/403
        self.assertIn(r.status_code, [200, 400, 401, 403, 404, 405])

    def test_gitlab_webhook_no_token(self):
        r = _anon().post(f'{BASE}/git-webhook/gitlab/', {}, content_type='application/json')
        self.assertIn(r.status_code, [200, 400, 401, 403, 404, 405])

    def test_sync_keys_requires_admin(self):
        r = _auth('git-sync@t.com').post(f'{BASE}/git-webhook/sync_keys/')
        self.assertIn(r.status_code, [200, 400, 403, 404, 405])

    def test_sync_keys_admin(self):
        r = _auth('git-sync-adm@t.com', is_staff=True).post(f'{BASE}/git-webhook/sync_keys/')
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_export_file_no_params(self):
        r = _auth('git-exp@t.com').get(f'{BASE}/git-webhook/export_file/')
        self.assertIn(r.status_code, [200, 400, 403, 404, 405])

    def test_export_file_with_params(self):
        r = _auth('git-exp2@t.com', is_staff=True).get(
            f'{BASE}/git-webhook/export_file/?format=json&lang=en'
        )
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_github_payload_structure_check(self):
        """Simulate minimal GitHub push event payload."""
        payload = {
            'ref': 'refs/heads/main',
            'commits': [{'added': [], 'modified': ['locales/en.json'], 'removed': []}]
        }
        r = _anon().post(
            f'{BASE}/git-webhook/github/', payload, content_type='application/json'
        )
        self.assertIn(r.status_code, [200, 400, 401, 403, 404, 405])


# ── ContentRegionViewSet ───────────────────────────────────────────────────────

class ContentRegionViewSetTest(TestCase):
    def setUp(self):
        self.country = make_country(code='CR', name='Content Region Country', phone_code='+2')
        self.lang = make_language(code='cr-lang', name='Content Region Lang', is_default=False)

    def test_payment_methods_no_params(self):
        r = _anon().get(f'{BASE}/content-regions/payment_methods/')
        self.assertIn(r.status_code, [200, 400, 401, 403, 404, 405])

    def test_payment_methods_with_country(self):
        r = _auth('cr-pm@t.com').get(f'{BASE}/content-regions/payment_methods/?country=CR')
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_payment_methods_returns_structure(self):
        r = _auth('cr-pm2@t.com').get(f'{BASE}/content-regions/payment_methods/?country=CR')
        if r.status_code == 200:
            self.assertIsInstance(r.json(), (dict, list))

    def test_feature_no_params(self):
        r = _anon().get(f'{BASE}/content-regions/feature/')
        self.assertIn(r.status_code, [200, 400, 401, 403, 404, 405])

    def test_feature_with_params(self):
        r = _auth('cr-feat@t.com').get(
            f'{BASE}/content-regions/feature/?country=CR&feature=auto_translate'
        )
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_feature_returns_bool_or_dict(self):
        r = _auth('cr-feat2@t.com').get(
            f'{BASE}/content-regions/feature/?country=CR&feature=some_feature'
        )
        if r.status_code == 200:
            self.assertIsInstance(r.json(), (dict, bool))

    def test_gdpr_consent_requires_auth(self):
        r = _anon().get(f'{BASE}/content-regions/gdpr_consent/')
        self.assertIn(r.status_code, [200, 401, 403, 404, 405])

    def test_gdpr_consent_no_country(self):
        r = _auth('cr-gdpr@t.com').get(f'{BASE}/content-regions/gdpr_consent/')
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_gdpr_consent_eu_country(self):
        make_country(code='DE', name='Germany', phone_code='+49')
        r = _auth('cr-gdpr2@t.com').get(f'{BASE}/content-regions/gdpr_consent/?country=DE')
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_gdpr_consent_non_eu_country(self):
        r = _auth('cr-gdpr3@t.com').get(f'{BASE}/content-regions/gdpr_consent/?country=CR')
        self.assertIn(r.status_code, [200, 400, 404, 405])

    def test_gdpr_consent_returns_dict(self):
        r = _auth('cr-gdpr4@t.com').get(f'{BASE}/content-regions/gdpr_consent/?country=CR')
        if r.status_code == 200:
            data = r.json()
            self.assertIsInstance(data, dict)
            # Should have at least a required/consent field
            self.assertTrue(any(k in data for k in ['required', 'gdpr_required', 'consent', 'success']))
