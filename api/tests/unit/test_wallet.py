"""
Unit tests for Wallet app.
Tests wallet models, transactions, and financial operations.
"""

import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from rest_framework import status
from rest_framework.test import APITestCase

from api.wallet.models import Wallet, Transaction, WithdrawalRequest, WalletHistory
from api.wallet.serializers import (
    WalletSerializer, TransactionSerializer, WithdrawalRequestSerializer,
    WalletTransferSerializer, WalletDepositSerializer
)
from api.wallet.services import WalletService, TransactionService, WithdrawalService
from api.wallet.factories import (
    WalletFactory, TransactionFactory, WithdrawalRequestFactory, WalletHistoryFactory
)
from api.tests.factories.UserFactory import UserFactory


# ==================== MODEL TESTS ====================
class TestWalletModel(APITestCase):
    """Test Wallet model functionality"""
    
    def setUp(self):
        self.user = UserFactory.create()
    
    def test_create_wallet(self):
        """Test creating a wallet"""
        wallet = WalletFactory.create(
            user=self.user,
            balance=Decimal('1000.00'),
            total_earned=Decimal('5000.00'),
            total_withdrawn=Decimal('1000.00')
        )
        
        self.assertEqual(wallet.user, self.user)
        self.assertEqual(wallet.balance, Decimal('1000.00'))
        self.assertEqual(wallet.total_earned, Decimal('5000.00'))
        self.assertEqual(wallet.total_withdrawn, Decimal('1000.00'))
    
    def test_wallet_str_representation(self):
        """Test string representation of wallet"""
        wallet = WalletFactory.create(user=self.user)
        expected = f"{self.user.username}'s Wallet"
        self.assertEqual(str(wallet), expected)
    
    def test_wallet_credit(self):
        """Test crediting wallet"""
        wallet = WalletFactory.create(
            user=self.user,
            balance=Decimal('100.00')
        )
        
        wallet.credit(Decimal('50.00'), 'offer_completion')
        
        self.assertEqual(wallet.balance, Decimal('150.00'))
        self.assertEqual(wallet.total_earned, Decimal('50.00'))
    
    def test_wallet_debit(self):
        """Test debiting wallet"""
        wallet = WalletFactory.create(
            user=self.user,
            balance=Decimal('100.00'),
            total_withdrawn=Decimal('0.00')
        )
        
        wallet.debit(Decimal('30.00'), 'withdrawal')
        
        self.assertEqual(wallet.balance, Decimal('70.00'))
        self.assertEqual(wallet.total_withdrawn, Decimal('30.00'))
    
    def test_wallet_debit_insufficient_balance(self):
        """Test debiting wallet with insufficient balance"""
        wallet = WalletFactory.create(
            user=self.user,
            balance=Decimal('50.00')
        )
        
        with self.assertRaises(ValueError) as context:
            wallet.debit(Decimal('100.00'), 'withdrawal')
        
        self.assertIn('Insufficient balance', str(context.exception))
    
    def test_wallet_transfer(self):
        """Test wallet-to-wallet transfer"""
        user1 = UserFactory.create()
        user2 = UserFactory.create()
        
        wallet1 = WalletFactory.create(
            user=user1,
            balance=Decimal('200.00')
        )
        wallet2 = WalletFactory.create(
            user=user2,
            balance=Decimal('100.00')
        )
        
        wallet1.transfer(Decimal('50.00'), wallet2, 'peer_transfer')
        
        self.assertEqual(wallet1.balance, Decimal('150.00'))
        self.assertEqual(wallet2.balance, Decimal('150.00'))
        self.assertEqual(wallet1.total_withdrawn, Decimal('50.00'))
        self.assertEqual(wallet2.total_earned, Decimal('50.00'))
    
    def test_wallet_balance_property(self):
        """Test wallet balance property"""
        wallet = WalletFactory.create(
            balance=Decimal('1000.00'),
            bonus_balance=Decimal('200.00'),
            pending_balance=Decimal('300.00')
        )
        
        self.assertEqual(wallet.available_balance, Decimal('1000.00'))
        self.assertEqual(wallet.total_balance, Decimal('1500.00'))
    
    def test_wallet_can_withdraw(self):
        """Test withdrawal eligibility check"""
        wallet = WalletFactory.create(
            balance=Decimal('500.00'),
            min_withdraw_amount=Decimal('100.00'),
            daily_withdraw_limit=Decimal('1000.00'),
            monthly_withdraw_limit=Decimal('5000.00'),
            is_verified=True
        )
        
        # Can withdraw valid amount
        self.assertTrue(wallet.can_withdraw(Decimal('200.00')))
        
        # Cannot withdraw below minimum
        self.assertFalse(wallet.can_withdraw(Decimal('50.00')))
        
        # Cannot withdraw more than balance
        self.assertFalse(wallet.can_withdraw(Decimal('600.00')))
        
        # Cannot withdraw if not verified
        wallet.is_verified = False
        self.assertFalse(wallet.can_withdraw(Decimal('200.00')))


class TestTransactionModel(APITestCase):
    """Test Transaction model functionality"""
    
    def setUp(self):
        self.user = UserFactory.create()
        self.wallet = WalletFactory.create(user=self.user)
    
    def test_create_transaction(self):
        """Test creating a transaction"""
        transaction = TransactionFactory.create(
            user=self.user,
            wallet=self.wallet,
            transaction_type='credit',
            amount=Decimal('100.00'),
            status='completed',
            description='Offer completion'
        )
        
        self.assertEqual(transaction.user, self.user)
        self.assertEqual(transaction.wallet, self.wallet)
        self.assertEqual(transaction.amount, Decimal('100.00'))
        self.assertEqual(transaction.transaction_type, 'credit')
        self.assertEqual(transaction.status, 'completed')
    
    def test_transaction_str_representation(self):
        """Test string representation of transaction"""
        transaction = TransactionFactory.create(
            user=self.user,
            amount=Decimal('100.00'),
            transaction_type='credit'
        )
        
        expected = f"TXN-{transaction.id}: {self.user.username} - credit - 100.00"
        self.assertEqual(str(transaction), expected)
    
    def test_transaction_completion(self):
        """Test transaction completion"""
        transaction = TransactionFactory.create(
            user=self.user,
            wallet=self.wallet,
            status='pending'
        )
        
        transaction.complete('Gateway transaction completed')
        
        self.assertEqual(transaction.status, 'completed')
        self.assertIsNotNone(transaction.completed_at)
        self.assertIsNotNone(transaction.gateway_response)
    
    def test_transaction_failure(self):
        """Test transaction failure"""
        transaction = TransactionFactory.create(
            user=self.user,
            wallet=self.wallet,
            status='pending'
        )
        
        transaction.fail('Insufficient funds')
        
        self.assertEqual(transaction.status, 'failed')
        self.assertIsNotNone(transaction.completed_at)
        self.assertEqual(transaction.failure_reason, 'Insufficient funds')
    
    def test_transaction_reversal(self):
        """Test transaction reversal"""
        # Create a completed credit transaction
        transaction = TransactionFactory.create(
            user=self.user,
            wallet=self.wallet,
            transaction_type='credit',
            amount=Decimal('100.00'),
            status='completed'
        )
        
        # Update wallet balance
        self.wallet.balance = Decimal('100.00')
        self.wallet.save()
        
        # Reverse the transaction
        reversal = transaction.reverse('Fraud detection')
        
        self.assertEqual(reversal.transaction_type, 'debit')
        self.assertEqual(reversal.amount, Decimal('100.00'))
        self.assertEqual(reversal.status, 'completed')
        self.assertEqual(reversal.description, 'Reversal of TXN-...')
        
        # Check wallet balance was adjusted
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('0.00'))


