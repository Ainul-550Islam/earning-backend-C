"""
Advertiser Performance Management

This module handles performance tracking, analysis, and optimization
for advertisers including KPI monitoring, performance scoring, and insights.
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
from ..database_models.performance_model import PerformanceMetric, PerformanceScore, PerformanceAlert
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class AdvertiserPerformanceService:
    """Service for managing advertiser performance operations."""
    
    @staticmethod
    def track_performance(advertiser_id: UUID, performance_data: Dict[str, Any],
                         tracked_by: Optional[User] = None) -> PerformanceMetric:
        """Track performance metrics for advertiser."""
        try:
            advertiser = AdvertiserPerformanceService.get_advertiser(advertiser_id)
            
            # Validate performance data
            metric_type = performance_data.get('metric_type')
            if not metric_type:
                raise AdvertiserValidationError("metric_type is required")
            
            valid_metric_types = ['impressions', 'clicks', 'conversions', 'revenue', 'ctr', 'cpc', 'cpa', 'roas', 'quality_score']
            if metric_type not in valid_metric_types:
                raise AdvertiserValidationError(f"Invalid metric_type. Must be one of: {', '.join(valid_metric_types)}")
            
            value = performance_data.get('value')
            if value is None:
                raise AdvertiserValidationError("value is required")
            
            with transaction.atomic():
                # Create performance metric
                performance_metric = PerformanceMetric.objects.create(
                    advertiser=advertiser,
                    campaign_id=performance_data.get('campaign_id'),
                    creative_id=performance_data.get('creative_id'),
                    metric_type=metric_type,
                    value=Decimal(str(value)),
                    unit=performance_data.get('unit', 'count'),
                    metric_date=performance_data.get('metric_date', date.today()),
                    dimensions=performance_data.get('dimensions', {}),
                    metadata=performance_data.get('metadata', {}),
                    created_by=tracked_by
                )
                
                # Update performance score
                AdvertiserPerformanceService._update_performance_score(advertiser, performance_metric)
                
                # Check performance alerts
                AdvertiserPerformanceService._check_performance_alerts(advertiser, performance_metric)
                
                # Log tracking
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='track_performance',
                    object_type='PerformanceMetric',
                    object_id=str(performance_metric.id),
                    user=tracked_by,
                    advertiser=advertiser,
                    description=f"Tracked {metric_type}: {value}"
                )
                
                return performance_metric
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error tracking performance {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to track performance: {str(e)}")
    
    @staticmethod
    def get_performance_summary(advertiser_id: UUID, date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        try:
            advertiser = AdvertiserPerformanceService.get_advertiser(advertiser_id)
            
            # Default date range (last 30 days)
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=30)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            # Get performance metrics
            metrics = AdvertiserPerformanceService._get_performance_metrics(advertiser, start_date, end_date)
            
            # Calculate derived metrics
            derived_metrics = AdvertiserPerformanceService._calculate_derived_metrics(metrics)
            
            # Get performance score
            performance_score = AdvertiserPerformanceService._get_current_performance_score(advertiser)
            
            # Get performance trends
            trends = AdvertiserPerformanceService._get_performance_trends(advertiser, start_date, end_date)
            
            return {
                'advertiser_id': str(advertiser_id),
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'performance_metrics': metrics,
                'derived_metrics': derived_metrics,
                'performance_score': performance_score,
                'trends': trends,
                'generated_at': timezone.now().isoformat()
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting performance summary {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get performance summary: {str(e)}")
    
    @staticmethod
    def get_performance_kpis(advertiser_id: UUID, kpi_types: Optional[List[str]] = None,
                            date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get specific KPI performance."""
        try:
            advertiser = AdvertiserPerformanceService.get_advertiser(advertiser_id)
            
            # Default KPI types
            if not kpi_types:
                kpi_types = ['impressions', 'clicks', 'conversions', 'ctr', 'cpc', 'cpa', 'roas']
            
            # Default date range (last 30 days)
            if not date_range:
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=30)
            else:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
            
            kpis = {}
            
            for kpi_type in kpi_types:
                metrics = PerformanceMetric.objects.filter(
                    advertiser=advertiser,
                    metric_type=kpi_type,
                    metric_date__gte=start_date,
                    metric_date__lte=end_date
                ).order_by('metric_date')
                
                if metrics.exists():
                    # Calculate KPI statistics
                    values = [float(metric.value) for metric in metrics]
                    
                    kpis[kpi_type] = {
                        'current_value': values[-1] if values else 0,
                        'average_value': sum(values) / len(values),
                        'min_value': min(values),
                        'max_value': max(values),
                        'trend': AdvertiserPerformanceService._calculate_trend(values),
                        'daily_values': [
                            {
                                'date': metric.metric_date.isoformat(),
                                'value': float(metric.value)
                            }
                            for metric in metrics
                        ]
                    }
                else:
                    kpis[kpi_type] = {
                        'current_value': 0,
                        'average_value': 0,
                        'min_value': 0,
                        'max_value': 0,
                        'trend': 'stable',
                        'daily_values': []
                    }
            
            return {
                'advertiser_id': str(advertiser_id),
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'kpis': kpis,
                'generated_at': timezone.now().isoformat()
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting performance KPIs {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get performance KPIs: {str(e)}")
    
    @staticmethod
    def get_performance_comparison(advertiser_id: UUID, comparison_type: str = 'industry',
                                   date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get performance comparison against benchmarks."""
        try:
            advertiser = AdvertiserPerformanceService.get_advertiser(advertiser_id)
            
            # Get current performance
            current_performance = AdvertiserPerformanceService.get_performance_summary(advertiser_id, date_range)
            
            # Get benchmarks based on comparison type
            if comparison_type == 'industry':
                benchmarks = AdvertiserPerformanceService._get_industry_benchmarks(advertiser.industry)
            elif comparison_type == 'historical':
                benchmarks = AdvertiserPerformanceService._get_historical_benchmarks(advertiser, date_range)
            elif comparison_type == 'competitor':
                benchmarks = AdvertiserPerformanceService._get_competitor_benchmarks(advertiser)
            else:
                raise AdvertiserValidationError("Invalid comparison_type. Use 'industry', 'historical', or 'competitor'")
            
            # Calculate comparison metrics
            comparison_metrics = {}
            
            for metric_name, current_value in current_performance['derived_metrics'].items():
                if metric_name in benchmarks:
                    benchmark_value = benchmarks[metric_name]
                    
                    if benchmark_value > 0:
                        performance_ratio = (current_value / benchmark_value) * 100
                        performance_gap = current_value - benchmark_value
                        
                        if performance_ratio >= 120:
                            performance_level = 'excellent'
                        elif performance_ratio >= 100:
                            performance_level = 'good'
                        elif performance_ratio >= 80:
                            performance_level = 'fair'
                        else:
                            performance_level = 'poor'
                    else:
                        performance_ratio = 0
                        performance_gap = 0
                        performance_level = 'unknown'
                    
                    comparison_metrics[metric_name] = {
                        'current_value': current_value,
                        'benchmark_value': benchmark_value,
                        'performance_ratio': performance_ratio,
                        'performance_gap': performance_gap,
                        'performance_level': performance_level
                    }
            
            return {
                'advertiser_id': str(advertiser_id),
                'comparison_type': comparison_type,
                'date_range': date_range or {
                    'start_date': (timezone.now().date() - timedelta(days=30)).isoformat(),
                    'end_date': timezone.now().date().isoformat()
                },
                'comparison_metrics': comparison_metrics,
                'benchmarks': benchmarks,
                'overall_performance': AdvertiserPerformanceService._calculate_overall_performance_level(comparison_metrics),
                'generated_at': timezone.now().isoformat()
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting performance comparison {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get performance comparison: {str(e)}")
    
    @staticmethod
    def get_performance_insights(advertiser_id: UUID) -> List[Dict[str, Any]]:
        """Get performance insights and recommendations."""
        try:
            advertiser = AdvertiserPerformanceService.get_advertiser(advertiser_id)
            
            insights = []
            
            # Get recent performance
            performance_summary = AdvertiserPerformanceService.get_performance_summary(advertiser_id)
            
            # Analyze CTR
            ctr = performance_summary['derived_metrics'].get('ctr', 0)
            if ctr < 1.0:
                insights.append({
                    'type': 'low_ctr',
                    'priority': 'high',
                    'title': 'Low Click-Through Rate',
                    'description': f'Your CTR is {ctr:.2f}%, which is below industry average.',
                    'metric': 'ctr',
                    'current_value': ctr,
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
                    'title': 'High Click-Through Rate',
                    'description': f'Your CTR is {ctr:.2f}%, which is excellent!',
                    'metric': 'ctr',
                    'current_value': ctr,
                    'recommendations': [
                        'Consider increasing budget for high-CTR campaigns',
                        'Scale successful ad variations',
                        'Test higher bids for better placement'
                    ]
                })
            
            # Analyze CPC
            cpc = performance_summary['derived_metrics'].get('cpc', 0)
            if cpc > 3.0:
                insights.append({
                    'type': 'high_cpc',
                    'priority': 'high',
                    'title': 'High Cost Per Click',
                    'description': f'Your CPC is ${cpc:.2f}, which is above optimal range.',
                    'metric': 'cpc',
                    'current_value': cpc,
                    'recommendations': [
                        'Optimize bidding strategy',
                        'Improve quality score',
                        'Refine audience targeting',
                        'Test different ad placements'
                    ]
                })
            elif cpc < 0.5:
                insights.append({
                    'type': 'low_cpc',
                    'priority': 'medium',
                    'title': 'Low Cost Per Click',
                    'description': f'Your CPC is ${cpc:.2f}, which is excellent!',
                    'metric': 'cpc',
                    'current_value': cpc,
                    'recommendations': [
                        'Increase bids for better placement',
                        'Scale successful campaigns',
                        'Test higher-value keywords'
                    ]
                })
            
            # Analyze CPA
            cpa = performance_summary['derived_metrics'].get('cpa', 0)
            if cpa > 50.0:
                insights.append({
                    'type': 'high_cpa',
                    'priority': 'critical',
                    'title': 'High Cost Per Acquisition',
                    'description': f'Your CPA is ${cpa:.2f}, which is significantly above target.',
                    'metric': 'cpa',
                    'current_value': cpa,
                    'recommendations': [
                        'Optimize landing page experience',
                        'Improve conversion rate',
                        'Refine audience targeting',
                        'Pause underperforming campaigns'
                    ]
                })
            elif cpa < 10.0:
                insights.append({
                    'type': 'low_cpa',
                    'priority': 'medium',
                    'title': 'Excellent Cost Per Acquisition',
                    'description': f'Your CPA is ${cpa:.2f}, which is outstanding!',
                    'metric': 'cpa',
                    'current_value': cpa,
                    'recommendations': [
                        'Scale successful campaigns',
                        'Increase budget allocation',
                        'Expand to similar audiences'
                    ]
                })
            
            # Analyze ROAS
            roas = performance_summary['derived_metrics'].get('roas', 0)
            if roas < 1.0:
                insights.append({
                    'type': 'negative_roas',
                    'priority': 'critical',
                    'title': 'Negative Return on Ad Spend',
                    'description': f'Your ROAS is {roas:.2f}x, meaning you\'re losing money.',
                    'metric': 'roas',
                    'current_value': roas,
                    'recommendations': [
                        'Pause all campaigns immediately',
                        'Review bidding strategy',
                        'Optimize conversion tracking',
                        'Reassess campaign objectives'
                    ]
                })
            elif roas > 5.0:
                insights.append({
                    'type': 'excellent_roas',
                    'priority': 'medium',
                    'title': 'Excellent Return on Ad Spend',
                    'description': f'Your ROAS is {roas:.2f}x, which is exceptional!',
                    'metric': 'roas',
                    'current_value': roas,
                    'recommendations': [
                        'Increase budget significantly',
                        'Scale to new channels',
                        'Test higher bids for premium placements'
                    ]
                })
            
            # Analyze performance trends
            trends = performance_summary.get('trends', {})
            for metric, trend_data in trends.items():
                if trend_data.get('trend') == 'declining' and trend_data.get('change_percentage', 0) < -20:
                    insights.append({
                        'type': 'declining_trend',
                        'priority': 'high',
                        'title': f'Declining {metric.upper()} Trend',
                        'description': f'{metric.upper()} has declined by {abs(trend_data.get("change_percentage", 0)):.1f}% recently.',
                        'metric': metric,
                        'current_value': trend_data.get('current_value', 0),
                        'recommendations': [
                            f'Investigate {metric} decline causes',
                            'Optimize campaign settings',
                            'Test new strategies'
                        ]
                    })
            
            return insights
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting performance insights {advertiser_id}: {str(e)}")
            return []
    
    @staticmethod
    def get_performance_alerts(advertiser_id: UUID) -> List[Dict[str, Any]]:
        """Get active performance alerts."""
        try:
            advertiser = AdvertiserPerformanceService.get_advertiser(advertiser_id)
            
            alerts = []
            
            # Get active performance alerts
            performance_alerts = PerformanceAlert.objects.filter(
                advertiser=advertiser,
                is_active=True,
                resolved_at__isnull=True
            ).order_by('-created_at')
            
            for alert in performance_alerts:
                alerts.append({
                    'id': str(alert.id),
                    'alert_type': alert.alert_type,
                    'severity': alert.severity,
                    'title': alert.title,
                    'description': alert.description,
                    'metric': alert.metric_type,
                    'threshold': float(alert.threshold),
                    'current_value': float(alert.current_value),
                    'created_at': alert.created_at.isoformat(),
                    'resolved_at': alert.resolved_at.isoformat() if alert.resolved_at else None
                })
            
            # Check for real-time alerts
            realtime_alerts = AdvertiserPerformanceService._check_realtime_alerts(advertiser)
            alerts.extend(realtime_alerts)
            
            return alerts
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting performance alerts {advertiser_id}: {str(e)}")
            return []
    
    @staticmethod
    def update_performance_score(advertiser_id: UUID, score_data: Dict[str, Any],
                                 updated_by: Optional[User] = None) -> PerformanceScore:
        """Update performance score for advertiser."""
        try:
            advertiser = AdvertiserPerformanceService.get_advertiser(advertiser_id)
            
            with transaction.atomic():
                # Calculate performance score
                score_components = AdvertiserPerformanceService._calculate_score_components(advertiser)
                overall_score = sum(score_components.values()) / len(score_components)
                
                # Create performance score record
                performance_score = PerformanceScore.objects.create(
                    advertiser=advertiser,
                    overall_score=overall_score,
                    components=score_components,
                    score_date=score_data.get('score_date', date.today()),
                    calculation_method=score_data.get('calculation_method', 'weighted_average'),
                    metadata=score_data.get('metadata', {}),
                    created_by=updated_by
                )
                
                # Update advertiser quality score
                advertiser.quality_score = overall_score
                advertiser.save(update_fields=['quality_score'])
                
                # Send notification for significant score changes
                previous_score = PerformanceScore.objects.filter(
                    advertiser=advertiser
                ).order_by('-score_date').first()
                
                if previous_score and abs(overall_score - previous_score.overall_score) > 20:
                    Notification.objects.create(
                        advertiser=advertiser,
                        user=updated_by,
                        title='Significant Performance Score Change',
                        message=f'Your performance score changed from {previous_score.overall_score:.1f} to {overall_score:.1f}.',
                        notification_type='performance',
                        priority='medium',
                        channels=['in_app']
                    )
                
                # Log score update
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='update_performance_score',
                    object_type='PerformanceScore',
                    object_id=str(performance_score.id),
                    user=updated_by,
                    advertiser=advertiser,
                    description=f"Updated performance score: {overall_score:.1f}"
                )
                
                return performance_score
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error updating performance score {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to update performance score: {str(e)}")
    
    @staticmethod
    def _get_performance_metrics(advertiser: Advertiser, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get performance metrics for date range."""
        try:
            metrics = {}
            
            # Get basic metrics
            for metric_type in ['impressions', 'clicks', 'conversions', 'revenue']:
                queryset = PerformanceMetric.objects.filter(
                    advertiser=advertiser,
                    metric_type=metric_type,
                    metric_date__gte=start_date,
                    metric_date__lte=end_date
                )
                
                total = queryset.aggregate(total=Sum('value'))['total'] or Decimal('0.00')
                metrics[metric_type] = float(total)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {str(e)}")
            return {'impressions': 0, 'clicks': 0, 'conversions': 0, 'revenue': 0}
    
    @staticmethod
    def _calculate_derived_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate derived metrics from basic metrics."""
        try:
            derived = {}
            
            impressions = metrics.get('impressions', 0)
            clicks = metrics.get('clicks', 0)
            conversions = metrics.get('conversions', 0)
            revenue = metrics.get('revenue', 0)
            
            # Calculate CTR
            derived['ctr'] = (clicks / impressions * 100) if impressions > 0 else 0
            
            # Calculate CPC
            derived['cpc'] = (revenue / clicks) if clicks > 0 else 0
            
            # Calculate CPA
            derived['cpa'] = (revenue / conversions) if conversions > 0 else 0
            
            # Calculate ROAS
            derived['roas'] = (revenue / (revenue / clicks if clicks > 0 else 0)) if clicks > 0 else 0
            
            # Calculate conversion rate
            derived['conversion_rate'] = (conversions / clicks * 100) if clicks > 0 else 0
            
            return derived
            
        except Exception as e:
            logger.error(f"Error calculating derived metrics: {str(e)}")
            return {}
    
    @staticmethod
    def _get_current_performance_score(advertiser: Advertiser) -> Optional[Dict[str, Any]]:
        """Get current performance score."""
        try:
            score = PerformanceScore.objects.filter(advertiser=advertiser).order_by('-score_date').first()
            
            if score:
                return {
                    'overall_score': float(score.overall_score),
                    'components': score.components,
                    'score_date': score.score_date.isoformat()
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting current performance score: {str(e)}")
            return None
    
    @staticmethod
    def _get_performance_trends(advertiser: Advertiser, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get performance trends."""
        try:
            trends = {}
            
            # Get trends for key metrics
            for metric_type in ['ctr', 'cpc', 'cpa', 'roas']:
                # Get recent and previous period data
                recent_metrics = PerformanceMetric.objects.filter(
                    advertiser=advertiser,
                    metric_type=metric_type,
                    metric_date__gte=end_date - timedelta(days=7),
                    metric_date__lte=end_date
                )
                
                previous_metrics = PerformanceMetric.objects.filter(
                    advertiser=advertiser,
                    metric_type=metric_type,
                    metric_date__gte=end_date - timedelta(days=14),
                    metric_date__lt=end_date - timedelta(days=7)
                )
                
                recent_avg = recent_metrics.aggregate(avg=Avg('value'))['avg'] or 0
                previous_avg = previous_metrics.aggregate(avg=Avg('value'))['avg'] or 0
                
                if previous_avg > 0:
                    change_percentage = ((recent_avg - previous_avg) / previous_avg) * 100
                    if change_percentage > 5:
                        trend = 'increasing'
                    elif change_percentage < -5:
                        trend = 'declining'
                    else:
                        trend = 'stable'
                else:
                    change_percentage = 0
                    trend = 'stable'
                
                trends[metric_type] = {
                    'current_value': float(recent_avg),
                    'previous_value': float(previous_avg),
                    'change_percentage': change_percentage,
                    'trend': trend
                }
            
            return trends
            
        except Exception as e:
            logger.error(f"Error getting performance trends: {str(e)}")
            return {}
    
    @staticmethod
    def _calculate_trend(values: List[float]) -> str:
        """Calculate trend from values."""
        try:
            if len(values) < 2:
                return 'stable'
            
            # Compare last value with average of previous values
            last_value = values[-1]
            previous_avg = sum(values[:-1]) / len(values[:-1])
            
            if previous_avg == 0:
                return 'stable'
            
            change_percentage = ((last_value - previous_avg) / previous_avg) * 100
            
            if change_percentage > 5:
                return 'increasing'
            elif change_percentage < -5:
                return 'declining'
            else:
                return 'stable'
                
        except Exception as e:
            logger.error(f"Error calculating trend: {str(e)}")
            return 'stable'
    
    @staticmethod
    def _get_industry_benchmarks(industry: str) -> Dict[str, Any]:
        """Get industry performance benchmarks."""
        try:
            # Mock industry benchmarks
            benchmarks = {
                'technology': {
                    'ctr': 2.5,
                    'cpc': 2.0,
                    'cpa': 25.0,
                    'roas': 3.0
                },
                'retail': {
                    'ctr': 1.8,
                    'cpc': 1.5,
                    'cpa': 18.0,
                    'roas': 2.5
                },
                'finance': {
                    'ctr': 1.2,
                    'cpc': 3.0,
                    'cpa': 35.0,
                    'roas': 2.8
                },
                'healthcare': {
                    'ctr': 1.5,
                    'cpc': 2.5,
                    'cpa': 30.0,
                    'roas': 2.7
                }
            }
            
            return benchmarks.get(industry.lower(), {
                'ctr': 2.0,
                'cpc': 2.0,
                'cpa': 20.0,
                'roas': 2.5
            })
            
        except Exception as e:
            logger.error(f"Error getting industry benchmarks: {str(e)}")
            return {'ctr': 2.0, 'cpc': 2.0, 'cpa': 20.0, 'roas': 2.5}
    
    @staticmethod
    def _get_historical_benchmarks(advertiser: Advertiser, date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get historical benchmarks for advertiser."""
        try:
            # Get performance from previous period
            if date_range:
                start_date = date.fromisoformat(date_range['start_date'])
                end_date = date.fromisoformat(date_range['end_date'])
                period_length = (end_date - start_date).days
                previous_start = start_date - timedelta(days=period_length)
                previous_end = start_date
            else:
                previous_end = timezone.now().date() - timedelta(days=30)
                previous_start = previous_end - timedelta(days=30)
            
            previous_performance = AdvertiserPerformanceService.get_performance_summary(
                str(advertiser.id),
                {'start_date': previous_start.isoformat(), 'end_date': previous_end.isoformat()}
            )
            
            return previous_performance.get('derived_metrics', {})
            
        except Exception as e:
            logger.error(f"Error getting historical benchmarks: {str(e)}")
            return {}
    
    @staticmethod
    def _get_competitor_benchmarks(advertiser: Advertiser) -> Dict[str, Any]:
        """Get competitor benchmarks (mock implementation)."""
        try:
            # This would integrate with competitive intelligence service
            # For now, return industry benchmarks as proxy
            return AdvertiserPerformanceService._get_industry_benchmarks(advertiser.industry)
            
        except Exception as e:
            logger.error(f"Error getting competitor benchmarks: {str(e)}")
            return {'ctr': 2.0, 'cpc': 2.0, 'cpa': 20.0, 'roas': 2.5}
    
    @staticmethod
    def _calculate_overall_performance_level(comparison_metrics: Dict[str, Any]) -> str:
        """Calculate overall performance level."""
        try:
            if not comparison_metrics:
                return 'unknown'
            
            performance_levels = []
            
            for metric_name, metric_data in comparison_metrics.items():
                performance_levels.append(metric_data.get('performance_level', 'unknown'))
            
            # Count performance levels
            excellent_count = performance_levels.count('excellent')
            good_count = performance_levels.count('good')
            fair_count = performance_levels.count('fair')
            poor_count = performance_levels.count('poor')
            
            total_count = len(performance_levels)
            
            # Determine overall level
            if excellent_count / total_count >= 0.5:
                return 'excellent'
            elif (excellent_count + good_count) / total_count >= 0.7:
                return 'good'
            elif fair_count / total_count >= 0.5:
                return 'fair'
            else:
                return 'poor'
                
        except Exception as e:
            logger.error(f"Error calculating overall performance level: {str(e)}")
            return 'unknown'
    
    @staticmethod
    def _update_performance_score(advertiser: Advertiser, performance_metric: PerformanceMetric) -> None:
        """Update performance score based on new metric."""
        try:
            # This would trigger score recalculation
            # For now, just update advertiser quality score
            score_components = AdvertiserPerformanceService._calculate_score_components(advertiser)
            overall_score = sum(score_components.values()) / len(score_components)
            
            advertiser.quality_score = overall_score
            advertiser.save(update_fields=['quality_score'])
            
        except Exception as e:
            logger.error(f"Error updating performance score: {str(e)}")
    
    @staticmethod
    def _check_performance_alerts(advertiser: Advertiser, performance_metric: PerformanceMetric) -> None:
        """Check and create performance alerts."""
        try:
            # Get alert configurations
            alert_configs = PerformanceAlert.objects.filter(
                advertiser=advertiser,
                metric_type=performance_metric.metric_type,
                is_active=True
            )
            
            for config in alert_configs:
                if performance_metric.value <= config.threshold:
                    # Create alert
                    PerformanceAlert.objects.create(
                        advertiser=advertiser,
                        metric_type=performance_metric.metric_type,
                        alert_type=config.alert_type,
                        severity=config.severity,
                        title=f'{performance_metric.metric_type.title()} Alert',
                        description=f'{performance_metric.metric_type.title()} is below threshold: {performance_metric.value}',
                        threshold=config.threshold,
                        current_value=performance_metric.value
                    )
                    
                    # Send notification
                    Notification.objects.create(
                        advertiser=advertiser,
                        user=advertiser.user,
                        title=f'Performance Alert: {performance_metric.metric_type.title()}',
                        message=f'Your {performance_metric.metric_type} has dropped below the threshold.',
                        notification_type='performance',
                        priority='medium',
                        channels=['in_app']
                    )
            
        except Exception as e:
            logger.error(f"Error checking performance alerts: {str(e)}")
    
    @staticmethod
    def _check_realtime_alerts(advertiser: Advertiser) -> List[Dict[str, Any]]:
        """Check for real-time performance alerts."""
        try:
            alerts = []
            
            # Get today's performance
            today = timezone.now().date()
            today_metrics = PerformanceMetric.objects.filter(
                advertiser=advertiser,
                metric_date=today
            )
            
            # Check for zero impressions
            impressions = today_metrics.filter(metric_type='impressions').aggregate(total=Sum('value'))['total'] or 0
            if impressions == 0:
                alerts.append({
                    'type': 'no_impressions',
                    'severity': 'high',
                    'title': 'No Impressions Today',
                    'description': 'No impressions recorded today. Check campaign status.',
                    'metric': 'impressions',
                    'current_value': 0,
                    'created_at': timezone.now().isoformat()
                })
            
            # Check for zero clicks
            clicks = today_metrics.filter(metric_type='clicks').aggregate(total=Sum('value'))['total'] or 0
            if clicks == 0 and impressions > 0:
                alerts.append({
                    'type': 'no_clicks',
                    'severity': 'high',
                    'title': 'No Clicks Today',
                    'description': f'{impressions} impressions but no clicks. Review ad creatives.',
                    'metric': 'clicks',
                    'current_value': 0,
                    'created_at': timezone.now().isoformat()
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking realtime alerts: {str(e)}")
            return []
    
    @staticmethod
    def _calculate_score_components(advertiser: Advertiser) -> Dict[str, float]:
        """Calculate performance score components."""
        try:
            components = {}
            
            # Get recent performance
            performance_summary = AdvertiserPerformanceService.get_performance_summary(str(advertiser.id))
            derived_metrics = performance_summary.get('derived_metrics', {})
            
            # CTR component (0-100)
            ctr = derived_metrics.get('ctr', 0)
            components['ctr'] = min(100, ctr * 20)  # 5% CTR = 100 points
            
            # CPC component (0-100, lower is better)
            cpc = derived_metrics.get('cpc', 0)
            components['cpc'] = max(0, 100 - cpc * 20)  # $5 CPC = 0 points, $0 CPC = 100 points
            
            # CPA component (0-100, lower is better)
            cpa = derived_metrics.get('cpa', 0)
            components['cpa'] = max(0, 100 - cpa * 2)  # $50 CPA = 0 points, $0 CPA = 100 points
            
            # ROAS component (0-100)
            roas = derived_metrics.get('roas', 0)
            components['roas'] = min(100, roas * 20)  # 5x ROAS = 100 points
            
            return components
            
        except Exception as e:
            logger.error(f"Error calculating score components: {str(e)}")
            return {'ctr': 0, 'cpc': 0, 'cpa': 0, 'roas': 0}
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def get_performance_statistics() -> Dict[str, Any]:
        """Get performance statistics across all advertisers."""
        try:
            # Get total metrics
            total_metrics = PerformanceMetric.objects.aggregate(
                total_impressions=Sum('value', filter=Q(metric_type='impressions')),
                total_clicks=Sum('value', filter=Q(metric_type='clicks')),
                total_conversions=Sum('value', filter=Q(metric_type='conversions')),
                total_revenue=Sum('value', filter=Q(metric_type='revenue'))
            )
            
            # Calculate derived totals
            total_impressions = total_metrics['total_impressions'] or 0
            total_clicks = total_metrics['total_clicks'] or 0
            total_conversions = total_metrics['total_conversions'] or 0
            total_revenue = total_metrics['total_revenue'] or 0
            
            overall_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            overall_cpc = (total_revenue / total_clicks) if total_clicks > 0 else 0
            overall_cpa = (total_revenue / total_conversions) if total_conversions > 0 else 0
            overall_roas = (total_revenue / (total_revenue / total_clicks if total_clicks > 0 else 0)) if total_clicks > 0 else 0
            
            # Get performance score distribution
            score_distribution = PerformanceScore.objects.extra(
                {'score_range': "CASE WHEN overall_score >= 80 THEN 'excellent' WHEN overall_score >= 60 THEN 'good' WHEN overall_score >= 40 THEN 'fair' ELSE 'poor' END"}
            ).values('score_range').annotate(
                count=Count('id')
            )
            
            return {
                'total_metrics': {
                    'total_impressions': total_impressions,
                    'total_clicks': total_clicks,
                    'total_conversions': total_conversions,
                    'total_revenue': float(total_revenue)
                },
                'overall_performance': {
                    'ctr': overall_ctr,
                    'cpc': overall_cpc,
                    'cpa': overall_cpa,
                    'roas': overall_roas
                },
                'score_distribution': [
                    {
                        'score_range': item['score_range'],
                        'count': item['count']
                    }
                    for item in score_distribution
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting performance statistics: {str(e)}")
            return {
                'total_metrics': {'total_impressions': 0, 'total_clicks': 0, 'total_conversions': 0, 'total_revenue': 0},
                'overall_performance': {'ctr': 0, 'cpc': 0, 'cpa': 0, 'roas': 0},
                'score_distribution': []
            }
