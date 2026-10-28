# api/djoyalty/tests/test_dry_refactoring.py
"""
DRY Refactoring Tests — Full Coverage।

Verifies that every new DRY abstraction:
  a) works correctly in isolation
  b) eliminates the pattern it was designed to replace
  c) is backward-compatible with existing callers

Section A: ServiceResult (12 tests)
Section B: DjoyaltyResponse (14 tests)
Section C: DjoyaltyBaseViewSet — customer helpers (10 tests)
Section D: DjoyaltyBaseViewSet — response helpers (8 tests)
Section E: DjoyaltyBaseService (10 tests)
Section F: Integration — CashoutService uses ServiceResult (6 tests)
Section G: Integration — Viewsets use DjoyaltyBaseViewSet (8 tests)
"""
import os
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock
from django.test import TestCase, RequestFactory
from rest_framework import status


# ══════════════════════════════════════════════════════════════════════════════
# SECTION A — ServiceResult
# ══════════════════════════════════════════════════════════════════════════════

class TestServiceResult(TestCase):

    def test_ok_sets_success_true(self):
        from api.djoyalty.service_result import ServiceResult
        result = ServiceResult.ok()
        self.assertTrue(result['success'])

    def test_ok_includes_kwargs(self):
        from api.djoyalty.service_result import ServiceResult
        result = ServiceResult.ok(cashout_id=42, reference='CO-001')
        self.assertTrue(result['success'])
        self.assertEqual(result['cashout_id'], 42)
        self.assertEqual(result['reference'], 'CO-001')

    def test_err_sets_success_false(self):
        from api.djoyalty.service_result import ServiceResult
        result = ServiceResult.err('Something failed.')
        self.assertFalse(result['success'])

    def test_err_sets_error_message(self):
        from api.djoyalty.service_result import ServiceResult
        result = ServiceResult.err('Insufficient balance.')
        self.assertEqual(result['error'], 'Insufficient balance.')

    def test_err_sets_code_when_provided(self):
        from api.djoyalty.service_result import ServiceResult
        result = ServiceResult.err('Rate not found.', code='NO_RATE')
        self.assertEqual(result['code'], 'NO_RATE')

    def test_err_no_code_key_when_omitted(self):
        from api.djoyalty.service_result import ServiceResult
        result = ServiceResult.err('Plain error.')
        self.assertNotIn('code', result)

    def test_is_ok_true_for_success(self):
        from api.djoyalty.service_result import ServiceResult
        self.assertTrue(ServiceResult.is_ok({'success': True}))

    def test_is_ok_false_for_failure(self):
        from api.djoyalty.service_result import ServiceResult
        self.assertFalse(ServiceResult.is_ok({'success': False, 'error': 'x'}))

    def test_is_err_is_inverse_of_is_ok(self):
        from api.djoyalty.service_result import ServiceResult
        ok_result  = ServiceResult.ok()
        err_result = ServiceResult.err('x')
        self.assertFalse(ServiceResult.is_err(ok_result))
        self.assertTrue(ServiceResult.is_err(err_result))

    def test_error_message_extracts_message(self):
        from api.djoyalty.service_result import ServiceResult
        result = ServiceResult.err('Duplicate pending cashout.')
        self.assertEqual(ServiceResult.error_message(result), 'Duplicate pending cashout.')

    def test_from_exception_converts_exception(self):
        from api.djoyalty.service_result import ServiceResult
        exc    = ValueError('DB constraint violated')
        result = ServiceResult.from_exception(exc, code='DB_ERROR')
        self.assertFalse(result['success'])
        self.assertIn('DB constraint violated', result['error'])
        self.assertEqual(result['code'], 'DB_ERROR')

    def test_skipped_sets_success_true_and_skipped_true(self):
        from api.djoyalty.service_result import ServiceResult
        result = ServiceResult.skipped('Already processed.')
        self.assertTrue(result['success'])
        self.assertTrue(result['skipped'])
        self.assertEqual(result['reason'], 'Already processed.')

    def test_paginated_returns_correct_structure(self):
        from api.djoyalty.service_result import ServiceResult
        result = ServiceResult.paginated(['a', 'b', 'c'], total=23, page=2, page_size=10)
        self.assertTrue(result['success'])
        self.assertEqual(result['total'], 23)
        self.assertEqual(result['page'], 2)
        self.assertEqual(result['total_pages'], 3)
        self.assertTrue(result['has_next'])
        self.assertTrue(result['has_prev'])


