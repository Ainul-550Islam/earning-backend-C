# api/publisher_tools/webhooks/impression_webhook.py
"""
Impression Webhook — Impression events publishers-দের endpoint-এ পাঠায়।
Real-time impression tracking ও notification।
"""
from decimal import Decimal
from typing import Dict, List, Optional
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def build_impression_event_payload(impression_data: Dict) -> Dict:
    """
    Impression event payload build করে।
    Publishers তাদের server-এ এই data receive করবে।
    """
    return {
        "event":          "impression",
        "event_id":       impression_data.get("event_id", ""),
        "timestamp":      timezone.now().isoformat(),
        "publisher_id":   impression_data.get("publisher_id", ""),
        "ad_unit_id":     impression_data.get("ad_unit_id", ""),
        "site_id":        impression_data.get("site_id"),
        "app_id":         impression_data.get("app_id"),
        "placement_id":   impression_data.get("placement_id"),
        "ad_format":      impression_data.get("ad_format", ""),
        "impression": {
            "impression_id":  impression_data.get("impression_id", ""),
            "ad_request_id":  impression_data.get("ad_request_id", ""),
            "creative_id":    impression_data.get("creative_id", ""),
            "advertiser_id":  impression_data.get("advertiser_id", ""),
            "campaign_id":    impression_data.get("campaign_id", ""),
            "is_viewable":    impression_data.get("is_viewable", False),
            "viewability_pct":impression_data.get("viewability_pct", 0),
            "time_in_view_sec":impression_data.get("time_in_view_sec", 0),
        },
        "revenue": {
            "gross_ecpm":     float(impression_data.get("gross_ecpm", 0)),
            "publisher_ecpm": float(impression_data.get("publisher_ecpm", 0)),
            "currency":       impression_data.get("currency", "USD"),
            "network":        impression_data.get("network_name", ""),
            "is_estimated":   impression_data.get("is_estimated", True),
        },
        "user": {
            "country":     impression_data.get("country", ""),
            "device_type": impression_data.get("device_type", ""),
            "os":          impression_data.get("os", ""),
            "browser":     impression_data.get("browser", ""),
            "session_id":  impression_data.get("session_id", ""),
        },
        "fraud": {
            "is_invalid":    impression_data.get("is_invalid", False),
            "fraud_score":   impression_data.get("fraud_score", 0),
            "ivt_type":      impression_data.get("ivt_type", ""),
        },
    }


def send_impression_webhook(publisher, impression_data: Dict) -> List[Dict]:
    """
    Publisher-এর impression webhook-এ event পাঠায়।
    Returns: list of delivery results
    """
    from .webhook_manager import send_webhook_event
    payload = build_impression_event_payload(impression_data)
    try:
        delivery_logs = send_webhook_event(publisher, "impression.served", payload)
        logger.debug(
            f"Impression webhook sent: publisher={publisher.publisher_id}, "
            f"unit={impression_data.get('ad_unit_id')}, deliveries={len(delivery_logs)}"
        )
        return [{"delivery_id": str(log.delivery_id), "status": log.status} for log in delivery_logs]
    except Exception as e:
        logger.error(f"Impression webhook failed: {e}")
        return []


def send_batch_impression_webhook(publisher, impressions: List[Dict]) -> Dict:
    """
    Batch impression events একসাথে পাঠায়।
    Reduces webhook call frequency।
    """
    from .webhook_manager import send_webhook_event
    if not impressions:
        return {"sent": 0, "failed": 0}
    batch_payload = {
        "event":        "impression.batch",
        "timestamp":    timezone.now().isoformat(),
        "publisher_id": publisher.publisher_id,
        "batch_count":  len(impressions),
        "impressions":  [build_impression_event_payload(imp) for imp in impressions],
        "batch_summary": {
            "total_impressions": len(impressions),
            "viewable": sum(1 for imp in impressions if imp.get("is_viewable")),
            "invalid":  sum(1 for imp in impressions if imp.get("is_invalid")),
            "total_ecpm": round(sum(float(imp.get("publisher_ecpm", 0)) for imp in impressions), 6),
        },
    }
    try:
        delivery_logs = send_webhook_event(publisher, "impression.batch", batch_payload)
        return {"sent": len(delivery_logs), "failed": 0, "batch_count": len(impressions)}
    except Exception as e:
        logger.error(f"Batch impression webhook failed: {e}")
        return {"sent": 0, "failed": len(impressions), "error": str(e)}


def handle_viewability_update(publisher, impression_id: str, viewability_data: Dict) -> bool:
    """
    Impression viewability update webhook পাঠায়।
    MRC viewability standard: 50% pixels, 1 second continuous।
    """
    from .webhook_manager import send_webhook_event
    payload = {
        "event":         "impression.viewability_update",
        "timestamp":     timezone.now().isoformat(),
        "publisher_id":  publisher.publisher_id,
        "impression_id": impression_id,
        "viewability": {
            "is_viewable":          viewability_data.get("is_viewable", False),
            "viewable_pixels_pct":  viewability_data.get("viewable_pixels_pct", 0),
            "continuous_view_sec":  viewability_data.get("continuous_view_sec", 0),
            "total_view_sec":       viewability_data.get("total_view_sec", 0),
            "mrc_standard_met":     viewability_data.get("mrc_standard_met", False),
            "groupm_standard_met":  viewability_data.get("groupm_standard_met", False),
        },
        "revenue_adjustment": {
            "viewable_ecpm":    float(viewability_data.get("viewable_ecpm", 0)),
            "adjustment_pct":   float(viewability_data.get("adjustment_pct", 0)),
        },
    }
    try:
        send_webhook_event(publisher, "impression.viewability_update", payload)
        return True
    except Exception as e:
        logger.error(f"Viewability update webhook failed: {e}")
        return False
