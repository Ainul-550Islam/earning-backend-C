"""
Test Report Service

Comprehensive tests for report service functionality
including report generation, scheduling, and export.
"""

from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch, MagicMock

from ..models.advertiser import Advertiser
from ..models.campaign import AdCampaign
from ..models.offer import AdvertiserOffer
from ..models.tracking import Conversion, TrackingPixel
try:
    from ..services import AdvertiserReportService
except ImportError:
    AdvertiserReportService = None
try:
    from ..services import RealtimeDashboardService
except ImportError:
    RealtimeDashboardService = None
try:
    from ..services import ReportExportService
except ImportError:
    ReportExportService = None
try:
    from ..services import AdvertiserService
except ImportError:
    AdvertiserService = None

User = get_user_model()


class AdvertiserReportServiceTestCase(TestCase):
    """Test cases for AdvertiserReportService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.report_service = AdvertiserReportService()
        
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
        
        # Create campaign
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
        
        # Create offer
        self.offer = AdvertiserOffer.objects.create(
            advertiser=self.advertiser,
            name='Test Offer',
            offer_type='cpa',
            payout_amount=Decimal('10.00'),
            currency='USD',
            landing_page='https://example.com/offer',
            target_countries=['US', 'CA', 'UK'],
            status='active'
        )
    
    def test_generate_performance_report_success(self):
        """Test successful performance report generation."""
        # Create some conversions
        for i in range(10):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal(str(10.00 + i)),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                campaign=self.campaign,
                offer=self.offer,
                created_at=timezone.now() - timezone.timedelta(hours=i)
            )
        
        # Generate report
        report = self.report_service.generate_performance_report(
            self.advertiser,
            start_date=timezone.now().date() - timezone.timedelta(days=7),
            end_date=timezone.now().date()
        )
        
        self.assertIn('summary', report)
        self.assertIn('campaign_performance', report)
        self.assertIn('offer_performance', report)
        self.assertIn('daily_breakdown', report)
        self.assertIn('metrics', report)
        
        # Check summary data
        summary = report['summary']
        self.assertIn('total_conversions', summary)
        self.assertIn('total_revenue', summary)
        self.assertIn('average_revenue', summary)
        self.assertIn('conversion_rate', summary)
        
        self.assertEqual(summary['total_conversions'], 10)
        self.assertGreater(summary['total_revenue'], Decimal('0.00'))
    
    def test_generate_performance_report_no_data(self):
        """Test performance report generation with no data."""
        report = self.report_service.generate_performance_report(
            self.advertiser,
            start_date=timezone.now().date() - timezone.timedelta(days=7),
            end_date=timezone.now().date()
        )
        
        self.assertIn('summary', report)
        self.assertEqual(report['summary']['total_conversions'], 0)
        self.assertEqual(report['summary']['total_revenue'], Decimal('0.00'))
    
    def test_generate_financial_report_success(self):
        """Test successful financial report generation."""
        # Create conversions with revenue
        for i in range(5):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('50.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                campaign=self.campaign,
                offer=self.offer,
                created_at=timezone.now() - timezone.timedelta(days=i)
            )
        
        # Generate report
        report = self.report_service.generate_financial_report(
            self.advertiser,
            start_date=timezone.now().date() - timezone.timedelta(days=7),
            end_date=timezone.now().date()
        )
        
        self.assertIn('revenue_summary', report)
        self.assertIn('cost_analysis', report)
        self.assertIn('profitability', report)
        self.assertIn('financial_trends', report)
        
        # Check revenue summary
        revenue_summary = report['revenue_summary']
        self.assertIn('total_revenue', revenue_summary)
        self.assertIn('average_revenue', revenue_summary)
        self.assertIn('revenue_by_campaign', revenue_summary)
        self.assertIn('revenue_by_offer', revenue_summary)
        
        self.assertEqual(revenue_summary['total_revenue'], Decimal('250.00'))
    
    def test_generate_financial_report_no_data(self):
        """Test financial report generation with no data."""
        report = self.report_service.generate_financial_report(
            self.advertiser,
            start_date=timezone.now().date() - timezone.timedelta(days=7),
            end_date=timezone.now().date()
        )
        
        self.assertIn('revenue_summary', report)
        self.assertEqual(report['revenue_summary']['total_revenue'], Decimal('0.00'))
    
    def test_generate_campaign_report_success(self):
        """Test successful campaign report generation."""
        # Create conversions for campaign
        for i in range(8):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('25.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                campaign=self.campaign,
                created_at=timezone.now() - timezone.timedelta(hours=i)
            )
        
        # Generate report
        report = self.report_service.generate_campaign_report(
            self.campaign,
            start_date=timezone.now().date() - timezone.timedelta(days=7),
            end_date=timezone.now().date()
        )
        
        self.assertIn('campaign_details', report)
        self.assertIn('performance_metrics', report)
        self.assertIn('conversion_analysis', report)
        self.assertIn('daily_performance', report)
        
        # Check performance metrics
        metrics = report['performance_metrics']
        self.assertIn('total_conversions', metrics)
        self.assertIn('total_revenue', metrics)
        self.assertIn('conversion_rate', metrics)
        self.assertIn('average_revenue', metrics)
        
        self.assertEqual(metrics['total_conversions'], 8)
        self.assertEqual(metrics['total_revenue'], Decimal('200.00'))
    
    def test_generate_campaign_report_no_data(self):
        """Test campaign report generation with no data."""
        report = self.report_service.generate_campaign_report(
            self.campaign,
            start_date=timezone.now().date() - timezone.timedelta(days=7),
            end_date=timezone.now().date()
        )
        
        self.assertIn('campaign_details', report)
        self.assertEqual(report['performance_metrics']['total_conversions'], 0)
    
    def test_generate_offer_report_success(self):
        """Test successful offer report generation."""
        # Create conversions for offer
        for i in range(6):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('15.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                offer=self.offer,
                created_at=timezone.now() - timezone.timedelta(hours=i)
            )
        
        # Generate report
        report = self.report_service.generate_offer_report(
            self.offer,
            start_date=timezone.now().date() - timezone.timedelta(days=7),
            end_date=timezone.now().date()
        )
        
        self.assertIn('offer_details', report)
        self.assertIn('performance_metrics', report)
        self.assertIn('conversion_analysis', report)
        self.assertIn('payout_analysis', report)
        
        # Check performance metrics
        metrics = report['performance_metrics']
        self.assertIn('total_conversions', metrics)
        self.assertIn('total_payout', metrics)
        self.assertIn('conversion_rate', metrics)
        
        self.assertEqual(metrics['total_conversions'], 6)
        self.assertEqual(metrics['total_payout'], Decimal('60.00'))
    
    def test_generate_geographic_report_success(self):
        """Test successful geographic report generation."""
        # Create conversions from different countries
        countries = ['US', 'CA', 'UK', 'DE', 'FR']
        for i, country in enumerate(countries):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{country}',
                revenue=Decimal('20.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                custom_parameters={'country': country},
                created_at=timezone.now() - timezone.timedelta(hours=i)
            )
        
        # Generate report
        report = self.report_service.generate_geographic_report(
            self.advertiser,
            start_date=timezone.now().date() - timezone.timedelta(days=7),
            end_date=timezone.now().date()
        )
        
        self.assertIn('geographic_breakdown', report)
        self.assertIn('country_performance', report)
        self.assertIn('regional_trends', report)
        self.assertIn('top_countries', report)
        
        # Check geographic breakdown
        geo_breakdown = report['geographic_breakdown']
        self.assertEqual(len(geo_breakdown), 5)
        self.assertIn('US', geo_breakdown)
        self.assertIn('CA', geo_breakdown)
    
    def test_generate_device_report_success(self):
        """Test successful device report generation."""
        # Create conversions from different devices
        devices = ['desktop', 'mobile', 'tablet']
        for i, device in enumerate(devices):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{device}',
                revenue=Decimal('25.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                custom_parameters={'device_type': device},
                created_at=timezone.now() - timezone.timedelta(hours=i)
            )
        
        # Generate report
        report = self.report_service.generate_device_report(
            self.advertiser,
            start_date=timezone.now().date() - timezone.timedelta(days=7),
            end_date=timezone.now().date()
        )
        
        self.assertIn('device_breakdown', report)
        self.assertIn('device_performance', report)
        self.assertIn('device_trends', report)
        self.assertIn('mobile_vs_desktop', report)
        
        # Check device breakdown
        device_breakdown = report['device_breakdown']
        self.assertEqual(len(device_breakdown), 3)
        self.assertIn('desktop', device_breakdown)
        self.assertIn('mobile', device_breakdown)
    
    def test_generate_time_report_success(self):
        """Test successful time-based report generation."""
        # Create conversions at different times
        for i in range(24):  # One per hour
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_hour_{i}',
                revenue=Decimal('10.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                created_at=timezone.now().replace(hour=i, minute=0, second=0, microsecond=0)
            )
        
        # Generate report
        report = self.report_service.generate_time_report(
            self.advertiser,
            start_date=timezone.now().date(),
            end_date=timezone.now().date()
        )
        
        self.assertIn('hourly_breakdown', report)
        self.assertIn('daily_breakdown', report)
        self.assertIn('peak_hours', report)
        self.assertIn('time_patterns', report)
        
        # Check hourly breakdown
        hourly_breakdown = report['hourly_breakdown']
        self.assertEqual(len(hourly_breakdown), 24)
    
    def test_generate_conversion_funnel_report_success(self):
        """Test successful conversion funnel report generation."""
        # Create conversions with funnel stages
        funnel_stages = ['awareness', 'interest', 'consideration', 'conversion']
        for i, stage in enumerate(funnel_stages):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{stage}',
                revenue=Decimal('25.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                custom_parameters={'funnel_stage': stage},
                created_at=timezone.now() - timezone.timedelta(hours=i)
            )
        
        # Generate report
        report = self.report_service.generate_conversion_funnel_report(
            self.advertiser,
            start_date=timezone.now().date() - timezone.timedelta(days=7),
            end_date=timezone.now().date()
        )
        
        self.assertIn('funnel_stages', report)
        self.assertIn('conversion_rates', report)
        self.assertIn('drop_off_points', report)
        self.assertIn('optimization_opportunities', report)
        
        # Check funnel stages
        stages = report['funnel_stages']
        self.assertEqual(len(stages), 4)
        self.assertIn('awareness', stages)
        self.assertIn('conversion', stages)
    
    def test_generate_roi_report_success(self):
        """Test successful ROI report generation."""
        # Create conversions with cost and revenue data
        for i in range(10):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('50.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                custom_parameters={
                    'cost': Decimal('20.00'),
                    'ad_spend': Decimal('15.00')
                },
                created_at=timezone.now() - timezone.timedelta(hours=i)
            )
        
        # Generate report
        report = self.report_service.generate_roi_report(
            self.advertiser,
            start_date=timezone.now().date() - timezone.timedelta(days=7),
            end_date=timezone.now().date()
        )
        
        self.assertIn('roi_summary', report)
        self.assertIn('campaign_roi', report)
        self.assertIn('offer_roi', report)
        self.assertIn('roi_trends', report)
        
        # Check ROI summary
        roi_summary = report['roi_summary']
        self.assertIn('total_revenue', roi_summary)
        self.assertIn('total_cost', roi_summary)
        self.assertIn('total_roi', roi_summary)
        self.assertIn('roi_percentage', roi_summary)
        
        self.assertEqual(roi_summary['total_revenue'], Decimal('500.00'))
        self.assertEqual(roi_summary['total_cost'], Decimal('200.00'))
        self.assertEqual(roi_summary['total_roi'], Decimal('300.00'))
    
    def test_schedule_report_success(self):
        """Test successful report scheduling."""
        schedule_data = {
            'report_type': 'performance',
            'frequency': 'daily',
            'recipients': ['test@example.com'],
            'format': 'pdf',
            'is_active': True,
        }
        
        schedule = self.report_service.schedule_report(
            self.advertiser,
            schedule_data
        )
        
        self.assertIn('schedule_id', schedule)
        self.assertEqual(schedule['report_type'], 'performance')
        self.assertEqual(schedule['frequency'], 'daily')
        self.assertEqual(schedule['recipients'], ['test@example.com'])
        self.assertTrue(schedule['is_active'])
    
    def test_get_report_schedules_success(self):
        """Test getting report schedules."""
        # Create multiple schedules
        for i in range(3):
            schedule_data = {
                'report_type': ['performance', 'financial', 'campaign'][i],
                'frequency': 'daily',
                'recipients': ['test@example.com'],
                'format': 'pdf',
                'is_active': True,
            }
            
            self.report_service.schedule_report(self.advertiser, schedule_data)
        
        # Get schedules
        schedules = self.report_service.get_report_schedules(self.advertiser)
        
        self.assertEqual(len(schedules), 3)
        
        # Check that all report types are present
        report_types = [s['report_type'] for s in schedules]
        self.assertIn('performance', report_types)
        self.assertIn('financial', report_types)
        self.assertIn('campaign', report_types)
    
    def test_update_report_schedule_success(self):
        """Test successful report schedule update."""
        # Create schedule
        schedule_data = {
            'report_type': 'performance',
            'frequency': 'daily',
            'recipients': ['test@example.com'],
            'format': 'pdf',
            'is_active': True,
        }
        
        schedule = self.report_service.schedule_report(self.advertiser, schedule_data)
        schedule_id = schedule['schedule_id']
        
        # Update schedule
        update_data = {
            'frequency': 'weekly',
            'recipients': ['updated@example.com'],
            'is_active': False,
        }
        
        updated_schedule = self.report_service.update_report_schedule(
            self.advertiser,
            schedule_id,
            update_data
        )
        
        self.assertEqual(updated_schedule['frequency'], 'weekly')
        self.assertEqual(updated_schedule['recipients'], ['updated@example.com'])
        self.assertFalse(updated_schedule['is_active'])
    
    def test_delete_report_schedule_success(self):
        """Test successful report schedule deletion."""
        # Create schedule
        schedule_data = {
            'report_type': 'performance',
            'frequency': 'daily',
            'recipients': ['test@example.com'],
            'format': 'pdf',
            'is_active': True,
        }
        
        schedule = self.report_service.schedule_report(self.advertiser, schedule_data)
        schedule_id = schedule['schedule_id']
        
        # Delete schedule
        result = self.report_service.delete_report_schedule(
            self.advertiser,
            schedule_id
        )
        
        self.assertTrue(result.get('success', False))
        
        # Check that schedule is deleted
        schedules = self.report_service.get_report_schedules(self.advertiser)
        schedule_ids = [s['schedule_id'] for s in schedules]
        self.assertNotIn(schedule_id, schedule_ids)
    
    def test_get_report_history_success(self):
        """Test getting report history."""
        # Generate some reports
        for i in range(3):
            self.report_service.generate_performance_report(
                self.advertiser,
                start_date=timezone.now().date() - timezone.timedelta(days=i+1),
                end_date=timezone.now().date() - timezone.timedelta(days=i)
            )
        
        # Get history
        history = self.report_service.get_report_history(
            self.advertiser,
            days=7
        )
        
        self.assertEqual(len(history), 3)
        
        for report in history:
            self.assertIn('report_type', report)
            self.assertIn('generated_at', report)
            self.assertIn('data_summary', report)
    
    def test_validate_report_parameters_success(self):
        """Test successful report parameter validation."""
        parameters = {
            'start_date': timezone.now().date() - timezone.timedelta(days=7),
            'end_date': timezone.now().date(),
            'report_type': 'performance',
            'format': 'pdf'
        }
        
        is_valid, errors = self.report_service.validate_report_parameters(parameters)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_report_parameters_invalid_dates(self):
        """Test report parameter validation with invalid dates."""
        parameters = {
            'start_date': timezone.now().date(),
            'end_date': timezone.now().date() - timezone.timedelta(days=7),  # End before start
            'report_type': 'performance',
            'format': 'pdf'
        }
        
        is_valid, errors = self.report_service.validate_report_parameters(parameters)
        
        self.assertFalse(is_valid)
        self.assertIn('date_range', errors)
    
    def test_validate_report_parameters_invalid_type(self):
        """Test report parameter validation with invalid type."""
        parameters = {
            'start_date': timezone.now().date() - timezone.timedelta(days=7),
            'end_date': timezone.now().date(),
            'report_type': 'invalid_type',
            'format': 'pdf'
        }
        
        is_valid, errors = self.report_service.validate_report_parameters(parameters)
        
        self.assertFalse(is_valid)
        self.assertIn('report_type', errors)
    
    def test_get_supported_report_types(self):
        """Test getting supported report types."""
        report_types = self.report_service.get_supported_report_types()
        
        expected_types = [
            'performance',
            'financial',
            'campaign',
            'offer',
            'geographic',
            'device',
            'time',
            'conversion_funnel',
            'roi'
        ]
        
        for report_type in expected_types:
            self.assertIn(report_type, report_types)
    
    def test_get_supported_formats(self):
        """Test getting supported report formats."""
        formats = self.report_service.get_supported_formats()
        
        expected_formats = ['pdf', 'excel', 'csv', 'json']
        
        for format_type in expected_formats:
            self.assertIn(format_type, formats)


class RealtimeDashboardServiceTestCase(TestCase):
    """Test cases for RealtimeDashboardService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.dashboard_service = RealtimeDashboardService()
        
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
        
        # Create campaign
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
    
    def test_get_realtime_metrics_success(self):
        """Test successful realtime metrics retrieval."""
        # Create recent conversions
        for i in range(10):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('25.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                campaign=self.campaign,
                created_at=timezone.now() - timezone.timedelta(minutes=i)
            )
        
        # Get realtime metrics
        metrics = self.dashboard_service.get_realtime_metrics(self.advertiser)
        
        self.assertIn('total_conversions', metrics)
        self.assertIn('total_revenue', metrics)
        self.assertIn('conversion_rate', metrics)
        self.assertIn('average_revenue', metrics)
        self.assertIn('active_campaigns', metrics)
        self.assertIn('last_updated', metrics)
        
        self.assertEqual(metrics['total_conversions'], 10)
        self.assertEqual(metrics['total_revenue'], Decimal('250.00'))
        self.assertEqual(metrics['active_campaigns'], 1)
    
    def test_get_realtime_metrics_no_data(self):
        """Test realtime metrics retrieval with no data."""
        metrics = self.dashboard_service.get_realtime_metrics(self.advertiser)
        
        self.assertEqual(metrics['total_conversions'], 0)
        self.assertEqual(metrics['total_revenue'], Decimal('0.00'))
        self.assertEqual(metrics['active_campaigns'], 1)
    
    def test_get_campaign_performance_success(self):
        """Test successful campaign performance retrieval."""
        # Create conversions for campaign
        for i in range(5):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('30.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                campaign=self.campaign,
                created_at=timezone.now() - timezone.timedelta(minutes=i)
            )
        
        # Get campaign performance
        performance = self.dashboard_service.get_campaign_performance(
            self.advertiser,
            hours=24
        )
        
        self.assertIn('campaigns', performance)
        self.assertIn('total_campaigns', performance)
        self.assertIn('total_conversions', performance)
        self.assertIn('total_revenue', performance)
        
        self.assertEqual(len(performance['campaigns']), 1)
        self.assertEqual(performance['total_conversions'], 5)
        self.assertEqual(performance['total_revenue'], Decimal('150.00'))
    
    def test_get_conversion_trends_success(self):
        """Test successful conversion trends retrieval."""
        # Create conversions over time
        for i in range(24):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('10.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                campaign=self.campaign,
                created_at=timezone.now() - timezone.timedelta(hours=i)
            )
        
        # Get conversion trends
        trends = self.dashboard_service.get_conversion_trends(
            self.advertiser,
            hours=24
        )
        
        self.assertIn('hourly_data', trends)
        self.assertIn('trend_analysis', trends)
        self.assertIn('growth_rate', trends)
        self.assertIn('forecast', trends)
        
        # Check hourly data
        hourly_data = trends['hourly_data']
        self.assertEqual(len(hourly_data), 24)
    
    def test_get_geographic_distribution_success(self):
        """Test successful geographic distribution retrieval."""
        # Create conversions from different countries
        countries = ['US', 'CA', 'UK', 'DE']
        for i, country in enumerate(countries):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{country}',
                revenue=Decimal('20.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                custom_parameters={'country': country},
                created_at=timezone.now() - timezone.timedelta(hours=i)
            )
        
        # Get geographic distribution
        distribution = self.dashboard_service.get_geographic_distribution(
            self.advertiser,
            hours=24
        )
        
        self.assertIn('countries', distribution)
        self.assertIn('top_countries', distribution)
        self.assertIn('regional_breakdown', distribution)
        
        # Check countries
        countries_data = distribution['countries']
        self.assertEqual(len(countries_data), 4)
        self.assertIn('US', countries_data)
        self.assertIn('CA', countries_data)
    
    def test_get_device_breakdown_success(self):
        """Test successful device breakdown retrieval."""
        # Create conversions from different devices
        devices = ['desktop', 'mobile', 'tablet']
        for i, device in enumerate(devices):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{device}',
                revenue=Decimal('25.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                custom_parameters={'device_type': device},
                created_at=timezone.now() - timezone.timedelta(hours=i)
            )
        
        # Get device breakdown
        breakdown = self.dashboard_service.get_device_breakdown(
            self.advertiser,
            hours=24
        )
        
        self.assertIn('devices', breakdown)
        self.assertIn('device_percentages', breakdown)
        self.assertIn('mobile_vs_desktop', breakdown)
        
        # Check devices
        devices_data = breakdown['devices']
        self.assertEqual(len(devices_data), 3)
        self.assertIn('desktop', devices_data)
        self.assertIn('mobile', devices_data)
    
    def test_get_revenue_analytics_success(self):
        """Test successful revenue analytics retrieval."""
        # Create conversions with different revenue amounts
        for i in range(10):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal(str(10.00 + i * 5)),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                campaign=self.campaign,
                created_at=timezone.now() - timezone.timedelta(minutes=i)
            )
        
        # Get revenue analytics
        analytics = self.dashboard_service.get_revenue_analytics(
            self.advertiser,
            hours=24
        )
        
        self.assertIn('total_revenue', analytics)
        self.assertIn('average_revenue', analytics)
        self.assertIn('revenue_trend', analytics)
        self.assertIn('revenue_by_hour', analytics)
        
        self.assertEqual(analytics['total_revenue'], Decimal('325.00'))
        self.assertEqual(analytics['average_revenue'], Decimal('32.50'))
    
    def test_get_alert_summary_success(self):
        """Test successful alert summary retrieval."""
        # Get alert summary
        alerts = self.dashboard_service.get_alert_summary(self.advertiser)
        
        self.assertIn('total_alerts', alerts)
        self.assertIn('critical_alerts', alerts)
        self.assertIn('warning_alerts', alerts)
        self.assertIn('recent_alerts', alerts)
        
        # Should have no alerts initially
        self.assertEqual(alerts['total_alerts'], 0)
    
    def test_get_dashboard_summary_success(self):
        """Test successful dashboard summary retrieval."""
        # Create some conversions
        for i in range(5):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('20.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                campaign=self.campaign,
                created_at=timezone.now() - timezone.timedelta(minutes=i)
            )
        
        # Get dashboard summary
        summary = self.dashboard_service.get_dashboard_summary(self.advertiser)
        
        self.assertIn('overview', summary)
        self.assertIn('performance', summary)
        self.assertIn('trends', summary)
        self.assertIn('alerts', summary)
        
        # Check overview
        overview = summary['overview']
        self.assertIn('total_conversions', overview)
        self.assertIn('total_revenue', overview)
        self.assertIn('active_campaigns', overview)
        
        self.assertEqual(overview['total_conversions'], 5)
        self.assertEqual(overview['total_revenue'], Decimal('100.00'))
    
    def test_update_dashboard_cache_success(self):
        """Test successful dashboard cache update."""
        # Create conversions
        for i in range(3):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_{i}',
                revenue=Decimal('15.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                campaign=self.campaign,
                created_at=timezone.now() - timezone.timedelta(minutes=i)
            )
        
        # Update cache
        result = self.dashboard_service.update_dashboard_cache(self.advertiser)
        
        self.assertTrue(result.get('success', False))
        self.assertIn('cache_updated_at', result)
        
        # Get metrics from cache
        cached_metrics = self.dashboard_service.get_cached_metrics(self.advertiser)
        
        self.assertIsNotNone(cached_metrics)
        self.assertEqual(cached_metrics['total_conversions'], 3)
    
    def test_get_realtime_alerts_success(self):
        """Test successful realtime alerts retrieval."""
        # Get alerts
        alerts = self.dashboard_service.get_realtime_alerts(self.advertiser)
        
        self.assertIsInstance(alerts, list)
        # Should return empty list if no alerts
    
    def test_get_performance_comparison_success(self):
        """Test successful performance comparison retrieval."""
        # Create conversions for current and previous period
        # Current period
        for i in range(10):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_current_{i}',
                revenue=Decimal('25.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                campaign=self.campaign,
                created_at=timezone.now() - timezone.timedelta(hours=i)
            )
        
        # Previous period
        for i in range(8):
            Conversion.objects.create(
                advertiser=self.advertiser,
                conversion_id=f'conv_previous_{i}',
                revenue=Decimal('20.00'),
                ip_address='192.168.1.1',
                user_agent='Mozilla/5.0',
                campaign=self.campaign,
                created_at=timezone.now() - timezone.timedelta(days=7, hours=i)
            )
        
        # Get comparison
        comparison = self.dashboard_service.get_performance_comparison(
            self.advertiser,
            current_period_hours=24,
            previous_period_hours=24,
            previous_period_days_ago=7
        )
        
        self.assertIn('current_period', comparison)
        self.assertIn('previous_period', comparison)
        self.assertIn('growth_rates', comparison)
        self.assertIn('performance_change', comparison)
        
        # Check periods
        current = comparison['current_period']
        previous = comparison['previous_period']
        
        self.assertEqual(current['total_conversions'], 10)
        self.assertEqual(previous['total_conversions'], 8)


