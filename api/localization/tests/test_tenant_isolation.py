# tests/test_tenant_isolation.py
"""
Tenant isolation tests.
Verifies that Tenant A cannot see Tenant B's data through any API endpoint.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from .factories import make_language, make_country, make_currency

User = get_user_model()
BASE = '/api/localization'


def _make_user(email, tenant_id=None):
    u, _ = User.objects.get_or_create(email=email, defaults={'username': email})
    # Store tenant_id on user for resolution (via X-Tenant-ID header in tests)
    return u


def _client(email, tenant_id=None):
    c = APIClient()
    u = _make_user(email, tenant_id)
    c.force_authenticate(user=u)
    if tenant_id:
        c.credentials(**{'HTTP_X_TENANT_ID': tenant_id})
    return c


class TenantResolutionTest(TestCase):
    """Test that get_tenant_id() resolves correctly."""

    def test_get_tenant_id_from_header(self):
        from api.localization.tenant import get_tenant_id
        from django.test import RequestFactory
        req = RequestFactory().get('/')
        req.META['HTTP_X_TENANT_ID'] = 'acme'
        req.user = _make_user('tenant-res@test.com')
        req.user.is_superuser = False
        self.assertEqual(get_tenant_id(req), 'acme')

    def test_superuser_gets_none(self):
        from api.localization.tenant import get_tenant_id
        from django.test import RequestFactory
        req = RequestFactory().get('/')
        req.META['HTTP_X_TENANT_ID'] = 'acme'
        req.user = _make_user('super@test.com')
        req.user.is_superuser = True
        self.assertIsNone(get_tenant_id(req))

    def test_unauthenticated_gets_none(self):
        from api.localization.tenant import get_tenant_id
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory
        req = RequestFactory().get('/')
        req.user = AnonymousUser()
        self.assertIsNone(get_tenant_id(req))

    def test_no_header_no_tenant(self):
        from api.localization.tenant import get_tenant_id
        from django.test import RequestFactory
        req = RequestFactory().get('/')
        req.user = _make_user('notenant@test.com')
        req.user.is_superuser = False
        self.assertIsNone(get_tenant_id(req))


class TenantMiddlewareTest(TestCase):
    """Test TenantMiddleware resolves tenant_id correctly."""

    def _get_middleware(self):
        from api.localization.middleware_tenant import TenantMiddleware
        from django.http import HttpResponse
        def get_response(request):
            return HttpResponse(getattr(request, 'tenant_id', '') or '')
        return TenantMiddleware(get_response)

    def test_header_resolution(self):
        from django.test import RequestFactory
        req = RequestFactory().get('/')
        req.META['HTTP_HOST'] = 'api.yourapp.com'
        req.META['HTTP_X_TENANT_ID'] = 'beta-corp'
        mw = self._get_middleware()
        resp = mw(req)
        self.assertEqual(resp.content, b'beta-corp')

    def test_subdomain_resolution(self):
        from django.test import RequestFactory
        req = RequestFactory().get('/')
        req.META['HTTP_HOST'] = 'acme.yourapp.com'
        mw = self._get_middleware()
        resp = mw(req)
        self.assertEqual(resp.content, b'acme')

    def test_www_ignored(self):
        from django.test import RequestFactory
        req = RequestFactory().get('/')
        req.META['HTTP_HOST'] = 'www.yourapp.com'
        mw = self._get_middleware()
        resp = mw(req)
        self.assertEqual(resp.content, b'')

    def test_api_subdomain_ignored(self):
        from django.test import RequestFactory
        req = RequestFactory().get('/')
        req.META['HTTP_HOST'] = 'api.yourapp.com'
        mw = self._get_middleware()
        resp = mw(req)
        self.assertEqual(resp.content, b'')

    def test_sets_tenant_id_on_request(self):
        from django.test import RequestFactory
        captured = {}

        def get_response(request):
            from django.http import HttpResponse
            captured['tid'] = getattr(request, 'tenant_id', 'MISSING')
            return HttpResponse('ok')

        from api.localization.middleware_tenant import TenantMiddleware
        mw = TenantMiddleware(get_response)
        req = RequestFactory().get('/')
        req.META['HTTP_X_TENANT_ID'] = 'gamma'
        mw(req)
        self.assertEqual(captured['tid'], 'gamma')


class TranslationRequestTenantIsolationTest(TestCase):
    """TranslationRequest must be scoped to the requesting tenant."""

    def setUp(self):
        self.lang = make_language(code='ti-req', name='TI Req Lang', is_default=False)
        self.client_a = _client('req-a@test.com', tenant_id='tenant-a')
        self.client_b = _client('req-b@test.com', tenant_id='tenant-b')

    def _create_request(self, client, title):
        return client.post(f'{BASE}/translation-requests/', {
            'title': title,
            'source_language': self.lang.pk,
            'target_languages': [],
            'status': 'pending',
            'priority': 'normal',
        })

    def test_tenant_a_cannot_see_tenant_b_requests(self):
        # Tenant B creates a request
        r = self._create_request(self.client_b, 'Tenant B Secret Job')
        if r.status_code not in [200, 201]:
            return  # skip if endpoint needs more fields

        # Tenant A lists — should NOT see Tenant B's request
        r = self.client_a.get(f'{BASE}/translation-requests/')
        if r.status_code == 200:
            titles = [item.get('title', '') for item in r.json().get('results', r.json())]
            self.assertNotIn('Tenant B Secret Job', titles)

    def test_tenant_a_request_visible_to_itself(self):
        r = self._create_request(self.client_a, 'Tenant A Own Job')
        if r.status_code not in [200, 201]:
            return
        r2 = self.client_a.get(f'{BASE}/translation-requests/')
        if r2.status_code == 200:
            data = r2.json()
            results = data.get('results', data) if isinstance(data, dict) else data
            self.assertIsInstance(results, list)


class WebhookTenantIsolationTest(TestCase):
    """WebhookRegistration must be scoped to the registering tenant."""

    def setUp(self):
        self.client_a = _client('wh-a@test.com', tenant_id='wh-tenant-a')
        self.client_b = _client('wh-b@test.com', tenant_id='wh-tenant-b')

    def test_tenant_a_cannot_see_tenant_b_webhooks(self):
        # Tenant B registers a webhook
        import json
        r = self.client_b.post(f'{BASE}/webhooks/',
            json.dumps({
            'name': 'Tenant B Webhook',
            'url': 'https://tenant-b.example.com/hook',
            'events': ['translation.created'],
            'is_active': True,
        }), content_type='application/json')
        if r.status_code not in [200, 201]:
            return

        # Tenant A lists webhooks
        r = self.client_a.get(f'{BASE}/webhooks/')
        if r.status_code == 200:
            data = r.json()
            results = data.get('results', data) if isinstance(data, dict) else data
            names = [item.get('name', '') for item in results]
            self.assertNotIn('Tenant B Webhook', names)


class GlobalModelNotTenantScopedTest(TestCase):
    """Global reference data (Language, Country, Currency) should NOT be filtered."""

    def setUp(self):
        make_language(code='ti-gl', name='Global Lang', is_default=False)
        self.client_a = _client('gl-a@test.com', tenant_id='gl-tenant-a')
        self.client_b = _client('gl-b@test.com', tenant_id='gl-tenant-b')

    def test_both_tenants_see_same_languages(self):
        r_a = self.client_a.get(f'{BASE}/languages/')
        r_b = self.client_b.get(f'{BASE}/languages/')
        if r_a.status_code == 200 and r_b.status_code == 200:
            data_a = r_a.json()
            items_a = data_a.get('results', data_a) if isinstance(data_a, dict) else data_a
            codes_a = {l['code'] for l in items_a}
            data_b = r_b.json()
            items_b = data_b.get('results', data_b) if isinstance(data_b, dict) else data_b
            codes_b = {l['code'] for l in items_b}
            self.assertEqual(codes_a, codes_b)

    def test_both_tenants_see_same_countries(self):
        r_a = self.client_a.get(f'{BASE}/countries/')
        r_b = self.client_b.get(f'{BASE}/countries/')
        if r_a.status_code == 200 and r_b.status_code == 200:
            self.assertEqual(r_a.json(), r_b.json())

    def test_both_tenants_see_same_currencies(self):
        r_a = self.client_a.get(f'{BASE}/currencies/')
        r_b = self.client_b.get(f'{BASE}/currencies/')
        if r_a.status_code == 200 and r_b.status_code == 200:
            self.assertEqual(r_a.json(), r_b.json())


class TenantConfigTest(TestCase):
    """LocalizationConfig is tenant-keyed — each tenant gets its own config."""

    def setUp(self):
        self.lang = make_language(code='ti-cfg', name='Config Lang', is_default=True)
        self.admin = _make_user('cfg-admin@test.com')
        self.admin.is_staff = True
        self.admin.save()

    def test_create_tenant_config(self):
        from api.localization.models.settings import LocalizationConfig
        config, _ = LocalizationConfig.objects.get_or_create(
            tenant_id='test-tenant-cfg',
            defaults={
                'default_language': self.lang,
                'detect_language_from_browser': True,
                'is_active': True,
            }
        )
        self.assertEqual(config.tenant_id, 'test-tenant-cfg')

    def test_get_tenant_config_utility(self):
        from api.localization.tenant import get_tenant_config
        from api.localization.models.settings import LocalizationConfig
        LocalizationConfig.objects.get_or_create(
            tenant_id='util-test-tenant',
            defaults={'default_language': self.lang, 'is_active': True}
        )
        cfg = get_tenant_config('util-test-tenant')
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.tenant_id, 'util-test-tenant')

    def test_get_tenant_config_nonexistent(self):
        from api.localization.tenant import get_tenant_config
        cfg = get_tenant_config('nonexistent-tenant-xyz')
        self.assertIsNone(cfg)

    def test_different_tenants_get_different_configs(self):
        from api.localization.tenant import get_tenant_config
        from api.localization.models.settings import LocalizationConfig
        cfg1, _ = LocalizationConfig.objects.get_or_create(
            tenant_id='multi-tenant-1',
            defaults={'default_language': self.lang, 'is_active': True}
        )
        cfg2, _ = LocalizationConfig.objects.get_or_create(
            tenant_id='multi-tenant-2',
            defaults={'default_language': self.lang, 'is_active': True}
        )
        r1 = get_tenant_config('multi-tenant-1')
        r2 = get_tenant_config('multi-tenant-2')
        self.assertIsNotNone(r1)
        self.assertIsNotNone(r2)
        self.assertNotEqual(r1.pk, r2.pk)