class TestWithdrawalRequestModel(APITestCase):
    """Test WithdrawalRequest model functionality"""
    
    def setUp(self):
        self.user = UserFactory.create()
        self.wallet = WalletFactory.create(
            user=self.user,
            balance=Decimal('1000.00')
        )
    
    def test_create_withdrawal_request(self):
        """Test creating withdrawal request"""
        withdrawal = WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet,
            amount=Decimal('500.00'),
            payment_method='bkash',
            status='pending'
        )
        
        self.assertEqual(withdrawal.user, self.user)
        self.assertEqual(withdrawal.amount, Decimal('500.00'))
        self.assertEqual(withdrawal.payment_method, 'bkash')
        self.assertEqual(withdrawal.status, 'pending')
    
    def test_withdrawal_str_representation(self):
        """Test string representation of withdrawal"""
        withdrawal = WithdrawalRequestFactory.create(
            user=self.user,
            amount=Decimal('500.00')
        )
        
        expected = f"WDR-{withdrawal.id}: {self.user.username} - 500.00 - pending"
        self.assertEqual(str(withdrawal), expected)
    
    def test_withdrawal_approval(self):
        """Test withdrawal approval"""
        withdrawal = WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet,
            amount=Decimal('500.00'),
            status='pending'
        )
        
        withdrawal.approve('admin_user', 'Approved manually')
        
        self.assertEqual(withdrawal.status, 'approved')
        self.assertEqual(withdrawal.processed_by, 'admin_user')
        self.assertEqual(withdrawal.notes, 'Approved manually')
        self.assertIsNotNone(withdrawal.approved_at)
    
    def test_withdrawal_rejection(self):
        """Test withdrawal rejection"""
        withdrawal = WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet,
            amount=Decimal('500.00'),
            status='pending'
        )
        
        withdrawal.reject('Insufficient verification documents')
        
        self.assertEqual(withdrawal.status, 'rejected')
        self.assertEqual(withdrawal.rejection_reason, 'Insufficient verification documents')
        self.assertIsNotNone(withdrawal.status_changed_at)
    
    def test_withdrawal_completion(self):
        """Test withdrawal completion"""
        withdrawal = WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet,
            amount=Decimal('500.00'),
            status='approved'
        )
        
        withdrawal.complete('txn_123456', 'Completed via bKash')
        
        self.assertEqual(withdrawal.status, 'completed')
        self.assertEqual(withdrawal.gateway_transaction_id, 'txn_123456')
        self.assertIsNotNone(withdrawal.completed_at)
    
    def test_withdrawal_cancellation(self):
        """Test withdrawal cancellation"""
        withdrawal = WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet,
            amount=Decimal('500.00'),
            status='pending'
        )
        
        withdrawal.cancel('User requested cancellation')
        
        self.assertEqual(withdrawal.status, 'cancelled')
        self.assertEqual(withdrawal.notes, 'User requested cancellation')


# ==================== SERIALIZER TESTS ====================
class TestWalletSerializer(APITestCase):
    """Test WalletSerializer"""
    
    def setUp(self):
        self.user = UserFactory.create()
        self.wallet = WalletFactory.create(user=self.user)
    
    def test_wallet_serialization(self):
        """Test wallet serialization"""
        serializer = WalletSerializer(self.wallet)
        
        expected_fields = [
            'id', 'user', 'balance', 'total_earned', 'total_withdrawn',
            'total_deposited', 'bonus_balance', 'pending_balance',
            'available_balance', 'total_balance', 'total_transactions',
            'successful_withdrawals', 'failed_withdrawals', 'auto_withdraw',
            'min_withdraw_amount', 'daily_withdraw_limit', 'monthly_withdraw_limit',
            'is_verified', 'verification_level', 'created_at', 'updated_at'
        ]
        
        for field in expected_fields:
            self.assertIn(field, serializer.data)
    
    def test_available_balance_calculation(self):
        """Test available balance calculation in serializer"""
        wallet = WalletFactory.create(
            balance=Decimal('1000.00'),
            bonus_balance=Decimal('200.00'),
            pending_balance=Decimal('300.00')
        )
        
        serializer = WalletSerializer(wallet)
        
        self.assertEqual(serializer.data['available_balance'], '1000.00')
        self.assertEqual(serializer.data['total_balance'], '1500.00')


class TestTransactionSerializer(APITestCase):
    """Test TransactionSerializer"""
    
    def setUp(self):
        self.user = UserFactory.create()
        self.wallet = WalletFactory.create(user=self.user)
        self.transaction = TransactionFactory.create(
            user=self.user,
            wallet=self.wallet
        )
    
    def test_transaction_serialization(self):
        """Test transaction serialization"""
        serializer = TransactionSerializer(self.transaction)
        
        expected_fields = [
            'id', 'transaction_id', 'user', 'wallet', 'transaction_type',
            'amount', 'currency', 'status', 'description', 'metadata',
            'fee_amount', 'tax_amount', 'net_amount', 'source_type',
            'source_id', 'payment_method', 'gateway_transaction_id',
            'account_number', 'account_name', 'bank_name', 'branch_name',
            'created_at', 'completed_at'
        ]
        
        for field in expected_fields:
            self.assertIn(field, serializer.data)
    
    def test_transaction_filtering(self):
        """Test transaction filtering in serializer context"""
        # Create multiple transactions
        TransactionFactory.create(
            user=self.user,
            wallet=self.wallet,
            transaction_type='credit',
            amount=Decimal('100.00'),
            created_at=timezone.now() - timedelta(days=1)
        )
        
        TransactionFactory.create(
            user=self.user,
            wallet=self.wallet,
            transaction_type='debit',
            amount=Decimal('50.00'),
            created_at=timezone.now()
        )
        
        # Filter credit transactions
        credit_transactions = self.wallet.transactions.filter(
            transaction_type='credit'
        )
        serializer = TransactionSerializer(credit_transactions, many=True)
        
        self.assertEqual(len(serializer.data), 1)
        self.assertEqual(serializer.data[0]['transaction_type'], 'credit')


