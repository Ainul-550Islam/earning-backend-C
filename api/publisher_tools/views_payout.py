# publisher_tools/views_payout.py
"""
PayoutViewSet — payment_settlement/ subfolder-এর সব floating functions
এখানে API-তে wire করা হয়েছে।

Previously floating (এখন wired):
  payment_settlement/payout_manager.py   → check_payout_eligibility,
                                            process_payout_request, get_payout_history
  payment_settlement/payment_history.py  → get_payment_history, get_payment_summary,
                                            get_lifetime_payment_stats
  payment_settlement/withholding_tax.py  → calculate_withholding_tax, get_tax_rate,
                                            is_tax_exempt

Register in urls.py:
  router.register(r'payout', PayoutViewSet, basename='payout')

Endpoints:
  GET  /api/publisher-tools/payout/eligibility/
  POST /api/publisher-tools/payout/request/
  GET  /api/publisher-tools/payout/history/
  GET  /api/publisher-tools/payout/payment-history/
  GET  /api/publisher-tools/payout/payment-summary/
  GET  /api/publisher-tools/payout/lifetime-stats/
  POST /api/publisher-tools/payout/withholding-tax/
  GET  /api/publisher-tools/payout/tax-rate/
  GET  /api/publisher-tools/payout/tax-exempt/

DRY:
  - PublisherViewMixin: self.publisher, self.handle_errors(), self.ok()
  - No local _get_publisher()
  - Decimal parsing extracted to _parse_decimal() helper (not duplicated)
"""

from decimal import Decimal, InvalidOperation
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from core.views import BaseViewSet
from .mixins import PublisherViewMixin
from .permissions import IsPublisher