# ══════════════════════════════════════════════════════════════════════════════
# SECTION B — DjoyaltyResponse
# ══════════════════════════════════════════════════════════════════════════════

class TestDjoyaltyResponse(TestCase):

    def test_ok_returns_200(self):
        from api.djoyalty.response_helpers import DjoyaltyResponse
        resp = DjoyaltyResponse.ok({'balance': 500})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['balance'], 500)

    def test_created_returns_201(self):
        from api.djoyalty.response_helpers import DjoyaltyResponse
        resp = DjoyaltyResponse.created({'id': 1})
        self.assertEqual(resp.status_code, 201)

    def test_err_returns_400_by_default(self):
        from api.djoyalty.response_helpers import DjoyaltyResponse
        resp = DjoyaltyResponse.err('Bad input.')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['error'], 'Bad input.')

    def test_err_with_custom_status(self):
        from api.djoyalty.response_helpers import DjoyaltyResponse
        resp = DjoyaltyResponse.err('Server error.', http_status=500)
        self.assertEqual(resp.status_code, 500)

    def test_err_with_code(self):
        from api.djoyalty.response_helpers import DjoyaltyResponse
        resp = DjoyaltyResponse.err('Rate not found.', code='NO_RATE')
        self.assertEqual(resp.data['code'], 'NO_RATE')

    def test_not_found_returns_404(self):
        from api.djoyalty.response_helpers import DjoyaltyResponse
        resp = DjoyaltyResponse.not_found()
        self.assertEqual(resp.status_code, 404)

    def test_forbidden_returns_403(self):
        from api.djoyalty.response_helpers import DjoyaltyResponse
        resp = DjoyaltyResponse.forbidden()
        self.assertEqual(resp.status_code, 403)

    def test_customer_not_found_is_404_with_message(self):
        from api.djoyalty.response_helpers import DjoyaltyResponse
        resp = DjoyaltyResponse.customer_not_found()
        self.assertEqual(resp.status_code, 404)
        self.assertIn('Customer', resp.data['error'])

    def test_customer_required_is_400_with_message(self):
        from api.djoyalty.response_helpers import DjoyaltyResponse
        resp = DjoyaltyResponse.customer_required()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('customer_id', resp.data['error'])

    def test_from_service_ok_returns_200(self):
        from api.djoyalty.response_helpers import DjoyaltyResponse
        from api.djoyalty.service_result import ServiceResult
        result = ServiceResult.ok(balance=500, tier='gold')
        resp   = DjoyaltyResponse.from_service(result)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['success'])

    def test_from_service_err_returns_400(self):
        from api.djoyalty.response_helpers import DjoyaltyResponse
        from api.djoyalty.service_result import ServiceResult
        result = ServiceResult.err('Insufficient balance.')
        resp   = DjoyaltyResponse.from_service(result)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Insufficient', resp.data['error'])

    def test_from_service_err_includes_code(self):
        from api.djoyalty.response_helpers import DjoyaltyResponse
        from api.djoyalty.service_result import ServiceResult
        result = ServiceResult.err('No rate.', code='NO_RATE')
        resp   = DjoyaltyResponse.from_service(result)
        self.assertEqual(resp.data['code'], 'NO_RATE')

    def test_from_service_created_returns_201_on_success(self):
        from api.djoyalty.response_helpers import DjoyaltyResponse
        from api.djoyalty.service_result import ServiceResult
        result = ServiceResult.ok(reference='CO-001')
        resp   = DjoyaltyResponse.from_service_created(result)
        self.assertEqual(resp.status_code, 201)

    def test_no_content_returns_204(self):
        from api.djoyalty.response_helpers import DjoyaltyResponse
        resp = DjoyaltyResponse.no_content()
        self.assertEqual(resp.status_code, 204)

    def test_reference_required_is_400(self):
        from api.djoyalty.response_helpers import DjoyaltyResponse
        resp = DjoyaltyResponse.reference_required()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('reference_id', resp.data['error'])


