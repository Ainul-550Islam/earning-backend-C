"""
WebRTC Call Manager — ICE server config, room management helpers.
"""
from __future__ import annotations
import logging
import uuid

logger = logging.getLogger(__name__)


def generate_room_id() -> str:
    """Generate a unique, short WebRTC room ID."""
    return uuid.uuid4().hex[:16]


def get_ice_servers(user_id=None) -> list:
    """
    Return ICE server configuration.
    Supports STUN + TURN from settings.
    """
    from django.conf import settings

    stun_servers = getattr(settings, "WEBRTC_STUN_SERVERS", [
        {"urls": "stun:stun.l.google.com:19302"},
        {"urls": "stun:stun1.l.google.com:19302"},
    ])

    turn_config = getattr(settings, "WEBRTC_TURN_CONFIG", None)
    if turn_config:
        # Support dynamic TURN credentials (Twilio NTS, Xirsys)
        turn_provider = turn_config.get("provider", "static")
        if turn_provider == "twilio":
            return _get_twilio_ice_servers()
        elif turn_provider == "xirsys":
            return _get_xirsys_ice_servers()
        elif turn_provider == "static":
            return stun_servers + turn_config.get("servers", [])

    return stun_servers


def _get_twilio_ice_servers() -> list:
    """Fetch temporary TURN credentials from Twilio Network Traversal Service."""
    from django.conf import settings
    import requests

    account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
    if not account_sid or not auth_token:
        logger.debug("_get_twilio_ice_servers: Twilio credentials not configured.")
        return [{"urls": "stun:stun.l.google.com:19302"}]

    try:
        resp = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Tokens.json",
            auth=(account_sid, auth_token),
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json().get("ice_servers", [])
    except Exception as exc:
        logger.warning("_get_twilio_ice_servers: failed: %s", exc)
        return [{"urls": "stun:stun.l.google.com:19302"}]


def _get_xirsys_ice_servers() -> list:
    """Fetch ICE servers from Xirsys."""
    from django.conf import settings
    import requests

    ident = getattr(settings, "XIRSYS_IDENT", None)
    secret = getattr(settings, "XIRSYS_SECRET", None)
    channel = getattr(settings, "XIRSYS_CHANNEL", "messaging")
    if not ident or not secret:
        return [{"urls": "stun:stun.l.google.com:19302"}]

    try:
        resp = requests.put(
            f"https://global.xirsys.net/_turn/{channel}",
            auth=(ident, secret),
            json={"format": "urls"},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json().get("v", {})
        return data.get("iceServers", [])
    except Exception as exc:
        logger.warning("_get_xirsys_ice_servers: failed: %s", exc)
        return [{"urls": "stun:stun.l.google.com:19302"}]


def build_sdp_offer_payload(room_id: str, caller_id: Any, callee_id: Any) -> dict:
    """Helper to build the WebSocket signaling payload for SDP offer."""
    return {
        "type": "call.signal",
        "signal_type": "offer",
        "room_id": room_id,
        "caller_id": str(caller_id),
        "callee_id": str(callee_id),
    }


def build_sdp_answer_payload(room_id: str, sdp: str) -> dict:
    return {"type": "call.signal", "signal_type": "answer", "room_id": room_id, "sdp": sdp}


def build_ice_candidate_payload(room_id: str, candidate: dict) -> dict:
    return {"type": "call.signal", "signal_type": "ice_candidate", "room_id": room_id, "candidate": candidate}
