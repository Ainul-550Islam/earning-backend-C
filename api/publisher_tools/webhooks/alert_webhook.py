# api/publisher_tools/webhooks/alert_webhook.py
"""
Alert Webhook — System alerts, performance alerts, action required notifications।
Publisher-দের সব important system events পাঠায়।
"""
from decimal import Decimal
from typing import Dict, List, Optional
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

ALERT_PRIORITIES = {
    "critical": 1,
    "high":     2,
    "medium":   3,
    "low":      4,
    "info":     5,
}


def build_alert_payload(publisher, alert_type: str, severity: str, title: str, message: str, data: Dict = None) -> Dict:
    """
    Alert event payload builder।
    সব alert types-এর জন্য uniform structure।
    """
    return {
        "event":         "alert",
        "alert_type":    alert_type,
        "timestamp":     timezone.now().isoformat(),
        "publisher_id":  publisher.publisher_id,
        "alert": {
            "title":     title,
            "message":   message,
            "severity":  severity,
            "priority":  ALERT_PRIORITIES.get(severity, 5),
            "data":      data or {},
            "is_action_required": severity in ("critical", "high"),
        },
        "publisher_info": {
            "display_name":  publisher.display_name,
            "status":        publisher.status,
            "tier":          publisher.tier,
        },
        "support": {
            "contact":   "publisher-support@publishertools.io",
            "portal_url":"https://publishertools.io/publisher/support",
        },
    }


def send_alert_webhook(publisher, alert_type: str, severity: str, title: str, message: str, data: Dict = None) -> bool:
    """
    Generic alert webhook sender।
    সব alert types এই function দিয়ে পাঠানো হয়।
    """
    from .webhook_manager import send_webhook_event
    payload = build_alert_payload(publisher, alert_type, severity, title, message, data)
    try:
        logs = send_webhook_event(publisher, f"alert.{alert_type}", payload)
        logger.info(f"Alert webhook sent: publisher={publisher.publisher_id}, type={alert_type}, severity={severity}")
        return len(logs) > 0
    except Exception as e:
        logger.error(f"Alert webhook failed [{alert_type}]: {e}")
        return False


def send_kyc_alert(publisher, alert_subtype: str, details: Dict = None) -> bool:
    """KYC related alerts।"""
    messages = {
        "kyc_required":   ("KYC Required", "Complete KYC verification to unlock full payout features.", "high"),
        "kyc_expiring":   ("KYC Expiring Soon", "Your KYC verification expires in 30 days. Please renew.", "medium"),
        "kyc_expired":    ("KYC Expired", "Your KYC has expired. Payouts are suspended until renewal.", "critical"),
        "kyc_rejected":   ("KYC Rejected", "Your KYC submission was rejected. Please resubmit.", "high"),
        "kyc_approved":   ("KYC Approved", "Your identity has been verified. Full features unlocked!", "info"),
    }
    title, message, severity = messages.get(alert_subtype, ("KYC Alert", "KYC action required.", "medium"))
    return send_alert_webhook(publisher, f"kyc.{alert_subtype}", severity, title, message, details)


def send_performance_alert(publisher, metric: str, current_value: float, threshold: float, direction: str = "below") -> bool:
    """
    Performance threshold alerts।
    eCPM drop, fill rate drop, IVT spike, etc.
    """
    messages = {
        "ecpm_drop":         ("eCPM Drop Alert", f"Your eCPM dropped to ${current_value:.4f}, below threshold ${threshold:.4f}.", "high"),
        "fill_rate_drop":    ("Fill Rate Drop", f"Fill rate is {current_value:.1f}%, below threshold {threshold:.1f}%.", "medium"),
        "ivt_spike":         ("IVT Rate Spike", f"Invalid traffic rate {current_value:.1f}% exceeds threshold {threshold:.1f}%.", "high"),
        "revenue_drop":      ("Revenue Drop", f"Daily revenue ${current_value:.2f} dropped significantly.", "medium"),
        "impression_spike":  ("Traffic Spike Detected", f"Impressions spiked {current_value:.0f}% above baseline.", "low"),
        "site_quality_drop": ("Site Quality Score Drop", f"Quality score dropped to {current_value:.0f}/100.", "medium"),
    }
    title, message, severity = messages.get(metric, (f"{metric} Alert", f"{metric} is {current_value}, threshold: {threshold}.", "medium"))
    data = {"metric": metric, "current_value": current_value, "threshold": threshold, "direction": direction}
    return send_alert_webhook(publisher, f"performance.{metric}", severity, title, message, data)


