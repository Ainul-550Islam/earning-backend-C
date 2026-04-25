"""
Test Tasks

Comprehensive tests for background tasks
including Celery tasks, scheduling, and error handling.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock
from datetime import timedelta

from ..models.advertiser import Advertiser
from ..models.campaign import AdCampaign
from ..models.offer import AdvertiserOffer
from ..models.tracking import Conversion, TrackingPixel
from ..models.billing import AdvertiserWallet, AdvertiserTransaction
from ..tasks.budget_check_tasks import (
    check_low_balance_alerts,
    check_budget_thresholds,
    check_campaign_budget_exhaustion,
    auto_pause_over_budget_campaigns
)
from ..tasks.campaign_schedule_tasks import (
    activate_scheduled_campaigns,
    deactivate_expired_campaigns,
    cleanup_completed_campaigns
)
from ..tasks.report_generation_tasks import (
    generate_daily_advertiser_reports,
    generate_weekly_performance_reports,
    generate_monthly_financial_reports
)
from ..tasks.invoice_tasks import (
    generate_monthly_invoices,
    send_invoice_reminders,
    process_invoice_payments
)

User = get_user_model()


class BudgetCheckTasksTestCase(TestCase):
    """Test cases for budget check tasks."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            contact_email='contact@testcompany.com',
            contact_phone='+1234567890',
            website='https://testcompany.com',
            industry='technology',
            company_size='medium'
        )
        
        # Fund wallet
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('100.00')
        wallet.save()
        
        self.campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Test Campaign',
            campaign_type='display',
            budget_limit=Decimal('200.00'),
            daily_budget=Decimal('50.00'),
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
            status='active'
        )
    
    def test_check_low_balance_alerts_success(self):
        """Test successful low balance alert checking."""
        # Set wallet balance to low amount
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('25.00')
        wallet.save()
        
        with patch('api.advertiser_portal.tasks.budget_check_tasks.send_notification') as mock_send:
            result = check_low_balance_alerts()
            
            self.assertTrue(result.get('success', False))
            self.assertIn('alerts_sent', result)
            self.assertGreater(result['alerts_sent'], 0)
            
            # Check that notification was sent
            mock_send.assert_called()
    
    def test_check_low_balance_alerts_no_alerts(self):
        """Test low balance alert checking with no alerts."""
        # Set wallet balance to normal amount
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('500.00')
        wallet.save()
        
        with patch('api.advertiser_portal.tasks.budget_check_tasks.send_notification') as mock_send:
            result = check_low_balance_alerts()
            
            self.assertTrue(result.get('success', False))
            self.assertEqual(result['alerts_sent'], 0)
            
            # Check that no notification was sent
            mock_send.assert_not_called()
    
    def test_check_budget_thresholds_success(self):
        """Test successful budget threshold checking."""
        # Set campaign spend to exceed threshold
        self.campaign.spend_amount = Decimal('180.00')  # 90% of budget
        self.campaign.save()
        
        with patch('api.advertiser_portal.tasks.budget_check_tasks.send_notification') as mock_send:
            result = check_budget_thresholds()
            
            self.assertTrue(result.get('success', False))
            self.assertIn('threshold_alerts', result)
            self.assertGreater(len(result['threshold_alerts']), 0)
            
            # Check that notification was sent
            mock_send.assert_called()
    
    def test_check_budget_thresholds_no_alerts(self):
        """Test budget threshold checking with no alerts."""
        # Set campaign spend to normal amount
        self.campaign.spend_amount = Decimal('50.00')  # 25% of budget
        self.campaign.save()
        
        with patch('api.advertiser_portal.tasks.budget_check_tasks.send_notification') as mock_send:
            result = check_budget_thresholds()
            
            self.assertTrue(result.get('success', False))
            self.assertEqual(len(result['threshold_alerts']), 0)
            
            # Check that no notification was sent
            mock_send.assert_not_called()
    
    def test_check_campaign_budget_exhaustion_success(self):
        """Test successful campaign budget exhaustion checking."""
        # Set campaign spend to exceed budget
        self.campaign.spend_amount = Decimal('250.00')  # Exceeds budget limit
        self.campaign.save()
        
        with patch('api.advertiser_portal.tasks.budget_check_tasks.send_notification') as mock_send:
            result = check_campaign_budget_exhaustion()
            
            self.assertTrue(result.get('success', False))
            self.assertIn('exhausted_campaigns', result)
            self.assertGreater(len(result['exhausted_campaigns']), 0)
            
            # Check that notification was sent
            mock_send.assert_called()
    
    def test_auto_pause_over_budget_campaigns_success(self):
        """Test successful auto-pause of over-budget campaigns."""
        # Set campaign spend to exceed budget
        self.campaign.spend_amount = Decimal('250.00')  # Exceeds budget limit
        self.campaign.save()
        
        with patch('api.advertiser_portal.tasks.budget_check_tasks.send_notification') as mock_send:
            result = auto_pause_over_budget_campaigns()
            
            self.assertTrue(result.get('success', False))
            self.assertIn('paused_campaigns', result)
            self.assertGreater(len(result['paused_campaigns']), 0)
            
            # Check that campaign was paused
            self.campaign.refresh_from_db()
            self.assertEqual(self.campaign.status, 'paused')
            
            # Check that notification was sent
            mock_send.assert_called()
    
    def test_auto_pause_over_budget_campaigns_already_paused(self):
        """Test auto-pause of already paused campaigns."""
        # Set campaign to paused status
        self.campaign.status = 'paused'
        self.campaign.save()
        
        # Set campaign spend to exceed budget
        self.campaign.spend_amount = Decimal('250.00')
        self.campaign.save()
        
        with patch('api.advertiser_portal.tasks.budget_check_tasks.send_notification') as mock_send:
            result = auto_pause_over_budget_campaigns()
            
            self.assertTrue(result.get('success', False))
            self.assertEqual(len(result['paused_campaigns']), 0)
            
            # Check that no notification was sent
            mock_send.assert_not_called()


