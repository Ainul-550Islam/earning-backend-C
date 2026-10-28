# publisher_tools/views_payment_advanced.py
"""
FILE 3 of 10 — Payment Settlement Advanced API
===============================================
payment_settlement/ remaining 14 floating functions exposed.

Previously floating (now wired):
  get_next_payment_date, get_publishers_due_for_payment,
  schedule_batch_payments, calculate_fee, validate_payment_details,
  get_minimum_threshold, calculate_platform_share,
  calculate_tiered_commission, calculate_referral_commission,
  is_overdue, age_days, generate_payment_receipt, generate_receipt_html

Register in urls.py:
  router.register(r'payment-advanced', PaymentAdvancedViewSet, basename='payment-adv')
"""
from decimal import Decimal, InvalidOperation
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher, IsAdminOrPublisher
from .models import PublisherInvoice


class PaymentAdvancedViewSet(BaseViewSet):
    """
    Payment Settlement Advanced API.

    Schedule:
      GET  /payment-advanced/next-date/              — next payment date
      GET  /payment-advanced/due-publishers/          — publishers due (admin)
      POST /payment-advanced/schedule-batch/          — schedule batch payout (admin)

    Fee calculation:
      GET  /payment-advanced/fee-calc/               — calculate transaction fee
      GET  /payment-advanced/min-threshold/          — minimum payout threshold
      GET  /payment-advanced/platform-share/         — platform revenue share
      GET  /payment-advanced/tiered-commission/      — tiered commission calculation
      GET  /payment-advanced/referral-commission/    — referral commission calculation

    Dispute resolution:
      GET  /payment-advanced/disputes/               — active disputes
      GET  /payment-advanced/dispute-detail/         — dispute age & overdue status

    Receipts:
      GET  /payment-advanced/receipt/{pk}/           — payment receipt data
      GET  /payment-advanced/receipt-html/{pk}/      — receipt HTML render
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    # ── PAYMENT SCHEDULE ───────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='next-date')
    def next_date(self, request):
        """Next scheduled payment date।"""
        publisher = self._get_publisher()
        try:
            from .payment_settlement.payment_schedule import get_next_payment_date
            result = get_next_payment_date(publisher)
            return self.success_response(data=result if isinstance(result, dict)
                                          else {'next_payment_date': str(result)})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(
        detail=False, methods=['get'], url_path='due-publishers',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def due_publishers(self, request):
        """[Admin] Publishers currently due for payment।"""
        try:
            from .payment_settlement.payment_schedule import get_publishers_due_for_payment
            publishers = get_publishers_due_for_payment()
            return self.success_response(data={
                'publishers': publishers,
                'count':      len(publishers),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(
        detail=False, methods=['post'], url_path='schedule-batch',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def schedule_batch(self, request):
        """
        [Admin] Batch payout schedule করে।
        POST body: { "publisher_ids": ["PUB-001", "PUB-002"] }
        """
        publisher_ids = request.data.get('publisher_ids', [])
        if not publisher_ids:
            return self.error_response('publisher_ids required.', status_code=400)
        try:
            from .payment_settlement.payment_schedule import schedule_batch_payments
            result = schedule_batch_payments(publisher_ids)
            return self.success_response(data=result)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── FEE CALCULATION ────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='fee-calc')
    def fee_calc(self, request):
        """
        Transaction fee calculation।
        GET ?amount=100.00&method=paypal | bank_transfer | payoneer
        """
        amount_str = request.query_params.get('amount', '100.00')
        method     = request.query_params.get('method', 'paypal')
        try:
            amount = Decimal(amount_str)
        except InvalidOperation:
            return self.error_response('Invalid amount.', status_code=400)
        try:
            from .payment_settlement.payment_method import calculate_fee
            fee    = calculate_fee(amount, method)
            net    = amount - fee
            return self.success_response(data={
                'amount':          str(amount),
                'method':          method,
                'fee':             str(fee),
                'net_amount':      str(net),
                'fee_percentage':  str(round(fee / amount * 100, 4)) if amount else '0',
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='min-threshold')
    def min_threshold(self, request):
        """
        Minimum payout threshold by payment method।
        GET ?method=paypal | bank_transfer | payoneer
        """
        method = request.query_params.get('method', 'paypal')
        try:
            from .payment_settlement.payment_method import get_minimum_threshold
            threshold = get_minimum_threshold(method)
            return self.success_response(data={
                'method':    method,
                'threshold': str(threshold),
                'currency':  'USD',
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='validate-payment-details')
    def validate_payment_details(self, request):
        """
        Payment method details validate করে।
        POST body: { "method": "paypal", "details": { "email": "user@example.com" } }
        """
        method  = request.data.get('method', '')
        details = request.data.get('details', {})
        if not method:
            return self.error_response('method required.', status_code=400)
        try:
            from .payment_settlement.payment_method import validate_payment_details
            result = validate_payment_details(method, details)
            return self.success_response(data=result if isinstance(result, dict)
                                          else {'valid': bool(result)})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── COMMISSION CALCULATION ─────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='platform-share')
    def platform_share(self, request):
        """
        Platform revenue share calculation।
        GET ?gross_revenue=1000.00
        """
        publisher = self._get_publisher()
        gross_str = request.query_params.get('gross_revenue', '1000.00')
        try:
            gross = Decimal(gross_str)
        except InvalidOperation:
            return self.error_response('Invalid gross_revenue.', status_code=400)
        try:
            from .payment_settlement.commission_calculator import calculate_platform_share
            result = calculate_platform_share(publisher, gross)
            return self.success_response(data=result if isinstance(result, dict) else {
                'gross_revenue':    str(gross),
                'platform_share':   str(result),
                'publisher_share':  str(gross - Decimal(str(result))),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='tiered-commission')
    def tiered_commission(self, request):
        """
        Tiered commission breakdown।
        GET ?gross_revenue=5000.00
        """
        publisher = self._get_publisher()
        gross_str = request.query_params.get('gross_revenue', '1000.00')
        try:
            gross = Decimal(gross_str)
        except InvalidOperation:
            return self.error_response('Invalid gross_revenue.', status_code=400)
        try:
            from .payment_settlement.commission_calculator import calculate_tiered_commission
            result = calculate_tiered_commission(publisher, float(gross))
            return self.success_response(data=result if isinstance(result, dict) else {
                'gross': str(gross), 'commission': str(result)
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='referral-commission')
    def referral_commission(self, request):
        """
        Referral commission calculation।
        GET ?referred_revenue=2000.00
        """
        publisher  = self._get_publisher()
        rev_str    = request.query_params.get('referred_revenue', '1000.00')
        try:
            referred_rev = Decimal(rev_str)
        except InvalidOperation:
            return self.error_response('Invalid referred_revenue.', status_code=400)
        try:
            from .payment_settlement.commission_calculator import calculate_referral_commission
            result = calculate_referral_commission(publisher, float(referred_rev))
            return self.success_response(data=result if isinstance(result, dict) else {
                'referred_revenue':   str(referred_rev),
                'referral_commission': str(result),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── DISPUTE RESOLUTION ─────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='disputes')
    def disputes(self, request):
        """Active disputes।"""
        publisher = self._get_publisher()
        try:
            from .payment_settlement.dispute_resolution import PaymentDispute
            disputes = PaymentDispute.objects.filter(
                publisher=publisher
            ).order_by('-created_at')[:50]
            return self.success_response(data={
                'disputes': [
                    {
                        'pk':          d.pk,
                        'status':      getattr(d, 'status', ''),
                        'amount':      str(getattr(d, 'disputed_amount', 0)),
                        'is_overdue':  d.is_overdue() if hasattr(d, 'is_overdue') else False,
                        'age_days':    d.age_days()   if hasattr(d, 'age_days')   else 0,
                        'created_at':  str(d.created_at),
                    }
                    for d in disputes
                ],
                'count': disputes.count(),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── RECEIPTS ───────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='receipt/(?P<invoice_pk>[0-9]+)')
    def receipt(self, request, invoice_pk=None):
        """Payment receipt data।"""
        publisher = self._get_publisher()
        try:
            invoice = PublisherInvoice.objects.get(pk=invoice_pk, publisher=publisher)
            from .payment_settlement.receipt_generator import generate_payment_receipt
            data = generate_payment_receipt(invoice)
            return self.success_response(data=data)
        except PublisherInvoice.DoesNotExist:
            return self.error_response('Invoice not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='receipt-html/(?P<invoice_pk>[0-9]+)')
    def receipt_html(self, request, invoice_pk=None):
        """Payment receipt HTML render।"""
        publisher = self._get_publisher()
        try:
            invoice = PublisherInvoice.objects.get(pk=invoice_pk, publisher=publisher)
            from .payment_settlement.receipt_generator import generate_receipt_html
            html = generate_receipt_html(invoice)
            from django.http import HttpResponse
            return HttpResponse(html, content_type='text/html')
        except PublisherInvoice.DoesNotExist:
            return self.error_response('Invoice not found.', status_code=404)
        except Exception as e:
            return self.error_response(str(e), status_code=503)