def send_site_quality_alert(publisher, site, alert_data: Dict) -> bool:
    """Site quality issue alerts।"""
    issues = alert_data.get("issues", [])
    severity = "critical" if alert_data.get("malware_detected") or alert_data.get("adult_content") else "high" if len(issues) > 3 else "medium"
    title   = f"Site Quality Alert: {site.domain}"
    message = f"Quality issues detected on {site.domain}. Issues: {', '.join(issues[:3])}."
    return send_alert_webhook(publisher, "site.quality_issue", severity, title, message, {
        "site_id":          site.site_id,
        "domain":           site.domain,
        "quality_score":    site.quality_score,
        "issues":           issues,
        "malware_detected": alert_data.get("malware_detected", False),
    })


def send_payment_method_alert(publisher, alert_subtype: str, bank_account=None) -> bool:
    """Payment method related alerts।"""
    messages = {
        "not_configured":   ("Payment Method Required", "Configure a payment method to receive payouts.", "high"),
        "not_verified":     ("Payment Method Unverified", "Verify your payment method to enable payouts.", "medium"),
        "expiring":         ("Payment Method Expiring", "Your payment method details may need updating.", "medium"),
        "verified":         ("Payment Method Verified", "Your payment method has been verified successfully!", "info"),
    }
    title, message, severity = messages.get(alert_subtype, ("Payment Alert", "Payment action required.", "medium"))
    data = {}
    if bank_account:
        data = {"account_type": bank_account.account_type, "account_label": bank_account.account_label}
    return send_alert_webhook(publisher, f"payment_method.{alert_subtype}", severity, title, message, data)


def send_tier_change_alert(publisher, old_tier: str, new_tier: str) -> bool:
    """Publisher tier upgrade/downgrade notification।"""
    is_upgrade = ALERT_PRIORITIES.get(new_tier, 5) < ALERT_PRIORITIES.get(old_tier, 5)
    icon = "🎉" if is_upgrade else "⚠️"
    title   = f"{icon} Account Tier {'Upgraded' if is_upgrade else 'Changed'}"
    message = f"Your account tier changed from {old_tier.title()} to {new_tier.title()}."
    severity = "info" if is_upgrade else "medium"
    return send_alert_webhook(publisher, "account.tier_change", severity, title, message, {
        "old_tier":  old_tier,
        "new_tier":  new_tier,
        "is_upgrade":is_upgrade,
        "benefits_url": "https://publishertools.io/pricing",
    })


def send_account_suspended_alert(publisher, reason: str) -> bool:
    """Account suspension notification।"""
    title   = "⛔ Account Suspended"
    message = f"Your publisher account has been suspended. Reason: {reason}"
    return send_alert_webhook(publisher, "account.suspended", "critical", title, message, {
        "reason":       reason,
        "appeal_url":   "https://publishertools.io/publisher/appeal",
        "support_email":"publisher-support@publishertools.io",
    })


def send_new_invoice_alert(publisher, invoice) -> bool:
    """New invoice ready notification।"""
    title   = f"📄 Invoice Ready: {invoice.invoice_number}"
    message = f"Your invoice for {invoice.period_start} – {invoice.period_end} is ready. Amount: ${invoice.net_payable}"
    return send_alert_webhook(publisher, "invoice.new", "info", title, message, {
        "invoice_number": invoice.invoice_number,
        "period":         f"{invoice.period_start} – {invoice.period_end}",
        "net_payable":    float(invoice.net_payable),
        "currency":       invoice.currency,
        "due_date":       str(invoice.due_date) if invoice.due_date else None,
        "invoice_url":    f"https://publishertools.io/publisher/invoices/{invoice.invoice_number}/",
    })


def send_payout_threshold_met_alert(publisher, balance: float, threshold: float) -> bool:
    """Payout threshold reached notification।"""
    title   = "💰 Payout Threshold Reached!"
    message = f"Your balance ${balance:.2f} has reached the payout threshold ${threshold:.2f}. You can now request a payout."
    return send_alert_webhook(publisher, "payout.threshold_met", "info", title, message, {
        "balance":        balance,
        "threshold":      threshold,
        "payout_url":     "https://publishertools.io/publisher/payouts/",
    })


def send_ab_test_alert(publisher, test, alert_subtype: str) -> bool:
    """A/B test lifecycle alerts।"""
    messages = {
        "winner_declared":  (f"🏆 A/B Test Winner: {test.name}", f"Winner declared for your A/B test: {test.winner_variant.name if test.winner_variant else 'Unknown'}", "info"),
        "auto_paused":      (f"⏸ A/B Test Paused: {test.name}", "Test auto-paused due to significant negative impact.", "high"),
        "completed":        (f"✅ A/B Test Completed: {test.name}", "Your A/B test has concluded.", "info"),
    }
    title, message, severity = messages.get(alert_subtype, ("A/B Test Alert", "A/B test update.", "info"))
    return send_alert_webhook(publisher, f"ab_test.{alert_subtype}", severity, title, message, {
        "test_id":       test.test_id,
        "test_name":     test.name,
        "test_type":     test.test_type,
        "status":        test.status,
    })
