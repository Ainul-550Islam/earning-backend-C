# api/support/tests/test_chat_queue.py  — WORLD #1
from django.test import TestCase
from api.support.services.livechat.ChatQueueService import ChatQueueService
from api.support.tests.factories import UserFactory

class ChatQueueServiceTest(TestCase):
    def test_join_queue(self):
        user   = UserFactory()
        svc    = ChatQueueService()
        result = svc.join(user)
        self.assertIn('position', result)
        self.assertGreater(result['position'], 0)

    def test_leave_queue(self):
        user   = UserFactory()
        svc    = ChatQueueService()
        svc.join(user)
        result = svc.leave(user.id)
        self.assertTrue(result)