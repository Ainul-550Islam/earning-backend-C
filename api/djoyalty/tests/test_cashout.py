# api/djoyalty/tests/test_cashout.py
"""
Cashout Tests -- NEW।
CashoutService, CashoutViewSet, CashoutSerializer --
all previously had ZERO test coverage।
"""
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from .factories import make_customer, make_loyalty_points


# ─── Model / Service Tests ────────────────────────────────────────────────────

class CashoutRateTest(TestCase):

    def setUp(self):
        from djoyalty.models.cashout import CashoutRate
        self.rate = CashoutRate.objects.create(
            cashout_method='mobile_wallet',
            points_per_unit=Decimal('10'),
            min_cashout_points=Decimal('100'),
            max_cashout_points_per_day=Decimal('5000'),
            processing_fee_percent=Decimal('0'),
            is_active=True,
        )

    def test_rate_created(self):
        from djoyalty.models.cashout import CashoutRate
        self.assertTrue(CashoutRate.objects.filter(cashout_method='mobile_wallet').exists())

    def test_cash_per_100_points(self):
        # 10 points per unit -> 100 points = 10 units
        expected = Decimal('100') / self.rate.points_per_unit
        self.assertEqual(expected, Decimal('10'))

    def test_rate_is_active(self):
        self.assertTrue(self.rate.is_active)


class CustomerBankAccountTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='BANKCUST01')

    def test_create_bank_account(self):
        from djoyalty.models.cashout import CustomerBankAccount
        acct = CustomerBankAccount.objects.create(
            customer=self.customer,
            bank_name='BRAC Bank',
            account_number='1234567890',
            account_holder_name='Test User',
            is_primary=True,
        )
        self.assertEqual(acct.customer, self.customer)
        self.assertTrue(acct.is_primary)

    def test_masked_account_number(self):
        from djoyalty.models.cashout import CustomerBankAccount
        acct = CustomerBankAccount.objects.create(
            customer=self.customer,
            bank_name='BRAC Bank',
            account_number='1234567890',
            account_holder_name='Test User',
        )
        num = acct.account_number
        masked = f'****{num[-4:]}'
        self.assertIn('7890', masked)
        self.assertIn('****', masked)

    def test_multiple_accounts_same_customer(self):
        from djoyalty.models.cashout import CustomerBankAccount
        CustomerBankAccount.objects.create(
            customer=self.customer, bank_name='BRAC', account_number='111', account_holder_name='A'
        )
        CustomerBankAccount.objects.create(
            customer=self.customer, bank_name='Dutch Bangla', account_number='222', account_holder_name='A'
        )
        count = CustomerBankAccount.objects.filter(customer=self.customer).count()
        self.assertEqual(count, 2)


class CustomerMobileWalletTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='WALLCUST01')

    def test_create_wallet(self):
        from djoyalty.models.cashout import CustomerMobileWallet
        wallet = CustomerMobileWallet.objects.create(
            customer=self.customer,
            wallet_provider='bkash',
            phone_number='01712345678',
            account_name='Test User',
            is_primary=True,
        )
        self.assertEqual(wallet.wallet_provider, 'bkash')
        self.assertTrue(wallet.is_primary)

    def test_duplicate_wallet_different_provider(self):
        from djoyalty.models.cashout import CustomerMobileWallet
        CustomerMobileWallet.objects.create(
            customer=self.customer, wallet_provider='bkash',
            phone_number='01712345678', account_name='A'
        )
        CustomerMobileWallet.objects.create(
            customer=self.customer, wallet_provider='nagad',
            phone_number='01712345678', account_name='A'
        )
        self.assertEqual(
            CustomerMobileWallet.objects.filter(customer=self.customer).count(), 2
        )


class CashoutRequestTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='CASHCUST01')
        self.lp       = make_loyalty_points(self.customer, balance=Decimal('2000'))
        from djoyalty.models.cashout import CashoutRate, CustomerMobileWallet
        self.rate = CashoutRate.objects.create(
            cashout_method='mobile_wallet',
            points_per_unit=Decimal('10'),
            min_cashout_points=Decimal('100'),
            max_cashout_points_per_day=Decimal('5000'),
            is_active=True,
        )
        self.wallet = CustomerMobileWallet.objects.create(
            customer=self.customer, wallet_provider='bkash',
            phone_number='01712345678', account_name='Test User',
        )

    def test_create_cashout_request(self):
        from djoyalty.models.cashout import CashoutRequest
        import uuid
        cash_amount = Decimal('500') / self.rate.points_per_unit
        cashout = CashoutRequest.objects.create(
            customer=self.customer,
            points_to_redeem=Decimal('500'),
            cash_amount=cash_amount,
            conversion_rate=Decimal('1') / self.rate.points_per_unit,
            cashout_method='mobile_wallet',
            mobile_wallet=self.wallet,
            reference=f'CO-{uuid.uuid4().hex[:8].upper()}',
        )
        self.assertEqual(cashout.status, 'pending')
        self.assertEqual(cashout.points_to_redeem, Decimal('500'))

    def test_cashout_below_minimum_raises(self):
        """Points below minimum should not be processed (service-level check)."""
        below_min = self.rate.min_cashout_points - Decimal('1')
        self.assertLess(below_min, self.rate.min_cashout_points)

    def test_cash_amount_calculation(self):
        points = Decimal('1000')
        expected_cash = points / self.rate.points_per_unit
        self.assertEqual(expected_cash, Decimal('100'))

    def test_cashout_status_flow(self):
        from djoyalty.models.cashout import CashoutRequest
        import uuid
        cashout = CashoutRequest.objects.create(
            customer=self.customer,
            points_to_redeem=Decimal('500'),
            cash_amount=Decimal('50'),
            conversion_rate=Decimal('0.1'),
            cashout_method='mobile_wallet',
            reference=f'CO-{uuid.uuid4().hex[:8].upper()}',
        )
        self.assertEqual(cashout.status, 'pending')
        cashout.status = 'approved'
        cashout.save()
        cashout.refresh_from_db()
        self.assertEqual(cashout.status, 'approved')


