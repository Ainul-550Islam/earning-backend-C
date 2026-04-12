"""
Advertiser Analytics Management

This module handles comprehensive analytics, reporting, and data analysis
for advertisers including custom reports, dashboards, and insights.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.analytics_model import AnalyticsReport, AnalyticsDashboard, AnalyticsWidget
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class AdvertiserAnalyticsService:
    """Service for managing advertiser analytics operations."""
    
    @staticmethod
    def create_custom_report(advertiser_id: UUID, report_data: Dict[str, Any],
                             created_by: Optional[User] = None) -> AnalyticsReport:
        """Create custom analytics report."""
        try:
            advertiser = AdvertiserAnalyticsService.get_advertiser(advertiser_id)
            
            # Validate report data
            report_name = report_data.get('name')
            if not report_name:
                raise AdvertiserValidationError("name is required")
            
            report_type = report_data.get('report_type', 'custom')
            if report_type not in ['custom', 'campaign', 'creative', 'targeting', 'billing']:
                raise AdvertiserValidationError("Invalid report_type")
            
            with transaction.atomic():
                # Create analytics report
                analytics_report = AnalyticsReport.objects.create(
                    advertiser=advertiser,
                    name=report_name,
                    description=report_data.get('description', ''),
                    report_type=report_type,
                    configuration=report_data.get('configuration', {}),
                    filters=report_data.get('filters', {}),
                    metrics=report_data.get('metrics', []),
                    dimensions=report_data.get('dimensions', []),
                    date_range=report_data.get('date_range'),
                    schedule=report_data.get('schedule', {}),
                    is_public=report_data.get('is_public', False),
                    created_by=created_by
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=created_by,
                    title='Analytics Report Created',
                    message=f'Your custom report "{report_name}" has been created successfully.',
                    notification_type='analytics',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    analytics_report,
                    created_by,
                    description=f"Created analytics report: {report_name}"
                )
                
                return analytics_report
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error creating custom report {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create custom report: {str(e)}")
    
    @staticmethod
    def generate_report_data(report_id: UUID, generation_data: Dict[str, Any],
                              generated_by: Optional[User] = None) -> Dict[str, Any]:
        """Generate data for analytics report."""
        try:
            analytics_report = AdvertiserAnalyticsService.get_analytics_report(report_id)
            
            # Validate generation data
            date_range = generation_data.get('date_range')
            if not date_range:
                # Use default date range from report
                date_range = analytics_report.date_range or {
                    'start_date': (timezone.now().date() - timedelta(days=30)).isoformat(),
                    'end_date': timezone.now().date().isoformat()
                }
            
            start_date = date.fromisoformat(date_range['start_date'])
            end_date = date.fromisoformat(date_range['end_date'])
            
            # Generate report data based on type
            if analytics_report.report_type == 'campaign':
                report_data = AdvertiserAnalyticsService._generate_campaign_report(
                    analytics_report.advertiser, start_date, end_date, analytics_report
                )
            elif analytics_report.report_type == 'creative':
                report_data = AdvertiserAnalyticsService._generate_creative_report(
                    analytics_report.advertiser, start_date, end_date, analytics_report
                )
            elif analytics_report.report_type == 'targeting':
                report_data = AdvertiserAnalyticsService._generate_targeting_report(
                    analytics_report.advertiser, start_date, end_date, analytics_report
                )
            elif analytics_report.report_type == 'billing':
                report_data = AdvertiserAnalyticsService._generate_billing_report(
                    analytics_report.advertiser, start_date, end_date, analytics_report
                )
            else:
                report_data = AdvertiserAnalyticsService._generate_custom_report(
                    analytics_report.advertiser, start_date, end_date, analytics_report
                )
            
            # Update report with generated data
            analytics_report.last_generated_at = timezone.now()
            analytics_report.save(update_fields=['last_generated_at'])
            
            return {
                'report_id': str(report_id),
                'report_name': analytics_report.name,
                'report_type': analytics_report.report_type,
                'date_range': date_range,
                'generated_at': timezone.now().isoformat(),
                'data': report_data
            }
            
        except AnalyticsReport.DoesNotExist:
            raise AdvertiserNotFoundError(f"Analytics report {report_id} not found")
        except Exception as e:
            logger.error(f"Error generating report data {report_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to generate report data: {str(e)}")
    
    @staticmethod
    def create_dashboard(advertiser_id: UUID, dashboard_data: Dict[str, Any],
                         created_by: Optional[User] = None) -> AnalyticsDashboard:
        """Create analytics dashboard."""
        try:
            advertiser = AdvertiserAnalyticsService.get_advertiser(advertiser_id)
            
            # Validate dashboard data
            dashboard_name = dashboard_data.get('name')
            if not dashboard_name:
                raise AdvertiserValidationError("name is required")
            
            with transaction.atomic():
                # Create analytics dashboard
                analytics_dashboard = AnalyticsDashboard.objects.create(
                    advertiser=advertiser,
                    name=dashboard_name,
                    description=dashboard_data.get('description', ''),
                    layout=dashboard_data.get('layout', 'grid'),
                    theme=dashboard_data.get('theme', 'default'),
                    is_default=dashboard_data.get('is_default', False),
                    is_public=dashboard_data.get('is_public', False),
                    configuration=dashboard_data.get('configuration', {}),
                    created_by=created_by
                )
                
                # Add widgets if provided
                widgets = dashboard_data.get('widgets', [])
                for widget_data in widgets:
                    AdvertiserAnalyticsService._add_widget_to_dashboard(analytics_dashboard, widget_data, created_by)
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=created_by,
                    title='Analytics Dashboard Created',
                    message=f'Your dashboard "{dashboard_name}" has been created successfully.',
                    notification_type='analytics',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    analytics_dashboard,
                    created_by,
                    description=f"Created analytics dashboard: {dashboard_name}"
                )
                
                return analytics_dashboard
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error creating dashboard {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create dashboard: {str(e)}")
    
    @staticmethod
    def get_dashboard_data(dashboard_id: UUID, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get dashboard data with all widgets."""
        try:
            analytics_dashboard = AdvertiserAnalyticsService.get_analytics_dashboard(dashboard_id)
            
            # Get dashboard widgets
            widgets = AnalyticsWidget.objects.filter(
                dashboard=analytics_dashboard
            ).order_by('position')
            
            # Generate data for each widget
            widget_data = []
            for widget in widgets:
                try:
                    widget_info = AdvertiserAnalyticsService._generate_widget_data(widget, filters)
                    widget_data.append(widget_info)
                except Exception as e:
                    logger.error(f"Error generating widget data {widget.id}: {str(e)}")
                    widget_data.append({
                        'id': str(widget.id),
                        'widget_type': widget.widget_type,
                        'title': widget.title,
                        'error': str(e)
                    })
            
            return {
                'dashboard_id': str(dashboard_id),
                'dashboard_name': analytics_dashboard.name,
                'layout': analytics_dashboard.layout,
                'theme': analytics_dashboard.theme,
                'widgets': widget_data,
                'generated_at': timezone.now().isoformat()
            }
            
        except AnalyticsDashboard.DoesNotExist:
            raise AdvertiserNotFoundError(f"Analytics dashboard {dashboard_id} not found")
        except Exception as e:
            logger.error(f"Error getting dashboard data {dashboard_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get dashboard data: {str(e)}")
    
    @staticmethod
    def get_analytics_summary(advertiser_id: UUID, date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get comprehensive analytics summary."""
        try:
            advertiser = AdvertiserAnalyticsService.get_advertiser(advertiser_id)
            
            # Default date range (last 30 days)
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=30)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            # Get campaign analytics
            campaign_analytics = AdvertiserAnalyticsService._get_campaign_analytics(advertiser, start_date, end_date)
            
            # Get creative analytics
            creative_analytics = AdvertiserAnalyticsService._get_creative_analytics(advertiser, start_date, end_date)
            
            # Get targeting analytics
            targeting_analytics = AdvertiserAnalyticsService._get_targeting_analytics(advertiser, start_date, end_date)
            
            # Get billing analytics
            billing_analytics = AdvertiserAnalyticsService._get_billing_analytics(advertiser, start_date, end_date)
            
            # Calculate overall metrics
            overall_metrics = AdvertiserAnalyticsService._calculate_overall_metrics(
                campaign_analytics, creative_analytics, targeting_analytics, billing_analytics
            )
            
            return {
                'advertiser_id': str(advertiser_id),
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'campaign_analytics': campaign_analytics,
                'creative_analytics': creative_analytics,
                'targeting_analytics': targeting_analytics,
                'billing_analytics': billing_analytics,
                'overall_metrics': overall_metrics,
                'generated_at': timezone.now().isoformat()
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting analytics summary {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get analytics summary: {str(e)}")
    
    @staticmethod
    def get_real_time_metrics(advertiser_id: UUID) -> Dict[str, Any]:
        """Get real-time metrics for advertiser."""
        try:
            advertiser = AdvertiserAnalyticsService.get_advertiser(advertiser_id)
            
            # Get today's data
            today = timezone.now().date()
            
            # Campaign real-time data
            campaigns = Campaign.objects.filter(
                advertiser=advertiser,
                status='active',
                is_deleted=False
            )
            
            # Calculate real-time metrics
            total_active_campaigns = campaigns.count()
            total_impressions_today = campaigns.aggregate(
                total=Sum('total_impressions')
            )['total'] or 0
            
            total_clicks_today = campaigns.aggregate(
                total=Sum('total_clicks')
            )['total'] or 0
            
            total_conversions_today = campaigns.aggregate(
                total=Sum('total_conversions')
            )['total'] or 0
            
            total_spend_today = campaigns.aggregate(
                total=Sum('current_spend')
            )['total'] or Decimal('0.00')
            
            # Calculate derived metrics
            ctr_today = (total_clicks_today / total_impressions_today * 100) if total_impressions_today > 0 else 0
            cpc_today = (total_spend_today / total_clicks_today) if total_clicks_today > 0 else 0
            cpa_today = (total_spend_today / total_conversions_today) if total_conversions_today > 0 else 0
            
            # Get hourly breakdown for today
            hourly_data = []
            current_hour = timezone.now().hour
            
            for hour in range(24):
                # Mock hourly data - would come from real-time tracking system
                hourly_impressions = total_impressions_today // 24 if total_impressions_today > 0 else 0
                hourly_clicks = total_clicks_today // 24 if total_clicks_today > 0 else 0
                
                hourly_data.append({
                    'hour': hour,
                    'impressions': hourly_impressions,
                    'clicks': hourly_clicks,
                    'conversions': hourly_conversions_today // 24 if total_conversions_today > 0 else 0,
                    'spend': float(total_spend_today / 24) if total_spend_today > 0 else 0,
                    'is_current_hour': hour == current_hour
                })
            
            return {
                'advertiser_id': str(advertiser_id),
                'date': today.isoformat(),
                'real_time_metrics': {
                    'active_campaigns': total_active_campaigns,
                    'impressions_today': total_impressions_today,
                    'clicks_today': total_clicks_today,
                    'conversions_today': total_conversions_today,
                    'spend_today': float(total_spend_today),
                    'ctr_today': ctr_today,
                    'cpc_today': float(cpc_today),
                    'cpa_today': float(cpa_today)
                },
                'hourly_breakdown': hourly_data,
                'top_performing_campaigns': AdvertiserAnalyticsService._get_top_campaigns(advertiser, 5),
                'generated_at': timezone.now().isoformat()
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting real-time metrics {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get real-time metrics: {str(e)}")
    
    @staticmethod
    def export_analytics_data(advertiser_id: UUID, export_config: Dict[str, Any],
                              exported_by: Optional[User] = None) -> Dict[str, Any]:
        """Export analytics data in various formats."""
        try:
            advertiser = AdvertiserAnalyticsService.get_advertiser(advertiser_id)
            
            # Validate export configuration
            export_format = export_config.get('format', 'json')
            if export_format not in ['json', 'csv', 'excel', 'pdf']:
                raise AdvertiserValidationError("Invalid format. Use 'json', 'csv', 'excel', or 'pdf'")
            
            data_type = export_config.get('data_type', 'summary')
            if data_type not in ['summary', 'campaign', 'creative', 'targeting', 'billing']:
                raise AdvertiserValidationError("Invalid data_type")
            
            date_range = export_config.get('date_range')
            if not date_range:
                date_range = {
                    'start_date': (timezone.now().date() - timedelta(days=30)).isoformat(),
                    'end_date': timezone.now().date().isoformat()
                }
            
            # Get data based on type
            if data_type == 'summary':
                data = AdvertiserAnalyticsService.get_analytics_summary(advertiser_id, date_range)
            elif data_type == 'campaign':
                data = AdvertiserAnalyticsService._get_campaign_analytics(
                    advertiser,
                    date.fromisoformat(date_range['start_date']),
                    date.fromisoformat(date_range['end_date'])
                )
            elif data_type == 'creative':
                data = AdvertiserAnalyticsService._get_creative_analytics(
                    advertiser,
                    date.fromisoformat(date_range['start_date']),
                    date.fromisoformat(date_range['end_date'])
                )
            elif data_type == 'targeting':
                data = AdvertiserAnalyticsService._get_targeting_analytics(
                    advertiser,
                    date.fromisoformat(date_range['start_date']),
                    date.fromisoformat(date_range['end_date'])
                )
            elif data_type == 'billing':
                data = AdvertiserAnalyticsService._get_billing_analytics(
                    advertiser,
                    date.fromisoformat(date_range['start_date']),
                    date.fromisoformat(date_range['end_date'])
                )
            
            # Format data based on export format
            if export_format == 'json':
                formatted_data = data
            elif export_format == 'csv':
                formatted_data = AdvertiserAnalyticsService._format_as_csv(data)
            elif export_format == 'excel':
                formatted_data = AdvertiserAnalyticsService._format_as_excel(data)
            elif export_format == 'pdf':
                formatted_data = AdvertiserAnalyticsService._format_as_pdf(data)
            
            # Log export
            from ..database_models.audit_model import AuditLog
            AuditLog.log_action(
                action='export_analytics',
                object_type='Advertiser',
                object_id=str(advertiser.id),
                user=exported_by,
                advertiser=advertiser,
                description=f"Exported {data_type} analytics in {export_format} format"
            )
            
            return {
                'advertiser_id': str(advertiser_id),
                'export_format': export_format,
                'data_type': data_type,
                'date_range': date_range,
                'data': formatted_data,
                'exported_at': timezone.now().isoformat()
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error exporting analytics data {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to export analytics data: {str(e)}")
    
    @staticmethod
    def get_analytics_insights(advertiser_id: UUID) -> List[Dict[str, Any]]:
        """Get analytics insights and recommendations."""
        try:
            advertiser = AdvertiserAnalyticsService.get_advertiser(advertiser_id)
            
            insights = []
            
            # Get recent analytics summary
            analytics_summary = AdvertiserAnalyticsService.get_analytics_summary(advertiser_id)
            
            # Analyze campaign performance
            campaign_metrics = analytics_summary.get('campaign_analytics', {})
            
            if campaign_metrics.get('active_campaigns', 0) == 0:
                insights.append({
                    'type': 'no_active_campaigns',
                    'priority': 'high',
                    'title': 'No Active Campaigns',
                    'description': 'You have no active campaigns running.',
                    'recommendations': [
                        'Create and launch new campaigns',
                        'Check if campaigns are paused or ended',
                        'Review campaign settings and budgets'
                    ]
                })
            
            # Analyze CTR performance
            overall_metrics = analytics_summary.get('overall_metrics', {})
            ctr = overall_metrics.get('ctr', 0)
            
            if ctr < 1.0:
                insights.append({
                    'type': 'low_ctr',
                    'priority': 'high',
                    'title': 'Low Click-Through Rate',
                    'description': f'Your CTR is {ctr:.2f}%, which is below optimal.',
                    'recommendations': [
                        'Improve ad creative quality',
                        'Refine targeting parameters',
                        'Test different ad formats',
                        'Optimize ad copy and headlines'
                    ]
                })
            elif ctr > 5.0:
                insights.append({
                    'type': 'high_ctr',
                    'priority': 'medium',
                    'title': 'Excellent Click-Through Rate',
                    'description': f'Your CTR is {ctr:.2f}%, which is excellent!',
                    'recommendations': [
                        'Consider increasing budget for high-CTR campaigns',
                        'Scale successful ad variations',
                        'Test higher bids for better placement'
                    ]
                })
            
            # Analyze spend efficiency
            spend = overall_metrics.get('total_spend', 0)
            revenue = overall_metrics.get('total_revenue', 0)
            
            if spend > 0 and revenue > 0:
                roas = revenue / spend
                if roas < 1.0:
                    insights.append({
                        'type': 'negative_roas',
                        'priority': 'critical',
                        'title': 'Negative Return on Ad Spend',
                        'description': f'Your ROAS is {roas:.2f}x, meaning you\'re losing money.',
                        'recommendations': [
                            'Pause underperforming campaigns immediately',
                            'Review bidding strategy',
                            'Optimize landing pages',
                            'Reassess campaign objectives'
                        ]
                    })
                elif roas > 5.0:
                    insights.append({
                        'type': 'excellent_roas',
                        'priority': 'medium',
                        'title': 'Excellent Return on Ad Spend',
                        'description': f'Your ROAS is {roas:.2f}x, which is exceptional!',
                        'recommendations': [
                            'Increase budget significantly',
                            'Scale to new channels',
                            'Test higher bids for premium placements'
                        ]
                    })
            
            # Analyze creative performance
            creative_metrics = analytics_summary.get('creative_analytics', {})
            
            top_creatives = creative_metrics.get('top_performing_creatives', [])
            if top_creatives:
                best_creative = top_creatives[0]
                insights.append({
                    'type': 'top_performing_creative',
                    'priority': 'medium',
                    'title': 'Top Performing Creative Identified',
                    'description': f'Your best creative "{best_creative.get("name", "Unknown")}" has a CTR of {best_creative.get("ctr", 0):.2f}%',
                    'recommendations': [
                        'Increase budget for top-performing creative',
                        'Analyze what makes this creative successful',
                        'Create similar variations based on success factors',
                        'Test this creative in different campaigns'
                    ]
                })
            
            # Analyze targeting efficiency
            targeting_metrics = analytics_summary.get('targeting_analytics', {})
            
            best_performing_target = targeting_metrics.get('best_performing_target')
            if best_performing_target:
                insights.append({
                    'type': 'best_targeting',
                    'priority': 'medium',
                    'title': 'Best Performing Target Segment',
                    'description': f'Your best performing target is {best_performing_target.get("segment", "Unknown")} with ROAS of {best_performing_target.get("roas", 0):.2f}x',
                    'recommendations': [
                        'Increase budget allocation to this segment',
                        'Expand audience with similar characteristics',
                        'Create tailored creatives for this segment',
                        'Test lookalike audiences based on this segment'
                    ]
                })
            
            return insights
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting analytics insights {advertiser_id}: {str(e)}")
            return []
    
    @staticmethod
    def _generate_campaign_report(advertiser: Advertiser, start_date: date, end_date: date,
                                   report: AnalyticsReport) -> Dict[str, Any]:
        """Generate campaign analytics report."""
        try:
            campaigns = Campaign.objects.filter(
                advertiser=advertiser,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date,
                is_deleted=False
            )
            
            # Campaign summary
            total_campaigns = campaigns.count()
            active_campaigns = campaigns.filter(status='active').count()
            
            # Performance metrics
            total_impressions = campaigns.aggregate(total=Sum('total_impressions'))['total'] or 0
            total_clicks = campaigns.aggregate(total=Sum('total_clicks'))['total'] or 0
            total_conversions = campaigns.aggregate(total=Sum('total_conversions'))['total'] or 0
            total_spend = campaigns.aggregate(total=Sum('current_spend'))['total'] or Decimal('0.00')
            
            # Calculate derived metrics
            ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            cpc = (total_spend / total_clicks) if total_clicks > 0 else 0
            cpa = (total_spend / total_conversions) if total_conversions > 0 else 0
            
            # Campaign breakdown
            campaign_breakdown = []
            for campaign in campaigns:
                campaign_breakdown.append({
                    'id': str(campaign.id),
                    'name': campaign.name,
                    'status': campaign.status,
                    'objective': campaign.objective,
                    'impressions': campaign.total_impressions,
                    'clicks': campaign.total_clicks,
                    'conversions': campaign.total_conversions,
                    'spend': float(campaign.current_spend),
                    'ctr': (campaign.total_clicks / campaign.total_impressions * 100) if campaign.total_impressions > 0 else 0
                })
            
            return {
                'summary': {
                    'total_campaigns': total_campaigns,
                    'active_campaigns': active_campaigns,
                    'total_impressions': total_impressions,
                    'total_clicks': total_clicks,
                    'total_conversions': total_conversions,
                    'total_spend': float(total_spend),
                    'ctr': ctr,
                    'cpc': float(cpc),
                    'cpa': float(cpa)
                },
                'campaign_breakdown': campaign_breakdown,
                'top_performing_campaigns': sorted(campaign_breakdown, key=lambda x: x['ctr'], reverse=True)[:5]
            }
            
        except Exception as e:
            logger.error(f"Error generating campaign report: {str(e)}")
            return {}
    
    @staticmethod
    def _generate_creative_report(advertiser: Advertiser, start_date: date, end_date: date,
                                  report: AnalyticsReport) -> Dict[str, Any]:
        """Generate creative analytics report."""
        try:
            # Mock creative analytics data
            return {
                'summary': {
                    'total_creatives': 10,
                    'active_creatives': 8,
                    'average_ctr': 2.5,
                    'top_performing_ctr': 5.2
                },
                'creative_performance': [
                    {
                        'id': 'creative_1',
                        'name': 'Banner Ad 1',
                        'type': 'banner',
                        'impressions': 10000,
                        'clicks': 250,
                        'ctr': 2.5
                    }
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating creative report: {str(e)}")
            return {}
    
    @staticmethod
    def _generate_targeting_report(advertiser: Advertiser, start_date: date, end_date: date,
                                    report: AnalyticsReport) -> Dict[str, Any]:
        """Generate targeting analytics report."""
        try:
            # Mock targeting analytics data
            return {
                'summary': {
                    'total_targeting_rules': 15,
                    'active_segments': 8,
                    'average_roas': 3.2,
                    'best_performing_roas': 5.8
                },
                'targeting_performance': [
                    {
                        'segment': 'Age 25-34',
                        'impressions': 5000,
                        'clicks': 150,
                        'conversions': 15,
                        'roas': 4.2
                    }
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating targeting report: {str(e)}")
            return {}
    
    @staticmethod
    def _generate_billing_report(advertiser: Advertiser, start_date: date, end_date: date,
                                report: AnalyticsReport) -> Dict[str, Any]:
        """Generate billing analytics report."""
        try:
            # Mock billing analytics data
            return {
                'summary': {
                    'total_spend': 1000.00,
                    'average_daily_spend': 33.33,
                    'total_invoices': 3,
                    'paid_invoices': 2
                },
                'spend_breakdown': [
                    {
                        'date': '2023-01-01',
                        'amount': 100.00,
                        'campaigns': 2
                    }
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating billing report: {str(e)}")
            return {}
    
    @staticmethod
    def _generate_custom_report(advertiser: Advertiser, start_date: date, end_date: date,
                                report: AnalyticsReport) -> Dict[str, Any]:
        """Generate custom analytics report."""
        try:
            # Get custom configuration
            configuration = report.configuration
            metrics = report.metrics
            dimensions = report.dimensions
            
            # Generate custom data based on configuration
            custom_data = {
                'configuration': configuration,
                'metrics': metrics,
                'dimensions': dimensions,
                'data': []
            }
            
            # Mock custom data generation
            for dimension in dimensions:
                custom_data['data'].append({
                    dimension: 100,
                    'metric_1': 50,
                    'metric_2': 25
                })
            
            return custom_data
            
        except Exception as e:
            logger.error(f"Error generating custom report: {str(e)}")
            return {}
    
    @staticmethod
    def _add_widget_to_dashboard(dashboard: AnalyticsDashboard, widget_data: Dict[str, Any],
                                 created_by: Optional[User] = None) -> AnalyticsWidget:
        """Add widget to dashboard."""
        try:
            widget = AnalyticsWidget.objects.create(
                dashboard=dashboard,
                widget_type=widget_data.get('widget_type', 'metric'),
                title=widget_data.get('title', ''),
                configuration=widget_data.get('configuration', {}),
                position=widget_data.get('position', 0),
                size=widget_data.get('size', 'medium'),
                created_by=created_by
            )
            
            return widget
            
        except Exception as e:
            logger.error(f"Error adding widget to dashboard: {str(e)}")
            raise
    
    @staticmethod
    def _generate_widget_data(widget: AnalyticsWidget, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate data for specific widget."""
        try:
            widget_type = widget.widget_type
            configuration = widget.configuration
            
            if widget_type == 'metric':
                return AdvertiserAnalyticsService._generate_metric_widget(widget, configuration, filters)
            elif widget_type == 'chart':
                return AdvertiserAnalyticsService._generate_chart_widget(widget, configuration, filters)
            elif widget_type == 'table':
                return AdvertiserAnalyticsService._generate_table_widget(widget, configuration, filters)
            else:
                return {'error': f'Unknown widget type: {widget_type}'}
                
        except Exception as e:
            logger.error(f"Error generating widget data: {str(e)}")
            return {'error': str(e)}
    
    @staticmethod
    def _generate_metric_widget(widget: AnalyticsWidget, configuration: Dict[str, Any],
                                 filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate metric widget data."""
        try:
            metric_name = configuration.get('metric', 'impressions')
            
            # Mock metric data
            return {
                'id': str(widget.id),
                'widget_type': widget.widget_type,
                'title': widget.title,
                'metric': metric_name,
                'value': 1000,
                'change': 10.5,
                'change_type': 'increase'
            }
            
        except Exception as e:
            logger.error(f"Error generating metric widget: {str(e)}")
            return {}
    
    @staticmethod
    def _generate_chart_widget(widget: AnalyticsWidget, configuration: Dict[str, Any],
                                filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate chart widget data."""
        try:
            chart_type = configuration.get('chart_type', 'line')
            
            # Mock chart data
            return {
                'id': str(widget.id),
                'widget_type': widget.widget_type,
                'title': widget.title,
                'chart_type': chart_type,
                'data': [
                    {'x': '2023-01-01', 'y': 100},
                    {'x': '2023-01-02', 'y': 150},
                    {'x': '2023-01-03', 'y': 120}
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating chart widget: {str(e)}")
            return {}
    
    @staticmethod
    def _generate_table_widget(widget: AnalyticsWidget, configuration: Dict[str, Any],
                                filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate table widget data."""
        try:
            # Mock table data
            return {
                'id': str(widget.id),
                'widget_type': widget.widget_type,
                'title': widget.title,
                'columns': ['Campaign', 'Impressions', 'Clicks', 'CTR'],
                'rows': [
                    ['Campaign 1', 1000, 50, 5.0],
                    ['Campaign 2', 2000, 80, 4.0]
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating table widget: {str(e)}")
            return {}
    
    @staticmethod
    def _get_campaign_analytics(advertiser: Advertiser, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get campaign analytics data."""
        try:
            campaigns = Campaign.objects.filter(
                advertiser=advertiser,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date,
                is_deleted=False
            )
            
            return {
                'total_campaigns': campaigns.count(),
                'active_campaigns': campaigns.filter(status='active').count(),
                'total_impressions': campaigns.aggregate(total=Sum('total_impressions'))['total'] or 0,
                'total_clicks': campaigns.aggregate(total=Sum('total_clicks'))['total'] or 0,
                'total_conversions': campaigns.aggregate(total=Sum('total_conversions'))['total'] or 0,
                'total_spend': float(campaigns.aggregate(total=Sum('current_spend'))['total'] or 0)
            }
            
        except Exception as e:
            logger.error(f"Error getting campaign analytics: {str(e)}")
            return {}
    
    @staticmethod
    def _get_creative_analytics(advertiser: Advertiser, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get creative analytics data."""
        try:
            # Mock creative analytics
            return {
                'total_creatives': 10,
                'active_creatives': 8,
                'average_ctr': 2.5,
                'top_performing_creatives': [
                    {'name': 'Creative 1', 'ctr': 5.2},
                    {'name': 'Creative 2', 'ctr': 4.8}
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting creative analytics: {str(e)}")
            return {}
    
    @staticmethod
    def _get_targeting_analytics(advertiser: Advertiser, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get targeting analytics data."""
        try:
            # Mock targeting analytics
            return {
                'total_segments': 15,
                'active_segments': 8,
                'average_roas': 3.2,
                'best_performing_target': {
                    'segment': 'Age 25-34',
                    'roas': 5.8
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting targeting analytics: {str(e)}")
            return {}
    
    @staticmethod
    def _get_billing_analytics(advertiser: Advertiser, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get billing analytics data."""
        try:
            # Mock billing analytics
            return {
                'total_spend': 1000.00,
                'average_daily_spend': 33.33,
                'total_invoices': 3,
                'paid_invoices': 2,
                'outstanding_amount': 500.00
            }
            
        except Exception as e:
            logger.error(f"Error getting billing analytics: {str(e)}")
            return {}
    
    @staticmethod
    def _calculate_overall_metrics(campaign: Dict, creative: Dict, targeting: Dict, billing: Dict) -> Dict[str, Any]:
        """Calculate overall metrics from different analytics categories."""
        try:
            total_impressions = campaign.get('total_impressions', 0)
            total_clicks = campaign.get('total_clicks', 0)
            total_conversions = campaign.get('total_conversions', 0)
            total_spend = campaign.get('total_spend', 0)
            
            return {
                'ctr': (total_clicks / total_impressions * 100) if total_impressions > 0 else 0,
                'cpc': (total_spend / total_clicks) if total_clicks > 0 else 0,
                'cpa': (total_spend / total_conversions) if total_conversions > 0 else 0,
                'total_impressions': total_impressions,
                'total_clicks': total_clicks,
                'total_conversions': total_conversions,
                'total_spend': total_spend
            }
            
        except Exception as e:
            logger.error(f"Error calculating overall metrics: {str(e)}")
            return {}
    
    @staticmethod
    def _get_top_campaigns(advertiser: Advertiser, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top performing campaigns."""
        try:
            campaigns = Campaign.objects.filter(
                advertiser=advertiser,
                status='active',
                is_deleted=False
            ).order_by('-total_clicks')[:limit]
            
            return [
                {
                    'id': str(campaign.id),
                    'name': campaign.name,
                    'impressions': campaign.total_impressions,
                    'clicks': campaign.total_clicks,
                    'ctr': (campaign.total_clicks / campaign.total_impressions * 100) if campaign.total_impressions > 0 else 0
                }
                for campaign in campaigns
            ]
            
        except Exception as e:
            logger.error(f"Error getting top campaigns: {str(e)}")
            return []
    
    @staticmethod
    def _format_as_csv(data: Dict[str, Any]) -> str:
        """Format data as CSV."""
        try:
            # Mock CSV formatting
            return "id,name,value\n1,Test,100"
            
        except Exception as e:
            logger.error(f"Error formatting as CSV: {str(e)}")
            return ""
    
    @staticmethod
    def _format_as_excel(data: Dict[str, Any]) -> bytes:
        """Format data as Excel."""
        try:
            # Mock Excel formatting
            return b"excel_data"
            
        except Exception as e:
            logger.error(f"Error formatting as Excel: {str(e)}")
            return b""
    
    @staticmethod
    def _format_as_pdf(data: Dict[str, Any]) -> bytes:
        """Format data as PDF."""
        try:
            # Mock PDF formatting
            return b"pdf_data"
            
        except Exception as e:
            logger.error(f"Error formatting as PDF: {str(e)}")
            return b""
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def get_analytics_report(report_id: UUID) -> AnalyticsReport:
        """Get analytics report by ID."""
        try:
            return AnalyticsReport.objects.get(id=report_id)
        except AnalyticsReport.DoesNotExist:
            raise AdvertiserNotFoundError(f"Analytics report {report_id} not found")
    
    @staticmethod
    def get_analytics_dashboard(dashboard_id: UUID) -> AnalyticsDashboard:
        """Get analytics dashboard by ID."""
        try:
            return AnalyticsDashboard.objects.get(id=dashboard_id)
        except AnalyticsDashboard.DoesNotExist:
            raise AdvertiserNotFoundError(f"Analytics dashboard {dashboard_id} not found")
    
    @staticmethod
    def get_analytics_statistics() -> Dict[str, Any]:
        """Get analytics statistics across all advertisers."""
        try:
            # Get total reports and dashboards
            total_reports = AnalyticsReport.objects.count()
            total_dashboards = AnalyticsDashboard.objects.count()
            total_widgets = AnalyticsWidget.objects.count()
            
            return {
                'total_reports': total_reports,
                'total_dashboards': total_dashboards,
                'total_widgets': total_widgets
            }
            
        except Exception as e:
            logger.error(f"Error getting analytics statistics: {str(e)}")
            return {
                'total_reports': 0,
                'total_dashboards': 0,
                'total_widgets': 0
            }
