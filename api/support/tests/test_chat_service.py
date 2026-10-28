# api/support/tests/test_chat_service.py  — WORLD #1
from django.test import TestCase
from api.support.services import LiveChatService, livechat_service
from api.support.tests.factories import UserFactory

class ChatServiceTest(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_start_session_creates_session(self):
        session = livechat_service.start_session(self.user)
        self.assertIsNotNone(session)
        self.assertEqual(session.user, self.user)
        self.assertIn(session.status, ('waiting','active'))

    def test_end_session(self):
        session = livechat_service.start_session(self.user)
        result  = livechat_service.end_session(str(session.session_id))
        self.assertTrue(result)
        session.refresh_from_db()
        self.assertEqual(session.status, 'ended')