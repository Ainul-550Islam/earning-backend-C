"""
Analytics Management Services

This module contains service classes for managing analytics operations,
including reporting, dashboards, metrics, and data visualization.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from ..database_models.analytics_model import AnalyticsReport, AnalyticsMetric, AnalyticsDashboard, AnalyticsAlert, AnalyticsDataPoint
from ..database_models.campaign_model import Campaign
from ..database_models.creative_model import Creative
from ..database_models.impression_model import Impression, ImpressionAggregation
from ..database_models.click_model import Click, ClickAggregation
from ..database_models.conversion_model import Conversion, ConversionAggregation
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class AnalyticsService:
    """Service for managing analytics operations."""
    
    @staticmethod
    def get_campaign_analytics(campaign_id: UUID, date_range: Optional[Dict[str, str]] = None,
                               metrics: Optional[List[str]] = None,
                               dimensions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get campaign analytics data."""
        try:
            campaign = Campaign.objects.get(id=campaign_id, is_deleted=False)
            
            # Default date range if not provided
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timezone.timedelta(days=30)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            # Default metrics if not provided
            if not metrics:
                metrics = ['impressions', 'clicks', 'conversions', 'cost', 'revenue', 'ctr', 'cpc', 'cpa', 'conversion_rate', 'roas']
            
            # Default dimensions if not provided
            if not dimensions:
                dimensions = ['date']
            
            # Get aggregated data
            analytics_data = AnalyticsService._get_aggregated_data(
                campaign, start_date, end_date, metrics, dimensions
            )
            
            # Calculate derived metrics
            analytics_data = AnalyticsService._calculate_derived_metrics(analytics_data)
            
            return {
                'campaign': {
                    'id': str(campaign.id),
                    'name': campaign.name,
                    'advertiser': campaign.advertiser.company_name
                },
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'metrics': metrics,
                'dimensions': dimensions,
                'data': analytics_data
            }
            
        except Campaign.DoesNotExist:
            raise AnalyticsNotFoundError(f"Campaign {campaign_id} not found")
        except Exception as e:
            logger.error(f"Error getting campaign analytics {campaign_id}: {str(e)}")
            raise AnalyticsServiceError(f"Failed to get campaign analytics: {str(e)}")
    
    @staticmethod
    def get_creative_analytics(creative_id: UUID, date_range: Optional[Dict[str, str]] = None,
                               metrics: Optional[List[str]] = None,
                               dimensions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get creative analytics data."""
        try:
            creative = Creative.objects.get(id=creative_id, is_deleted=False)
            
            # Default date range if not provided
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timezone.timedelta(days=30)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            # Default metrics if not provided
            if not metrics:
                metrics = ['impressions', 'clicks', 'conversions', 'cost', 'revenue', 'ctr', 'cpc', 'cpa', 'conversion_rate', 'roas']
            
            # Default dimensions if not provided
            if not dimensions:
                dimensions = ['date']
            
            # Get aggregated data
            analytics_data = AnalyticsService._get_aggregated_creative_data(
                creative, start_date, end_date, metrics, dimensions
            )
            
            # Calculate derived metrics
            analytics_data = AnalyticsService._calculate_derived_metrics(analytics_data)
            
            return {
                'creative': {
                    'id': str(creative.id),
                    'name': creative.name,
                    'creative_type': creative.creative_type,
                    'campaign': creative.campaign.name
                },
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'metrics': metrics,
                'dimensions': dimensions,
                'data': analytics_data
            }
            
        except Creative.DoesNotExist:
            raise AnalyticsNotFoundError(f"Creative {creative_id} not found")
        except Exception as e:
            logger.error(f"Error getting creative analytics {creative_id}: {str(e)}")
            raise AnalyticsServiceError(f"Failed to get creative analytics: {str(e)}")
    
    @staticmethod
    def get_advertiser_analytics(advertiser_id: UUID, date_range: Optional[Dict[str, str]] = None,
                                  metrics: Optional[List[str]] = None,
                                  dimensions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get advertiser analytics data."""
        try:
            from ..database_models.advertiser_model import Advertiser
            advertiser = Advertiser.objects.get(id=advertiser_id, is_deleted=False)
            
            # Default date range if not provided
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timezone.timedelta(days=30)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            # Default metrics if not provided
            if not metrics:
                metrics = ['impressions', 'clicks', 'conversions', 'cost', 'revenue', 'ctr', 'cpc', 'cpa', 'conversion_rate', 'roas']
            
            # Default dimensions if not provided
            if not dimensions:
                dimensions = ['date']
            
            # Get all campaigns for advertiser
            campaigns = Campaign.objects.filter(advertiser=advertiser, is_deleted=False)
            
            # Aggregate data across all campaigns
            analytics_data = AnalyticsService._get_aggregated_advertiser_data(
                campaigns, start_date, end_date, metrics, dimensions
            )
            
            # Calculate derived metrics
            analytics_data = AnalyticsService._calculate_derived_metrics(analytics_data)
            
            return {
                'advertiser': {
                    'id': str(advertiser.id),
                    'company_name': advertiser.company_name
                },
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'metrics': metrics,
                'dimensions': dimensions,
                'data': analytics_data
            }
            
        except Advertiser.DoesNotExist:
            raise AnalyticsNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting advertiser analytics {advertiser_id}: {str(e)}")
            raise AnalyticsServiceError(f"Failed to get advertiser analytics: {str(e)}")
    
    @staticmethod
    def _get_aggregated_data(campaign: Campaign, start_date: date, end_date: date,
                              metrics: List[str], dimensions: List[str]) -> Dict[str, Any]:
        """Get aggregated data for campaign."""
        data = {}
        
        # Get impression data
        if 'impressions' in metrics:
            impression_data = ImpressionAggregation.objects.filter(
                campaign=campaign,
                date__gte=start_date,
                date__lte=end_date
            ).values(*dimensions).annotate(
                total_impressions=Sum('impressions'),
                total_cost=Sum('total_cost')
            )
            data['impressions'] = list(impression_data)
        
        # Get click data
        if 'clicks' in metrics:
            click_data = ClickAggregation.objects.filter(
                campaign=campaign,
                date__gte=start_date,
                date__lte=end_date
            ).values(*dimensions).annotate(
                total_clicks=Sum('clicks'),
                total_cost=Sum('total_cost')
            )
            data['clicks'] = list(click_data)
        
        # Get conversion data
        if 'conversions' in metrics:
            conversion_data = ConversionAggregation.objects.filter(
                campaign=campaign,
                date__gte=start_date,
                date__lte=end_date
            ).values(*dimensions).annotate(
                total_conversions=Sum('conversions'),
                total_revenue=Sum('total_revenue')
            )
            data['conversions'] = list(conversion_data)
        
        return data
    
    @staticmethod
    def _get_aggregated_creative_data(creative: Creative, start_date: date, end_date: date,
                                        metrics: List[str], dimensions: List[str]) -> Dict[str, Any]:
        """Get aggregated data for creative."""
        data = {}
        
        # Get impression data
        if 'impressions' in metrics:
            impression_data = ImpressionAggregation.objects.filter(
                creative=creative,
                date__gte=start_date,
                date__lte=end_date
            ).values(*dimensions).annotate(
                total_impressions=Sum('impressions'),
                total_cost=Sum('total_cost')
            )
            data['impressions'] = list(impression_data)
        
        # Get click data
        if 'clicks' in metrics:
            click_data = ClickAggregation.objects.filter(
                creative=creative,
                date__gte=start_date,
                date__lte=end_date
            ).values(*dimensions).annotate(
                total_clicks=Sum('clicks'),
                total_cost=Sum('total_cost')
            )
            data['clicks'] = list(click_data)
        
        # Get conversion data
        if 'conversions' in metrics:
            conversion_data = ConversionAggregation.objects.filter(
                creative=creative,
                date__gte=start_date,
                date__lte=end_date
            ).values(*dimensions).annotate(
                total_conversions=Sum('conversions'),
                total_revenue=Sum('total_revenue')
            )
            data['conversions'] = list(conversion_data)
        
        return data
    
    @staticmethod
    def _get_aggregated_advertiser_data(campaigns, start_date: date, end_date: date,
                                        metrics: List[str], dimensions: List[str]) -> Dict[str, Any]:
        """Get aggregated data for advertiser."""
        data = {}
        
        # Get impression data
        if 'impressions' in metrics:
            impression_data = ImpressionAggregation.objects.filter(
                campaign__in=campaigns,
                date__gte=start_date,
                date__lte=end_date
            ).values(*dimensions).annotate(
                total_impressions=Sum('impressions'),
                total_cost=Sum('total_cost')
            )
            data['impressions'] = list(impression_data)
        
        # Get click data
        if 'clicks' in metrics:
            click_data = ClickAggregation.objects.filter(
                campaign__in=campaigns,
                date__gte=start_date,
                date__lte=end_date
            ).values(*dimensions).annotate(
                total_clicks=Sum('clicks'),
                total_cost=Sum('total_cost')
            )
            data['clicks'] = list(click_data)
        
        # Get conversion data
        if 'conversions' in metrics:
            conversion_data = ConversionAggregation.objects.filter(
                campaign__in=campaigns,
                date__gte=start_date,
                date__lte=end_date
            ).values(*dimensions).annotate(
                total_conversions=Sum('conversions'),
                total_revenue=Sum('total_revenue')
            )
            data['conversions'] = list(conversion_data)
        
        return data
    
    @staticmethod
    def _calculate_derived_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate derived metrics from base metrics."""
        # This would implement actual derived metric calculations
        # For now, return data as-is
        return data
    
    @staticmethod
    def get_real_time_metrics(entity_type: str, entity_id: UUID) -> Dict[str, Any]:
        """Get real-time metrics for entity."""
        try:
            if entity_type == 'campaign':
                campaign = Campaign.objects.get(id=entity_id, is_deleted=False)
                return AnalyticsService._get_real_time_campaign_metrics(campaign)
            elif entity_type == 'creative':
                creative = Creative.objects.get(id=entity_id, is_deleted=False)
                return AnalyticsService._get_real_time_creative_metrics(creative)
            else:
                raise AnalyticsValidationError(f"Unsupported entity type: {entity_type}")
                
        except (Campaign.DoesNotExist, Creative.DoesNotExist):
            raise AnalyticsNotFoundError(f"Entity {entity_id} not found")
        except Exception as e:
            logger.error(f"Error getting real-time metrics {entity_type} {entity_id}: {str(e)}")
            raise AnalyticsServiceError(f"Failed to get real-time metrics: {str(e)}")
    
    @staticmethod
    def _get_real_time_campaign_metrics(campaign: Campaign) -> Dict[str, Any]:
        """Get real-time metrics for campaign."""
        # This would implement actual real-time metric calculation
        # For now, return mock data
        return {
            'current_impressions': 1000,
            'current_clicks': 50,
            'current_conversions': 5,
            'current_cost': 25.50,
            'current_ctr': 5.0,
            'current_cpc': 0.51,
            'current_cpa': 5.10,
            'current_conversion_rate': 10.0,
            'current_roas': 2.0,
            'timestamp': timezone.now().isoformat()
        }
    
    @staticmethod
    def _get_real_time_creative_metrics(creative: Creative) -> Dict[str, Any]:
        """Get real-time metrics for creative."""
        # This would implement actual real-time metric calculation
        # For now, return mock data
        return {
            'current_impressions': 500,
            'current_clicks': 25,
            'current_conversions': 2,
            'current_cost': 12.75,
            'current_ctr': 5.0,
            'current_cpc': 0.51,
            'current_cpa': 6.38,
            'current_conversion_rate': 8.0,
            'current_roas': 1.5,
            'timestamp': timezone.now().isoformat()
        }
    
    @staticmethod
    def calculate_attribution(conversion_id: UUID, attribution_model: str = 'last_click') -> Dict[str, Any]:
        """Calculate attribution for conversion."""
        try:
            conversion = Conversion.objects.get(id=conversion_id)
            
            # Get conversion path
            from ..database_models.conversion_model import ConversionPath
            paths = ConversionPath.objects.filter(conversion=conversion).order_by('timestamp')
            
            # Apply attribution model
            if attribution_model == 'last_click':
                attribution_data = AnalyticsService._apply_last_click_attribution(paths)
            elif attribution_model == 'first_click':
                attribution_data = AnalyticsService._apply_first_click_attribution(paths)
            elif attribution_model == 'linear':
                attribution_data = AnalyticsService._apply_linear_attribution(paths)
            elif attribution_model == 'time_decay':
                attribution_data = AnalyticsService._apply_time_decay_attribution(paths)
            else:
                raise AnalyticsValidationError(f"Unsupported attribution model: {attribution_model}")
            
            return {
                'conversion_id': str(conversion.id),
                'conversion_value': float(conversion.conversion_value),
                'attribution_model': attribution_model,
                'attribution_data': attribution_data
            }
            
        except Conversion.DoesNotExist:
            raise AnalyticsNotFoundError(f"Conversion {conversion_id} not found")
        except Exception as e:
            logger.error(f"Error calculating attribution {conversion_id}: {str(e)}")
            raise AnalyticsServiceError(f"Failed to calculate attribution: {str(e)}")
    
    @staticmethod
    def _apply_last_click_attribution(paths) -> Dict[str, Any]:
        """Apply last-click attribution model."""
        if not paths:
            return {}
        
        # Get last touchpoint
        last_touch = paths.last()
        
        return {
            'attributed_touchpoints': [
                {
                    'touchpoint_id': str(last_touch.touchpoint_id),
                    'touchpoint_type': last_touch.touchpoint_type,
                    'attribution_weight': 1.0,
                    'attributed_value': float(last_touch.conversion_value)
                }
            ]
        }
    
    @staticmethod
    def _apply_first_click_attribution(paths) -> Dict[str, Any]:
        """Apply first-click attribution model."""
        if not paths:
            return {}
        
        # Get first touchpoint
        first_touch = paths.first()
        
        return {
            'attributed_touchpoints': [
                {
                    'touchpoint_id': str(first_touch.touchpoint_id),
                    'touchpoint_type': first_touch.touchpoint_type,
                    'attribution_weight': 1.0,
                    'attributed_value': float(first_touch.conversion_value)
                }
            ]
        }
    
    @staticmethod
    def _apply_linear_attribution(paths) -> Dict[str, Any]:
        """Apply linear attribution model."""
        if not paths:
            return {}
        
        weight = 1.0 / len(paths)
        attributed_touchpoints = []
        
        for path in paths:
            attributed_touchpoints.append({
                'touchpoint_id': str(path.touchpoint_id),
                'touchpoint_type': path.touchpoint_type,
                'attribution_weight': weight,
                'attributed_value': float(path.conversion_value * weight)
            })
        
        return {
            'attributed_touchpoints': attributed_touchpoints
        }
    
    @staticmethod
    def _apply_time_decay_attribution(paths) -> Dict[str, Any]:
        """Apply time-decay attribution model."""
        if not paths:
            return {}
        
        # Calculate weights based on time decay
        total_weight = 0
        weighted_paths = []
        
        for path in paths:
            # Calculate time-based weight (simplified)
            days_since_touch = (timezone.now() - path.timestamp).days
            weight = 1.0 / (1 + days_since_touch * 0.1)
            
            weighted_paths.append({
                'touchpoint_id': str(path.touchpoint_id),
                'touchpoint_type': path.touchpoint_type,
                'weight': weight,
                'conversion_value': float(path.conversion_value)
            })
            total_weight += weight
        
        # Normalize weights
        attributed_touchpoints = []
        for path in weighted_paths:
            normalized_weight = path['weight'] / total_weight
            attributed_touchpoints.append({
                'touchpoint_id': path['touchpoint_id'],
                'touchpoint_type': path['touchpoint_type'],
                'attribution_weight': normalized_weight,
                'attributed_value': float(path['conversion_value'] * normalized_weight)
            })
        
        return {
            'attributed_touchpoints': attributed_touchpoints
        }


class ReportingService:
    """Service for managing reporting operations."""
    
    @staticmethod
    def create_report(data: Dict[str, Any], created_by: Optional[User] = None) -> AnalyticsReport:
        """Create a new analytics report."""
        try:
            with transaction.atomic():
                report = AnalyticsReport.objects.create(
                    advertiser=data.get('advertiser'),
                    campaign=data.get('campaign'),
                    report_name=data['name'],
                    report_type=data.get('report_type', 'custom'),
                    start_date=data.get('start_date'),
                    end_date=data.get('end_date'),
                    metrics=data.get('metrics', []),
                    dimensions=data.get('dimensions', []),
                    filters=data.get('filters', {}),
                    schedule_frequency=data.get('schedule_frequency'),
                    schedule_time=data.get('schedule_time'),
                    recipients=data.get('recipients', []),
                    delivery_method=data.get('delivery_method', 'email'),
                    output_format=data.get('output_format', 'pdf'),
                    template_id=data.get('template_id'),
                    is_scheduled=data.get('is_scheduled', False),
                    created_by=created_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=report.advertiser,
                    user=created_by,
                    title='Report Created',
                    message=f'Report "{report.name}" has been created successfully.',
                    notification_type='system',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    report,
                    created_by,
                    description=f"Created report: {report.name}"
                )
                
                return report
                
        except Exception as e:
            logger.error(f"Error creating report: {str(e)}")
            raise AnalyticsServiceError(f"Failed to create report: {str(e)}")
    
    @staticmethod
    def generate_report(report_id: UUID, generated_by: Optional[User] = None) -> bool:
        """Generate report data and file."""
        try:
            report = AnalyticsReport.objects.get(id=report_id)
            
            with transaction.atomic():
                # Update status
                report.status = 'generating'
                report.save(update_fields=['status'])
                
                # Generate report data
                report_data = ReportingService._generate_report_data(report)
                
                # Generate report file
                file_path = ReportingService._generate_report_file(report, report_data)
                
                # Update report
                report.status = 'completed'
                report.last_run = timezone.now()
                report.last_file = file_path
                report.save(update_fields=['status', 'last_run', 'last_file'])
                
                # Send report if scheduled
                if report.is_scheduled:
                    ReportingService._send_report(report, file_path)
                
                # Log generation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='generate',
                    object_type='AnalyticsReport',
                    object_id=str(report.id),
                    user=generated_by,
                    advertiser=report.advertiser,
                    description=f"Generated report: {report.name}"
                )
                
                return True
                
        except AnalyticsReport.DoesNotExist:
            raise AnalyticsNotFoundError(f"Report {report_id} not found")
        except Exception as e:
            logger.error(f"Error generating report {report_id}: {str(e)}")
            return False
    
    @staticmethod
    def _generate_report_data(report: AnalyticsReport) -> Dict[str, Any]:
        """Generate report data."""
        # Get analytics data based on report configuration
        if report.campaign:
            analytics_data = AnalyticsService.get_campaign_analytics(
                report.campaign.id,
                {'start_date': report.start_date.isoformat(), 'end_date': report.end_date.isoformat()},
                report.metrics,
                report.dimensions
            )
        else:
            analytics_data = AnalyticsService.get_advertiser_analytics(
                report.advertiser.id,
                {'start_date': report.start_date.isoformat(), 'end_date': report.end_date.isoformat()},
                report.metrics,
                report.dimensions
            )
        
        return analytics_data
    
    @staticmethod
    def _generate_report_file(report: AnalyticsReport, data: Dict[str, Any]) -> str:
        """Generate report file."""
        # This would implement actual file generation based on format
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{report.name}_{timestamp}.{report.output_format}"
        file_path = f"reports/{report.advertiser.id}/{filename}"
        
        return file_path
    
    @staticmethod
    def _send_report(report: AnalyticsReport, file_path: str) -> bool:
        """Send report via configured delivery method."""
        try:
            if report.delivery_method == 'email':
                return ReportingService._send_email_report(report, file_path)
            elif report.delivery_method == 'webhook':
                return ReportingService._send_webhook_report(report, file_path)
            elif report.delivery_method == 'ftp':
                return ReportingService._send_ftp_report(report, file_path)
            
            return True
        except Exception as e:
            logger.error(f"Error sending report {report.id}: {str(e)}")
            return False
    
    @staticmethod
    def _send_email_report(report: AnalyticsReport, file_path: str) -> bool:
        """Send report via email."""
        # This would implement actual email sending
        return True
    
    @staticmethod
    def _send_webhook_report(report: AnalyticsReport, file_path: str) -> bool:
        """Send report via webhook."""
        # This would implement actual webhook sending
        return True
    
    @staticmethod
    def _send_ftp_report(report: AnalyticsReport, file_path: str) -> bool:
        """Send report via FTP."""
        # This would implement actual FTP sending
        return True
    
    @staticmethod
    def get_report_history(report_id: UUID) -> List[Dict[str, Any]]:
        """Get report generation history."""
        try:
            report = AnalyticsReport.objects.get(id=report_id)
            
            # This would query report generation logs
            # For now, return empty list
            return []
            
        except AnalyticsReport.DoesNotExist:
            raise AnalyticsNotFoundError(f"Report {report_id} not found")
        except Exception as e:
            logger.error(f"Error getting report history {report_id}: {str(e)}")
            return []
    
    @staticmethod
    def schedule_report(report_id: UUID, schedule_data: Dict[str, Any],
                        scheduled_by: Optional[User] = None) -> bool:
        """Schedule report generation."""
        try:
            report = AnalyticsReport.objects.get(id=report_id)
            
            with transaction.atomic():
                # Update schedule settings
                report.is_scheduled = True
                report.schedule_frequency = schedule_data.get('frequency', 'daily')
                report.schedule_time = schedule_data.get('time')
                report.recipients = schedule_data.get('recipients', [])
                report.save(update_fields=['is_scheduled', 'schedule_frequency', 'schedule_time', 'recipients'])
                
                # Calculate next run time
                next_run = ReportingService._calculate_next_run(report)
                if next_run:
                    report.next_run = next_run
                    report.save(update_fields=['next_run'])
                
                # Log scheduling
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='schedule',
                    object_type='AnalyticsReport',
                    object_id=str(report.id),
                    user=scheduled_by,
                    advertiser=report.advertiser,
                    description=f"Scheduled report: {report.name}"
                )
                
                return True
                
        except AnalyticsReport.DoesNotExist:
            raise AnalyticsNotFoundError(f"Report {report_id} not found")
        except Exception as e:
            logger.error(f"Error scheduling report {report_id}: {str(e)}")
            return False
    
    @staticmethod
    def _calculate_next_run(report: AnalyticsReport) -> Optional[datetime]:
        """Calculate next run time for scheduled report."""
        if not report.is_scheduled:
            return None
        
        now = timezone.now()
        
        if report.schedule_frequency == 'daily':
            if report.schedule_time:
                next_run = now.replace(
                    hour=report.schedule_time.hour,
                    minute=report.schedule_time.minute,
                    second=0
                )
                if next_run <= now:
                    next_run += timezone.timedelta(days=1)
                return next_run
            else:
                return now + timezone.timedelta(days=1)
        
        elif report.schedule_frequency == 'weekly':
            return now + timezone.timedelta(days=7)
        
        elif report.schedule_frequency == 'monthly':
            return now + timezone.timedelta(days=30)
        
        return None


class DashboardService:
    """Service for managing dashboard operations."""
    
    @staticmethod
    def create_dashboard(data: Dict[str, Any], created_by: Optional[User] = None) -> AnalyticsDashboard:
        """Create a new analytics dashboard."""
        try:
            with transaction.atomic():
                dashboard = AnalyticsDashboard.objects.create(
                    advertiser=data.get('advertiser'),
                    name=data['name'],
                    description=data.get('description', ''),
                    layout_type=data.get('layout_type', 'grid'),
                    theme=data.get('theme', 'light'),
                    refresh_interval=data.get('refresh_interval', 300),
                    widgets=data.get('widgets', []),
                    layout_config=data.get('layout_config', {}),
                    default_filters=data.get('default_filters', {}),
                    available_filters=data.get('available_filters', []),
                    is_public=data.get('is_public', False),
                    shared_users=data.get('shared_users', []),
                    sharing_token=data.get('sharing_token'),
                    is_active=data.get('is_active', True),
                    is_default=data.get('is_default', False),
                    created_by=created_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=dashboard.advertiser,
                    user=created_by,
                    title='Dashboard Created',
                    message=f'Dashboard "{dashboard.name}" has been created successfully.',
                    notification_type='system',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    dashboard,
                    created_by,
                    description=f"Created dashboard: {dashboard.name}"
                )
                
                return dashboard
                
        except Exception as e:
            logger.error(f"Error creating dashboard: {str(e)}")
            raise AnalyticsServiceError(f"Failed to create dashboard: {str(e)}")
    
    @staticmethod
    def update_dashboard(dashboard_id: UUID, data: Dict[str, Any],
                         updated_by: Optional[User] = None) -> AnalyticsDashboard:
        """Update dashboard configuration."""
        try:
            dashboard = DashboardService.get_dashboard(dashboard_id)
            
            with transaction.atomic():
                # Track changes for audit log
                changed_fields = {}
                
                # Update fields
                for field in ['name', 'description', 'layout_type', 'theme', 'refresh_interval',
                             'widgets', 'layout_config', 'default_filters', 'available_filters',
                             'is_public', 'shared_users', 'is_active', 'is_default']:
                    if field in data:
                        old_value = getattr(dashboard, field)
                        new_value = data[field]
                        if old_value != new_value:
                            setattr(dashboard, field, new_value)
                            changed_fields[field] = {'old': old_value, 'new': new_value}
                
                dashboard.modified_by = updated_by
                dashboard.save()
                
                # Log changes
                if changed_fields:
                    from ..database_models.audit_model import AuditLog
                    AuditLog.log_update(
                        dashboard,
                        changed_fields,
                        updated_by,
                        description=f"Updated dashboard: {dashboard.name}"
                    )
                
                return dashboard
                
        except AnalyticsDashboard.DoesNotExist:
            raise AnalyticsNotFoundError(f"Dashboard {dashboard_id} not found")
        except Exception as e:
            logger.error(f"Error updating dashboard {dashboard_id}: {str(e)}")
            raise AnalyticsServiceError(f"Failed to update dashboard: {str(e)}")
    
    @staticmethod
    def get_dashboard(dashboard_id: UUID) -> AnalyticsDashboard:
        """Get dashboard by ID."""
        try:
            return AnalyticsDashboard.objects.get(id=dashboard_id)
        except AnalyticsDashboard.DoesNotExist:
            raise AnalyticsNotFoundError(f"Dashboard {dashboard_id} not found")
    
    @staticmethod
    def get_dashboard_data(dashboard_id: UUID, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get dashboard data with widgets populated."""
        try:
            dashboard = DashboardService.get_dashboard(dashboard_id)
            
            # Get dashboard configuration
            dashboard_config = dashboard.get_dashboard_config()
            
            # Populate widget data
            widget_data = DashboardService._populate_widget_data(dashboard, filters)
            
            return {
                'dashboard': dashboard_config,
                'widgets': widget_data,
                'filters': filters or {},
                'generated_at': timezone.now().isoformat()
            }
            
        except AnalyticsDashboard.DoesNotExist:
            raise AnalyticsNotFoundError(f"Dashboard {dashboard_id} not found")
        except Exception as e:
            logger.error(f"Error getting dashboard data {dashboard_id}: {str(e)}")
            raise AnalyticsServiceError(f"Failed to get dashboard data: {str(e)}")
    
    @staticmethod
    def _populate_widget_data(dashboard: AnalyticsDashboard, filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Populate data for all widgets in dashboard."""
        widget_data = []
        
        for widget_config in dashboard.widgets:
            widget_type = widget_config.get('type')
            widget_id = widget_config.get('id')
            
            if widget_type == 'metric':
                data = DashboardService._get_metric_widget_data(widget_config, filters)
            elif widget_type == 'chart':
                data = DashboardService._get_chart_widget_data(widget_config, filters)
            elif widget_type == 'table':
                data = DashboardService._get_table_widget_data(widget_config, filters)
            else:
                data = {}
            
            widget_data.append({
                'id': widget_id,
                'type': widget_type,
                'data': data
            })
        
        return widget_data
    
    @staticmethod
    def _get_metric_widget_data(widget_config: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Get data for metric widget."""
        # This would implement actual metric widget data calculation
        return {
            'value': 1000,
            'change': 10.5,
            'trend': 'up'
        }
    
    @staticmethod
    def _get_chart_widget_data(widget_config: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Get data for chart widget."""
        # This would implement actual chart widget data calculation
        return {
            'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
            'datasets': [
                {
                    'label': 'Impressions',
                    'data': [1000, 1200, 1100, 1300, 1400]
                }
            ]
        }
    
    @staticmethod
    def _get_table_widget_data(widget_config: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Get data for table widget."""
        # This would implement actual table widget data calculation
        return {
            'columns': ['Campaign', 'Impressions', 'Clicks', 'CTR'],
            'rows': [
                ['Campaign 1', 1000, 50, 5.0],
                ['Campaign 2', 2000, 100, 5.0]
            ]
        }
    
    @staticmethod
    def share_dashboard(dashboard_id: UUID, sharing_data: Dict[str, Any],
                        shared_by: Optional[User] = None) -> bool:
        """Share dashboard with other users."""
        try:
            dashboard = DashboardService.get_dashboard(dashboard_id)
            
            with transaction.atomic():
                # Update sharing settings
                dashboard.is_public = sharing_data.get('is_public', False)
                dashboard.shared_users = sharing_data.get('shared_users', [])
                
                if dashboard.is_public and not dashboard.sharing_token:
                    dashboard.sharing_token = DashboardService._generate_sharing_token()
                
                dashboard.save(update_fields=['is_public', 'shared_users', 'sharing_token'])
                
                # Log sharing
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='share',
                    object_type='AnalyticsDashboard',
                    object_id=str(dashboard.id),
                    user=shared_by,
                    advertiser=dashboard.advertiser,
                    description=f"Shared dashboard: {dashboard.name}"
                )
                
                return True
                
        except AnalyticsDashboard.DoesNotExist:
            raise AnalyticsNotFoundError(f"Dashboard {dashboard_id} not found")
        except Exception as e:
            logger.error(f"Error sharing dashboard {dashboard_id}: {str(e)}")
            return False
    
    @staticmethod
    def _generate_sharing_token() -> str:
        """Generate unique sharing token."""
        import secrets
        return f"dash_{secrets.token_urlsafe(32)}"


class MetricsService:
    """Service for managing metrics operations."""
    
    @staticmethod
    def calculate_metric(entity_type: str, entity_id: UUID, metric_name: str,
                         date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Calculate specific metric for entity."""
        try:
            if entity_type == 'campaign':
                campaign = Campaign.objects.get(id=entity_id, is_deleted=False)
                return MetricsService._calculate_campaign_metric(campaign, metric_name, date_range)
            elif entity_type == 'creative':
                creative = Creative.objects.get(id=entity_id, is_deleted=False)
                return MetricsService._calculate_creative_metric(creative, metric_name, date_range)
            else:
                raise AnalyticsValidationError(f"Unsupported entity type: {entity_type}")
                
        except (Campaign.DoesNotExist, Creative.DoesNotExist):
            raise AnalyticsNotFoundError(f"Entity {entity_id} not found")
        except Exception as e:
            logger.error(f"Error calculating metric {metric_name} for {entity_type} {entity_id}: {str(e)}")
            raise AnalyticsServiceError(f"Failed to calculate metric: {str(e)}")
    
    @staticmethod
    def _calculate_campaign_metric(campaign: Campaign, metric_name: str,
                                   date_range: Optional[Dict[str, str]]) -> Dict[str, Any]:
        """Calculate metric for campaign."""
        # Default date range if not provided
        if not date_range:
            end_date = timezone.now().date()
            start_date = end_date - timezone.timedelta(days=30)
        else:
            start_date = date.fromisoformat(date_range['start_date'])
            end_date = date.fromisoformat(date_range['end_date'])
        
        # Calculate specific metric
        if metric_name == 'ctr':
            return MetricsService._calculate_ctr(campaign, start_date, end_date)
        elif metric_name == 'cpc':
            return MetricsService._calculate_cpc(campaign, start_date, end_date)
        elif metric_name == 'cpa':
            return MetricsService._calculate_cpa(campaign, start_date, end_date)
        elif metric_name == 'conversion_rate':
            return MetricsService._calculate_conversion_rate(campaign, start_date, end_date)
        elif metric_name == 'roas':
            return MetricsService._calculate_roas(campaign, start_date, end_date)
        else:
            raise AnalyticsValidationError(f"Unsupported metric: {metric_name}")
    
    @staticmethod
    def _calculate_creative_metric(creative: Creative, metric_name: str,
                                   date_range: Optional[Dict[str, str]]) -> Dict[str, Any]:
        """Calculate metric for creative."""
        # Similar to campaign metric calculation but for creative
        return MetricsService._calculate_campaign_metric(creative.campaign, metric_name, date_range)
    
    @staticmethod
    def _calculate_ctr(campaign: Campaign, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate click-through rate."""
        impressions = ImpressionAggregation.objects.filter(
            campaign=campaign,
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum('impressions'))['total'] or 0
        
        clicks = ClickAggregation.objects.filter(
            campaign=campaign,
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum('clicks'))['total'] or 0
        
        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        
        return {
            'metric_name': 'ctr',
            'value': ctr,
            'impressions': impressions,
            'clicks': clicks,
            'date_range': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        }
    
    @staticmethod
    def _calculate_cpc(campaign: Campaign, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate cost per click."""
        clicks = ClickAggregation.objects.filter(
            campaign=campaign,
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum('clicks'))['total'] or 0
        
        cost = ClickAggregation.objects.filter(
            campaign=campaign,
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum('total_cost'))['total'] or 0
        
        cpc = (cost / clicks) if clicks > 0 else 0
        
        return {
            'metric_name': 'cpc',
            'value': float(cpc),
            'clicks': clicks,
            'cost': float(cost),
            'date_range': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        }
    
    @staticmethod
    def _calculate_cpa(campaign: Campaign, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate cost per acquisition."""
        conversions = ConversionAggregation.objects.filter(
            campaign=campaign,
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum('conversions'))['total'] or 0
        
        cost = ClickAggregation.objects.filter(
            campaign=campaign,
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum('total_cost'))['total'] or 0
        
        cpa = (cost / conversions) if conversions > 0 else 0
        
        return {
            'metric_name': 'cpa',
            'value': float(cpa),
            'conversions': conversions,
            'cost': float(cost),
            'date_range': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        }
    
    @staticmethod
    def _calculate_conversion_rate(campaign: Campaign, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate conversion rate."""
        clicks = ClickAggregation.objects.filter(
            campaign=campaign,
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum('clicks'))['total'] or 0
        
        conversions = ConversionAggregation.objects.filter(
            campaign=campaign,
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum('conversions'))['total'] or 0
        
        conversion_rate = (conversions / clicks * 100) if clicks > 0 else 0
        
        return {
            'metric_name': 'conversion_rate',
            'value': conversion_rate,
            'clicks': clicks,
            'conversions': conversions,
            'date_range': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        }
    
    @staticmethod
    def _calculate_roas(campaign: Campaign, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate return on ad spend."""
        cost = ClickAggregation.objects.filter(
            campaign=campaign,
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum('total_cost'))['total'] or 0
        
        revenue = ConversionAggregation.objects.filter(
            campaign=campaign,
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum('total_revenue'))['total'] or 0
        
        roas = (revenue / cost) if cost > 0 else 0
        
        return {
            'metric_name': 'roas',
            'value': float(roas),
            'cost': float(cost),
            'revenue': float(revenue),
            'date_range': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        }
    
    @staticmethod
    def get_metric_definitions() -> Dict[str, Any]:
        """Get definitions for all available metrics."""
        return {
            'ctr': {
                'name': 'Click-Through Rate',
                'description': 'Percentage of impressions that resulted in clicks',
                'formula': '(Clicks / Impressions) * 100',
                'unit': '%'
            },
            'cpc': {
                'name': 'Cost Per Click',
                'description': 'Average cost for each click',
                'formula': 'Total Cost / Clicks',
                'unit': 'currency'
            },
            'cpa': {
                'name': 'Cost Per Acquisition',
                'description': 'Average cost for each conversion',
                'formula': 'Total Cost / Conversions',
                'unit': 'currency'
            },
            'conversion_rate': {
                'name': 'Conversion Rate',
                'description': 'Percentage of clicks that resulted in conversions',
                'formula': '(Conversions / Clicks) * 100',
                'unit': '%'
            },
            'roas': {
                'name': 'Return on Ad Spend',
                'description': 'Revenue generated per dollar spent',
                'formula': 'Total Revenue / Total Cost',
                'unit': 'ratio'
            }
        }


class VisualizationService:
    """Service for managing data visualization operations."""
    
    @staticmethod
    def create_visualization(data: Dict[str, Any], created_by: Optional[User] = None) -> Dict[str, Any]:
        """Create a new data visualization."""
        try:
            # This would implement actual visualization creation
            # For now, return mock response
            return {
                'visualization_id': str(uuid.uuid4()),
                'name': data.get('name', 'Visualization'),
                'type': data.get('type', 'chart'),
                'status': 'created'
            }
            
        except Exception as e:
            logger.error(f"Error creating visualization: {str(e)}")
            raise AnalyticsServiceError(f"Failed to create visualization: {str(e)}")
    
    @staticmethod
    def generate_chart_data(data_config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate data for chart visualization."""
        try:
            # This would implement actual chart data generation
            # For now, return mock data
            return {
                'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
                'datasets': [
                    {
                        'label': 'Dataset 1',
                        'data': [10, 20, 30, 40, 50]
                    }
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating chart data: {str(e)}")
            raise AnalyticsServiceError(f"Failed to generate chart data: {str(e)}")
    
    @staticmethod
    def get_chart_types() -> List[Dict[str, Any]]:
        """Get available chart types."""
        return [
            {
                'type': 'line',
                'name': 'Line Chart',
                'description': 'Display data as points connected by straight lines',
                'suitable_for': ['time_series', 'trends']
            },
            {
                'type': 'bar',
                'name': 'Bar Chart',
                'description': 'Display data as rectangular bars',
                'suitable_for': ['comparisons', 'categories']
            },
            {
                'type': 'pie',
                'name': 'Pie Chart',
                'description': 'Display data as slices of a circle',
                'suitable_for': ['proportions', 'percentages']
            },
            {
                'type': 'area',
                'name': 'Area Chart',
                'description': 'Display data as filled area under line',
                'suitable_for': ['cumulative', 'volume']
            }
        ]
