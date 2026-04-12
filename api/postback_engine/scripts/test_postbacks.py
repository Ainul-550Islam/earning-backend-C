"""
scripts/test_postbacks.py – Test postback sending utility.

Usage:
  python manage.py shell < api/postback_engine/scripts/test_postbacks.py
  -- or --
  python api/postback_engine/scripts/test_postbacks.py --network cpalead
"""
import hashlib
import hmac
import time
import urllib.parse

import requests


BASE_URL = "http://localhost:8000"


def send_test_postback(
    network_key: str,
    user_sub_id: str,
    offer_id: str = "test_offer_001",
    payout: float = 0.50,
    secret: str = "",
):
    """Send a test postback to the local server."""
    lead_id = f"TEST_{int(time.time())}"
    timestamp = str(int(time.time()))

    params = {
        "lead_id": lead_id,
        "offer_id": offer_id,
        "payout": str(payout),
        "currency": "USD",
        "sub_id": user_sub_id,
        "ts": timestamp,
    }

    # Sign if secret provided
    if secret:
        sorted_params = sorted(params.items())
        message = urllib.parse.urlencode(sorted_params) + f"&ts={timestamp}"
        sig = hmac.new(
            secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()
        params["sig"] = sig

    url = f"{BASE_URL}/api/postback_engine/postback/{network_key}/"
    resp = requests.get(url, params=params, timeout=10)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.json()}")
    return resp


def replay_failed_postbacks(limit: int = 50):
    """Replay all failed postbacks via admin API."""
    import django
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    from api.postback_engine.models import PostbackRawLog
    from api.postback_engine.enums import PostbackStatus
    from api.postback_engine.tasks import process_postback_task

    qs = PostbackRawLog.objects.filter(status=PostbackStatus.FAILED)[:limit]
    count = 0
    for raw_log in qs:
        process_postback_task.apply_async(args=[str(raw_log.id)], countdown=0)
        count += 1
    print(f"Queued {count} postbacks for replay.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test postback sender")
    parser.add_argument("--network", default="cpalead", help="Network key")
    parser.add_argument("--user", default="test_user_001", help="Sub ID / user ID")
    parser.add_argument("--offer", default="test_offer", help="Offer ID")
    parser.add_argument("--payout", type=float, default=0.5, help="Payout amount")
    parser.add_argument("--secret", default="", help="HMAC secret")
    args = parser.parse_args()

    print(f"Sending test postback to network={args.network}...")
    send_test_postback(
        network_key=args.network,
        user_sub_id=args.user,
        offer_id=args.offer,
        payout=args.payout,
        secret=args.secret,
    )
