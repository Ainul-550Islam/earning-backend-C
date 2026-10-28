# publisher_tools/views_payment.py
# Exposes payment_settlement/ subfolder logic via DRF.
# Register: router.register(r'payments', PaymentViewSet, basename='payment')

from decimal import Decimal
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher


class PaymentViewSet(BaseViewSet):
    """
    Payment & Settlement API.
    payment_settlement/ subfolder-এর সব logic expose করা হয়েছে।

    Publisher endpoints:
      GET  /payments/earnings/           — monthly earnings calculation
      GET  /payments/invoice-preview/    — invoice preview before generation
      GET  /payments/tax-estimate/       — withholding tax estimate
      GET  /payments/payout-history/     — payout history
      GET  /payments/commission/         — platform commission breakdown
      POST /payments/request-payout/     — manual payout request
      GET  /payments/disputes/           — open disputes
      POST /payments/create-dispute/     — create payment dispute

    Admin endpoints:
      POST /payments/apply-adjustment/   — revenue adjustment
      POST /payments/resolve-dispute/    — resolve dispute
      GET  /payments/currency-rates/     — exchange rates
      GET  /payments/threshold-check/    — eligibility check for all publishers
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def _get_publisher(self):
        try:
            return self.request.user.publisher_profile
        except Exception:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No active publisher profile.')

    # ── PUBLISHER: Monthly Earnings ───────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='earnings')
    def earnings(self, request):
        """
        Monthly earnings calculation।
        GET /payments/earnings/?year=2025&month=1
        """
        publisher = self._get_publisher()
        import datetime
        now   = datetime.date.today()
        year  = int(request.query_params.get('year', now.year))
        month = int(request.query_params.get('month', now.month))

        try:
            from .payment_settlement import calculate_monthly_earnings
            data = calculate_monthly_earnings(publisher, year, month)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=data)

    # ── PUBLISHER: Invoice Preview ────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='invoice-preview')
    def invoice_preview(self, request):
        """
        Invoice preview before official generation।
        GET /payments/invoice-preview/?year=2025&month=1
        """
        publisher = self._get_publisher()
        import datetime
        now   = datetime.date.today()
        year  = int(request.query_params.get('year', now.year))
        month = int(request.query_params.get('month', now.month))

        try:
            from .payment_settlement import calculate_monthly_earnings, calculate_invoice_summary, calculate_withholding_tax
            earnings = calculate_monthly_earnings(publisher, year, month)
            gross    = Decimal(str(earnings.get('gross_revenue', 0)))
            net      = Decimal(str(earnings.get('publisher_revenue', 0)))
            tax_info = calculate_withholding_tax(net, publisher.country or 'US')
            summary  = calculate_invoice_summary(gross, net, tax_info.get('tax_amount', Decimal('0')))
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'year':    year,
            'month':   month,
            'preview': summary,
            'tax':     tax_info,
        })

    # ── PUBLISHER: Tax Estimate ───────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='tax-estimate')
    def tax_estimate(self, request):
        """
        Withholding tax estimate।
        GET /payments/tax-estimate/?amount=1000&country=BD
        """
        amount_str = request.query_params.get('amount', '0')
        country    = request.query_params.get('country') or self._get_publisher().country or 'US'
        has_w8     = request.query_params.get('has_w8', 'false').lower() == 'true'

        try:
            amount = Decimal(amount_str)
        except Exception:
            return self.error_response('Invalid amount.', status_code=400)

        try:
            from .payment_settlement import calculate_withholding_tax, get_tax_rate, is_tax_exempt
            tax_info  = calculate_withholding_tax(amount, country, has_w8)
            rate      = get_tax_rate(country)
            exempt    = is_tax_exempt(country, has_w8)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'amount':     float(amount),
            'country':    country,
            'rate_pct':   float(rate * 100),
            'is_exempt':  exempt,
            'tax_amount': tax_info,
        })

    # ── PUBLISHER: Payout History ─────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='payout-history')
    def payout_history(self, request):
        """
        Paid invoices / payout history।
        GET /payments/payout-history/?limit=20
        """
        publisher = self._get_publisher()
        limit     = int(request.query_params.get('limit', 20))

        from .models import PublisherInvoice
        from .serializers import PublisherInvoiceListSerializer
        invoices = PublisherInvoice.objects.filter(
            publisher=publisher,
            status='paid',
        ).order_by('-paid_at')[:limit]

        return self.success_response(data=PublisherInvoiceListSerializer(invoices, many=True).data)

    # ── PUBLISHER: Commission Breakdown ───────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='commission')
    def commission(self, request):
        """
        Platform commission breakdown।
        GET /payments/commission/?amount=1000
        """
        publisher  = self._get_publisher()
        amount_str = request.query_params.get('amount', '0')
        try:
            amount = Decimal(amount_str)
        except Exception:
            return self.error_response('Invalid amount.', status_code=400)

        try:
            from .payment_settlement import calculate_platform_commission, calculate_publisher_share
            commission    = calculate_platform_commission(amount, publisher.revenue_share_percentage)
            pub_share     = calculate_publisher_share(amount, publisher.revenue_share_percentage)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={
            'gross_amount':          float(amount),
            'revenue_share_pct':     float(publisher.revenue_share_percentage),
            'platform_commission':   commission,
            'publisher_share':       pub_share,
        })

    # ── PUBLISHER: Request Payout ─────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='request-payout')
    def request_payout(self, request):
        """
        Manual payout request।
        POST /payments/request-payout/
        Body: {"threshold_id": "<pk>"}
        """
        publisher    = self._get_publisher()
        threshold_id = request.data.get('threshold_id')

        if not threshold_id:
            return self.error_response('threshold_id is required.', status_code=400)

        from .models import PayoutThreshold
        threshold = PayoutThreshold.objects.filter(
            id=threshold_id, publisher=publisher
        ).first()
        if not threshold:
            return self.error_response('Threshold not found.', status_code=404)

        try:
            from .payment_settlement import process_payout_request, calculate_payable_amount
            payable = calculate_payable_amount(publisher)
            result  = process_payout_request(publisher, threshold, payable)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data=result, message='Payout request submitted.')

    # ── PUBLISHER: Disputes ───────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='disputes')
    def disputes(self, request):
        """
        Publisher-এর open disputes।
        GET /payments/disputes/
        """
        publisher = self._get_publisher()

        try:
            from .payment_settlement import get_open_disputes
            data = get_open_disputes(publisher)
        except (ImportError, Exception):
            from .models import PublisherInvoice
            disputed = PublisherInvoice.objects.filter(
                publisher=publisher, status='disputed'
            ).values('id', 'invoice_number', 'payable_amount', 'publisher_notes', 'updated_at')
            data = list(disputed)

        return self.success_response(data=data)

    # ── PUBLISHER: Create Dispute ─────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='create-dispute')
    def create_dispute(self, request):
        """
        Create a payment dispute।
        POST /payments/create-dispute/
        Body: {"invoice_id": "<pk>", "reason": "..."}
        """
        publisher  = self._get_publisher()
        invoice_id = request.data.get('invoice_id')
        reason     = request.data.get('reason', '')

        if not invoice_id or not reason:
            return self.error_response('invoice_id and reason are required.', status_code=400)

        from .models import PublisherInvoice
        invoice = PublisherInvoice.objects.filter(
            id=invoice_id, publisher=publisher, status='issued'
        ).first()
        if not invoice:
            return self.error_response('Invoice not found or not in issued status.', status_code=404)

        try:
            from .payment_settlement import create_payment_dispute
            data = create_payment_dispute(invoice, reason)
        except (ImportError, Exception):
            invoice.status          = 'disputed'
            invoice.publisher_notes = reason
            invoice.save(update_fields=['status', 'publisher_notes', 'updated_at'])
            data = {'invoice_id': str(invoice_id), 'status': 'disputed'}

        return self.success_response(data=data, message='Dispute created.')

    # ── ADMIN: Apply Adjustment ───────────────────────────────────────────────

    @action(
        detail=False, methods=['post'], url_path='apply-adjustment',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def apply_adjustment(self, request):
        """
        Revenue adjustment (admin only)।
        POST /payments/apply-adjustment/
        Body: {"publisher_id": "PUB...", "amount": "-50.00", "reason": "IVT deduction"}
        """
        pub_id = request.data.get('publisher_id')
        amount = request.data.get('amount')
        reason = request.data.get('reason', '')

        if not pub_id or amount is None or not reason:
            return self.error_response('publisher_id, amount, reason required.', status_code=400)

        from .models import Publisher
        try:
            publisher = Publisher.objects.get(publisher_id=pub_id)
        except Publisher.DoesNotExist:
            return self.error_response(f'Publisher {pub_id} not found.', status_code=404)

        try:
            from .payment_settlement import apply_revenue_adjustment
            apply_revenue_adjustment(publisher, Decimal(str(amount)), reason, adjusted_by=request.user)
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(
            data={'publisher_id': pub_id, 'adjustment': amount, 'reason': reason},
            message='Adjustment applied.',
        )

    # ── ADMIN: Resolve Dispute ────────────────────────────────────────────────

    @action(
        detail=False, methods=['post'], url_path='resolve-dispute',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def resolve_dispute(self, request):
        """
        Resolve a payment dispute (admin only)。
        POST /payments/resolve-dispute/
        Body: {"invoice_id": "<pk>", "resolution": "accepted|rejected", "notes": "..."}
        """
        invoice_id  = request.data.get('invoice_id')
        resolution  = request.data.get('resolution')
        notes       = request.data.get('notes', '')

        if not invoice_id or resolution not in ('accepted', 'rejected'):
            return self.error_response('invoice_id and resolution (accepted|rejected) required.', status_code=400)

        from .models import PublisherInvoice
        invoice = PublisherInvoice.objects.filter(id=invoice_id, status='disputed').first()
        if not invoice:
            return self.error_response('Disputed invoice not found.', status_code=404)

        try:
            from .payment_settlement import resolve_payment_dispute
            data = resolve_payment_dispute(invoice, resolution, notes, resolved_by=request.user)
        except (ImportError, Exception):
            new_status = 'issued' if resolution == 'rejected' else 'paid'
            invoice.status      = new_status
            invoice.admin_notes = notes
            invoice.save(update_fields=['status', 'admin_notes', 'updated_at'])
            data = {'invoice_id': str(invoice_id), 'resolution': resolution, 'new_status': new_status}

        return self.success_response(data=data, message='Dispute resolved.')

    # ── ADMIN: Currency Rates ─────────────────────────────────────────────────

    @action(
        detail=False, methods=['get'], url_path='currency-rates',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def currency_rates(self, request):
        """
        Current exchange rates (admin only)。
        GET /payments/currency-rates/
        """
        try:
            from .payment_settlement import get_exchange_rate
            currencies = ['BDT', 'EUR', 'GBP', 'INR', 'CAD', 'AUD', 'JPY', 'SGD']
            rates      = {c: float(get_exchange_rate('USD', c)) for c in currencies}
        except (ImportError, Exception) as e:
            return self.error_response(str(e), status_code=503)

        return self.success_response(data={'base': 'USD', 'rates': rates})
