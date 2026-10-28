# api/support/tests/test_kb_search.py  — WORLD #1
from django.test import TestCase
from api.support.services.knowledge_base.KBSearchService import KBSearchService
from api.support.services.knowledge_base.KBRecommendService import KBRecommendService
from api.support.tests.factories import KBArticleFactory

class KBSearchServiceTest(TestCase):
    def setUp(self):
        self.article1 = KBArticleFactory(title='How to withdraw money via bKash')
        self.article2 = KBArticleFactory(title='Payment methods accepted')

    def test_search_by_title(self):
        svc     = KBSearchService()
        results = svc.search('withdraw')
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]['title'], self.article1.title)

    def test_recommend_for_ticket(self):
        svc     = KBRecommendService()
        results = svc.suggest_for_ticket('money not credited', category='coins')
        self.assertIsInstance(results, list)