"""
Advertiser Spend Management

This module handles spend tracking, spend analysis, spend optimization,
and spend forecasting for advertisers.
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
from ..database_models.spend_model import SpendRecord, SpendAlert, SpendForecast
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class AdvertiserSpendService:
    """Service for managing advertiser spend operations."""
    
    @staticmethod
    def record_spend(advertiser_id: UUID, spend_data: Dict[str, Any],
                     recorded_by: Optional[User] = None) -> SpendRecord:
        """Record spend transaction for advertiser."""
        try:
            advertiser = AdvertiserSpendService.get_advertiser(advertiser_id)
            
            # Validate spend data
            amount = Decimal(str(spend_data.get('amount', 0)))
            if amount <= 0:
                raise AdvertiserValidationError("amount must be positive")
            
            spend_type = spend_data.get('spend_type', 'campaign')
            if spend_type not in ['campaign', 'creative', 'targeting', 'optimization', 'other']:
                raise AdvertiserValidationError("Invalid spend type")
            
            with transaction.atomic():
                # Create spend record
                spend_record = SpendRecord.objects.create(
                    advertiser=advertiser,
                    campaign_id=spend_data.get('campaign_id'),
                    creative_id=spend_data.get('creative_id'),
                    spend_type=spend_type,
                    amount=amount,
                    currency=spend_data.get('currency', 'USD'),
                    spend_date=spend_data.get('spend_date', date.today()),
                    description=spend_data.get('description', f'{spend_type.title()} spend'),
                    reference_number=spend_data.get('reference_number', ''),
                    metadata=spend_data.get('metadata', {}),
                    created_by=recorded_by
                )
                
                # Update advertiser total spend
                advertiser.total_spend += amount
                advertiser.save(update_fields=['total_spend'])
                
                # Update campaign spend if campaign provided
                if spend_record.campaign:
                    spend_record.campaign.current_spend += amount
                    spend_record.campaign.save(update_fields=['current_spend'])
                
                # Check spend alerts
                AdvertiserSpendService._check_spend_alerts(advertiser, spend_record)
                
                # Log spend
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='record_spend',
                    object_type='SpendRecord',
                    object_id=str(spend_record.id),
                    user=recorded_by,
                    advertiser=advertiser,
                    description=f"Recorded spend: {amount}"
                )
                
                return spend_record
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error recording spend {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to record spend: {str(e)}")
    
    @staticmethod
    def get_spend_summary(advertiser_id: UUID, date_range: Optional[Dict[str, str]] = None,
                          spend_type: Optional[str] = None) -> Dict[str, Any]:
        """Get spend summary for advertiser."""
        try:
            advertiser = AdvertiserSpendService.get_advertiser(advertiser_id)
            
            # Default date range (last 30 days)
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=30)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            # Get spend records
            queryset = SpendRecord.objects.filter(
                advertiser=advertiser,
                spend_date__gte=start_date,
                spend_date__lte=end_date
            )
            
            if spend_type:
                queryset = queryset.filter(spend_type=spend_type)
            
            # Aggregate spend data
            total_spend = queryset.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # Get spend by type
            spend_by_type = queryset.values('spend_type').annotate(
                total_amount=Sum('amount'),
                count=Count('id')
            )
            
            # Get spend by campaign
            spend_by_campaign = queryset.values('campaign__name').annotate(
                total_amount=Sum('amount'),
                count=Count('id')
            )
            
            # Get daily spend trend
            daily_spend = queryset.extra(
                {'date': 'spend_date'}
            ).values('date').annotate(
                total_amount=Sum('amount')
            ).order_by('date')
            
            # Calculate average daily spend
            days_in_period = (end_date - start_date).days + 1
            avg_daily_spend = total_spend / days_in_period if days_in_period > 0 else 0
            
            return {
                'advertiser_id': str(advertiser_id),
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days_in_period': days_in_period
                },
                'spend_summary': {
                    'total_spend': float(total_spend),
                    'avg_daily_spend': float(avg_daily_spend),
                    'total_transactions': queryset.count()
                },
                'spend_by_type': [
                    {
                        'spend_type': item['spend_type'],
                        'total_amount': float(item['total_amount']),
                        'count': item['count'],
                        'percentage': float((item['total_amount'] / total_spend * 100) if total_spend > 0 else 0)
                    }
                    for item in spend_by_type
                ],
                'spend_by_campaign': [
                    {
                        'campaign_name': item['campaign__name'],
                        'total_amount': float(item['total_amount']),
                        'count': item['count']
                    }
                    for item in spend_by_campaign
                ],
                'daily_spend': [
                    {
                        'date': item['date'].isoformat(),
                        'total_amount': float(item['total_amount'])
                    }
                    for item in daily_spend
                ]
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting spend summary {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get spend summary: {str(e)}")
    
    @staticmethod
    def get_spend_trends(advertiser_id: UUID, period: str = 'daily',
                          date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get spend trends analysis."""
        try:
            advertiser = AdvertiserSpendService.get_advertiser(advertiser_id)
            
            # Default date range (last 90 days for trends)
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=90)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            # Get spend records
            queryset = SpendRecord.objects.filter(
                advertiser=advertiser,
                spend_date__gte=start_date,
                spend_date__lte=end_date
            )
            
            # Group by period
            if period == 'daily':
                spend_trends = queryset.extra(
                    {'period': 'spend_date'}
                ).values('period').annotate(
                    total_amount=Sum('amount'),
                    count=Count('id')
                ).order_by('period')
            elif period == 'weekly':
                spend_trends = queryset.extra(
                    {'period': 'DATE_TRUNC(\'week\', spend_date)'}
                ).values('period').annotate(
                    total_amount=Sum('amount'),
                    count=Count('id')
                ).order_by('period')
            elif period == 'monthly':
                spend_trends = queryset.extra(
                    {'period': 'DATE_TRUNC(\'month\', spend_date)'}
                ).values('period').annotate(
                    total_amount=Sum('amount'),
                    count=Count('id')
                ).order_by('period')
            else:
                raise AdvertiserValidationError("Invalid period. Use 'daily', 'weekly', or 'monthly'")
            
            # Calculate trend metrics
            if len(spend_trends) >= 2:
                first_period = float(spend_trends[0]['total_amount'])
                last_period = float(spend_trends[-1]['total_amount'])
                trend_change = ((last_period - first_period) / first_period * 100) if first_period > 0 else 0
                
                # Calculate moving average
                moving_avg = []
                for i in range(len(spend_trends)):
                    if i < 3:  # Use first 3 periods for initial average
                        period_data = spend_trends[:i+1]
                    else:
                        period_data = spend_trends[i-2:i+1]
                    
                    avg = sum(float(p['total_amount']) for p in period_data) / len(period_data)
                    moving_avg.append(avg)
            else:
                trend_change = 0
                moving_avg = []
            
            return {
                'advertiser_id': str(advertiser_id),
                'period': period,
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'trend_analysis': {
                    'trend_change': trend_change,
                    'trend_direction': 'increasing' if trend_change > 0 else 'decreasing' if trend_change < 0 else 'stable',
                    'total_periods': len(spend_trends)
                },
                'spend_trends': [
                    {
                        'period': str(item['period']),
                        'total_amount': float(item['total_amount']),
                        'count': item['count'],
                        'moving_average': moving_avg[i] if i < len(moving_avg) else None
                    }
                    for i, item in enumerate(spend_trends)
                ]
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting spend trends {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get spend trends: {str(e)}")
    
    @staticmethod
    def forecast_spend(advertiser_id: UUID, forecast_period: int = 30,
                       forecast_type: str = 'linear') -> Dict[str, Any]:
        """Forecast future spend based on historical data."""
        try:
            advertiser = AdvertiserSpendService.get_advertiser(advertiser_id)
            
            # Get historical spend data (last 90 days)
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=90)
            
            historical_spend = SpendRecord.objects.filter(
                advertiser=advertiser,
                spend_date__gte=start_date,
                spend_date__lte=end_date
            ).extra(
                {'date': 'spend_date'}
            ).values('date').annotate(
                total_amount=Sum('amount')
            ).order_by('date')
            
            if len(historical_spend) < 7:
                raise AdvertiserValidationError("Insufficient historical data for forecasting")
            
            # Calculate forecast based on type
            if forecast_type == 'linear':
                forecast = AdvertiserSpendService._linear_forecast(historical_spend, forecast_period)
            elif forecast_type == 'exponential':
                forecast = AdvertiserSpendService._exponential_forecast(historical_spend, forecast_period)
            elif forecast_type == 'moving_average':
                forecast = AdvertiserSpendService._moving_average_forecast(historical_spend, forecast_period)
            else:
                raise AdvertiserValidationError("Invalid forecast type. Use 'linear', 'exponential', or 'moving_average'")
            
            # Calculate forecast confidence
            confidence = AdvertiserSpendService._calculate_forecast_confidence(historical_spend)
            
            return {
                'advertiser_id': str(advertiser_id),
                'forecast_period': forecast_period,
                'forecast_type': forecast_type,
                'historical_period': f"{start_date.isoformat()} to {end_date.isoformat()}",
                'confidence_score': confidence,
                'forecast_data': forecast,
                'generated_at': timezone.now().isoformat()
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error forecasting spend {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to forecast spend: {str(e)}")
    
    @staticmethod
    def get_spend_efficiency(advertiser_id: UUID, date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get spend efficiency analysis."""
        try:
            advertiser = AdvertiserSpendService.get_advertiser(advertiser_id)
            
            # Default date range (last 30 days)
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=30)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            # Get spend and performance data
            spend_data = AdvertiserSpendService.get_spend_summary(advertiser_id, date_range)
            
            # Get campaign performance
            campaigns = Campaign.objects.filter(
                advertiser=advertiser,
                is_deleted=False,
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
            
            # Calculate efficiency metrics
            total_spend = spend_data['spend_summary']['total_spend']
            total_impressions = campaigns.aggregate(total=Sum('total_impressions'))['total'] or 0
            total_clicks = campaigns.aggregate(total=Sum('total_clicks'))['total'] or 0
            total_conversions = campaigns.aggregate(total=Sum('total_conversions'))['total'] or 0
            
            # Calculate efficiency ratios
            cpm = (total_spend / total_impressions * 1000) if total_impressions > 0 else 0
            cpc = (total_spend / total_clicks) if total_clicks > 0 else 0
            cpa = (total_spend / total_conversions) if total_conversions > 0 else 0
            
            # Get spend by performance tier
            spend_by_performance = []
            
            for campaign in campaigns:
                campaign_spend = campaign.current_spend
                campaign_impressions = campaign.total_impressions
                campaign_clicks = campaign.total_clicks
                campaign_conversions = campaign.total_conversions
                
                campaign_cpm = (campaign_spend / campaign_impressions * 1000) if campaign_impressions > 0 else 0
                campaign_cpc = (campaign_spend / campaign_clicks) if campaign_clicks > 0 else 0
                campaign_cpa = (campaign_spend / campaign_conversions) if campaign_conversions > 0 else 0
                
                # Determine performance tier
                if campaign_cpa <= 10:
                    tier = 'high'
                elif campaign_cpa <= 25:
                    tier = 'medium'
                else:
                    tier = 'low'
                
                spend_by_performance.append({
                    'campaign_id': str(campaign.id),
                    'campaign_name': campaign.name,
                    'spend': float(campaign_spend),
                    'cpm': float(cpm),
                    'cpc': float(cpc),
                    'cpa': float(cpa),
                    'performance_tier': tier
                })
            
            # Sort by performance
            spend_by_performance.sort(key=lambda x: x['cpa'])
            
            return {
                'advertiser_id': str(advertiser_id),
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'efficiency_metrics': {
                    'total_spend': float(total_spend),
                    'cpm': float(cpm),
                    'cpc': float(cpc),
                    'cpa': float(cpa),
                    'total_impressions': total_impressions,
                    'total_clicks': total_clicks,
                    'total_conversions': total_conversions,
                    'click_through_rate': (total_clicks / total_impressions * 100) if total_impressions > 0 else 0,
                    'conversion_rate': (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
                },
                'spend_by_performance': spend_by_performance,
                'efficiency_score': AdvertiserSpendService._calculate_efficiency_score(cpm, cpc, cpa)
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting spend efficiency {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get spend efficiency: {str(e)}")
    
    @staticmethod
    def get_spend_alerts(advertiser_id: UUID) -> List[Dict[str, Any]]:
        """Get spend alerts for advertiser."""
        try:
            advertiser = AdvertiserSpendService.get_advertiser(advertiser_id)
            
            alerts = []
            
            # Check for unusual spend patterns
            recent_spend = SpendRecord.objects.filter(
                advertiser=advertiser,
                spend_date__gte=timezone.now().date() - timedelta(days=7)
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # Compare with previous period
            previous_spend = SpendRecord.objects.filter(
                advertiser=advertiser,
                spend_date__gte=timezone.now().date() - timedelta(days=14),
                spend_date__lt=timezone.now().date() - timedelta(days=7)
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            if previous_spend > 0:
                spend_change = (recent_spend - previous_spend) / previous_spend * 100
                
                if spend_change > 50:
                    alerts.append({
                        'type': 'spend_spike',
                        'severity': 'high',
                        'message': f'Spend increased by {spend_change:.1f}% compared to previous week',
                        'current_spend': float(recent_spend),
                        'previous_spend': float(previous_spend),
                        'change_percentage': float(spend_change)
                    })
                elif spend_change < -50:
                    alerts.append({
                        'type': 'spend_drop',
                        'severity': 'medium',
                        'message': f'Spend decreased by {abs(spend_change):.1f}% compared to previous week',
                        'current_spend': float(recent_spend),
                        'previous_spend': float(previous_spend),
                        'change_percentage': float(spend_change)
                    })
            
            # Check for zero spend
            if recent_spend == 0:
                alerts.append({
                    'type': 'no_spend',
                    'severity': 'medium',
                    'message': 'No spend recorded in the last 7 days',
                    'current_spend': 0,
                    'days_inactive': 7
                })
            
            # Check daily spend limits
            today_spend = SpendRecord.objects.filter(
                advertiser=advertiser,
                spend_date=timezone.now().date()
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # Get daily budget (mock implementation)
            daily_budget = advertiser.total_spend / 30  # Simple calculation
            
            if daily_budget > 0 and today_spend > daily_budget * 1.5:
                alerts.append({
                    'type': 'daily_budget_exceeded',
                    'severity': 'high',
                    'message': f'Daily spend exceeded budget by {((today_spend / daily_budget - 1) * 100):.1f}%',
                    'today_spend': float(today_spend),
                    'daily_budget': float(daily_budget),
                    'over_percentage': float((today_spend / daily_budget - 1) * 100)
                })
            
            return alerts
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting spend alerts {advertiser_id}: {str(e)}")
            return []
    
    @staticmethod
    def _check_spend_alerts(advertiser: Advertiser, spend_record: SpendRecord) -> None:
        """Check and create spend alerts."""
        try:
            # Check daily spend threshold
            daily_spend = SpendRecord.objects.filter(
                advertiser=advertiser,
                spend_date=spend_record.spend_date
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # Get spend alerts configuration
            alerts = SpendAlert.objects.filter(
                advertiser=advertiser,
                is_active=True
            )
            
            for alert_config in alerts:
                if alert_config.alert_type == 'daily_spend' and daily_spend >= alert_config.threshold:
                    Notification.objects.create(
                        advertiser=advertiser,
                        user=advertiser.user,
                        title='Daily Spend Alert',
                        message=f'Daily spend has exceeded threshold: {daily_spend}',
                        notification_type='spend',
                        priority='medium',
                        channels=['in_app']
                    )
                
                elif alert_config.alert_type == 'unusual_spend':
                    # Check for unusual spend patterns
                    avg_daily_spend = SpendRecord.objects.filter(
                        advertiser=advertiser,
                        spend_date__gte=spend_record.spend_date - timedelta(days=7),
                        spend_date__lt=spend_record.spend_date
                    ).aggregate(avg=Avg('amount'))['avg'] or Decimal('0.00')
                    
                    if avg_daily_spend > 0 and daily_spend > avg_daily_spend * 2:
                        Notification.objects.create(
                            advertiser=advertiser,
                            user=advertiser.user,
                            title='Unusual Spend Alert',
                            message=f'Unusual spend pattern detected: {daily_spend}',
                            notification_type='spend',
                            priority='high',
                            channels=['in_app', 'email']
                        )
            
        except Exception as e:
            logger.error(f"Error checking spend alerts: {str(e)}")
    
    @staticmethod
    def _linear_forecast(historical_data: List[Dict[str, Any]], periods: int) -> List[Dict[str, Any]]:
        """Linear forecast based on historical data."""
        try:
            if len(historical_data) < 2:
                return []
            
            # Calculate slope and intercept
            x_values = list(range(len(historical_data)))
            y_values = [float(item['total_amount']) for item in historical_data]
            
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
            last_date = historical_data[-1]['date']
            
            for i in range(1, periods + 1):
                forecast_date = last_date + timedelta(days=i)
                forecast_value = slope * (len(historical_data) + i) + intercept
                
                forecast.append({
                    'date': forecast_date.isoformat(),
                    'forecast_amount': max(0, forecast_value),  # Ensure non-negative
                    'confidence_lower': max(0, forecast_value * 0.8),
                    'confidence_upper': forecast_value * 1.2
                })
            
            return forecast
            
        except Exception as e:
            logger.error(f"Error in linear forecast: {str(e)}")
            return []
    
    @staticmethod
    def _exponential_forecast(historical_data: List[Dict[str, Any]], periods: int) -> List[Dict[str, Any]]:
        """Exponential forecast based on historical data."""
        try:
            if len(historical_data) < 2:
                return []
            
            # Calculate growth rate
            values = [float(item['total_amount']) for item in historical_data]
            growth_rates = []
            
            for i in range(1, len(values)):
                if values[i-1] > 0:
                    growth_rate = (values[i] - values[i-1]) / values[i-1]
                    growth_rates.append(growth_rate)
            
            if not growth_rates:
                return []
            
            avg_growth_rate = sum(growth_rates) / len(growth_rates)
            last_value = values[-1]
            
            # Generate forecast
            forecast = []
            last_date = historical_data[-1]['date']
            
            for i in range(1, periods + 1):
                forecast_date = last_date + timedelta(days=i)
                forecast_value = last_value * ((1 + avg_growth_rate) ** i)
                
                forecast.append({
                    'date': forecast_date.isoformat(),
                    'forecast_amount': max(0, forecast_value),
                    'confidence_lower': max(0, forecast_value * 0.7),
                    'confidence_upper': forecast_value * 1.3
                })
            
            return forecast
            
        except Exception as e:
            logger.error(f"Error in exponential forecast: {str(e)}")
            return []
    
    @staticmethod
    def _moving_average_forecast(historical_data: List[Dict[str, Any]], periods: int) -> List[Dict[str, Any]]:
        """Moving average forecast based on historical data."""
        try:
            if len(historical_data) < 7:
                return []
            
            # Calculate 7-day moving average
            moving_averages = []
            values = [float(item['total_amount']) for item in historical_data]
            
            for i in range(6, len(values)):
                avg = sum(values[i-6:i+1]) / 7
                moving_averages.append(avg)
            
            if not moving_averages:
                return []
            
            # Use last moving average as forecast
            last_avg = moving_averages[-1]
            
            # Generate forecast
            forecast = []
            last_date = historical_data[-1]['date']
            
            for i in range(1, periods + 1):
                forecast_date = last_date + timedelta(days=i)
                
                forecast.append({
                    'date': forecast_date.isoformat(),
                    'forecast_amount': last_avg,
                    'confidence_lower': last_avg * 0.9,
                    'confidence_upper': last_avg * 1.1
                })
            
            return forecast
            
        except Exception as e:
            logger.error(f"Error in moving average forecast: {str(e)}")
            return []
    
    @staticmethod
    def _calculate_forecast_confidence(historical_data: List[Dict[str, Any]]) -> float:
        """Calculate forecast confidence score."""
        try:
            if len(historical_data) < 7:
                return 0.5  # Low confidence for insufficient data
            
            values = [float(item['total_amount']) for item in historical_data]
            
            # Calculate variance
            mean = sum(values) / len(values)
            variance = sum((x - mean) ** 2 for x in values) / len(values)
            std_dev = variance ** 0.5
            
            # Calculate coefficient of variation
            cv = (std_dev / mean) if mean > 0 else float('inf')
            
            # Convert to confidence score (lower CV = higher confidence)
            if cv <= 0.1:
                return 0.9
            elif cv <= 0.2:
                return 0.8
            elif cv <= 0.3:
                return 0.7
            elif cv <= 0.5:
                return 0.6
            else:
                return 0.5
            
        except Exception as e:
            logger.error(f"Error calculating forecast confidence: {str(e)}")
            return 0.5
    
    @staticmethod
    def _calculate_efficiency_score(cpm: float, cpc: float, cpa: float) -> float:
        """Calculate overall efficiency score."""
        try:
            # Industry benchmarks (mock values)
            industry_cpm = 2.5
            industry_cpc = 1.5
            industry_cpa = 20.0
            
            # Calculate individual scores (lower is better for cost metrics)
            cpm_score = max(0, 100 - (cpm / industry_cpm * 100))
            cpc_score = max(0, 100 - (cpc / industry_cpc * 100))
            cpa_score = max(0, 100 - (cpa / industry_cpa * 100))
            
            # Weighted average
            efficiency_score = (cpm_score * 0.3 + cpc_score * 0.3 + cpa_score * 0.4)
            
            return round(efficiency_score, 2)
            
        except Exception as e:
            logger.error(f"Error calculating efficiency score: {str(e)}")
            return 50.0
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def get_spend_statistics() -> Dict[str, Any]:
        """Get spend statistics across all advertisers."""
        try:
            # Get total spend statistics
            total_spend = SpendRecord.objects.aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
            
            # Get spend by type
            spend_by_type = SpendRecord.objects.values('spend_type').annotate(
                total_amount=Sum('amount'),
                count=Count('id')
            )
            
            # Get monthly spend trend
            monthly_spend = SpendRecord.objects.extra(
                {'month': 'DATE_TRUNC(\'month\', spend_date)'}
            ).values('month').annotate(
                total_amount=Sum('amount')
            ).order_by('-month')[:12]
            
            # Get top spenders
            top_spenders = SpendRecord.objects.values('advertiser__company_name').annotate(
                total_amount=Sum('amount')
            ).order_by('-total_amount')[:10]
            
            return {
                'total_spend': float(total_spend),
                'spend_by_type': list(spend_by_type),
                'monthly_spend': [
                    {
                        'month': str(item['month']),
                        'total_amount': float(item['total_amount'])
                    }
                    for item in monthly_spend
                ],
                'top_spenders': [
                    {
                        'advertiser': item['advertiser__company_name'],
                        'total_amount': float(item['total_amount'])
                    }
                    for item in top_spenders
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting spend statistics: {str(e)}")
            return {
                'total_spend': 0,
                'spend_by_type': [],
                'monthly_spend': [],
                'top_spenders': []
            }
