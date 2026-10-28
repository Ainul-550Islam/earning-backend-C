"""
test_utils_call_manager.py
===========================
Full coverage for messaging/utils/call_manager.py
Functions: generate_room_id, get_ice_servers, _get_twilio_ice_servers,
           _get_xirsys_ice_servers, build_sdp_offer_payload,
           build_sdp_answer_payload, build_ice_candidate_payload
Place in: messaging/tests/test_utils_call_manager.py
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from ..utils.call_manager import (
    generate_room_id,
    get_ice_servers,
    _get_twilio_ice_servers,
    _get_xirsys_ice_servers,
    build_sdp_offer_payload,
    build_sdp_answer_payload,
    build_ice_candidate_payload,
)


class TestGenerateRoomId(TestCase):
    def test_returns_string(self):
        self.assertIsInstance(generate_room_id(), str)

    def test_length_is_16(self):
        self.assertEqual(len(generate_room_id()), 16)

    def test_unique_each_call(self):
        ids = {generate_room_id() for _ in range(100)}
        self.assertEqual(len(ids), 100)

    def test_only_hex_chars(self):
        room_id = generate_room_id()
        self.assertTrue(all(c in "0123456789abcdef" for c in room_id))


class TestGetIceServers(TestCase):
    @override_settings(WEBRTC_STUN_SERVERS=None, WEBRTC_TURN_CONFIG=None)
    def test_returns_default_stun_servers(self):
        result = get_ice_servers()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        urls = [s.get("urls", "") for s in result]
        self.assertTrue(any("stun:" in u for u in urls))

    @override_settings(WEBRTC_TURN_CONFIG=None)
    def test_returns_list_when_no_turn_config(self):
        result = get_ice_servers()
        self.assertIsInstance(result, list)

    @override_settings(WEBRTC_TURN_CONFIG={"provider": "static", "servers": [{"urls": "turn:turn.example.com"}]})
    def test_static_turn_config_appended(self):
        result = get_ice_servers()
        urls = [s.get("urls", "") for s in result]
        self.assertIn("turn:turn.example.com", urls)

    @override_settings(WEBRTC_TURN_CONFIG={"provider": "twilio"})
    @patch("messaging.utils.call_manager._get_twilio_ice_servers")
    def test_delegates_to_twilio(self, mock_twilio):
        mock_twilio.return_value = [{"urls": "stun:global.stun.twilio.com"}]
        result = get_ice_servers()
        mock_twilio.assert_called_once()
        self.assertEqual(result, [{"urls": "stun:global.stun.twilio.com"}])

    @override_settings(WEBRTC_TURN_CONFIG={"provider": "xirsys"})
    @patch("messaging.utils.call_manager._get_xirsys_ice_servers")
    def test_delegates_to_xirsys(self, mock_xirsys):
        mock_xirsys.return_value = [{"urls": "turn:xirsys.example.com"}]
        result = get_ice_servers()
        mock_xirsys.assert_called_once()
        self.assertEqual(result, [{"urls": "turn:xirsys.example.com"}])

    def test_user_id_param_accepted(self):
        result = get_ice_servers(user_id=42)
        self.assertIsInstance(result, list)


class TestGetTwilioIceServers(TestCase):
    @override_settings(TWILIO_ACCOUNT_SID=None, TWILIO_AUTH_TOKEN=None)
    def test_returns_fallback_stun_when_not_configured(self):
        result = _get_twilio_ice_servers()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertIn("stun:", result[0]["urls"])

    @override_settings(TWILIO_ACCOUNT_SID="ACfake", TWILIO_AUTH_TOKEN="fake_token")
    @patch("requests.post")
    def test_returns_ice_servers_from_twilio(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "ice_servers": [
                {"urls": "stun:global.stun.twilio.com:3478"},
                {"urls": "turn:global.turn.twilio.com:3478", "username": "u", "credential": "p"},
            ]
        }
        mock_post.return_value = mock_resp
        result = _get_twilio_ice_servers()
        self.assertEqual(len(result), 2)
        urls = [s["urls"] for s in result]
        self.assertIn("stun:global.stun.twilio.com:3478", urls)

    @override_settings(TWILIO_ACCOUNT_SID="ACfake", TWILIO_AUTH_TOKEN="fake_token")
    @patch("requests.post")
    def test_returns_fallback_on_request_error(self, mock_post):
        mock_post.side_effect = Exception("Connection refused")
        result = _get_twilio_ice_servers()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertIn("stun:", result[0]["urls"])


class TestGetXirsysIceServers(TestCase):
    @override_settings(XIRSYS_IDENT=None, XIRSYS_SECRET=None)
    def test_returns_fallback_when_not_configured(self):
        result = _get_xirsys_ice_servers()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertIn("stun:", result[0]["urls"])

    @override_settings(XIRSYS_IDENT="myident", XIRSYS_SECRET="mysecret", XIRSYS_CHANNEL="messaging")
    @patch("requests.put")
    def test_returns_ice_servers_from_xirsys(self, mock_put):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "v": {
                "iceServers": [
                    {"urls": "stun:ss-turn1.xirsys.com"},
                    {"urls": "turn:ss-turn1.xirsys.com", "username": "u", "credential": "c"},
                ]
            }
        }
        mock_put.return_value = mock_resp
        result = _get_xirsys_ice_servers()
        self.assertEqual(len(result), 2)

    @override_settings(XIRSYS_IDENT="myident", XIRSYS_SECRET="mysecret")
    @patch("requests.put")
    def test_returns_fallback_on_error(self, mock_put):
        mock_put.side_effect = Exception("Timeout")
        result = _get_xirsys_ice_servers()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)


class TestBuildSdpOfferPayload(TestCase):
    def test_returns_correct_structure(self):
        payload = build_sdp_offer_payload("room123", caller_id=1, callee_id=2)
        self.assertEqual(payload["type"], "call.signal")
        self.assertEqual(payload["signal_type"], "offer")
        self.assertEqual(payload["room_id"], "room123")
        self.assertEqual(payload["caller_id"], "1")
        self.assertEqual(payload["callee_id"], "2")

    def test_ids_are_stringified(self):
        payload = build_sdp_offer_payload("abc", caller_id=99, callee_id=77)
        self.assertIsInstance(payload["caller_id"], str)
        self.assertIsInstance(payload["callee_id"], str)

    def test_uuid_ids(self):
        import uuid
        cid = uuid.uuid4()
        payload = build_sdp_offer_payload("r1", caller_id=cid, callee_id=cid)
        self.assertEqual(payload["caller_id"], str(cid))


class TestBuildSdpAnswerPayload(TestCase):
    def test_returns_correct_structure(self):
        payload = build_sdp_answer_payload("room456", sdp="v=0\r\no=...")
        self.assertEqual(payload["type"], "call.signal")
        self.assertEqual(payload["signal_type"], "answer")
        self.assertEqual(payload["room_id"], "room456")
        self.assertEqual(payload["sdp"], "v=0\r\no=...")

    def test_empty_sdp_allowed(self):
        payload = build_sdp_answer_payload("r", sdp="")
        self.assertEqual(payload["sdp"], "")


class TestBuildIceCandidatePayload(TestCase):
    def test_returns_correct_structure(self):
        candidate = {"candidate": "candidate:0 1 UDP ...", "sdpMid": "0", "sdpMLineIndex": 0}
        payload = build_ice_candidate_payload("room789", candidate)
        self.assertEqual(payload["type"], "call.signal")
        self.assertEqual(payload["signal_type"], "ice_candidate")
        self.assertEqual(payload["room_id"], "room789")
        self.assertEqual(payload["candidate"], candidate)

    def test_candidate_dict_preserved(self):
        candidate = {"candidate": "...", "sdpMid": "audio", "sdpMLineIndex": 1}
        payload = build_ice_candidate_payload("r", candidate)
        self.assertIs(payload["candidate"], candidate)