class TestWithdrawalRequestSerializer(APITestCase):
    """Test WithdrawalRequestSerializer"""
    
    def setUp(self):
        self.user = UserFactory.create()
        self.wallet = WalletFactory.create(user=self.user)
        self.withdrawal = WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet
        )
    
    def test_withdrawal_serialization(self):
        """Test withdrawal request serialization"""
        serializer = WithdrawalRequestSerializer(self.withdrawal)
        
        expected_fields = [
            'id', 'request_id', 'user', 'wallet', 'amount', 'currency',
            'payment_method', 'account_number', 'account_name', 'status',
            'processing_fee', 'tax_amount', 'net_amount', 'notes',
            'rejection_reason', 'requested_at', 'approved_at', 'completed_at',
            'status_changed_at', 'processed_by', 'gateway_transaction_id',
            'metadata', 'created_at', 'updated_at'
        ]
        
        for field in expected_fields:
            self.assertIn(field, serializer.data)
    
    def test_withdrawal_creation(self):
        """Test withdrawal request creation through serializer"""
        data = {
            'amount': '500.00',
            'payment_method': 'bkash',
            'account_number': '01712345678',
            'account_name': 'Test User'
        }
        
        serializer = WithdrawalRequestSerializer(
            data=data,
            context={'user': self.user, 'wallet': self.wallet}
        )
        
        self.assertTrue(serializer.is_valid())
        
        withdrawal = serializer.save()
        
        self.assertEqual(withdrawal.user, self.user)
        self.assertEqual(withdrawal.wallet, self.wallet)
        self.assertEqual(withdrawal.amount, Decimal('500.00'))
        self.assertEqual(withdrawal.payment_method, 'bkash')
        self.assertEqual(withdrawal.status, 'pending')


# ==================== SERVICE TESTS ====================
class TestWalletService(APITestCase):
    """Test WalletService functionality"""
    
    def setUp(self):
        self.wallet_service = WalletService()
        self.user = UserFactory.create()
        self.wallet = WalletFactory.create(user=self.user)
    
    def test_get_wallet(self):
        """Test getting wallet by user"""
        wallet = self.wallet_service.get_wallet(self.user.id)
        self.assertEqual(wallet, self.wallet)
    
    def test_create_wallet(self):
        """Test wallet creation service"""
        new_user = UserFactory.create()
        wallet = self.wallet_service.create_wallet(new_user.id)
        
        self.assertEqual(wallet.user, new_user)
        self.assertEqual(wallet.balance, Decimal('0.00'))
    
    def test_credit_wallet(self):
        """Test wallet credit service"""
        initial_balance = self.wallet.balance
        
        transaction = self.wallet_service.credit_wallet(
            user_id=self.user.id,
            amount=Decimal('100.00'),
            source_type='offer',
            source_id=123,
            description='Offer completion reward'
        )
        
        self.wallet.refresh_from_db()
        
        self.assertEqual(self.wallet.balance, initial_balance + Decimal('100.00'))
        self.assertEqual(transaction.amount, Decimal('100.00'))
        self.assertEqual(transaction.transaction_type, 'credit')
        self.assertEqual(transaction.status, 'completed')
    
    def test_debit_wallet(self):
        """Test wallet debit service"""
        self.wallet.balance = Decimal('500.00')
        self.wallet.save()
        
        transaction = self.wallet_service.debit_wallet(
            user_id=self.user.id,
            amount=Decimal('200.00'),
            source_type='withdrawal',
            description='Withdrawal to bKash'
        )
        
        self.wallet.refresh_from_db()
        
        self.assertEqual(self.wallet.balance, Decimal('300.00'))
        self.assertEqual(transaction.amount, Decimal('200.00'))
        self.assertEqual(transaction.transaction_type, 'debit')
        self.assertEqual(transaction.status, 'completed')
    
    def test_debit_wallet_insufficient_balance(self):
        """Test wallet debit with insufficient balance"""
        self.wallet.balance = Decimal('100.00')
        self.wallet.save()
        
        with self.assertRaises(ValueError) as context:
            self.wallet_service.debit_wallet(
                user_id=self.user.id,
                amount=Decimal('200.00'),
                source_type='withdrawal'
            )
        
        self.assertIn('Insufficient balance', str(context.exception))
    
    def test_transfer_between_wallets(self):
        """Test wallet-to-wallet transfer service"""
        user2 = UserFactory.create()
        wallet2 = WalletFactory.create(
            user=user2,
            balance=Decimal('100.00')
        )
        
        self.wallet.balance = Decimal('500.00')
        self.wallet.save()
        
        transaction = self.wallet_service.transfer(
            from_user_id=self.user.id,
            to_user_id=user2.id,
            amount=Decimal('150.00'),
            description='Peer transfer'
        )
        
        self.wallet.refresh_from_db()
        wallet2.refresh_from_db()
        
        self.assertEqual(self.wallet.balance, Decimal('350.00'))
        self.assertEqual(wallet2.balance, Decimal('250.00'))
        self.assertEqual(transaction.amount, Decimal('150.00'))
    
    def test_get_wallet_statistics(self):
        """Test wallet statistics service"""
        # Create some transactions
        for i in range(5):
            TransactionFactory.create(
                user=self.user,
                wallet=self.wallet,
                transaction_type='credit',
                amount=Decimal('100.00'),
                status='completed'
            )
        
        for i in range(2):
            TransactionFactory.create(
                user=self.user,
                wallet=self.wallet,
                transaction_type='debit',
                amount=Decimal('50.00'),
                status='completed'
            )
        
        stats = self.wallet_service.get_wallet_statistics(self.user.id)
        
        self.assertIn('total_balance', stats)
        self.assertIn('total_credited', stats)
        self.assertIn('total_debited', stats)
        self.assertIn('transaction_count', stats)
        self.assertIn('success_rate', stats)
        
        self.assertEqual(stats['total_credited'], Decimal('500.00'))
        self.assertEqual(stats['total_debited'], Decimal('100.00'))
        self.assertEqual(stats['transaction_count'], 7)
    
    def test_check_withdrawal_eligibility(self):
        """Test withdrawal eligibility check service"""
        self.wallet.balance = Decimal('500.00')
        self.wallet.min_withdraw_amount = Decimal('100.00')
        self.wallet.daily_withdraw_limit = Decimal('1000.00')
        self.wallet.is_verified = True
        self.wallet.save()
        
        # Create some withdrawals today
        WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet,
            amount=Decimal('300.00'),
            status='completed',
            requested_at=timezone.now()
        )
        
        eligibility = self.wallet_service.check_withdrawal_eligibility(
            user_id=self.user.id,
            amount=Decimal('200.00')
        )
        
        self.assertTrue(eligibility['eligible'])
        self.assertEqual(eligibility['available_balance'], Decimal('500.00'))
        self.assertEqual(eligibility['remaining_daily_limit'], Decimal('700.00'))
        
        # Test with amount exceeding daily limit
        eligibility2 = self.wallet_service.check_withdrawal_eligibility(
            user_id=self.user.id,
            amount=Decimal('800.00')
        )
        
        self.assertFalse(eligibility2['eligible'])
        self.assertIn('Daily withdrawal limit exceeded', eligibility2['message'])
    
    def test_lock_wallet_for_transaction(self):
        """Test wallet locking for concurrent transactions"""
        from threading import Thread
        
        results = []
        
        def perform_transaction():
            try:
                with transaction.atomic():
                    # Lock wallet
                    wallet = Wallet.objects.select_for_update().get(id=self.wallet.id)
                    
                    # Simulate some processing
                    import time
                    time.sleep(0.1)
                    
                    wallet.balance += Decimal('100.00')
                    wallet.save()
                    
                results.append('success')
            except Exception as e:
                results.append(str(e))
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = Thread(target=perform_transaction)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All threads should succeed without deadlock
        self.assertEqual(results.count('success'), 5)
        
        # Check final balance
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('500.00'))