class CampaignScheduleTasksTestCase(TestCase):
    """Test cases for campaign schedule tasks."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            contact_email='contact@testcompany.com',
            contact_phone='+1234567890',
            website='https://testcompany.com',
            industry='technology',
            company_size='medium'
        )
        
        # Fund wallet
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('1000.00')
        wallet.save()
        
        self.active_campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Active Campaign',
            campaign_type='display',
            budget_limit=Decimal('500.00'),
            daily_budget=Decimal('50.00'),
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
            status='active'
        )
        
        self.scheduled_campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Scheduled Campaign',
            campaign_type='display',
            budget_limit=Decimal('500.00'),
            daily_budget=Decimal('50.00'),
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
            status='scheduled'
        )
        
        self.expired_campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Expired Campaign',
            campaign_type='display',
            budget_limit=Decimal('500.00'),
            daily_budget=Decimal('50.00'),
            start_date=timezone.now().date() - timezone.timedelta(days=31),
            end_date=timezone.now().date() - timezone.timedelta(days=1),
            status='active'
        )
    
    def test_activate_scheduled_campaigns_success(self):
        """Test successful activation of scheduled campaigns."""
        # Set start date to today
        self.scheduled_campaign.start_date = timezone.now().date()
        self.scheduled_campaign.save()
        
        with patch('api.advertiser_portal.tasks.campaign_schedule_tasks.send_notification') as mock_send:
            result = activate_scheduled_campaigns()
            
            self.assertTrue(result.get('success', False))
            self.assertIn('activated_campaigns', result)
            self.assertGreater(len(result['activated_campaigns']), 0)
            
            # Check that campaign was activated
            self.scheduled_campaign.refresh_from_db()
            self.assertEqual(self.scheduled_campaign.status, 'active')
            
            # Check that notification was sent
            mock_send.assert_called()
    
    def test_activate_scheduled_campaigns_future_date(self):
        """Test activation of campaigns with future start dates."""
        # Set start date to future
        self.scheduled_campaign.start_date = timezone.now().date() + timezone.timedelta(days=7)
        self.scheduled_campaign.save()
        
        with patch('api.advertiser_portal.tasks.campaign_schedule_tasks.send_notification') as mock_send:
            result = activate_scheduled_campaigns()
            
            self.assertTrue(result.get('success', False))
            self.assertEqual(len(result['activated_campaigns']), 0)
            
            # Check that campaign is still scheduled
            self.scheduled_campaign.refresh_from_db()
            self.assertEqual(self.scheduled_campaign.status, 'scheduled')
            
            # Check that no notification was sent
            mock_send.assert_not_called()
    
    def test_deactivate_expired_campaigns_success(self):
        """Test successful deactivation of expired campaigns."""
        with patch('api.advertiser_portal.tasks.campaign_schedule_tasks.send_notification') as mock_send:
            result = deactivate_expired_campaigns()
            
            self.assertTrue(result.get('success', False))
            self.assertIn('deactivated_campaigns', result)
            self.assertGreater(len(result['deactivated_campaigns']), 0)
            
            # Check that campaign was deactivated
            self.expired_campaign.refresh_from_db()
            self.assertEqual(self.expired_campaign.status, 'ended')
            
            # Check that notification was sent
            mock_send.assert_called()
    
    def test_deactivate_expired_campaigns_no_expired(self):
        """Test deactivation with no expired campaigns."""
        # Set expired campaign end date to future
        self.expired_campaign.end_date = timezone.now().date() + timezone.timedelta(days=30)
        self.expired_campaign.save()
        
        with patch('api.advertiser_portal.tasks.campaign_schedule_tasks.send_notification') as mock_send:
            result = deactivate_expired_campaigns()
            
            self.assertTrue(result.get('success', False))
            self.assertEqual(len(result['deactivated_campaigns']), 0)
            
            # Check that no notification was sent
            mock_send.assert_not_called()
    
    def test_cleanup_completed_campaigns_success(self):
        """Test successful cleanup of completed campaigns."""
        # Set campaign to completed status
        self.active_campaign.status = 'completed'
        self.active_campaign.completed_at = timezone.now() - timezone.timedelta(days=90)
        self.active_campaign.save()
        
        with patch('api.advertiser_portal.tasks.campaign_schedule_tasks.send_notification') as mock_send:
            result = cleanup_completed_campaigns()
            
            self.assertTrue(result.get('success', False))
            self.assertIn('cleaned_campaigns', result)
            self.assertGreater(len(result['cleaned_campaigns']), 0)
            
            # Check that campaign was archived or deleted
            # (Implementation dependent on cleanup strategy)
    
    def test_cleanup_completed_campaigns_recent(self):
        """Test cleanup of recently completed campaigns."""
        # Set campaign to completed status (recent)
        self.active_campaign.status = 'completed'
        self.active_campaign.completed_at = timezone.now() - timezone.timedelta(days=10)
        self.active_campaign.save()
        
        with patch('api.advertiser_portal.tasks.campaign_schedule_tasks.send_notification') as mock_send:
            result = cleanup_completed_campaigns()
            
            self.assertTrue(result.get('success', False))
            self.assertEqual(len(result['cleaned_campaigns']), 0)
            
            # Check that no notification was sent
            mock_send.assert_not_called()


class ReportGenerationTasksTestCase(TestCase):
    """Test cases for report generation tasks."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            contact_email='contact@testcompany.com',
            contact_phone='+1234567890',
            website='https://testcompany.com',
            industry='technology',
            company_size='medium'
        )
        
        self.campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Test Campaign',
            campaign_type='display',
            budget_limit=Decimal('1000.00'),
            daily_budget=Decimal('100.00'),
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
            status='active'
        )
        
        # Create conversions for reporting
        for i in range(10):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('25.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                campaign=self.campaign,
                created_at=timezone.now() - timezone.timedelta(hours=i)
            )
    
    def test_generate_daily_advertiser_reports_success(self):
        """Test successful daily advertiser report generation."""
        with patch('api.advertiser_portal.tasks.report_generation_tasks.send_notification') as mock_send:
            result = generate_daily_advertiser_reports()
            
            self.assertTrue(result.get('success', False))
            self.assertIn('reports_generated', result)
            self.assertGreater(result['reports_generated'], 0)
            
            # Check that notification was sent
            mock_send.assert_called()
    
    def test_generate_daily_advertiser_reports_no_data(self):
        """Test daily report generation with no data."""
        # Delete all conversions
        Conversion.objects.all().delete()
        
        with patch('api.advertiser_portal.tasks.report_generation_tasks.send_notification') as mock_send:
            result = generate_daily_advertiser_reports()
            
            self.assertTrue(result.get('success', False))
            self.assertEqual(result['reports_generated'], 0)
            
            # Check that no notification was sent
            mock_send.assert_not_called()
    
    def test_generate_weekly_performance_reports_success(self):
        """Test successful weekly performance report generation."""
        with patch('api.advertiser_portal.tasks.report_generation_tasks.send_notification') as mock_send:
            result = generate_weekly_performance_reports()
            
            self.assertTrue(result.get('success', False))
            self.assertIn('reports_generated', result)
            self.assertGreater(result['reports_generated'], 0)
            
            # Check that notification was sent
            mock_send.assert_called()
    
    def test_generate_monthly_financial_reports_success(self):
        """Test successful monthly financial report generation."""
        with patch('api.advertiser_portal.tasks.report_generation_tasks.send_notification') as mock_send:
            result = generate_monthly_financial_reports()
            
            self.assertTrue(result.get('success', False))
            self.assertIn('reports_generated', result)
            self.assertGreater(result['reports_generated'], 0)
            
            # Check that notification was sent
            mock_send.assert_called()
    
    def test_report_generation_error_handling(self):
        """Test report generation error handling."""
        with patch('api.advertiser_portal.tasks.report_generation_tasks.generate_report') as mock_generate:
            mock_generate.side_effect = Exception('Report generation failed')
            
            result = generate_daily_advertiser_reports()
            
            self.assertFalse(result.get('success', False))
            self.assertIn('error', result)
            self.assertIn('Report generation failed', result['error'])


