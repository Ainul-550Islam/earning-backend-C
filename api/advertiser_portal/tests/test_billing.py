"""
Test Billing

Comprehensive tests for billing functionality
including wallet management, transactions, and invoicing.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock

from ..models.billing import AdvertiserWallet, AdvertiserTransaction, AdvertiserInvoice
from ..models.advertiser import Advertiser
try:
    from ..services import AdvertiserBillingService
except ImportError:
    AdvertiserBillingService = None
try:
    from ..services import BudgetEnforcementService
except ImportError:
    BudgetEnforcementService = None
try:
    from ..services import AutoRefillService
except ImportError:
    AutoRefillService = None
try:
    from ..services import AdvertiserService
except ImportError:
    AdvertiserService = None

User = get_user_model()


class AdvertiserBillingServiceTestCase(TestCase):
    """Test cases for AdvertiserBillingService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.billing_service = AdvertiserBillingService()
        
        self.advertiser = self.advertiser_service.create_advertiser(
            self.user, 
            {
                'company_name': 'Test Company',
                'contact_email': 'contact@testcompany.com',
                'contact_phone': '+1234567890',
                'website': 'https://testcompany.com',
                'industry': 'technology',
                'company_size': 'medium',
            }
        )
        
        # Fund wallet
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('1000.00')
        wallet.credit_limit = Decimal('2000.00')
        wallet.save()
    
    def test_create_wallet_success(self):
        """Test successful wallet creation."""
        new_user = User.objects.create_user(
            username='newuser',
            email='new@example.com',
            password='newpass123'
        )
        
        new_advertiser = self.advertiser_service.create_advertiser(
            new_user,
            {
                'company_name': 'New Company',
                'contact_email': 'contact@newcompany.com',
                'contact_phone': '+1234567890',
                'website': 'https://newcompany.com',
                'industry': 'technology',
                'company_size': 'small',
            }
        )
        
        wallet = self.billing_service.create_wallet(new_advertiser)
        
        self.assertIsInstance(wallet, AdvertiserWallet)
        self.assertEqual(wallet.advertiser, new_advertiser)
        self.assertEqual(wallet.balance, Decimal('0.00'))
        self.assertEqual(wallet.credit_limit, Decimal('1000.00'))  # Default
        self.assertEqual(wallet.status, 'active')
    
    def test_create_wallet_custom_credit_limit(self):
        """Test wallet creation with custom credit limit."""
        new_user = User.objects.create_user(
            username='newuser2',
            email='new2@example.com',
            password='newpass123'
        )
        
        new_advertiser = self.advertiser_service.create_advertiser(
            new_user,
            {
                'company_name': 'New Company 2',
                'contact_email': 'contact@newcompany2.com',
                'contact_phone': '+1234567890',
                'website': 'https://newcompany2.com',
                'industry': 'finance',
                'company_size': 'large',
            }
        )
        
        wallet = self.billing_service.create_wallet(
            new_advertiser,
            credit_limit=Decimal('5000.00')
        )
        
        self.assertEqual(wallet.credit_limit, Decimal('5000.00'))
    
    def test_get_wallet_balance_success(self):
        """Test successful wallet balance retrieval."""
        balance_info = self.billing_service.get_wallet_balance(self.advertiser)
        
        self.assertIn('available_balance', balance_info)
        self.assertIn('credit_limit', balance_info)
        self.assertIn('used_credit', balance_info)
        self.assertIn('available_credit', balance_info)
        
        self.assertEqual(balance_info['available_balance'], Decimal('1000.00'))
        self.assertEqual(balance_info['credit_limit'], Decimal('2000.00'))
        self.assertEqual(balance_info['available_credit'], Decimal('1000.00'))
    
    def test_deposit_funds_success(self):
        """Test successful funds deposit."""
        deposit_amount = Decimal('500.00')
        payment_method = 'credit_card'
        payment_reference = 'payment_12345'
        
        transaction = self.billing_service.deposit_funds(
            self.advertiser,
            deposit_amount,
            payment_method,
            payment_reference
        )
        
        self.assertIsInstance(transaction, AdvertiserTransaction)
        self.assertEqual(transaction.advertiser, self.advertiser)
        self.assertEqual(transaction.amount, deposit_amount)
        self.assertEqual(transaction.transaction_type, 'deposit')
        self.assertEqual(transaction.status, 'completed')
        self.assertEqual(transaction.payment_method, payment_method)
        self.assertEqual(transaction.payment_reference, payment_reference)
        
        # Check wallet balance
        wallet = self.advertiser.wallet
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('1500.00'))
    
    def test_deposit_funds_invalid_amount(self):
        """Test funds deposit with invalid amount."""
        with self.assertRaises(ValueError) as context:
            self.billing_service.deposit_funds(
                self.advertiser,
                Decimal('-100.00'),  # Negative amount
                'credit_card',
                'payment_12345'
            )
        
        self.assertIn('Deposit amount must be positive', str(context.exception))
    
    def test_charge_funds_success(self):
        """Test successful funds charge."""
        charge_amount = Decimal('200.00')
        description = 'Campaign spend'
        
        transaction = self.billing_service.charge_funds(
            self.advertiser,
            charge_amount,
            description
        )
        
        self.assertIsInstance(transaction, AdvertiserTransaction)
        self.assertEqual(transaction.advertiser, self.advertiser)
        self.assertEqual(transaction.amount, charge_amount)
        self.assertEqual(transaction.transaction_type, 'charge')
        self.assertEqual(transaction.status, 'completed')
        self.assertEqual(transaction.description, description)
        
        # Check wallet balance
        wallet = self.advertiser.wallet
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('800.00'))
    
    def test_charge_funds_insufficient_balance(self):
        """Test funds charge with insufficient balance."""
        # Set wallet balance to low amount
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('50.00')
        wallet.save()
        
        with self.assertRaises(ValueError) as context:
            self.billing_service.charge_funds(
                self.advertiser,
                Decimal('100.00'),  # More than available
                'Campaign spend'
            )
        
        self.assertIn('Insufficient wallet balance', str(context.exception))
    
    def test_charge_funds_exceeds_credit_limit(self):
        """Test funds charge that exceeds credit limit."""
        # Set wallet balance to use credit limit
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('1900.00')  # Close to limit
        wallet.save()
        
        with self.assertRaises(ValueError) as context:
            self.billing_service.charge_funds(
                self.advertiser,
                Decimal('200.00'),  # Would exceed limit
                'Campaign spend'
            )
        
        self.assertIn('Charge would exceed credit limit', str(context.exception))
    
    def test_get_transaction_history_success(self):
        """Test successful transaction history retrieval."""
        # Create some transactions
        self.billing_service.deposit_funds(
            self.advertiser,
            Decimal('500.00'),
            'credit_card',
            'payment_12345'
        )
        
        self.billing_service.charge_funds(
            self.advertiser,
            Decimal('100.00'),
            'Campaign spend'
        )
        
        self.billing_service.deposit_funds(
            self.advertiser,
            Decimal('300.00'),
            'bank_transfer',
            'payment_67890'
        )
        
        # Get transaction history
        history = self.billing_service.get_transaction_history(self.advertiser)
        
        self.assertEqual(len(history), 3)
        
        # Check transaction types
        transaction_types = [t.transaction_type for t in history]
        self.assertIn('deposit', transaction_types)
        self.assertIn('charge', transaction_types)
    
    def test_get_transaction_by_id_success(self):
        """Test getting transaction by ID."""
        # Create transaction
        transaction = self.billing_service.deposit_funds(
            self.advertiser,
            Decimal('500.00'),
            'credit_card',
            'payment_12345'
        )
        
        # Get transaction by ID
        retrieved_transaction = self.billing_service.get_transaction_by_id(
            self.advertiser,
            transaction.id
        )
        
        self.assertEqual(retrieved_transaction.id, transaction.id)
        self.assertEqual(retrieved_transaction.amount, Decimal('500.00'))
    
    def test_get_transaction_by_id_not_found(self):
        """Test getting transaction by ID when not found."""
        with self.assertRaises(ValueError) as context:
            self.billing_service.get_transaction_by_id(
                self.advertiser,
                99999  # Non-existent ID
            )
        
        self.assertIn('Transaction not found', str(context.exception))
    
    def test_create_invoice_success(self):
        """Test successful invoice creation."""
        # Create some charges
        for i in range(3):
            self.billing_service.charge_funds(
                self.advertiser,
                Decimal('100.00'),
                f'Campaign spend {i+1}'
            )
        
        # Create invoice for current month
        invoice = self.billing_service.create_invoice(
            self.advertiser,
            timezone.now().date().replace(day=1)
        )
        
        self.assertIsInstance(invoice, AdvertiserInvoice)
        self.assertEqual(invoice.advertiser, self.advertiser)
        self.assertEqual(invoice.status, 'draft')
        self.assertGreater(invoice.total_amount, Decimal('0.00'))
    
    def test_create_invoice_no_transactions(self):
        """Test invoice creation with no transactions."""
        with self.assertRaises(ValueError) as context:
            self.billing_service.create_invoice(
                self.advertiser,
                timezone.now().date().replace(day=1)
            )
        
        self.assertIn('No transactions found for invoice period', str(context.exception))
    
    def test_finalize_invoice_success(self):
        """Test successful invoice finalization."""
        # Create some charges
        for i in range(3):
            self.billing_service.charge_funds(
                self.advertiser,
                Decimal('100.00'),
                f'Campaign spend {i+1}'
            )
        
        # Create and finalize invoice
        invoice = self.billing_service.create_invoice(
            self.advertiser,
            timezone.now().date().replace(day=1)
        )
        
        finalized_invoice = self.billing_service.finalize_invoice(invoice)
        
        self.assertEqual(finalized_invoice.status, 'sent')
        self.assertIsNotNone(finalized_invoice.sent_at)
        self.assertIsNotNone(finalized_invoice.due_date)
    
    def test_pay_invoice_success(self):
        """Test successful invoice payment."""
        # Create some charges
        for i in range(3):
            self.billing_service.charge_funds(
                self.advertiser,
                Decimal('100.00'),
                f'Campaign spend {i+1}'
            )
        
        # Create and finalize invoice
        invoice = self.billing_service.create_invoice(
            self.advertiser,
            timezone.now().date().replace(day=1)
        )
        
        finalized_invoice = self.billing_service.finalize_invoice(invoice)
        
        # Pay invoice
        payment_method = 'credit_card'
        payment_reference = 'payment_invoice_12345'
        
        paid_invoice = self.billing_service.pay_invoice(
            finalized_invoice,
            payment_method,
            payment_reference
        )
        
        self.assertEqual(paid_invoice.status, 'paid')
        self.assertIsNotNone(paid_invoice.paid_at)
        self.assertEqual(paid_invoice.payment_method, payment_method)
        self.assertEqual(paid_invoice.payment_reference, payment_reference)
    
    def test_pay_already_paid_invoice(self):
        """Test paying already paid invoice."""
        # Create some charges
        for i in range(3):
            self.billing_service.charge_funds(
                self.advertiser,
                Decimal('100.00'),
                f'Campaign spend {i+1}'
            )
        
        # Create, finalize, and pay invoice
        invoice = self.billing_service.create_invoice(
            self.advertiser,
            timezone.now().date().replace(day=1)
        )
        
        finalized_invoice = self.billing_service.finalize_invoice(invoice)
        paid_invoice = self.billing_service.pay_invoice(
            finalized_invoice,
            'credit_card',
            'payment_12345'
        )
        
        # Try to pay again
        with self.assertRaises(ValueError) as context:
            self.billing_service.pay_invoice(
                paid_invoice,
                'credit_card',
                'payment_67890'
            )
        
        self.assertIn('Invoice is already paid', str(context.exception))
    
    def test_get_invoice_history_success(self):
        """Test successful invoice history retrieval."""
        # Create multiple invoices
        for i in range(3):
            # Create charges
            for j in range(2):
                self.billing_service.charge_funds(
                    self.advertiser,
                    Decimal('50.00'),
                    f'Campaign spend {i+1}-{j+1}'
                )
            
            # Create invoice for different months
            invoice_date = timezone.now().date().replace(day=1) - timezone.timedelta(days=i*30)
            invoice = self.billing_service.create_invoice(self.advertiser, invoice_date)
            self.billing_service.finalize_invoice(invoice)
        
        # Get invoice history
        history = self.billing_service.get_invoice_history(self.advertiser)
        
        self.assertEqual(len(history), 3)
        
        for invoice in history:
            self.assertEqual(invoice.status, 'sent')
    
    def test_get_billing_statistics_success(self):
        """Test successful billing statistics retrieval."""
        # Create some transactions
        self.billing_service.deposit_funds(
            self.advertiser,
            Decimal('1000.00'),
            'credit_card',
            'payment_12345'
        )
        
        for i in range(5):
            self.billing_service.charge_funds(
                self.advertiser,
                Decimal('100.00'),
                f'Campaign spend {i+1}'
            )
        
        # Get statistics
        stats = self.billing_service.get_billing_statistics(self.advertiser)
        
        self.assertIn('total_deposits', stats)
        self.assertIn('total_charges', stats)
        self.assertIn('net_balance', stats)
        self.assertIn('transaction_count', stats)
        self.assertIn('average_transaction_amount', stats)
        
        self.assertEqual(stats['total_deposits'], Decimal('1000.00'))
        self.assertEqual(stats['total_charges'], Decimal('500.00'))
        self.assertEqual(stats['net_balance'], Decimal('500.00'))
    
    def test_suspend_wallet_success(self):
        """Test successful wallet suspension."""
        suspended_wallet = self.billing_service.suspend_wallet(self.advertiser.wallet)
        
        self.assertEqual(suspended_wallet.status, 'suspended')
        self.assertIsNotNone(suspended_wallet.suspended_at)
    
    def test_suspend_already_suspended_wallet(self):
        """Test suspending already suspended wallet."""
        self.billing_service.suspend_wallet(self.advertiser.wallet)
        
        with self.assertRaises(ValueError) as context:
            self.billing_service.suspend_wallet(self.advertiser.wallet)
        
        self.assertIn('Wallet is already suspended', str(context.exception))
    
    def test_unsuspend_wallet_success(self):
        """Test successful wallet unsuspension."""
        # Suspend wallet first
        self.billing_service.suspend_wallet(self.advertiser.wallet)
        
        # Unsuspend wallet
        unsuspended_wallet = self.billing_service.unsuspend_wallet(self.advertiser.wallet)
        
        self.assertEqual(unsuspended_wallet.status, 'active')
        self.assertIsNone(unsuspended_wallet.suspended_at)
    
    def test_unsuspend_active_wallet(self):
        """Test unsuspending already active wallet."""
        with self.assertRaises(ValueError) as context:
            self.billing_service.unsuspend_wallet(self.advertiser.wallet)
        
        self.assertIn('Wallet is not suspended', str(context.exception))
    
    def test_update_credit_limit_success(self):
        """Test successful credit limit update."""
        new_limit = Decimal('5000.00')
        reason = 'Increased credit limit for good payment history'
        
        updated_wallet = self.billing_service.update_credit_limit(
            self.advertiser.wallet,
            new_limit,
            reason
        )
        
        self.assertEqual(updated_wallet.credit_limit, new_limit)
        self.assertIsNotNone(updated_wallet.credit_limit_updated_at)
        self.assertEqual(updated_wallet.credit_limit_update_reason, reason)
    
    def test_update_credit_limit_invalid_amount(self):
        """Test credit limit update with invalid amount."""
        with self.assertRaises(ValueError) as context:
            self.billing_service.update_credit_limit(
                self.advertiser.wallet,
                Decimal('-1000.00'),  # Negative amount
                'Invalid update'
            )
        
        self.assertIn('Credit limit must be positive', str(context.exception))
    
    def test_get_wallet_activity_summary(self):
        """Test getting wallet activity summary."""
        # Create some transactions
        self.billing_service.deposit_funds(
            self.advertiser,
            Decimal('1000.00'),
            'credit_card',
            'payment_12345'
        )
        
        for i in range(5):
            self.billing_service.charge_funds(
                self.advertiser,
                Decimal('50.00'),
                f'Campaign spend {i+1}'
            )
        
        # Get activity summary
        summary = self.billing_service.get_wallet_activity_summary(
            self.advertiser,
            days=30
        )
        
        self.assertIn('total_transactions', summary)
        self.assertIn('total_deposits', summary)
        self.assertIn('total_charges', summary)
        self.assertIn('net_change', summary)
        self.assertIn('daily_breakdown', summary)
        
        self.assertEqual(summary['total_transactions'], 6)
        self.assertEqual(summary['total_deposits'], Decimal('1000.00'))
        self.assertEqual(summary['total_charges'], Decimal('250.00'))
    
    def test_export_billing_data(self):
        """Test exporting billing data."""
        # Create some transactions
        self.billing_service.deposit_funds(
            self.advertiser,
            Decimal('1000.00'),
            'credit_card',
            'payment_12345'
        )
        
        for i in range(3):
            self.billing_service.charge_funds(
                self.advertiser,
                Decimal('100.00'),
                f'Campaign spend {i+1}'
            )
        
        # Create invoice
        invoice = self.billing_service.create_invoice(
            self.advertiser,
            timezone.now().date().replace(day=1)
        )
        self.billing_service.finalize_invoice(invoice)
        
        # Export data
        export_data = self.billing_service.export_billing_data(
            self.advertiser,
            days=30
        )
        
        self.assertIn('wallet', export_data)
        self.assertIn('transactions', export_data)
        self.assertIn('invoices', export_data)
        self.assertIn('statistics', export_data)
        self.assertIn('export_date', export_data)
        
        # Check data counts
        self.assertEqual(len(export_data['transactions']), 4)
        self.assertEqual(len(export_data['invoices']), 1)
    
    @patch('api.advertiser_portal.services.billing.AdvertiserBillingService.send_notification')
    def test_send_billing_notification(self, mock_send_notification):
        """Test sending billing notification."""
        # Create transaction
        transaction = self.billing_service.deposit_funds(
            self.advertiser,
            Decimal('500.00'),
            'credit_card',
            'payment_12345'
        )
        
        # Send notification
        self.billing_service.send_billing_notification(
            self.advertiser,
            'deposit_completed',
            'Your deposit of $500.00 has been processed successfully',
            {'transaction_id': transaction.id}
        )
        
        mock_send_notification.assert_called_once()
        
        # Check notification data
        call_args = mock_send_notification.call_args
        notification_data = call_args[0][1] if call_args else None
        
        if notification_data:
            self.assertEqual(notification_data['type'], 'deposit_completed')
            self.assertIn('deposit of $500.00', notification_data['message'])