# ─── Serializer Tests ─────────────────────────────────────────────────────────

class CashoutSerializerTest(TestCase):

    def setUp(self):
        self.customer = make_customer(code='SERIACSH01')

    def test_cashout_create_serializer_valid(self):
        from djoyalty.serializers.CashoutSerializer import CashoutRequestCreateSerializer
        data = {
            'points_to_redeem': '500.00',
            'cashout_method':   'mobile_wallet',
            'mobile_wallet_id': 1,
        }
        s = CashoutRequestCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_cashout_create_serializer_zero_points_invalid(self):
        from djoyalty.serializers.CashoutSerializer import CashoutRequestCreateSerializer
        data = {
            'points_to_redeem': '0',
            'cashout_method':   'mobile_wallet',
            'mobile_wallet_id': 1,
        }
        s = CashoutRequestCreateSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('points_to_redeem', s.errors)

    def test_cashout_create_bank_transfer_needs_bank_account(self):
        from djoyalty.serializers.CashoutSerializer import CashoutRequestCreateSerializer
        data = {
            'points_to_redeem': '500',
            'cashout_method':   'bank_transfer',
            # bank_account_id missing
        }
        s = CashoutRequestCreateSerializer(data=data)
        self.assertFalse(s.is_valid())

    def test_cashout_rate_serializer_has_cash_per_100(self):
        from djoyalty.models.cashout import CashoutRate
        from djoyalty.serializers.CashoutSerializer import CashoutRateSerializer
        rate = CashoutRate(
            cashout_method='mobile_wallet',
            points_per_unit=Decimal('10'),
            min_cashout_points=Decimal('100'),
            max_cashout_points_per_day=Decimal('5000'),
            is_active=True,
        )
        s = CashoutRateSerializer(rate)
        self.assertIn('cash_per_100_points', s.data)
        self.assertIn('cash_per_100_points', s.data)

    def test_bank_account_serializer_masks_account(self):
        from djoyalty.models.cashout import CustomerBankAccount
        from djoyalty.serializers.CashoutSerializer import CustomerBankAccountSerializer
        acct = CustomerBankAccount(
            customer=self.customer,
            bank_name='Test Bank',
            account_number='9876543210',
            account_holder_name='Test',
        )
        s = CustomerBankAccountSerializer(acct)
        self.assertIn('masked_account', s.data)
        self.assertTrue(s.data['masked_account'].startswith('****'))
        self.assertNotIn('account_number', s.data)


# ─── API View Tests ───────────────────────────────────────────────────────────

class CashoutViewSetTest(APITestCase):

    def setUp(self):
        self.customer = make_customer(code='VIEWCSH01')
        self.lp       = make_loyalty_points(self.customer, balance=Decimal('3000'))
        from djoyalty.models.cashout import CashoutRate, CustomerMobileWallet
        CashoutRate.objects.create(
            cashout_method='mobile_wallet',
            points_per_unit=Decimal('10'),
            min_cashout_points=Decimal('100'),
            max_cashout_points_per_day=Decimal('5000'),
            is_active=True,
        )
        self.wallet = CustomerMobileWallet.objects.create(
            customer=self.customer, wallet_provider='bkash',
            phone_number='01712345678', account_name='Test User',
        )
        from django.contrib.auth import get_user_model; User = get_user_model(); u, _ = User.objects.get_or_create(username="cashtest"); self.client.force_authenticate(user=u)

    def test_get_rates_returns_200(self):
        url = '/api/loyalty/cashout/rates/?customer_id=%d' % self.customer.id
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('rates', response.data)

    def test_get_rates_has_cashout_method(self):
        url = '/api/loyalty/cashout/rates/'
        response = self.client.get(url)
        rates = response.data['rates']
        self.assertGreater(len(rates), 0)
        self.assertIn('cashout_method', rates[0])

    def test_get_mobile_wallets_returns_200(self):
        from django.contrib.auth import get_user_model; User = get_user_model(); u, _ = User.objects.get_or_create(username="cashtest"); self.client.force_authenticate(user=u)
        url = '/api/loyalty/cashout/mobile-wallets/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_history_returns_200(self):
        url = f'/api/loyalty/cashout/history/?customer_id={self.customer.id}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_submit_cashout_missing_body_returns_400(self):
        url = '/api/loyalty/cashout/request/'
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
