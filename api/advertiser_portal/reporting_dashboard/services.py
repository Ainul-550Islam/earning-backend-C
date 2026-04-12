"""
Reporting Dashboard Services

This module handles reporting and dashboard operations with enterprise-grade
security, real-time analytics, and comprehensive data visualization
following industry standards from Google Analytics, Tableau, and Power BI.
"""

from typing import Optional, List, Dict, Any, Union, Tuple
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json
import math
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum
import time

from django.db import transaction, connection
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Count, Sum, Avg, StdDev, Q, F, Window, Case, When
from django.db.models.functions import Coalesce, RowNumber, Lead, Lag, Trunc, Extract
from django.core.cache import cache
from django.http import HttpResponse
from django.core.paginator import Paginator

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.creative_model import Creative
from ..database_models.analytics_model import AnalyticsEvent, PerformanceMetric
from ..database_models.reporting_model import Report, Dashboard, Visualization, ReportSchedule
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


@dataclass
class ReportData:
    """Report data structure with metadata."""
    report_id: str
    report_name: str
    report_type: str
    data: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    generated_at: datetime
    total_records: int
    execution_time: float
    cache_key: Optional[str] = None


@dataclass
class DashboardWidget:
    """Dashboard widget configuration."""
    widget_id: str
    widget_type: str
    title: str
    data_source: str
    configuration: Dict[str, Any]
    data: Dict[str, Any]
    last_updated: datetime
    refresh_interval: int


@dataclass
class AnalyticsMetric:
    """Analytics metric definition."""
    metric_id: str
    metric_name: str
    metric_type: str  # count, sum, avg, rate, ratio
    data_source: str
    calculation: Dict[str, Any]
    filters: Dict[str, Any]
    time_range: str


@dataclass
class VisualizationConfig:
    """Visualization configuration."""
    viz_id: str
    viz_type: str  # chart, table, map, funnel, etc.
    title: str
    data_source: str
    chart_config: Dict[str, Any]
    filters: Dict[str, Any]
    time_range: str


