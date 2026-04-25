# api/payment_gateways/invoice_pdf.py
# PDF invoice generation for advertisers and publishers
from django.utils import timezone
import logging
logger = logging.getLogger(__name__)

class InvoiceGenerator:
    def generate_deposit_invoice(self, deposit, fmt='html'):
        from api.payment_gateways.services.ReceiptGenerator import ReceiptGenerator
        return ReceiptGenerator().generate_deposit_receipt(deposit, fmt=fmt)
    def generate_payout_invoice(self, payout, fmt='html'):
        from api.payment_gateways.services.ReceiptGenerator import ReceiptGenerator
        return ReceiptGenerator().generate_withdrawal_receipt(payout, fmt=fmt)
    def generate_advertiser_invoice(self, advertiser, period):
        from api.payment_gateways.tracking.models import Conversion
        from django.db.models import Sum, Count
        year, month = map(int, period.split('-'))
        from datetime import datetime
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        import calendar
        end = datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59, tzinfo=timezone.utc)
        agg = Conversion.objects.filter(advertiser=advertiser, status='approved', created_at__range=(start,end)).aggregate(spend=Sum('cost'), count=Count('id'))
        return {'invoice_number':f'INV-ADV-{advertiser.id}-{period}','period':period,'advertiser':advertiser.email,'total_spend':float(agg['spend'] or 0),'total_conversions':agg['count'] or 0,'issued_at':timezone.now().isoformat(),'status':'paid'}
    def generate_publisher_statement(self, publisher, month, year):
        from api.payment_gateways.services.ReceiptGenerator import ReceiptGenerator
        from datetime import date
        return ReceiptGenerator().generate_statement(publisher, date(year,month,1), date(year,month,28))
invoice_generator = InvoiceGenerator()
