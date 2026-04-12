#!/usr/bin/env python
# api/publisher_tools/scripts/process_payments.py
"""
Process Payments — Automatic payment processing pipeline।
Eligible payout requests automatically process করে।
"""
import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)


def process_pending_payout_requests():
    """Pending payout requests process করে।"""
    from api.publisher_tools.publisher_management.publisher_payout import PayoutRequest
    from api.publisher_tools.payment_settlement.payout_manager import check_payout_eligibility
    pending = PayoutRequest.objects.filter(status="pending").select_related("publisher", "bank_account")
    processed = 0
    approved  = 0
    rejected  = 0
    for payout in pending:
        try:
            eligibility = check_payout_eligibility(payout.publisher)
            if eligibility.get("eligible"):
                payout.approve(approved_amount=payout.requested_amount)
                approved += 1
                print(f"  ✅ Approved: {payout.request_id} — ${payout.approved_amount}")
            else:
                payout.reject(eligibility.get("reason", "Eligibility check failed"))
                rejected += 1
                print(f"  ❌ Rejected: {payout.request_id} — {eligibility.get('reason')}")
            processed += 1
        except Exception as e:
            logger.error(f"Payout processing error [{payout.request_id}]: {e}")
    print(f"Payouts: {approved} approved, {rejected} rejected of {processed} processed")
    return {"processed": processed, "approved": approved, "rejected": rejected}


def execute_approved_payouts():
    """
    Approved payouts execute করে (payment gateway call)।
    Production-এ bKash/Nagad API অথবা bank transfer।
    """
    from api.publisher_tools.publisher_management.publisher_payout import PayoutRequest
    from api.publisher_tools.webhooks.payment_webhook import send_payout_status_webhook
    import uuid
    approved = PayoutRequest.objects.filter(status="approved").select_related("publisher", "bank_account")
    executed = 0
    for payout in approved:
        try:
            payout.status = "processing"
            payout.save(update_fields=["status", "updated_at"])
            # Production: actual payment gateway call here
            # e.g., bkash_api.transfer(payout.bank_account.account_number, payout.net_amount)
            payment_reference = f"PT-{uuid.uuid4().hex[:12].upper()}"
            payout.mark_completed(payment_reference)
            send_payout_status_webhook(payout.publisher, payout)
            executed += 1
            print(f"  💰 Executed: {payout.request_id} — ${payout.net_amount} — Ref: {payment_reference}")
        except Exception as e:
            payout.status = "failed"
            payout.save(update_fields=["status", "updated_at"])
            logger.error(f"Payout execution error [{payout.request_id}]: {e}")
    print(f"✅ Executed {executed} payouts")
    return {"executed": executed}


def check_overdue_invoices():
    """Overdue invoices check ও reminder পাঠায়।"""
    from api.publisher_tools.models import PublisherInvoice
    today = timezone.now().date()
    overdue = PublisherInvoice.objects.filter(status="issued", due_date__lt=today)
    count = 0
    for invoice in overdue:
        try:
            from api.publisher_tools.webhooks.payment_webhook import send_invoice_failed_webhook
            send_invoice_failed_webhook(invoice.publisher, invoice, "Payment overdue")
            count += 1
        except Exception as e:
            logger.error(f"Overdue reminder failed [{invoice.invoice_number}]: {e}")
    print(f"✅ Overdue invoice reminders sent: {count}")
    return {"overdue_count": count}


def run():
    print(f"🔄 Payment processing started at {timezone.now()}")
    return {
        "pending_processed": process_pending_payout_requests(),
        "approved_executed": execute_approved_payouts(),
        "overdue_checked":   check_overdue_invoices(),
        "completed_at":      timezone.now().isoformat(),
    }

if __name__ == "__main__":
    run()