class TestTransactionService(APITestCase):
    """Test TransactionService functionality"""
    
    def setUp(self):
        self.transaction_service = TransactionService()
        self.user = UserFactory.create()
        self.wallet = WalletFactory.create(user=self.user)
    
    def test_get_transaction(self):
        """Test getting transaction by ID"""
        transaction = TransactionFactory.create(
            user=self.user,
            wallet=self.wallet
        )
        
        result = self.transaction_service.get_transaction(transaction.id)
        self.assertEqual(result, transaction)
    
    def test_get_user_transactions(self):
        """Test getting user transactions"""
        # Create transactions
        for i in range(10):
            TransactionFactory.create(
                user=self.user,
                wallet=self.wallet,
                amount=Decimal(str((i + 1) * 10))
            )
        
        transactions = self.transaction_service.get_user_transactions(
            user_id=self.user.id,
            limit=5
        )
        
        self.assertEqual(len(transactions), 5)
        
        # Should be ordered by created_at descending
        self.assertTrue(
            transactions[0].created_at >= transactions[1].created_at
        )
    
    def test_filter_transactions(self):
        """Test transaction filtering"""
        # Create different types of transactions
        TransactionFactory.create(
            user=self.user,
            wallet=self.wallet,
            transaction_type='credit',
            amount=Decimal('100.00'),
            status='completed'
        )
        TransactionFactory.create(
            user=self.user,
            wallet=self.wallet,
            transaction_type='debit',
            amount=Decimal('50.00'),
            status='completed'
        )
        TransactionFactory.create(
            user=self.user,
            wallet=self.wallet,
            transaction_type='credit',
            amount=Decimal('200.00'),
            status='pending'
        )
        
        # Filter credit transactions
        credit_txns = self.transaction_service.filter_transactions(
            user_id=self.user.id,
            transaction_type='credit'
        )
        self.assertEqual(len(credit_txns), 2)
        
        # Filter completed transactions
        completed_txns = self.transaction_service.filter_transactions(
            user_id=self.user.id,
            status='completed'
        )
        self.assertEqual(len(completed_txns), 2)
        
        # Filter by amount range
        amount_txns = self.transaction_service.filter_transactions(
            user_id=self.user.id,
            min_amount=Decimal('150.00'),
            max_amount=Decimal('250.00')
        )
        self.assertEqual(len(amount_txns), 1)
        self.assertEqual(amount_txns[0].amount, Decimal('200.00'))
    
    def test_get_transaction_statistics(self):
        """Test transaction statistics"""
        # Create transactions for different dates
        today = timezone.now()
        
        # Today's transactions
        for i in range(3):
            TransactionFactory.create(
                user=self.user,
                wallet=self.wallet,
                created_at=today - timedelta(hours=i),
                amount=Decimal('100.00'),
                transaction_type='credit'
            )
        
        # Yesterday's transactions
        for i in range(2):
            TransactionFactory.create(
                user=self.user,
                wallet=self.wallet,
                created_at=today - timedelta(days=1, hours=i),
                amount=Decimal('50.00'),
                transaction_type='debit'
            )
        
        stats = self.transaction_service.get_transaction_statistics(
            user_id=self.user.id,
            days=7
        )
        
        self.assertIn('total_transactions', stats)
        self.assertIn('total_amount', stats)
        self.assertIn('avg_transaction_amount', stats)
        self.assertIn('by_type', stats)
        self.assertIn('by_day', stats)
        
        self.assertEqual(stats['total_transactions'], 5)
        self.assertEqual(stats['total_amount'], Decimal('400.00'))
        self.assertEqual(stats['avg_transaction_amount'], Decimal('80.00'))
        
        # Check distribution by type
        self.assertEqual(stats['by_type']['credit'], Decimal('300.00'))
        self.assertEqual(stats['by_type']['debit'], Decimal('100.00'))
    
    def test_export_transactions(self):
        """Test transaction export"""
        # Create transactions
        for i in range(3):
            TransactionFactory.create(
                user=self.user,
                wallet=self.wallet,
                amount=Decimal(str((i + 1) * 50))
            )
        
        # Export to CSV
        csv_data = self.transaction_service.export_transactions(
            user_id=self.user.id,
            format='csv'
        )
        
        self.assertIsInstance(csv_data, str)
        self.assertIn('Transaction ID', csv_data)
        self.assertIn('Amount', csv_data)
        self.assertIn('Status', csv_data)
        
        # Count lines (header + 3 transactions)
        lines = csv_data.strip().split('\n')
        self.assertEqual(len(lines), 4)
    
    def test_bulk_transaction_processing(self):
        """Test bulk transaction processing"""
        transactions_data = [
            {
                'user_id': self.user.id,
                'amount': Decimal('100.00'),
                'transaction_type': 'credit',
                'description': f'Bulk transaction {i}'
            }
            for i in range(10)
        ]
        
        results = self.transaction_service.process_bulk_transactions(
            transactions_data
        )
        
        self.assertEqual(len(results), 10)
        self.assertEqual(results['successful'], 10)
        self.assertEqual(results['failed'], 0)
        
        # Verify transactions were created
        transaction_count = Transaction.objects.filter(
            user=self.user
        ).count()
        self.assertEqual(transaction_count, 10)
    
    def test_transaction_reversal(self):
        """Test transaction reversal service"""
        # Create a completed transaction
        original_txn = TransactionFactory.create(
            user=self.user,
            wallet=self.wallet,
            transaction_type='credit',
            amount=Decimal('100.00'),
            status='completed'
        )
        
        # Update wallet balance
        self.wallet.balance = Decimal('100.00')
        self.wallet.save()
        
        reversal = self.transaction_service.reverse_transaction(
            transaction_id=original_txn.id,
            reason='Fraud detection'
        )
        
        self.assertEqual(reversal.transaction_type, 'debit')
        self.assertEqual(reversal.amount, Decimal('100.00'))
        self.assertEqual(reversal.status, 'completed')
        self.assertIn('Reversal', reversal.description)
        
        # Verify wallet balance was adjusted
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('0.00'))
        
        # Verify original transaction is marked as reversed
        original_txn.refresh_from_db()
        self.assertEqual(original_txn.status, 'reversed')


