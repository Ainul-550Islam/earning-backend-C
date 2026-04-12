# api/publisher_tools/webhooks/fraud_webhook.py
"""
Fraud Webhook — IVT detection, fraud alerts, revenue deductions।
Real-time fraud notifications publishers-দের পাঠায়।
"""
from decimal import Decimal
from typing import Dict, List, Optional
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def build_fraud_detected_payload(fraud_log) -> Dict:
    """Fraud detection event payload।"""
    publisher = fraud_log.publisher
    return {
        "event":         "fraud.detected",
        "timestamp":     timezone.now().isoformat(),
        "publisher_id":  publisher.publisher_id,
        "fraud": {
            "log_id":           str(fraud_log.id),
            "traffic_type":     fraud_log.traffic_type,
            "severity":         fraud_log.severity,
            "fraud_score":      fraud_log.fraud_score,
            "detection_signals":fraud_log.detection_signals,
            "ip_address":       fraud_log.ip_address,
            "country":          fraud_log.country,
            "device_type":      fraud_log.device_type,
            "detected_at":      fraud_log.detected_at.isoformat(),
        },
        "inventory": {
            "site_id":      fraud_log.site.site_id if fraud_log.site else None,
            "app_id":       fraud_log.app.app_id if fraud_log.app else None,
            "ad_unit_id":   fraud_log.ad_unit.unit_id if fraud_log.ad_unit else None,
        },
        "impact": {
            "affected_impressions": fraud_log.affected_impressions,
            "revenue_at_risk":     float(fraud_log.revenue_at_risk),
            "action_taken":        fraud_log.action_taken,
        },
        "action_required": fraud_log.severity in ("high", "critical"),
        "dispute_available": True,
        "dispute_window_days": 5,
    }


def build_ivt_summary_payload(publisher, summary_data: Dict) -> Dict:
    """Daily IVT summary payload।"""
    return {
        "event":          "fraud.daily_summary",
        "timestamp":      timezone.now().isoformat(),
        "publisher_id":   publisher.publisher_id,
        "period":         summary_data.get("period", "daily"),
        "summary": {
            "total_ivt_events":     summary_data.get("total_events", 0),
            "critical_events":      summary_data.get("critical", 0),
            "high_events":          summary_data.get("high", 0),
            "ivt_rate_pct":         float(summary_data.get("ivt_rate", 0)),
            "revenue_at_risk_usd":  float(summary_data.get("revenue_at_risk", 0)),
            "revenue_deducted_usd": float(summary_data.get("revenue_deducted", 0)),
        },
        "by_type":    summary_data.get("by_type", []),
        "risk_level": summary_data.get("risk_level", "low"),
        "recommendation": (
            "Immediate action required — contact support." if summary_data.get("risk_level") == "critical"
            else "Review and investigate suspicious traffic sources."
        ),
    }


def send_fraud_detected_webhook(publisher, fraud_log) -> bool:
    """
    Fraud detection webhook।
    High/critical severity হলে immediately পাঠায়।
    """
    from .webhook_manager import send_webhook_event
    if fraud_log.severity not in ("high", "critical"):
        return False  # Only send for high+ severity
    payload = build_fraud_detected_payload(fraud_log)
    try:
        logs = send_webhook_event(publisher, "fraud.high_risk_detected", payload)
        logger.warning(
            f"Fraud webhook sent: publisher={publisher.publisher_id}, "
            f"type={fraud_log.traffic_type}, severity={fraud_log.severity}, score={fraud_log.fraud_score}"
        )
        return len(logs) > 0
    except Exception as e:
        logger.error(f"Fraud detection webhook failed: {e}")
        return False


def send_ivt_daily_summary_webhook(publisher, summary_data: Dict) -> bool:
    """Daily IVT summary webhook।"""
    from .webhook_manager import send_webhook_event
    payload = build_ivt_summary_payload(publisher, summary_data)
    try:
        send_webhook_event(publisher, "fraud.daily_summary", payload)
        return True
    except Exception as e:
        logger.error(f"IVT summary webhook failed: {e}")
        return False


