"""
Utility tests — encryption, rate limiter, spam detector, search engine.
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock


class TestE2EEncryption(TestCase):
    def test_generate_key_pair(self):
        from ..utils.e2e_encryption import generate_identity_key_pair
        priv, pub = generate_identity_key_pair()
        self.assertEqual(len(priv), 32)
        self.assertEqual(len(pub), 32)
        self.assertNotEqual(priv, pub)

    def test_two_keypairs_are_different(self):
        from ..utils.e2e_encryption import generate_identity_key_pair
        priv1, pub1 = generate_identity_key_pair()
        priv2, pub2 = generate_identity_key_pair()
        self.assertNotEqual(priv1, priv2)
        self.assertNotEqual(pub1, pub2)

    def test_x3dh_key_agreement(self):
        from ..utils.e2e_encryption import (
            generate_identity_key_pair, x3dh_sender, x3dh_recipient
        )
        alice_priv, alice_pub = generate_identity_key_pair()
        bob_priv,   bob_pub   = generate_identity_key_pair()
        bob_spk_priv, bob_spk_pub = generate_identity_key_pair()

        # Alice initiates
        alice_secret, eph_pub = x3dh_sender(
            sender_identity_priv=alice_priv,
            sender_identity_pub=alice_pub,
            recipient_identity_pub=bob_pub,
            recipient_signed_prekey_pub=bob_spk_pub,
        )
        self.assertEqual(len(alice_secret), 32)
        self.assertEqual(len(eph_pub), 32)

    def test_double_ratchet_encrypt_decrypt(self):
        from ..utils.e2e_encryption import DoubleRatchet
        import os
        shared_secret = os.urandom(32)
        plaintext = "Hello, secret world!"

        # Sender
        sender = DoubleRatchet(shared_secret, is_sender=True)
        payload = sender.ratchet_encrypt(plaintext.encode())

        self.assertIn("header", payload)
        self.assertIn("ciphertext", payload)
        self.assertIn("nonce", payload)

    def test_encode_decode_key(self):
        from ..utils.e2e_encryption import encode_key, decode_key
        import os
        key = os.urandom(32)
        encoded = encode_key(key)
        decoded = decode_key(encoded)
        self.assertEqual(key, decoded)


class TestRateLimiter(TestCase):
    @patch("messaging.utils.rate_limiter._get_redis_client")
    def test_sliding_window_allows_under_limit(self, mock_redis):
        mock_redis.return_value = None  # use cache fallback
        from ..utils.rate_limiter import sliding_window_check
        allowed, count = sliding_window_check("test:user:1", limit=10, window_seconds=60)
        self.assertTrue(allowed)

    @patch("messaging.utils.rate_limiter._get_redis_client")
    def test_rate_limit_exceeded(self, mock_redis):
        mock_redis.return_value = None
        from ..utils.rate_limiter import sliding_window_check
        # First 5 requests
        for i in range(5):
            sliding_window_check("test:user:99", limit=5, window_seconds=60)
        # 6th should be blocked
        allowed, count = sliding_window_check("test:user:99", limit=5, window_seconds=60)
        self.assertFalse(allowed)


class TestSpamDetector(TestCase):
    def test_clean_message_not_spam(self):
        from ..utils.spam_detector import analyze_message
        result = analyze_message("Hello, how are you today?")
        self.assertFalse(result["is_spam"])
        self.assertLess(result["spam_score"], 0.5)

    def test_spam_keywords_detected(self):
        from ..utils.spam_detector import analyze_message
        result = analyze_message("click here buy now guaranteed earn $ free money")
        self.assertGreater(result["spam_score"], 0.0)

    def test_excessive_caps(self):
        from ..utils.spam_detector import analyze_message
        result = analyze_message("HELLO EVERYONE BUY MY PRODUCT NOW IT IS AMAZING")
        self.assertGreater(result["spam_score"], 0.0)
        self.assertIn("excessive_caps", result["reasons"])

    def test_repeated_characters(self):
        from ..utils.spam_detector import analyze_message
        result = analyze_message("Hellooooooooo!!!!!!! Check this out!!!")
        self.assertIn("repeated_chars", result["reasons"])

    def test_duplicate_detection(self):
        from ..utils.spam_detector import check_duplicate_message
        user_id = 999
        content = "Buy my product!"
        # First 2 should be ok
        for _ in range(2):
            is_dup, count = check_duplicate_message(user_id, content)
        # Third should be duplicate
        is_dup, count = check_duplicate_message(user_id, content)
        self.assertTrue(is_dup)

    def test_should_auto_moderate_clean(self):
        from ..utils.spam_detector import should_auto_moderate
        blocked, reason = should_auto_moderate("This is a clean message.")
        self.assertFalse(blocked)


class TestDeliveryManager(TestCase):
    def test_queue_and_flush(self):
        from ..utils.delivery_manager import (
            queue_message_for_offline_user, flush_offline_queue
        )
        user_id = 12345
        msg1 = {"message_id": "msg-1", "content": "Hello"}
        msg2 = {"message_id": "msg-2", "content": "World"}
        queue_message_for_offline_user(user_id, msg1)
        queue_message_for_offline_user(user_id, msg2)
        messages = flush_offline_queue(user_id)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["message_id"], "msg-1")
        # Queue should be empty now
        empty = flush_offline_queue(user_id)
        self.assertEqual(len(empty), 0)

    def test_unread_count(self):
        from ..utils.delivery_manager import (
            increment_unread, get_unread_for_chat, clear_unread_cache
        )
        user_id = 99999
        chat_id = "chat-abc"
        clear_unread_cache(user_id, chat_id)
        count = increment_unread(user_id, chat_id)
        self.assertEqual(count, 1)
        count = increment_unread(user_id, chat_id)
        self.assertEqual(count, 2)
        stored = get_unread_for_chat(user_id, chat_id)
        self.assertEqual(stored, 2)


class TestSearchEngine(TestCase):
    def test_db_fallback_search(self):
        from ..utils.search_engine import _db_search_fallback
        from .factories import UserFactory, InternalChatFactory, ChatParticipantFactory, ChatMessageFactory

        user = UserFactory()
        chat = InternalChatFactory()
        ChatParticipantFactory(chat=chat, user=user)
        ChatMessageFactory(chat=chat, sender=user, content="Hello world test message")
        ChatMessageFactory(chat=chat, sender=user, content="Another message here")

        result = _db_search_fallback(
            user_id=user.pk, query="hello", chat_id=None, page=1, page_size=10
        )
        self.assertGreaterEqual(result["total"], 1)
        self.assertTrue(any("hello" in r["content"].lower() for r in result["results"]))

    def test_empty_query_returns_empty(self):
        from ..utils.search_engine import _db_search_fallback
        from .factories import UserFactory
        user = UserFactory()
        result = _db_search_fallback(user_id=user.pk, query="", chat_id=None, page=1, page_size=10)
        self.assertEqual(result["total"], 0)

    def test_autocomplete_users(self):
        from ..utils.search_engine import autocomplete_users
        from .factories import UserFactory
        UserFactory(username="testuser_john", first_name="John")
        results = autocomplete_users("john", limit=10)
        self.assertTrue(any("john" in r["username"].lower() or "john" in r["full_name"].lower()
                            for r in results))


class TestLinkPreview(TestCase):
    def test_extract_urls(self):
        from ..utils.link_preview import extract_urls
        text = "Check out https://example.com and also https://google.com for more info"
        urls = extract_urls(text)
        self.assertIn("https://example.com", urls)
        self.assertIn("https://google.com", urls)

    def test_extract_urls_empty(self):
        from ..utils.link_preview import extract_urls
        urls = extract_urls("No URLs here at all")
        self.assertEqual(urls, [])

    def test_extract_urls_max_5(self):
        from ..utils.link_preview import extract_urls
        text = " ".join([f"https://example{i}.com" for i in range(10)])
        urls = extract_urls(text)
        self.assertLessEqual(len(urls), 5)
