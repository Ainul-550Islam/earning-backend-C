"""
Test Campaign Scheduler Service

Comprehensive tests for campaign scheduling functionality
including automated campaign lifecycle management.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from unittest.mock import Mock, patch, MagicMock

from ..models.campaign import AdCampaign, CampaignSchedule
from ..models.advertiser import Advertiser
try:
    from ..services import CampaignSchedulerService
except ImportError:
    CampaignSchedulerService = None
from ..tasks.campaign_schedule_tasks import (
    start_scheduled_campaigns,
    pause_expired_campaigns,
    update_campaign_schedules,
    check_campaign_schedule_conflicts
)

User = get_user_model()


class CampaignSchedulerServiceTestCase(APITestCase):
    """Test cases for CampaignSchedulerService."""
    
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
            website='https://test.com',
            business_type='business',
            country='US',
            verification_status='verified'
        )
        
        self.campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Test Campaign',
            description='Test campaign description',
            status='draft'
        )
        
        self.scheduler_service = CampaignSchedulerService()
    
    def test_start_campaign_immediately(self):
        """Test starting a campaign immediately."""
        result = self.scheduler_service.start_campaign(
            campaign=self.campaign,
            start_immediately=True
        )
        
        self.assertTrue(result['success'])
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, 'active')
        self.assertIsNotNone(self.campaign.started_at)
    
    def test_schedule_campaign_start(self):
        """Test scheduling campaign start for future date."""
        start_date = timezone.now() + timezone.timedelta(days=1)
        
        result = self.scheduler_service.schedule_campaign_start(
            campaign=self.campaign,
            start_date=start_date
        )
        
        self.assertTrue(result['success'])
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, 'scheduled')
        
        # Check schedule was created
        schedule = CampaignSchedule.objects.get(campaign=self.campaign)
        self.assertEqual(schedule.start_date, start_date)
    
    def test_schedule_campaign_end(self):
        """Test scheduling campaign end."""
        end_date = timezone.now() + timezone.timedelta(days=7)
        
        result = self.scheduler_service.schedule_campaign_end(
            campaign=self.campaign,
            end_date=end_date
        )
        
        self.assertTrue(result['success'])
        
        # Check schedule was created
        schedule = CampaignSchedule.objects.get(campaign=self.campaign)
        self.assertEqual(schedule.end_date, end_date)
    
    def test_pause_campaign(self):
        """Test pausing a campaign."""
        # First start the campaign
        self.campaign.status = 'active'
        self.campaign.save()
        
        result = self.scheduler_service.pause_campaign(self.campaign)
        
        self.assertTrue(result['success'])
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, 'paused')
        self.assertIsNotNone(self.campaign.paused_at)
    
    def test_resume_campaign(self):
        """Test resuming a paused campaign."""
        # First pause the campaign
        self.campaign.status = 'paused'
        self.campaign.save()
        
        result = self.scheduler_service.resume_campaign(self.campaign)
        
        self.assertTrue(result['success'])
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, 'active')
        self.assertIsNotNone(self.campaign.resumed_at)
    
    def test_get_campaign_schedule(self):
        """Test getting campaign schedule."""
        # Create a schedule
        start_date = timezone.now() + timezone.timedelta(days=1)
        end_date = timezone.now() + timezone.timedelta(days=7)
        
        CampaignSchedule.objects.create(
            campaign=self.campaign,
            start_date=start_date,
            end_date=end_date
        )
        
        schedule = self.scheduler_service.get_campaign_schedule(self.campaign)
        
        self.assertIsNotNone(schedule)
        self.assertEqual(schedule.start_date, start_date)
        self.assertEqual(schedule.end_date, end_date)
    
    def test_update_campaign_schedule(self):
        """Test updating campaign schedule."""
        # Create initial schedule
        start_date = timezone.now() + timezone.timedelta(days=1)
        schedule = CampaignSchedule.objects.create(
            campaign=self.campaign,
            start_date=start_date
        )
        
        # Update schedule
        new_start_date = timezone.now() + timezone.timedelta(days=2)
        new_end_date = timezone.now() + timezone.timedelta(days=10)
        
        result = self.scheduler_service.update_campaign_schedule(
            campaign=self.campaign,
            start_date=new_start_date,
            end_date=new_end_date
        )
        
        self.assertTrue(result['success'])
        schedule.refresh_from_db()
        self.assertEqual(schedule.start_date, new_start_date)
        self.assertEqual(schedule.end_date, new_end_date)
    
    def test_delete_campaign_schedule(self):
        """Test deleting campaign schedule."""
        # Create a schedule
        CampaignSchedule.objects.create(
            campaign=self.campaign,
            start_date=timezone.now() + timezone.timedelta(days=1)
        )
        
        result = self.scheduler_service.delete_campaign_schedule(self.campaign)
        
        self.assertTrue(result['success'])
        self.assertFalse(CampaignSchedule.objects.filter(campaign=self.campaign).exists())
    
    def test_validate_schedule_dates(self):
        """Test schedule date validation."""
        # Test invalid dates (end before start)
        start_date = timezone.now() + timezone.timedelta(days=7)
        end_date = timezone.now() + timezone.timedelta(days=1)
        
        with self.assertRaises(Exception):  # Should raise validation error
            self.scheduler_service.schedule_campaign_start(
                campaign=self.campaign,
                start_date=start_date,
                end_date=end_date
            )
    
    def test_get_scheduled_campaigns(self):
        """Test getting all scheduled campaigns."""
        # Create multiple campaigns with schedules
        for i in range(3):
            campaign = AdCampaign.objects.create(
                advertiser=self.advertiser,
                name=f'Test Campaign {i}',
                description=f'Test campaign {i} description',
                status='scheduled'
            )
            
            CampaignSchedule.objects.create(
                campaign=campaign,
                start_date=timezone.now() + timezone.timedelta(days=i+1)
            )
        
        scheduled_campaigns = self.scheduler_service.get_scheduled_campaigns()
        
        self.assertEqual(len(scheduled_campaigns), 3)
    
    def test_check_schedule_conflicts(self):
        """Test checking for schedule conflicts."""
        # Create a campaign with schedule
        start_date = timezone.now() + timezone.timedelta(days=1)
        end_date = timezone.now() + timezone.timedelta(days=7)
        
        CampaignSchedule.objects.create(
            campaign=self.campaign,
            start_date=start_date,
            end_date=end_date
        )
        
        # Try to create conflicting schedule
        conflicting_start = start_date + timezone.timedelta(days=2)
        conflicting_end = end_date + timezone.timedelta(days=2)
        
        conflicts = self.scheduler_service.check_schedule_conflicts(
            advertiser=self.advertiser,
            start_date=conflicting_start,
            end_date=conflicting_end
        )
        
        self.assertTrue(len(conflicts) > 0)
    
    @patch('advertiser_portal.services.campaign.CampaignSchedulerService.logger')
    def test_error_handling(self, mock_logger):
        """Test error handling in scheduler service."""
        # Test with invalid campaign
        with self.assertRaises(Exception):
            self.scheduler_service.start_campaign(None)
        
        # Verify error was logged
        mock_logger.error.assert_called()


class CampaignScheduleTasksTestCase(APITestCase):
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
            website='https://test.com',
            business_type='business',
            country='US',
            verification_status='verified'
        )
        
        # Create campaigns with different schedules
        self.campaign_to_start = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Campaign to Start',
            status='scheduled'
        )
        
        self.campaign_to_pause = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Campaign to Pause',
            status='active'
        )
        
        # Create schedules
        CampaignSchedule.objects.create(
            campaign=self.campaign_to_start,
            start_date=timezone.now() - timezone.timedelta(hours=1),  # Should start now
            end_date=timezone.now() + timezone.timedelta(days=7)
        )
        
        CampaignSchedule.objects.create(
            campaign=self.campaign_to_pause,
            start_date=timezone.now() - timezone.timedelta(days=1),
            end_date=timezone.now() + timezone.timedelta(hours=1)  # Should pause now
        )
    
    def test_start_scheduled_campaigns_task(self):
        """Test start_scheduled_campaigns task."""
        result = start_scheduled_campaigns()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['campaigns_started'], 1)
        
        # Check campaign was started
        self.campaign_to_start.refresh_from_db()
        self.assertEqual(self.campaign_to_start.status, 'active')
    
    def test_pause_expired_campaigns_task(self):
        """Test pause_expired_campaigns task."""
        result = pause_expired_campaigns()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['campaigns_paused'], 1)
        
        # Check campaign was paused
        self.campaign_to_pause.refresh_from_db()
        self.assertEqual(self.campaign_to_pause.status, 'paused')
    
    def test_update_campaign_schedules_task(self):
        """Test update_campaign_schedules task."""
        result = update_campaign_schedules()
        
        self.assertTrue(result['success'])
        self.assertIn('schedules_updated', result)
    
    def test_check_campaign_schedule_conflicts_task(self):
        """Test check_campaign_schedule_conflicts task."""
        result = check_campaign_schedule_conflicts()
        
        self.assertTrue(result['success'])
        self.assertIn('conflicts_found', result)


class CampaignScheduleIntegrationTestCase(APITestCase):
    """Integration tests for campaign scheduling."""
    
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
            website='https://test.com',
            business_type='business',
            country='US',
            verification_status='verified'
        )
        
        self.scheduler_service = CampaignSchedulerService()
    
    def test_complete_campaign_lifecycle(self):
        """Test complete campaign lifecycle with scheduling."""
        # 1. Create campaign
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Lifecycle Test Campaign',
            description='Testing complete lifecycle',
            status='draft'
        )
        
        # 2. Schedule campaign to start in future
        start_date = timezone.now() + timezone.timedelta(hours=1)
        end_date = timezone.now() + timezone.timedelta(days=7)
        
        result = self.scheduler_service.schedule_campaign_start(
            campaign=campaign,
            start_date=start_date,
            end_date=end_date
        )
        
        self.assertTrue(result['success'])
        
        # 3. Manually start campaign (simulating scheduled start)
        result = self.scheduler_service.start_campaign(campaign)
        self.assertTrue(result['success'])
        
        # 4. Pause campaign
        result = self.scheduler_service.pause_campaign(campaign)
        self.assertTrue(result['success'])
        
        # 5. Resume campaign
        result = self.scheduler_service.resume_campaign(campaign)
        self.assertTrue(result['success'])
        
        # 6. End campaign
        result = self.scheduler_service.pause_campaign(campaign)  # Simulate end
        self.assertTrue(result['success'])
        
        # Verify final state
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'paused')
    
    def test_multiple_campaign_scheduling(self):
        """Test scheduling multiple campaigns."""
        campaigns = []
        
        # Create multiple campaigns
        for i in range(5):
            campaign = AdCampaign.objects.create(
                advertiser=self.advertiser,
                name=f'Multi Test Campaign {i}',
                description=f'Testing multiple campaigns {i}',
                status='draft'
            )
            campaigns.append(campaign)
        
        # Schedule all campaigns
        for i, campaign in enumerate(campaigns):
            start_date = timezone.now() + timezone.timedelta(hours=i+1)
            result = self.scheduler_service.schedule_campaign_start(
                campaign=campaign,
                start_date=start_date
            )
            self.assertTrue(result['success'])
        
        # Verify all campaigns are scheduled
        scheduled_campaigns = self.scheduler_service.get_scheduled_campaigns()
        self.assertEqual(len(scheduled_campaigns), 5)
    
    def test_schedule_with_budget_constraints(self):
        """Test scheduling with budget constraints."""
        # Create campaign with budget
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Budget Test Campaign',
            description='Testing budget constraints',
            daily_budget=Decimal('100.00'),
            total_budget=Decimal('1000.00'),
            status='draft'
        )
        
        # Schedule campaign
        start_date = timezone.now() + timezone.timedelta(hours=1)
        result = self.scheduler_service.schedule_campaign_start(
            campaign=campaign,
            start_date=start_date
        )
        
        self.assertTrue(result['success'])
        
        # Start campaign and check budget is respected
        result = self.scheduler_service.start_campaign(campaign)
        self.assertTrue(result['success'])
        
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'active')
        self.assertEqual(campaign.daily_budget, Decimal('100.00'))
    
    @patch('advertiser_portal.tasks.campaign_schedule_tasks.start_scheduled_campaigns')
    def test_task_integration(self, mock_task):
        """Test integration with Celery tasks."""
        # Schedule a campaign
        campaign = AdCampaign.objects.create(
            advertiser=self.advertiser,
            name='Task Integration Campaign',
            description='Testing task integration',
            status='scheduled'
        )
        
        CampaignSchedule.objects.create(
            campaign=campaign,
            start_date=timezone.now() - timezone.timedelta(hours=1)  # Should start now
        )
        
        # Run task
        result = start_scheduled_campaigns()
        
        # Verify task was called
        mock_task.assert_called_once()
        
        # Check campaign was started
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'active')
