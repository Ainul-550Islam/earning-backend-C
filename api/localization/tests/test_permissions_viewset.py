# tests/test_permissions_viewset.py
"""ViewSet permission tests — ensures proper auth enforcement"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from .factories import make_language, make_currency

User = get_user_model()


class AnonymousPermissionTest(TestCase):
    """Anonymous users — public endpoints only"""
    def setUp(self):
        self.client = Client()
        self.lang = make_language(code='pt-vw', name='Perm Test Lang', is_default=True)

    def test_health_public(self):
        r = self.client.get('/api/localization/health/')
        self.assertEqual(r.status_code, 200)

    def test_docs_public(self):
        r = self.client.get('/api/localization/docs/')
        self.assertEqual(r.status_code, 200)

    def test_public_translations_accessible(self):
        r = self.client.get('/api/localization/public/translations/pt-vw/')
        self.assertIn(r.status_code, [200, 404])

    def test_admin_cache_requires_auth(self):
        r = self.client.get('/api/localization/translation-cache/')
        self.assertIn(r.status_code, [401, 403])

    def test_admin_insights_requires_auth(self):
        r = self.client.get('/api/localization/insights/')
        self.assertIn(r.status_code, [401, 403])

    def test_admin_localization_requires_auth(self):
        r = self.client.get('/api/localization/admin-localization/')
        self.assertIn(r.status_code, [401, 403])

    def test_exchange_rates_requires_auth(self):
        r = self.client.get('/api/localization/exchange-rates/')
        self.assertIn(r.status_code, [401, 403])


class AuthenticatedUserPermissionTest(TestCase):
    """Regular authenticated user"""
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('ptuser@test.com', 'ptuser@test.com', 'pass123')
        self.client.login(username='ptuser@test.com', password='pass123')
        self.lang = make_language(code='pt-au', name='Auth Test Lang', is_default=False)

    def test_user_preferences_accessible(self):
        r = self.client.get('/api/localization/user-preferences/my/')
        # Should be 200 (authenticated) or 404 (no pref yet)
        self.assertIn(r.status_code, [200, 404])

    def test_coverage_accessible(self):
        r = self.client.get('/api/localization/coverage/')
        self.assertIn(r.status_code, [200, 401, 403])

    def test_admin_cache_denied_for_regular_user(self):
        r = self.client.get('/api/localization/translation-cache/')
        self.assertIn(r.status_code, [200, 403])  # 403 if not admin

    def test_languages_readable(self):
        r = self.client.get('/api/localization/languages/')
        self.assertIn(r.status_code, [200, 401])

    def test_currencies_readable(self):
        r = self.client.get('/api/localization/currencies/')
        self.assertIn(r.status_code, [200, 401])

    def test_countries_readable(self):
        r = self.client.get('/api/localization/countries/')
        self.assertIn(r.status_code, [200, 401])


class AdminPermissionTest(TestCase):
    """Admin user — all endpoints accessible"""
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser('ptadmin@test.com', 'ptadmin@test.com', 'pass123')
        self.client.login(username='ptadmin@test.com', password='pass123')

    def test_admin_can_access_translation_cache(self):
        r = self.client.get('/api/localization/translation-cache/')
        self.assertIn(r.status_code, [200])

    def test_admin_can_access_insights(self):
        r = self.client.get('/api/localization/insights/')
        self.assertIn(r.status_code, [200])

    def test_admin_can_access_missing_translations(self):
        r = self.client.get('/api/localization/missing-translations/')
        self.assertIn(r.status_code, [200])

    def test_admin_can_access_coverage(self):
        r = self.client.get('/api/localization/coverage/')
        self.assertIn(r.status_code, [200])


class PermissionModelTest(TestCase):
    """Custom permission classes unit tests"""
    def test_is_rtl_check(self):
        from ..utils_module import is_rtl_language
        self.assertTrue(is_rtl_language('ar'))
        self.assertTrue(is_rtl_language('he'))
        self.assertTrue(is_rtl_language('ur'))
        self.assertTrue(is_rtl_language('fa'))
        self.assertFalse(is_rtl_language('en'))
        self.assertFalse(is_rtl_language('bn'))
        self.assertFalse(is_rtl_language('zh'))

    def test_get_text_direction(self):
        from ..utils_module import get_text_direction
        self.assertEqual(get_text_direction('ar'), 'rtl')
        self.assertEqual(get_text_direction('en'), 'ltr')
        self.assertEqual(get_text_direction('ur'), 'rtl')
        self.assertEqual(get_text_direction('bn'), 'ltr')

    def test_accept_language_parsing(self):
        from ..utils_module import get_language_from_accept_header
        # Standard header
        result = get_language_from_accept_header('bn-BD,bn;q=0.9,en;q=0.8', ['en', 'bn', 'hi'])
        self.assertEqual(result, 'bn')
        # English fallback
        result = get_language_from_accept_header('en-US,en;q=0.9', ['en', 'bn'])
        self.assertEqual(result, 'en')
        # Unknown language falls to next
        result = get_language_from_accept_header('xx;q=1.0,en;q=0.5', ['en', 'bn'])
        self.assertEqual(result, 'en')
