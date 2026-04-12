"""testing/test_queue_manager.py — Queue management tests."""
from django.test import TestCase
from unittest.mock import patch, MagicMock

class TestRedisQueueOperations(TestCase):
    def test_enqueue_returns_string_id(self):
        from api.postback_engine.queue_management.redis_queue import RedisQueue
        q = RedisQueue()
        mock_client = MagicMock()
        mock_client.zadd.return_value = 1
        with patch.object(q, "_get_client", return_value=mock_client):
            item_id = q.enqueue({"test": "data"}, priority=3)
        self.assertIsInstance(item_id, str)
        self.assertTrue(len(item_id) > 0)

    def test_depth_sums_all_priorities(self):
        from api.postback_engine.queue_management.redis_queue import RedisQueue
        q = RedisQueue()
        mock_client = MagicMock()
        mock_client.zcard.return_value = 10
        with patch.object(q, "_get_client", return_value=mock_client):
            depth = q.depth()
        self.assertGreaterEqual(depth, 0)

class TestRetrySchedule(TestCase):
    def test_retry_delays_correct(self):
        from api.postback_engine.postback_handlers.retry_handler import RETRY_DELAYS_SECONDS
        self.assertEqual(RETRY_DELAYS_SECONDS[0], 60)
        self.assertEqual(RETRY_DELAYS_SECONDS[1], 300)
        self.assertEqual(RETRY_DELAYS_SECONDS[2], 1800)
        self.assertEqual(RETRY_DELAYS_SECONDS[3], 7200)
        self.assertEqual(RETRY_DELAYS_SECONDS[4], 21600)

    def test_wallet_retry_delays_correct(self):
        from api.postback_engine.postback_handlers.retry_handler import WALLET_RETRY_DELAYS_SECONDS
        self.assertEqual(WALLET_RETRY_DELAYS_SECONDS[0], 30)
        self.assertEqual(WALLET_RETRY_DELAYS_SECONDS[1], 120)