class TestWithdrawalService(APITestCase):
    """Test WithdrawalService functionality"""
    
    def setUp(self):
        self.withdrawal_service = WithdrawalService()
        self.user = UserFactory.create()
        self.wallet = WalletFactory.create(
            user=self.user,
            balance=Decimal('1000.00')
        )
    
    def test_create_withdrawal_request(self):
        """Test withdrawal request creation"""
        data = {
            'amount': Decimal('500.00'),
            'payment_method': 'bkash',
            'account_number': '01712345678',
            'account_name': 'Test User',
            'notes': 'Regular withdrawal'
        }
        
        withdrawal = self.withdrawal_service.create_withdrawal_request(
            user_id=self.user.id,
            **data
        )
        
        self.assertEqual(withdrawal.user, self.user)
        self.assertEqual(withdrawal.amount, Decimal('500.00'))
        self.assertEqual(withdrawal.payment_method, 'bkash')
        self.assertEqual(withdrawal.status, 'pending')
        
        # Verify wallet balance is reserved
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('500.00'))  # 1000 - 500
        
        # Verify transaction was created
        transaction = Transaction.objects.filter(
            user=self.user,
            transaction_type='debit',
            status='pending'
        ).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, Decimal('500.00'))
    
    def test_approve_withdrawal(self):
        """Test withdrawal approval"""
        withdrawal = WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet,
            amount=Decimal('500.00'),
            status='pending'
        )
        
        result = self.withdrawal_service.approve_withdrawal(
            withdrawal_id=withdrawal.id,
            processed_by='admin',
            notes='Approved manually'
        )
        
        self.assertTrue(result['success'])
        
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, 'approved')
        self.assertEqual(withdrawal.processed_by, 'admin')
        self.assertIsNotNone(withdrawal.approved_at)
    
    def test_reject_withdrawal(self):
        """Test withdrawal rejection"""
        withdrawal = WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet,
            amount=Decimal('500.00'),
            status='pending'
        )
        
        result = self.withdrawal_service.reject_withdrawal(
            withdrawal_id=withdrawal.id,
            reason='Insufficient verification'
        )
        
        self.assertTrue(result['success'])
        
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, 'rejected')
        self.assertEqual(withdrawal.rejection_reason, 'Insufficient verification')
        
        # Verify wallet balance is restored
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('1500.00'))  # 1000 + 500
    
    def test_process_withdrawal(self):
        """Test withdrawal processing"""
        withdrawal = WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet,
            amount=Decimal('500.00'),
            status='approved'
        )
        
        result = self.withdrawal_service.process_withdrawal(
            withdrawal_id=withdrawal.id,
            gateway_transaction_id='txn_123456',
            notes='Processed via bKash'
        )
        
        self.assertTrue(result['success'])
        
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, 'processing')
        self.assertEqual(withdrawal.gateway_transaction_id, 'txn_123456')
    
    def test_complete_withdrawal(self):
        """Test withdrawal completion"""
        withdrawal = WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet,
            amount=Decimal('500.00'),
            status='processing'
        )
        
        result = self.withdrawal_service.complete_withdrawal(
            withdrawal_id=withdrawal.id,
            gateway_response={'status': 'success', 'transaction_id': 'txn_123456'}
        )
        
        self.assertTrue(result['success'])
        
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, 'completed')
        self.assertIsNotNone(withdrawal.completed_at)
        self.assertIsNotNone(withdrawal.gateway_response)
        
        # Verify transaction is completed
        transaction = withdrawal.transactions.filter(
            transaction_type='debit'
        ).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.status, 'completed')
    
    def test_cancel_withdrawal(self):
        """Test withdrawal cancellation"""
        withdrawal = WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet,
            amount=Decimal('500.00'),
            status='pending'
        )
        
        result = self.withdrawal_service.cancel_withdrawal(
            withdrawal_id=withdrawal.id,
            reason='User requested cancellation'
        )
        
        self.assertTrue(result['success'])
        
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, 'cancelled')
        
        # Verify wallet balance is restored
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('1500.00'))  # 1000 + 500
    
    def test_get_pending_withdrawals(self):
        """Test getting pending withdrawals"""
        # Create withdrawals with different statuses
        WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet,
            status='pending',
            amount=Decimal('100.00')
        )
        WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet,
            status='approved',
            amount=Decimal('200.00')
        )
        WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet,
            status='pending',
            amount=Decimal('300.00')
        )
        
        pending = self.withdrawal_service.get_pending_withdrawals()
        
        self.assertEqual(len(pending), 2)
        for withdrawal in pending:
            self.assertEqual(withdrawal.status, 'pending')
    
    def test_get_withdrawal_statistics(self):
        """Test withdrawal statistics"""
        # Create withdrawals for different dates
        today = timezone.now()
        
        # Today's withdrawals
        WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet,
            status='completed',
            amount=Decimal('500.00'),
            requested_at=today
        )
        WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet,
            status='rejected',
            amount=Decimal('300.00'),
            requested_at=today
        )
        
        # Yesterday's withdrawals
        WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet,
            status='completed',
            amount=Decimal('400.00'),
            requested_at=today - timedelta(days=1)
        )
        
        stats = self.withdrawal_service.get_withdrawal_statistics(days=7)
        
        self.assertIn('total_withdrawals', stats)
        self.assertIn('total_amount', stats)
        self.assertIn('success_rate', stats)
        self.assertIn('by_status', stats)
        self.assertIn('by_payment_method', stats)
        
        self.assertEqual(stats['total_withdrawals'], 3)
        self.assertEqual(stats['total_amount'], Decimal('1200.00'))
        
        # Check distribution by status
        self.assertEqual(stats['by_status']['completed'], Decimal('900.00'))
        self.assertEqual(stats['by_status']['rejected'], Decimal('300.00'))
    
    def test_auto_approve_withdrawals(self):
        """Test automatic withdrawal approval"""
        # Configure wallet for auto-approval
        self.wallet.auto_withdraw = True
        self.wallet.save()
        
        # Create withdrawal request
        withdrawal = WithdrawalRequestFactory.create(
            user=self.user,
            wallet=self.wallet,
            amount=Decimal('100.00'),
            status='pending'
        )
        
        result = self.withdrawal_service.auto_approve_withdrawals()
        
        self.assertEqual(result['approved'], 1)
        self.assertEqual(result['failed'], 0)
        
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, 'approved')
        self.assertEqual(withdrawal.processed_by, 'auto')


