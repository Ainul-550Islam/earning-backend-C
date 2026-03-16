# wallet/tests.py
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction, IntegrityError
from decimal import Decimal
import uuid
from unittest.mock import patch, MagicMock

from .models import Wallet, WalletTransaction, UserPaymentMethod, Withdrawal, WalletWebhookLog
from .serializers import get_safe_value, CircuitBreaker
from .tasks import expire_bonus_balances, user_request_withdrawal

User = get_user_model()


# ============================================
# BULLETPROOF TEST MIXINS
# ============================================

class BulletproofTestMixin:
    """
    Mixin for bulletproof testing patterns
    """
    
    def setUp(self):
        """Common setup for all tests"""
        # Clear cache before each test
        cache.clear()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create admin user
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        # Create wallet for test user
        self.wallet = Wallet.objects.create(
            user=self.user,
            current_balance=Decimal('1000.00'),
            pending_balance=Decimal('100.00'),
            total_earned=Decimal('1500.00'),
            total_withdrawn=Decimal('500.00'),
            frozen_balance=Decimal('50.00'),
            currency='BDT'
        )
    
    def assert_decimal_equal(self, first, second, msg=None, places=2):
        """Compare Decimal values with precision"""
        if msg is None:
            msg = f"{first} != {second}"
        self.assertEqual(
            first.quantize(Decimal('0.' + '0' * places)),
            second.quantize(Decimal('0.' + '0' * places)),
            msg
        )
    
    def assert_safe_value(self, obj, key, expected, default=None):
        """Test get_safe_value function"""
        result = get_safe_value(obj, key, default)
        self.assertEqual(result, expected)


# ============================================
# MODEL TESTS
# ============================================

class WalletModelTests(BulletproofTestMixin, TestCase):
    """Bulletproof Wallet model tests"""
    
    def test_wallet_creation(self):
        """Test wallet creation with default values"""
        wallet = Wallet.objects.create(user=self.user)
        
        self.assertEqual(wallet.currency, 'BDT')
        self.assert_decimal_equal(wallet.current_balance, Decimal('0.00'))
        self.assert_decimal_equal(wallet.available_balance, Decimal('0.00'))
        self.assertFalse(wallet.is_locked)
    
    def test_available_balance_calculation(self):
        """Test available balance calculation"""
        self.assert_decimal_equal(
            self.wallet.available_balance,
            Decimal('950.00')  # 1000 - 50
        )
    
    def test_wallet_lock_unlock(self):
        """Test wallet lock and unlock functionality"""
        # Test lock
        self.wallet.lock("Suspicious activity")
        self.wallet.refresh_from_db()
        
        self.assertTrue(self.wallet.is_locked)
        self.assertEqual(self.wallet.locked_reason, "Suspicious activity")
        self.assertIsNotNone(self.wallet.locked_at)
        
        # Test unlock
        self.wallet.unlock()
        self.wallet.refresh_from_db()
        
        self.assertFalse(self.wallet.is_locked)
        self.assertEqual(self.wallet.locked_reason, '')
        self.assertIsNone(self.wallet.locked_at)
    
    def test_freeze_unfreeze(self):
        """Test freeze and unfreeze functionality"""
        initial_balance = self.wallet.current_balance
        initial_frozen = self.wallet.frozen_balance
        
        # Test freeze
        self.wallet.freeze(Decimal('100.00'), "Test freeze")
        self.wallet.refresh_from_db()
        
        self.assert_decimal_equal(
            self.wallet.current_balance,
            initial_balance - Decimal('100.00')
        )
        self.assert_decimal_equal(
            self.wallet.frozen_balance,
            initial_frozen + Decimal('100.00')
        )
        
        # Test unfreeze
        self.wallet.unfreeze(Decimal('50.00'), "Partial unfreeze")
        self.wallet.refresh_from_db()
        
        self.assert_decimal_equal(
            self.wallet.current_balance,
            initial_balance - Decimal('50.00')
        )
        self.assert_decimal_equal(
            self.wallet.frozen_balance,
            initial_frozen + Decimal('50.00')
        )
    
    def test_freeze_insufficient_balance(self):
        """Test freeze with insufficient balance"""
        with self.assertRaises(ValueError):
            self.wallet.freeze(Decimal('5000.00'), "Too much")
    
    def test_unfreeze_exceeds_frozen(self):
        """Test unfreeze exceeding frozen amount"""
        self.wallet.freeze(Decimal('100.00'), "Test")
        
        with self.assertRaises(ValueError):
            self.wallet.unfreeze(Decimal('200.00'), "Too much")


