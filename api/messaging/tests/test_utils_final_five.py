"""
test_utils_final_five.py
==========================
Tests for 5 utils modules against their ACTUAL implementations:
  spam_detector.py   — analyze_message, check_duplicate_message,
                        check_toxicity, should_auto_moderate
  translator.py      — detect_language, translate_text
  voice_processor.py — generate_waveform, get_audio_duration,
                        transcribe_audio (+ per-provider helpers)
  websocket_auth.py  — authenticate_websocket_user (+ internal helpers)
  search_engine.py   — search_messages, autocomplete_users,
                        index_message, delete_from_index, ensure_index_exists

Place in: messaging/tests/test_utils_final_five.py
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from asgiref.sync import async_to_sync

from .factories import InternalChatFactory, ChatParticipantFactory, ChatMessageFactory, UserFactory
from ..utils.spam_detector import (
    analyze_message,
    check_duplicate_message,
    check_toxicity,
    should_auto_moderate,
)
from ..utils.translator import detect_language, translate_text
from ..utils.voice_processor import (
    generate_waveform,
    get_audio_duration,
    transcribe_audio,
)
from ..utils.websocket_auth import authenticate_websocket_user
from ..exceptions import WebSocketAuthError
from ..utils.search_engine import (
    search_messages,
    autocomplete_users,
    index_message,
    delete_from_index,
    ensure_index_exists,
)


def _run(fn, *args, **kwargs):
    return async_to_sync(fn)(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# spam_detector.py
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyzeMessage(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
    def test_empty_content_is_never_spam(self):
        result = analyze_message("")
        self.assertFalse(result["is_spam"])
        self.assertEqual(result["spam_score"], 0.0)

    def test_clean_message_is_not_spam(self):
        result = analyze_message("Hey, how's your day going?")
        self.assertFalse(result["is_spam"])
        self.assertEqual(result["reasons"], [])

    def test_spam_keywords_increase_score(self):
        result = analyze_message("BUY NOW, guaranteed winner, free money!!!")
        self.assertGreater(result["spam_score"], 0)
        self.assertTrue(any("spam_keywords" in r for r in result["reasons"]))

    def test_excessive_caps_flagged(self):
        result = analyze_message("THIS IS A VERY LOUD MESSAGE WRITTEN ENTIRELY IN CAPS")
        self.assertIn("excessive_caps", result["reasons"])

    def test_repeated_chars_flagged(self):
        result = analyze_message("heyyyyyyyy there!!!!!!")
        self.assertIn("repeated_chars", result["reasons"])

    def test_excessive_links_flagged(self):
        urls = " ".join(f"https://x{i}.com" for i in range(6))
        result = analyze_message(urls)
        self.assertTrue(any("excessive_links" in r for r in result["reasons"]))

    def test_combined_signals_cross_spam_threshold(self):
        result = analyze_message("BUY NOW!!! guaranteed winner, free money, act now!!!!!!")
        self.assertTrue(result["is_spam"])
        self.assertGreaterEqual(result["spam_score"], 0.5)

    def test_duplicate_flooding_increases_score(self):
        user = UserFactory()
        for _ in range(3):
            analyze_message("same message", user_id=user.pk)
        result = analyze_message("same message", user_id=user.pk)
        self.assertTrue(any("duplicate_message" in r for r in result["reasons"]))

    def test_duplicate_reason_string_reports_accurate_send_count(self):
        """On the 3rd identical send (the one that first crosses the
        duplicate threshold), the reason string must say x3, not x2 -
        the off-by-one this fixes was directly visible here."""
        user = UserFactory()
        analyze_message("same message", user_id=user.pk)
        analyze_message("same message", user_id=user.pk)
        result = analyze_message("same message", user_id=user.pk)
        dup_reasons = [r for r in result["reasons"] if r.startswith("duplicate_message")]
        self.assertEqual(dup_reasons, ["duplicate_message:x3"])


class TestCheckDuplicateMessage(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
    def test_first_message_is_not_duplicate(self):
        user = UserFactory()
        is_dup, count = check_duplicate_message(user.pk, "hello")
        self.assertFalse(is_dup)
        self.assertEqual(count, 1)  # sent once so far

    def test_returned_count_accurately_tracks_actual_sends(self):
        """
        Regression test (Part 6 audit): check_duplicate_message computed
        new_count (and stored it in cache) but returned the stale
        pre-increment `count` instead - a dead-variable tell for an
        off-by-one. is_dup's trigger point happened to land correctly
        either way (count>=2 and new_count>=3 are equivalent given
        new_count=count+1), but the returned count under-reported by
        exactly 1, which fed directly into analyze_message's spam_score
        (min(0.5, dup_count*0.2)) and the logged/user-facing
        "duplicate_message:xN" reason string. This checks the actual
        send-by-send sequence.
        """
        user = UserFactory()
        _, c1 = check_duplicate_message(user.pk, "flood")
        _, c2 = check_duplicate_message(user.pk, "flood")
        is_dup3, c3 = check_duplicate_message(user.pk, "flood")
        self.assertEqual((c1, c2, c3), (1, 2, 3))
        self.assertTrue(is_dup3)

    def test_third_identical_message_is_duplicate(self):
        user = UserFactory()
        check_duplicate_message(user.pk, "hello")
        check_duplicate_message(user.pk, "hello")
        is_dup, count = check_duplicate_message(user.pk, "hello")
        self.assertTrue(is_dup)

    def test_case_and_whitespace_insensitive(self):
        user = UserFactory()
        check_duplicate_message(user.pk, "Hello World")
        check_duplicate_message(user.pk, "  hello world  ")
        is_dup, _ = check_duplicate_message(user.pk, "HELLO WORLD")
        self.assertTrue(is_dup)

    def test_different_users_tracked_independently(self):
        user1, user2 = UserFactory(), UserFactory()
        check_duplicate_message(user1.pk, "hello")
        check_duplicate_message(user1.pk, "hello")
        is_dup, _ = check_duplicate_message(user2.pk, "hello")
        self.assertFalse(is_dup)


class TestCheckToxicity(TestCase):
    @override_settings(PERSPECTIVE_API_KEY=None)
    def test_returns_not_toxic_when_no_api_key(self):
        result = check_toxicity("anything")
        self.assertFalse(result["is_toxic"])
        self.assertEqual(result["toxic_score"], 0.0)

    @override_settings(PERSPECTIVE_API_KEY="fake-key")
    @patch("messaging.utils.spam_detector.requests.post")
    def test_flags_high_toxicity_score(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "attributeScores": {
                "TOXICITY": {"summaryScore": {"value": 0.95}},
                "SEVERE_TOXICITY": {"summaryScore": {"value": 0.1}},
            }
        }
        mock_post.return_value = mock_resp
        result = check_toxicity("some text")
        self.assertTrue(result["is_toxic"])
        self.assertEqual(result["toxic_score"], 0.95)

    @override_settings(PERSPECTIVE_API_KEY="fake-key")
    @patch("messaging.utils.spam_detector.requests.post")
    def test_low_toxicity_score_not_flagged(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "attributeScores": {
                "TOXICITY": {"summaryScore": {"value": 0.1}},
                "SEVERE_TOXICITY": {"summaryScore": {"value": 0.05}},
            }
        }
        mock_post.return_value = mock_resp
        result = check_toxicity("some text")
        self.assertFalse(result["is_toxic"])

    @override_settings(PERSPECTIVE_API_KEY="fake-key")
    @patch("messaging.utils.spam_detector.requests.post")
    def test_returns_not_toxic_on_request_failure(self, mock_post):
        mock_post.side_effect = Exception("timeout")
        result = check_toxicity("some text")
        self.assertFalse(result["is_toxic"])


class TestShouldAutoModerate(TestCase):
    def test_empty_content_never_blocked(self):
        should_block, reason = should_auto_moderate("")
        self.assertFalse(should_block)

    def test_clean_message_not_blocked(self):
        should_block, _ = should_auto_moderate("Hi, how are you?")
        self.assertFalse(should_block)

    def test_high_spam_score_blocks(self):
        should_block, reason = should_auto_moderate(
            "BUY NOW FREE MONEY GUARANTEED WINNER ACT NOW CLICK HERE!!!!!!!"
        )
        self.assertTrue(should_block)
        self.assertTrue(reason.startswith("spam:"))

    @override_settings(PERSPECTIVE_API_KEY="fake-key")
    @patch("messaging.utils.spam_detector.requests")
    def test_high_toxicity_blocks(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "attributeScores": {
                "TOXICITY": {"summaryScore": {"value": 0.95}},
                "SEVERE_TOXICITY": {"summaryScore": {"value": 0.1}},
            }
        }
        mock_requests.post.return_value = mock_resp
        should_block, reason = should_auto_moderate("some genuinely toxic text here")
        self.assertTrue(should_block)
        self.assertTrue(reason.startswith("toxic:"))


class TestCheckDuplicateMessageCacheFailure(TestCase):
    def test_returns_false_zero_on_cache_exception(self):
        with patch("django.core.cache.cache.get", side_effect=Exception("Redis down")):
            is_dup, count = check_duplicate_message(1, "hello")
        self.assertFalse(is_dup)
        self.assertEqual(count, 0)


# ─────────────────────────────────────────────────────────────────────────────
# translator.py
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectLanguage(TestCase):
    @override_settings(GOOGLE_TRANSLATE_API_KEY=None)
    def test_returns_unknown_without_api_key(self):
        self.assertEqual(detect_language("hello"), "unknown")

    @override_settings(GOOGLE_TRANSLATE_API_KEY="fake-key")
    @patch("messaging.utils.translator.requests.post")
    def test_returns_detected_language_code(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "data": {"detections": [[{"language": "bn", "confidence": 0.99}]]}
        }
        mock_post.return_value = mock_resp
        self.assertEqual(detect_language("আমি ভালো আছি"), "bn")

    @override_settings(GOOGLE_TRANSLATE_API_KEY="fake-key")
    @patch("messaging.utils.translator.requests.post")
    def test_returns_unknown_on_request_failure(self, mock_post):
        mock_post.side_effect = Exception("timeout")
        self.assertEqual(detect_language("hello"), "unknown")


class TestTranslateText(TestCase):
    @override_settings(GOOGLE_TRANSLATE_API_KEY=None, DEEPL_API_KEY=None)
    def test_falls_back_to_stub_when_no_provider_configured(self):
        text, lang = translate_text("Hello", target_lang="bn")
        self.assertEqual(text, "[BN] Hello")

    @override_settings(GOOGLE_TRANSLATE_API_KEY="fake-key", DEEPL_API_KEY=None)
    @patch("messaging.utils.translator.requests.post")
    def test_uses_google_when_configured(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "data": {"translations": [{"translatedText": "Bonjour", "detectedSourceLanguage": "en"}]}
        }
        mock_post.return_value = mock_resp
        text, lang = translate_text("Hello", target_lang="fr")
        self.assertEqual(text, "Bonjour")
        self.assertEqual(lang, "en")

    @override_settings(GOOGLE_TRANSLATE_API_KEY="fake-key", DEEPL_API_KEY="fake-deepl")
    @patch("messaging.utils.translator.requests.post")
    def test_falls_back_to_deepl_when_google_fails(self, mock_post):
        google_fail = Exception("google down")

        def side_effect(url, **kwargs):
            if "googleapis" in url:
                raise google_fail
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {
                "translations": [{"text": "Bonjour", "detected_source_language": "EN"}]
            }
            return mock_resp

        mock_post.side_effect = side_effect
        text, lang = translate_text("Hello", target_lang="fr")
        self.assertEqual(text, "Bonjour")
        self.assertEqual(lang, "en")


# ─────────────────────────────────────────────────────────────────────────────
# voice_processor.py
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateWaveform(TestCase):
    def test_empty_audio_returns_zeroed_waveform(self):
        result = generate_waveform(b"", num_samples=10)
        self.assertEqual(result, [0.0] * 10)

    def test_falls_back_when_pydub_not_installed(self):
        # pydub isn't installed in this environment, so this exercises the
        # real ImportError fallback path, not a simulated one.
        result = generate_waveform(b"\x00\xff\x10\x80" * 20, num_samples=8)
        self.assertEqual(len(result), 8)
        self.assertTrue(all(0.0 <= v <= 1.0 for v in result))

    def test_fallback_is_deterministic(self):
        data = bytes([10, 200, 50, 100] * 10)
        r1 = generate_waveform(data, num_samples=8)
        r2 = generate_waveform(data, num_samples=8)
        self.assertEqual(r1, r2)


class TestGetAudioDuration(TestCase):
    def test_returns_zero_without_pydub(self):
        # pydub isn't installed — get_audio_duration has no fallback, it
        # just returns 0.0 on any failure to decode.
        self.assertEqual(get_audio_duration(b"not real audio"), 0.0)

    def test_returns_zero_for_empty_bytes(self):
        self.assertEqual(get_audio_duration(b""), 0.0)


class TestTranscribeAudio(TestCase):
    def test_unknown_provider_returns_error(self):
        result = transcribe_audio(b"data", provider="unknown_provider")
        self.assertEqual(result["text"], "")
        self.assertEqual(result["error"], "unknown provider")

    @override_settings(OPENAI_API_KEY=None)
    def test_whisper_without_api_key_returns_error(self):
        result = transcribe_audio(b"data", provider="whisper")
        self.assertEqual(result["provider"], "whisper")
        self.assertIn("OPENAI_API_KEY", result["error"])

    @override_settings(OPENAI_API_KEY="fake-key")
    @patch("messaging.utils.voice_processor.requests.post")
    def test_whisper_returns_transcribed_text(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"text": "hello world", "language": "en"}
        mock_post.return_value = mock_resp
        result = transcribe_audio(b"fake audio bytes", provider="whisper")
        self.assertEqual(result["text"], "hello world")
        self.assertEqual(result["provider"], "whisper")
        self.assertEqual(result["error"], "")

    @override_settings(GOOGLE_STT_API_KEY=None)
    def test_google_without_api_key_returns_error(self):
        result = transcribe_audio(b"data", provider="google")
        self.assertIn("GOOGLE_STT_API_KEY", result["error"])

    @override_settings(GOOGLE_STT_API_KEY="fake-key")
    @patch("messaging.utils.voice_processor.requests.post")
    def test_google_returns_transcribed_text(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "results": [{"alternatives": [{"transcript": "hello", "confidence": 0.9}]}]
        }
        mock_post.return_value = mock_resp
        result = transcribe_audio(b"data", provider="google")
        self.assertEqual(result["text"], "hello")
        self.assertEqual(result["confidence"], 0.9)

    @override_settings(AZURE_SPEECH_KEY=None)
    def test_azure_without_api_key_returns_error(self):
        result = transcribe_audio(b"data", provider="azure")
        self.assertIn("AZURE_SPEECH_KEY", result["error"])

    @override_settings(AZURE_SPEECH_KEY="fake-key", AZURE_SPEECH_REGION="eastus")
    @patch("messaging.utils.voice_processor.requests.post")
    def test_azure_returns_transcribed_text(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"DisplayText": "hello azure", "RecognitionStatus": "Success"}
        mock_post.return_value = mock_resp
        result = transcribe_audio(b"data", provider="azure")
        self.assertEqual(result["text"], "hello azure")
        self.assertEqual(result["error"], "")

    @override_settings(OPENAI_API_KEY="fake-key")
    @patch("messaging.utils.voice_processor.requests.post")
    def test_whisper_returns_error_on_api_failure(self, mock_post):
        mock_post.side_effect = Exception("connection refused")
        result = transcribe_audio(b"data", provider="whisper")
        self.assertEqual(result["text"], "")
        self.assertIn("connection refused", result["error"])


# ─────────────────────────────────────────────────────────────────────────────
# websocket_auth.py
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthenticateWebsocketUser(TestCase):
    def test_raises_for_non_dict_scope(self):
        with self.assertRaises(WebSocketAuthError):
            _run(authenticate_websocket_user, "not a dict")

    def test_authenticates_via_session_user_in_scope(self):
        user = UserFactory()
        scope = {"user": user, "query_string": b""}
        result = _run(authenticate_websocket_user, scope)
        self.assertEqual(result.pk, user.pk)

    def test_rejects_inactive_session_user(self):
        user = UserFactory(is_active=False)
        scope = {"user": user, "query_string": b""}
        with self.assertRaises(WebSocketAuthError):
            _run(authenticate_websocket_user, scope)

    def test_raises_when_no_user_and_no_token(self):
        scope = {"query_string": b""}
        with self.assertRaises(WebSocketAuthError):
            _run(authenticate_websocket_user, scope)

    def test_authenticates_via_valid_jwt_token(self):
        from rest_framework_simplejwt.tokens import AccessToken
        user = UserFactory()
        token = str(AccessToken.for_user(user))
        scope = {"query_string": f"token={token}".encode()}
        result = _run(authenticate_websocket_user, scope)
        self.assertEqual(result.pk, user.pk)

    def test_rejects_garbage_token(self):
        scope = {"query_string": b"token=not-a-real-token"}
        with self.assertRaises(WebSocketAuthError):
            _run(authenticate_websocket_user, scope)

    def test_authenticates_via_bearer_authorization_param(self):
        from rest_framework_simplejwt.tokens import AccessToken
        user = UserFactory()
        token = str(AccessToken.for_user(user))
        scope = {"query_string": f"authorization=Bearer {token}".encode()}
        result = _run(authenticate_websocket_user, scope)
        self.assertEqual(result.pk, user.pk)

    def test_authenticates_via_bearer_param_with_realistic_url_encoding(self):
        """
        Regression test (Part 6 audit): the test above builds its
        query_string with a literal, unencoded space - not how any real
        client (browser URLSearchParams, Python urlencode, etc.) actually
        constructs one; a real client percent- or plus-encodes the space.
        _extract_token_from_scope() never decoded query values, so this
        realistic form was never actually authenticatable before the fix.
        """
        from urllib.parse import quote_plus
        from rest_framework_simplejwt.tokens import AccessToken
        user = UserFactory()
        token = str(AccessToken.for_user(user))
        encoded = quote_plus(f"Bearer {token}")
        self.assertIn("+", encoded)  # sanity: the space really is encoded (quote_plus uses '+')
        scope = {"query_string": f"authorization={encoded}".encode()}
        result = _run(authenticate_websocket_user, scope)
        self.assertEqual(result.pk, user.pk)

    def test_authenticates_via_drf_token_fallback(self):
        from rest_framework.authtoken.models import Token
        user = UserFactory()
        tok = Token.objects.create(user=user)
        scope = {"query_string": f"token={tok.key}".encode()}
        result = _run(authenticate_websocket_user, scope)
        self.assertEqual(result.pk, user.pk)

    def test_rejects_drf_token_for_inactive_user(self):
        from rest_framework.authtoken.models import Token
        user = UserFactory(is_active=False)
        tok = Token.objects.create(user=user)
        scope = {"query_string": f"token={tok.key}".encode()}
        with self.assertRaises(WebSocketAuthError):
            _run(authenticate_websocket_user, scope)

    def test_session_user_takes_priority_over_token(self):
        from rest_framework_simplejwt.tokens import AccessToken
        session_user = UserFactory()
        other_user = UserFactory()
        token = str(AccessToken.for_user(other_user))
        scope = {"user": session_user, "query_string": f"token={token}".encode()}
        result = _run(authenticate_websocket_user, scope)
        self.assertEqual(result.pk, session_user.pk)


# ─────────────────────────────────────────────────────────────────────────────
# search_engine.py
# ─────────────────────────────────────────────────────────────────────────────

class TestSearchMessages(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_falls_back_to_db_when_es_unavailable(self):
        ChatMessageFactory(chat=self.chat, sender=self.user, content="hello world from search test")
        with patch("messaging.utils.search_engine.get_es_client", return_value=None):
            result = search_messages(user_id=self.user.pk, query="hello world")
        self.assertEqual(result["total"], 1)
        self.assertEqual(len(result["results"]), 1)

    def test_empty_query_returns_no_results(self):
        with patch("messaging.utils.search_engine.get_es_client", return_value=None):
            result = search_messages(user_id=self.user.pk, query="   ")
        self.assertEqual(result["total"], 0)

    def test_only_returns_messages_from_users_own_chats(self):
        other_chat = InternalChatFactory()
        ChatMessageFactory(chat=other_chat, sender=UserFactory(), content="hello world secret")
        ChatMessageFactory(chat=self.chat, sender=self.user, content="hello world mine")
        with patch("messaging.utils.search_engine.get_es_client", return_value=None):
            result = search_messages(user_id=self.user.pk, query="hello world")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["results"][0]["content"], "hello world mine")

    def test_es_query_failure_falls_back_to_db(self):
        ChatMessageFactory(chat=self.chat, sender=self.user, content="hello world fallback test")
        mock_es = MagicMock()
        mock_es.search.side_effect = Exception("ES cluster down")
        with patch("messaging.utils.search_engine.get_es_client", return_value=mock_es):
            result = search_messages(user_id=self.user.pk, query="hello world")
        self.assertEqual(result["total"], 1)


class TestAutocompleteUsers(TestCase):
    def test_finds_user_by_username_substring(self):
        UserFactory(username="naim_rahman")
        results = autocomplete_users("naim")
        usernames = [r["username"] for r in results]
        self.assertIn("naim_rahman", usernames)

    def test_no_match_returns_empty_list(self):
        results = autocomplete_users("zzz_no_such_user_zzz")
        self.assertEqual(results, [])

    def test_respects_limit(self):
        for i in range(5):
            UserFactory(username=f"searchlimit_{i}")
        results = autocomplete_users("searchlimit", limit=2)
        self.assertEqual(len(results), 2)

    def test_excludes_inactive_users(self):
        UserFactory(username="inactive_search_user", is_active=False)
        results = autocomplete_users("inactive_search_user")
        self.assertEqual(results, [])


class TestIndexMessage(TestCase):
    def test_returns_false_when_es_unavailable(self):
        with patch("messaging.utils.search_engine.get_es_client", return_value=None):
            result = index_message(
                message_id="m1", chat_id="c1", sender_id="u1",
                content="hi", message_type="TEXT", created_at="2026-01-01T00:00:00Z",
            )
        self.assertFalse(result)

    def test_returns_true_on_successful_index(self):
        mock_es = MagicMock()
        with patch("messaging.utils.search_engine.get_es_client", return_value=mock_es):
            result = index_message(
                message_id="m1", chat_id="c1", sender_id="u1",
                content="hi", message_type="TEXT", created_at="2026-01-01T00:00:00Z",
            )
        self.assertTrue(result)
        mock_es.index.assert_called_once()

    def test_returns_false_on_exception(self):
        mock_es = MagicMock()
        mock_es.index.side_effect = Exception("boom")
        with patch("messaging.utils.search_engine.get_es_client", return_value=mock_es):
            result = index_message(
                message_id="m1", chat_id="c1", sender_id="u1",
                content="hi", message_type="TEXT", created_at="2026-01-01T00:00:00Z",
            )
        self.assertFalse(result)


class TestDeleteFromIndex(TestCase):
    def test_returns_true_when_es_unavailable(self):
        # No ES configured — nothing to clean up, treated as trivial success.
        with patch("messaging.utils.elasticsearch_setup.get_es_client", return_value=None):
            result = delete_from_index("m1")
        self.assertTrue(result)

    def test_returns_true_on_successful_delete(self):
        mock_es = MagicMock()
        with patch("messaging.utils.elasticsearch_setup.get_es_client", return_value=mock_es):
            result = delete_from_index("m1")
        self.assertTrue(result)
        mock_es.update.assert_called_once()

    def test_returns_false_on_exception(self):
        mock_es = MagicMock()
        mock_es.update.side_effect = Exception("boom")
        with patch("messaging.utils.elasticsearch_setup.get_es_client", return_value=mock_es):
            result = delete_from_index("m1")
        self.assertFalse(result)

    def test_single_canonical_implementation_used(self):
        # Regression guard: this module previously defined delete_from_index
        # twice (the second silently shadowing the first), plus a third
        # near-identical copy in elasticsearch_setup.py. Confirm the public
        # entry point genuinely delegates rather than running its own copy.
        with patch("messaging.utils.elasticsearch_setup.delete_from_index") as mock_delete:
            mock_delete.return_value = True
            delete_from_index("m1")
        mock_delete.assert_called_once_with("m1")


class TestEnsureIndexExists(TestCase):
    def test_delegates_to_elasticsearch_setup(self):
        with patch("messaging.utils.elasticsearch_setup.ensure_index_exists") as mock_ensure:
            mock_ensure.return_value = True
            result = ensure_index_exists("custom_index")
        self.assertTrue(result)
        mock_ensure.assert_called_once_with(index="custom_index")

    def test_returns_false_on_exception(self):
        with patch(
            "messaging.utils.elasticsearch_setup.ensure_index_exists",
            side_effect=Exception("boom"),
        ):
            result = ensure_index_exists()
        self.assertFalse(result)
