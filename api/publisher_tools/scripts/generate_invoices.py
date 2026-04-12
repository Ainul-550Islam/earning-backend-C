#!/usr/bin/env python
# api/publisher_tools/scripts/generate_invoices.py
"""
Generate Invoices — Monthly invoice generation script।
Usage: python manage.py shell < scripts/generate_invoices.py
"""
import logging
from decimal import Decimal
from datetime import date
from calendar import monthrange
from django.utils import timezone

logger = logging.getLogger(__name__)


def generate_invoices_for_month(year: int = None, month: int = None, dry_run: bool = False):
    """
    Specified month-এর সব eligible publishers-এর invoice generate করে।
    dry_run=True হলে শুধু দেখায়, save করে না।
    """
    from api.publisher_tools.models import Publisher, PublisherInvoice
    from api.publisher_tools.services import InvoiceService

    now = timezone.now()
    year  = year or now.year
    month = month or now.month
    # Previous month
    if month == 1:
        target_year  = year - 1
        target_month = 12
    else:
        target_year  = year
        target_month = month - 1

    print(f"📅 Generating invoices for {target_year}-{target_month:02d} {'(DRY RUN)' if dry_run else ''}")

    publishers = Publisher.objects.filter(status="active", is_kyc_verified=True)
    generated = 0
    skipped   = 0
    errors    = 0

    for pub in publishers:
        try:
            # Skip if invoice already exists
            exists = PublisherInvoice.objects.filter(
                publisher=pub,
                period_start__year=target_year,
                period_start__month=target_month,
            ).exists()
            if exists:
                skipped += 1
                continue

            eligibility = InvoiceService.check_payout_eligibility(pub)
            if not eligibility.get("eligible"):
                skipped += 1
                continue

            if not dry_run:
                invoice = InvoiceService.generate_monthly_invoice(pub, target_year, target_month)
                print(f"  ✅ {pub.publisher_id}: Invoice {invoice.invoice_number} — ${invoice.net_payable}")
                generated += 1
            else:
                print(f"  [DRY] {pub.publisher_id}: Would generate invoice")
                generated += 1

        except Exception as e:
            logger.error(f"Invoice generation failed [{pub.publisher_id}]: {e}")
            errors += 1

    summary = {
        "year": target_year, "month": target_month,
        "generated": generated, "skipped": skipped, "errors": errors,
        "dry_run": dry_run,
    }
    print(f"Summary: {generated} generated, {skipped} skipped, {errors} errors")
    return summary


def issue_pending_invoices():
    """Draft invoices issue করে।"""
    from api.publisher_tools.models import PublisherInvoice
    from api.publisher_tools.services import InvoiceService
    drafts = PublisherInvoice.objects.filter(status="draft")
    issued = 0
    for invoice in drafts:
        try:
            InvoiceService.issue_invoice(invoice)
            issued += 1
        except Exception as e:
            logger.error(f"Invoice issue failed [{invoice.invoice_number}]: {e}")
    print(f"✅ Issued {issued} invoices")
    return {"issued": issued}


def send_invoice_notifications():
    """Issued invoices-এর notification পাঠায়।"""
    from api.publisher_tools.models import PublisherInvoice
    from api.publisher_tools.webhooks.payment_webhook import send_invoice_issued_webhook
    issued = PublisherInvoice.objects.filter(status="issued", issued_at__isnull=False)
    sent = 0
    for invoice in issued:
        try:
            send_invoice_issued_webhook(invoice.publisher, invoice)
            sent += 1
        except Exception as e:
            logger.error(f"Invoice notification failed [{invoice.invoice_number}]: {e}")
    print(f"✅ Invoice notifications sent: {sent}")
    return {"sent": sent}


def run(year: int = None, month: int = None, dry_run: bool = False):
    print(f"🔄 Invoice generation script started at {timezone.now()}")
    return {
        "generation": generate_invoices_for_month(year, month, dry_run),
        "issued":     issue_pending_invoices() if not dry_run else {"dry_run": True},
    }

if __name__ == "__main__":
    run()
