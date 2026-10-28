# api/support/tests/test_canned_responses.py  — WORLD #1
from django.test import TestCase
from api.support.services.automation.CannedResponseService import CannedResponseService
from api.support.models import CannedResponse
from api.support.tests.factories import UserFactory

class CannedResponseServiceTest(TestCase):
    def setUp(self):
        user = UserFactory()
        CannedResponse.objects.create(shortcut_key='/greeting', title='Greeting', content='Hello!', is_active=True, created_by=user)

    def test_search_by_shortcut(self):
        svc     = CannedResponseService()
        results = svc.search(shortcut='/greeting')
        self.assertGreater(len(results), 0)

    def test_use_increments_count(self):
        r   = CannedResponse.objects.get(shortcut_key='/greeting')
        svc = CannedResponseService()
        content = svc.use(r.id)
        self.assertEqual(content, 'Hello!')
        r.refresh_from_db()
        self.assertEqual(r.usage_count, 1)