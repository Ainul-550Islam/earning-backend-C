"""
Spend Rollup Tasks

Hourly spend aggregation for campaigns
and advertisers for reporting.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from django.core.cache import cache

from ..models.campaign import AdCampaign
from ..models.billing import AdvertiserWallet
from ..models.reporting import CampaignSpend, AdvertiserSpend
try:
    from ..services import AdvertiserBillingService
except ImportError:
    AdvertiserBillingService = None

import logging
logger = logging.getLogger(__name__)


@shared_task(name="advertiser_portal.rollup_campaign_spend")
def rollup_campaign_spend():
    """
    Roll up hourly spend data for all campaigns.
    
    This task runs every hour to aggregate spend data
    for campaigns and store in spend tables.
    """
    try:
        billing_service = AdvertiserBillingService()
        
        # Get current hour
        current_time = timezone.now()
        hour_start = current_time.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timezone.timedelta(hours=1)
        
        # Get all active campaigns
        active_campaigns = AdCampaign.objects.filter(
            status='active'
        ).select_related('advertiser')
        
        campaigns_processed = 0
        spend_records_created = 0
        
        for campaign in active_campaigns:
            try:
                # Get spend data for the hour
                spend_data = billing_service.get_campaign_spend_by_hour(
                    campaign,
                    hour_start,
                    hour_end
                )
                
                if spend_data and spend_data.get('total_spend', 0) > 0:
                    # Check if spend record already exists
                    existing_spend = CampaignSpend.objects.filter(
                        campaign=campaign,
                        hour=hour_start
                    ).first()
                    
                    if existing_spend:
                        # Update existing record
                        existing_spend.impressions = spend_data.get('impressions', 0)
                        existing_spend.clicks = spend_data.get('clicks', 0)
                        existing_spend.conversions = spend_data.get('conversions', 0)
                        existing_spend.spend_amount = spend_data.get('total_spend', 0)
                        existing_spend.ctr = spend_data.get('ctr', 0)
                        existing_spend.cpc = spend_data.get('cpc', 0)
                        existing_spend.cpa = spend_data.get('cpa', 0)
                        existing_spend.updated_at = timezone.now()
                        existing_spend.save()
                    else:
                        # Create new spend record
                        CampaignSpend.objects.create(
                            campaign=campaign,
                            advertiser=campaign.advertiser,
                            hour=hour_start,
                            impressions=spend_data.get('impressions', 0),
                            clicks=spend_data.get('clicks', 0),
                            conversions=spend_data.get('conversions', 0),
                            spend_amount=spend_data.get('total_spend', 0),
                            ctr=spend_data.get('ctr', 0),
                            cpc=spend_data.get('cpc', 0),
                            cpa=spend_data.get('cpa', 0),
                            created_at=timezone.now()
                        )
                        spend_records_created += 1
                    
                    campaigns_processed += 1
                    logger.info(f"Spend rolled up for campaign {campaign.id}: ${spend_data.get('total_spend', 0):.2f}")
                
            except Exception as e:
                logger.error(f"Error rolling up spend for campaign {campaign.id}: {e}")
                continue
        
        logger.info(f"Campaign spend rollup completed: {campaigns_processed} campaigns processed, {spend_records_created} records created")
        
        return {
            'hour': hour_start.strftime('%Y-%m-%d %H:00'),
            'campaigns_processed': campaigns_processed,
            'spend_records_created': spend_records_created,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in campaign spend rollup task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.rollup_advertiser_spend")
def rollup_advertiser_spend():
    """
    Roll up hourly spend data for all advertisers.
    
    This task runs every hour to aggregate spend data
    for advertisers and store in spend tables.
    """
    try:
        billing_service = AdvertiserBillingService()
        
        # Get current hour
        current_time = timezone.now()
        hour_start = current_time.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timezone.timedelta(hours=1)
        
        # Get all active advertisers
        from ..models.advertiser import Advertiser
        active_advertisers = Advertiser.objects.filter(
            status='active'
        )
        
        advertisers_processed = 0
        spend_records_created = 0
        
        for advertiser in active_advertisers:
            try:
                # Get spend data for the hour
                spend_data = billing_service.get_advertiser_spend_by_hour(
                    advertiser,
                    hour_start,
                    hour_end
                )
                
                if spend_data and spend_data.get('total_spend', 0) > 0:
                    # Check if spend record already exists
                    existing_spend = AdvertiserSpend.objects.filter(
                        advertiser=advertiser,
                        hour=hour_start
                    ).first()
                    
                    if existing_spend:
                        # Update existing record
                        existing_spend.impressions = spend_data.get('impressions', 0)
                        existing_spend.clicks = spend_data.get('clicks', 0)
                        existing_spend.conversions = spend_data.get('conversions', 0)
                        existing_spend.spend_amount = spend_data.get('total_spend', 0)
                        existing_spend.ctr = spend_data.get('ctr', 0)
                        existing_spend.cpc = spend_data.get('cpc', 0)
                        existing_spend.cpa = spend_data.get('cpa', 0)
                        existing_spend.updated_at = timezone.now()
                        existing_spend.save()
                    else:
                        # Create new spend record
                        AdvertiserSpend.objects.create(
                            advertiser=advertiser,
                            hour=hour_start,
                            impressions=spend_data.get('impressions', 0),
                            clicks=spend_data.get('clicks', 0),
                            conversions=spend_data.get('conversions', 0),
                            spend_amount=spend_data.get('total_spend', 0),
                            ctr=spend_data.get('ctr', 0),
                            cpc=spend_data.get('cpc', 0),
                            cpa=spend_data.get('cpa', 0),
                            created_at=timezone.now()
                        )
                        spend_records_created += 1
                    
                    advertisers_processed += 1
                    logger.info(f"Spend rolled up for advertiser {advertiser.id}: ${spend_data.get('total_spend', 0):.2f}")
                
            except Exception as e:
                logger.error(f"Error rolling up spend for advertiser {advertiser.id}: {e}")
                continue
        
        logger.info(f"Advertiser spend rollup completed: {advertisers_processed} advertisers processed, {spend_records_created} records created")
        
        return {
            'hour': hour_start.strftime('%Y-%m-%d %H:00'),
            'advertisers_processed': advertisers_processed,
            'spend_records_created': spend_records_created,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in advertiser spend rollup task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.aggregate_daily_spend")
def aggregate_daily_spend():
    """
    Aggregate hourly spend data into daily totals.
    
    This task runs daily at midnight to aggregate
    hourly spend data into daily summaries.
    """
    try:
        # Get yesterday's date
        yesterday = timezone.now().date() - timezone.timedelta(days=1)
        
        # Aggregate campaign spend
        campaign_spend_records = CampaignSpend.objects.filter(
            hour__date=yesterday
        ).values('campaign', 'campaign__advertiser').annotate(
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            total_spend=Sum('spend_amount'),
            avg_ctr=Avg('ctr'),
            avg_cpc=Avg('cpc'),
            avg_cpa=Avg('cpa')
        )
        
        campaign_daily_records = 0
        
        for record in campaign_spend_records:
            try:
                # Create daily spend record
                from ..models.reporting import CampaignDailySpend
                CampaignDailySpend.objects.update_or_create(
                    campaign_id=record['campaign'],
                    date=yesterday,
                    defaults={
                        'advertiser_id': record['campaign__advertiser'],
                        'impressions': record['total_impressions'] or 0,
                        'clicks': record['total_clicks'] or 0,
                        'conversions': record['total_conversions'] or 0,
                        'spend_amount': record['total_spend'] or 0,
                        'ctr': record['avg_ctr'] or 0,
                        'cpc': record['avg_cpc'] or 0,
                        'cpa': record['avg_cpa'] or 0,
                        'created_at': timezone.now()
                    }
                )
                campaign_daily_records += 1
                
            except Exception as e:
                logger.error(f"Error creating daily campaign spend record: {e}")
                continue
        
        # Aggregate advertiser spend
        advertiser_spend_records = AdvertiserSpend.objects.filter(
            hour__date=yesterday
        ).values('advertiser').annotate(
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            total_spend=Sum('spend_amount'),
            avg_ctr=Avg('ctr'),
            avg_cpc=Avg('cpc'),
            avg_cpa=Avg('cpa')
        )
        
        advertiser_daily_records = 0
        
        for record in advertiser_spend_records:
            try:
                # Create daily spend record
                from ..models.reporting import AdvertiserDailySpend
                AdvertiserDailySpend.objects.update_or_create(
                    advertiser_id=record['advertiser'],
                    date=yesterday,
                    defaults={
                        'impressions': record['total_impressions'] or 0,
                        'clicks': record['total_clicks'] or 0,
                        'conversions': record['total_conversions'] or 0,
                        'spend_amount': record['total_spend'] or 0,
                        'ctr': record['avg_ctr'] or 0,
                        'cpc': record['avg_cpc'] or 0,
                        'cpa': record['avg_cpa'] or 0,
                        'created_at': timezone.now()
                    }
                )
                advertiser_daily_records += 1
                
            except Exception as e:
                logger.error(f"Error creating daily advertiser spend record: {e}")
                continue
        
        logger.info(f"Daily spend aggregation completed: {campaign_daily_records} campaign records, {advertiser_daily_records} advertiser records")
        
        return {
            'date': yesterday.isoformat(),
            'campaign_daily_records': campaign_daily_records,
            'advertiser_daily_records': advertiser_daily_records,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in daily spend aggregation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.update_spend_cache")
def update_spend_cache():
    """
    Update spend cache for real-time reporting.
    
    This task runs every 15 minutes to update
    cached spend data for fast reporting.
    """
    try:
        # Get current time
        current_time = timezone.now()
        
        # Update today's spend cache
        today = current_time.date()
        
        # Get campaign spend for today
        campaign_spend = CampaignSpend.objects.filter(
            hour__date=today
        ).values('campaign').annotate(
            total_spend=Sum('spend_amount'),
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions')
        )
        
        campaign_cache_data = {}
        for record in campaign_spend:
            campaign_cache_data[record['campaign']] = {
                'spend': float(record['total_spend'] or 0),
                'impressions': record['total_impressions'] or 0,
                'clicks': record['total_clicks'] or 0,
                'conversions': record['total_conversions'] or 0,
            }
        
        # Cache campaign spend data
        cache_key = f"campaign_spend_{today.strftime('%Y%m%d')}"
        cache.set(cache_key, campaign_cache_data, timeout=86400)  # Cache for 24 hours
        
        # Get advertiser spend for today
        advertiser_spend = AdvertiserSpend.objects.filter(
            hour__date=today
        ).values('advertiser').annotate(
            total_spend=Sum('spend_amount'),
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions')
        )
        
        advertiser_cache_data = {}
        for record in advertiser_spend:
            advertiser_cache_data[record['advertiser']] = {
                'spend': float(record['total_spend'] or 0),
                'impressions': record['total_impressions'] or 0,
                'clicks': record['total_clicks'] or 0,
                'conversions': record['total_conversions'] or 0,
            }
        
        # Cache advertiser spend data
        cache_key = f"advertiser_spend_{today.strftime('%Y%m%d')}"
        cache.set(cache_key, advertiser_cache_data, timeout=86400)  # Cache for 24 hours
        
        logger.info(f"Spend cache updated for {today}: {len(campaign_cache_data)} campaigns, {len(advertiser_cache_data)} advertisers")
        
        return {
            'date': today.isoformat(),
            'campaigns_cached': len(campaign_cache_data),
            'advertisers_cached': len(advertiser_cache_data),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in spend cache update task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.cleanup_spend_data")
def cleanup_spend_data():
    """
    Clean up old spend data to maintain performance.
    
    This task runs weekly to clean up hourly spend
    data older than 90 days.
    """
    try:
        # Clean up hourly spend data older than 90 days
        cutoff_date = timezone.now() - timezone.timedelta(days=90)
        
        # Clean up campaign spend
        campaign_spend_deleted = CampaignSpend.objects.filter(
            hour__lt=cutoff_date
        ).delete()[0]
        
        # Clean up advertiser spend
        advertiser_spend_deleted = AdvertiserSpend.objects.filter(
            hour__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Spend data cleanup completed: {campaign_spend_deleted} campaign records, {advertiser_spend_deleted} advertiser records deleted")
        
        return {
            'cutoff_date': cutoff_date.date().isoformat(),
            'campaign_spend_deleted': campaign_spend_deleted,
            'advertiser_spend_deleted': advertiser_spend_deleted,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in spend data cleanup task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task(name="advertiser_portal.generate_spend_reports")
def generate_spend_reports():
    """
    Generate spend reports for analysis.
    
    This task runs daily to generate spend reports
    for administrators and advertisers.
    """
    try:
        # Get yesterday's date
        yesterday = timezone.now().date() - timezone.timedelta(days=1)
        
        # Generate system spend summary
        from ..models.reporting import CampaignDailySpend, AdvertiserDailySpend
        
        campaign_spend = CampaignDailySpend.objects.filter(date=yesterday).aggregate(
            total_spend=Sum('spend_amount'),
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            campaign_count=Count('campaign', distinct=True)
        )
        
        advertiser_spend = AdvertiserDailySpend.objects.filter(date=yesterday).aggregate(
            total_spend=Sum('spend_amount'),
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            advertiser_count=Count('advertiser', distinct=True)
        )
        
        # Generate report data
        report_data = {
            'date': yesterday.isoformat(),
            'campaign_metrics': {
                'total_spend': float(campaign_spend['total_spend'] or 0),
                'total_impressions': campaign_spend['total_impressions'] or 0,
                'total_clicks': campaign_spend['total_clicks'] or 0,
                'total_conversions': campaign_spend['total_conversions'] or 0,
                'campaign_count': campaign_spend['campaign_count'] or 0,
                'avg_cpc': float((campaign_spend['total_spend'] or 0) / (campaign_spend['total_clicks'] or 1)),
                'avg_cpa': float((campaign_spend['total_spend'] or 0) / (campaign_spend['total_conversions'] or 1)),
            },
            'advertiser_metrics': {
                'total_spend': float(advertiser_spend['total_spend'] or 0),
                'total_impressions': advertiser_spend['total_impressions'] or 0,
                'total_clicks': advertiser_spend['total_clicks'] or 0,
                'total_conversions': advertiser_spend['total_conversions'] or 0,
                'advertiser_count': advertiser_spend['advertiser_count'] or 0,
                'avg_spend_per_advertiser': float((advertiser_spend['total_spend'] or 0) / (advertiser_spend['advertiser_count'] or 1)),
            },
            'generated_at': timezone.now().isoformat(),
        }
        
        # Store report
        from ..models.reporting import SpendReport
        report = SpendReport.objects.create(
            report_date=yesterday,
            data=report_data,
            generated_at=timezone.now()
        )
        
        logger.info(f"Spend report generated for {yesterday}: ${report_data['campaign_metrics']['total_spend']:.2f}")
        
        return report_data
        
    except Exception as e:
        logger.error(f"Error in spend report generation task: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }
