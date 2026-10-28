# api/support/tests/test_kb_service.py  — WORLD #1
from django.test import TestCase
from api.support.services.knowledge_base.KBSearchService import KBSearchService
from api.support.tests.factories import KBArticleFactory

class KBSearchTest(TestCase):
    def setUp(self):
        self.article = KBArticleFactory(title='How to withdraw money', status='published')

    def test_search_returns_results(self):
        svc = KBSearchService()
        results = svc.search('withdraw', limit=5)
        self.assertIsInstance(results, list)

    def test_search_empty_query(self):
        svc = KBSearchService()
        results = svc.search('', limit=5)
        self.assertEqual(results, [])

    def test_search_short_query(self):
        svc = KBSearchService()
        results = svc.search('a', limit=5)
        self.assertEqual(results, [])