# ══════════════════════════════════════════════════════════════════════════════
# SECTION C — DjoyaltyBaseViewSet customer helpers
# ══════════════════════════════════════════════════════════════════════════════

class TestDjoyaltyBaseViewSetCustomerHelpers(TestCase):
    """DjoyaltyBaseViewSet.get_customer() and require_customer()"""

    def _make_viewset(self, request):
        from api.djoyalty.mixins import DjoyaltyBaseViewSet
        class V(DjoyaltyBaseViewSet):
            pass
        v = V(); v.request = request; return v

    def _make_request(self, customer=None, data=None, params=None):
        factory = RequestFactory()
        req = factory.post('/', data=data or {}, content_type='application/json')
        if customer:
            req.loyalty_customer = customer
        return req

    def test_get_customer_returns_middleware_customer(self):
        mock_customer = MagicMock(); mock_customer.code = 'C001'
        req  = self._make_request(customer=mock_customer)
        vs   = self._make_viewset(req)
        result = vs.get_customer(req)
        self.assertEqual(result, mock_customer)

    def test_get_customer_returns_none_when_no_id(self):
        req = self._make_request()
        vs  = self._make_viewset(req)
        req.data = {}
        result = vs.get_customer(req)
        self.assertIsNone(result)

    def test_get_customer_looks_up_by_customer_id(self):
        req = self._make_request()
        req.data   = {'customer_id': '42'}
        req.query_params = {}
        vs  = self._make_viewset(req)
        mock_cust = MagicMock()
        with patch('api.djoyalty.models.core.Customer.objects') as MockC:
            MockC.get.return_value = mock_cust
            result = vs.get_customer(req)
        self.assertEqual(result, mock_cust)

    def test_get_customer_returns_none_on_does_not_exist(self):
        req = self._make_request()
        req.data        = {'customer_id': '999'}
        req.query_params = {}
        vs = self._make_viewset(req)
        with patch('api.djoyalty.models.core.Customer.objects') as MockC:
            MockC.get.side_effect = Exception('DoesNotExist')
            result = vs.get_customer(req)
        self.assertIsNone(result)

    def test_require_customer_returns_tuple_on_success(self):
        mock_customer = MagicMock(); mock_customer.code = 'C002'
        req = self._make_request(customer=mock_customer)
        vs  = self._make_viewset(req)
        customer, err = vs.require_customer(req)
        self.assertEqual(customer, mock_customer)
        self.assertIsNone(err)

    def test_require_customer_returns_customer_required_when_no_id(self):
        req = self._make_request()
        req.data        = {}
        req.query_params = {}
        vs  = self._make_viewset(req)
        customer, err = vs.require_customer(req)
        self.assertIsNone(customer)
        self.assertIsNotNone(err)
        self.assertEqual(err.status_code, 400)

    def test_require_customer_returns_404_when_id_not_found(self):
        req = self._make_request()
        req.data        = {'customer_id': '999'}
        req.query_params = {}
        vs = self._make_viewset(req)
        with patch('api.djoyalty.models.core.Customer.objects') as MockC:
            MockC.get.side_effect = Exception('DoesNotExist')
            customer, err = vs.require_customer(req)
        self.assertIsNone(customer)
        self.assertEqual(err.status_code, 404)

    def test_get_customer_reads_from_query_params(self):
        factory = RequestFactory()
        req = factory.get('/?customer_id=10')
        req.loyalty_customer = None
        req.data = {}
        # DRF query_params is an immutable QueryDict — use a plain dict mock
        from django.http import QueryDict
        req.query_params = {'customer_id': '10'}
        vs = self._make_viewset(req)
        with patch('api.djoyalty.models.core.Customer.objects') as MockC:
            mock_c = MagicMock()
            MockC.get.return_value = mock_c
            result = vs.get_customer(req)
        self.assertEqual(result, mock_c)

    def test_get_tenant_returns_request_tenant(self):
        req = self._make_request()
        tenant = MagicMock()
        req.tenant = tenant
        vs = self._make_viewset(req)
        self.assertEqual(vs.get_tenant(), tenant)

    def test_get_tenant_returns_none_when_no_tenant(self):
        req = self._make_request()
        vs  = self._make_viewset(req)
        self.assertIsNone(vs.get_tenant())


