"""
Test Auto Refill

Comprehensive tests for auto-refill functionality
including threshold monitoring, payment processing, and notifications.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock

from ..models.billing import AdvertiserWallet, AdvertiserTransaction
from ..models.advertiser import Advertiser
try:
    from ..services import AutoRefillService
except ImportError:
    AutoRefillService = None
try:
    from ..services import AdvertiserBillingService
except ImportError:
    AdvertiserBillingService = None
try:
    from ..services import AdvertiserService
except ImportError:
    AdvertiserService = None

User = get_user_model()


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
        
        self.valid_refill_config = {
            'enabled': True,
            'threshold_amount': Decimal('100.00'),
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
            'max_monthly_refill': Decimal('2000.00'),
            'min_balance_before_refill': Decimal('50.00'),
        }
    
    def test_enable_auto_refill_success(self):
        """Test successful auto-refill enablement."""
        config = self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            self.valid_refill_config
        )
        
        self.assertTrue(config.get('enabled', False))
        self.assertEqual(config.get('threshold_amount'), Decimal('100.00'))
        self.assertEqual(config.get('refill_amount'), Decimal('500.00'))
        self.assertEqual(config.get('payment_method'), 'credit_card')
        self.assertEqual(config.get('payment_reference'), 'auto_refill_card_12345')
        self.assertEqual(config.get('max_monthly_refill'), Decimal('2000.00'))
        
        # Check wallet was updated
        wallet = self.advertiser.wallet
        wallet.refresh_from_db()
        self.assertTrue(wallet.auto_refill_enabled)
        self.assertEqual(wallet.auto_refill_threshold, Decimal('100.00'))
        self.assertEqual(wallet.auto_refill_amount, Decimal('500.00'))
    
    def test_enable_auto_refill_invalid_config(self):
        """Test auto-refill enablement with invalid config."""
        invalid_config = self.valid_refill_config.copy()
        invalid_config['threshold_amount'] = Decimal('-100.00')  # Invalid
        
        with self.assertRaises(ValueError) as context:
            self.auto_refill_service.enable_auto_refill(
                self.advertiser.wallet,
                invalid_config
            )
        
        self.assertIn('Threshold amount must be positive', str(context.exception))
    
    def test_enable_auto_refill_insufficient_payment_method(self):
        """Test auto-refill enablement with insufficient payment method."""
        invalid_config = self.valid_refill_config.copy()
        invalid_config['payment_method'] = ''  # Missing payment method
        
        with self.assertRaises(ValueError) as context:
            self.auto_refill_service.enable_auto_refill(
                self.advertiser.wallet,
                invalid_config
            )
        
        self.assertIn('Payment method is required', str(context.exception))
    
    def test_disable_auto_refill_success(self):
        """Test successful auto-refill disabling."""
        # Enable auto-refill first
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            self.valid_refill_config
        )
        
        # Disable auto-refill
        config = self.auto_refill_service.disable_auto_refill(
            self.advertiser.wallet
        )
        
        self.assertFalse(config.get('enabled', False))
        
        # Check wallet was updated
        wallet = self.advertiser.wallet
        wallet.refresh_from_db()
        self.assertFalse(wallet.auto_refill_enabled)
    
    def test_disable_auto_refill_already_disabled(self):
        """Test disabling already disabled auto-refill."""
        with self.assertRaises(ValueError) as context:
            self.auto_refill_service.disable_auto_refill(
                self.advertiser.wallet
            )
        
        self.assertIn('Auto-refill is already disabled', str(context.exception))
    
    def test_check_auto_refill_trigger_success(self):
        """Test successful auto-refill trigger."""
        # Enable auto-refill
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            self.valid_refill_config
        )
        
        # Set balance below threshold
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('50.00')  # Below threshold of 100.00
        wallet.save()
        
        # Check auto-refill
        with patch('api.advertiser_portal.services.billing.AdvertiserBillingService.deposit_funds') as mock_deposit:
            mock_deposit.return_value = Mock(
                id=1,
                amount=Decimal('500.00'),
                status='completed'
            )
            
            result = self.auto_refill_service.check_auto_refill(
                self.advertiser.wallet
            )
            
            self.assertTrue(result.get('triggered', False))
            self.assertEqual(result.get('refill_amount'), Decimal('500.00'))
            self.assertIn('transaction_id', result)
            
            mock_deposit.assert_called_once_with(
                self.advertiser,
                Decimal('500.00'),
                'credit_card',
                'auto_refill_card_12345'
            )
    
    def test_check_auto_refill_no_trigger_above_threshold(self):
        """Test auto-refill check with no trigger (balance above threshold)."""
        # Enable auto-refill
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            self.valid_refill_config
        )
        
        # Balance is above threshold
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('150.00')  # Above threshold of 100.00
        wallet.save()
        
        # Check auto-refill
        result = self.auto_refill_service.check_auto_refill(
            self.advertiser.wallet
        )
        
        self.assertFalse(result.get('triggered', False))
        self.assertEqual(result.get('reason'), 'Balance above threshold')
    
    def test_check_auto_refill_no_trigger_disabled(self):
        """Test auto-refill check with no trigger (disabled)."""
        # Check auto-refill without enabling
        result = self.auto_refill_service.check_auto_refill(
            self.advertiser.wallet
        )
        
        self.assertFalse(result.get('triggered', False))
        self.assertEqual(result.get('reason'), 'Auto-refill is disabled')
    
    def test_check_auto_refill_no_trigger_above_min_balance(self):
        """Test auto-refill check with no trigger (above min balance)."""
        # Enable auto-refill with min balance requirement
        config = self.valid_refill_config.copy()
        config['min_balance_before_refill'] = Decimal('25.00')
        
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            config
        )
        
        # Set balance below threshold but above min balance
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('30.00')  # Below threshold (100) but above min (25)
        wallet.save()
        
        # Check auto-refill
        result = self.auto_refill_service.check_auto_refill(
            self.advertiser.wallet
        )
        
        self.assertFalse(result.get('triggered', False))
        self.assertEqual(result.get('reason'), 'Balance above minimum threshold')
    
    def test_check_auto_refill_payment_failure(self):
        """Test auto-refill check with payment failure."""
        # Enable auto-refill
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            self.valid_refill_config
        )
        
        # Set balance below threshold
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('50.00')
        wallet.save()
        
        # Check auto-refill with payment failure
        with patch('api.advertiser_portal.services.billing.AdvertiserBillingService.deposit_funds') as mock_deposit:
            mock_deposit.side_effect = Exception('Payment failed')
            
            result = self.auto_refill_service.check_auto_refill(
                self.advertiser.wallet
            )
            
            self.assertFalse(result.get('triggered', False))
            self.assertIn('error', result)
            self.assertEqual(result.get('error'), 'Payment failed')
    
    def test_check_auto_refill_monthly_limit_reached(self):
        """Test auto-refill check with monthly limit reached."""
        # Enable auto-refill with low monthly limit
        config = self.valid_refill_config.copy()
        config['max_monthly_refill'] = Decimal('100.00')
        
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            config
        )
        
        # Record monthly refills that reach limit
        self.auto_refill_service.record_monthly_refill(
            self.advertiser.wallet,
            Decimal('100.00')
        )
        
        # Set balance below threshold
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('50.00')
        wallet.save()
        
        # Check auto-refill
        result = self.auto_refill_service.check_auto_refill(
            self.advertiser.wallet
        )
        
        self.assertFalse(result.get('triggered', False))
        self.assertEqual(result.get('reason'), 'Monthly refill limit reached')
    
    def test_check_auto_refill_suspended_wallet(self):
        """Test auto-refill check with suspended wallet."""
        # Enable auto-refill
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            self.valid_refill_config
        )
        
        # Suspend wallet
        wallet = self.advertiser.wallet
        wallet.status = 'suspended'
        wallet.save()
        
        # Check auto-refill
        result = self.auto_refill_service.check_auto_refill(
            self.advertiser.wallet
        )
        
        self.assertFalse(result.get('triggered', False))
        self.assertEqual(result.get('reason'), 'Wallet is suspended')
    
    def test_record_auto_refill_success(self):
        """Test successful auto-refill recording."""
        refill_amount = Decimal('500.00')
        refill_id = 'auto_refill_12345'
        
        refill_record = self.auto_refill_service.record_auto_refill(
            self.advertiser.wallet,
            refill_amount,
            refill_id
        )
        
        self.assertEqual(refill_record['wallet_id'], self.advertiser.wallet.id)
        self.assertEqual(refill_record['amount'], refill_amount)
        self.assertEqual(refill_record['refill_id'], refill_id)
        self.assertIn('refilled_at', refill_record)
        self.assertIn('month', refill_record)
        self.assertIn('year', refill_record)
    
    def test_record_monthly_refill_success(self):
        """Test successful monthly refill recording."""
        refill_amount = Decimal('500.00')
        
        monthly_total = self.auto_refill_service.record_monthly_refill(
            self.advertiser.wallet,
            refill_amount
        )
        
        self.assertEqual(monthly_total, refill_amount)
        
        # Add another refill
        additional_amount = Decimal('300.00')
        monthly_total = self.auto_refill_service.record_monthly_refill(
            self.advertiser.wallet,
            additional_amount
        )
        
        self.assertEqual(monthly_total, Decimal('800.00'))
    
    def test_get_monthly_refill_total_success(self):
        """Test getting monthly refill total."""
        # Record some refills
        self.auto_refill_service.record_monthly_refill(
            self.advertiser.wallet,
            Decimal('500.00')
        )
        
        self.auto_refill_service.record_monthly_refill(
            self.advertiser.wallet,
            Decimal('300.00')
        )
        
        # Get monthly total
        monthly_total = self.auto_refill_service.get_monthly_refill_total(
            self.advertiser.wallet
        )
        
        self.assertEqual(monthly_total, Decimal('800.00'))
    
    def test_get_monthly_refill_total_no_refills(self):
        """Test getting monthly refill total with no refills."""
        monthly_total = self.auto_refill_service.get_monthly_refill_total(
            self.advertiser.wallet
        )
        
        self.assertEqual(monthly_total, Decimal('0.00'))
    
    def test_reset_monthly_refill_total_success(self):
        """Test successful monthly refill total reset."""
        # Record some refills
        self.auto_refill_service.record_monthly_refill(
            self.advertiser.wallet,
            Decimal('500.00')
        )
        
        # Reset monthly total
        self.auto_refill_service.reset_monthly_refill_total(
            self.advertiser.wallet
        )
        
        # Check that total is reset
        monthly_total = self.auto_refill_service.get_monthly_refill_total(
            self.advertiser.wallet
        )
        
        self.assertEqual(monthly_total, Decimal('0.00'))
    
    def test_get_auto_refill_history_success(self):
        """Test successful auto-refill history retrieval."""
        # Enable auto-refill
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            self.valid_refill_config
        )
        
        # Record some refills
        for i in range(5):
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
        
        self.assertEqual(len(history), 5)
        
        for refill in history:
            self.assertEqual(refill['amount'], Decimal('500.00'))
            self.assertIn('refill_id', refill)
            self.assertIn('refilled_at', refill)
    
    def test_get_auto_refill_history_no_refills(self):
        """Test getting auto-refill history with no refills."""
        history = self.auto_refill_service.get_auto_refill_history(
            self.advertiser.wallet,
            days=30
        )
        
        self.assertEqual(len(history), 0)
    
    def test_validate_auto_refill_config_success(self):
        """Test successful auto-refill config validation."""
        is_valid, errors = self.auto_refill_service.validate_auto_refill_config(
            self.valid_refill_config
        )
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_auto_refill_config_invalid_threshold(self):
        """Test auto-refill config validation with invalid threshold."""
        invalid_config = self.valid_refill_config.copy()
        invalid_config['threshold_amount'] = Decimal('-100.00')
        
        is_valid, errors = self.auto_refill_service.validate_auto_refill_config(
            invalid_config
        )
        
        self.assertFalse(is_valid)
        self.assertIn('threshold_amount', errors)
        self.assertIn('must be positive', errors['threshold_amount'])
    
    def test_validate_auto_refill_config_invalid_refill_amount(self):
        """Test auto-refill config validation with invalid refill amount."""
        invalid_config = self.valid_refill_config.copy()
        invalid_config['refill_amount'] = Decimal('0.00')
        
        is_valid, errors = self.auto_refill_service.validate_auto_refill_config(
            invalid_config
        )
        
        self.assertFalse(is_valid)
        self.assertIn('refill_amount', errors)
        self.assertIn('must be positive', errors['refill_amount'])
    
    def test_validate_auto_refill_config_invalid_payment_method(self):
        """Test auto-refill config validation with invalid payment method."""
        invalid_config = self.valid_refill_config.copy()
        invalid_config['payment_method'] = 'invalid_method'
        
        is_valid, errors = self.auto_refill_service.validate_auto_refill_config(
            invalid_config
        )
        
        self.assertFalse(is_valid)
        self.assertIn('payment_method', errors)
        self.assertIn('must be valid', errors['payment_method'])
    
    def test_validate_auto_refill_config_invalid_monthly_limit(self):
        """Test auto-refill config validation with invalid monthly limit."""
        invalid_config = self.valid_refill_config.copy()
        invalid_config['max_monthly_refill'] = Decimal('-500.00')
        
        is_valid, errors = self.auto_refill_service.validate_auto_refill_config(
            invalid_config
        )
        
        self.assertFalse(is_valid)
        self.assertIn('max_monthly_refill', errors)
        self.assertIn('must be positive', errors['max_monthly_refill'])
    
    def test_validate_auto_refill_config_refill_exceeds_limit(self):
        """Test auto-refill config validation with refill amount exceeding limit."""
        invalid_config = self.valid_refill_config.copy()
        invalid_config['refill_amount'] = Decimal('3000.00')
        invalid_config['max_monthly_refill'] = Decimal('2000.00')
        
        is_valid, errors = self.auto_refill_service.validate_auto_refill_config(
            invalid_config
        )
        
        self.assertFalse(is_valid)
        self.assertIn('refill_amount', errors)
        self.assertIn('cannot exceed monthly limit', errors['refill_amount'])
    
    def test_get_supported_payment_methods(self):
        """Test getting supported payment methods."""
        payment_methods = self.auto_refill_service.get_supported_payment_methods()
        
        expected_methods = [
            'credit_card',
            'debit_card',
            'bank_transfer',
            'paypal',
            'stripe',
            'ach'
        ]
        
        for method in expected_methods:
            self.assertIn(method, payment_methods)
    
    def test_get_auto_refill_statistics_success(self):
        """Test successful auto-refill statistics retrieval."""
        # Enable auto-refill
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            self.valid_refill_config
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
        self.assertIn('last_refill', stats)
        
        self.assertEqual(stats['total_refills'], 5)
        self.assertEqual(stats['total_refilled_amount'], Decimal('2500.00'))
        self.assertEqual(stats['average_refill_amount'], Decimal('500.00'))
    
    def test_get_auto_refill_statistics_no_refills(self):
        """Test getting auto-refill statistics with no refills."""
        stats = self.auto_refill_service.get_auto_refill_statistics(
            self.advertiser.wallet,
            days=30
        )
        
        self.assertEqual(stats['total_refills'], 0)
        self.assertEqual(stats['total_refilled_amount'], Decimal('0.00'))
        self.assertEqual(stats['average_refill_amount'], Decimal('0.00'))
        self.assertEqual(stats['monthly_refill_total'], Decimal('0.00'))
    
    def test_get_auto_refill_health_status_success(self):
        """Test successful auto-refill health status retrieval."""
        # Enable auto-refill
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            self.valid_refill_config
        )
        
        # Record some refills
        for i in range(3):
            self.auto_refill_service.record_auto_refill(
                self.advertiser.wallet,
                Decimal('500.00'),
                f'auto_refill_{i+1}'
            )
        
        # Get health status
        health_status = self.auto_refill_service.get_auto_refill_health_status(
            self.advertiser.wallet
        )
        
        self.assertIn('status', health_status)
        self.assertIn('enabled', health_status)
        self.assertIn('last_refill', health_status)
        self.assertIn('monthly_usage', health_status)
        self.assertIn('limit_usage_percentage', health_status)
        self.assertIn('recommendations', health_status)
        
        self.assertTrue(health_status['enabled'])
        self.assertEqual(health_status['status'], 'healthy')
    
    def test_get_auto_refill_health_status_disabled(self):
        """Test getting auto-refill health status when disabled."""
        health_status = self.auto_refill_service.get_auto_refill_health_status(
            self.advertiser.wallet
        )
        
        self.assertFalse(health_status['enabled'])
        self.assertEqual(health_status['status'], 'disabled')
    
    def test_get_auto_refill_recommendations(self):
        """Test getting auto-refill recommendations."""
        # Enable auto-refill
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            self.valid_refill_config
        )
        
        # Record some refills
        for i in range(5):
            self.auto_refill_service.record_auto_refill(
                self.advertiser.wallet,
                Decimal('500.00'),
                f'auto_refill_{i+1}'
            )
        
        recommendations = self.auto_refill_service.get_auto_refill_recommendations(
            self.advertiser.wallet
        )
        
        self.assertIn('threshold_adjustments', recommendations)
        self.assertIn('refill_amount_optimizations', recommendations)
        self.assertIn('payment_method_suggestions', recommendations)
        self.assertIn('limit_adjustments', recommendations)
    
    def test_update_auto_refill_config_success(self):
        """Test successful auto-refill config update."""
        # Enable auto-refill
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            self.valid_refill_config
        )
        
        # Update config
        updated_config = {
            'threshold_amount': Decimal('150.00'),
            'refill_amount': Decimal('750.00'),
            'max_monthly_refill': Decimal('3000.00'),
        }
        
        config = self.auto_refill_service.update_auto_refill_config(
            self.advertiser.wallet,
            updated_config
        )
        
        self.assertEqual(config.get('threshold_amount'), Decimal('150.00'))
        self.assertEqual(config.get('refill_amount'), Decimal('750.00'))
        self.assertEqual(config.get('max_monthly_refill'), Decimal('3000.00'))
        
        # Check wallet was updated
        wallet = self.advertiser.wallet
        wallet.refresh_from_db()
        self.assertEqual(wallet.auto_refill_threshold, Decimal('150.00'))
        self.assertEqual(wallet.auto_refill_amount, Decimal('750.00'))
    
    def test_update_auto_refill_config_invalid(self):
        """Test auto-refill config update with invalid data."""
        # Enable auto-refill
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            self.valid_refill_config
        )
        
        # Try to update with invalid config
        invalid_config = {
            'threshold_amount': Decimal('-100.00'),  # Invalid
        }
        
        with self.assertRaises(ValueError) as context:
            self.auto_refill_service.update_auto_refill_config(
                self.advertiser.wallet,
                invalid_config
            )
        
        self.assertIn('Invalid configuration', str(context.exception))
    
    def test_export_auto_refill_data(self):
        """Test exporting auto-refill data."""
        # Enable auto-refill
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            self.valid_refill_config
        )
        
        # Record some refills
        for i in range(3):
            self.auto_refill_service.record_auto_refill(
                self.advertiser.wallet,
                Decimal('500.00'),
                f'auto_refill_{i+1}'
            )
        
        # Export data
        export_data = self.auto_refill_service.export_auto_refill_data(
            self.advertiser.wallet,
            days=30
        )
        
        self.assertIn('config', export_data)
        self.assertIn('refill_history', export_data)
        self.assertIn('statistics', export_data)
        self.assertIn('monthly_usage', export_data)
        self.assertIn('export_date', export_data)
        
        # Check data counts
        self.assertEqual(len(export_data['refill_history']), 3)
    
    @patch('api.advertiser_portal.services.billing.AutoRefillService.send_notification')
    def test_send_auto_refill_notification(self, mock_send_notification):
        """Test sending auto-refill notification."""
        # Enable auto-refill
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            self.valid_refill_config
        )
        
        # Send notification
        self.auto_refill_service.send_auto_refill_notification(
            self.advertiser.wallet,
            'auto_refill_triggered',
            'Auto-refill of $500.00 has been processed successfully',
            {'refill_amount': Decimal('500.00')}
        )
        
        mock_send_notification.assert_called_once()
        
        # Check notification data
        call_args = mock_send_notification.call_args
        notification_data = call_args[0][1] if call_args else None
        
        if notification_data:
            self.assertEqual(notification_data['type'], 'auto_refill_triggered')
            self.assertIn('Auto-refill of $500.00', notification_data['message'])
    
    def test_auto_refill_with_different_payment_methods(self):
        """Test auto-refill with different payment methods."""
        payment_methods = ['credit_card', 'bank_transfer', 'paypal']
        
        for method in payment_methods:
            config = self.valid_refill_config.copy()
            config['payment_method'] = method
            config['payment_reference'] = f'auto_refill_{method}_12345'
            
            # Enable auto-refill
            self.auto_refill_service.enable_auto_refill(
                self.advertiser.wallet,
                config
            )
            
            # Set balance below threshold
            wallet = self.advertiser.wallet
            wallet.balance = Decimal('50.00')
            wallet.save()
            
            # Check auto-refill
            with patch('api.advertiser_portal.services.billing.AdvertiserBillingService.deposit_funds') as mock_deposit:
                mock_deposit.return_value = Mock(
                    id=1,
                    amount=Decimal('500.00'),
                    status='completed'
                )
                
                result = self.auto_refill_service.check_auto_refill(
                    self.advertiser.wallet
                )
                
                self.assertTrue(result.get('triggered', False))
                
                # Check correct payment method was used
                mock_deposit.assert_called_once()
                call_args = mock_deposit.call_args
                self.assertEqual(call_args[0][2], method)
            
            # Disable for next test
            self.auto_refill_service.disable_auto_refill(self.advertiser.wallet)
    
    def test_auto_refill_with_multiple_thresholds(self):
        """Test auto-refill with multiple threshold levels."""
        # Enable auto-refill with multiple thresholds
        config = self.valid_refill_config.copy()
        config['multi_threshold'] = True
        config['thresholds'] = [
            {'amount': Decimal('200.00'), 'refill': Decimal('300.00')},
            {'amount': Decimal('100.00'), 'refill': Decimal('500.00')},
            {'amount': Decimal('50.00'), 'refill': Decimal('700.00')}
        ]
        
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            config
        )
        
        # Test different balance levels
        test_cases = [
            {'balance': Decimal('250.00'), 'expected_refill': Decimal('300.00')},
            {'balance': Decimal('80.00'), 'expected_refill': Decimal('500.00')},
            {'balance': Decimal('30.00'), 'expected_refill': Decimal('700.00')},
        ]
        
        for case in test_cases:
            # Set balance
            wallet = self.advertiser.wallet
            wallet.balance = case['balance']
            wallet.save()
            
            # Check auto-refill
            with patch('api.advertiser_portal.services.billing.AdvertiserBillingService.deposit_funds') as mock_deposit:
                mock_deposit.return_value = Mock(
                    id=1,
                    amount=case['expected_refill'],
                    status='completed'
                )
                
                result = self.auto_refill_service.check_auto_refill(
                    self.advertiser.wallet
                )
                
                self.assertTrue(result.get('triggered', False))
                self.assertEqual(result.get('refill_amount'), case['expected_refill'])
    
    def test_auto_refill_with_time_restrictions(self):
        """Test auto-refill with time restrictions."""
        # Enable auto-refill with time restrictions
        config = self.valid_refill_config.copy()
        config['time_restrictions'] = {
            'enabled': True,
            'allowed_hours': list(range(6, 22)),  # 6 AM to 10 PM
            'allowed_days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
        }
        
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            config
        )
        
        # Set balance below threshold
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('50.00')
        wallet.save()
        
        # Test during allowed time
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = timezone.now().replace(hour=14, weekday=0)  # 2 PM, Monday
            
            with patch('api.advertiser_portal.services.billing.AdvertiserBillingService.deposit_funds') as mock_deposit:
                mock_deposit.return_value = Mock(
                    id=1,
                    amount=Decimal('500.00'),
                    status='completed'
                )
                
                result = self.auto_refill_service.check_auto_refill(
                    self.advertiser.wallet
                )
                
                self.assertTrue(result.get('triggered', False))
        
        # Test during restricted time
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = timezone.now().replace(hour=23, weekday=5)  # 11 PM, Saturday
            
            result = self.auto_refill_service.check_auto_refill(
                self.advertiser.wallet
            )
            
            self.assertFalse(result.get('triggered', False))
            self.assertEqual(result.get('reason'), 'Outside allowed time window')
    
    def test_auto_refill_with_conditional_logic(self):
        """Test auto-refill with conditional logic."""
        # Enable auto-refill with conditions
        config = self.valid_refill_config.copy()
        config['conditions'] = {
            'min_days_since_last_refill': 7,
            'max_refills_per_month': 4,
            'require_active_campaigns': True
        }
        
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            config
        )
        
        # Set balance below threshold
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('50.00')
        wallet.save()
        
        # Test with conditions not met (recent refill)
        self.auto_refill_service.record_auto_refill(
            self.advertiser.wallet,
            Decimal('500.00'),
            'recent_refill'
        )
        
        result = self.auto_refill_service.check_auto_refill(
            self.advertiser.wallet
        )
        
        self.assertFalse(result.get('triggered', False))
        self.assertIn('condition not met', result.get('reason', ''))


class AutoRefillIntegrationTestCase(TestCase):
    """Test cases for auto-refill integration."""
    
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
    
    def test_auto_refill_billing_integration(self):
        """Test auto-refill integration with billing service."""
        # Enable auto-refill
        config = {
            'enabled': True,
            'threshold_amount': Decimal('100.00'),
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
        }
        
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            config
        )
        
        # Set balance below threshold
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('50.00')
        wallet.save()
        
        # Check auto-refill (should trigger deposit)
        result = self.auto_refill_service.check_auto_refill(
            self.advertiser.wallet
        )
        
        self.assertTrue(result.get('triggered', False))
        
        # Check that wallet balance was updated
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('550.00'))
        
        # Check that transaction was created
        transactions = AdvertiserTransaction.objects.filter(
            advertiser=self.advertiser,
            transaction_type='deposit'
        )
        self.assertEqual(transactions.count(), 1)
        
        transaction = transactions.first()
        self.assertEqual(transaction.amount, Decimal('500.00'))
        self.assertEqual(transaction.payment_method, 'credit_card')
        self.assertEqual(transaction.payment_reference, 'auto_refill_card_12345')
    
    def test_auto_refill_notification_integration(self):
        """Test auto-refill notification integration."""
        # Enable auto-refill
        config = {
            'enabled': True,
            'threshold_amount': Decimal('100.00'),
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
        }
        
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            config
        )
        
        # Set balance below threshold
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('50.00')
        wallet.save()
        
        # Check auto-refill with notification
        with patch('api.advertiser_portal.services.billing.AutoRefillService.send_notification') as mock_send_notification:
            result = self.auto_refill_service.check_auto_refill(
                self.advertiser.wallet
            )
            
            self.assertTrue(result.get('triggered', False))
            
            # Check that notification was sent
            mock_send_notification.assert_called_once()
            
            # Get notification data
            call_args = mock_send_notification.call_args
            notification_data = call_args[0][1] if call_args else None
            
            if notification_data:
                self.assertEqual(notification_data['type'], 'auto_refill_triggered')
                self.assertIn('Auto-refill of $500.00', notification_data['message'])
    
    def test_auto_refill_with_campaign_spend(self):
        """Test auto-refill with campaign spend integration."""
        # Enable auto-refill
        config = {
            'enabled': True,
            'threshold_amount': Decimal('100.00'),
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
        }
        
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            config
        )
        
        # Make campaign charges that trigger auto-refill
        for i in range(3):
            self.billing_service.charge_funds(
                self.advertiser,
                Decimal('100.00'),
                f'Campaign spend {i+1}'
            )
        
        # Check that auto-refill was triggered
        wallet = self.advertiser.wallet
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('500.00'))  # Should be refilled
        
        # Check transaction history
        transactions = AdvertiserTransaction.objects.filter(
            advertiser=self.advertiser
        ).order_by('created_at')
        
        self.assertEqual(transactions.count(), 4)  # 3 charges + 1 deposit
        
        # Check that deposit was last transaction
        self.assertEqual(transactions.last().transaction_type, 'deposit')
        self.assertEqual(transactions.last().amount, Decimal('500.00'))
    
    def test_auto_refill_error_handling(self):
        """Test auto-refill error handling."""
        # Enable auto-refill
        config = {
            'enabled': True,
            'threshold_amount': Decimal('100.00'),
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
        }
        
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            config
        )
        
        # Set balance below threshold
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('50.00')
        wallet.save()
        
        # Test with payment failure
        with patch('api.advertiser_portal.services.billing.AdvertiserBillingService.deposit_funds') as mock_deposit:
            mock_deposit.side_effect = Exception('Payment processing failed')
            
            result = self.auto_refill_service.check_auto_refill(
                self.advertiser.wallet
            )
            
            self.assertFalse(result.get('triggered', False))
            self.assertIn('error', result)
            
            # Check that wallet balance was not changed
            wallet.refresh_from_db()
            self.assertEqual(wallet.balance, Decimal('50.00'))
    
    def test_auto_refill_with_multiple_wallets(self):
        """Test auto-refill with multiple wallets."""
        # Create additional advertiser
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
                'industry': 'finance',
                'company_size': 'large',
            }
        )
        
        # Fund both wallets
        for advertiser in [self.advertiser, new_advertiser]:
            wallet = advertiser.wallet
            wallet.balance = Decimal('100.00')
            wallet.save()
        
        # Enable auto-refill for both wallets
        config = {
            'enabled': True,
            'threshold_amount': Decimal('100.00'),
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
        }
        
        for advertiser in [self.advertiser, new_advertiser]:
            self.auto_refill_service.enable_auto_refill(advertiser.wallet, config)
        
        # Set both balances below threshold
        for advertiser in [self.advertiser, new_advertiser]:
            wallet = advertiser.wallet
            wallet.balance = Decimal('50.00')
            wallet.save()
        
        # Check auto-refill for both wallets
        results = []
        for advertiser in [self.advertiser, new_advertiser]:
            result = self.auto_refill_service.check_auto_refill(advertiser.wallet)
            results.append(result)
        
        # Both should trigger
        for result in results:
            self.assertTrue(result.get('triggered', False))
        
        # Check that both wallets were refilled
        for advertiser in [self.advertiser, new_advertiser]:
            wallet = advertiser.wallet
            wallet.refresh_from_db()
            self.assertEqual(wallet.balance, Decimal('550.00'))
    
    def test_auto_refill_performance_monitoring(self):
        """Test auto-refill performance monitoring."""
        # Enable auto-refill
        config = {
            'enabled': True,
            'threshold_amount': Decimal('100.00'),
            'refill_amount': Decimal('500.00'),
            'payment_method': 'credit_card',
            'payment_reference': 'auto_refill_card_12345',
        }
        
        self.auto_refill_service.enable_auto_refill(
            self.advertiser.wallet,
            config
        )
        
        # Trigger multiple refills
        for i in range(5):
            wallet = self.advertiser.wallet
            wallet.balance = Decimal('50.00')
            wallet.save()
            
            self.auto_refill_service.check_auto_refill(self.advertiser.wallet)
        
        # Get performance metrics
        metrics = self.auto_refill_service.get_auto_refill_performance_metrics(
            self.advertiser.wallet,
            days=30
        )
        
        self.assertIn('total_refills', metrics)
        self.assertIn('average_response_time', metrics)
        self.assertIn('success_rate', metrics)
        self.assertIn('payment_method_performance', metrics)
        
        self.assertEqual(metrics['total_refills'], 5)
        self.assertEqual(metrics['success_rate'], 100.0)