class AutoRefillServiceTestCase(TestCase):
    """Test cases for AutoRefillService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.billing_service = AdvertiserBillingService()
        self.auto_refill_service = AutoRefillService()
        
        self.advertiser = self.advertiser_service.create_advertiser(
            self.user, 
            {
                'company_name': 'Test Company',
                'contact_email': 'contact@testcompany.com',
                'contact_phone': '+1234567890',
                'website': 'https://testcompany.com',
                'industry': 'technology',
                'company_size': 'medium',
            }
        )
        
        # Fund wallet
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('100.00')
        wallet.credit_limit = Decimal('2000.00')
        wallet.save()
    
    def test_enable_auto_refill_success(self):
        """Test successful auto-refill enablement."""
        refill_config = {
            'enabled': True,
            'threshold_amount': Decimal('100.00'),
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
            'max_monthly_refill': Decimal('2000.00'),
        }
        
        config = self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            refill_config
        )
        
        self.assertTrue(config['enabled'])
        self.assertEqual(config['threshold_amount'], Decimal('100.00'))
        self.assertEqual(config['refill_amount'], Decimal('500.00'))
        self.assertEqual(config['payment_method'], 'credit_card')
    
    def test_enable_auto_refill_invalid_config(self):
        """Test auto-refill enablement with invalid config."""
        invalid_config = {
            'enabled': True,
            'threshold_amount': Decimal('-100.00'),  # Invalid threshold
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
        }
        
        with self.assertRaises(ValueError) as context:
            self.auto_refill_service.enable_auto_refill(
                self.advertiser.wallet,
                invalid_config
            )
        
        self.assertIn('Threshold amount must be positive', str(context.exception))
    
    def test_disable_auto_refill_success(self):
        """Test successful auto-refill disabling."""
        # Enable auto-refill first
        refill_config = {
            'enabled': True,
            'threshold_amount': Decimal('100.00'),
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
        }
        
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            refill_config
        )
        
        # Disable auto-refill
        disabled_config = self.auto_refill_service.disable_auto_refill(
            self.advertiser.wallet
        )
        
        self.assertFalse(disabled_config['enabled'])
    
    def test_check_auto_refill_trigger_success(self):
        """Test successful auto-refill trigger."""
        # Enable auto-refill
        refill_config = {
            'enabled': True,
            'threshold_amount': Decimal('150.00'),  # Higher than current balance
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
        }
        
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            refill_config
        )
        
        # Check auto-refill
        with patch('api.advertiser_portal.services.billing.AdvertiserBillingService.deposit_funds') as mock_deposit:
            mock_deposit.return_value = Mock(
                id=1,
                amount=Decimal('500.00'),
                status='completed'
            )
            
            refill_result = self.auto_refill_service.check_auto_refill(
                self.advertiser.wallet
            )
            
            self.assertTrue(refill_result.get('triggered', False))
            self.assertIn('refill_amount', refill_result)
            self.assertEqual(refill_result['refill_amount'], Decimal('500.00'))
            
            mock_deposit.assert_called_once()
    
    def test_check_auto_refill_no_trigger(self):
        """Test auto-refill check with no trigger."""
        # Enable auto-refill with high threshold
        refill_config = {
            'enabled': True,
            'threshold_amount': Decimal('50.00'),  # Lower than current balance
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
        }
        
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            refill_config
        )
        
        # Check auto-refill
        refill_result = self.auto_refill_service.check_auto_refill(
            self.advertiser.wallet
        )
        
        self.assertFalse(refill_result.get('triggered', False))
        self.assertEqual(refill_result['reason'], 'Balance above threshold')
    
    def test_check_auto_refill_disabled(self):
        """Test auto-refill check when disabled."""
        # Check auto-refill without enabling
        refill_result = self.auto_refill_service.check_auto_refill(
            self.advertiser.wallet
        )
        
        self.assertFalse(refill_result.get('triggered', False))
        self.assertEqual(refill_result['reason'], 'Auto-refill is disabled')
    
    def test_check_auto_refill_monthly_limit_reached(self):
        """Test auto-refill check when monthly limit is reached."""
        # Enable auto-refill with monthly limit
        refill_config = {
            'enabled': True,
            'threshold_amount': Decimal('150.00'),
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
            'max_monthly_refill': Decimal('100.00'),  # Low limit
        }
        
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            refill_config
        )
        
        # Simulate monthly refills
        self.auto_refill_service.record_monthly_refill(
            self.advertiser.wallet,
            Decimal('100.00')
        )
        
        # Check auto-refill
        refill_result = self.auto_refill_service.check_auto_refill(
            self.advertiser.wallet
        )
        
        self.assertFalse(refill_result.get('triggered', False))
        self.assertEqual(refill_result['reason'], 'Monthly refill limit reached')
    
    def test_get_auto_refill_history_success(self):
        """Test getting auto-refill history."""
        # Enable auto-refill
        refill_config = {
            'enabled': True,
            'threshold_amount': Decimal('150.00'),
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
        }
        
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            refill_config
        )
        
        # Record some refills
        for i in range(3):
            self.auto_refill_service.record_auto_refill(
                self.advertiser.wallet,
                Decimal('500.00'),
                f'auto_refill_{i+1}'
            )
        
        # Get history
        history = self.auto_refill_service.get_auto_refill_history(
            self.advertiser.wallet,
            days=30
        )
        
        self.assertEqual(len(history), 3)
        
        for refill in history:
            self.assertEqual(refill['amount'], Decimal('500.00'))
            self.assertIn('refill_id', refill)
            self.assertIn('refilled_at', refill)
    
    def test_validate_auto_refill_config_success(self):
        """Test successful auto-refill config validation."""
        config = {
            'threshold_amount': Decimal('100.00'),
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
            'max_monthly_refill': Decimal('2000.00'),
        }
        
        is_valid, errors = self.auto_refill_service.validate_auto_refill_config(config)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_auto_refill_config_invalid(self):
        """Test auto-refill config validation with invalid data."""
        config = {
            'threshold_amount': Decimal('-100.00'),  # Invalid
            'refill_amount': Decimal('0.00'),  # Invalid
            'payment_method': 'invalid_method',  # Invalid
            'payment_reference': '',  # Missing
            'max_monthly_refill': Decimal('-500.00'),  # Invalid
        }
        
        is_valid, errors = self.auto_refill_service.validate_auto_refill_config(config)
        
        self.assertFalse(is_valid)
        self.assertIn('threshold_amount', errors)
        self.assertIn('refill_amount', errors)
        self.assertIn('payment_method', errors)
        self.assertIn('payment_reference', errors)
        self.assertIn('max_monthly_refill', errors)
    
    def test_get_auto_refill_statistics(self):
        """Test getting auto-refill statistics."""
        # Enable auto-refill
        refill_config = {
            'enabled': True,
            'threshold_amount': Decimal('150.00'),
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
        }
        
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            refill_config
        )
        
        # Record some refills
        for i in range(5):
            self.auto_refill_service.record_auto_refill(
                self.advertiser.wallet,
                Decimal('500.00'),
                f'auto_refill_{i+1}'
            )
        
        # Get statistics
        stats = self.auto_refill_service.get_auto_refill_statistics(
            self.advertiser.wallet,
            days=30
        )
        
        self.assertIn('total_refills', stats)
        self.assertIn('total_refilled_amount', stats)
        self.assertIn('average_refill_amount', stats)
        self.assertIn('monthly_refill_total', stats)
        self.assertIn('refill_frequency', stats)
        
        self.assertEqual(stats['total_refills'], 5)
        self.assertEqual(stats['total_refilled_amount'], Decimal('2500.00'))
        self.assertEqual(stats['average_refill_amount'], Decimal('500.00'))
    
    @patch('api.advertiser_portal.services.billing.AutoRefillService.send_notification')
    def test_send_auto_refill_notification(self, mock_send_notification):
        """Test sending auto-refill notification."""
        # Enable auto-refill
        refill_config = {
            'enabled': True,
            'threshold_amount': Decimal('150.00'),
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
        }
        
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            refill_config
        )
        
        # Send notification
        self.auto_refill_service.send_auto_refill_notification(
            self.advertiser.wallet,
            'auto_refill_triggered',
            'Auto-refill of $500.00 has been processed',
            {'refill_amount': Decimal('500.00')}
        )
        
        mock_send_notification.assert_called_once()
        
        # Check notification data
        call_args = mock_send_notification.call_args
        notification_data = call_args[0][1] if call_args else None
        
        if notification_data:
            self.assertEqual(notification_data['type'], 'auto_refill_triggered')
            self.assertIn('Auto-refill of $500.00', notification_data['message'])


class BillingIntegrationTestCase(TestCase):
    """Test cases for billing integration."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.billing_service = AdvertiserBillingService()
        self.auto_refill_service = AutoRefillService()
        
        self.advertiser = self.advertiser_service.create_advertiser(
            self.user, 
            {
                'company_name': 'Test Company',
                'contact_email': 'contact@testcompany.com',
                'contact_phone': '+1234567890',
                'website': 'https://testcompany.com',
                'industry': 'technology',
                'company_size': 'medium',
            }
        )
    
    def test_complete_billing_flow(self):
        """Test complete billing flow."""
        # 1. Create wallet
        wallet = self.billing_service.create_wallet(self.advertiser)
        self.assertEqual(wallet.balance, Decimal('0.00'))
        
        # 2. Deposit funds
        deposit = self.billing_service.deposit_funds(
            self.advertiser,
            Decimal('1000.00'),
            'credit_card',
            'payment_12345'
        )
        
        # 3. Enable auto-refill
        refill_config = {
            'enabled': True,
            'threshold_amount': Decimal('200.00'),
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
        }
        
        self.auto_refill_service.enable_auto_refill(wallet, refill_config)
        
        # 4. Make charges
        for i in range(5):
            self.billing_service.charge_funds(
                self.advertiser,
                Decimal('100.00'),
                f'Campaign spend {i+1}'
            )
        
        # 5. Check final balance
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('500.00'))
        
        # 6. Get transaction history
        history = self.billing_service.get_transaction_history(self.advertiser)
        self.assertEqual(len(history), 6)  # 1 deposit + 5 charges
        
        # 7. Create invoice
        invoice = self.billing_service.create_invoice(
            self.advertiser,
            timezone.now().date().replace(day=1)
        )
        
        self.assertIsNotNone(invoice)
        self.assertGreater(invoice.total_amount, Decimal('0.00'))
    
    def test_auto_refill_integration(self):
        """Test auto-refill integration with billing."""
        # Create wallet and deposit
        wallet = self.billing_service.create_wallet(self.advertiser)
        self.billing_service.deposit_funds(
            self.advertiser,
            Decimal('200.00'),
            'credit_card',
            'payment_12345'
        )
        
        # Enable auto-refill
        refill_config = {
            'enabled': True,
            'threshold_amount': Decimal('150.00'),
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
        }
        
        self.auto_refill_service.enable_auto_refill(wallet, refill_config)
        
        # Make charges that trigger auto-refill
        for i in range(3):
            self.billing_service.charge_funds(
                self.advertiser,
                Decimal('100.00'),
                f'Campaign spend {i+1}'
            )
        
        # Check auto-refill
        with patch('api.advertiser_portal.services.billing.AdvertiserBillingService.deposit_funds') as mock_deposit:
            mock_deposit.return_value = Mock(
                id=1,
                amount=Decimal('500.00'),
                status='completed'
            )
            
            refill_result = self.auto_refill_service.check_auto_refill(wallet)
            
            self.assertTrue(refill_result.get('triggered', False))
            mock_deposit.assert_called_once()
    
    def test_billing_error_handling(self):
        """Test billing error handling."""
        # Test with insufficient balance
        wallet = self.billing_service.create_wallet(self.advertiser)
        
        # Try to charge without funds
        with self.assertRaises(ValueError) as context:
            self.billing_service.charge_funds(
                self.advertiser,
                Decimal('100.00'),
                'Campaign spend'
            )
        
        self.assertIn('Insufficient wallet balance', str(context.exception))
        
        # Test with invalid deposit amount
        with self.assertRaises(ValueError) as context:
            self.billing_service.deposit_funds(
                self.advertiser,
                Decimal('-100.00'),
                'credit_card',
                'payment_12345'
            )
        
        self.assertIn('Deposit amount must be positive', str(context.exception))
    
    def test_billing_notification_integration(self):
        """Test billing notification integration."""
        with patch('api.advertiser_portal.services.billing.AdvertiserBillingService.send_notification') as mock_send_notification:
            # Deposit funds
            self.billing_service.deposit_funds(
                self.advertiser,
                Decimal('500.00'),
                'credit_card',
                'payment_12345'
            )
            
            # Check that notification was sent
            mock_send_notification.assert_called()
            
            # Get notification data
            call_args = mock_send_notification.call_args
            notification_data = call_args[0][1] if call_args else None
            
            if notification_data:
                self.assertEqual(notification_data['type'], 'deposit_completed')
    
    def test_billing_statistics_integration(self):
        """Test billing statistics integration."""
        # Create various transactions
        self.billing_service.deposit_funds(
            self.advertiser,
            Decimal('1000.00'),
            'credit_card',
            'payment_12345'
        )
        
        self.billing_service.deposit_funds(
            self.advertiser,
            Decimal('500.00'),
            'bank_transfer',
            'payment_67890'
        )
        
        for i in range(5):
            self.billing_service.charge_funds(
                self.advertiser,
                Decimal('100.00'),
                f'Campaign spend {i+1}'
            )
        
        # Get comprehensive statistics
        stats = self.billing_service.get_billing_statistics(self.advertiser)
        
        self.assertEqual(stats['total_deposits'], Decimal('1500.00'))
        self.assertEqual(stats['total_charges'], Decimal('500.00'))
        self.assertEqual(stats['net_balance'], Decimal('1000.00'))
        self.assertEqual(stats['transaction_count'], 7)
        
        # Get wallet activity summary
        summary = self.billing_service.get_wallet_activity_summary(
            self.advertiser,
            days=30
        )
        
        self.assertEqual(summary['total_transactions'], 7)
        self.assertEqual(summary['total_deposits'], Decimal('1500.00'))
        self.assertEqual(summary['total_charges'], Decimal('500.00'))
    
    def test_invoice_generation_integration(self):
        """Test invoice generation integration."""
        # Create transactions over multiple months
        for month in range(3):
            # Create charges
            for i in range(3):
                self.billing_service.charge_funds(
                    self.advertiser,
                    Decimal('100.00'),
                    f'Campaign spend {month+1}-{i+1}'
                )
            
            # Create invoice for the month
            invoice_date = timezone.now().date().replace(day=1) - timezone.timedelta(days=month*30)
            invoice = self.billing_service.create_invoice(self.advertiser, invoice_date)
            self.billing_service.finalize_invoice(invoice)
        
        # Get invoice history
        history = self.billing_service.get_invoice_history(self.advertiser)
        self.assertEqual(len(history), 3)
        
        # Check that all invoices are finalized
        for invoice in history:
            self.assertEqual(invoice.status, 'sent')
            self.assertIsNotNone(invoice.sent_at)
            self.assertIsNotNone(invoice.due_date)