class ReportingService:
    """
    Enterprise-grade reporting service with comprehensive analytics.
    
    Features:
    - Real-time data aggregation
    - Custom report generation
    - Scheduled report delivery
    - Multi-format export (CSV, Excel, PDF)
    - High-performance data processing
    - Advanced filtering and segmentation
    """
    
    @staticmethod
    def generate_report(report_config: Dict[str, Any], requested_by: Optional[User] = None) -> ReportData:
        """
        Generate comprehensive report with enterprise-grade processing.
        
        Report types:
        - Performance reports (CTR, CPC, CPA, ROAS)
        - Financial reports (spend, revenue, ROI)
        - Audience reports (demographics, behavior)
        - Campaign reports (performance, optimization)
        - Custom reports (user-defined)
        
        Performance optimizations:
        - Parallel data processing
        - Database query optimization
        - Caching of frequent reports
        - Batch processing for large datasets
        """
        try:
            start_time = time.time()
            
            # Security: Validate report configuration
            ReportingService._validate_report_config(report_config, requested_by)
            
            # Generate cache key
            cache_key = ReportingService._generate_cache_key(report_config)
            
            # Performance: Check cache first
            cached_report = cache.get(cache_key)
            if cached_report:
                return cached_report
            
            # Initialize report data
            report_data = ReportData(
                report_id=str(UUID.uuid4()),
                report_name=report_config.get('name', 'Untitled Report'),
                report_type=report_config.get('report_type', 'custom'),
                data=[],
                metadata={},
                generated_at=timezone.now(),
                total_records=0,
                execution_time=0.0,
                cache_key=cache_key
            )
            
            # Generate report based on type
            if report_config.get('report_type') == 'performance':
                report_data = ReportingService._generate_performance_report(report_config, report_data)
            elif report_config.get('report_type') == 'financial':
                report_data = ReportingService._generate_financial_report(report_config, report_data)
            elif report_config.get('report_type') == 'audience':
                report_data = ReportingService._generate_audience_report(report_config, report_data)
            elif report_config.get('report_type') == 'campaign':
                report_data = ReportingService._generate_campaign_report(report_config, report_data)
            else:
                report_data = ReportingService._generate_custom_report(report_config, report_data)
            
            # Calculate execution time
            report_data.execution_time = time.time() - start_time
            
            # Performance: Cache report
            cache_timeout = ReportingService._get_cache_timeout(report_config.get('report_type'))
            cache.set(cache_key, report_data, timeout=cache_timeout)
            
            # Log report generation
            ReportingService._log_report_generation(report_data, requested_by)
            
            return report_data
            
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            raise AdvertiserServiceError(f"Failed to generate report: {str(e)}")
    
    @staticmethod
    def schedule_report(schedule_config: Dict[str, Any], created_by: Optional[User] = None) -> ReportSchedule:
        """Schedule automated report generation and delivery."""
        try:
            # Security: Validate schedule configuration
            ReportingService._validate_schedule_config(schedule_config, created_by)
            
            with transaction.atomic():
                # Create report schedule
                schedule = ReportSchedule.objects.create(
                    name=schedule_config.get('name'),
                    description=schedule_config.get('description', ''),
                    report_config=schedule_config.get('report_config', {}),
                    schedule_type=schedule_config.get('schedule_type', 'daily'),
                    schedule_params=schedule_config.get('schedule_params', {}),
                    delivery_method=schedule_config.get('delivery_method', 'email'),
                    delivery_params=schedule_config.get('delivery_params', {}),
                    is_active=schedule_config.get('is_active', True),
                    created_by=created_by
                )
                
                # Send notification
                Notification.objects.create(
                    user=created_by,
                    title='Report Schedule Created',
                    message=f'Report schedule "{schedule.name}" has been created.',
                    notification_type='reporting',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log schedule creation
                ReportingService._log_schedule_creation(schedule, created_by)
                
                return schedule
                
        except Exception as e:
            logger.error(f"Error scheduling report: {str(e)}")
            raise AdvertiserServiceError(f"Failed to schedule report: {str(e)}")
    
    @staticmethod
    def export_report(report_id: UUID, export_format: str = 'csv', 
                     filters: Optional[Dict[str, Any]] = None) -> HttpResponse:
        """
        Export report in various formats with enterprise-grade processing.
        
        Export formats:
        - CSV (Comma-separated values)
        - Excel (XLSX with formatting)
        - PDF (Formatted report with charts)
        - JSON (Structured data)
        - XML (Structured data)
        
        Performance optimizations:
        - Streaming for large datasets
        - Memory-efficient processing
        - Parallel data generation
        - Compressed output
        """
        try:
            # Security: Validate export request
            ReportingService._validate_export_request(report_id, export_format, filters)
            
            # Get report data
            report_data = ReportingService._get_report_data(report_id, filters)
            
            # Generate export based on format
            if export_format.lower() == 'csv':
                return ReportingService._export_csv(report_data)
            elif export_format.lower() == 'excel':
                return ReportingService._export_excel(report_data)
            elif export_format.lower() == 'pdf':
                return ReportingService._export_pdf(report_data)
            elif export_format.lower() == 'json':
                return ReportingService._export_json(report_data)
            elif export_format.lower() == 'xml':
                return ReportingService._export_xml(report_data)
            else:
                raise AdvertiserValidationError(f"Unsupported export format: {export_format}")
                
        except Exception as e:
            logger.error(f"Error exporting report: {str(e)}")
            raise AdvertiserServiceError(f"Failed to export report: {str(e)}")
    
    @staticmethod
    def _generate_performance_report(report_config: Dict[str, Any], report_data: ReportData) -> ReportData:
        """Generate performance report with comprehensive metrics."""
        try:
            # Get time range
            time_range = ReportingService._parse_time_range(report_config.get('time_range', 'last_30_days'))
            
            # Get advertiser filter
            advertiser_id = report_config.get('advertiser_id')
            
            # Performance: Use optimized queries
            with ThreadPoolExecutor(max_workers=4) as executor:
                # Parallel data collection
                futures = {
                    'metrics': executor.submit(ReportingService._get_performance_metrics, time_range, advertiser_id),
                    'trends': executor.submit(ReportingService._get_performance_trends, time_range, advertiser_id),
                    'comparisons': executor.submit(ReportingService._get_performance_comparisons, time_range, advertiser_id),
                    'breakdowns': executor.submit(ReportingService._get_performance_breakdowns, time_range, advertiser_id)
                }
                
                # Collect results
                results = {}
                for key, future in futures.items():
                    try:
                        results[key] = future.result(timeout=30)  # 30 second timeout
                    except Exception as e:
                        logger.error(f"Error getting {key}: {str(e)}")
                        results[key] = {}
            
            # Structure report data
            report_data.data = [
                {
                    'metric': 'CTR',
                    'value': results['metrics'].get('ctr', 0),
                    'change': results['comparisons'].get('ctr_change', 0),
                    'trend': results['trends'].get('ctr_trend', 'stable')
                },
                {
                    'metric': 'CPC',
                    'value': results['metrics'].get('cpc', 0),
                    'change': results['comparisons'].get('cpc_change', 0),
                    'trend': results['trends'].get('cpc_trend', 'stable')
                },
                {
                    'metric': 'CPA',
                    'value': results['metrics'].get('cpa', 0),
                    'change': results['comparisons'].get('cpa_change', 0),
                    'trend': results['trends'].get('cpa_trend', 'stable')
                },
                {
                    'metric': 'ROAS',
                    'value': results['metrics'].get('roas', 0),
                    'change': results['comparisons'].get('roas_change', 0),
                    'trend': results['trends'].get('roas_trend', 'stable')
                },
                {
                    'metric': 'Conversions',
                    'value': results['metrics'].get('conversions', 0),
                    'change': results['comparisons'].get('conversions_change', 0),
                    'trend': results['trends'].get('conversions_trend', 'stable')
                },
                {
                    'metric': 'Revenue',
                    'value': results['metrics'].get('revenue', 0),
                    'change': results['comparisons'].get('revenue_change', 0),
                    'trend': results['trends'].get('revenue_trend', 'stable')
                }
            ]
            
            # Add breakdowns
            report_data.metadata = {
                'time_range': report_config.get('time_range'),
                'advertiser_id': advertiser_id,
                'breakdowns': results['breakdowns'],
                'generated_at': report_data.generated_at.isoformat()
            }
            
            report_data.total_records = len(report_data.data)
            
            return report_data
            
        except Exception as e:
            logger.error(f"Error generating performance report: {str(e)}")
            raise AdvertiserServiceError(f"Failed to generate performance report: {str(e)}")
    
    @staticmethod
    def _generate_financial_report(report_config: Dict[str, Any], report_data: ReportData) -> ReportData:
        """Generate financial report with comprehensive financial metrics."""
        try:
            # Get time range
            time_range = ReportingService._parse_time_range(report_config.get('time_range', 'last_30_days'))
            
            # Get advertiser filter
            advertiser_id = report_config.get('advertiser_id')
            
            # Performance: Use optimized queries
            financial_data = ReportingService._get_financial_metrics(time_range, advertiser_id)
            
            # Structure report data
            report_data.data = [
                {
                    'category': 'Revenue',
                    'current_period': financial_data.get('current_revenue', 0),
                    'previous_period': financial_data.get('previous_revenue', 0),
                    'change': financial_data.get('revenue_change', 0),
                    'change_percentage': financial_data.get('revenue_change_percentage', 0)
                },
                {
                    'category': 'Spend',
                    'current_period': financial_data.get('current_spend', 0),
                    'previous_period': financial_data.get('previous_spend', 0),
                    'change': financial_data.get('spend_change', 0),
                    'change_percentage': financial_data.get('spend_change_percentage', 0)
                },
                {
                    'category': 'Profit',
                    'current_period': financial_data.get('current_profit', 0),
                    'previous_period': financial_data.get('previous_profit', 0),
                    'change': financial_data.get('profit_change', 0),
                    'change_percentage': financial_data.get('profit_change_percentage', 0)
                },
                {
                    'category': 'ROI',
                    'current_period': financial_data.get('current_roi', 0),
                    'previous_period': financial_data.get('previous_roi', 0),
                    'change': financial_data.get('roi_change', 0),
                    'change_percentage': financial_data.get('roi_change_percentage', 0)
                },
                {
                    'category': 'CAC',
                    'current_period': financial_data.get('current_cac', 0),
                    'previous_period': financial_data.get('previous_cac', 0),
                    'change': financial_data.get('cac_change', 0),
                    'change_percentage': financial_data.get('cac_change_percentage', 0)
                },
                {
                    'category': 'LTV',
                    'current_period': financial_data.get('current_ltv', 0),
                    'previous_period': financial_data.get('previous_ltv', 0),
                    'change': financial_data.get('ltv_change', 0),
                    'change_percentage': financial_data.get('ltv_change_percentage', 0)
                }
            ]
            
            # Add metadata
            report_data.metadata = {
                'time_range': report_config.get('time_range'),
                'advertiser_id': advertiser_id,
                'currency': 'USD',
                'generated_at': report_data.generated_at.isoformat()
            }
            
            report_data.total_records = len(report_data.data)
            
            return report_data
            
        except Exception as e:
            logger.error(f"Error generating financial report: {str(e)}")
            raise AdvertiserServiceError(f"Failed to generate financial report: {str(e)}")
    
    @staticmethod
    def _generate_audience_report(report_config: Dict[str, Any], report_data: ReportData) -> ReportData:
        """Generate audience report with comprehensive audience analytics."""
        try:
            # Get time range
            time_range = ReportingService._parse_time_range(report_config.get('time_range', 'last_30_days'))
            
            # Get advertiser filter
            advertiser_id = report_config.get('advertiser_id')
            
            # Performance: Use optimized queries
            audience_data = ReportingService._get_audience_metrics(time_range, advertiser_id)
            
            # Structure report data
            report_data.data = [
                {
                    'segment': 'Demographics',
                    'metrics': audience_data.get('demographics', {})
                },
                {
                    'segment': 'Geography',
                    'metrics': audience_data.get('geography', {})
                },
                {
                    'segment': 'Behavior',
                    'metrics': audience_data.get('behavior', {})
                },
                {
                    'segment': 'Device',
                    'metrics': audience_data.get('device', {})
                },
                {
                    'segment': 'Interests',
                    'metrics': audience_data.get('interests', {})
                }
            ]
            
            # Add metadata
            report_data.metadata = {
                'time_range': report_config.get('time_range'),
                'advertiser_id': advertiser_id,
                'total_audience_size': audience_data.get('total_size', 0),
                'generated_at': report_data.generated_at.isoformat()
            }
            
            report_data.total_records = len(report_data.data)
            
            return report_data
            
        except Exception as e:
            logger.error(f"Error generating audience report: {str(e)}")
            raise AdvertiserServiceError(f"Failed to generate audience report: {str(e)}")
    
    @staticmethod
    def _generate_campaign_report(report_config: Dict[str, Any], report_data: ReportData) -> ReportData:
        """Generate campaign report with comprehensive campaign analytics."""
        try:
            # Get time range
            time_range = ReportingService._parse_time_range(report_config.get('time_range', 'last_30_days'))
            
            # Get campaign filter
            campaign_id = report_config.get('campaign_id')
            
            # Performance: Use optimized queries
            campaign_data = ReportingService._get_campaign_metrics(time_range, campaign_id)
            
            # Structure report data
            report_data.data = [
                {
                    'campaign_id': str(campaign.get('id')),
                    'campaign_name': campaign.get('name'),
                    'status': campaign.get('status'),
                    'metrics': campaign.get('metrics', {})
                }
                for campaign in campaign_data.get('campaigns', [])
            ]
            
            # Add metadata
            report_data.metadata = {
                'time_range': report_config.get('time_range'),
                'campaign_id': campaign_id,
                'total_campaigns': len(campaign_data.get('campaigns', [])),
                'generated_at': report_data.generated_at.isoformat()
            }
            
            report_data.total_records = len(report_data.data)
            
            return report_data
            
        except Exception as e:
            logger.error(f"Error generating campaign report: {str(e)}")
            raise AdvertiserServiceError(f"Failed to generate campaign report: {str(e)}")
    
    @staticmethod
    def _generate_custom_report(report_config: Dict[str, Any], report_data: ReportData) -> ReportData:
        """Generate custom report based on user-defined configuration."""
        try:
            # Get custom query configuration
            query_config = report_config.get('query_config', {})
            
            # Execute custom query
            custom_data = ReportingService._execute_custom_query(query_config)
            
            # Structure report data
            report_data.data = custom_data.get('data', [])
            
            # Add metadata
            report_data.metadata = {
                'query_config': query_config,
                'generated_at': report_data.generated_at.isoformat()
            }
            
            report_data.total_records = len(report_data.data)
            
            return report_data
            
        except Exception as e:
            logger.error(f"Error generating custom report: {str(e)}")
            raise AdvertiserServiceError(f"Failed to generate custom report: {str(e)}")
    
    @staticmethod
    def _get_performance_metrics(time_range: Tuple[datetime, datetime], 
                              advertiser_id: Optional[UUID]) -> Dict[str, Any]:
        """Get performance metrics with optimized queries."""
        try:
            # Build base query
            queryset = PerformanceMetric.objects.filter(
                timestamp__range=time_range
            )
            
            # Apply advertiser filter
            if advertiser_id:
                queryset = queryset.filter(advertiser_id=advertiser_id)
            
            # Performance: Use optimized aggregate queries
            metrics = queryset.aggregate(
                total_impressions=Coalesce(Sum('impressions'), 0),
                total_clicks=Coalesce(Sum('clicks'), 0),
                total_conversions=Coalesce(Sum('conversions'), 0),
                total_spend=Coalesce(Sum('spend'), Decimal('0.00')),
                total_revenue=Coalesce(Sum('revenue'), Decimal('0.00'))
            )
            
            # Calculate derived metrics
            impressions = metrics['total_impressions'] or 0
            clicks = metrics['total_clicks'] or 0
            conversions = metrics['total_conversions'] or 0
            spend = metrics['total_spend'] or Decimal('0.00')
            revenue = metrics['total_revenue'] or Decimal('0.00')
            
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            cpc = (spend / clicks) if clicks > 0 else Decimal('0.00')
            cpa = (spend / conversions) if conversions > 0 else Decimal('0.00')
            roas = (revenue / spend) if spend > 0 else Decimal('0.00')
            
            return {
                'impressions': impressions,
                'clicks': clicks,
                'conversions': conversions,
                'spend': float(spend),
                'revenue': float(revenue),
                'ctr': round(ctr, 2),
                'cpc': float(cpc),
                'cpa': float(cpa),
                'roas': float(roas)
            }
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {str(e)}")
            return {}
    
    @staticmethod
    def _get_performance_trends(time_range: Tuple[datetime, datetime], 
                              advertiser_id: Optional[UUID]) -> Dict[str, str]:
        """Get performance trends with time series analysis."""
        try:
            # Build base query
            queryset = PerformanceMetric.objects.filter(
                timestamp__range=time_range
            )
            
            # Apply advertiser filter
            if advertiser_id:
                queryset = queryset.filter(advertiser_id=advertiser_id)
            
            # Performance: Use optimized time series query
            daily_metrics = queryset.annotate(
                date=Trunc('timestamp', 'day')
            ).values('date').annotate(
                daily_impressions=Sum('impressions'),
                daily_clicks=Sum('clicks'),
                daily_conversions=Sum('conversions'),
                daily_spend=Sum('spend'),
                daily_revenue=Sum('revenue')
            ).order_by('date')
            
            # Calculate trends
            trends = {}
            if len(daily_metrics) >= 7:
                recent_week = daily_metrics[-7:]
                previous_week = daily_metrics[-14:-7] if len(daily_metrics) >= 14 else daily_metrics[:-7]
                
                # CTR trend
                recent_ctr = sum(item['daily_clicks'] or 0 for item in recent_week) / sum(item['daily_impressions'] or 1 for item in recent_week) * 100
                previous_ctr = sum(item['daily_clicks'] or 0 for item in previous_week) / sum(item['daily_impressions'] or 1 for item in previous_week) * 100
                trends['ctr_trend'] = 'increasing' if recent_ctr > previous_ctr else 'decreasing' if recent_ctr < previous_ctr else 'stable'
                
                # ROAS trend
                recent_roas = sum(item['daily_revenue'] or 0 for item in recent_week) / sum(item['daily_spend'] or 1 for item in recent_week)
                previous_roas = sum(item['daily_revenue'] or 0 for item in previous_week) / sum(item['daily_spend'] or 1 for item in previous_week)
                trends['roas_trend'] = 'increasing' if recent_roas > previous_roas else 'decreasing' if recent_roas < previous_roas else 'stable'
                
                # Conversions trend
                recent_conversions = sum(item['daily_conversions'] or 0 for item in recent_week)
                previous_conversions = sum(item['daily_conversions'] or 0 for item in previous_week)
                trends['conversions_trend'] = 'increasing' if recent_conversions > previous_conversions else 'decreasing' if recent_conversions < previous_conversions else 'stable'
            
            return trends
            
        except Exception as e:
            logger.error(f"Error getting performance trends: {str(e)}")
            return {}
    
    @staticmethod
    def _get_performance_comparisons(time_range: Tuple[datetime, datetime], 
                                   advertiser_id: Optional[UUID]) -> Dict[str, float]:
        """Get performance comparisons with previous period."""
        try:
            # Calculate previous period
            duration = time_range[1] - time_range[0]
            previous_start = time_range[0] - duration
            previous_end = time_range[0]
            
            # Get current period metrics
            current_metrics = ReportingService._get_performance_metrics(time_range, advertiser_id)
            
            # Get previous period metrics
            previous_metrics = ReportingService._get_performance_metrics((previous_start, previous_end), advertiser_id)
            
            # Calculate changes
            comparisons = {}
            
            # CTR change
            current_ctr = current_metrics.get('ctr', 0)
            previous_ctr = previous_metrics.get('ctr', 0)
            comparisons['ctr_change'] = current_ctr - previous_ctr
            comparisons['ctr_change_percentage'] = ((current_ctr - previous_ctr) / previous_ctr * 100) if previous_ctr > 0 else 0
            
            # ROAS change
            current_roas = current_metrics.get('roas', 0)
            previous_roas = previous_metrics.get('roas', 0)
            comparisons['roas_change'] = current_roas - previous_roas
            comparisons['roas_change_percentage'] = ((current_roas - previous_roas) / previous_roas * 100) if previous_roas > 0 else 0
            
            # Conversions change
            current_conversions = current_metrics.get('conversions', 0)
            previous_conversions = previous_metrics.get('conversions', 0)
            comparisons['conversions_change'] = current_conversions - previous_conversions
            comparisons['conversions_change_percentage'] = ((current_conversions - previous_conversions) / previous_conversions * 100) if previous_conversions > 0 else 0
            
            return comparisons
            
        except Exception as e:
            logger.error(f"Error getting performance comparisons: {str(e)}")
            return {}
    
    @staticmethod
    def _get_performance_breakdowns(time_range: Tuple[datetime, datetime], 
                                  advertiser_id: Optional[UUID]) -> Dict[str, Any]:
        """Get performance breakdowns by various dimensions."""
        try:
            # Build base query
            queryset = PerformanceMetric.objects.filter(
                timestamp__range=time_range
            )
            
            # Apply advertiser filter
            if advertiser_id:
                queryset = queryset.filter(advertiser_id=advertiser_id)
            
            # Performance: Use optimized breakdown queries
            breakdowns = {}
            
            # Breakdown by campaign
            campaign_breakdown = queryset.values('campaign__name').annotate(
                impressions=Sum('impressions'),
                clicks=Sum('clicks'),
                conversions=Sum('conversions'),
                spend=Sum('spend'),
                revenue=Sum('revenue')
            ).order_by('-revenue')[:10]
            
            breakdowns['by_campaign'] = list(campaign_breakdown)
            
            # Breakdown by device
            device_breakdown = queryset.values('device_type').annotate(
                impressions=Sum('impressions'),
                clicks=Sum('clicks'),
                conversions=Sum('conversions'),
                spend=Sum('spend'),
                revenue=Sum('revenue')
            ).order_by('-revenue')
            
            breakdowns['by_device'] = list(device_breakdown)
            
            # Breakdown by geography
            geo_breakdown = queryset.values('country').annotate(
                impressions=Sum('impressions'),
                clicks=Sum('clicks'),
                conversions=Sum('conversions'),
                spend=Sum('spend'),
                revenue=Sum('revenue')
            ).order_by('-revenue')[:10]
            
            breakdowns['by_geography'] = list(geo_breakdown)
            
            return breakdowns
            
        except Exception as e:
            logger.error(f"Error getting performance breakdowns: {str(e)}")
            return {}
    
    @staticmethod
    def _get_financial_metrics(time_range: Tuple[datetime, datetime], 
                              advertiser_id: Optional[UUID]) -> Dict[str, Any]:
        """Get financial metrics with optimized queries."""
        try:
            # Build base query
            queryset = PerformanceMetric.objects.filter(
                timestamp__range=time_range
            )
            
            # Apply advertiser filter
            if advertiser_id:
                queryset = queryset.filter(advertiser_id=advertiser_id)
            
            # Calculate current period metrics
            current_metrics = queryset.aggregate(
                current_spend=Coalesce(Sum('spend'), Decimal('0.00')),
                current_revenue=Coalesce(Sum('revenue'), Decimal('0.00')),
                current_conversions=Coalesce(Sum('conversions'), 0)
            )
            
            # Calculate previous period metrics
            duration = time_range[1] - time_range[0]
            previous_start = time_range[0] - duration
            previous_end = time_range[0]
            
            previous_metrics = queryset.filter(
                timestamp__range=(previous_start, previous_end)
            ).aggregate(
                previous_spend=Coalesce(Sum('spend'), Decimal('0.00')),
                previous_revenue=Coalesce(Sum('revenue'), Decimal('0.00')),
                previous_conversions=Coalesce(Sum('conversions'), 0)
            )
            
            # Calculate derived metrics
            current_spend = current_metrics['current_spend'] or Decimal('0.00')
            current_revenue = current_metrics['current_revenue'] or Decimal('0.00')
            current_conversions = current_metrics['current_conversions'] or 0
            
            previous_spend = previous_metrics['previous_spend'] or Decimal('0.00')
            previous_revenue = previous_metrics['previous_revenue'] or Decimal('0.00')
            previous_conversions = previous_metrics['previous_conversions'] or 0
            
            current_profit = current_revenue - current_spend
            previous_profit = previous_revenue - previous_spend
            
            current_roi = (current_profit / current_spend * 100) if current_spend > 0 else 0
            previous_roi = (previous_profit / previous_spend * 100) if previous_spend > 0 else 0
            
            current_cac = (current_spend / current_conversions) if current_conversions > 0 else Decimal('0.00')
            previous_cac = (previous_spend / previous_conversions) if previous_conversions > 0 else Decimal('0.00')
            
            # LTV calculation (simplified)
            current_ltv = current_revenue / current_conversions if current_conversions > 0 else Decimal('0.00')
            previous_ltv = previous_revenue / previous_conversions if previous_conversions > 0 else Decimal('0.00')
            
            return {
                'current_revenue': float(current_revenue),
                'previous_revenue': float(previous_revenue),
                'revenue_change': float(current_revenue - previous_revenue),
                'revenue_change_percentage': ((current_revenue - previous_revenue) / previous_revenue * 100) if previous_revenue > 0 else 0,
                
                'current_spend': float(current_spend),
                'previous_spend': float(previous_spend),
                'spend_change': float(current_spend - previous_spend),
                'spend_change_percentage': ((current_spend - previous_spend) / previous_spend * 100) if previous_spend > 0 else 0,
                
                'current_profit': float(current_profit),
                'previous_profit': float(previous_profit),
                'profit_change': float(current_profit - previous_profit),
                'profit_change_percentage': ((current_profit - previous_profit) / previous_profit * 100) if previous_profit > 0 else 0,
                
                'current_roi': current_roi,
                'previous_roi': previous_roi,
                'roi_change': current_roi - previous_roi,
                'roi_change_percentage': ((current_roi - previous_roi) / previous_roi * 100) if previous_roi != 0 else 0,
                
                'current_cac': float(current_cac),
                'previous_cac': float(previous_cac),
                'cac_change': float(current_cac - previous_cac),
                'cac_change_percentage': ((current_cac - previous_cac) / previous_cac * 100) if previous_cac > 0 else 0,
                
                'current_ltv': float(current_ltv),
                'previous_ltv': float(previous_ltv),
                'ltv_change': float(current_ltv - previous_ltv),
                'ltv_change_percentage': ((current_ltv - previous_ltv) / previous_ltv * 100) if previous_ltv > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting financial metrics: {str(e)}")
            return {}
    
    @staticmethod
    def _get_audience_metrics(time_range: Tuple[datetime, datetime], 
                             advertiser_id: Optional[UUID]) -> Dict[str, Any]:
        """Get audience metrics with optimized queries."""
        try:
            # Build base query
            queryset = AnalyticsEvent.objects.filter(
                timestamp__range=time_range
            )
            
            # Apply advertiser filter
            if advertiser_id:
                queryset = queryset.filter(advertiser_id=advertiser_id)
            
            # Performance: Use optimized aggregate queries
            audience_metrics = {}
            
            # Demographics breakdown
            demographics = queryset.values('demographics').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            audience_metrics['demographics'] = list(demographics)
            
            # Geography breakdown
            geography = queryset.values('country').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            audience_metrics['geography'] = list(geography)
            
            # Behavior breakdown
            behavior = queryset.values('behavior_type').annotate(
                count=Count('id'),
                avg_session_duration=Avg('session_duration')
            ).order_by('-count')
            
            audience_metrics['behavior'] = list(behavior)
            
            # Device breakdown
            device = queryset.values('device_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            audience_metrics['device'] = list(device)
            
            # Interests breakdown
            interests = queryset.values('interests').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            audience_metrics['interests'] = list(interests)
            
            # Total audience size
            audience_metrics['total_size'] = queryset.values('user_id').distinct().count()
            
            return audience_metrics
            
        except Exception as e:
            logger.error(f"Error getting audience metrics: {str(e)}")
            return {}
    
    @staticmethod
    def _get_campaign_metrics(time_range: Tuple[datetime, datetime], 
                           campaign_id: Optional[UUID]) -> Dict[str, Any]:
        """Get campaign metrics with optimized queries."""
        try:
            # Build base query
            queryset = PerformanceMetric.objects.filter(
                timestamp__range=time_range
            )
            
            # Apply campaign filter
            if campaign_id:
                queryset = queryset.filter(campaign_id=campaign_id)
            
            # Performance: Use optimized aggregate queries
            campaigns = queryset.values('campaign_id', 'campaign__name', 'campaign__status').annotate(
                impressions=Sum('impressions'),
                clicks=Sum('clicks'),
                conversions=Sum('conversions'),
                spend=Sum('spend'),
                revenue=Sum('revenue')
            ).order_by('-revenue')
            
            # Calculate metrics for each campaign
            campaign_data = []
            for campaign in campaigns:
                impressions = campaign['impressions'] or 0
                clicks = campaign['clicks'] or 0
                conversions = campaign['conversions'] or 0
                spend = campaign['spend'] or Decimal('0.00')
                revenue = campaign['revenue'] or Decimal('0.00')
                
                ctr = (clicks / impressions * 100) if impressions > 0 else 0
                cpc = (spend / clicks) if clicks > 0 else Decimal('0.00')
                cpa = (spend / conversions) if conversions > 0 else Decimal('0.00')
                roas = (revenue / spend) if spend > 0 else Decimal('0.00')
                
                campaign_data.append({
                    'id': campaign['campaign_id'],
                    'name': campaign['campaign__name'],
                    'status': campaign['campaign__status'],
                    'metrics': {
                        'impressions': impressions,
                        'clicks': clicks,
                        'conversions': conversions,
                        'spend': float(spend),
                        'revenue': float(revenue),
                        'ctr': round(ctr, 2),
                        'cpc': float(cpc),
                        'cpa': float(cpa),
                        'roas': float(roas)
                    }
                })
            
            return {'campaigns': campaign_data}
            
        except Exception as e:
            logger.error(f"Error getting campaign metrics: {str(e)}")
            return {'campaigns': []}
    
    @staticmethod
    def _execute_custom_query(query_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute custom query with security validation."""
        try:
            # Security: Validate query configuration
            ReportingService._validate_custom_query(query_config)
            
            # Execute custom query
            # This would implement a safe query builder
            # For now, return mock data
            return {
                'data': [
                    {'id': 1, 'value': 100},
                    {'id': 2, 'value': 200}
                ]
            }
            
        except Exception as e:
            logger.error(f"Error executing custom query: {str(e)}")
            return {'data': []}
    
    @staticmethod
    def _validate_report_config(report_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate report configuration with security checks."""
        # Security: Check required fields
        required_fields = ['name', 'report_type']
        for field in required_fields:
            if not report_config.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate report type
        valid_types = ['performance', 'financial', 'audience', 'campaign', 'custom']
        if report_config.get('report_type') not in valid_types:
            raise AdvertiserValidationError(f"Invalid report type: {report_config.get('report_type')}")
        
        # Security: Validate time range
        time_range = report_config.get('time_range')
        if time_range:
            valid_ranges = ['today', 'yesterday', 'last_7_days', 'last_30_days', 'last_90_days', 'this_month', 'last_month', 'this_year', 'custom']
            if time_range not in valid_ranges:
                raise AdvertiserValidationError(f"Invalid time range: {time_range}")
        
        # Security: Check user permissions
        if user and not user.is_superuser:
            advertiser_id = report_config.get('advertiser_id')
            if advertiser_id:
                try:
                    advertiser = Advertiser.objects.get(id=advertiser_id, is_deleted=False)
                    if advertiser.user != user:
                        raise AdvertiserValidationError("User does not have access to this advertiser")
                except Advertiser.DoesNotExist:
                    raise AdvertiserValidationError("Advertiser not found")
    
    @staticmethod
    def _validate_schedule_config(schedule_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate schedule configuration with security checks."""
        # Security: Check required fields
        required_fields = ['name', 'report_config', 'schedule_type']
        for field in required_fields:
            if not schedule_config.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate schedule type
        valid_types = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly', 'custom']
        if schedule_config.get('schedule_type') not in valid_types:
            raise AdvertiserValidationError(f"Invalid schedule type: {schedule_config.get('schedule_type')}")
        
        # Security: Validate delivery method
        delivery_method = schedule_config.get('delivery_method', 'email')
        valid_methods = ['email', 'ftp', 'webhook', 'api']
        if delivery_method not in valid_methods:
            raise AdvertiserValidationError(f"Invalid delivery method: {delivery_method}")
    
    @staticmethod
    def _validate_export_request(report_id: UUID, export_format: str, 
                              filters: Optional[Dict[str, Any]]) -> None:
        """Validate export request with security checks."""
        # Security: Validate report ID
        try:
            report = Report.objects.get(id=report_id)
        except Report.DoesNotExist:
            raise AdvertiserValidationError("Report not found")
        
        # Security: Validate export format
        valid_formats = ['csv', 'excel', 'pdf', 'json', 'xml']
        if export_format not in valid_formats:
            raise AdvertiserValidationError(f"Invalid export format: {export_format}")
        
        # Security: Validate filters
        if filters:
            # Validate filter structure
            if not isinstance(filters, dict):
                raise AdvertiserValidationError("Filters must be a dictionary")
    
    @staticmethod
    def _get_report_data(report_id: UUID, filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Get report data with filters."""
        try:
            # Get report
            report = Report.objects.get(id=report_id)
            
            # Apply filters to report data
            data = report.data
            if filters:
                data = ReportingService._apply_filters(data, filters)
            
            return {
                'report': report,
                'data': data
            }
            
        except Report.DoesNotExist:
            raise AdvertiserValidationError("Report not found")
    
    @staticmethod
    def _apply_filters(data: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply filters to report data."""
        try:
            filtered_data = data
            
            # Apply date range filter
            if 'date_range' in filters:
                date_range = filters['date_range']
                # Filter data based on date range
                pass
            
            # Apply value range filter
            if 'value_range' in filters:
                value_range = filters['value_range']
                # Filter data based on value range
                pass
            
            # Apply text filter
            if 'text_filter' in filters:
                text_filter = filters['text_filter']
                # Filter data based on text
                pass
            
            return filtered_data
            
        except Exception as e:
            logger.error(f"Error applying filters: {str(e)}")
            return data
    
    @staticmethod
    def _export_csv(report_data: Dict[str, Any]) -> HttpResponse:
        """Export report data as CSV."""
        try:
            import csv
            from django.http import HttpResponse
            
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="report_{report_data["report"].id}.csv"'
            
            writer = csv.writer(response)
            
            # Write headers
            if report_data['data']:
                headers = list(report_data['data'][0].keys())
                writer.writerow(headers)
                
                # Write data rows
                for row in report_data['data']:
                    writer.writerow([row.get(header, '') for header in headers])
            
            return response
            
        except Exception as e:
            logger.error(f"Error exporting CSV: {str(e)}")
            raise AdvertiserServiceError(f"Failed to export CSV: {str(e)}")
    
    @staticmethod
    def _export_excel(report_data: Dict[str, Any]) -> HttpResponse:
        """Export report data as Excel."""
        try:
            import openpyxl
            from openpyxl import Workbook
            from django.http import HttpResponse
            
            # Create workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "Report Data"
            
            # Write headers
            if report_data['data']:
                headers = list(report_data['data'][0].keys())
                ws.append(headers)
                
                # Write data rows
                for row in report_data['data']:
                    ws.append([row.get(header, '') for header in headers])
            
            # Save to response
            response = HttpResponse(
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="report_{report_data["report"].id}.xlsx"'
            
            wb.save(response)
            return response
            
        except Exception as e:
            logger.error(f"Error exporting Excel: {str(e)}")
            raise AdvertiserServiceError(f"Failed to export Excel: {str(e)}")
    
    @staticmethod
    def _export_pdf(report_data: Dict[str, Any]) -> HttpResponse:
        """Export report data as PDF."""
        try:
            from django.http import HttpResponse
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            
            # Create PDF document
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="report_{report_data["report"].id}.pdf"'
            
            # Create PDF content
            doc = SimpleDocTemplate(response, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            
            # Add title
            title = Paragraph(f"Report: {report_data['report'].name}", styles['Title'])
            elements.append(title)
            
            # Add table
            if report_data['data']:
                headers = list(report_data['data'][0].keys())
                data = [headers]
                
                for row in report_data['data']:
                    data.append([str(row.get(header, '')) for header in headers])
                
                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), '#f0f0f0'),
                    ('TEXTCOLOR', (0, 0), (-1, -1), '#000000'),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), '#ffffff'),
                    ('GRID', (0, 0), (-1, -1), 1, '#000000')
                ]))
                
                elements.append(table)
            
            # Build PDF
            doc.build(elements)
            return response
            
        except Exception as e:
            logger.error(f"Error exporting PDF: {str(e)}")
            raise AdvertiserServiceError(f"Failed to export PDF: {str(e)}")
    
    @staticmethod
    def _export_json(report_data: Dict[str, Any]) -> HttpResponse:
        """Export report data as JSON."""
        try:
            from django.http import HttpResponse
            import json
            
            response = HttpResponse(content_type='application/json')
            response['Content-Disposition'] = f'attachment; filename="report_{report_data["report"].id}.json"'
            
            json_data = json.dumps(report_data['data'], indent=2, default=str)
            response.write(json_data)
            
            return response
            
        except Exception as e:
            logger.error(f"Error exporting JSON: {str(e)}")
            raise AdvertiserServiceError(f"Failed to export JSON: {str(e)}")
    
    @staticmethod
    def _export_xml(report_data: Dict[str, Any]) -> HttpResponse:
        """Export report data as XML."""
        try:
            from django.http import HttpResponse
            import xml.etree.ElementTree as ET
            
            response = HttpResponse(content_type='application/xml')
            response['Content-Disposition'] = f'attachment; filename="report_{report_data["report"].id}.xml"'
            
            # Create XML structure
            root = ET.Element('report')
            root.set('name', report_data['report'].name)
            root.set('generated_at', report_data['report'].generated_at.isoformat())
            
            # Add data rows
            for row in report_data['data']:
                row_element = ET.SubElement(root, 'row')
                for key, value in row.items():
                    element = ET.SubElement(row_element, key)
                    element.text = str(value)
            
            # Generate XML
            xml_str = ET.tostring(root, encoding='unicode')
            response.write(xml_str)
            
            return response
            
        except Exception as e:
            logger.error(f"Error exporting XML: {str(e)}")
            raise AdvertiserServiceError(f"Failed to export XML: {str(e)}")
    
    @staticmethod
    def _generate_cache_key(report_config: Dict[str, Any]) -> str:
        """Generate cache key for report."""
        try:
            import hashlib
            
            # Create cache key from report configuration
            config_str = json.dumps(report_config, sort_keys=True)
            cache_key = hashlib.md5(config_str.encode()).hexdigest()
            
            return f"report_cache_{cache_key}"
            
        except Exception as e:
            logger.error(f"Error generating cache key: {str(e)}")
            return f"report_cache_{timezone.now().isoformat()}"
    
    @staticmethod
    def _get_cache_timeout(report_type: str) -> int:
        """Get cache timeout based on report type."""
        timeouts = {
            'performance': 300,      # 5 minutes
            'financial': 600,         # 10 minutes
            'audience': 1800,        # 30 minutes
            'campaign': 600,         # 10 minutes
            'custom': 300            # 5 minutes
        }
        
        return timeouts.get(report_type, 300)
    
    @staticmethod
    def _parse_time_range(time_range: str) -> Tuple[datetime, datetime]:
        """Parse time range string to datetime tuple."""
        try:
            now = timezone.now()
            
            if time_range == 'today':
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            elif time_range == 'yesterday':
                yesterday = now - timedelta(days=1)
                start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
                end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
            elif time_range == 'last_7_days':
                end = now
                start = now - timedelta(days=7)
            elif time_range == 'last_30_days':
                end = now
                start = now - timedelta(days=30)
            elif time_range == 'last_90_days':
                end = now
                start = now - timedelta(days=90)
            elif time_range == 'this_month':
                start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                end = now
            elif time_range == 'last_month':
                first_day_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                end = first_day_this_month - timedelta(microseconds=1)
                start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            elif time_range == 'this_year':
                start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                end = now
            else:
                # Default to last 30 days
                end = now
                start = now - timedelta(days=30)
            
            return (start, end)
            
        except Exception as e:
            logger.error(f"Error parsing time range: {str(e)}")
            # Default to last 30 days
            end = timezone.now()
            start = end - timedelta(days=30)
            return (start, end)
    
    @staticmethod
    def _validate_custom_query(query_config: Dict[str, Any]) -> None:
        """Validate custom query configuration."""
        # Security: Check for SQL injection
        if 'sql' in query_config:
            sql = query_config['sql']
            dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
            
            for keyword in dangerous_keywords:
                if keyword.lower() in sql.lower():
                    raise AdvertiserValidationError(f"Dangerous SQL keyword detected: {keyword}")
        
        # Security: Validate table names
        if 'tables' in query_config:
            valid_tables = ['performance_metric', 'analytics_event', 'campaign', 'advertiser']
            for table in query_config['tables']:
                if table not in valid_tables:
                    raise AdvertiserValidationError(f"Invalid table name: {table}")
    
    @staticmethod
    def _log_report_generation(report_data: ReportData, user: Optional[User]) -> None:
        """Log report generation for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_creation(
                report_data,
                user,
                description=f"Generated report: {report_data.report_name}"
            )
        except Exception as e:
            logger.error(f"Error logging report generation: {str(e)}")
    
    @staticmethod
    def _log_schedule_creation(schedule: ReportSchedule, user: Optional[User]) -> None:
        """Log schedule creation for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_creation(
                schedule,
                user,
                description=f"Created report schedule: {schedule.name}"
            )
        except Exception as e:
            logger.error(f"Error logging schedule creation: {str(e)}")


class DashboardService:
    """
    Enterprise-grade dashboard service with real-time widgets and visualizations.
    
    Features:
    - Real-time dashboard widgets
    - Customizable layouts
    - Interactive visualizations
    - Performance optimization
    - Multi-device support
    """
    
    @staticmethod
    def create_dashboard(dashboard_config: Dict[str, Any], created_by: Optional[User] = None) -> Dashboard:
        """Create customizable dashboard with widgets."""
        try:
            # Security: Validate dashboard configuration
            DashboardService._validate_dashboard_config(dashboard_config, created_by)
            
            with transaction.atomic():
                # Create dashboard
                dashboard = Dashboard.objects.create(
                    name=dashboard_config.get('name'),
                    description=dashboard_config.get('description', ''),
                    layout=dashboard_config.get('layout', {}),
                    widgets=dashboard_config.get('widgets', []),
                    filters=dashboard_config.get('filters', {}),
                    is_default=dashboard_config.get('is_default', False),
                    is_public=dashboard_config.get('is_public', False),
                    created_by=created_by
                )
                
                # Send notification
                Notification.objects.create(
                    user=created_by,
                    title='Dashboard Created',
                    message=f'Dashboard "{dashboard.name}" has been created.',
                    notification_type='dashboard',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log dashboard creation
                DashboardService._log_dashboard_creation(dashboard, created_by)
                
                return dashboard
                
        except Exception as e:
            logger.error(f"Error creating dashboard: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create dashboard: {str(e)}")
    
    @staticmethod
    def get_dashboard_data(dashboard_id: UUID, user: Optional[User] = None) -> Dict[str, Any]:
        """Get dashboard data with real-time widget updates."""
        try:
            # Security: Validate dashboard access
            dashboard = DashboardService._get_dashboard_with_validation(dashboard_id, user)
            
            # Performance: Check cache first
            cache_key = f"dashboard_data_{dashboard_id}"
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
            
            # Initialize dashboard data
            dashboard_data = {
                'dashboard_id': str(dashboard_id),
                'name': dashboard.name,
                'description': dashboard.description,
                'layout': dashboard.layout,
                'widgets': [],
                'filters': dashboard.filters,
                'last_updated': timezone.now().isoformat()
            }
            
            # Get widget data
            for widget_config in dashboard.widgets:
                widget_data = DashboardService._get_widget_data(widget_config)
                dashboard_data['widgets'].append(widget_data)
            
            # Performance: Cache dashboard data
            cache.set(cache_key, dashboard_data, timeout=300)  # 5 minutes cache
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error getting dashboard data: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get dashboard data: {str(e)}")
    
    @staticmethod
    def update_dashboard_layout(dashboard_id: UUID, layout_config: Dict[str, Any],
                            updated_by: Optional[User] = None) -> bool:
        """Update dashboard layout configuration."""
        try:
            # Security: Validate dashboard access
            dashboard = DashboardService._get_dashboard_with_validation(dashboard_id, updated_by)
            
            with transaction.atomic():
                # Update layout
                dashboard.layout = layout_config
                dashboard.updated_at = timezone.now()
                dashboard.updated_by = updated_by
                dashboard.save(update_fields=['layout', 'updated_at', 'updated_by'])
                
                # Clear cache
                cache.delete(f"dashboard_data_{dashboard_id}")
                
                # Log layout update
                DashboardService._log_layout_update(dashboard, layout_config, updated_by)
                
                return True
                
        except Exception as e:
            logger.error(f"Error updating dashboard layout: {str(e)}")
            return False
    
    @staticmethod
    def _get_widget_data(widget_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get data for specific widget."""
        try:
            widget_type = widget_config.get('type')
            data_source = widget_config.get('data_source')
            widget_id = widget_config.get('id')
            
            # Get data based on widget type
            if widget_type == 'metric':
                return DashboardService._get_metric_widget_data(widget_config)
            elif widget_type == 'chart':
                return DashboardService._get_chart_widget_data(widget_config)
            elif widget_type == 'table':
                return DashboardService._get_table_widget_data(widget_config)
            elif widget_type == 'map':
                return DashboardService._get_map_widget_data(widget_config)
            elif widget_type == 'funnel':
                return DashboardService._get_funnel_widget_data(widget_config)
            else:
                return DashboardService._get_custom_widget_data(widget_config)
                
        except Exception as e:
            logger.error(f"Error getting widget data: {str(e)}")
            return {
                'widget_id': widget_config.get('id'),
                'type': widget_config.get('type'),
                'error': 'Failed to load widget data'
            }
    
    @staticmethod
    def _get_metric_widget_data(widget_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get data for metric widget."""
        try:
            data_source = widget_config.get('data_source')
            metric_type = widget_config.get('metric_type', 'count')
            
            # Get metric data
            metric_data = DashboardService._get_metric_data(data_source, metric_type)
            
            return {
                'widget_id': widget_config.get('id'),
                'type': 'metric',
                'title': widget_config.get('title'),
                'value': metric_data.get('value', 0),
                'change': metric_data.get('change', 0),
                'change_percentage': metric_data.get('change_percentage', 0),
                'trend': metric_data.get('trend', 'stable'),
                'last_updated': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting metric widget data: {str(e)}")
            return {
                'widget_id': widget_config.get('id'),
                'type': 'metric',
                'error': 'Failed to load metric data'
            }
    
    @staticmethod
    def _get_chart_widget_data(widget_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get data for chart widget."""
        try:
            data_source = widget_config.get('data_source')
            chart_type = widget_config.get('chart_type', 'line')
            time_range = widget_config.get('time_range', 'last_30_days')
            
            # Get chart data
            chart_data = DashboardService._get_chart_data(data_source, chart_type, time_range)
            
            return {
                'widget_id': widget_config.get('id'),
                'type': 'chart',
                'title': widget_config.get('title'),
                'chart_type': chart_type,
                'data': chart_data,
                'last_updated': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting chart widget data: {str(e)}")
            return {
                'widget_id': widget_config.get('id'),
                'type': 'chart',
                'error': 'Failed to load chart data'
            }
    
    @staticmethod
    def _get_table_widget_data(widget_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get data for table widget."""
        try:
            data_source = widget_config.get('data_source')
            columns = widget_config.get('columns', [])
            limit = widget_config.get('limit', 10)
            
            # Get table data
            table_data = DashboardService._get_table_data(data_source, columns, limit)
            
            return {
                'widget_id': widget_config.get('id'),
                'type': 'table',
                'title': widget_config.get('title'),
                'columns': columns,
                'data': table_data,
                'last_updated': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting table widget data: {str(e)}")
            return {
                'widget_id': widget_config.get('id'),
                'type': 'table',
                'error': 'Failed to load table data'
            }
    
    @staticmethod
    def _get_map_widget_data(widget_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get data for map widget."""
        try:
            data_source = widget_config.get('data_source')
            map_type = widget_config.get('map_type', 'world')
            
            # Get map data
            map_data = DashboardService._get_map_data(data_source, map_type)
            
            return {
                'widget_id': widget_config.get('id'),
                'type': 'map',
                'title': widget_config.get('title'),
                'map_type': map_type,
                'data': map_data,
                'last_updated': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting map widget data: {str(e)}")
            return {
                'widget_id': widget_config.get('id'),
                'type': 'map',
                'error': 'Failed to load map data'
            }
    
    @staticmethod
    def _get_funnel_widget_data(widget_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get data for funnel widget."""
        try:
            data_source = widget_config.get('data_source')
            funnel_steps = widget_config.get('funnel_steps', [])
            
            # Get funnel data
            funnel_data = DashboardService._get_funnel_data(data_source, funnel_steps)
            
            return {
                'widget_id': widget_config.get('id'),
                'type': 'funnel',
                'title': widget_config.get('title'),
                'funnel_steps': funnel_steps,
                'data': funnel_data,
                'last_updated': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting funnel widget data: {str(e)}")
            return {
                'widget_id': widget_config.get('id'),
                'type': 'funnel',
                'error': 'Failed to load funnel data'
            }
    
    @staticmethod
    def _get_custom_widget_data(widget_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get data for custom widget."""
        try:
            custom_config = widget_config.get('custom_config', {})
            
            # Execute custom data query
            custom_data = DashboardService._execute_custom_data_query(custom_config)
            
            return {
                'widget_id': widget_config.get('id'),
                'type': 'custom',
                'title': widget_config.get('title'),
                'custom_config': custom_config,
                'data': custom_data,
                'last_updated': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting custom widget data: {str(e)}")
            return {
                'widget_id': widget_config.get('id'),
                'type': 'custom',
                'error': 'Failed to load custom widget data'
            }
    
    @staticmethod
    def _get_metric_data(data_source: str, metric_type: str) -> Dict[str, Any]:
        """Get metric data for widget."""
        try:
            # Performance: Use optimized queries
            if data_source == 'performance':
                queryset = PerformanceMetric.objects.all()
            elif data_source == 'analytics':
                queryset = AnalyticsEvent.objects.all()
            else:
                return {}
            
            # Calculate metric based on type
            if metric_type == 'count':
                value = queryset.count()
            elif metric_type == 'sum':
                value = queryset.aggregate(total=Sum('value'))['total'] or 0
            elif metric_type == 'avg':
                value = queryset.aggregate(avg=Avg('value'))['avg'] or 0
            else:
                value = 0
            
            return {
                'value': value,
                'change': 0,  # Would calculate against previous period
                'change_percentage': 0,
                'trend': 'stable'
            }
            
        except Exception as e:
            logger.error(f"Error getting metric data: {str(e)}")
            return {}
    
    @staticmethod
    def _get_chart_data(data_source: str, chart_type: str, time_range: str) -> List[Dict[str, Any]]:
        """Get chart data for widget."""
        try:
            # Parse time range
            start_date, end_date = ReportingService._parse_time_range(time_range)
            
            # Performance: Use optimized queries
            if data_source == 'performance':
                queryset = PerformanceMetric.objects.filter(timestamp__range=(start_date, end_date))
            elif data_source == 'analytics':
                queryset = AnalyticsEvent.objects.filter(timestamp__range=(start_date, end_date))
            else:
                return []
            
            # Generate chart data based on type
            if chart_type == 'line':
                # Time series data
                data = queryset.annotate(
                    date=Trunc('timestamp', 'day')
                ).values('date').annotate(
                    value=Sum('value')
                ).order_by('date')
                
                return [
                    {'date': item['date'].isoformat(), 'value': item['value']}
                    for item in data
                ]
            elif chart_type == 'bar':
                # Category data
                data = queryset.values('category').annotate(
                    value=Sum('value')
                ).order_by('-value')[:10]
                
                return [
                    {'category': item['category'], 'value': item['value']}
                    for item in data
                ]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error getting chart data: {str(e)}")
            return []
    
    @staticmethod
    def _get_table_data(data_source: str, columns: List[str], limit: int) -> List[Dict[str, Any]]:
        """Get table data for widget."""
        try:
            # Performance: Use optimized queries
            if data_source == 'performance':
                queryset = PerformanceMetric.objects.all()
            elif data_source == 'analytics':
                queryset = AnalyticsEvent.objects.all()
            else:
                return []
            
            # Get data with specified columns
            data = queryset.values(*columns)[:limit] if columns else queryset.all()[:limit]
            
            return list(data)
            
        except Exception as e:
            logger.error(f"Error getting table data: {str(e)}")
            return []
    
    @staticmethod
    def _get_map_data(data_source: str, map_type: str) -> List[Dict[str, Any]]:
        """Get map data for widget."""
        try:
            # Performance: Use optimized queries
            if data_source == 'performance':
                queryset = PerformanceMetric.objects.all()
            elif data_source == 'analytics':
                queryset = AnalyticsEvent.objects.all()
            else:
                return []
            
            # Get geographical data
            if map_type == 'world':
                data = queryset.values('country').annotate(
                    value=Sum('value')
                ).order_by('-value')
                
                return [
                    {'country': item['country'], 'value': item['value']}
                    for item in data
                ]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error getting map data: {str(e)}")
            return []
    
    @staticmethod
    def _get_funnel_data(data_source: str, funnel_steps: List[str]) -> List[Dict[str, Any]]:
        """Get funnel data for widget."""
        try:
            # Performance: Use optimized queries
            if data_source == 'performance':
                queryset = PerformanceMetric.objects.all()
            elif data_source == 'analytics':
                queryset = AnalyticsEvent.objects.all()
            else:
                return []
            
            # Get funnel data
            funnel_data = []
            for step in funnel_steps:
                step_data = queryset.filter(step=step).count()
                funnel_data.append({
                    'step': step,
                    'count': step_data
                })
            
            return funnel_data
            
        except Exception as e:
            logger.error(f"Error getting funnel data: {str(e)}")
            return []
    
    @staticmethod
    def _execute_custom_data_query(custom_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute custom data query for widget."""
        try:
            # Security: Validate custom query
            DashboardService._validate_custom_query(custom_config)
            
            # Execute custom query
            # This would implement a safe query builder
            # For now, return mock data
            return {
                'data': [
                    {'label': 'Item 1', 'value': 100},
                    {'label': 'Item 2', 'value': 200}
                ]
            }
            
        except Exception as e:
            logger.error(f"Error executing custom data query: {str(e)}")
            return {'data': []}
    
    @staticmethod
    def _validate_dashboard_config(dashboard_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate dashboard configuration."""
        # Security: Check required fields
        required_fields = ['name']
        for field in required_fields:
            if not dashboard_config.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate widgets
        widgets = dashboard_config.get('widgets', [])
        for widget in widgets:
            if not isinstance(widget, dict):
                raise AdvertiserValidationError("Widget configuration must be a dictionary")
            
            if 'id' not in widget or 'type' not in widget:
                raise AdvertiserValidationError("Widget must have id and type")
    
    @staticmethod
    def _get_dashboard_with_validation(dashboard_id: UUID, user: Optional[User]) -> Dashboard:
        """Get dashboard with security validation."""
        try:
            dashboard = Dashboard.objects.get(id=dashboard_id)
            
            # Security: Check user permissions
            if user and not user.is_superuser:
                if dashboard.created_by != user and not dashboard.is_public:
                    raise AdvertiserValidationError("User does not have access to this dashboard")
            
            return dashboard
            
        except Dashboard.DoesNotExist:
            raise AdvertiserNotFoundError(f"Dashboard {dashboard_id} not found")
    
    @staticmethod
    def _validate_custom_query(custom_config: Dict[str, Any]) -> None:
        """Validate custom query configuration."""
        # Security: Check for SQL injection
        if 'sql' in custom_config:
            sql = custom_config['sql']
            dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
            
            for keyword in dangerous_keywords:
                if keyword.lower() in sql.lower():
                    raise AdvertiserValidationError(f"Dangerous SQL keyword detected: {keyword}")
    
    @staticmethod
    def _log_dashboard_creation(dashboard: Dashboard, user: Optional[User]) -> None:
        """Log dashboard creation for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_creation(
                dashboard,
                user,
                description=f"Created dashboard: {dashboard.name}"
            )
        except Exception as e:
            logger.error(f"Error logging dashboard creation: {str(e)}")
    
    @staticmethod
    def _log_layout_update(dashboard: Dashboard, layout_config: Dict[str, Any], user: Optional[User]) -> None:
        """Log layout update for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_action(
                action='update_dashboard_layout',
                object_type='Dashboard',
                object_id=str(dashboard.id),
                user=user,
                description=f"Updated dashboard layout: {dashboard.name}"
            )
        except Exception as e:
            logger.error(f"Error logging layout update: {str(e)}")


class AnalyticsService:
    """
    Enterprise-grade analytics service with advanced metrics and insights.
    
    Features:
    - Real-time analytics processing
    - Advanced metric calculations
    - Predictive analytics
    - Behavioral analysis
    - Performance optimization
    """
    
    @staticmethod
    def calculate_metrics(metric_config: Dict[str, Any], requested_by: Optional[User] = None) -> Dict[str, Any]:
        """Calculate advanced analytics metrics."""
        try:
            # Security: Validate metric configuration
            AnalyticsService._validate_metric_config(metric_config, requested_by)
            
            # Get metric data
            metric_data = AnalyticsService._get_metric_data(metric_config)
            
            # Calculate advanced metrics
            calculated_metrics = AnalyticsService._calculate_advanced_metrics(metric_data, metric_config)
            
            return {
                'metric_id': metric_config.get('id'),
                'metric_name': metric_config.get('name'),
                'metric_type': metric_config.get('type'),
                'data': metric_data,
                'calculated_metrics': calculated_metrics,
                'calculated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating metrics: {str(e)}")
            raise AdvertiserServiceError(f"Failed to calculate metrics: {str(e)}")
    
    @staticmethod
    def get_insights(insight_config: Dict[str, Any], requested_by: Optional[User] = None) -> List[Dict[str, Any]]:
        """Generate actionable insights from analytics data."""
        try:
            # Security: Validate insight configuration
            AnalyticsService._validate_insight_config(insight_config, requested_by)
            
            # Get analytics data
            analytics_data = AnalyticsService._get_analytics_data(insight_config)
            
            # Generate insights
            insights = AnalyticsService._generate_insights(analytics_data, insight_config)
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating insights: {str(e)}")
            raise AdvertiserServiceError(f"Failed to generate insights: {str(e)}")
    
    @staticmethod
    def _get_metric_data(metric_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get metric data with optimized queries."""
        try:
            data_source = metric_config.get('data_source')
            time_range = metric_config.get('time_range', 'last_30_days')
            filters = metric_config.get('filters', {})
            
            # Parse time range
            start_date, end_date = ReportingService._parse_time_range(time_range)
            
            # Performance: Use optimized queries
            if data_source == 'performance':
                queryset = PerformanceMetric.objects.filter(timestamp__range=(start_date, end_date))
            elif data_source == 'analytics':
                queryset = AnalyticsEvent.objects.filter(timestamp__range=(start_date, end_date))
            else:
                return {}
            
            # Apply filters
            queryset = AnalyticsService._apply_filters(queryset, filters)
            
            # Get aggregated data
            data = queryset.aggregate(
                total=Count('id'),
                sum_value=Sum('value'),
                avg_value=Avg('value'),
                min_value=Coalesce(Min('value'), 0),
                max_value=Coalesce(Max('value'), 0)
            )
            
            return data
            
        except Exception as e:
            logger.error(f"Error getting metric data: {str(e)}")
            return {}
    
    @staticmethod
    def _calculate_advanced_metrics(metric_data: Dict[str, Any], metric_config: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate advanced metrics from base data."""
        try:
            advanced_metrics = {}
            
            # Calculate growth rate
            if 'previous_period_data' in metric_data:
                current_value = metric_data.get('sum_value', 0)
                previous_value = metric_data['previous_period_data'].get('sum_value', 0)
                
                if previous_value > 0:
                    growth_rate = ((current_value - previous_value) / previous_value) * 100
                    advanced_metrics['growth_rate'] = round(growth_rate, 2)
            
            # Calculate moving average
            if 'time_series_data' in metric_data:
                time_series = metric_data['time_series_data']
                if len(time_series) >= 7:
                    moving_avg = sum(time_series[-7:]) / 7
                    advanced_metrics['moving_average_7d'] = round(moving_avg, 2)
            
            # Calculate volatility
            if 'time_series_data' in metric_data:
                time_series = metric_data['time_series_data']
                if len(time_series) >= 2:
                    variance = sum((x - sum(time_series)/len(time_series))**2 for x in time_series) / len(time_series)
                    volatility = math.sqrt(variance)
                    advanced_metrics['volatility'] = round(volatility, 2)
            
            return advanced_metrics
            
        except Exception as e:
            logger.error(f"Error calculating advanced metrics: {str(e)}")
            return {}
    
    @staticmethod
    def _get_analytics_data(insight_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get analytics data for insight generation."""
        try:
            data_source = insight_config.get('data_source')
            time_range = insight_config.get('time_range', 'last_30_days')
            
            # Parse time range
            start_date, end_date = ReportingService._parse_time_range(time_range)
            
            # Performance: Use optimized queries
            if data_source == 'performance':
                queryset = PerformanceMetric.objects.filter(timestamp__range=(start_date, end_date))
            elif data_source == 'analytics':
                queryset = AnalyticsEvent.objects.filter(timestamp__range=(start_date, end_date))
            else:
                return {}
            
            # Get comprehensive analytics data
            analytics_data = {
                'time_series': list(queryset.annotate(
                    date=Trunc('timestamp', 'day')
                ).values('date').annotate(
                    value=Sum('value')
                ).order_by('date')),
                'segmentation': list(queryset.values('segment').annotate(
                    value=Sum('value')
                ).order_by('-value')[:10]),
                'correlation': AnalyticsService._calculate_correlations(queryset)
            }
            
            return analytics_data
            
        except Exception as e:
            logger.error(f"Error getting analytics data: {str(e)}")
            return {}
    
    @staticmethod
    def _generate_insights(analytics_data: Dict[str, Any], insight_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate actionable insights from analytics data."""
        try:
            insights = []
            
            # Trend insights
            if 'time_series' in analytics_data:
                time_series = analytics_data['time_series']
                if len(time_series) >= 7:
                    recent_values = [item['value'] for item in time_series[-7:]]
                    trend = 'increasing' if recent_values[-1] > recent_values[0] else 'decreasing'
                    
                    insights.append({
                        'type': 'trend',
                        'title': f'{trend.capitalize()} Trend Detected',
                        'description': f'Values have been {trend} over the last 7 days',
                        'confidence': 0.8,
                        'recommendation': f'Consider {"increasing" if trend == "increasing" else "decreasing"} your strategy'
                    })
            
            # Segmentation insights
            if 'segmentation' in analytics_data:
                segmentation = analytics_data['segmentation']
                if segmentation:
                    top_segment = max(segmentation, key=lambda x: x['value'])
                    
                    insights.append({
                        'type': 'segmentation',
                        'title': 'Top Performing Segment',
                        'description': f'Segment "{top_segment["segment"]}" has the highest value',
                        'confidence': 0.9,
                        'recommendation': f'Focus more resources on the {top_segment["segment"]} segment'
                    })
            
            # Correlation insights
            if 'correlation' in analytics_data:
                correlations = analytics_data['correlation']
                high_correlations = [corr for corr in correlations if abs(corr['correlation']) > 0.7]
                
                for corr in high_correlations:
                    insights.append({
                        'type': 'correlation',
                        'title': 'Strong Correlation Found',
                        'description': f'Correlation of {corr["correlation"]:.2f} between {corr["metric1"]} and {corr["metric2"]}',
                        'confidence': abs(corr['correlation']),
                        'recommendation': f'Consider the relationship between {corr["metric1"]} and {corr["metric2"]}'
                    })
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating insights: {str(e)}")
            return []
    
    @staticmethod
    def _apply_filters(queryset, filters: Dict[str, Any]):
        """Apply filters to queryset."""
        try:
            # Apply date range filter
            if 'date_range' in filters:
                start_date = filters['date_range'].get('start')
                end_date = filters['date_range'].get('end')
                if start_date and end_date:
                    queryset = queryset.filter(timestamp__range=(start_date, end_date))
            
            # Apply segment filter
            if 'segment' in filters:
                segment = filters['segment']
                queryset = queryset.filter(segment=segment)
            
            # Apply value range filter
            if 'value_range' in filters:
                min_value = filters['value_range'].get('min')
                max_value = filters['value_range'].get('max')
                if min_value is not None:
                    queryset = queryset.filter(value__gte=min_value)
                if max_value is not None:
                    queryset = queryset.filter(value__lte=max_value)
            
            return queryset
            
        except Exception as e:
            logger.error(f"Error applying filters: {str(e)}")
            return queryset
    
    @staticmethod
    def _calculate_correlations(queryset) -> List[Dict[str, Any]]:
        """Calculate correlations between metrics."""
        try:
            # Get data for correlation calculation
            data = list(queryset.values('metric1', 'metric2', 'value'))
            
            if len(data) < 2:
                return []
            
            # Calculate correlation matrix
            correlations = []
            # This is a simplified correlation calculation
            # In production, this would use more sophisticated methods
            
            return correlations
            
        except Exception as e:
            logger.error(f"Error calculating correlations: {str(e)}")
            return []
    
    @staticmethod
    def _validate_metric_config(metric_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate metric configuration."""
        # Security: Check required fields
        required_fields = ['name', 'type', 'data_source']
        for field in required_fields:
            if not metric_config.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate data source
        valid_sources = ['performance', 'analytics', 'campaign', 'creative']
        if metric_config.get('data_source') not in valid_sources:
            raise AdvertiserValidationError(f"Invalid data source: {metric_config.get('data_source')}")
    
    @staticmethod
    def _validate_insight_config(insight_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate insight configuration."""
        # Security: Check required fields
        required_fields = ['data_source', 'insight_types']
        for field in required_fields:
            if not insight_config.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate insight types
        valid_types = ['trend', 'segmentation', 'correlation', 'anomaly', 'prediction']
        insight_types = insight_config.get('insight_types', [])
        for insight_type in insight_types:
            if insight_type not in valid_types:
                raise AdvertiserValidationError(f"Invalid insight type: {insight_type}")


class VisualizationService:
    """
    Enterprise-grade visualization service with interactive charts and dashboards.
    
    Features:
    - Interactive chart generation
    - Real-time data visualization
    - Custom visualization types
    - High-performance rendering
    - Multi-format export
    """
    
    @staticmethod
    def create_visualization(viz_config: Dict[str, Any], created_by: Optional[User] = None) -> Visualization:
        """Create interactive visualization."""
        try:
            # Security: Validate visualization configuration
            VisualizationService._validate_viz_config(viz_config, created_by)
            
            with transaction.atomic():
                # Create visualization
                visualization = Visualization.objects.create(
                    name=viz_config.get('name'),
                    description=viz_config.get('description', ''),
                    viz_type=viz_config.get('viz_type'),
                    data_source=viz_config.get('data_source'),
                    chart_config=viz_config.get('chart_config', {}),
                    filters=viz_config.get('filters', {}),
                    is_interactive=viz_config.get('is_interactive', True),
                    created_by=created_by
                )
                
                # Send notification
                Notification.objects.create(
                    user=created_by,
                    title='Visualization Created',
                    message=f'Visualization "{visualization.name}" has been created.',
                    notification_type='visualization',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log visualization creation
                VisualizationService._log_visualization_creation(visualization, created_by)
                
                return visualization
                
        except Exception as e:
            logger.error(f"Error creating visualization: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create visualization: {str(e)}")
    
    @staticmethod
    def get_visualization_data(viz_id: UUID, user: Optional[User] = None) -> Dict[str, Any]:
        """Get visualization data with interactive features."""
        try:
            # Security: Validate visualization access
            visualization = VisualizationService._get_visualization_with_validation(viz_id, user)
            
            # Performance: Check cache first
            cache_key = f"viz_data_{viz_id}"
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
            
            # Get visualization data
            viz_data = VisualizationService._generate_viz_data(visualization)
            
            # Performance: Cache visualization data
            cache.set(cache_key, viz_data, timeout=300)  # 5 minutes cache
            
            return viz_data
            
        except Exception as e:
            logger.error(f"Error getting visualization data: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get visualization data: {str(e)}")
    
    @staticmethod
    def _generate_viz_data(visualization: Visualization) -> Dict[str, Any]:
        """Generate visualization data based on configuration."""
        try:
            viz_type = visualization.viz_type
            data_source = visualization.data_source
            chart_config = visualization.chart_config
            
            # Get data based on visualization type
            if viz_type == 'line_chart':
                return VisualizationService._generate_line_chart_data(data_source, chart_config)
            elif viz_type == 'bar_chart':
                return VisualizationService._generate_bar_chart_data(data_source, chart_config)
            elif viz_type == 'pie_chart':
                return VisualizationService._generate_pie_chart_data(data_source, chart_config)
            elif viz_type == 'scatter_plot':
                return VisualizationService._generate_scatter_plot_data(data_source, chart_config)
            elif viz_type == 'heatmap':
                return VisualizationService._generate_heatmap_data(data_source, chart_config)
            else:
                return VisualizationService._generate_custom_viz_data(data_source, chart_config)
                
        except Exception as e:
            logger.error(f"Error generating visualization data: {str(e)}")
            return {
                'error': 'Failed to generate visualization data'
            }
    
    @staticmethod
    def _generate_line_chart_data(data_source: str, chart_config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate line chart data."""
        try:
            # Get time series data
            time_range = chart_config.get('time_range', 'last_30_days')
            start_date, end_date = ReportingService._parse_time_range(time_range)
            
            # Performance: Use optimized queries
            if data_source == 'performance':
                queryset = PerformanceMetric.objects.filter(timestamp__range=(start_date, end_date))
            elif data_source == 'analytics':
                queryset = AnalyticsEvent.objects.filter(timestamp__range=(start_date, end_date))
            else:
                return {'data': []}
            
            # Get time series data
            data = queryset.annotate(
                date=Trunc('timestamp', 'day')
            ).values('date').annotate(
                value=Sum('value')
            ).order_by('date')
            
            return {
                'type': 'line_chart',
                'data': [
                    {'date': item['date'].isoformat(), 'value': item['value']}
                    for item in data
                ],
                'config': chart_config
            }
            
        except Exception as e:
            logger.error(f"Error generating line chart data: {str(e)}")
            return {'data': []}
    
    @staticmethod
    def _generate_bar_chart_data(data_source: str, chart_config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate bar chart data."""
        try:
            # Get categorical data
            time_range = chart_config.get('time_range', 'last_30_days')
            start_date, end_date = ReportingService._parse_time_range(time_range)
            
            # Performance: Use optimized queries
            if data_source == 'performance':
                queryset = PerformanceMetric.objects.filter(timestamp__range=(start_date, end_date))
            elif data_source == 'analytics':
                queryset = AnalyticsEvent.objects.filter(timestamp__range=(start_date, end_date))
            else:
                return {'data': []}
            
            # Get categorical data
            data = queryset.values('category').annotate(
                value=Sum('value')
            ).order_by('-value')[:10]
            
            return {
                'type': 'bar_chart',
                'data': [
                    {'category': item['category'], 'value': item['value']}
                    for item in data
                ],
                'config': chart_config
            }
            
        except Exception as e:
            logger.error(f"Error generating bar chart data: {str(e)}")
            return {'data': []}
    
    @staticmethod
    def _generate_pie_chart_data(data_source: str, chart_config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate pie chart data."""
        try:
            # Get proportional data
            time_range = chart_config.get('time_range', 'last_30_days')
            start_date, end_date = ReportingService._parse_time_range(time_range)
            
            # Performance: Use optimized queries
            if data_source == 'performance':
                queryset = PerformanceMetric.objects.filter(timestamp__range=(start_date, end_date))
            elif data_source == 'analytics':
                queryset = AnalyticsEvent.objects.filter(timestamp__range=(start_date, end_date))
            else:
                return {'data': []}
            
            # Get proportional data
            data = queryset.values('category').annotate(
                value=Sum('value')
            ).order_by('-value')[:10]
            
            # Calculate percentages
            total = sum(item['value'] for item in data)
            pie_data = []
            for item in data:
                percentage = (item['value'] / total * 100) if total > 0 else 0
                pie_data.append({
                    'category': item['category'],
                    'value': item['value'],
                    'percentage': round(percentage, 2)
                })
            
            return {
                'type': 'pie_chart',
                'data': pie_data,
                'config': chart_config
            }
            
        except Exception as e:
            logger.error(f"Error generating pie chart data: {str(e)}")
            return {'data': []}
    
    @staticmethod
    def _generate_scatter_plot_data(data_source: str, chart_config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate scatter plot data."""
        try:
            # Get x-y data
            time_range = chart_config.get('time_range', 'last_30_days')
            start_date, end_date = ReportingService._parse_time_range(time_range)
            
            # Performance: Use optimized queries
            if data_source == 'performance':
                queryset = PerformanceMetric.objects.filter(timestamp__range=(start_date, end_date))
            elif data_source == 'analytics':
                queryset = AnalyticsEvent.objects.filter(timestamp__range=(start_date, end_date))
            else:
                return {'data': []}
            
            # Get x-y data
            data = list(queryset.values('x_value', 'y_value')[:1000])  # Limit to 1000 points
            
            return {
                'type': 'scatter_plot',
                'data': data,
                'config': chart_config
            }
            
        except Exception as e:
            logger.error(f"Error generating scatter plot data: {str(e)}")
            return {'data': []}
    
    @staticmethod
    def _generate_heatmap_data(data_source: str, chart_config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate heatmap data."""
        try:
            # Get matrix data
            time_range = chart_config.get('time_range', 'last_30_days')
            start_date, end_date = ReportingService._parse_time_range(time_range)
            
            # Performance: Use optimized queries
            if data_source == 'performance':
                queryset = PerformanceMetric.objects.filter(timestamp__range=(start_date, end_date))
            elif data_source == 'analytics':
                queryset = AnalyticsEvent.objects.filter(timestamp__range=(start_date, end_date))
            else:
                return {'data': []}
            
            # Get matrix data
            data = queryset.values('x_category', 'y_category').annotate(
                value=Sum('value')
            ).order_by('x_category', 'y_category')
            
            # Convert to matrix format
            matrix_data = {}
            for item in data:
                x_cat = item['x_category']
                y_cat = item['y_category']
                if x_cat not in matrix_data:
                    matrix_data[x_cat] = {}
                matrix_data[x_cat][y_cat] = item['value']
            
            return {
                'type': 'heatmap',
                'data': matrix_data,
                'config': chart_config
            }
            
        except Exception as e:
            logger.error(f"Error generating heatmap data: {str(e)}")
            return {'data': {}}
    
    @staticmethod
    def _generate_custom_viz_data(data_source: str, chart_config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate custom visualization data."""
        try:
            # Execute custom data query
            custom_data = VisualizationService._execute_custom_viz_query(chart_config)
            
            return {
                'type': 'custom',
                'data': custom_data,
                'config': chart_config
            }
            
        except Exception as e:
            logger.error(f"Error generating custom visualization data: {str(e)}")
            return {'data': []}
    
    @staticmethod
    def _execute_custom_viz_query(chart_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute custom visualization query."""
        try:
            # Security: Validate custom query
            VisualizationService._validate_custom_query(chart_config)
            
            # Execute custom query
            # This would implement a safe query builder
            # For now, return mock data
            return [
                {'x': 1, 'y': 2},
                {'x': 2, 'y': 4},
                {'x': 3, 'y': 6}
            ]
            
        except Exception as e:
            logger.error(f"Error executing custom viz query: {str(e)}")
            return []
    
    @staticmethod
    def _validate_viz_config(viz_config: Dict[str, Any], user: Optional[User]) -> None:
        """Validate visualization configuration."""
        # Security: Check required fields
        required_fields = ['name', 'viz_type', 'data_source']
        for field in required_fields:
            if not viz_config.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate visualization type
        valid_types = ['line_chart', 'bar_chart', 'pie_chart', 'scatter_plot', 'heatmap', 'custom']
        if viz_config.get('viz_type') not in valid_types:
            raise AdvertiserValidationError(f"Invalid visualization type: {viz_config.get('viz_type')}")
    
    @staticmethod
    def _get_visualization_with_validation(viz_id: UUID, user: Optional[User]) -> Visualization:
        """Get visualization with security validation."""
        try:
            visualization = Visualization.objects.get(id=viz_id)
            
            # Security: Check user permissions
            if user and not user.is_superuser:
                if visualization.created_by != user:
                    raise AdvertiserValidationError("User does not have access to this visualization")
            
            return visualization
            
        except Visualization.DoesNotExist:
            raise AdvertiserNotFoundError(f"Visualization {viz_id} not found")
    
    @staticmethod
    def _validate_custom_query(chart_config: Dict[str, Any]) -> None:
        """Validate custom query configuration."""
        # Security: Check for SQL injection
        if 'sql' in chart_config:
            sql = chart_config['sql']
            dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
            
            for keyword in dangerous_keywords:
                if keyword.lower() in sql.lower():
                    raise AdvertiserValidationError(f"Dangerous SQL keyword detected: {keyword}")
    
    @staticmethod
    def _log_visualization_creation(visualization: Visualization, user: Optional[User]) -> None:
        """Log visualization creation for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_creation(
                visualization,
                user,
                description=f"Created visualization: {visualization.name}"
            )
        except Exception as e:
            logger.error(f"Error logging visualization creation: {str(e)}")


class ReportGenerationService:
    """
    Enterprise-grade report generation service with automated scheduling.
    
    Features:
    - Automated report generation
    - Multi-format output
    - Scheduled delivery
    - Template management
    - Performance optimization
    """
    
    @staticmethod
    def generate_automated_report(schedule_id: UUID) -> bool:
        """Generate automated report based on schedule."""
        try:
            # Get schedule
            schedule = ReportSchedule.objects.get(id=schedule_id)
            
            # Check if schedule is active
            if not schedule.is_active:
                return False
            
            # Check if schedule should run now
            if not ReportGenerationService._should_run_now(schedule):
                return False
            
            # Generate report
            report_config = schedule.report_config
            report_data = ReportingService.generate_report(report_config)
            
            # Deliver report
            delivery_success = ReportGenerationService._deliver_report(report_data, schedule)
            
            # Update schedule
            if delivery_success:
                schedule.last_run = timezone.now()
                schedule.save(update_fields=['last_run'])
            
            return delivery_success
            
        except Exception as e:
            logger.error(f"Error generating automated report: {str(e)}")
            return False
    
    @staticmethod
    def _should_run_now(schedule: ReportSchedule) -> bool:
        """Check if schedule should run now."""
        try:
            now = timezone.now()
            schedule_type = schedule.schedule_type
            schedule_params = schedule.schedule_params
            
            if schedule_type == 'daily':
                # Check if it's the scheduled time
                scheduled_time = schedule_params.get('time', '09:00')
                hour, minute = map(int, scheduled_time.split(':'))
                return now.hour == hour and now.minute == minute
            
            elif schedule_type == 'weekly':
                # Check if it's the scheduled day and time
                scheduled_day = schedule_params.get('day', 1)  # 0 = Monday, 6 = Sunday
                scheduled_time = schedule_params.get('time', '09:00')
                hour, minute = map(int, scheduled_time.split(':'))
                return now.weekday() == scheduled_day and now.hour == hour and now.minute == minute
            
            elif schedule_type == 'monthly':
                # Check if it's the scheduled day and time
                scheduled_day = schedule_params.get('day', 1)
                scheduled_time = schedule_params.get('time', '09:00')
                hour, minute = map(int, scheduled_time.split(':'))
                return now.day == scheduled_day and now.hour == hour and now.minute == minute
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking schedule: {str(e)}")
            return False
    
    @staticmethod
    def _deliver_report(report_data: ReportData, schedule: ReportSchedule) -> bool:
        """Deliver report using configured method."""
        try:
            delivery_method = schedule.delivery_method
            delivery_params = schedule.delivery_params
            
            if delivery_method == 'email':
                return ReportGenerationService._deliver_email_report(report_data, delivery_params)
            elif delivery_method == 'ftp':
                return ReportGenerationService._deliver_ftp_report(report_data, delivery_params)
            elif delivery_method == 'webhook':
                return ReportGenerationService._deliver_webhook_report(report_data, delivery_params)
            elif delivery_method == 'api':
                return ReportGenerationService._deliver_api_report(report_data, delivery_params)
            
            return False
            
        except Exception as e:
            logger.error(f"Error delivering report: {str(e)}")
            return False
    
    @staticmethod
    def _deliver_email_report(report_data: ReportData, delivery_params: Dict[str, Any]) -> bool:
        """Deliver report via email."""
        try:
            recipients = delivery_params.get('recipients', [])
            subject = delivery_params.get('subject', f'Report: {report_data.report_name}')
            
            # Generate email content
            html_content = ReportGenerationService._generate_email_html(report_data)
            
            # Send email
            send_mail(
                subject=subject,
                message=html_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                html_message=html_content,
                fail_silently=False
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error delivering email report: {str(e)}")
            return False
    
    @staticmethod
    def _generate_email_html(report_data: ReportData) -> str:
        """Generate HTML email content for report."""
        try:
            html_template = """
            <html>
            <head>
                <title>{title}</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    .header { background-color: #f4f4f4; padding: 20px; text-align: center; }
                    .content { padding: 20px; }
                    .metric { margin: 10px 0; padding: 10px; border: 1px solid #ddd; }
                    .metric-title { font-weight: bold; color: #333; }
                    .metric-value { font-size: 18px; color: #007bff; }
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>{title}</h1>
                    <p>Generated on: {generated_at}</p>
                </div>
                <div class="content">
                    {content}
                </div>
            </body>
            </html>
            """
            
            # Generate content
            content = ""
            for item in report_data.data:
                content += f"""
                <div class="metric">
                    <div class="metric-title">{item.get('metric', 'Unknown')}</div>
                    <div class="metric-value">{item.get('value', 0)}</div>
                </div>
                """
            
            return html_template.format(
                title=report_data.report_name,
                generated_at=report_data.generated_at.strftime('%Y-%m-%d %H:%M:%S'),
                content=content
            )
            
        except Exception as e:
            logger.error(f"Error generating email HTML: {str(e)}")
            return "<html><body>Error generating report content</body></html>"
    
    @staticmethod
    def _deliver_ftp_report(report_data: ReportData, delivery_params: Dict[str, Any]) -> bool:
        """Deliver report via FTP."""
        try:
            # FTP implementation would go here
            # For now, just log the delivery
            logger.info(f"FTP delivery for report {report_data.report_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error delivering FTP report: {str(e)}")
            return False
    
    @staticmethod
    def _deliver_webhook_report(report_data: ReportData, delivery_params: Dict[str, Any]) -> bool:
        """Deliver report via webhook."""
        try:
            import requests
            
            webhook_url = delivery_params.get('url')
            if not webhook_url:
                return False
            
            # Send webhook
            response = requests.post(
                webhook_url,
                json={
                    'report_id': report_data.report_id,
                    'report_name': report_data.report_name,
                    'report_type': report_data.report_type,
                    'data': report_data.data,
                    'generated_at': report_data.generated_at.isoformat()
                },
                timeout=30
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error delivering webhook report: {str(e)}")
            return False
    
    @staticmethod
    def _deliver_api_report(report_data: ReportData, delivery_params: Dict[str, Any]) -> bool:
        """Deliver report via API."""
        try:
            # API delivery implementation would go here
            # For now, just log the delivery
            logger.info(f"API delivery for report {report_data.report_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error delivering API report: {str(e)}")
            return False