class WalletTransactionModelTests(BulletproofTestMixin, TransactionTestCase):
    """Bulletproof WalletTransaction model tests"""
    
    def test_transaction_creation(self):
        """Test transaction creation"""
        trans = WalletTransaction.objects.create(
            wallet=self.wallet,
            type='earning',
            amount=Decimal('100.00'),
            status='approved',
            description="Test transaction",
            balance_before=self.wallet.current_balance,
            created_by=self.user
        )
        
        self.assertIsNotNone(trans.transaction_id)
        self.assertEqual(trans.wallet, self.wallet)
        self.assertEqual(trans.type, 'earning')
        self.assert_decimal_equal(trans.amount, Decimal('100.00'))
        self.assertEqual(trans.status, 'approved')
    
    def test_transaction_approval(self):
        """Test transaction approval"""
        trans = WalletTransaction.objects.create(
            wallet=self.wallet,
            type='earning',
            amount=Decimal('100.00'),
            status='pending',
            balance_before=self.wallet.current_balance,
            created_by=self.user
        )
        
        initial_balance = self.wallet.current_balance
        
        # Approve transaction
        trans.approve(approved_by=self.admin)
        trans.refresh_from_db()
        self.wallet.refresh_from_db()
        
        self.assertEqual(trans.status, 'approved')
        self.assertIsNotNone(trans.approved_at)
        self.assertEqual(trans.approved_by, self.admin)
        self.assert_decimal_equal(
            trans.balance_after,
            initial_balance + Decimal('100.00')
        )
        self.assert_decimal_equal(
            self.wallet.current_balance,
            initial_balance + Decimal('100.00')
        )
    
    def test_transaction_rejection(self):
        """Test transaction rejection"""
        trans = WalletTransaction.objects.create(
            wallet=self.wallet,
            type='earning',
            amount=Decimal('100.00'),
            status='pending',
            description="Test",
            created_by=self.user
        )
        
        trans.reject(reason="Invalid transaction")
        trans.refresh_from_db()
        
        self.assertEqual(trans.status, 'rejected')
        self.assertIn("Rejected: Invalid transaction", trans.description)
    
    def test_transaction_reversal(self):
        """Test transaction reversal"""
        # Create and approve a transaction
        trans = WalletTransaction.objects.create(
            wallet=self.wallet,
            type='earning',
            amount=Decimal('100.00'),
            status='approved',
            balance_before=self.wallet.current_balance,
            created_by=self.user,
            approved_by=self.admin,
            approved_at=timezone.now()
        )
        
        initial_balance = self.wallet.current_balance
        self.wallet.current_balance += Decimal('100.00')
        self.wallet.save()
        trans.balance_after = self.wallet.current_balance
        trans.save()
        
        # Reverse the transaction
        reversal = trans.reverse(
            reason="Test reversal",
            reversed_by=self.admin
        )
        
        trans.refresh_from_db()
        reversal.refresh_from_db()
        self.wallet.refresh_from_db()
        
        self.assertTrue(trans.is_reversed)
        self.assertIsNotNone(trans.reversed_at)
        self.assertEqual(trans.reversed_by, reversal)
        
        self.assertEqual(reversal.type, 'reversal')
        self.assert_decimal_equal(reversal.amount, Decimal('-100.00'))
        
        self.assert_decimal_equal(self.wallet.current_balance, initial_balance)
    
    def test_approve_non_pending_transaction(self):
        """Test approving non-pending transaction"""
        trans = WalletTransaction.objects.create(
            wallet=self.wallet,
            type='earning',
            amount=Decimal('100.00'),
            status='approved',
            created_by=self.user
        )
        
        with self.assertRaises(ValueError):
            trans.approve(approved_by=self.admin)
    
    def test_reject_non_pending_transaction(self):
        """Test rejecting non-pending transaction"""
        trans = WalletTransaction.objects.create(
            wallet=self.wallet,
            type='earning',
            amount=Decimal('100.00'),
            status='approved',
            created_by=self.user
        )
        
        with self.assertRaises(ValueError):
            trans.reject(reason="Test")


