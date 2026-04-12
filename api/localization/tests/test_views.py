# tests/test_views.py
from django.test import TestCase, Client
from django.urls import reverse
from .factories import make_language, make_country, make_currency


class LanguageViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.lang = make_language(code='te-vw', name='View Test', is_default=True)

    def test_health_check(self):
        response = self.client.get('/api/localization/health/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

    def test_docs_endpoint(self):
        response = self.client.get('/api/localization/docs/')
        self.assertEqual(response.status_code, 200)

    def test_public_translations(self):
        response = self.client.get('/api/localization/public/translations/te-vw/')
        self.assertIn(response.status_code, [200, 404])
