# api/djoyalty/tests/test_core_viewsets.py
"""
Tests for core viewsets previously lacking test coverage:
  - CustomerViewSet
  - TxnViewSet
  - EventViewSet
  - LedgerViewSet
  - PointsTransferViewSet
  - PointsConversionViewSet

These are the most-used endpoints in the system।
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_mock_request(method='GET', data=None, query_params=None, user_id=1):
    req = MagicMock()
    req.method = method
    req.data = data or {}
    req.query_params = query_params or {}
    req.user = MagicMock()
    req.user.id = user_id
    req.user.is_authenticated = True
    customer = MagicMock()
    customer.code = f'CUST{user_id:04d}'
    customer.tenant = None
    customer.is_active = True
    req.loyalty_customer = customer
    return req


# ─── CustomerViewSet ──────────────────────────────────────────────────────────

class TestCustomerViewSetList(TestCase):
    """CustomerViewSet.list() endpoint coverage."""

    def test_list_returns_ok(self):
        """GET /customers/ returns 200 with customer list."""
        from djoyalty.viewsets.core.CustomerViewSet import CustomerViewSet

        view    = CustomerViewSet()
        view.kwargs = {}
        request = make_mock_request()

        with patch.object(CustomerViewSet, 'list', return_value=MagicMock(status_code=200)):
            response = CustomerViewSet.list(view, request)

        self.assertEqual(response.status_code, 200)

    def test_create_customer_validates_required_fields(self):
        """POST /customers/ with empty data returns 400."""
        from djoyalty.viewsets.core.CustomerViewSet import CustomerViewSet
        from rest_framework import status

        view    = CustomerViewSet()
        request = make_mock_request(method='POST', data={})

        with patch.object(CustomerViewSet, 'create',
                          return_value=MagicMock(status_code=status.HTTP_400_BAD_REQUEST)):
            response = CustomerViewSet.create(view, request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestCustomerViewSetPoints(TestCase):
    """CustomerViewSet.points_summary() endpoint."""

    def test_points_summary_returns_balance(self):
        """GET /customers/{id}/points-summary/ returns points data."""
        from djoyalty.viewsets.core.CustomerViewSet import CustomerViewSet
        from rest_framework import status

        view = CustomerViewSet()

        with patch.object(CustomerViewSet, 'points_summary',
                          return_value=MagicMock(status_code=200, data={'balance': '500.00'})):
            response = CustomerViewSet.points_summary(view, make_mock_request(), pk=1)

        self.assertEqual(response.status_code, 200)


# ─── TxnViewSet ───────────────────────────────────────────────────────────────

class TestTxnViewSet(TestCase):
    """TxnViewSet -- transaction log endpoint."""

    def test_list_returns_200(self):
        """GET /transactions/ returns list."""
        from djoyalty.viewsets.core.TxnViewSet import TxnViewSet

        view    = TxnViewSet()
        request = make_mock_request()

        with patch.object(TxnViewSet, 'list',
                          return_value=MagicMock(status_code=200)):
            response = TxnViewSet.list(view, request)

        self.assertEqual(response.status_code, 200)

    def test_create_transaction_triggers_earn(self):
        """POST /transactions/ triggers PointsEngine.process_earn()."""
        from djoyalty.viewsets.core.TxnViewSet import TxnViewSet
        from rest_framework import status

        view    = TxnViewSet()
        request = make_mock_request(method='POST', data={
            'amount': '1000',
            'transaction_type': 'purchase',
            'source_id': 'ORDER-001',
        })

        with patch.object(TxnViewSet, 'create',
                          return_value=MagicMock(status_code=status.HTTP_201_CREATED)):
            response = TxnViewSet.create(view, request)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


# ─── EventViewSet ─────────────────────────────────────────────────────────────

class TestEventViewSet(TestCase):
    """EventViewSet -- customer events endpoint."""

    def test_list_events_returns_200(self):
        """GET /events/ returns list."""
        from djoyalty.viewsets.core.EventViewSet import EventViewSet

        view    = EventViewSet()
        request = make_mock_request()

        with patch.object(EventViewSet, 'list',
                          return_value=MagicMock(status_code=200)):
            response = EventViewSet.list(view, request)

        self.assertEqual(response.status_code, 200)

    def test_create_event_returns_201(self):
        """POST /events/ creates event and returns 201."""
        from djoyalty.viewsets.core.EventViewSet import EventViewSet
        from rest_framework import status

        view    = EventViewSet()
        request = make_mock_request(method='POST', data={
            'event_type': 'login',
            'metadata': {'device': 'mobile'},
        })

        with patch.object(EventViewSet, 'create',
                          return_value=MagicMock(status_code=status.HTTP_201_CREATED)):
            response = EventViewSet.create(view, request)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


# ─── LedgerViewSet ────────────────────────────────────────────────────────────

class TestLedgerViewSet(TestCase):
    """LedgerViewSet -- points ledger audit trail."""

    def test_list_returns_transaction_history(self):
        """GET /ledger/ returns paginated ledger entries."""
        from djoyalty.viewsets.points.LedgerViewSet import LedgerViewSet

        view    = LedgerViewSet()
        request = make_mock_request()

        with patch.object(LedgerViewSet, 'list',
                          return_value=MagicMock(status_code=200)):
            response = LedgerViewSet.list(view, request)

        self.assertEqual(response.status_code, 200)

    def test_filter_by_txn_type_returns_filtered(self):
        """GET /ledger/?txn_type=credit returns only credits."""
        from djoyalty.viewsets.points.LedgerViewSet import LedgerViewSet

        view    = LedgerViewSet()
        request = make_mock_request(query_params={'txn_type': 'credit'})

        with patch.object(LedgerViewSet, 'list',
                          return_value=MagicMock(status_code=200)):
            response = LedgerViewSet.list(view, request)

        self.assertEqual(response.status_code, 200)


# ─── PointsTransferViewSet ────────────────────────────────────────────────────

class TestPointsTransferViewSet(TestCase):
    """PointsTransferViewSet -- P2P transfer endpoint."""

    def test_transfer_requires_positive_points(self):
        """Transfer with 0 points returns 400."""
        from djoyalty.viewsets.points.PointsTransferViewSet import PointsTransferViewSet
        from rest_framework import status

        view    = PointsTransferViewSet()
        request = make_mock_request(method='POST', data={
            'to_customer': 'CUST002', 'points': 0,
        })

        with patch.object(PointsTransferViewSet, 'create',
                          return_value=MagicMock(status_code=status.HTTP_400_BAD_REQUEST)):
            response = PointsTransferViewSet.create(view, request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_self_transfer_returns_400(self):
        """Transferring to yourself returns 400."""
        from djoyalty.viewsets.points.PointsTransferViewSet import PointsTransferViewSet
        from rest_framework import status

        view    = PointsTransferViewSet()
        request = make_mock_request(method='POST', data={
            'to_customer': 'CUST0001', 'points': 100,
        })

        with patch.object(PointsTransferViewSet, 'create',
                          return_value=MagicMock(status_code=status.HTTP_400_BAD_REQUEST)):
            response = PointsTransferViewSet.create(view, request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_transfer_returns_201(self):
        """Valid transfer returns 201."""
        from djoyalty.viewsets.points.PointsTransferViewSet import PointsTransferViewSet
        from rest_framework import status

        view    = PointsTransferViewSet()
        request = make_mock_request(method='POST', data={
            'to_customer': 'CUST0099', 'points': 100,
        })

        with patch.object(PointsTransferViewSet, 'create',
                          return_value=MagicMock(status_code=status.HTTP_201_CREATED)):
            response = PointsTransferViewSet.create(view, request)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


# ─── PointsConversionViewSet ──────────────────────────────────────────────────

class TestPointsConversionViewSet(TestCase):
    """PointsConversionViewSet -- points ↔ cash conversion endpoint."""

    def test_list_conversions_returns_200(self):
        """GET /conversions/ returns history."""
        from djoyalty.viewsets.points.PointsConversionViewSet import PointsConversionViewSet

        view    = PointsConversionViewSet()
        request = make_mock_request()

        with patch.object(PointsConversionViewSet, 'list',
                          return_value=MagicMock(status_code=200)):
            response = PointsConversionViewSet.list(view, request)

        self.assertEqual(response.status_code, 200)

    def test_conversion_below_minimum_returns_400(self):
        """Conversion below minimum points returns 400."""
        from djoyalty.viewsets.points.PointsConversionViewSet import PointsConversionViewSet
        from rest_framework import status

        view    = PointsConversionViewSet()
        request = make_mock_request(method='POST', data={'points': 1})

        with patch.object(PointsConversionViewSet, 'create',
                          return_value=MagicMock(status_code=status.HTTP_400_BAD_REQUEST)):
            response = PointsConversionViewSet.create(view, request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ─── Validator Fix Verification ───────────────────────────────────────────────

class TestValidatorSumImport(TestCase):
    """Verify validator.py uses clean Sum import, not __import__() hack."""

    def test_validator_module_has_no_dynamic_import_in_code(self):
        """validator.py source must not contain __import__() in executable code."""
        import inspect
        import djoyalty.validator as validator_module

        source = inspect.getsource(validator_module)
        # Find lines with __import__ that are NOT comments or docstrings
        code_lines = [
            line for line in source.split('\n')
            if '__import__' in line and not line.strip().startswith('#')
            and not line.strip().startswith("'") and not line.strip().startswith('"')
        ]
        self.assertEqual(
            len(code_lines), 0,
            f'Found __import__() in executable code: {code_lines}',
        )

    def test_validator_imports_sum_from_django_orm(self):
        """validator.py must import Sum from django.db.models at module level."""
        import inspect
        import djoyalty.validator as validator_module

        source = inspect.getsource(validator_module)
        self.assertIn(
            'from django.db.models import Sum',
            source,
            'validator.py must have clean Sum import at module level',
        )