class UserPaymentMethodTests(BulletproofTestMixin, TestCase):
    """Bulletproof UserPaymentMethod tests"""
    
    def setUp(self):
        super().setUp()
        self.payment_method = UserPaymentMethod.objects.create(
            user=self.user,
            method_type='bkash',
            account_number='01712345678',
            account_name='Test User',
            is_verified=True,
            is_primary=True
        )
    
    def test_payment_method_creation(self):
        """Test payment method creation"""
        self.assertEqual(self.payment_method.user, self.user)
        self.assertEqual(self.payment_method.method_type, 'bkash')
        self.assertEqual(self.payment_method.account_number, '01712345678')
        self.assertTrue(self.payment_method.is_verified)
        self.assertTrue(self.payment_method.is_primary)
    
    def test_only_one_primary(self):
        """Test only one primary payment method per user"""
        # Try to create another primary method
        another_method = UserPaymentMethod.objects.create(
            user=self.user,
            method_type='nagad',
            account_number='01812345678',
            account_name='Test User',
            is_primary=True
        )
        
        # Refresh both from DB
        self.payment_method.refresh_from_db()
        another_method.refresh_from_db()
        
        # Only the new one should be primary
        self.assertFalse(self.payment_method.is_primary)
        self.assertTrue(another_method.is_primary)


class WithdrawalModelTests(BulletproofTestMixin, TransactionTestCase):
    """Bulletproof Withdrawal model tests"""
    
    def setUp(self):
        super().setUp()
        
        # Create payment method
        self.payment_method = UserPaymentMethod.objects.create(
            user=self.user,
            method_type='bkash',
            account_number='01712345678',
            account_name='Test User',
            is_verified=True
        )
        
        # Create transaction for withdrawal
        self.transaction = WalletTransaction.objects.create(
            wallet=self.wallet,
            type='withdrawal',
            amount=Decimal('-100.00'),
            status='pending',
            created_by=self.user
        )
        
        # Create withdrawal
        self.withdrawal = Withdrawal.objects.create(
            user=self.user,
            wallet=self.wallet,
            payment_method=self.payment_method,
            amount=Decimal('100.00'),
            fee=Decimal('5.00'),
            net_amount=Decimal('95.00'),
            status='pending',
            transaction=self.transaction
        )
    
    def test_withdrawal_creation(self):
        """Test withdrawal creation"""
        self.assertIsNotNone(self.withdrawal.withdrawal_id)
        self.assertEqual(self.withdrawal.user, self.user)
        self.assertEqual(self.withdrawal.wallet, self.wallet)
        self.assert_decimal_equal(self.withdrawal.amount, Decimal('100.00'))
        self.assert_decimal_equal(self.withdrawal.fee, Decimal('5.00'))
        self.assert_decimal_equal(self.withdrawal.net_amount, Decimal('95.00'))
        self.assertEqual(self.withdrawal.status, 'pending')
    
    def test_withdrawal_save_net_amount(self):
        """Test net amount calculation on save"""
        withdrawal = Withdrawal(
            user=self.user,
            wallet=self.wallet,
            amount=Decimal('200.00'),
            fee=Decimal('10.00')
        )
        
        # Net amount should be calculated on save
        withdrawal.save()
        
        self.assert_decimal_equal(withdrawal.net_amount, Decimal('190.00'))
    
    def test_withdrawal_string_representation(self):
        """Test withdrawal string representation"""
        expected = f"{self.withdrawal.withdrawal_id} - {self.user.username} - 100.00"
        self.assertEqual(str(self.withdrawal), expected)


# ============================================
# SERIALIZER TESTS
# ============================================

