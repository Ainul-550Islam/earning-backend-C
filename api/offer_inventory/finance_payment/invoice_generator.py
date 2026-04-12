# api/offer_inventory/finance_payment/invoice_generator.py
"""
Invoice Generator.
Creates PDF-ready invoice records for advertisers.
"""
import uuid
import logging
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)


class InvoiceGenerator:
    """Generate and manage advertiser invoices."""

    @staticmethod
    def generate(advertiser_id, amount: Decimal, currency: str = 'BDT',
                 due_days: int = 30, notes: str = '',
                 line_items: list = None) -> object:
        """Create an invoice record."""
        from api.offer_inventory.models import Invoice, DirectAdvertiser

        advertiser = DirectAdvertiser.objects.get(id=advertiser_id)
        inv_no     = InvoiceGenerator._generate_number()

        invoice = Invoice.objects.create(
            advertiser=advertiser,
            invoice_no=inv_no,
            amount    =amount,
            currency  =currency,
            due_at    =timezone.now() + timedelta(days=due_days),
            notes     =notes or InvoiceGenerator._default_notes(advertiser, line_items),
        )
        logger.info(f'Invoice generated: {inv_no} | amount={amount} {currency}')
        return invoice

    @staticmethod
    def mark_paid(invoice_id) -> object:
        """Mark invoice as paid."""
        from api.offer_inventory.models import Invoice
        Invoice.objects.filter(id=invoice_id).update(
            is_paid =True,
            paid_at =timezone.now(),
        )

    @staticmethod
    def get_overdue() -> list:
        """List overdue unpaid invoices."""
        from api.offer_inventory.models import Invoice
        return list(
            Invoice.objects.filter(
                is_paid=False, due_at__lt=timezone.now()
            ).select_related('advertiser')
        )

    @staticmethod
    def _generate_number() -> str:
        now = timezone.now()
        return f'INV-{now.strftime("%Y%m")}-{str(uuid.uuid4())[:6].upper()}'

    @staticmethod
    def _default_notes(advertiser, line_items: list = None) -> str:
        lines = line_items or []
        body  = f'Invoice for {advertiser.company_name}\n'
        for item in lines:
            body += f'  - {item.get("description","")}: {item.get("amount","")}\n'
        return body
