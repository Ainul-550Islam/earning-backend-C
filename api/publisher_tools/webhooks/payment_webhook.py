# api/publisher_tools/webhooks/payment_webhook.py
"""
Payment Webhook — Invoice ও payout events।
Invoice generated, issued, paid, failed — সব events।
"""
from decimal import Decimal
from typing import Dict, List, Optional
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def build_invoice_created_payload(invoice) -> Dict:
    """Invoice created event payload।"""
    publisher = invoice.publisher
    return {
        "event":          "invoice.created",
        "timestamp":      timezone.now().isoformat(),
        "publisher_id":   publisher.publisher_id,
        "invoice": {
            "invoice_number":   invoice.invoice_number,
            "invoice_type":     invoice.get_invoice_type_display(),
            "period_start":     str(invoice.period_start),
            "period_end":       str(invoice.period_end),
            "status":           invoice.status,
        },
        "amounts": {
            "gross_revenue":    float(invoice.gross_revenue),
            "publisher_share":  float(invoice.publisher_share),
            "ivt_deduction":    float(invoice.ivt_deduction),
            "processing_fee":   float(invoice.processing_fee),
            "withholding_tax":  float(invoice.withholding_tax),
            "net_payable":      float(invoice.net_payable),
            "currency":         invoice.currency,
        },
        "traffic": {
            "total_impressions": invoice.total_impressions,
            "total_clicks":      invoice.total_clicks,
            "total_ad_requests": invoice.total_ad_requests,
        },
    }


def build_invoice_paid_payload(invoice) -> Dict:
    """Invoice paid event payload।"""
    publisher = invoice.publisher
    return {
        "event":         "invoice.paid",
        "timestamp":     timezone.now().isoformat(),
        "publisher_id":  publisher.publisher_id,
        "invoice": {
            "invoice_number":   invoice.invoice_number,
            "period_start":     str(invoice.period_start),
            "period_end":       str(invoice.period_end),
            "net_payable":      float(invoice.net_payable),
            "currency":         invoice.currency,
            "status":           "paid",
            "paid_at":          invoice.paid_at.isoformat() if invoice.paid_at else None,
        },
        "payment": {
            "payment_reference":    invoice.payment_reference,
            "payment_method":       invoice.payout_threshold.get_payment_method_display() if invoice.payout_threshold else "N/A",
            "account_masked":       invoice.payout_threshold.masked_account_number if invoice.payout_threshold else "",
        },
        "balance_update": {
            "new_total_paid_out": float(publisher.total_paid_out),
            "pending_balance":    float(publisher.pending_balance),
        },
    }


def build_payout_request_payload(payout_request) -> Dict:
    """Payout request event payload।"""
    publisher = payout_request.publisher
    return {
        "event":         f"payout.{payout_request.status}",
        "timestamp":     timezone.now().isoformat(),
        "publisher_id":  publisher.publisher_id,
        "payout": {
            "request_id":       payout_request.request_id,
            "requested_amount": float(payout_request.requested_amount),
            "approved_amount":  float(payout_request.approved_amount or 0),
            "processing_fee":   float(payout_request.processing_fee),
            "withholding_tax":  float(payout_request.withholding_tax),
            "net_amount":       float(payout_request.net_amount or 0),
            "currency":         "USD",
            "status":           payout_request.status,
            "payment_method":   payout_request.bank_account.get_account_type_display() if payout_request.bank_account else "N/A",
            "payment_reference": payout_request.payment_reference,
            "created_at":       payout_request.created_at.isoformat(),
            "completed_at":     payout_request.completed_at.isoformat() if payout_request.completed_at else None,
        },
    }


def send_invoice_created_webhook(publisher, invoice) -> bool:
    """Invoice created notification।"""
    from .webhook_manager import send_webhook_event
    payload = build_invoice_created_payload(invoice)
    try:
        logs = send_webhook_event(publisher, "invoice.created", payload)
        logger.info(f"Invoice created webhook sent: {invoice.invoice_number}, deliveries={len(logs)}")
        return True
    except Exception as e:
        logger.error(f"Invoice created webhook failed: {e}")
        return False


