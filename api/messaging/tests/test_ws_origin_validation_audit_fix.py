"""
test_ws_origin_validation_audit_fix.py
========================================
Audit finding (Part 19): routing.py's own recommended asgi.py integration
(AuthMiddlewareStack wrapping URLRouter, nothing else) was Cross-Site
WebSocket Hijacking (CSWSH) vulnerable — utils.websocket_auth.
authenticate_websocket_user()'s first strategy is session-cookie auth
(scope["user"], populated by AuthMiddlewareStack from the browser's own
cookie jar), and nothing anywhere in the module validated the Origin
header before a connection reached that auth check. CSRF middleware
never runs for the WebSocket protocol upgrade, so this was not covered
by whatever CSRF configuration exists at the project level either.

Fixed by messaging.routing.messaging_origin_validator() + the new
`application` export. These tests cover:
  1. The three-tier fallback selection logic in isolation.
  2. That an empty/unset allowlist denies all rather than allowing all.
  3. Real protocol-level connect() behaviour through the validator.
"""
from __future__ import annotations

from channels.routing import URLRouter
from channels.security.websocket import OriginValidator
from channels.testing import WebsocketCommunicator
from django.test import TestCase, override_settings

from .factories import ChatParticipantFactory, InternalChatFactory, UserFactory
from ..routing import application, messaging_origin_validator, websocket_urlpatterns

TIMEOUT = 5


class _DummyInnerApp:
    """Minimal ASGI stand-in — validator-selection tests don't need a real router."""

    async def __call__(self, scope, receive, send):  # pragma: no cover - never invoked
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Fallback-chain selection (MESSAGING_WS_ALLOWED_ORIGINS -> CORS_ALLOWED_ORIGINS
# -> ALLOWED_HOSTS)
# ─────────────────────────────────────────────────────────────────────────────

class TestMessagingOriginValidatorSelection(TestCase):

    @override_settings(MESSAGING_WS_ALLOWED_ORIGINS=["https://app.example.com"])
    def test_uses_explicit_setting_when_present(self):
        validator = messaging_origin_validator(_DummyInnerApp())
        self.assertIsInstance(validator, OriginValidator)
        self.assertEqual(validator.allowed_origins, ["https://app.example.com"])

    @override_settings(MESSAGING_WS_ALLOWED_ORIGINS=None,
                        CORS_ALLOWED_ORIGINS=["https://cors.example.com"])
    def test_falls_back_to_cors_allowed_origins(self):
        validator = messaging_origin_validator(_DummyInnerApp())
        self.assertIsInstance(validator, OriginValidator)
        self.assertEqual(validator.allowed_origins, ["https://cors.example.com"])

    @override_settings(MESSAGING_WS_ALLOWED_ORIGINS=None, CORS_ALLOWED_ORIGINS=None,
                        ALLOWED_HOSTS=["backend.example.com"])
    def test_falls_back_to_allowed_hosts(self):
        validator = messaging_origin_validator(_DummyInnerApp())
        self.assertIsInstance(validator, OriginValidator)
        self.assertEqual(validator.allowed_origins, ["backend.example.com"])

    @override_settings(MESSAGING_WS_ALLOWED_ORIGINS=["*"],
                        CORS_ALLOWED_ORIGINS=["https://cors.example.com"])
    def test_explicit_setting_takes_priority_over_cors(self):
        validator = messaging_origin_validator(_DummyInnerApp())
        self.assertEqual(validator.allowed_origins, ["*"])

    @override_settings(MESSAGING_WS_ALLOWED_ORIGINS=None, CORS_ALLOWED_ORIGINS=["https://cors.example.com"],
                        ALLOWED_HOSTS=["backend.example.com"])
    def test_cors_takes_priority_over_allowed_hosts(self):
        validator = messaging_origin_validator(_DummyInnerApp())
        self.assertEqual(validator.allowed_origins, ["https://cors.example.com"])

    @override_settings(MESSAGING_WS_ALLOWED_ORIGINS=None, CORS_ALLOWED_ORIGINS=None,
                        ALLOWED_HOSTS=[], DEBUG=False)
    def test_empty_everything_denies_all_not_allows_all(self):
        """Fail-safe rule: absence of configuration must never mean 'trust everything'."""
        validator = messaging_origin_validator(_DummyInnerApp())
        self.assertEqual(validator.allowed_origins, [])
        self.assertFalse(validator.valid_origin(None))


# ─────────────────────────────────────────────────────────────────────────────
# application export
# ─────────────────────────────────────────────────────────────────────────────

class TestApplicationExport(TestCase):

    def test_application_is_importable(self):
        self.assertIsNotNone(application)

    def test_application_is_origin_validated(self):
        self.assertIsInstance(application, OriginValidator)

    def test_websocket_urlpatterns_still_exported_unchanged(self):
        """Backward compat: anything importing the raw list directly (as the
        existing integration tests do) must keep working unmodified."""
        paths = [str(p.pattern) for p in websocket_urlpatterns]
        self.assertEqual(len(paths), 4)


# ─────────────────────────────────────────────────────────────────────────────
# Real protocol-level connect() through the validator
# ─────────────────────────────────────────────────────────────────────────────

class TestOriginValidationEndToEnd(TestCase):

    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    @override_settings(MESSAGING_WS_ALLOWED_ORIGINS=["https://trusted.example.com"])
    async def test_matching_origin_is_allowed_through(self):
        app = messaging_origin_validator(URLRouter(websocket_urlpatterns))
        communicator = WebsocketCommunicator(
            app, f"/ws/messaging/chat/{self.chat.id}/",
            headers=[(b"origin", b"https://trusted.example.com")],
        )
        communicator.scope["user"] = self.user
        connected, _ = await communicator.connect(timeout=TIMEOUT)
        self.assertTrue(connected)
        await communicator.disconnect()

    @override_settings(MESSAGING_WS_ALLOWED_ORIGINS=["https://trusted.example.com"])
    async def test_foreign_origin_is_rejected_before_reaching_consumer(self):
        """The actual CSWSH scenario: an attacker-controlled page trying to
        open a connection carrying the victim's already-authenticated scope."""
        app = messaging_origin_validator(URLRouter(websocket_urlpatterns))
        communicator = WebsocketCommunicator(
            app, f"/ws/messaging/chat/{self.chat.id}/",
            headers=[(b"origin", b"https://evil.example.com")],
        )
        communicator.scope["user"] = self.user
        connected, _ = await communicator.connect(timeout=TIMEOUT)
        self.assertFalse(connected)

    @override_settings(MESSAGING_WS_ALLOWED_ORIGINS=["https://trusted.example.com"])
    async def test_missing_origin_header_is_rejected(self):
        app = messaging_origin_validator(URLRouter(websocket_urlpatterns))
        communicator = WebsocketCommunicator(
            app, f"/ws/messaging/chat/{self.chat.id}/",
        )
        communicator.scope["user"] = self.user
        connected, _ = await communicator.connect(timeout=TIMEOUT)
        self.assertFalse(connected)

    @override_settings(MESSAGING_WS_ALLOWED_ORIGINS=["*"])
    async def test_wildcard_allows_any_origin(self):
        app = messaging_origin_validator(URLRouter(websocket_urlpatterns))
        communicator = WebsocketCommunicator(
            app, f"/ws/messaging/chat/{self.chat.id}/",
            headers=[(b"origin", b"https://anything.example.com")],
        )
        communicator.scope["user"] = self.user
        connected, _ = await communicator.connect(timeout=TIMEOUT)
        self.assertTrue(connected)
        await communicator.disconnect()