# ══════════════════════════════════════════════════════════════════════════════
# SECTION D — DjoyaltyBaseViewSet response helpers
# ══════════════════════════════════════════════════════════════════════════════

class TestDjoyaltyBaseViewSetResponseHelpers(TestCase):

    def _viewset(self):
        from api.djoyalty.mixins import DjoyaltyBaseViewSet
        class V(DjoyaltyBaseViewSet):
            pass
        v = V()
        v.request = MagicMock()
        return v

    def test_ok_returns_200(self):
        vs   = self._viewset()
        resp = vs.ok({'key': 'value'})
        self.assertEqual(resp.status_code, 200)

    def test_created_returns_201(self):
        vs   = self._viewset()
        resp = vs.created({'id': 1})
        self.assertEqual(resp.status_code, 201)

    def test_err_returns_400_with_message(self):
        vs   = self._viewset()
        resp = vs.err('Something went wrong.')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['error'], 'Something went wrong.')

    def test_not_found_returns_404(self):
        vs   = self._viewset()
        resp = vs.not_found('Resource not found.')
        self.assertEqual(resp.status_code, 404)

    def test_forbidden_returns_403(self):
        vs   = self._viewset()
        resp = vs.forbidden('Access denied.')
        self.assertEqual(resp.status_code, 403)

    def test_from_service_ok_returns_200(self):
        from api.djoyalty.service_result import ServiceResult
        vs   = self._viewset()
        resp = vs.from_service(ServiceResult.ok(data='x'))
        self.assertEqual(resp.status_code, 200)

    def test_from_service_err_returns_400(self):
        from api.djoyalty.service_result import ServiceResult
        vs   = self._viewset()
        resp = vs.from_service(ServiceResult.err('Failed.'))
        self.assertEqual(resp.status_code, 400)

    def test_from_service_created_returns_201(self):
        from api.djoyalty.service_result import ServiceResult
        vs   = self._viewset()
        resp = vs.from_service_created(ServiceResult.ok(ref='x'))
        self.assertEqual(resp.status_code, 201)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION E — DjoyaltyBaseService
# ══════════════════════════════════════════════════════════════════════════════

