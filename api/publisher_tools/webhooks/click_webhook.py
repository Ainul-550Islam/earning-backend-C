# api/publisher_tools/webhooks/click_webhook.py
"""
Click Webhook — Click events publishers-দের endpoint-এ real-time পাঠায়।
Click fraud detection result সহ delivery করে।
"""
from decimal import Decimal
from typing import Dict, List, Optional
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def build_click_event_payload(click_data: Dict) -> Dict:
    """
    Click event payload build করে।
    Click revenue ও fraud score সহ।
    """
    return {
        "event":         "click",
        "event_id":      click_data.get("event_id", ""),
        "timestamp":     timezone.now().isoformat(),
        "publisher_id":  click_data.get("publisher_id", ""),
        "ad_unit_id":    click_data.get("ad_unit_id", ""),
        "site_id":       click_data.get("site_id"),
        "app_id":        click_data.get("app_id"),
        "placement_id":  click_data.get("placement_id"),
        "click": {
            "click_id":       click_data.get("click_id", ""),
            "impression_id":  click_data.get("impression_id", ""),
            "ad_format":      click_data.get("ad_format", ""),
            "creative_id":    click_data.get("creative_id", ""),
            "destination_url":click_data.get("destination_url", ""),
            "click_position": click_data.get("click_position", ""),
            "time_since_impression_sec": click_data.get("time_since_impression_sec", 0),
        },
        "revenue": {
            "cpc_amount":      float(click_data.get("cpc_amount", 0)),
            "publisher_cpc":   float(click_data.get("publisher_cpc", 0)),
            "currency":        click_data.get("currency", "USD"),
            "network":         click_data.get("network_name", ""),
            "earning_type":    click_data.get("earning_type", "cpc"),
        },
        "user": {
            "country":      click_data.get("country", ""),
            "device_type":  click_data.get("device_type", ""),
            "os":           click_data.get("os", ""),
            "browser":      click_data.get("browser", ""),
            "ip_address":   click_data.get("ip_masked", ""),
            "session_id":   click_data.get("session_id", ""),
            "user_agent_hash": click_data.get("user_agent_hash", ""),
        },
        "fraud": {
            "is_fraud":       click_data.get("is_fraud", False),
            "fraud_score":    click_data.get("fraud_score", 0),
            "fraud_type":     click_data.get("fraud_type", ""),
            "is_deducted":    click_data.get("is_deducted", False),
            "deduction_reason":click_data.get("deduction_reason", ""),
        },
    }


def send_click_webhook(publisher, click_data: Dict) -> List[Dict]:
    """
    Publisher-এর click webhook-এ event পাঠায়।
    Valid ও invalid clicks উভয়ের জন্যই পাঠানো হয়।
    """
    from .webhook_manager import send_webhook_event
    payload = build_click_event_payload(click_data)
    event_type = "click.fraud_detected" if click_data.get("is_fraud") else "click.valid"
    try:
        delivery_logs = send_webhook_event(publisher, event_type, payload)
        logger.debug(
            f"Click webhook sent: publisher={publisher.publisher_id}, "
            f"unit={click_data.get('ad_unit_id')}, fraud={click_data.get('is_fraud')}"
        )
        return [{"delivery_id": str(log.delivery_id), "status": log.status} for log in delivery_logs]
    except Exception as e:
        logger.error(f"Click webhook failed: {e}")
        return []


def send_click_deduction_webhook(publisher, click_id: str, deduction_data: Dict) -> bool:
    """
    Click revenue deduction notification পাঠায়।
    Invalid click-এর revenue কাটা গেলে publisher-কে জানায়।
    """
    from .webhook_manager import send_webhook_event
    payload = {
        "event":          "click.revenue_deducted",
        "timestamp":      timezone.now().isoformat(),
        "publisher_id":   publisher.publisher_id,
        "click_id":       click_id,
        "deduction": {
            "original_cpc":     float(deduction_data.get("original_cpc", 0)),
            "deducted_amount":  float(deduction_data.get("deducted_amount", 0)),
            "deduction_reason": deduction_data.get("reason", "invalid_traffic"),
            "fraud_type":       deduction_data.get("fraud_type", ""),
            "fraud_score":      deduction_data.get("fraud_score", 0),
            "detection_method": deduction_data.get("detection_method", "automated"),
        },
        "dispute_info": {
            "can_dispute":    True,
            "dispute_window": "5 business days",
            "dispute_url":    f"https://publishertools.io/publisher/disputes/",
        },
    }
    try:
        send_webhook_event(publisher, "click.revenue_deducted", payload)
        return True
    except Exception as e:
        logger.error(f"Click deduction webhook failed: {e}")
        return False


def send_click_velocity_alert(publisher, unit_id: str, velocity_data: Dict) -> bool:
    """
    High click velocity alert পাঠায়।
    Unusual click patterns detect হলে।
    """
    from .webhook_manager import send_webhook_event
    payload = {
        "event":          "click.velocity_alert",
        "timestamp":      timezone.now().isoformat(),
        "publisher_id":   publisher.publisher_id,
        "ad_unit_id":     unit_id,
        "velocity": {
            "clicks_per_minute": velocity_data.get("clicks_per_minute", 0),
            "threshold":         velocity_data.get("threshold", 10),
            "time_window_sec":   velocity_data.get("time_window_sec", 60),
            "source_ip":         velocity_data.get("source_ip_masked", ""),
            "action_taken":      velocity_data.get("action_taken", "flagged"),
        },
        "recommendation": "Review traffic sources for this ad unit immediately.",
    }
    try:
        send_webhook_event(publisher, "click.velocity_alert", payload)
        return True
    except Exception as e:
        logger.error(f"Click velocity alert webhook failed: {e}")
        return False
