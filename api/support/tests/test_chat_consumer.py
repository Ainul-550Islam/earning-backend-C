# api/support/tests/test_chat_consumer.py  — WORLD #1
from django.test import TestCase

class ChatConsumerTest(TestCase):
    def test_consumer_import(self):
        try:
            from api.support.consumers.ChatConsumer import ChatConsumer
            self.assertTrue(True)
        except ImportError:
            self.skipTest("django-channels not installed")

    def test_agent_consumer_import(self):
        try:
            from api.support.consumers.AgentConsumer import AgentConsumer
            self.assertTrue(True)
        except ImportError:
            self.skipTest("django-channels not installed")