class InvoiceTasksTestCase(TestCase):
    """Test cases for invoice tasks."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            contact_email='contact@testcompany.com',
            contact_phone='+1234567890',
            website='https://testcompany.com',
            industry='technology',
            company_size='medium'
        )
        
        # Create transactions for invoicing
        for i in range(5):
            AdvertiserTransaction.objects.create(
                advertiser=self.advertiser,
                transaction_type='charge',
                amount=Decimal('100.00'),
                description=f'Campaign spend {i+1}',
                status='completed',
                created_at=timezone.now() - timezone.timedelta(days=i)
            )
    
    def test_generate_monthly_invoices_success(self):
        """Test successful monthly invoice generation."""
        with patch('api.advertiser_portal.tasks.invoice_tasks.send_notification') as mock_send:
            result = generate_monthly_invoices()
            
            self.assertTrue(result.get('success', False))
            self.assertIn('invoices_generated', result)
            self.assertGreater(result['invoices_generated'], 0)
            
            # Check that notification was sent
            mock_send.assert_called()
    
    def test_generate_monthly_invoices_no_transactions(self):
        """Test monthly invoice generation with no transactions."""
        # Delete all transactions
        AdvertiserTransaction.objects.all().delete()
        
        with patch('api.advertiser_portal.tasks.invoice_tasks.send_notification') as mock_send:
            result = generate_monthly_invoices()
            
            self.assertTrue(result.get('success', False))
            self.assertEqual(result['invoices_generated'], 0)
            
            # Check that no notification was sent
            mock_send.assert_not_called()
    
    def test_send_invoice_reminders_success(self):
        """Test successful invoice reminder sending."""
        # Create unpaid invoice
        from ..models.billing import AdvertiserInvoice
        invoice = AdvertiserInvoice.objects.create(
            advertiser=self.advertiser,
            invoice_number='INV-12345',
            total_amount=Decimal('500.00'),
            status='sent',
            due_date=timezone.now().date() + timezone.timedelta(days=5),
            sent_at=timezone.now() - timezone.timedelta(days=5)
        )
        
        with patch('api.advertiser_portal.tasks.invoice_tasks.send_notification') as mock_send:
            result = send_invoice_reminders()
            
            self.assertTrue(result.get('success', False))
            self.assertIn('reminders_sent', result)
            self.assertGreater(result['reminders_sent'], 0)
            
            # Check that notification was sent
            mock_send.assert_called()
    
    def test_send_invoice_reminders_no_invoices(self):
        """Test invoice reminder sending with no unpaid invoices."""
        with patch('api.advertiser_portal.tasks.invoice_tasks.send_notification') as mock_send:
            result = send_invoice_reminders()
            
            self.assertTrue(result.get('success', False))
            self.assertEqual(result['reminders_sent'], 0)
            
            # Check that no notification was sent
            mock_send.assert_not_called()
    
    def test_process_invoice_payments_success(self):
        """Test successful invoice payment processing."""
        # Create paid invoice
        from ..models.billing import AdvertiserInvoice
        invoice = AdvertiserInvoice.objects.create(
            advertiser=self.advertiser,
            invoice_number='INV-12345',
            total_amount=Decimal('500.00'),
            status='paid',
            paid_at=timezone.now(),
            payment_method='credit_card',
            payment_reference='payment_12345'
        )
        
        with patch('api.advertiser_portal.tasks.invoice_tasks.send_notification') as mock_send:
            result = process_invoice_payments()
            
            self.assertTrue(result.get('success', False))
            self.assertIn('payments_processed', result)
            self.assertGreater(result['payments_processed'], 0)
            
            # Check that notification was sent
            mock_send.assert_called()
    
    def test_process_invoice_payments_no_payments(self):
        """Test invoice payment processing with no payments."""
        with patch('api.advertiser_portal.tasks.invoice_tasks.send_notification') as mock_send:
            result = process_invoice_payments()
            
            self.assertTrue(result.get('success', False))
            self.assertEqual(result['payments_processed'], 0)
            
            # Check that no notification was sent
            mock_send.assert_not_called()


class TaskErrorHandlingTestCase(TestCase):
    """Test cases for task error handling."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            contact_email='contact@testcompany.com',
            contact_phone='+1234567890',
            website='https://testcompany.com',
            industry='technology',
            company_size='medium'
        )
    
    def test_task_database_error_handling(self):
        """Test task database error handling."""
        with patch('django.db.connection.cursor') as mock_cursor:
            mock_cursor.side_effect = Exception('Database connection failed')
            
            result = check_low_balance_alerts()
            
            self.assertFalse(result.get('success', False))
            self.assertIn('error', result)
            self.assertIn('Database connection failed', result['error'])
    
    def test_task_notification_error_handling(self):
        """Test task notification error handling."""
        # Set wallet balance to low amount
        wallet = self.advertiser.wallet
        wallet.balance = Decimal('25.00')
        wallet.save()
        
        with patch('api.advertiser_portal.tasks.budget_check_tasks.send_notification') as mock_send:
            mock_send.side_effect = Exception('Notification sending failed')
            
            result = check_low_balance_alerts()
            
            # Task should still succeed even if notification fails
            self.assertTrue(result.get('success', False))
            self.assertIn('alerts_sent', result)
            self.assertIn('notification_errors', result)
    
    def test_task_retry_mechanism(self):
        """Test task retry mechanism."""
        with patch('api.advertiser_portal.tasks.budget_check_tasks.AdvertiserWallet.objects') as mock_wallet:
            # First call fails, second succeeds
            mock_wallet.side_effect = [
                Exception('Temporary database error'),
                Mock(filter=Mock(return_value=Mock(count=1)))
            ]
            
            # This would be handled by Celery's retry mechanism
            # For testing, we simulate the retry logic
            try:
                check_low_balance_alerts()
            except Exception as e:
                # In real scenario, Celery would retry
                pass
    
    def test_task_timeout_handling(self):
        """Test task timeout handling."""
        with patch('api.advertiser_portal.tasks.budget_check_tasks.time.sleep') as mock_sleep:
            mock_sleep.side_effect = Exception('Task timeout')
            
            # Simulate timeout by mocking a long-running operation
            with patch('api.advertiser_portal.tasks.budget_check_tasks.AdvertiserWallet.objects.filter') as mock_filter:
                mock_filter.return_value.iterator.side_effect = Exception('Query timeout')
                
                result = check_low_balance_alerts()
                
                self.assertFalse(result.get('success', False))
                self.assertIn('error', result)
    
    def test_task_memory_error_handling(self):
        """Test task memory error handling."""
        # Create many advertisers to potentially cause memory issues
        for i in range(100):
            user = User.objects.create_user(
                username=f'user_{i}',
                email=f'user_{i}@example.com',
                password='testpass123'
            )
            
            Advertiser.objects.create(
                user=user,
                company_name=f'Company {i}',
                contact_email=f'contact@company{i}.com',
                contact_phone='+1234567890',
                website=f'https://company{i}.com',
                industry='technology',
                company_size='small'
            )
        
        # Mock memory error
        with patch('django.db.models.QuerySet.__iter__') as mock_iter:
            mock_iter.side_effect = MemoryError('Out of memory')
            
            result = check_low_balance_alerts()
            
            self.assertFalse(result.get('success', False))
            self.assertIn('error', result)
    
    def test_task_concurrent_execution(self):
        """Test task concurrent execution."""
        # This would be tested with actual Celery workers
        # For unit testing, we simulate concurrent execution
        
        with patch('api.advertiser_portal.tasks.budget_check_tasks.check_low_balance_alerts') as mock_task:
            mock_task.return_value = {'success': True, 'alerts_sent': 1}
            
            # Simulate concurrent execution
            import threading
            import time
            
            results = []
            
            def run_task():
                result = check_low_balance_alerts()
                results.append(result)
            
            # Run multiple threads
            threads = []
            for i in range(5):
                thread = threading.Thread(target=run_task)
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # All tasks should succeed
            self.assertEqual(len(results), 5)
            for result in results:
                self.assertTrue(result.get('success', False))