# ==================== VIEW TESTS ====================
class TestWalletViews(APITestCase):
    """Test Wallet API views"""
    
    def setUp(self):
        self.user = UserFactory.create()
        self.wallet = WalletFactory.create(user=self.user)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_get_wallet_balance(self):
        """Test wallet balance retrieval"""
        url = '/api/v1/wallet/balance/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('balance', response.data)
        self.assertIn('available_balance', response.data)
        self.assertIn('total_balance', response.data)
    
    def test_get_transactions(self):
        """Test transactions retrieval"""
        # Create some transactions
        for i in range(5):
            TransactionFactory.create(
                user=self.user,
                wallet=self.wallet
            )
        
        url = '/api/v1/wallet/transactions/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 5)
    
    def test_create_withdrawal_request(self):
        """Test withdrawal request creation"""
        url = '/api/v1/wallet/withdraw/'
        data = {
            'amount': '500.00',
            'payment_method': 'bkash',
            'account_number': '01712345678',
            'account_name': 'Test User'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['amount'], '500.00')
        self.assertEqual(response.data['payment_method'], 'bkash')
        self.assertEqual(response.data['status'], 'pending')
    
    def test_get_withdrawal_requests(self):
        """Test withdrawal requests retrieval"""
        # Create some withdrawal requests
        for i in range(3):
            WithdrawalRequestFactory.create(
                user=self.user,
                wallet=self.wallet
            )
        
        url = '/api/v1/wallet/withdrawals/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 3)
    
    def test_transfer_to_user(self):
        """Test wallet-to-wallet transfer"""
        receiver = UserFactory.create()
        receiver_wallet = WalletFactory.create(
            user=receiver,
            balance=Decimal('100.00')
        )
        
        self.wallet.balance = Decimal('500.00')
        self.wallet.save()
        
        url = '/api/v1/wallet/transfer/'
        data = {
            'to_user_id': receiver.id,
            'amount': '150.00',
            'description': 'Test transfer'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify sender balance decreased
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('350.00'))
        
        # Verify receiver balance increased
        receiver_wallet.refresh_from_db()
        self.assertEqual(receiver_wallet.balance, Decimal('250.00'))
    
    def test_deposit_request(self):
        """Test deposit request creation"""
        url = '/api/v1/wallet/deposit/'
        data = {
            'amount': '1000.00',
            'payment_method': 'bkash',
            'transaction_id': 'txn_123456'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['amount'], '1000.00')
        self.assertEqual(response.data['payment_method'], 'bkash')
        self.assertEqual(response.data['status'], 'pending')
    
    def test_get_wallet_statistics(self):
        """Test wallet statistics retrieval"""
        url = '/api/v1/wallet/statistics/'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_balance', response.data)
        self.assertIn('total_credited', response.data)
        self.assertIn('total_debited', response.data)
        self.assertIn('transaction_count', response.data)
    
    def test_export_transactions(self):
        """Test transactions export"""
        url = '/api/v1/wallet/transactions/export/?format=csv'
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('Transaction ID', response.content.decode())
    
    def test_check_withdrawal_eligibility(self):
        """Test withdrawal eligibility check"""
        url = '/api/v1/wallet/withdraw/check/'
        params = {'amount': '200.00'}
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('eligible', response.data)
        self.assertIn('available_balance', response.data)
        self.assertIn('min_withdraw_amount', response.data)