class TestDjoyaltyBaseService(TestCase):

    def _make_service(self):
        from api.djoyalty.services.base import DjoyaltyBaseService
        class TestSvc(DjoyaltyBaseService):
            pass
        return TestSvc

    def test_ok_returns_success_true(self):
        Svc = self._make_service()
        result = Svc._ok(value=42)
        self.assertTrue(result['success'])
        self.assertEqual(result['value'], 42)

    def test_err_returns_success_false(self):
        Svc = self._make_service()
        result = Svc._err('Invalid.')
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Invalid.')

    def test_err_with_code(self):
        Svc = self._make_service()
        result = Svc._err('No rate.', code='NO_RATE')
        self.assertEqual(result['code'], 'NO_RATE')

    def test_err_exc_converts_exception(self):
        Svc = self._make_service()
        exc = ValueError('boom')
        result = Svc._err_exc(exc)
        self.assertFalse(result['success'])
        self.assertIn('boom', result['error'])

    def test_err_exc_logs_error(self):
        Svc = self._make_service()
        with patch.object(Svc, '_err_log') as mock_log:
            Svc._err_exc(ValueError('test'))
        mock_log.assert_called_once()

    def test_skipped_returns_skipped_result(self):
        Svc    = self._make_service()
        result = Svc._skipped('Already done.')
        self.assertTrue(result['success'])
        self.assertTrue(result['skipped'])

    def test_logger_is_named_after_subclass(self):
        Svc = self._make_service()
        logger = Svc._logger()
        self.assertIn('TestSvc', logger.name)

    def test_resolve_tenant_prefers_explicit_tenant(self):
        Svc = self._make_service()
        explicit = MagicMock()
        customer = MagicMock()
        customer.tenant = MagicMock()
        result = Svc._resolve_tenant(customer=customer, tenant=explicit)
        self.assertEqual(result, explicit)

    def test_resolve_tenant_falls_back_to_customer(self):
        Svc    = self._make_service()
        tenant = MagicMock()
        customer = MagicMock()
        customer.tenant = tenant
        result = Svc._resolve_tenant(customer=customer)
        self.assertEqual(result, tenant)

    def test_resolve_tenant_returns_none_when_nothing(self):
        Svc    = self._make_service()
        result = Svc._resolve_tenant()
        self.assertIsNone(result)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION F — CashoutService uses ServiceResult
# ══════════════════════════════════════════════════════════════════════════════

class TestCashoutServiceUsesServiceResult(TestCase):
    """Verify CashoutService returns properly structured ServiceResult dicts。"""

    def _customer(self):
        c = MagicMock(); c.id=1; c.code='DRYDRY'; c.is_active=True
        c.is_verified=True; c.tenant=None; return c

    @patch('api.djoyalty.models.cashout.CashoutRequest')
    def test_create_request_returns_err_on_duplicate_pending(self, MockCR):
        from api.djoyalty.services.CashoutService import CashoutService
        from api.djoyalty.service_result import ServiceResult
        MockCR.objects.filter.return_value.exists.return_value = True
        result = CashoutService.create_request(
            self._customer(), Decimal('200'), 'bank_transfer',
        )
        self.assertFalse(ServiceResult.is_ok(result))
        self.assertIn('pending', ServiceResult.error_message(result))
        self.assertEqual(ServiceResult.error_code(result), 'DUPLICATE_PENDING')

    @patch('api.djoyalty.models.cashout.CashoutRequest')
    def test_create_request_result_has_code_key_on_failure(self, MockCR):
        from api.djoyalty.services.CashoutService import CashoutService
        MockCR.objects.filter.return_value.exists.return_value = True
        result = CashoutService.create_request(
            self._customer(), Decimal('200'), 'bank_transfer',
        )
        self.assertIn('code', result)

    @patch('api.djoyalty.models.cashout.CashoutRequest')
    @patch('api.djoyalty.validator.LoyaltyValidator')
    def test_create_request_result_has_code_on_validation_failure(self, MockVal, MockCR):
        from api.djoyalty.services.CashoutService import CashoutService
        MockCR.objects.filter.return_value.exists.return_value = False
        MockVal.validate_cashout.return_value = (False, 'Insufficient balance.')
        result = CashoutService.create_request(
            self._customer(), Decimal('200'), 'bank_transfer',
        )
        self.assertFalse(result['success'])
        self.assertEqual(result.get('code'), 'VALIDATION_FAILED')

    @patch('api.djoyalty.models.cashout.CashoutRequest')
    @patch('api.djoyalty.validator.LoyaltyValidator')
    @patch('api.djoyalty.models.cashout.CashoutRate')
    def test_create_request_returns_no_rate_code(self, MockCRate, MockVal, MockCR):
        from api.djoyalty.services.CashoutService import CashoutService
        MockCR.objects.filter.return_value.exists.return_value = False
        MockVal.validate_cashout.return_value = (True, '')
        # Make CashoutRate return None so service returns NO_RATE error
        MockCRate.objects.filter.return_value.order_by.return_value.first.return_value = None
        result = CashoutService.create_request(
            self._customer(), Decimal('200'), 'bank_transfer', rate=None,
        )
        self.assertFalse(result['success'])
        self.assertEqual(result.get('code'), 'NO_RATE')

    def test_cashout_service_inherits_base_service(self):
        from api.djoyalty.services.CashoutService import CashoutService
        from api.djoyalty.services.base import DjoyaltyBaseService
        self.assertTrue(issubclass(CashoutService, DjoyaltyBaseService))

    def test_cashout_service_has_ok_method(self):
        from api.djoyalty.services.CashoutService import CashoutService
        self.assertTrue(hasattr(CashoutService, '_ok'))
        self.assertTrue(hasattr(CashoutService, '_err'))
        self.assertTrue(hasattr(CashoutService, '_err_exc'))


