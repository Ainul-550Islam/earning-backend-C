"""
Advertiser ROI Management

This module handles ROI (Return on Investment) calculations, analysis,
and reporting for advertisers including performance metrics and optimization insights.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.conversion_model import Conversion
from ..database_models.roi_model import ROICalculation, ROIMetric, ROIBenchmark
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class AdvertiserROIService:
    """Service for managing advertiser ROI operations."""
    
    @staticmethod
    def calculate_roi(advertiser_id: UUID, roi_data: Dict[str, Any],
                      calculated_by: Optional[User] = None) -> ROICalculation:
        """Calculate ROI for advertiser."""
        try:
            advertiser = AdvertiserROIService.get_advertiser(advertiser_id)
            
            # Validate ROI data
            date_range = roi_data.get('date_range')
            if not date_range or not date_range.get('start_date') or not date_range.get('end_date'):
                raise AdvertiserValidationError("date_range with start_date and end_date is required")
            
            start_date = date.fromisoformat(date_range['start_date'])
            end_date = date.fromisoformat(date_range['end_date'])
            
            roi_type = roi_data.get('roi_type', 'campaign')
            if roi_type not in ['campaign', 'creative', 'channel', 'overall']:
                raise AdvertiserValidationError("Invalid roi_type")
            
            with transaction.atomic():
                # Get spend data
                spend_data = AdvertiserROIService._get_spend_data(advertiser, start_date, end_date, roi_data)
                total_spend = spend_data['total_spend']
                
                # Get revenue data
                revenue_data = AdvertiserROIService._get_revenue_data(advertiser, start_date, end_date, roi_data)
                total_revenue = revenue_data['total_revenue']
                
                # Calculate ROI metrics
                roi_metrics = AdvertiserROIService._calculate_roi_metrics(
                    total_spend, total_revenue, spend_data, revenue_data
                )
                
                # Create ROI calculation record
                roi_calculation = ROICalculation.objects.create(
                    advertiser=advertiser,
                    roi_type=roi_type,
                    start_date=start_date,
                    end_date=end_date,
                    total_spend=total_spend,
                    total_revenue=total_revenue,
                    net_profit=total_revenue - total_spend,
                    roi_percentage=roi_metrics['roi_percentage'],
                    roas=roi_metrics['roas'],
                    payback_period=roi_metrics['payback_period'],
                    metrics=roi_metrics,
                    calculation_method=roi_data.get('calculation_method', 'standard'),
                    assumptions=roi_data.get('assumptions', {}),
                    created_by=calculated_by
                )
                
                # Send notification for significant ROI
                if roi_metrics['roi_percentage'] < 0:
                    Notification.objects.create(
                        advertiser=advertiser,
                        user=calculated_by,
                        title='Negative ROI Detected',
                        message=f'Your {roi_type} ROI is {roi_metrics["roi_percentage"]:.1f}%. Consider optimization.',
                        notification_type='roi',
                        priority='high',
                        channels=['in_app']
                    )
                elif roi_metrics['roi_percentage'] > 200:
                    Notification.objects.create(
                        advertiser=advertiser,
                        user=calculated_by,
                        title='Excellent ROI Achieved',
                        message=f'Your {roi_type} ROI is {roi_metrics["roi_percentage"]:.1f}%! Great performance!',
                        notification_type='roi',
                        priority='medium',
                        channels=['in_app']
                    )
                
                # Log calculation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='calculate_roi',
                    object_type='ROICalculation',
                    object_id=str(roi_calculation.id),
                    user=calculated_by,
                    advertiser=advertiser,
                    description=f"Calculated {roi_type} ROI: {roi_metrics['roi_percentage']:.1f}%"
                )
                
                return roi_calculation
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error calculating ROI {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to calculate ROI: {str(e)}")
    
    @staticmethod
    def get_roi_analysis(advertiser_id: UUID, date_range: Optional[Dict[str, str]] = None,
                         roi_type: Optional[str] = None) -> Dict[str, Any]:
        """Get comprehensive ROI analysis."""
        try:
            advertiser = AdvertiserROIService.get_advertiser(advertiser_id)
            
            # Default date range (last 90 days)
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=90)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            # Get ROI calculations
            queryset = ROICalculation.objects.filter(
                advertiser=advertiser,
                start_date__gte=start_date,
                end_date__lte=end_date
            )
            
            if roi_type:
                queryset = queryset.filter(roi_type=roi_type)
            
            # Get latest calculation
            latest_roi = queryset.order_by('-created_at').first()
            
            if not latest_roi:
                return {
                    'advertiser_id': str(advertiser_id),
                    'date_range': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat()
                    },
                    'roi_status': 'no_data',
                    'message': 'No ROI calculations found for the specified period'
                }
            
            # Get ROI trends
            roi_trends = queryset.extra(
                {'period': 'DATE_TRUNC(\'week\', created_at)'}
            ).values('period').annotate(
                avg_roi=Avg('roi_percentage'),
                avg_roas=Avg('roas'),
                calculations=Count('id')
            ).order_by('period')
            
            # Get ROI by type
            roi_by_type = queryset.values('roi_type').annotate(
                avg_roi=Avg('roi_percentage'),
                avg_roas=Avg('roas'),
                calculations=Count('id')
            )
            
            # Get performance benchmarks
            benchmarks = AdvertiserROIService._get_roi_benchmarks(advertiser.industry)
            
            # Calculate performance vs benchmarks
            performance_vs_benchmark = AdvertiserROIService._compare_with_benchmarks(latest_roi, benchmarks)
            
            return {
                'advertiser_id': str(advertiser_id),
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'latest_roi': {
                    'id': str(latest_roi.id),
                    'roi_type': latest_roi.roi_type,
                    'roi_percentage': float(latest_roi.roi_percentage),
                    'roas': float(latest_roi.roas),
                    'total_spend': float(latest_roi.total_spend),
                    'total_revenue': float(latest_roi.total_revenue),
                    'net_profit': float(latest_roi.net_profit),
                    'calculated_at': latest_roi.created_at.isoformat()
                },
                'roi_trends': [
                    {
                        'period': str(item['period']),
                        'avg_roi': float(item['avg_roi']),
                        'avg_roas': float(item['avg_roas']),
                        'calculations': item['calculations']
                    }
                    for item in roi_trends
                ],
                'roi_by_type': [
                    {
                        'roi_type': item['roi_type'],
                        'avg_roi': float(item['avg_roi']),
                        'avg_roas': float(item['avg_roas']),
                        'calculations': item['calculations']
                    }
                    for item in roi_by_type
                ],
                'benchmarks': benchmarks,
                'performance_vs_benchmark': performance_vs_benchmark,
                'roi_status': AdvertiserROIService._determine_roi_status(latest_roi.roi_percentage)
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting ROI analysis {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get ROI analysis: {str(e)}")
    
    @staticmethod
    def get_roi_forecast(advertiser_id: UUID, forecast_period: int = 30,
                         forecast_method: str = 'linear') -> Dict[str, Any]:
        """Forecast ROI based on historical data."""
        try:
            advertiser = AdvertiserROIService.get_advertiser(advertiser_id)
            
            # Get historical ROI data (last 180 days)
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=180)
            
            historical_roi = ROICalculation.objects.filter(
                advertiser=advertiser,
                start_date__gte=start_date,
                end_date__lte=end_date
            ).order_by('start_date')
            
            if len(historical_roi) < 4:
                raise AdvertiserValidationError("Insufficient historical data for ROI forecasting")
            
            # Extract ROI time series
            roi_time_series = []
            for roi_calc in historical_roi:
                roi_time_series.append({
                    'date': roi_calc.end_date,
                    'roi_percentage': float(roi_calc.roi_percentage),
                    'roas': float(roi_calc.roas)
                })
            
            # Generate forecast
            if forecast_method == 'linear':
                forecast = AdvertiserROIService._linear_roi_forecast(roi_time_series, forecast_period)
            elif forecast_method == 'exponential':
                forecast = AdvertiserROIService._exponential_roi_forecast(roi_time_series, forecast_period)
            elif forecast_method == 'moving_average':
                forecast = AdvertiserROIService._moving_average_roi_forecast(roi_time_series, forecast_period)
            else:
                raise AdvertiserValidationError("Invalid forecast method. Use 'linear', 'exponential', or 'moving_average'")
            
            # Calculate forecast confidence
            confidence = AdvertiserROIService._calculate_roi_forecast_confidence(roi_time_series)
            
            return {
                'advertiser_id': str(advertiser_id),
                'forecast_period': forecast_period,
                'forecast_method': forecast_method,
                'historical_period': f"{start_date.isoformat()} to {end_date.isoformat()}",
                'confidence_score': confidence,
                'forecast_data': forecast,
                'generated_at': timezone.now().isoformat()
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error forecasting ROI {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to forecast ROI: {str(e)}")
    
    @staticmethod
    def get_roi_optimization_recommendations(advertiser_id: UUID) -> List[Dict[str, Any]]:
        """Get ROI optimization recommendations."""
        try:
            advertiser = AdvertiserROIService.get_advertiser(advertiser_id)
            
            recommendations = []
            
            # Get recent ROI analysis
            roi_analysis = AdvertiserROIService.get_roi_analysis(advertiser_id)
            
            if roi_analysis['roi_status'] == 'no_data':
                recommendations.append({
                    'type': 'data_collection',
                    'priority': 'high',
                    'title': 'Start Tracking ROI',
                    'description': 'Begin tracking spend and revenue to calculate ROI',
                    'potential_impact': 'Essential for measuring campaign effectiveness',
                    'action_items': [
                        'Implement conversion tracking',
                        'Set up spend monitoring',
                        'Define revenue attribution model',
                        'Create ROI calculation schedule'
                    ]
                })
                return recommendations
            
            latest_roi = roi_analysis['latest_roi']
            
            # Analyze ROI performance
            roi_percentage = latest_roi['roi_percentage']
            roas = latest_roi['roas']
            
            if roi_percentage < 0:
                recommendations.append({
                    'type': 'negative_roi',
                    'priority': 'critical',
                    'title': 'Address Negative ROI',
                    'description': f'Current ROI is {roi_percentage:.1f}%. Immediate action required.',
                    'potential_impact': 'Prevent continued losses and improve profitability',
                    'action_items': [
                        'Pause underperforming campaigns',
                        'Review targeting and bidding strategy',
                        'Optimize ad creatives and landing pages',
                        'Reduce spend on low-performing channels'
                    ]
                })
            elif roi_percentage < 50:
                recommendations.append({
                    'type': 'low_roi',
                    'priority': 'high',
                    'title': 'Improve Low ROI',
                    'description': f'Current ROI is {roi_percentage:.1f}%. Significant improvement needed.',
                    'potential_impact': 'Could double or triple profitability',
                    'action_items': [
                        'A/B test different ad variations',
                        'Refine audience targeting',
                        'Optimize bidding strategy',
                        'Improve conversion rate'
                    ]
                })
            elif roi_percentage > 300:
                recommendations.append({
                    'type': 'scaling_opportunity',
                    'priority': 'medium',
                    'title': 'Scale Successful Campaigns',
                    'description': f'Excellent ROI of {roi_percentage:.1f}%. Consider scaling.',
                    'potential_impact': 'Increase revenue while maintaining efficiency',
                    'action_items': [
                        'Increase budget for high-ROI campaigns',
                        'Expand to new channels or audiences',
                        'Test higher bids for better placements',
                        'Replicate successful strategies'
                    ]
                })
            
            # Compare with industry benchmarks
            benchmarks = roi_analysis['benchmarks']
            benchmark_comparison = roi_analysis['performance_vs_benchmark']
            
            if benchmark_comparison['roi_performance'] == 'below_average':
                recommendations.append({
                    'type': 'benchmark_improvement',
                    'priority': 'medium',
                    'title': 'Improve vs Industry Benchmark',
                    'description': f'ROI is {benchmark_comparison["roi_difference"]:.1f}% below industry average.',
                    'potential_impact': 'Achieve industry-standard performance',
                    'action_items': [
                        'Study top-performing competitors',
                        'Adopt industry best practices',
                        'Focus on high-conversion segments',
                        'Improve attribution accuracy'
                    ]
                })
            
            # Analyze ROAS efficiency
            if roas < 1.0:
                recommendations.append({
                    'type': 'roas_optimization',
                    'priority': 'high',
                    'title': 'Improve ROAS',
                    'description': f'ROAS is {roas:.2f}x. Need to increase revenue per spend.',
                    'potential_impact': 'Achieve positive return on ad spend',
                    'action_items': [
                        'Increase conversion rate',
                        'Improve average order value',
                        'Optimize landing pages',
                        'Focus on high-value customers'
                    ]
                })
            
            # Get campaign-specific recommendations
            campaign_recommendations = AdvertiserROIService._get_campaign_roi_recommendations(advertiser)
            recommendations.extend(campaign_recommendations)
            
            return recommendations
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting ROI recommendations {advertiser_id}: {str(e)}")
            return []
    
    @staticmethod
    def get_roi_dashboard(advertiser_id: UUID) -> Dict[str, Any]:
        """Get comprehensive ROI dashboard data."""
        try:
            advertiser = AdvertiserROIService.get_advertiser(advertiser_id)
            
            # Get different time period analyses
            periods = {
                '7_days': {'days': 7, 'label': 'Last 7 Days'},
                '30_days': {'days': 30, 'label': 'Last 30 Days'},
                '90_days': {'days': 90, 'label': 'Last 90 Days'}
            }
            
            period_data = {}
            
            for period_key, period_info in periods.items():
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=period_info['days'])
                
                date_range = {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
                
                roi_analysis = AdvertiserROIService.get_roi_analysis(advertiser_id, date_range)
                period_data[period_key] = roi_analysis
            
            # Get ROI trends
            roi_trends = AdvertiserROIService.get_roi_analysis(advertiser_id)
            
            # Get ROI forecast
            try:
                roi_forecast = AdvertiserROIService.get_roi_forecast(advertiser_id, 30)
            except:
                roi_forecast = None
            
            # Get optimization recommendations
            recommendations = AdvertiserROIService.get_roi_optimization_recommendations(advertiser_id)
            
            return {
                'advertiser_id': str(advertiser_id),
                'period_analysis': period_data,
                'roi_trends': roi_trends,
                'roi_forecast': roi_forecast,
                'recommendations': recommendations,
                'generated_at': timezone.now().isoformat()
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting ROI dashboard {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get ROI dashboard: {str(e)}")
    
    @staticmethod
    def _get_spend_data(advertiser: Advertiser, start_date: date, end_date: date,
                          roi_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get spend data for ROI calculation."""
        try:
            from ..database_models.spend_model import SpendRecord
            
            queryset = SpendRecord.objects.filter(
                advertiser=advertiser,
                spend_date__gte=start_date,
                spend_date__lte=end_date
            )
            
            # Apply filters based on ROI data
            if roi_data.get('campaign_id'):
                queryset = queryset.filter(campaign_id=roi_data['campaign_id'])
            
            if roi_data.get('creative_id'):
                queryset = queryset.filter(creative_id=roi_data['creative_id'])
            
            total_spend = queryset.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            return {
                'total_spend': total_spend,
                'transaction_count': queryset.count(),
                'daily_average': total_spend / ((end_date - start_date).days + 1)
            }
            
        except Exception as e:
            logger.error(f"Error getting spend data: {str(e)}")
            return {'total_spend': Decimal('0.00'), 'transaction_count': 0, 'daily_average': 0}
    
    @staticmethod
    def _get_revenue_data(advertiser: Advertiser, start_date: date, end_date: date,
                           roi_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get revenue data for ROI calculation."""
        try:
            from ..database_models.conversion_model import Conversion
            
            queryset = Conversion.objects.filter(
                campaign__advertiser=advertiser,
                conversion_date__date__gte=start_date,
                conversion_date__date__lte=end_date
            )
            
            # Apply filters based on ROI data
            if roi_data.get('campaign_id'):
                queryset = queryset.filter(campaign_id=roi_data['campaign_id'])
            
            total_revenue = queryset.aggregate(total=Sum('conversion_value'))['total'] or Decimal('0.00')
            
            return {
                'total_revenue': total_revenue,
                'conversion_count': queryset.count(),
                'average_order_value': total_revenue / queryset.count() if queryset.count() > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting revenue data: {str(e)}")
            return {'total_revenue': Decimal('0.00'), 'conversion_count': 0, 'average_order_value': 0}
    
    @staticmethod
    def _calculate_roi_metrics(total_spend: Decimal, total_revenue: Decimal,
                               spend_data: Dict[str, Any], revenue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate comprehensive ROI metrics."""
        try:
            net_profit = total_revenue - total_spend
            roi_percentage = (net_profit / total_spend * 100) if total_spend > 0 else 0
            roas = (total_revenue / total_spend) if total_spend > 0 else 0
            
            # Calculate payback period (days)
            daily_spend = spend_data.get('daily_average', 0)
            payback_period = (total_spend / (total_revenue / spend_data.get('transaction_count', 1))) if total_revenue > 0 and spend_data.get('transaction_count', 1) > 0 else 0
            
            # Calculate LTV:CAC ratio (Lifetime Value to Customer Acquisition Cost)
            ltv = revenue_data.get('average_order_value', 0)
            cac = total_spend / revenue_data.get('conversion_count', 1) if revenue_data.get('conversion_count', 1) > 0 else 0
            ltv_cac_ratio = ltv / cac if cac > 0 else 0
            
            return {
                'net_profit': float(net_profit),
                'roi_percentage': float(roi_percentage),
                'roas': float(roas),
                'payback_period': payback_period,
                'ltv_cac_ratio': float(ltv_cac_ratio),
                'profit_margin': float((net_profit / total_revenue * 100) if total_revenue > 0 else 0)
            }
            
        except Exception as e:
            logger.error(f"Error calculating ROI metrics: {str(e)}")
            return {
                'net_profit': 0,
                'roi_percentage': 0,
                'roas': 0,
                'payback_period': 0,
                'ltv_cac_ratio': 0,
                'profit_margin': 0
            }
    
    @staticmethod
    def _get_roi_benchmarks(industry: str) -> Dict[str, Any]:
        """Get industry ROI benchmarks."""
        try:
            # Mock industry benchmarks (would come from database or external API)
            benchmarks = {
                'technology': {
                    'average_roi': 150.0,
                    'average_roas': 2.5,
                    'top_quartile_roi': 250.0,
                    'bottom_quartile_roi': 50.0
                },
                'retail': {
                    'average_roi': 120.0,
                    'average_roas': 2.2,
                    'top_quartile_roi': 200.0,
                    'bottom_quartile_roi': 40.0
                },
                'finance': {
                    'average_roi': 180.0,
                    'average_roas': 2.8,
                    'top_quartile_roi': 300.0,
                    'bottom_quartile_roi': 80.0
                },
                'healthcare': {
                    'average_roi': 160.0,
                    'average_roas': 2.6,
                    'top_quartile_roi': 280.0,
                    'bottom_quartile_roi': 60.0
                },
                'ecommerce': {
                    'average_roi': 130.0,
                    'average_roas': 2.3,
                    'top_quartile_roi': 220.0,
                    'bottom_quartile_roi': 45.0
                }
            }
            
            return benchmarks.get(industry.lower(), {
                'average_roi': 140.0,
                'average_roas': 2.4,
                'top_quartile_roi': 230.0,
                'bottom_quartile_roi': 50.0
            })
            
        except Exception as e:
            logger.error(f"Error getting ROI benchmarks: {str(e)}")
            return {
                'average_roi': 140.0,
                'average_roas': 2.4,
                'top_quartile_roi': 230.0,
                'bottom_quartile_roi': 50.0
            }
    
    @staticmethod
    def _compare_with_benchmarks(latest_roi: ROICalculation, benchmarks: Dict[str, Any]) -> Dict[str, Any]:
        """Compare ROI with industry benchmarks."""
        try:
            roi_percentage = float(latest_roi.roi_percentage)
            avg_roi = benchmarks['average_roi']
            
            roi_difference = ((roi_percentage - avg_roi) / avg_roi * 100) if avg_roi > 0 else 0
            
            if roi_percentage >= benchmarks['top_quartile_roi']:
                performance = 'excellent'
            elif roi_percentage >= benchmarks['average_roi']:
                performance = 'above_average'
            elif roi_percentage >= benchmarks['bottom_quartile_roi']:
                performance = 'below_average'
            else:
                performance = 'poor'
            
            return {
                'roi_performance': performance,
                'roi_difference': roi_difference,
                'industry_average': avg_roi,
                'top_quartile': benchmarks['top_quartile_roi'],
                'bottom_quartile': benchmarks['bottom_quartile_roi']
            }
            
        except Exception as e:
            logger.error(f"Error comparing with benchmarks: {str(e)}")
            return {
                'roi_performance': 'unknown',
                'roi_difference': 0,
                'industry_average': 0,
                'top_quartile': 0,
                'bottom_quartile': 0
            }
    
    @staticmethod
    def _determine_roi_status(roi_percentage: float) -> str:
        """Determine ROI status based on percentage."""
        if roi_percentage > 200:
            return 'excellent'
        elif roi_percentage > 100:
            return 'good'
        elif roi_percentage > 50:
            return 'fair'
        elif roi_percentage > 0:
            return 'low'
        else:
            return 'negative'
    
    @staticmethod
    def _linear_roi_forecast(roi_time_series: List[Dict[str, Any]], periods: int) -> List[Dict[str, Any]]:
        """Linear ROI forecast."""
        try:
            if len(roi_time_series) < 2:
                return []
            
            # Extract ROI percentages
            x_values = list(range(len(roi_time_series)))
            y_values = [item['roi_percentage'] for item in roi_time_series]
            
            # Simple linear regression
            n = len(x_values)
            sum_x = sum(x_values)
            sum_y = sum(y_values)
            sum_xy = sum(x * y for x, y in zip(x_values, y_values))
            sum_x2 = sum(x * x for x in x_values)
            
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            intercept = (sum_y - slope * sum_x) / n
            
            # Generate forecast
            forecast = []
            last_date = roi_time_series[-1]['date']
            
            for i in range(1, periods + 1):
                forecast_date = last_date + timedelta(days=i)
                forecast_roi = slope * (len(roi_time_series) + i) + intercept
                
                forecast.append({
                    'date': forecast_date.isoformat(),
                    'forecast_roi': forecast_roi,
                    'confidence_lower': forecast_roi * 0.8,
                    'confidence_upper': forecast_roi * 1.2
                })
            
            return forecast
            
        except Exception as e:
            logger.error(f"Error in linear ROI forecast: {str(e)}")
            return []
    
    @staticmethod
    def _exponential_roi_forecast(roi_time_series: List[Dict[str, Any]], periods: int) -> List[Dict[str, Any]]:
        """Exponential ROI forecast."""
        try:
            if len(roi_time_series) < 2:
                return []
            
            # Calculate growth rate
            roi_values = [item['roi_percentage'] for item in roi_time_series]
            growth_rates = []
            
            for i in range(1, len(roi_values)):
                if roi_values[i-1] != 0:
                    growth_rate = (roi_values[i] - roi_values[i-1]) / abs(roi_values[i-1])
                    growth_rates.append(growth_rate)
            
            if not growth_rates:
                return []
            
            avg_growth_rate = sum(growth_rates) / len(growth_rates)
            last_roi = roi_values[-1]
            
            # Generate forecast
            forecast = []
            last_date = roi_time_series[-1]['date']
            
            for i in range(1, periods + 1):
                forecast_date = last_date + timedelta(days=i)
                forecast_roi = last_roi * ((1 + avg_growth_rate) ** i)
                
                forecast.append({
                    'date': forecast_date.isoformat(),
                    'forecast_roi': forecast_roi,
                    'confidence_lower': forecast_roi * 0.7,
                    'confidence_upper': forecast_roi * 1.3
                })
            
            return forecast
            
        except Exception as e:
            logger.error(f"Error in exponential ROI forecast: {str(e)}")
            return []
    
    @staticmethod
    def _moving_average_roi_forecast(roi_time_series: List[Dict[str, Any]], periods: int) -> List[Dict[str, Any]]:
        """Moving average ROI forecast."""
        try:
            if len(roi_time_series) < 7:
                return []
            
            # Calculate 7-period moving average
            moving_averages = []
            roi_values = [item['roi_percentage'] for item in roi_time_series]
            
            for i in range(6, len(roi_values)):
                avg = sum(roi_values[i-6:i+1]) / 7
                moving_averages.append(avg)
            
            if not moving_averages:
                return []
            
            # Use last moving average as forecast
            last_avg = moving_averages[-1]
            
            # Generate forecast
            forecast = []
            last_date = roi_time_series[-1]['date']
            
            for i in range(1, periods + 1):
                forecast_date = last_date + timedelta(days=i)
                
                forecast.append({
                    'date': forecast_date.isoformat(),
                    'forecast_roi': last_avg,
                    'confidence_lower': last_avg * 0.9,
                    'confidence_upper': last_avg * 1.1
                })
            
            return forecast
            
        except Exception as e:
            logger.error(f"Error in moving average ROI forecast: {str(e)}")
            return []
    
    @staticmethod
    def _calculate_roi_forecast_confidence(roi_time_series: List[Dict[str, Any]]) -> float:
        """Calculate ROI forecast confidence score."""
        try:
            if len(roi_time_series) < 7:
                return 0.5
            
            roi_values = [item['roi_percentage'] for item in roi_time_series]
            
            # Calculate variance
            mean = sum(roi_values) / len(roi_values)
            variance = sum((x - mean) ** 2 for x in roi_values) / len(roi_values)
            std_dev = variance ** 0.5
            
            # Calculate coefficient of variation
            cv = (std_dev / abs(mean)) if mean != 0 else float('inf')
            
            # Convert to confidence score (lower CV = higher confidence)
            if cv <= 0.2:
                return 0.9
            elif cv <= 0.4:
                return 0.8
            elif cv <= 0.6:
                return 0.7
            elif cv <= 1.0:
                return 0.6
            else:
                return 0.5
            
        except Exception as e:
            logger.error(f"Error calculating ROI forecast confidence: {str(e)}")
            return 0.5
    
    @staticmethod
    def _get_campaign_roi_recommendations(advertiser: Advertiser) -> List[Dict[str, Any]]:
        """Get campaign-specific ROI recommendations."""
        try:
            recommendations = []
            
            # Get campaigns with ROI data
            campaigns = Campaign.objects.filter(advertiser=advertiser, is_deleted=False)
            
            for campaign in campaigns:
                # Get latest ROI calculation for this campaign
                campaign_roi = ROICalculation.objects.filter(
                    campaign_id=campaign.id
                ).order_by('-created_at').first()
                
                if campaign_roi:
                    if campaign_roi.roi_percentage < 0:
                        recommendations.append({
                            'type': 'campaign_optimization',
                            'priority': 'high',
                            'title': f'Optimize {campaign.name}',
                            'description': f'Campaign ROI is {campaign_roi.roi_percentage:.1f}%',
                            'campaign_id': str(campaign.id),
                            'action_items': [
                                f'Review and pause {campaign.name}',
                                'Optimize targeting and bidding',
                                'Test new ad creatives',
                                'Improve landing page experience'
                            ]
                        })
                    elif campaign_roi.roi_percentage < 50:
                        recommendations.append({
                            'type': 'campaign_improvement',
                            'priority': 'medium',
                            'title': f'Improve {campaign.name}',
                            'description': f'Campaign ROI is {campaign_roi.roi_percentage:.1f}%',
                            'campaign_id': str(campaign.id),
                            'action_items': [
                                f'A/B test ad variations for {campaign.name}',
                                'Refine audience targeting',
                                'Adjust bidding strategy'
                            ]
                        })
                    elif campaign_roi.roi_percentage > 300:
                        recommendations.append({
                            'type': 'campaign_scaling',
                            'priority': 'medium',
                            'title': f'Scale {campaign.name}',
                            'description': f'Excellent ROI of {campaign_roi.roi_percentage:.1f}%',
                            'campaign_id': str(campaign.id),
                            'action_items': [
                                f'Increase budget for {campaign.name}',
                                'Expand targeting reach',
                                'Test higher bids'
                            ]
                        })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting campaign ROI recommendations: {str(e)}")
            return []
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def get_roi_statistics() -> Dict[str, Any]:
        """Get ROI statistics across all advertisers."""
        try:
            # Get total ROI statistics
            total_calculations = ROICalculation.objects.count()
            
            # Get ROI distribution
            roi_distribution = ROICalculation.objects.aggregate(
                avg_roi=Avg('roi_percentage'),
                avg_roas=Avg('roas'),
                total_spend=Sum('total_spend'),
                total_revenue=Sum('total_revenue'),
                total_profit=Sum('net_profit')
            )
            
            # Get ROI by type
            roi_by_type = ROICalculation.objects.values('roi_type').annotate(
                avg_roi=Avg('roi_percentage'),
                avg_roas=Avg('roas'),
                count=Count('id')
            )
            
            # Get monthly ROI trends
            monthly_roi = ROICalculation.objects.extra(
                {'month': 'DATE_TRUNC(\'month\', created_at)'}
            ).values('month').annotate(
                avg_roi=Avg('roi_percentage'),
                count=Count('id')
            ).order_by('-month')[:12]
            
            return {
                'total_calculations': total_calculations,
                'overall_metrics': {
                    'avg_roi': float(roi_distribution['avg_roi'] or 0),
                    'avg_roas': float(roi_distribution['avg_roas'] or 0),
                    'total_spend': float(roi_distribution['total_spend'] or 0),
                    'total_revenue': float(roi_distribution['total_revenue'] or 0),
                    'total_profit': float(roi_distribution['total_profit'] or 0)
                },
                'roi_by_type': [
                    {
                        'roi_type': item['roi_type'],
                        'avg_roi': float(item['avg_roi'] or 0),
                        'avg_roas': float(item['avg_roas'] or 0),
                        'count': item['count']
                    }
                    for item in roi_by_type
                ],
                'monthly_roi': [
                    {
                        'month': str(item['month']),
                        'avg_roi': float(item['avg_roi'] or 0),
                        'calculations': item['count']
                    }
                    for item in monthly_roi
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting ROI statistics: {str(e)}")
            return {
                'total_calculations': 0,
                'overall_metrics': {
                    'avg_roi': 0,
                    'avg_roas': 0,
                    'total_spend': 0,
                    'total_revenue': 0,
                    'total_profit': 0
                },
                'roi_by_type': [],
                'monthly_roi': []
            }