class GetSafeValueTests(TestCase):
    """Tests for get_safe_value helper function"""
    
    def test_dict_get_existing_key(self):
        """Test getting existing key from dict"""
        data = {'name': 'John', 'age': 30}
        result = get_safe_value(data, 'name', 'Unknown')
        self.assertEqual(result, 'John')
    
    def test_dict_get_missing_key(self):
        """Test getting missing key from dict"""
        data = {'name': 'John'}
        result = get_safe_value(data, 'age', 0)
        self.assertEqual(result, 0)
    
    def test_object_get_existing_attribute(self):
        """Test getting existing attribute from object"""
        class Person:
            name = 'John'
            age = 30
        
        person = Person()
        result = get_safe_value(person, 'name', 'Unknown')
        self.assertEqual(result, 'John')
    
    def test_object_get_missing_attribute(self):
        """Test getting missing attribute from object"""
        class Person:
            name = 'John'
        
        person = Person()
        result = get_safe_value(person, 'age', 0)
        self.assertEqual(result, 0)
    
    def test_type_validation_correct(self):
        """Test type validation with correct type"""
        data = {'amount': '100.50'}
        result = get_safe_value(data, 'amount', Decimal('0'), Decimal)
        self.assertIsInstance(result, Decimal)
        self.assert_decimal_equal(result, Decimal('100.50'))
    
    def test_type_validation_incorrect(self):
        """Test type validation with incorrect type"""
        data = {'amount': 'invalid'}
        result = get_safe_value(data, 'amount', Decimal('0'), Decimal)
        self.assert_decimal_equal(result, Decimal('0'))


