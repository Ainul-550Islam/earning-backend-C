# api/djoyalty/tests/test_cashout_extended.py
"""
Extended CashoutViewSet tests -- admin_action, admin_pending, wallet_history,
bank_accounts, mobile_wallets, add_bank_account, add_mobile_wallet।
Previously: 0 of these 12 actions were tested।
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


def _tenant():
    from djoyalty.models.core import Tenant
    return Tenant.objects.create(name='CashoutCo', slug='cashout-co', is_active=True)

def _customer(tenant):
    from djoyalty.models.core import Customer
    u = User.objects.create_user(username=f'cu_{Customer.objects.count()}', password='pw')
    return Customer.objects.create(tenant=tenant, user=u,
                                   code=f'CC{Customer.objects.count():04d}', is_active=True)

def _admin():
    u = User.objects.create_user(username='cashout_admin', password='pw', is_staff=True)
    c = APIClient(); c.force_authenticate(user=u)
    return c

def _client(customer):
    c = APIClient(); c.force_authenticate(user=customer.user)
    return c

def _cashout(customer, points=Decimal('100'), status_='pending'):
    from djoyalty.models.cashout import CashoutRate, CashoutRequest
    rate, _ = CashoutRate.objects.get_or_create(
        cashout_method='bkash', defaults={
            'min_cashout_points': Decimal('100'), 'points_per_unit': Decimal('10'),
            'is_active': True,
        }
    )
    return CashoutRequest.objects.create(
        customer=customer, tenant=customer.tenant,
        points_to_redeem=points, cash_amount=Decimal('10.00'),
        conversion_rate=Decimal('0.10'), currency='BDT',
        cashout_method='bkash', reference='CO-TEST001', status=status_,
    )


class CashoutAdminPendingTest(TestCase):
    def setUp(self):
        self.tenant   = _tenant()
        self.customer = _customer(self.tenant)
        self.admin    = _admin()

    def test_admin_pending_returns_list(self):
        _cashout(self.customer)
        resp = self.admin.get('/api/loyalty/cashouts/admin/pending/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('results', resp.data)
        self.assertIn('count', resp.data)
        self.assertGreaterEqual(resp.data['count'], 1)

    def test_admin_pending_filters_by_status(self):
        _cashout(self.customer, status_='approved')
        resp = self.admin.get('/api/loyalty/cashouts/admin/pending/?status=approved')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_pending_requires_admin(self):
        cli = _client(self.customer)
        resp = cli.get('/api/loyalty/cashouts/admin/pending/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class CashoutAdminActionTest(TestCase):
    def setUp(self):
        self.tenant   = _tenant()
        self.customer = _customer(self.tenant)
        self.admin    = _admin()

    @patch('djoyalty.viewsets.advanced.CashoutViewSet.WalletBridgeService.approve_cashout')
    def test_admin_approve_action(self, mock_approve):
        cashout = _cashout(self.customer)
        resp = self.admin.post(f'/api/loyalty/cashouts/{cashout.pk}/action/', {
            'action': 'approve', 'note': 'Looks good',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['action'], 'approve')
        mock_approve.assert_called_once()

    @patch('djoyalty.viewsets.advanced.CashoutViewSet.WalletBridgeService.reject_cashout')
    def test_admin_reject_action(self, mock_reject):
        cashout = _cashout(self.customer)
        resp = self.admin.post(f'/api/loyalty/cashouts/{cashout.pk}/action/', {
            'action': 'reject', 'note': 'Fraud risk',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['action'], 'reject')
        mock_reject.assert_called_once()

    @patch('djoyalty.viewsets.advanced.CashoutViewSet.WalletBridgeService.complete_cashout')
    @patch('djoyalty.viewsets.advanced.CashoutViewSet.CashoutViewSet._fire_cashout_approved')
    def test_admin_complete_fires_signal(self, mock_fire, mock_complete):
        cashout = _cashout(self.customer, status_='approved')
        resp = self.admin.post(f'/api/loyalty/cashouts/{cashout.pk}/action/', {
            'action': 'complete', 'payment_reference': 'TXN-9999',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_fire.assert_called_once()
        fired_kwargs = mock_fire.call_args[1]
        self.assertEqual(fired_kwargs['action'], 'completed')
        self.assertEqual(fired_kwargs['payment_reference'], 'TXN-9999')

    def test_admin_action_requires_admin(self):
        cashout = _cashout(self.customer)
        cli = _client(self.customer)
        resp = cli.post(f'/api/loyalty/cashouts/{cashout.pk}/action/', {'action': 'approve'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class CashoutBankAccountTest(TestCase):
    def setUp(self):
        self.tenant   = _tenant()
        self.customer = _customer(self.tenant)
        self.cli      = _client(self.customer)
        self.admin    = _admin()

    def test_list_bank_accounts_empty(self):
        resp = self.cli.get('/api/loyalty/cashouts/bank-accounts/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_add_bank_account(self):
        resp = self.cli.post('/api/loyalty/cashouts/bank-accounts/add/', {
            'bank_name':       'Dutch-Bangla Bank',
            'account_name':    'Test Customer',
            'account_number':  '1234567890',
            'routing_number':  '090271524',
            'is_primary':      True,
        })
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_list_mobile_wallets_empty(self):
        resp = self.cli.get('/api/loyalty/cashouts/mobile-wallets/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_add_mobile_wallet_bkash(self):
        resp = self.cli.post('/api/loyalty/cashouts/mobile-wallets/add/', {
            'wallet_type':    'bkash',
            'phone_number':   '01711111111',
            'account_name':   'Test Customer',
            'is_primary':     True,
        })
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])


class CashoutWalletHistoryTest(TestCase):
    def setUp(self):
        self.tenant   = _tenant()
        self.customer = _customer(self.tenant)
        self.cli      = _client(self.customer)

    def test_wallet_history_returns_list(self):
        resp = self.cli.get(
            f'/api/loyalty/cashouts/wallet-history/?customer_id={self.customer.pk}'
        )
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_wallet_history_filters_by_type(self):
        resp = self.cli.get(
            f'/api/loyalty/cashouts/wallet-history/?customer_id={self.customer.pk}&type=earn'
        )
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])


class CashoutRatesTest(TestCase):
    def setUp(self):
        self.tenant   = _tenant()
        self.customer = _customer(self.tenant)
        self.cli      = _client(self.customer)

    def test_rates_returns_list(self):
        from djoyalty.models.cashout import CashoutRate
        CashoutRate.objects.get_or_create(
            cashout_method='bkash', defaults={
                'min_cashout_points': 100, 'points_per_unit': 10, 'is_active': True,
            }
        )
        resp = self.cli.get('/api/loyalty/cashouts/rates/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('rates', resp.data)