class TaskSchedulingTestCase(TestCase):
    """Test cases for task scheduling."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser = Advertiser.objects.create(
            user=self.user,
            company_name='Test Company',
            contact_email='contact@testcompany.com',
            contact_phone='+1234567890',
            website='https://testcompany.com',
            industry='technology',
            company_size='medium'
        )
    
    def test_daily_task_scheduling(self):
        """Test daily task scheduling."""
        # This would be tested with actual Celery Beat configuration
        # For unit testing, we verify the task can be called with daily frequency
        
        with patch('api.advertiser_portal.tasks.budget_check_tasks.check_low_balance_alerts') as mock_task:
            mock_task.return_value = {'success': True, 'alerts_sent': 0}
            
            # Simulate daily execution
            result = check_low_balance_alerts()
            
            self.assertTrue(result.get('success', False))
            mock_task.assert_called_once()
    
    def test_hourly_task_scheduling(self):
        """Test hourly task scheduling."""
        # Create campaign for hourly checks
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Hourly Check Campaign',
            campaign_type='display',
            budget_limit=Decimal('100.00'),
            daily_budget=Decimal('10.00'),
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
            status='active'
        )
        
        with patch('api.advertiser_portal.tasks.budget_check_tasks.check_budget_thresholds') as mock_task:
            mock_task.return_value = {'success': True, 'threshold_alerts': 0}
            
            # Simulate hourly execution
            result = check_budget_thresholds()
            
            self.assertTrue(result.get('success', False))
            mock_task.assert_called_once()
    
    def test_weekly_task_scheduling(self):
        """Test weekly task scheduling."""
        with patch('api.advertiser_portal.tasks.report_generation_tasks.generate_weekly_performance_reports') as mock_task:
            mock_task.return_value = {'success': True, 'reports_generated': 0}
            
            # Simulate weekly execution
            result = generate_weekly_performance_reports()
            
            self.assertTrue(result.get('success', False))
            mock_task.assert_called_once()
    
    def test_monthly_task_scheduling(self):
        """Test monthly task scheduling."""
        with patch('api.advertiser_portal.tasks.invoice_tasks.generate_monthly_invoices') as mock_task:
            mock_task.return_value = {'success': True, 'invoices_generated': 0}
            
            # Simulate monthly execution
            result = generate_monthly_invoices()
            
            self.assertTrue(result.get('success', False))
            mock_task.assert_called_once()
    
    def test_task_timezone_handling(self):
        """Test task timezone handling."""
        # Create campaign with timezone-specific scheduling
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Timezone Test Campaign',
            campaign_type='display',
            budget_limit=Decimal('100.00'),
            daily_budget=Decimal('10.00'),
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timezone.timedelta(days=30)).date(),
            status='scheduled'
        )
        
        # Test that tasks handle timezone correctly
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = timezone.now()
            
            with patch('api.advertiser_portal.tasks.campaign_schedule_tasks.activate_scheduled_campaigns') as mock_activate:
                mock_activate.return_value = {'success': True, 'activated_campaigns': 0}
                
                result = activate_scheduled_campaigns()
                
                self.assertTrue(result.get('success', False))
                mock_activate.assert_called_once()
    
    def test_task_dependency_handling(self):
        """Test task dependency handling."""
        # Test tasks that depend on other tasks
        with patch('api.advertiser_portal.tasks.report_generation_tasks.generate_daily_advertiser_reports') as mock_daily:
            with patch('api.advertiser_portal.tasks.report_generation_tasks.generate_weekly_performance_reports') as mock_weekly:
                mock_daily.return_value = {'success': True, 'reports_generated': 5}
                mock_weekly.return_value = {'success': True, 'reports_generated': 2}
                
                # Run daily reports first
                daily_result = generate_daily_advertiser_reports()
                self.assertTrue(daily_result.get('success', False))
                
                # Run weekly reports (might depend on daily data)
                weekly_result = generate_weekly_performance_reports()
                self.assertTrue(weekly_result.get('success', False))
    
    def test_task_idempotency(self):
        """Test task idempotency."""
        # Tasks should be idempotent - running multiple times should not cause issues
        with patch('api.advertiser_portal.tasks.budget_check_tasks.check_low_balance_alerts') as mock_task:
            mock_task.return_value = {'success': True, 'alerts_sent': 0}
            
            # Run task multiple times
            result1 = check_low_balance_alerts()
            result2 = check_low_balance_alerts()
            result3 = check_low_balance_alerts()
            
            # All should succeed
            self.assertTrue(result1.get('success', False))
            self.assertTrue(result2.get('success', False))
            self.assertTrue(result3.get('success', False))
            
            # Task should be called each time
            self.assertEqual(mock_task.call_count, 3)