# ══════════════════════════════════════════════════════════════════════════════
# SECTION G — Viewsets use DjoyaltyBaseViewSet (structural checks)
# ══════════════════════════════════════════════════════════════════════════════

class TestViewsetsUseDjoyaltyBaseViewSet(TestCase):

    def _get_src(self, relpath):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return open(os.path.join(base, relpath)).read()

    def test_cashout_viewset_inherits_dry_base(self):
        src = self._get_src('viewsets/advanced/CashoutViewSet.py')
        self.assertIn('DjoyaltyBaseViewSet', src)

    def test_conversion_viewset_inherits_dry_base(self):
        src = self._get_src('viewsets/points/PointsConversionViewSet.py')
        self.assertIn('DjoyaltyBaseViewSet', src)

    def test_transfer_viewset_inherits_dry_base(self):
        src = self._get_src('viewsets/points/PointsTransferViewSet.py')
        self.assertIn('DjoyaltyBaseViewSet', src)

    def test_cashout_viewset_uses_require_customer(self):
        src = self._get_src('viewsets/advanced/CashoutViewSet.py')
        self.assertIn('require_customer', src)
        # Must NOT have the old pattern
        self.assertNotIn(
            "getattr(request, 'loyalty_customer', None)\n        if not customer:",
            src,
        )

    def test_cashout_viewset_uses_self_err_not_inline_response(self):
        src = self._get_src('viewsets/advanced/CashoutViewSet.py')
        self.assertIn('return self.err(', src)
        self.assertIn('return self.ok(', src)
        self.assertIn('return self.created(', src)

    def test_conversion_viewset_uses_self_helpers(self):
        src = self._get_src('viewsets/points/PointsConversionViewSet.py')
        self.assertIn('return self.err(', src)
        self.assertIn('return self.ok(', src)

    def test_transfer_viewset_uses_self_helpers(self):
        src = self._get_src('viewsets/points/PointsTransferViewSet.py')
        self.assertIn('return self.err(', src)
        self.assertIn('return self.forbidden(', src)

    def test_no_raw_response_dict_error_in_cashout_viewset(self):
        """CashoutViewSet must not have raw inline Response({'error': ...}) calls。"""
        src = self._get_src('viewsets/advanced/CashoutViewSet.py')
        import re
        raw_patterns = re.findall(r"return Response\(\{['\"]error['\"]", src)
        self.assertEqual(
            len(raw_patterns), 0,
            f'CashoutViewSet still has {len(raw_patterns)} raw Response(error) calls: {raw_patterns}',
        )