def send_publisher_warned_webhook(publisher, warning_data: Dict) -> bool:
    """
    Publisher fraud warning notification।
    IVT rate threshold exceed করলে।
    """
    from .webhook_manager import send_webhook_event
    payload = {
        "event":          "fraud.publisher_warned",
        "timestamp":      timezone.now().isoformat(),
        "publisher_id":   publisher.publisher_id,
        "warning": {
            "type":              warning_data.get("type", "high_ivt_rate"),
            "current_ivt_rate":  float(warning_data.get("ivt_rate", 0)),
            "threshold":         float(warning_data.get("threshold", 20)),
            "period":            warning_data.get("period", "7 days"),
            "warning_level":     warning_data.get("level", "yellow"),
            "action_deadline":   warning_data.get("deadline", ""),
        },
        "consequences": {
            "if_not_resolved": "Account may be suspended if IVT rate exceeds 40%.",
            "current_status":   publisher.status,
            "at_risk":          warning_data.get("ivt_rate", 0) > 30,
        },
        "resources": {
            "fraud_guide_url":   "https://docs.publishertools.io/fraud-prevention",
            "support_url":       "https://publishertools.io/support",
            "contact":           "fraud@publishertools.io",
        },
    }
    try:
        send_webhook_event(publisher, "fraud.publisher_warned", payload)
        return True
    except Exception as e:
        logger.error(f"Publisher warned webhook failed: {e}")
        return False


def send_revenue_deduction_webhook(publisher, deduction_data: Dict) -> bool:
    """
    Revenue deduction notification।
    IVT কারণে revenue কাটা হলে।
    """
    from .webhook_manager import send_webhook_event
    payload = {
        "event":          "fraud.revenue_deducted",
        "timestamp":      timezone.now().isoformat(),
        "publisher_id":   publisher.publisher_id,
        "deduction": {
            "period_start":     deduction_data.get("period_start", ""),
            "period_end":       deduction_data.get("period_end", ""),
            "gross_revenue":    float(deduction_data.get("gross_revenue", 0)),
            "deducted_amount":  float(deduction_data.get("deducted_amount", 0)),
            "net_revenue":      float(deduction_data.get("net_revenue", 0)),
            "deduction_reason": deduction_data.get("reason", "invalid_traffic"),
            "ivt_rate_pct":     float(deduction_data.get("ivt_rate", 0)),
            "affected_ad_units":deduction_data.get("affected_units", []),
        },
        "dispute_info": {
            "can_dispute":    True,
            "dispute_deadline":deduction_data.get("dispute_deadline", ""),
            "dispute_url":    "https://publishertools.io/publisher/disputes/",
            "evidence_needed": "Traffic source reports, server logs, GA data",
        },
    }
    try:
        send_webhook_event(publisher, "fraud.revenue_deducted", payload)
        return True
    except Exception as e:
        logger.error(f"Revenue deduction webhook failed: {e}")
        return False


def send_ip_blocked_webhook(publisher, ip_data: Dict) -> bool:
    """IP blocked notification।"""
    from .webhook_manager import send_webhook_event
    payload = {
        "event":          "fraud.ip_blocked",
        "timestamp":      timezone.now().isoformat(),
        "publisher_id":   publisher.publisher_id,
        "blocked_ip": {
            "ip_masked":      ip_data.get("ip_masked", "xxx.xxx.xxx.xxx"),
            "country":        ip_data.get("country", ""),
            "block_reason":   ip_data.get("reason", "suspicious_traffic"),
            "fraud_score":    ip_data.get("fraud_score", 0),
            "block_duration": ip_data.get("duration_hours", 24),
            "blocked_at":     timezone.now().isoformat(),
        },
    }
    try:
        send_webhook_event(publisher, "fraud.ip_blocked", payload)
        return True
    except Exception as e:
        logger.error(f"IP blocked webhook failed: {e}")
        return False