class PayoutViewSet(PublisherViewMixin, BaseViewSet):
    """
    Payout API — payment_settlement/ subfolder-এর সব logic exposed।

    Inherits from PublisherViewMixin:
      - self.publisher         → cached publisher
      - self.handle_errors()   → collapses try/except boilerplate
      - self.ok(data, message) → standardised success response
    """

    permission_classes = [IsAuthenticated, IsPublisher]

    # ─────────────────────────────────────────────────────────────────────────
    # PRIVATE HELPERS  (DRY — defined once, used many times below)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_amount(raw) -> Decimal:
        """
        Parses `amount` from request.data safely।
        Raises ValueError with a clear message if invalid।
        """
        if raw is None:
            raise ValueError('amount is required.')
        try:
            val = Decimal(str(raw))
        except InvalidOperation:
            raise ValueError(f'Invalid amount: {raw!r}. Must be a decimal number.')
        if val <= 0:
            raise ValueError('amount must be greater than zero.')
        return val

    # ─────────────────────────────────────────────────────────────────────────
    # PAYOUT ELIGIBILITY
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='eligibility')
    def eligibility(self, request):
        """
        Check if publisher is eligible for payout।
        Wires: payment_settlement.payout_manager.check_payout_eligibility()

        GET (no params)

        Response:
          {
            "eligible": true,
            "balance":  123.45,
            "payment_method": "paypal",
            "threshold": 50.0
          }
        """
        pub = self.publisher
        with self.handle_errors() as guard:
            from .payment_settlement.payout_manager import check_payout_eligibility
            data = check_payout_eligibility(pub)
            return self.ok(data)
        return guard.response

    # ─────────────────────────────────────────────────────────────────────────
    # PAYOUT REQUEST
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='request')
    def request_payout(self, request):
        """
        Submit a payout request।
        Wires: payment_settlement.payout_manager.process_payout_request()

        POST body:
          {
            "amount":          123.45,
            "bank_account_id": "uuid-or-int",
            "notes":           "Optional notes"
          }

        Response on success:
          {
            "payout_id": "REQ-001",
            "amount":    123.45,
            "net_amount": 110.0
          }
        """
        pub  = self.publisher
        data = request.data

        # Validate amount using shared helper
        try:
            amount = self._parse_amount(data.get('amount'))
        except ValueError as e:
            return self.error_response(str(e), status_code=400)

        bank_account_id = data.get('bank_account_id')
        if not bank_account_id:
            return self.error_response('bank_account_id is required.', status_code=400)

        notes = data.get('notes', '')

        with self.handle_errors() as guard:
            from .payment_settlement.payout_manager import process_payout_request
            result = process_payout_request(
                publisher=pub,
                amount=amount,
                bank_account_id=bank_account_id,
                notes=notes,
            )

            if not result.get('success'):
                return self.error_response(
                    result.get('reason', 'Payout request failed.'), status_code=400
                )

            return self.ok(result, message='Payout request submitted successfully.')
        return guard.response

    # ─────────────────────────────────────────────────────────────────────────
    # PAYOUT HISTORY
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='history')
    def payout_history(self, request):
        """
        Publisher-এর payout request history।
        Wires: payment_settlement.payout_manager.get_payout_history()

        GET ?limit=20

        Response:
          {
            "limit":   20,
            "records": [{"request_id": ..., "amount": ..., "status": ...}, ...]
          }
        """
        pub = self.publisher
        try:
            limit = int(request.query_params.get('limit', 20))
        except (ValueError, TypeError):
            limit = 20

        limit = max(1, min(limit, 100))

        with self.handle_errors() as guard:
            from .payment_settlement.payout_manager import get_payout_history
            records = get_payout_history(pub, limit=limit)
            return self.ok({'limit': limit, 'count': len(records), 'records': records})
        return guard.response

    # ─────────────────────────────────────────────────────────────────────────
    # PAYMENT HISTORY
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='payment-history')
    def payment_history(self, request):
        """
        Complete payment transaction history (payouts + invoices)।
        Wires: payment_settlement.payment_history.get_payment_history()

        GET ?limit=50
        """
        pub = self.publisher
        try:
            limit = int(request.query_params.get('limit', 50))
        except (ValueError, TypeError):
            limit = 50

        limit = max(1, min(limit, 200))

        with self.handle_errors() as guard:
            from .payment_settlement.payment_history import get_payment_history
            records = get_payment_history(pub, limit=limit)
            return self.ok({'limit': limit, 'count': len(records), 'records': records})
        return guard.response

    @action(detail=False, methods=['get'], url_path='payment-summary')
    def payment_summary(self, request):
        """
        Annual payment summary।
        Wires: payment_settlement.payment_history.get_payment_summary()

        GET ?year=2025
        """
        pub = self.publisher
        try:
            from datetime import date as dt
            year = int(request.query_params.get('year', dt.today().year))
        except (ValueError, TypeError):
            return self.error_response('year must be an integer.', status_code=400)

        with self.handle_errors() as guard:
            from .payment_settlement.payment_history import get_payment_summary
            data = get_payment_summary(pub, year=year)
            return self.ok(data)
        return guard.response

    @action(detail=False, methods=['get'], url_path='lifetime-stats')
    def lifetime_stats(self, request):
        """
        Lifetime payment statistics।
        Wires: payment_settlement.payment_history.get_lifetime_payment_stats()

        GET (no params)
        """
        pub = self.publisher
        with self.handle_errors() as guard:
            from .payment_settlement.payment_history import get_lifetime_payment_stats
            data = get_lifetime_payment_stats(pub)
            return self.ok(data)
        return guard.response

    # ─────────────────────────────────────────────────────────────────────────
    # WITHHOLDING TAX
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='withholding-tax')
    def withholding_tax(self, request):
        """
        Calculate withholding tax for a given amount and country।
        Wires: payment_settlement.withholding_tax.calculate_withholding_tax()

        POST body:
          {
            "amount":  100.00,
            "country": "US",
            "has_w8":  false
          }

        Response:
          {
            "gross_amount": 100.00,
            "country":      "US",
            "tax_rate_pct": 30.0,
            "tax_amount":   30.0,
            "net_amount":   70.0,
            "has_w8_form":  false
          }
        """
        data = request.data

        try:
            amount = self._parse_amount(data.get('amount'))
        except ValueError as e:
            return self.error_response(str(e), status_code=400)

        country = data.get('country', '').strip().upper()
        if not country or len(country) != 2:
            return self.error_response(
                'country must be a 2-letter ISO 3166-1 alpha-2 code (e.g. "US", "BD").',
                status_code=400,
            )

        has_w8 = bool(data.get('has_w8', False))

        with self.handle_errors() as guard:
            from .payment_settlement.withholding_tax import calculate_withholding_tax
            result = calculate_withholding_tax(amount, country, has_w8=has_w8)
            return self.ok(result)
        return guard.response

    @action(detail=False, methods=['get'], url_path='tax-rate')
    def tax_rate(self, request):
        """
        Withholding tax rate for a given country।
        Wires: payment_settlement.withholding_tax.get_tax_rate()

        GET ?country=BD
        """
        country = request.query_params.get('country', '').strip().upper()
        if not country:
            return self.error_response('country is required.', status_code=400)

        with self.handle_errors() as guard:
            from .payment_settlement.withholding_tax import get_tax_rate, is_tax_exempt
            rate   = get_tax_rate(country)
            exempt = is_tax_exempt(country)
            return self.ok({
                'country':    country,
                'rate_pct':   float(rate),
                'is_exempt':  exempt,
            })
        return guard.response

    @action(detail=False, methods=['get'], url_path='tax-exempt')
    def tax_exempt_countries(self, request):
        """
        List of tax-exempt countries (rate = 0%)।
        Wires: payment_settlement.withholding_tax.WITHHOLDING_TAX_RATES

        GET (no params)
        """
        with self.handle_errors() as guard:
            from .payment_settlement.withholding_tax import WITHHOLDING_TAX_RATES
            from decimal import Decimal as D
            exempt = [
                c for c, rate in WITHHOLDING_TAX_RATES.items()
                if rate == D('0.00') and c != 'DEFAULT'
            ]
            all_rates = {
                c: float(r) for c, r in WITHHOLDING_TAX_RATES.items()
                if c != 'DEFAULT'
            }
            return self.ok({'exempt_countries': exempt, 'all_rates': all_rates})
        return guard.response