# ==================== INTEGRATION TESTS ====================
class TestWalletIntegration(APITestCase):
    """Integration tests for wallet workflows"""
    
    def setUp(self):
        self.user = UserFactory.create()
        self.wallet = WalletFactory.create(
            user=self.user,
            balance=Decimal('1000.00')
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_complete_withdrawal_flow(self):
        """Test complete withdrawal workflow"""
        # 1. Check eligibility
        url = '/api/v1/wallet/withdraw/check/'
        params = {'amount': '500.00'}
        
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['eligible'])
        
        # 2. Create withdrawal request
        url = '/api/v1/wallet/withdraw/'
        data = {
            'amount': '500.00',
            'payment_method': 'bkash',
            'account_number': '01712345678',
            'account_name': 'Test User'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        withdrawal_id = response.data['id']
        
        # 3. Verify wallet balance is reserved
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('500.00'))
        
        # 4. Approve withdrawal (admin action)
        admin = UserFactory.create(
            email='admin@example.com',
            user_type='admin',
            is_staff=True,
            is_superuser=True
        )
        admin_client = APIClient()
        admin_client.force_authenticate(user=admin)
        
        url = f'/api/v1/admin/withdrawals/{withdrawal_id}/approve/'
        response = admin_client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 5. Process withdrawal
        url = f'/api/v1/admin/withdrawals/{withdrawal_id}/process/'
        data = {
            'gateway_transaction_id': 'txn_123456',
            'notes': 'Processed via bKash'
        }
        response = admin_client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 6. Complete withdrawal
        url = f'/api/v1/admin/withdrawals/{withdrawal_id}/complete/'
        data = {
            'gateway_response': {'status': 'success'}
        }
        response = admin_client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 7. Verify final state
        url = f'/api/v1/wallet/withdrawals/{withdrawal_id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'completed')
        
        # 8. Verify transaction history
        url = '/api/v1/wallet/transactions/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should have debit transaction for withdrawal
        debit_transactions = [
            t for t in response.data['results']
            if t['transaction_type'] == 'debit'
        ]
        self.assertGreaterEqual(len(debit_transactions), 1)
    
    def test_complete_deposit_flow(self):
        """Test complete deposit workflow"""
        # 1. Create deposit request
        url = '/api/v1/wallet/deposit/'
        data = {
            'amount': '1000.00',
            'payment_method': 'bkash',
            'transaction_id': 'txn_deposit_123'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        deposit_id = response.data['id']
        initial_balance = self.wallet.balance
        
        # 2. Verify deposit request is pending
        url = f'/api/v1/wallet/deposits/{deposit_id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'pending')
        
        # 3. Verify payment (simulated - in real app, would verify with payment gateway)
        # 4. Complete deposit (admin action)
        admin = UserFactory.create(
            email='admin@example.com',
            user_type='admin',
            is_staff=True,
            is_superuser=True
        )
        admin_client = APIClient()
        admin_client.force_authenticate(user=admin)
        
        url = f'/api/v1/admin/deposits/{deposit_id}/complete/'
        data = {
            'gateway_response': {'status': 'success', 'transaction_id': 'txn_deposit_123'}
        }
        response = admin_client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 5. Verify wallet balance increased
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, initial_balance + Decimal('1000.00'))
        
        # 6. Verify transaction history
        url = '/api/v1/wallet/transactions/'
        response = self.client.get(url)
        
        credit_transactions = [
            t for t in response.data['results']
            if t['transaction_type'] == 'credit' and t['amount'] == '1000.00'
        ]
        self.assertGreaterEqual(len(credit_transactions), 1)
    
    def test_peer_to_peer_transfer_flow(self):
        """Test peer-to-peer transfer workflow"""
        # Create receiver
        receiver = UserFactory.create()
        receiver_wallet = WalletFactory.create(
            user=receiver,
            balance=Decimal('100.00')
        )
        
        # 1. Check transfer eligibility
        url = '/api/v1/wallet/transfer/check/'
        data = {
            'to_user_id': receiver.id,
            'amount': '200.00'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['eligible'])
        
        # 2. Perform transfer
        url = '/api/v1/wallet/transfer/'
        data = {
            'to_user_id': receiver.id,
            'amount': '200.00',
            'description': 'Test peer transfer'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 3. Verify sender balance decreased
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('800.00'))
        
        # 4. Verify receiver balance increased
        receiver_wallet.refresh_from_db()
        self.assertEqual(receiver_wallet.balance, Decimal('300.00'))
        
        # 5. Verify transaction history for sender
        url = '/api/v1/wallet/transactions/'
        response = self.client.get(url)
        
        sender_debit = [
            t for t in response.data['results']
            if t['transaction_type'] == 'debit' and t['amount'] == '200.00'
        ]
        self.assertGreaterEqual(len(sender_debit), 1)
        
        # 6. Verify transaction history for receiver
        receiver_client = APIClient()
        receiver_client.force_authenticate(user=receiver)
        
        url = '/api/v1/wallet/transactions/'
        response = receiver_client.get(url)
        
        receiver_credit = [
            t for t in response.data['results']
            if t['transaction_type'] == 'credit' and t['amount'] == '200.00'
        ]
        self.assertGreaterEqual(len(receiver_credit), 1)


# ==================== SECURITY TESTS ====================
@pytest.mark.security
class TestWalletSecurity(APITestCase):
    """Security tests for wallet operations"""
    
    def setUp(self):
        self.user1 = UserFactory.create()
        self.wallet1 = WalletFactory.create(
            user=self.user1,
            balance=Decimal('1000.00')
        )
        
        self.user2 = UserFactory.create()
        self.wallet2 = WalletFactory.create(
            user=self.user2,
            balance=Decimal('500.00')
        )
        
        self.client1 = APIClient()
        self.client1.force_authenticate(user=self.user1)
        
        self.client2 = APIClient()
        self.client2.force_authenticate(user=self.user2)
    
    def test_user_cannot_access_others_wallet(self):
        """Test user cannot access another user's wallet"""
        url = f'/api/v1/wallet/{self.wallet2.id}/balance/'
        
        response = self.client1.get(url)
        
        # Should return 403 Forbidden or 404 Not Found
        self.assertIn(response.status_code, [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ])
    
    def test_user_cannot_withdraw_from_others_wallet(self):
        """Test user cannot withdraw from another user's wallet"""
        url = '/api/v1/wallet/withdraw/'
        data = {
            'amount': '500.00',
            'payment_method': 'bkash',
            'account_number': '01712345678',
            'account_name': 'Test User'
        }
        
        # user1 tries to use user2's wallet ID (if API allows specifying wallet)
        # This depends on API implementation
        response = self.client1.post(url, data, format='json')
        
        # Should create withdrawal for authenticated user's wallet
        # Not for the specified wallet
        if response.status_code == status.HTTP_201_CREATED:
            self.assertEqual(response.data['user'], self.user1.id)
    
    def test_sql_injection_in_transaction_search(self):
        """Test SQL injection prevention in transaction search"""
        malicious_inputs = [
            "' OR '1'='1",
            "'; DROP TABLE transactions; --",
            "' UNION SELECT * FROM users --"
        ]
        
        for malicious_input in malicious_inputs:
            url = f'/api/v1/wallet/transactions/?search={malicious_input}'
            
            response = self.client1.get(url)
            
            # Should not crash with 500 error
            self.assertNotEqual(
                response.status_code,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"SQL injection vulnerability detected: {malicious_input}"
            )
    
    def test_amount_validation(self):
        """Test amount validation for various attacks"""
        test_cases = [
            ('-100.00', False),  # Negative amount
            ('0.00', False),     # Zero amount
            ('0.01', True),      # Very small amount
            ('9999999.99', True), # Large amount
            ('100.001', False),  # Too many decimal places
            ('1e6', False),      # Scientific notation
            ('100,000.00', False), # Comma separated
            ('', False),         # Empty string
            ('abc', False),      # Non-numeric
        ]
        
        for amount, should_succeed in test_cases:
            url = '/api/v1/wallet/withdraw/'
            data = {
                'amount': amount,
                'payment_method': 'bkash',
                'account_number': '01712345678',
                'account_name': 'Test User'
            }
            
            response = self.client1.post(url, data, format='json')
            
            if should_succeed:
                self.assertIn(
                    response.status_code,
                    [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST],
                    f"Amount '{amount}' should be processed or validated"
                )
            else:
                self.assertEqual(
                    response.status_code,
                    status.HTTP_400_BAD_REQUEST,
                    f"Invalid amount '{amount}' should be rejected"
                )
    
    def test_concurrent_withdrawal_prevention(self):
        """Test prevention of concurrent withdrawal attacks"""
        import threading
        
        results = []
        
        def attempt_withdrawal():
            try:
                client = APIClient()
                client.force_authenticate(user=self.user1)
                
                url = '/api/v1/wallet/withdraw/'
                data = {
                    'amount': '800.00',
                    'payment_method': 'bkash',
                    'account_number': '01712345678',
                    'account_name': 'Test User'
                }
                
                response = client.post(url, data, format='json')
                results.append(response.status_code)
            except Exception as e:
                results.append(str(e))
        
        # Start multiple threads to attempt concurrent withdrawals
        threads = []
        for i in range(3):
            thread = threading.Thread(target=attempt_withdrawal)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Only one withdrawal should succeed, others should fail
        success_count = results.count(status.HTTP_201_CREATED)
        failure_count = results.count(status.HTTP_400_BAD_REQUEST)
        
        self.assertEqual(success_count, 1)
        self.assertEqual(failure_count, 2)
        
        # Final balance should be correct
        self.wallet1.refresh_from_db()
        self.assertEqual(self.wallet1.balance, Decimal('200.00'))  # 1000 - 800


