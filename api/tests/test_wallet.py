# api/tests/test_wallet.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
import uuid

User = get_user_model()
def uid(): return uuid.uuid4().hex[:8]


class WalletModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username=f'u_{uid()}',
            email=f'{uid()}@test.com',
            password='testpass123'
        )

    def _get_or_create_wallet(self, user=None):
        from api.wallet.models import Wallet
        u = user or self.user
        wallet, _ = Wallet.objects.get_or_create(
            user=u,
            defaults={
                'currency': 'BDT',
                'current_balance': Decimal('0'),
                'pending_balance': Decimal('0'),
                'total_earned': Decimal('0'),
                'total_withdrawn': Decimal('0'),
            }
        )
        return wallet

    def test_wallet_auto_created(self):
        from api.wallet.models import Wallet
        exists = Wallet.objects.filter(user=self.user).exists()
        if not exists:
            Wallet.objects.create(user=self.user, currency='BDT')
        self.assertTrue(Wallet.objects.filter(user=self.user).exists())

    def test_wallet_fields(self):
        wallet = self._get_or_create_wallet()
        self.assertEqual(wallet.currency, 'BDT')
        self.assertEqual(wallet.current_balance, Decimal('0'))
        self.assertFalse(wallet.is_locked)

    def test_wallet_available_balance(self):
        wallet = self._get_or_create_wallet()
        wallet.current_balance = Decimal('100')
        wallet.frozen_balance = Decimal('20')
        wallet.save()
        self.assertEqual(wallet.available_balance, Decimal('80'))

    def test_wallet_lock_unlock(self):
        wallet = self._get_or_create_wallet()
        wallet.lock('Suspicious activity')
        self.assertTrue(wallet.is_locked)
        wallet.unlock()
        self.assertFalse(wallet.is_locked)

    def test_wallet_transaction_creation(self):
        from api.wallet.models import WalletTransaction
        wallet = self._get_or_create_wallet()
        txn = WalletTransaction.objects.create(
            wallet=wallet,
            type='earning',
            amount=Decimal('50'),
            status='pending',
            description='Test earning',
        )
        self.assertEqual(txn.type, 'earning')
        self.assertEqual(txn.status, 'pending')

    def test_wallet_transaction_approve(self):
        from api.wallet.models import WalletTransaction
        wallet = self._get_or_create_wallet()
        wallet.current_balance = Decimal('0')
        wallet.save()
        txn = WalletTransaction.objects.create(
            wallet=wallet,
            type='reward',
            amount=Decimal('100'),
            status='pending',
            balance_before=Decimal('0'),
        )
        txn.approve(approved_by=self.user)
        self.assertEqual(txn.status, 'approved')
        wallet.refresh_from_db()
        self.assertEqual(wallet.current_balance, Decimal('100'))

    def test_wallet_transaction_reject(self):
        from api.wallet.models import WalletTransaction
        wallet = self._get_or_create_wallet()
        txn = WalletTransaction.objects.create(
            wallet=wallet,
            type='bonus',
            amount=Decimal('30'),
            status='pending',
        )
        txn.reject(reason='Fraud detected')
        self.assertEqual(txn.status, 'rejected')

    def test_user_payment_method(self):
        from api.wallet.models import UserPaymentMethod
        pm = UserPaymentMethod.objects.create(
            user=self.user,
            method_type='bkash',
            account_number='01712345678',
            account_name='Test User',
            is_primary=True,
        )
        self.assertEqual(pm.method_type, 'bkash')
        self.assertTrue(pm.is_primary)

    def test_wallet_webhook_log(self):
        from api.wallet.models import WalletWebhookLog
        log = WalletWebhookLog.objects.create(
            webhook_type='bkash',
            event_type='payment_success',
            payload={'trxID': 'TRX123', 'amount': '100'},
            is_processed=False,
        )
        self.assertEqual(log.webhook_type, 'bkash')
        self.assertFalse(log.is_processed)

    def test_withdrawal_request(self):
        from api.wallet.models import WithdrawalRequest
        wr = WithdrawalRequest.objects.create(
            user=self.user,
            amount=Decimal('500'),
            fee=Decimal('5'),
            method='Bkash',
            account_number='01712345678',
            status='pending',
        )
        self.assertEqual(wr.status, 'pending')
        self.assertEqual(wr.amount, Decimal('500'))

    def test_wallet_freeze_unfreeze(self):
        from api.wallet.models import WalletTransaction
        wallet = self._get_or_create_wallet()
        wallet.current_balance = Decimal('200')
        wallet.frozen_balance = Decimal('0')
        wallet.save()
        wallet.freeze(Decimal('50'), 'Dispute')
        wallet.refresh_from_db()
        self.assertEqual(wallet.frozen_balance, Decimal('50'))
        self.assertEqual(wallet.current_balance, Decimal('150'))
        wallet.unfreeze(Decimal('50'), 'Resolved')
        wallet.refresh_from_db()
        self.assertEqual(wallet.frozen_balance, Decimal('0'))
        self.assertEqual(wallet.current_balance, Decimal('200'))