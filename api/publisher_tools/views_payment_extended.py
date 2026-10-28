# publisher_tools/views_payment_extended.py
"""
FILE 5 of 10 — Payment Settlement Extended API
===============================================
payment_settlement/ subfolder-এর 6টি floating function expose করা হয়েছে।

Previously floating (now wired):
  calculate_daily_earnings, check_threshold_reached/check_threshold_met,
  convert_currency, build_invoice_data, generate_invoice_html,
  get_eligible_publishers

Register in urls.py:
  router.register(r'payments-extended', PaymentExtendedViewSet, basename='payment-ext')
"""
import datetime
from decimal import Decimal, InvalidOperation
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher, IsAdminOrPublisher
from .models import PublisherInvoice


class PaymentExtendedViewSet(BaseViewSet):
    """
    Payment Extended API — payment_settlement/ subfolder-এর
    সব floating functions expose করে।

    Publisher endpoints:
      GET  /payments-extended/daily-earnings/       — daily earnings breakdown
      GET  /payments-extended/threshold-status/     — payout threshold check
      GET  /payments-extended/all-thresholds/       — all payment method thresholds
      GET  /payments-extended/currency-convert/     — currency conversion
      GET  /payments-extended/invoice-data/{pk}/    — invoice structured data
      GET  /payments-extended/invoice-html/{pk}/    — invoice HTML render

    Admin endpoints:
      GET  /payments-extended/eligible-publishers/  — publishers ready for payout
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    # ── DAILY EARNINGS ─────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='daily-earnings')
    def daily_earnings(self, request):
        """
        নির্দিষ্ট দিনের earnings breakdown।
        GET /payments-extended/daily-earnings/?date=2025-06-01
        অথবা ?year=2025&month=6&day=1
        """
        publisher = self._get_publisher()
        # Parse date from query params
        date_str = request.query_params.get('date')
        if date_str:
            try:
                report_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                return self.error_response(
                    'Invalid date format. Use YYYY-MM-DD.', status_code=400
                )
        else:
            today = datetime.date.today()
            try:
                year  = int(request.query_params.get('year',  today.year))
                month = int(request.query_params.get('month', today.month))
                day   = int(request.query_params.get('day',   today.day))
                report_date = datetime.date(year, month, day)
            except (ValueError, TypeError):
                return self.error_response('Invalid date parameters.', status_code=400)
        try:
            from .payment_settlement.earnings_calculator import calculate_daily_earnings
            data = calculate_daily_earnings(publisher, report_date)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── THRESHOLD STATUS ───────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='threshold-status')
    def threshold_status(self, request):
        """
        Publisher-এর payout threshold পূরণ হয়েছে কিনা।
        GET ?payment_method=paypal | bank_transfer | payoneer
        """
        publisher      = self._get_publisher()
        payment_method = request.query_params.get('payment_method')
        try:
            from .payment_settlement.threshold_manager import check_threshold_met
            result = check_threshold_met(publisher, payment_method=payment_method)
            return self.success_response(data=result)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='all-thresholds')
    def all_thresholds(self, request):
        """
        Publisher-এর সব payment method-এর threshold list।
        """
        publisher = self._get_publisher()
        try:
            from .payment_settlement.threshold_manager import get_all_thresholds
            thresholds = get_all_thresholds(publisher)
            return self.success_response(data={'thresholds': thresholds})
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── CURRENCY CONVERSION ────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='currency-convert')
    def currency_convert(self, request):
        """
        Currency conversion with live exchange rate।
        GET ?amount=100.00&from=USD&to=EUR
        """
        amount_str    = request.query_params.get('amount', '1.00')
        from_currency = (request.query_params.get('from') or 'USD').upper()
        to_currency   = (request.query_params.get('to')   or 'USD').upper()
        try:
            amount = Decimal(amount_str)
            if amount < 0:
                return self.error_response('amount must be ≥ 0.', status_code=400)
        except InvalidOperation:
            return self.error_response('Invalid amount.', status_code=400)
        if from_currency == to_currency:
            return self.success_response(data={
                'original_amount': str(amount),
                'converted_amount': str(amount),
                'from_currency':   from_currency,
                'to_currency':     to_currency,
                'exchange_rate':   '1.000000',
            })
        try:
            from .payment_settlement.currency_converter import convert, get_exchange_rate, format_amount
            rate   = get_exchange_rate(from_currency, to_currency)
            result = convert(amount, from_currency, to_currency)
            return self.success_response(data={
                'original_amount':  str(amount),
                'original_display': format_amount(amount, from_currency),
                'converted_amount': str(result.get('converted', amount * rate)),
                'converted_display': format_amount(
                    result.get('converted', amount * rate), to_currency
                ),
                'from_currency':   from_currency,
                'to_currency':     to_currency,
                'exchange_rate':   str(rate),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='exchange-rates')
    def exchange_rates(self, request):
        """
        Common currencies-এর USD exchange rates।
        GET ?base=USD (default)
        """
        base       = (request.query_params.get('base') or 'USD').upper()
        currencies = ['USD', 'EUR', 'GBP', 'BDT', 'INR', 'AUD', 'CAD',
                      'JPY', 'SGD', 'AED', 'PKR', 'NGN']
        rates = {}
        try:
            from .payment_settlement.currency_converter import get_exchange_rate
            for cur in currencies:
                if cur == base:
                    rates[cur] = '1.000000'
                    continue
                try:
                    rates[cur] = str(get_exchange_rate(base, cur))
                except Exception:
                    rates[cur] = None
        except Exception as e:
            return self.error_response(str(e), status_code=503)
        return self.success_response(data={'base': base, 'rates': rates})

    # ── INVOICE DATA ───────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='invoice-data/(?P<invoice_pk>[0-9]+)')
    def invoice_data(self, request, invoice_pk=None):
        """
        Invoice-এর structured data — PDF generation বা preview-এর জন্য।
        GET /payments-extended/invoice-data/42/
        """
        publisher = self._get_publisher()
        try:
            invoice = PublisherInvoice.objects.get(
                pk=invoice_pk, publisher=publisher
            )
        except PublisherInvoice.DoesNotExist:
            return self.error_response('Invoice not found.', status_code=404)
        try:
            from .payment_settlement.invoice_generator import build_invoice_data
            data = build_invoice_data(invoice)
            return self.success_response(data=data)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='invoice-html/(?P<invoice_pk>[0-9]+)')
    def invoice_html(self, request, invoice_pk=None):
        """
        Invoice-এর HTML render — browser preview বা PDF conversion-এর জন্য।
        GET /payments-extended/invoice-html/42/
        """
        publisher = self._get_publisher()
        try:
            invoice = PublisherInvoice.objects.get(
                pk=invoice_pk, publisher=publisher
            )
        except PublisherInvoice.DoesNotExist:
            return self.error_response('Invoice not found.', status_code=404)
        try:
            from .payment_settlement.invoice_generator import generate_invoice_html
            html = generate_invoice_html(invoice)
            from django.http import HttpResponse
            return HttpResponse(html, content_type='text/html')
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── ADMIN: ELIGIBLE PUBLISHERS ─────────────────────────────────────────────

    @action(
        detail=False, methods=['get'], url_path='eligible-publishers',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def eligible_publishers(self, request):
        """
        [Admin] Payout threshold পূরণ করেছে এমন publishers।
        GET ?payment_method=paypal | bank_transfer
        """
        payment_method = request.query_params.get('payment_method')
        try:
            from .payment_settlement.threshold_manager import get_all_thresholds
            from .models import Publisher
            eligible = []
            queryset = Publisher.objects.filter(status='active').select_related()
            for pub in queryset:
                try:
                    from .payment_settlement.threshold_manager import check_threshold_met
                    result = check_threshold_met(pub, payment_method=payment_method)
                    if result.get('threshold_met'):
                        eligible.append({
                            'publisher_id':   pub.publisher_id,
                            'name':           pub.business_name or pub.user.get_full_name(),
                            'payable_amount': str(result.get('payable_amount', 0)),
                            'payment_method': result.get('payment_method'),
                        })
                except Exception:
                    continue
            return self.success_response(data={
                'eligible_publishers': eligible,
                'count':               len(eligible),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)