class CircuitBreakerTests(TestCase):
    """Tests for CircuitBreaker class"""
    
    def test_circuit_breaker_success(self):
        """Test circuit breaker with successful operation"""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        
        with cb as breaker:
            # Simulate successful operation
            pass
        
        self.assertEqual(cb.state, 'CLOSED')
        self.assertEqual(cb.failures, 0)
    
    def test_circuit_breaker_failure(self):
        """Test circuit breaker with failing operation"""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
        
        # First failure
        try:
            with cb:
                raise ConnectionError("First failure")
        except ConnectionError:
            pass
        
        self.assertEqual(cb.failures, 1)
        self.assertEqual(cb.state, 'CLOSED')
        
        # Second failure - should trip
        try:
            with cb:
                raise ConnectionError("Second failure")
        except ConnectionError:
            pass
        
        self.assertEqual(cb.failures, 2)
        self.assertEqual(cb.state, 'OPEN')
    
    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery"""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)  # 1 second recovery
        
        # Trip the breaker
        cb.failures = 2
        cb.state = 'OPEN'
        cb.last_failure_time = timezone.now() - timezone.timedelta(seconds=2)
        
        # Should allow after recovery timeout
        with self.assertRaises(ConnectionError):
            with cb:
                raise ConnectionError("Test")
        
        # State should be HALF_OPEN
        self.assertEqual(cb.state, 'HALF_OPEN')


# ============================================
# TASK TESTS (Mocked)
# ============================================

class TaskTests(BulletproofTestMixin, TestCase):
    """Bulletproof task tests"""
    
    @patch('wallet.tasks.timezone.sleep', return_value=None)
    def test_expire_bonus_balances(self, mock_sleep):
        """Test bonus expiration task"""
        # Create wallet with expired bonus
        expired_wallet = Wallet.objects.create(
            user=self.user,
            bonus_balance=Decimal('50.00'),
            bonus_expires_at=timezone.now() - timezone.timedelta(days=1)
        )
        
        # Create wallet with non-expired bonus
        active_wallet = Wallet.objects.create(
            user=self.admin,
            bonus_balance=Decimal('100.00'),
            bonus_expires_at=timezone.now() + timezone.timedelta(days=1)
        )
        
        # Run task
        result = expire_bonus_balances()
        
        # Check results
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['expired_count'], 1)
        self.assertEqual(float(result['refunded_amount']), 50.00)
        
        # Refresh wallets
        expired_wallet.refresh_from_db()
        active_wallet.refresh_from_db()
        
        # Check expired wallet
        self.assert_decimal_equal(expired_wallet.bonus_balance, Decimal('0.00'))
        self.assertIsNone(expired_wallet.bonus_expires_at)
        
        # Check active wallet (should not change)
        self.assert_decimal_equal(active_wallet.bonus_balance, Decimal('100.00'))
        self.assertIsNotNone(active_wallet.bonus_expires_at)
    
    @patch('wallet.tasks.CircuitBreaker')
    def test_user_request_withdrawal_success(self, mock_circuit_breaker):
        """Test successful withdrawal request task"""
        # Create verified payment method
        payment_method = UserPaymentMethod.objects.create(
            user=self.user,
            method_type='bkash',
            account_number='01712345678',
            account_name='Test User',
            is_verified=True
        )
        
        # Mock circuit breaker
        mock_instance = MagicMock()
        mock_circuit_breaker.return_value.__enter__.return_value = mock_instance
        
        # Run task
        result = user_request_withdrawal(
            self.user.id,
            Decimal('100.00'),
            payment_method.id
        )
        
        # Check result
        self.assertEqual(result['status'], 'success')
        self.assertIn('withdrawal_id', result)
        self.assertEqual(float(result['amount']), 100.00)
        self.assertEqual(float(result['net_amount']), 85.00)  # 100 - (100*0.015=10)
        
        # Check withdrawal was created
        withdrawal = Withdrawal.objects.get(
            user=self.user,
            amount=Decimal('100.00')
        )
        self.assertIsNotNone(withdrawal)
    
    def test_user_request_withdrawal_insufficient_balance(self):
        """Test withdrawal request with insufficient balance"""
        payment_method = UserPaymentMethod.objects.create(
            user=self.user,
            method_type='bkash',
            account_number='01712345678',
            account_name='Test User',
            is_verified=True
        )
        
        # Try to withdraw more than available
        result = user_request_withdrawal(
            self.user.id,
            Decimal('10000.00'),  # More than balance
            payment_method.id
        )
        
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['code'], 'INSUFFICIENT_BALANCE')
    
    def test_user_request_withdrawal_locked_wallet(self):
        """Test withdrawal request with locked wallet"""
        # Lock wallet
        self.wallet.lock("Test lock")
        
        payment_method = UserPaymentMethod.objects.create(
            user=self.user,
            method_type='bkash',
            account_number='01712345678',
            account_name='Test User',
            is_verified=True
        )
        
        result = user_request_withdrawal(
            self.user.id,
            Decimal('100.00'),
            payment_method.id
        )
        
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['code'], 'WALLET_LOCKED')


# ============================================
# INTEGRATION TESTS
# ============================================

class IntegrationTests(BulletproofTestMixin, TransactionTestCase):
    """Bulletproof integration tests"""
    
    def test_complete_withdrawal_flow(self):
        """Test complete withdrawal flow"""
        # 1. Create payment method
        payment_method = UserPaymentMethod.objects.create(
            user=self.user,
            method_type='bkash',
            account_number='01712345678',
            account_name='Test User',
            is_verified=True
        )
        
        initial_balance = self.wallet.current_balance
        
        # 2. Create withdrawal request
        result = user_request_withdrawal(
            self.user.id,
            Decimal('100.00'),
            payment_method.id
        )
        
        self.assertEqual(result['status'], 'success')
        
        # 3. Check wallet balance reduced
        self.wallet.refresh_from_db()
        self.assert_decimal_equal(
            self.wallet.current_balance,
            initial_balance - Decimal('100.00')
        )
        
        # 4. Check withdrawal record
        withdrawal = Withdrawal.objects.get(
            withdrawal_id=result['withdrawal_id']
        )
        self.assertEqual(withdrawal.status, 'pending')
        
        # 5. Check transaction record
        transaction = withdrawal.transaction
        self.assertEqual(transaction.type, 'withdrawal')
        self.assert_decimal_equal(transaction.amount, Decimal('-100.00'))
        
        # 6. Process withdrawal (simulate admin action)
        withdrawal.status = 'completed'
        withdrawal.processed_at = timezone.now()
        withdrawal.save()
        
        transaction.status = 'completed'
        transaction.approved_at = timezone.now()
        transaction.save()
        
        # 7. Verify final state
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, 'completed')
        self.assertIsNotNone(withdrawal.processed_at)
    
    def test_transaction_reversal_flow(self):
        """Test complete transaction reversal flow"""
        # Create a transaction
        transaction = WalletTransaction.objects.create(
            wallet=self.wallet,
            type='earning',
            amount=Decimal('100.00'),
            status='approved',
            balance_before=self.wallet.current_balance,
            created_by=self.user,
            approved_by=self.admin,
            approved_at=timezone.now()
        )
        
        initial_balance = self.wallet.current_balance
        
        # Update wallet balance
        self.wallet.current_balance += Decimal('100.00')
        self.wallet.save()
        transaction.balance_after = self.wallet.current_balance
        transaction.save()
        
        # Reverse transaction
        reversal = transaction.reverse(
            reason="Test reversal",
            reversed_by=self.admin
        )
        
        # Verify reversal
        transaction.refresh_from_db()
        self.assertTrue(transaction.is_reversed)
        self.assertEqual(transaction.reversed_by, reversal)
        
        # Verify wallet balance restored
        self.wallet.refresh_from_db()
        self.assert_decimal_equal(self.wallet.current_balance, initial_balance)
        
        # Verify reversal transaction
        self.assertEqual(reversal.type, 'reversal')
        self.assert_decimal_equal(reversal.amount, Decimal('-100.00'))


# ============================================
# PERFORMANCE TESTS
# ============================================

class PerformanceTests(BulletproofTestMixin, TestCase):
    """Bulletproof performance tests"""
    
    def test_bulk_transaction_performance(self):
        """Test performance of bulk transaction operations"""
        import time
        
        # Create 1000 transactions
        start_time = time.time()
        
        transactions = []
        for i in range(1000):
            transactions.append(WalletTransaction(
                wallet=self.wallet,
                type='earning',
                amount=Decimal('1.00'),
                status='pending',
                description=f"Test transaction {i}",
                balance_before=self.wallet.current_balance,
                created_by=self.user
            ))
        
        # Bulk create
        WalletTransaction.objects.bulk_create(transactions)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete in reasonable time
        self.assertLess(duration, 5.0)  # Less than 5 seconds
        
        # Verify count
        count = WalletTransaction.objects.filter(wallet=self.wallet).count()
        self.assertEqual(count, 1000)
    
    def test_query_optimization(self):
        """Test query optimization with select_related"""
        # Create related objects
        payment_method = UserPaymentMethod.objects.create(
            user=self.user,
            method_type='bkash',
            account_number='01712345678',
            account_name='Test User'
        )
        
        transaction = WalletTransaction.objects.create(
            wallet=self.wallet,
            type='withdrawal',
            amount=Decimal('-100.00'),
            status='pending',
            created_by=self.user
        )
        
        withdrawal = Withdrawal.objects.create(
            user=self.user,
            wallet=self.wallet,
            payment_method=payment_method,
            amount=Decimal('100.00'),
            transaction=transaction
        )
        
        # Test optimized query
        with self.assertNumQueries(1):  # Should use only 1 query
            withdrawal = Withdrawal.objects.select_related(
                'user', 'wallet', 'payment_method', 'transaction'
            ).get(id=withdrawal.id)
            
            # Access related fields (should not trigger extra queries)
            username = withdrawal.user.username
            wallet_balance = withdrawal.wallet.current_balance
            method_type = withdrawal.payment_method.method_type
            trans_type = withdrawal.transaction.type


# ============================================
# ERROR HANDLING TESTS
# ============================================

class ErrorHandlingTests(BulletproofTestMixin, TestCase):
    """Bulletproof error handling tests"""
    
    def test_graceful_degradation_on_missing_data(self):
        """Test graceful handling of missing data"""
        # Test with None object
        result = get_safe_value(None, 'name', 'Default')
        self.assertEqual(result, 'Default')
        
        # Test with empty dict
        result = get_safe_value({}, 'amount', Decimal('0'), Decimal)
        self.assert_decimal_equal(result, Decimal('0'))
        
        # Test with invalid Decimal conversion
        result = get_safe_value({'amount': 'invalid'}, 'amount', Decimal('0'), Decimal)
        self.assert_decimal_equal(result, Decimal('0'))
    
    def test_transaction_atomic_rollback(self):
        """Test transaction rollback on error"""
        initial_balance = self.wallet.current_balance
        
        try:
            with transaction.atomic():
                # Create transaction
                WalletTransaction.objects.create(
                    wallet=self.wallet,
                    type='earning',
                    amount=Decimal('100.00'),
                    status='approved',
                    balance_before=self.wallet.current_balance
                )
                
                # Update wallet
                self.wallet.current_balance += Decimal('100.00')
                self.wallet.save()
                
                # Simulate error
                raise ValueError("Simulated error")
                
        except ValueError:
            pass
        
        # Wallet balance should be unchanged (rolled back)
        self.wallet.refresh_from_db()
        self.assert_decimal_equal(self.wallet.current_balance, initial_balance)
        
        # Transaction should not exist
        count = WalletTransaction.objects.filter(wallet=self.wallet).count()
        self.assertEqual(count, 0)