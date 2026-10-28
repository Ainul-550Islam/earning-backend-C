# api/djoyalty/tests/test_export_viewset.py
"""
ExportViewSet tests -- all 7 export endpoints。
Previously 0 of these actions were tested (viewset was new this session)。
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


def _admin():
    u = User.objects.create_user(username=f'exp_{User.objects.count()}', password='pw', is_staff=True)
    c = APIClient(); c.force_authenticate(user=u)
    return c

def _customer_and_cli():
    from djoyalty.models.core import Tenant, Customer
    t = Tenant.objects.create(name=f'ExpCo-{Tenant.objects.count()}',
                               slug=f'exp-{Tenant.objects.count()}', is_active=True)
    u = User.objects.create_user(username=f'expc_{User.objects.count()}', password='pw')
    c = Customer.objects.create(tenant=t, user=u, code=f'EX{Customer.objects.count():04d}', is_active=True)
    cli = APIClient(); cli.force_authenticate(user=u)
    return c, cli


class ExportCustomersTest(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.customer, self.cli = _customer_and_cli()

    @patch('djoyalty.viewsets.advanced.ExportViewSet.LoyaltyExportService.export_customers_csv')
    def test_export_customers_csv(self, mock_export):
        mock_export.return_value = (
            'customer_code,email,phone,balance,tier\n'
            'C001,test@example.com,01711111111,500.00,Gold\n'
        )
        resp = self.admin.get('/api/loyalty/export/customers/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        self.assertIn('customers.csv', resp['Content-Disposition'])
        mock_export.assert_called_once()

    @patch('djoyalty.viewsets.advanced.ExportViewSet.LoyaltyExportService.export_customers_csv')
    def test_export_filters_active(self, mock_export):
        mock_export.return_value = 'customer_code\nC001\n'
        resp = self.admin.get('/api/loyalty/export/customers/?is_active=true')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        call_kwargs = mock_export.call_args[1]
        self.assertTrue(call_kwargs.get('is_active'))

    def test_export_requires_admin(self):
        resp = self.cli.get('/api/loyalty/export/customers/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class ExportPointsTest(TestCase):
    def setUp(self):
        self.admin = _admin()

    @patch('djoyalty.viewsets.advanced.ExportViewSet.LoyaltyExportService.export_points_csv')
    def test_export_points_csv(self, mock_export):
        mock_export.return_value = 'customer_code,txn_type,points,balance,created_at\n'
        resp = self.admin.get('/api/loyalty/export/points/?days=30')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        self.assertIn('points_ledger.csv', resp['Content-Disposition'])


class ExportTransactionsTest(TestCase):
    def setUp(self):
        self.admin = _admin()

    @patch('djoyalty.viewsets.advanced.ExportViewSet.LoyaltyExportService.export_transactions_csv')
    def test_export_transactions_csv(self, mock_export):
        mock_export.return_value = 'customer_code,amount,source,reference,created_at\n'
        resp = self.admin.get('/api/loyalty/export/transactions/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('transactions.csv', resp['Content-Disposition'])


class ExportRedemptionsTest(TestCase):
    def setUp(self):
        self.admin = _admin()

    @patch('djoyalty.viewsets.advanced.ExportViewSet.LoyaltyExportService.export_redemptions_csv')
    def test_export_redemptions_csv(self, mock_export):
        mock_export.return_value = 'customer_code,points_used,status,created_at\n'
        resp = self.admin.get('/api/loyalty/export/redemptions/?status=completed')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('redemptions.csv', resp['Content-Disposition'])
        call_kwargs = mock_export.call_args[1]
        self.assertEqual(call_kwargs.get('filter_status'), 'completed')


class ExportTiersTest(TestCase):
    def setUp(self):
        self.admin = _admin()

    @patch('djoyalty.viewsets.advanced.ExportViewSet.LoyaltyExportService.export_tier_distribution_csv')
    def test_export_tiers_csv(self, mock_export):
        mock_export.return_value = 'tier_name,customer_count,pct\nBronze,500,50.0\n'
        resp = self.admin.get('/api/loyalty/export/tiers/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('tier_distribution.csv', resp['Content-Disposition'])


class ExportGDPRTest(TestCase):
    def setUp(self):
        self.admin = _admin()
        self.customer, self.cli = _customer_and_cli()

    @patch('djoyalty.viewsets.advanced.ExportViewSet.LoyaltyExportService.export_customer_gdpr_json')
    def test_gdpr_export(self, mock_export):
        mock_export.return_value = {
            'customer_id':    self.customer.pk,
            'customer_code':  self.customer.code,
            'profile':        {'code': self.customer.code},
            'points_history': [],
            'redemptions':    [],
            'consents':       [],
            'exported_at':    '2026-06-01T00:00:00Z',
        }
        resp = self.admin.post('/api/loyalty/export/customer-gdpr/',
                               {'customer_id': self.customer.pk})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'application/json')
        self.assertIn('gdpr', resp['Content-Disposition'].lower())
        mock_export.assert_called_once_with(self.customer)

    def test_gdpr_export_missing_customer_id(self):
        resp = self.admin.post('/api/loyalty/export/customer-gdpr/', {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_gdpr_export_not_found(self):
        resp = self.admin.post('/api/loyalty/export/customer-gdpr/', {'customer_id': 99999})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_gdpr_export_requires_admin(self):
        resp = self.cli.post('/api/loyalty/export/customer-gdpr/',
                             {'customer_id': self.customer.pk})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