class ReportExportServiceTestCase(TestCase):
    """Test cases for ReportExportService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.advertiser_service = AdvertiserService()
        self.export_service = ReportExportService()
        
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
        
        # Create campaign
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
        
        # Create sample report data
        self.sample_report_data = {
            'summary': {
                'total_conversions': 10,
                'total_revenue': Decimal('250.00'),
                'average_revenue': Decimal('25.00'),
                'conversion_rate': 2.5
            },
            'campaign_performance': [
                {
                    'campaign_name': 'Test Campaign',
                    'conversions': 10,
                    'revenue': Decimal('250.00'),
                    'conversion_rate': 2.5
                }
            ],
            'daily_breakdown': [
                {
                    'date': '2023-01-01',
                    'conversions': 5,
                    'revenue': Decimal('125.00')
                },
                {
                    'date': '2023-01-02',
                    'conversions': 5,
                    'revenue': Decimal('125.00')
                }
            ]
        }
    
    def test_export_to_pdf_success(self):
        """Test successful PDF export."""
        with patch('api.advertiser_portal.services.reporting.ReportExportService.generate_pdf') as mock_generate_pdf:
            mock_generate_pdf.return_value = b'PDF content'
            
            result = self.export_service.export_to_pdf(
                self.advertiser,
                self.sample_report_data,
                'Performance Report'
            )
            
            self.assertTrue(result.get('success', False))
            self.assertIn('file_content', result)
            self.assertIn('file_name', result)
            self.assertEqual(result['file_type'], 'pdf')
            
            mock_generate_pdf.assert_called_once()
    
    def test_export_to_excel_success(self):
        """Test successful Excel export."""
        with patch('api.advertiser_portal.services.reporting.ReportExportService.generate_excel') as mock_generate_excel:
            mock_generate_excel.return_value = b'Excel content'
            
            result = self.export_service.export_to_excel(
                self.advertiser,
                self.sample_report_data,
                'Performance Report'
            )
            
            self.assertTrue(result.get('success', False))
            self.assertIn('file_content', result)
            self.assertIn('file_name', result)
            self.assertEqual(result['file_type'], 'xlsx')
            
            mock_generate_excel.assert_called_once()
    
    def test_export_to_csv_success(self):
        """Test successful CSV export."""
        with patch('api.advertiser_portal.services.reporting.ReportExportService.generate_csv') as mock_generate_csv:
            mock_generate_csv.return_value = b'CSV content'
            
            result = self.export_service.export_to_csv(
                self.advertiser,
                self.sample_report_data,
                'Performance Report'
            )
            
            self.assertTrue(result.get('success', False))
            self.assertIn('file_content', result)
            self.assertIn('file_name', result)
            self.assertEqual(result['file_type'], 'csv')
            
            mock_generate_csv.assert_called_once()
    
    def test_export_to_json_success(self):
        """Test successful JSON export."""
        result = self.export_service.export_to_json(
            self.advertiser,
            self.sample_report_data,
            'Performance Report'
        )
        
        self.assertTrue(result.get('success', False))
        self.assertIn('file_content', result)
        self.assertIn('file_name', result)
        self.assertEqual(result['file_type'], 'json')
        
        # Check that content is valid JSON
        import json
        content = result['file_content']
        parsed_data = json.loads(content)
        self.assertIn('summary', parsed_data)
        self.assertIn('campaign_performance', parsed_data)
    
    def test_export_with_invalid_format(self):
        """Test export with invalid format."""
        with self.assertRaises(ValueError) as context:
            self.export_service.export_report(
                self.advertiser,
                self.sample_report_data,
                'Performance Report',
                'invalid_format'
            )
        
        self.assertIn('Unsupported export format', str(context.exception))
    
    def test_export_with_empty_data(self):
        """Test export with empty data."""
        empty_data = {
            'summary': {
                'total_conversions': 0,
                'total_revenue': Decimal('0.00')
            }
        }
        
        result = self.export_service.export_to_json(
            self.advertiser,
            empty_data,
            'Empty Report'
        )
        
        self.assertTrue(result.get('success', False))
        self.assertIn('file_content', result)
    
    def test_get_export_history_success(self):
        """Test getting export history."""
        # Create some exports
        for i in range(3):
            self.export_service.export_to_json(
                self.advertiser,
                self.sample_report_data,
                f'Report {i}'
            )
        
        # Get history
        history = self.export_service.get_export_history(
            self.advertiser,
            days=7
        )
        
        self.assertEqual(len(history), 3)
        
        for export in history:
            self.assertIn('export_id', export)
            self.assertIn('file_name', export)
            self.assertIn('file_type', export)
            self.assertIn('exported_at', export)
    
    def test_validate_export_data_success(self):
        """Test successful export data validation."""
        is_valid, errors = self.export_service.validate_export_data(
            self.sample_report_data
        )
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_export_data_invalid(self):
        """Test export data validation with invalid data."""
        invalid_data = {
            'summary': {
                'total_conversions': 'invalid',  # Should be number
                'total_revenue': 'invalid'  # Should be Decimal
            }
        }
        
        is_valid, errors = self.export_service.validate_export_data(
            invalid_data
        )
        
        self.assertFalse(is_valid)
        self.assertIn('summary', errors)
    
    def test_get_supported_export_formats(self):
        """Test getting supported export formats."""
        formats = self.export_service.get_supported_export_formats()
        
        expected_formats = ['pdf', 'excel', 'csv', 'json']
        
        for format_type in expected_formats:
            self.assertIn(format_type, formats)
    
    def test_schedule_export_success(self):
        """Test successful export scheduling."""
        schedule_data = {
            'report_type': 'performance',
            'export_format': 'pdf',
            'frequency': 'weekly',
            'recipients': ['test@example.com'],
            'is_active': True,
        }
        
        schedule = self.export_service.schedule_export(
            self.advertiser,
            schedule_data
        )
        
        self.assertIn('schedule_id', schedule)
        self.assertEqual(schedule['report_type'], 'performance')
        self.assertEqual(schedule['export_format'], 'pdf')
        self.assertEqual(schedule['frequency'], 'weekly')
        self.assertTrue(schedule['is_active'])
    
    def test_get_export_schedules_success(self):
        """Test getting export schedules."""
        # Create multiple schedules
        for i in range(3):
            schedule_data = {
                'report_type': 'performance',
                'export_format': ['pdf', 'excel', 'csv'][i],
                'frequency': 'weekly',
                'recipients': ['test@example.com'],
                'is_active': True,
            }
            
            self.export_service.schedule_export(self.advertiser, schedule_data)
        
        # Get schedules
        schedules = self.export_service.get_export_schedules(self.advertiser)
        
        self.assertEqual(len(schedules), 3)
        
        # Check that all formats are present
        formats = [s['export_format'] for s in schedules]
        self.assertIn('pdf', formats)
        self.assertIn('excel', formats)
        self.assertIn('csv', formats)
    
    @patch('api.advertiser_portal.services.reporting.ReportExportService.send_notification')
    def test_send_export_notification(self, mock_send_notification):
        """Test sending export notification."""
        # Export report
        result = self.export_service.export_to_json(
            self.advertiser,
            self.sample_report_data,
            'Test Report'
        )
        
        # Send notification
        self.export_service.send_export_notification(
            self.advertiser,
            'export_completed',
            'Your report export has been completed',
            {
                'file_name': result['file_name'],
                'file_type': result['file_type']
            }
        )
        
        mock_send_notification.assert_called_once()
        
        # Check notification data
        call_args = mock_send_notification.call_args
        notification_data = call_args[0][1] if call_args else None
        
        if notification_data:
            self.assertEqual(notification_data['type'], 'export_completed')
            self.assertIn('report export has been completed', notification_data['message'])