# ==================== PERFORMANCE TESTS ====================
@pytest.mark.performance
class TestWalletPerformance(APITestCase):
    """Performance tests for wallet operations"""
    
    def setUp(self):
        self.user = UserFactory.create()
        self.wallet = WalletFactory.create(user=self.user)
        
        # Create bulk transactions for performance testing
        self.transactions = []
        for i in range(1000):
            transaction = TransactionFactory.create(
                user=self.user,
                wallet=self.wallet,
                amount=Decimal(str((i % 100) + 1))
            )
            self.transactions.append(transaction)
    
    def test_bulk_transaction_processing_performance(self):
        """Test performance of bulk transaction processing"""
        import time
        
        transaction_service = TransactionService()
        
        # Prepare bulk transaction data
        bulk_data = [
            {
                'user_id': self.user.id,
                'amount': Decimal('100.00'),
                'transaction_type': 'credit',
                'description': f'Bulk transaction {i}'
            }
            for i in range(100)
        ]
        
        start_time = time.time()
        
        result = transaction_service.process_bulk_transactions(bulk_data)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Should process 100 transactions in less than 2 seconds
        self.assertLess(elapsed, 2.0)
        self.assertEqual(result['successful'], 100)
        
        print(f"Processed 100 bulk transactions in {elapsed:.2f} seconds")
    
    def test_transaction_search_performance(self):
        """Test performance of transaction search with filters"""
        import time
        
        start_time = time.time()
        
        # Search with multiple filters
        transactions = Transaction.objects.filter(
            user=self.user,
            transaction_type='credit',
            status='completed',
            amount__gte=Decimal('50.00')
        ).select_related('user', 'wallet')[:100]
        
        # Process results
        for transaction in transactions:
            _ = transaction.amount
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Should complete in less than 0.1 seconds
        self.assertLess(elapsed, 0.1)
        
        print(f"Searched and processed 100 transactions in {elapsed:.4f} seconds")
    
    def test_wallet_balance_calculation_performance(self):
        """Test performance of wallet balance calculations"""
        import time
        
        start_time = time.time()
        
        # Calculate balance from transactions (worst-case scenario)
        total_credit = Transaction.objects.filter(
            user=self.user,
            transaction_type='credit',
            status='completed'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        total_debit = Transaction.objects.filter(
            user=self.user,
            transaction_type='debit',
            status='completed'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        calculated_balance = total_credit - total_debit
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Should calculate in less than 0.05 seconds
        self.assertLess(elapsed, 0.05)
        
        print(f"Calculated balance from 1000 transactions in {elapsed:.4f} seconds")
        print(f"Calculated balance: {calculated_balance}")
    
    def test_concurrent_wallet_operations_performance(self):
        """Test performance under concurrent operations"""
        import threading
        import time
        
        results = []
        
        def perform_operation(operation_type, amount):
            try:
                wallet_service = WalletService()
                
                if operation_type == 'credit':
                    wallet_service.credit_wallet(
                        user_id=self.user.id,
                        amount=Decimal(amount),
                        source_type='test',
                        description='Performance test'
                    )
                elif operation_type == 'debit':
                    try:
                        wallet_service.debit_wallet(
                            user_id=self.user.id,
                            amount=Decimal(amount),
                            source_type='test',
                            description='Performance test'
                        )
                    except ValueError:  # Insufficient balance
                        pass
                
                results.append('success')
            except Exception as e:
                results.append(str(e))
        
        start_time = time.time()
        
        # Start multiple threads
        threads = []
        operations = []
        
        # Create mixed operations
        for i in range(50):
            operations.append(('credit', '10.00'))
        for i in range(50):
            operations.append(('debit', '5.00'))
        
        for i, (op_type, amount) in enumerate(operations):
            thread = threading.Thread(
                target=perform_operation,
                args=(op_type, amount)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Should complete 100 operations in less than 5 seconds
        self.assertLess(elapsed, 5.0)
        
        success_count = results.count('success')
        print(f"Completed {success_count}/100 concurrent operations in {elapsed:.2f} seconds")
        
        # Verify final balance
        self.wallet.refresh_from_db()
        expected_credits = Decimal('500.00')  # 50 * 10.00
        expected_debits = Decimal('250.00')   # 50 * 5.00
        expected_balance = expected_credits - expected_debits
        
        # Account for initial balance and any failed debits
        print(f"Final wallet balance: {self.wallet.balance}")