def send_invoice_issued_webhook(publisher, invoice) -> bool:
    """Invoice issued notification (Draft → Issued)।"""
    from .webhook_manager import send_webhook_event
    payload = {
        **build_invoice_created_payload(invoice),
        "event":      "invoice.issued",
        "issued_at":  invoice.issued_at.isoformat() if invoice.issued_at else None,
        "due_date":   str(invoice.due_date) if invoice.due_date else None,
        "action_required": "Please ensure your payment details are up to date.",
    }
    try:
        send_webhook_event(publisher, "invoice.issued", payload)
        return True
    except Exception as e:
        logger.error(f"Invoice issued webhook failed: {e}")
        return False


def send_invoice_paid_webhook(publisher, invoice) -> bool:
    """Invoice paid notification।"""
    from .webhook_manager import send_webhook_event
    payload = build_invoice_paid_payload(invoice)
    try:
        logs = send_webhook_event(publisher, "invoice.paid", payload)
        logger.info(f"Invoice paid webhook sent: {invoice.invoice_number}, amount=${invoice.net_payable}")
        return True
    except Exception as e:
        logger.error(f"Invoice paid webhook failed: {e}")
        return False


def send_invoice_failed_webhook(publisher, invoice, reason: str = "") -> bool:
    """Payment failed notification।"""
    from .webhook_manager import send_webhook_event
    payload = {
        "event":         "invoice.payment_failed",
        "timestamp":     timezone.now().isoformat(),
        "publisher_id":  publisher.publisher_id,
        "invoice": {
            "invoice_number": invoice.invoice_number,
            "net_payable":    float(invoice.net_payable),
            "currency":       invoice.currency,
            "status":         "failed",
            "failed_at":      invoice.failed_at.isoformat() if invoice.failed_at else None,
        },
        "failure": {
            "reason":              reason or "Payment processing failed",
            "retry_scheduled":     True,
            "next_retry_in_hours": 24,
            "support_contact":     "publisher-support@publishertools.io",
        },
    }
    try:
        send_webhook_event(publisher, "invoice.payment_failed", payload)
        return True
    except Exception as e:
        logger.error(f"Invoice failed webhook error: {e}")
        return False


def send_payout_status_webhook(publisher, payout_request) -> bool:
    """Payout request status change notification।"""
    from .webhook_manager import send_webhook_event
    payload = build_payout_request_payload(payout_request)
    event = f"payout.{payout_request.status}"
    try:
        send_webhook_event(publisher, event, payload)
        return True
    except Exception as e:
        logger.error(f"Payout status webhook failed: {e}")
        return False


def send_payment_milestone_webhook(publisher, milestone_type: str, amount: float) -> bool:
    """
    Payment milestone notification।
    First payment, $100, $1000, $10000 milestones।
    """
    from .webhook_manager import send_webhook_event
    milestones = {
        "first_payment":  "🎉 First payment received!",
        "hundred_dollar": "💰 $100 earned!",
        "thousand_dollar":"🏆 $1,000 earned!",
        "ten_thousand":   "🚀 $10,000 earned!",
    }
    payload = {
        "event":         "payment.milestone",
        "timestamp":     timezone.now().isoformat(),
        "publisher_id":  publisher.publisher_id,
        "milestone": {
            "type":           milestone_type,
            "message":        milestones.get(milestone_type, "Payment milestone reached!"),
            "amount":         amount,
            "total_earned":   float(publisher.total_revenue),
            "total_paid_out": float(publisher.total_paid_out),
        },
    }
    try:
        send_webhook_event(publisher, "payment.milestone", payload)
        return True
    except Exception as e:
        logger.error(f"Milestone webhook failed: {e}")
        return False
