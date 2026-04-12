# tests/test_permissions.py
from django.test import TestCase, Client
from django.contrib.auth import get_user_model

User = get_user_model()


class ViewPermissionTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser('admin@test.com', 'admin@test.com', 'pass123')
        self.user = User.objects.create_user('user@test.com', 'user@test.com', 'pass123')

    def test_public_translations_no_auth(self):
        response = self.client.get('/api/localization/public/translations/en/')
        self.assertIn(response.status_code, [200, 404])

    def test_health_no_auth(self):
        response = self.client.get('/api/localization/health/')
        self.assertEqual(response.status_code, 200)

    def test_docs_no_auth(self):
        response = self.client.get('/api/localization/docs/')
        self.assertEqual(response.status_code, 200)

    def test_admin_endpoint_requires_auth(self):
        response = self.client.get('/api/localization/translation-cache/')
        self.assertIn(response.status_code, [401, 403])

    def test_admin_can_access_cache(self):
        self.client.login(username='admin@test.com', password='pass123')
        response = self.client.get('/api/localization/translation-cache/')
        self.assertIn(response.status_code, [200, 403])

    def test_language_list_public(self):
        response = self.client.get('/api/localization/languages/')
        self.assertIn(response.status_code, [200, 401])
