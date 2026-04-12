# api/publisher_tools/webhooks/conversion_webhook.py
"""
Conversion Webhook — CPA/CPI/CPS conversion events।
Offerwall, rewarded ads, affiliate conversions track করে।
"""
from decimal import Decimal
from typing import Dict, List, Optional
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def build_conversion_event_payload(conversion_data: Dict) -> Dict:
    """
    Conversion event payload build করে।
    CPA, CPI, CPS, CPS earnings সব include করে।
    """
    return {
        "event":         "conversion",
        "event_id":      conversion_data.get("event_id", ""),
        "timestamp":     timezone.now().isoformat(),
        "publisher_id":  conversion_data.get("publisher_id", ""),
        "ad_unit_id":    conversion_data.get("ad_unit_id", ""),
        "site_id":       conversion_data.get("site_id"),
        "app_id":        conversion_data.get("app_id"),
        "conversion": {
            "conversion_id":     conversion_data.get("conversion_id", ""),
            "click_id":          conversion_data.get("click_id", ""),
            "impression_id":     conversion_data.get("impression_id", ""),
            "offer_id":          conversion_data.get("offer_id", ""),
            "offer_name":        conversion_data.get("offer_name", ""),
            "advertiser_id":     conversion_data.get("advertiser_id", ""),
            "conversion_type":   conversion_data.get("conversion_type", "install"),
            "conversion_action": conversion_data.get("conversion_action", ""),
            "is_verified":       conversion_data.get("is_verified", False),
            "verification_method": conversion_data.get("verification_method", "postback"),
            "time_to_convert_sec":  conversion_data.get("time_to_convert_sec", 0),
        },
        "revenue": {
            "payout_type":     conversion_data.get("payout_type", "CPA"),
            "gross_payout":    float(conversion_data.get("gross_payout", 0)),
            "publisher_payout":float(conversion_data.get("publisher_payout", 0)),
            "currency":        conversion_data.get("currency", "USD"),
            "revenue_share_pct": float(conversion_data.get("revenue_share_pct", 70)),
            "network":         conversion_data.get("network_name", ""),
        },
        "user": {
            "country":          conversion_data.get("country", ""),
            "device_type":      conversion_data.get("device_type", ""),
            "os":               conversion_data.get("os", ""),
            "device_id_hash":   conversion_data.get("device_id_hash", ""),
            "is_new_user":      conversion_data.get("is_new_user", True),
        },
        "fraud": {
            "is_fraud":         conversion_data.get("is_fraud", False),
            "fraud_score":      conversion_data.get("fraud_score", 0),
            "fraud_type":       conversion_data.get("fraud_type", ""),
            "is_deducted":      conversion_data.get("is_deducted", False),
        },
        "postback": {
            "postback_url":     conversion_data.get("postback_url", ""),
            "postback_sent":    conversion_data.get("postback_sent", False),
            "postback_status":  conversion_data.get("postback_status", ""),
        },
    }


def send_conversion_webhook(publisher, conversion_data: Dict) -> List[Dict]:
    """
    Publisher-এর conversion webhook-এ event পাঠায়।
    Offerwall completions, installs, purchases সব।
    """
    from .webhook_manager import send_webhook_event
    payload = build_conversion_event_payload(conversion_data)
    conv_type = conversion_data.get("conversion_type", "install")
    event_name = f"conversion.{conv_type}"
    try:
        delivery_logs = send_webhook_event(publisher, event_name, payload)
        logger.info(
            f"Conversion webhook sent: publisher={publisher.publisher_id}, "
            f"type={conv_type}, payout=${conversion_data.get('publisher_payout', 0)}"
        )
        return [{"delivery_id": str(log.delivery_id), "status": log.status} for log in delivery_logs]
    except Exception as e:
        logger.error(f"Conversion webhook failed: {e}")
        return []


def send_postback_confirmation(publisher, postback_data: Dict) -> bool:
    """
    Server-side postback confirmation।
    Advertiser postback received হলে publisher-কে জানায়।
    """
    from .webhook_manager import send_webhook_event
    payload = {
        "event":          "conversion.postback_received",
        "timestamp":      timezone.now().isoformat(),
        "publisher_id":   publisher.publisher_id,
        "postback": {
            "conversion_id":    postback_data.get("conversion_id", ""),
            "offer_id":         postback_data.get("offer_id", ""),
            "advertiser_id":    postback_data.get("advertiser_id", ""),
            "payout":           float(postback_data.get("payout", 0)),
            "currency":         postback_data.get("currency", "USD"),
            "goal_id":          postback_data.get("goal_id", ""),
            "status":           postback_data.get("status", "approved"),
            "received_at":      postback_data.get("received_at", timezone.now().isoformat()),
        },
        "ssv": {
            "ssv_verified":     postback_data.get("ssv_verified", False),
            "signature_valid":  postback_data.get("signature_valid", False),
            "verification_url": postback_data.get("verification_url", ""),
        },
    }
    try:
        send_webhook_event(publisher, "conversion.postback_received", payload)
        return True
    except Exception as e:
        logger.error(f"Postback confirmation webhook failed: {e}")
        return False


def send_conversion_reversal_webhook(publisher, conversion_id: str, reversal_data: Dict) -> bool:
    """
    Conversion reversal notification।
    Chargeback বা fraudulent conversion-এ।
    """
    from .webhook_manager import send_webhook_event
    payload = {
        "event":         "conversion.reversed",
        "timestamp":     timezone.now().isoformat(),
        "publisher_id":  publisher.publisher_id,
        "conversion_id": conversion_id,
        "reversal": {
            "reason":          reversal_data.get("reason", "chargeback"),
            "original_payout": float(reversal_data.get("original_payout", 0)),
            "reversed_amount": float(reversal_data.get("reversed_amount", 0)),
            "reversed_at":     reversal_data.get("reversed_at", timezone.now().isoformat()),
            "can_dispute":     reversal_data.get("can_dispute", True),
        },
        "dispute_info": {
            "dispute_window":  "5 business days",
            "contact":         "publisher-support@publishertools.io",
        },
    }
    try:
        send_webhook_event(publisher, "conversion.reversed", payload)
        return True
    except Exception as e:
        logger.error(f"Conversion reversal webhook failed: {e}")
        return False
