# api/admin_panel/invoice_generator.py
"""PDF invoice generation for advertisers and publishers."""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.utils import timezone

logger = logging.getLogger(__name__)

class InvoiceGenerator:
    @classmethod
    def generate_advertiser_invoice(cls, advertiser_id: Any, period_start, period_end, actor) -> Dict:
        """Generate invoice PDF for advertiser spending."""
        try:
            from api.payment_gateways.models import GatewayTransaction
            from django.db.models import Sum
            spend = GatewayTransaction.objects.filter(
                user_id=advertiser_id,
                created_at__date__range=[period_start, period_end],
                status='COMPLETED'
            ).aggregate(total=Sum('amount'))
            total = float(spend['total'] or 0)
            invoice_data = {
                'invoice_number': f"INV-{advertiser_id}-{timezone.now().strftime('%Y%m%d')}",
                'advertiser_id': advertiser_id,
                'period': f"{period_start} to {period_end}",
                'amount': total,
                'currency': 'BDT',
                'generated_at': timezone.now().isoformat(),
                'status': 'generated',
            }
            # Try PDF generation
            pdf_path = cls._generate_pdf(invoice_data)
            invoice_data['pdf_path'] = pdf_path
            return {'success': True, 'invoice': invoice_data}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def _generate_pdf(cls, data: Dict) -> str:
        """Generate PDF using reportlab or weasyprint."""
        try:
            from reportlab.pdfgen import canvas
            import os
            from django.conf import settings
            filename = f"invoice_{data['invoice_number']}.pdf"
            path = os.path.join(settings.MEDIA_ROOT, 'invoices', filename)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            c = canvas.Canvas(path)
            c.drawString(100, 750, f"Invoice: {data['invoice_number']}")
            c.drawString(100, 720, f"Amount: {data['currency']} {data['amount']:,.2f}")
            c.drawString(100, 690, f"Period: {data['period']}")
            c.save()
            return path
        except Exception as e:
            logger.warning(f"[InvoiceGenerator] PDF failed: {e}")
            return ''

    @classmethod
    def generate_publisher_payment_slip(cls, publisher_id: Any, payout_ids: List[Any]) -> Dict:
        try:
            from api.payout_queue.models import PayoutItem
            from django.db.models import Sum
            payouts = PayoutItem.objects.filter(pk__in=payout_ids)
            total = float(payouts.aggregate(t=Sum('net_amount'))['t'] or 0)
            return {
                'success': True,
                'slip_number': f"PAY-{publisher_id}-{timezone.now().strftime('%Y%m%d%H%M')}",
                'publisher_id': publisher_id,
                'payout_count': payouts.count(),
                'total_amount': total,
                'currency': 'BDT',
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

invoice_generator = InvoiceGenerator()