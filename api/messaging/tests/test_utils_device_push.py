"""
test_utils_device_push.py
==========================
Full coverage for messaging/utils/device_push.py
Functions: _get_fcm_access_token, send_fcm, _get_apns_provider_token,
           send_apns, send_webpush, send_expo_push
Place in: messaging/tests/test_utils_device_push.py

Part 6 audit: send_fcm() was rewritten from the (dead, shut-down-since-2024)
FCM legacy HTTP API to the HTTP v1 API with a service-account JWT bearer
token, and send_apns() now caches its provider JWT instead of re-minting
one on every call. Tests below cover both rewrites plus the two new helper
functions; the WebPush/Expo sections are unchanged from prior sessions.
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock, mock_open
from django.test import TestCase, override_settings
from django.core.cache import cache
from ..utils.device_push import (
    send_fcm,
    send_apns,
    send_webpush,
    send_expo_push,
    _get_fcm_access_token,
    _get_apns_provider_token,
)

FAKE_SERVICE_ACCOUNT = (
    '{"client_email": "svc@my-project.iam.gserviceaccount.com", '
    '"private_key": "-----BEGIN PRIVATE KEY-----\\nfake\\n-----END PRIVATE KEY-----", '
    '"project_id": "my-project"}'
)


class TestGetFcmAccessToken(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @override_settings(FCM_SERVICE_ACCOUNT_FILE=None)
    def test_returns_none_when_not_configured(self):
        token, project_id = _get_fcm_access_token()
        self.assertIsNone(token)
        self.assertIsNone(project_id)

    @override_settings(FCM_SERVICE_ACCOUNT_FILE="/fake/service-account.json")
    @patch("builtins.open", mock_open(read_data=FAKE_SERVICE_ACCOUNT))
    @patch("messaging.utils.device_push._jwt")
    @patch("messaging.utils.device_push.requests")
    def test_mints_token_from_service_account(self, mock_requests, mock_jwt):
        mock_jwt.encode.return_value = "signed.jwt.assertion"
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"access_token": "ya29.fake", "expires_in": 3600}
        mock_requests.post.return_value = mock_resp

        token, project_id = _get_fcm_access_token()

        self.assertEqual(token, "ya29.fake")
        self.assertEqual(project_id, "my-project")
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        self.assertEqual(call_args[0][0], "https://oauth2.googleapis.com/token")
        self.assertEqual(call_args[1]["data"]["assertion"], "signed.jwt.assertion")
        self.assertEqual(
            call_args[1]["data"]["grant_type"],
            "urn:ietf:params:oauth:grant-type:jwt-bearer",
        )

    @override_settings(FCM_SERVICE_ACCOUNT_FILE="/fake/service-account.json")
    @patch("builtins.open", mock_open(read_data=FAKE_SERVICE_ACCOUNT))
    @patch("messaging.utils.device_push._jwt")
    @patch("messaging.utils.device_push.requests")
    def test_caches_token_across_calls(self, mock_requests, mock_jwt):
        mock_jwt.encode.return_value = "assertion"
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"access_token": "ya29.cached", "expires_in": 3600}
        mock_requests.post.return_value = mock_resp

        first = _get_fcm_access_token()
        second = _get_fcm_access_token()

        self.assertEqual(first, second)
        mock_requests.post.assert_called_once()  # 2nd call served from cache

    @override_settings(FCM_SERVICE_ACCOUNT_FILE="/fake/service-account.json")
    @patch("builtins.open", side_effect=FileNotFoundError("no such file"))
    def test_returns_none_on_missing_file(self, _mock_open):
        token, project_id = _get_fcm_access_token()
        self.assertIsNone(token)
        self.assertIsNone(project_id)

    @override_settings(FCM_SERVICE_ACCOUNT_FILE="/fake/service-account.json")
    @patch("builtins.open", mock_open(read_data=FAKE_SERVICE_ACCOUNT))
    @patch("messaging.utils.device_push.requests")
    def test_returns_none_when_token_endpoint_fails(self, mock_requests):
        mock_requests.post.side_effect = Exception("network error")
        token, project_id = _get_fcm_access_token()
        self.assertIsNone(token)
        self.assertIsNone(project_id)


class TestSendFcm(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @override_settings(FCM_SERVICE_ACCOUNT_FILE=None)
    def test_returns_false_when_not_configured(self):
        result = send_fcm(token="device_token", title="Hello", body="World", data={})
        self.assertFalse(result)

    @override_settings(FCM_SERVICE_ACCOUNT_FILE="/fake/service-account.json")
    @patch("builtins.open", mock_open(read_data=FAKE_SERVICE_ACCOUNT))
    @patch("messaging.utils.device_push._jwt")
    @patch("messaging.utils.device_push.requests")
    def test_returns_true_on_success(self, mock_requests, mock_jwt):
        mock_jwt.encode.return_value = "assertion"
        token_resp = MagicMock()
        token_resp.raise_for_status = MagicMock()
        token_resp.json.return_value = {"access_token": "ya29.fake"}
        send_resp = MagicMock()
        send_resp.status_code = 200
        mock_requests.post.side_effect = [token_resp, send_resp]

        result = send_fcm(
            token="ExponentPushToken[xxx]", title="New message",
            body="Hello there", data={"chat_id": "c1"},
        )
        self.assertTrue(result)

    @override_settings(FCM_SERVICE_ACCOUNT_FILE="/fake/service-account.json")
    @patch("builtins.open", mock_open(read_data=FAKE_SERVICE_ACCOUNT))
    @patch("messaging.utils.device_push._jwt")
    @patch("messaging.utils.device_push.requests")
    def test_returns_false_on_non_200(self, mock_requests, mock_jwt):
        mock_jwt.encode.return_value = "assertion"
        token_resp = MagicMock()
        token_resp.raise_for_status = MagicMock()
        token_resp.json.return_value = {"access_token": "ya29.fake"}
        send_resp = MagicMock()
        send_resp.status_code = 404
        send_resp.text = "UNREGISTERED"
        mock_requests.post.side_effect = [token_resp, send_resp]

        result = send_fcm(token="bad-token", title="T", body="B", data={})
        self.assertFalse(result)

    @override_settings(FCM_SERVICE_ACCOUNT_FILE="/fake/service-account.json")
    @patch("builtins.open", mock_open(read_data=FAKE_SERVICE_ACCOUNT))
    @patch("messaging.utils.device_push._jwt")
    @patch("messaging.utils.device_push.requests")
    def test_returns_false_on_exception(self, mock_requests, mock_jwt):
        mock_jwt.encode.return_value = "assertion"
        token_resp = MagicMock()
        token_resp.raise_for_status = MagicMock()
        token_resp.json.return_value = {"access_token": "ya29.fake"}
        mock_requests.post.side_effect = [token_resp, Exception("Network error")]

        result = send_fcm(token="t", title="T", body="B", data={})
        self.assertFalse(result)

    @override_settings(FCM_SERVICE_ACCOUNT_FILE="/fake/service-account.json")
    @patch("builtins.open", mock_open(read_data=FAKE_SERVICE_ACCOUNT))
    @patch("messaging.utils.device_push._jwt")
    @patch("messaging.utils.device_push.requests")
    def test_high_priority_sets_android_high(self, mock_requests, mock_jwt):
        mock_jwt.encode.return_value = "assertion"
        token_resp = MagicMock()
        token_resp.raise_for_status = MagicMock()
        token_resp.json.return_value = {"access_token": "ya29.fake"}
        send_resp = MagicMock()
        send_resp.status_code = 200
        mock_requests.post.side_effect = [token_resp, send_resp]

        send_fcm(token="t", title="T", body="B", data={}, priority="high")
        payload = mock_requests.post.call_args_list[1][1]["json"]
        self.assertEqual(payload["message"]["android"]["priority"], "high")

    @override_settings(FCM_SERVICE_ACCOUNT_FILE="/fake/service-account.json")
    @patch("builtins.open", mock_open(read_data=FAKE_SERVICE_ACCOUNT))
    @patch("messaging.utils.device_push._jwt")
    @patch("messaging.utils.device_push.requests")
    def test_payload_contains_notification_and_data(self, mock_requests, mock_jwt):
        mock_jwt.encode.return_value = "assertion"
        token_resp = MagicMock()
        token_resp.raise_for_status = MagicMock()
        token_resp.json.return_value = {"access_token": "ya29.fake"}
        send_resp = MagicMock()
        send_resp.status_code = 200
        mock_requests.post.side_effect = [token_resp, send_resp]

        send_fcm(token="t", title="Test Title", body="Test Body", data={"k": "v"})
        payload = mock_requests.post.call_args_list[1][1]["json"]
        self.assertEqual(payload["message"]["notification"]["title"], "Test Title")
        self.assertEqual(payload["message"]["notification"]["body"], "Test Body")
        self.assertEqual(payload["message"]["data"]["k"], "v")
        self.assertEqual(payload["message"]["token"], "t")

    @override_settings(FCM_SERVICE_ACCOUNT_FILE="/fake/service-account.json")
    @patch("builtins.open", mock_open(read_data=FAKE_SERVICE_ACCOUNT))
    @patch("messaging.utils.device_push._jwt")
    @patch("messaging.utils.device_push.requests")
    def test_uses_v1_endpoint_with_project_id_and_bearer_auth(self, mock_requests, mock_jwt):
        mock_jwt.encode.return_value = "assertion"
        token_resp = MagicMock()
        token_resp.raise_for_status = MagicMock()
        token_resp.json.return_value = {"access_token": "ya29.fake"}
        send_resp = MagicMock()
        send_resp.status_code = 200
        mock_requests.post.side_effect = [token_resp, send_resp]

        send_fcm(token="t", title="T", body="B", data={})
        send_url = mock_requests.post.call_args_list[1][0][0]
        self.assertEqual(
            send_url, "https://fcm.googleapis.com/v1/projects/my-project/messages:send"
        )
        headers = mock_requests.post.call_args_list[1][1]["headers"]
        self.assertEqual(headers["Authorization"], "Bearer ya29.fake")

    @override_settings(FCM_SERVICE_ACCOUNT_FILE="/fake/service-account.json")
    @patch("builtins.open", mock_open(read_data=FAKE_SERVICE_ACCOUNT))
    @patch("messaging.utils.device_push._jwt")
    @patch("messaging.utils.device_push.requests")
    def test_data_values_stringified_for_fcm(self, mock_requests, mock_jwt):
        """FCM v1 requires all `data` map values to be strings."""
        mock_jwt.encode.return_value = "assertion"
        token_resp = MagicMock()
        token_resp.raise_for_status = MagicMock()
        token_resp.json.return_value = {"access_token": "ya29.fake"}
        send_resp = MagicMock()
        send_resp.status_code = 200
        mock_requests.post.side_effect = [token_resp, send_resp]

        send_fcm(token="t", title="T", body="B", data={"count": 3, "flag": True})
        payload = mock_requests.post.call_args_list[1][1]["json"]
        self.assertEqual(payload["message"]["data"]["count"], "3")
        self.assertEqual(payload["message"]["data"]["flag"], "True")


class TestSendApns(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @override_settings(APNS_CERT_FILE=None, APNS_KEY_ID=None, APNS_TEAM_ID=None, APNS_BUNDLE_ID=None)
    def test_returns_false_when_not_configured(self):
        result = send_apns(token="device-token", title="Hi", body="msg", data={})
        self.assertFalse(result)

    @override_settings(
        APNS_CERT_FILE="/fake/key.p8",
        APNS_KEY_ID="KEYID12345",
        APNS_TEAM_ID="TEAMID123",
        APNS_BUNDLE_ID="com.example.app",
    )
    @patch("builtins.open", mock_open(read_data="-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----"))
    @patch("messaging.utils.device_push.requests")
    @patch("messaging.utils.device_push._jwt")
    def test_returns_true_on_200_response(self, mock_jwt, mock_requests):
        mock_jwt.encode.return_value = "fake.jwt.token"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests.post.return_value = mock_resp
        result = send_apns(token="ios-device-token", title="Alert", body="Message", data={})
        self.assertTrue(result)

    @override_settings(
        APNS_CERT_FILE="/fake/key.p8",
        APNS_KEY_ID="KEYID12345",
        APNS_TEAM_ID="TEAMID123",
        APNS_BUNDLE_ID="com.example.app",
    )
    @patch("builtins.open", mock_open(read_data="fake key"))
    @patch("messaging.utils.device_push.requests")
    @patch("messaging.utils.device_push._jwt")
    def test_returns_false_on_non_200(self, mock_jwt, mock_requests):
        mock_jwt.encode.return_value = "token"
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_requests.post.return_value = mock_resp
        result = send_apns(token="bad-token", title="T", body="B", data={})
        self.assertFalse(result)

    @override_settings(
        APNS_CERT_FILE="/fake/key.p8",
        APNS_KEY_ID="K",
        APNS_TEAM_ID="T",
        APNS_BUNDLE_ID="com.app",
    )
    @patch("builtins.open", side_effect=FileNotFoundError("key not found"))
    def test_returns_false_on_file_not_found(self, _mock_open):
        result = send_apns(token="t", title="T", body="B", data={})
        self.assertFalse(result)

    @override_settings(
        APNS_CERT_FILE="/k.p8", APNS_KEY_ID="K", APNS_TEAM_ID="T", APNS_BUNDLE_ID="com.app"
    )
    @patch("builtins.open", mock_open(read_data="key"))
    @patch("messaging.utils.device_push.requests")
    @patch("messaging.utils.device_push._jwt")
    def test_voip_push_type_passed(self, mock_jwt, mock_requests):
        mock_jwt.encode.return_value = "tok"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests.post.return_value = mock_resp
        result = send_apns(token="t", title="T", body="B", data={}, push_type="voip")
        call_headers = mock_requests.post.call_args[1]["headers"]
        self.assertEqual(call_headers["apns-push-type"], "voip")

    @override_settings(
        APNS_CERT_FILE="/k.p8", APNS_KEY_ID="K9", APNS_TEAM_ID="T9", APNS_BUNDLE_ID="com.app"
    )
    @patch("builtins.open", mock_open(read_data="key"))
    @patch("messaging.utils.device_push.requests")
    @patch("messaging.utils.device_push._jwt")
    def test_provider_token_reused_across_sends(self, mock_jwt, mock_requests):
        """
        Regression test (Part 6 audit): previously a fresh ES256 JWT was
        signed - and the key file re-read from disk - on every single call,
        which Apple's docs warn against (TooManyProviderTokenUpdates risk).
        """
        mock_jwt.encode.return_value = "fake.jwt.token"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests.post.return_value = mock_resp

        send_apns(token="dev-1", title="A", body="B", data={})
        send_apns(token="dev-2", title="A", body="B", data={})

        mock_jwt.encode.assert_called_once()
        self.assertEqual(mock_requests.post.call_count, 2)  # both pushes still sent


class TestGetApnsProviderToken(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch("builtins.open", mock_open(read_data="fake-key"))
    @patch("messaging.utils.device_push._jwt")
    def test_mints_and_caches_token(self, mock_jwt):
        mock_jwt.encode.return_value = "token-1"
        first = _get_apns_provider_token(key_file="/k.p8", key_id="K1", team_id="T1")
        self.assertEqual(first, "token-1")

        mock_jwt.encode.return_value = "token-2"
        second = _get_apns_provider_token(key_file="/k.p8", key_id="K1", team_id="T1")
        self.assertEqual(second, "token-1")  # still cached, not regenerated

    @patch("builtins.open", mock_open(read_data="fake-key"))
    @patch("messaging.utils.device_push._jwt")
    def test_different_key_id_not_cross_cached(self, mock_jwt):
        mock_jwt.encode.return_value = "token-a"
        _get_apns_provider_token(key_file="/k.p8", key_id="K1", team_id="T1")

        mock_jwt.encode.return_value = "token-b"
        second = _get_apns_provider_token(key_file="/k.p8", key_id="K2", team_id="T1")
        self.assertEqual(second, "token-b")


class TestSendWebpush(TestCase):
    @override_settings(VAPID_PRIVATE_KEY=None, VAPID_PUBLIC_KEY=None, VAPID_CLAIM_EMAIL=None)
    def test_returns_false_when_not_configured(self):
        result = send_webpush(
            subscription_info='{"endpoint": "https://..."}',
            title="Hi",
            body="Msg",
            data={},
        )
        self.assertFalse(result)

    @override_settings(
        VAPID_PRIVATE_KEY="fake_private_key",
        VAPID_PUBLIC_KEY="fake_public_key",
        VAPID_CLAIM_EMAIL="admin@example.com",
    )
    @patch("messaging.utils.device_push.webpush")
    def test_returns_true_on_success(self, mock_webpush):
        import sys
        sys.modules.setdefault("pywebpush", MagicMock())
        mock_webpush.return_value = None
        result = send_webpush(
            subscription_info='{"endpoint": "https://push.example.com", "keys": {"auth": "a", "p256dh": "b"}}',
            title="Notification",
            body="You have a new message",
            data={"chat_id": "c1"},
        )
        self.assertTrue(result)

    @override_settings(
        VAPID_PRIVATE_KEY="k", VAPID_PUBLIC_KEY="k", VAPID_CLAIM_EMAIL="e@e.com"
    )
    @patch("messaging.utils.device_push.webpush")
    def test_returns_false_on_exception(self, mock_webpush):
        mock_webpush.side_effect = Exception("WebPushException: 410 Gone")
        result = send_webpush(
            subscription_info='{"endpoint": "https://expired.com"}',
            title="T", body="B", data={},
        )
        self.assertFalse(result)

    @override_settings(
        VAPID_PRIVATE_KEY="k", VAPID_PUBLIC_KEY="k", VAPID_CLAIM_EMAIL="e@e.com"
    )
    def test_returns_false_on_invalid_json(self):
        result = send_webpush(
            subscription_info="not-valid-json",
            title="T", body="B", data={},
        )
        self.assertFalse(result)


class TestSendExpoPush(TestCase):
    @patch("messaging.utils.device_push.requests")
    def test_returns_true_on_success(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": {"status": "ok"}}
        mock_requests.post.return_value = mock_resp
        result = send_expo_push(
            token="ExponentPushToken[xxx]",
            title="New message",
            body="Hello!",
            data={"chat_id": "c1"},
        )
        self.assertTrue(result)

    @patch("messaging.utils.device_push.requests")
    def test_returns_false_when_expo_reports_error(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {"status": "error", "message": "DeviceNotRegistered"}
        }
        mock_requests.post.return_value = mock_resp
        result = send_expo_push(token="bad-token", title="T", body="B", data={})
        self.assertFalse(result)

    @patch("messaging.utils.device_push.requests")
    def test_returns_false_on_exception(self, mock_requests):
        mock_requests.post.side_effect = Exception("Timeout")
        result = send_expo_push(token="t", title="T", body="B", data={})
        self.assertFalse(result)

    @patch("messaging.utils.device_push.requests")
    def test_payload_includes_sound_and_priority(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": {"status": "ok"}}
        mock_requests.post.return_value = mock_resp
        send_expo_push(token="t", title="T", body="B", data={})
        payload = mock_requests.post.call_args[1]["json"]
        self.assertEqual(payload["sound"], "default")
        self.assertEqual(payload["priority"], "high")

    @patch("messaging.utils.device_push.requests")
    def test_expo_push_url_is_correct(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": {"status": "ok"}}
        mock_requests.post.return_value = mock_resp
        send_expo_push(token="t", title="T", body="B", data={})
        url = mock_requests.post.call_args[0][0]
        self.assertIn("exp.host", url)
        self.assertIn("push/send", url)
