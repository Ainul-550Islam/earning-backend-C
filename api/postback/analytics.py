"""
analytics.py – Advanced analytics engine for postback module.

Provides comprehensive analytics functionality including:
- Real-time analytics processing
- Advanced metrics calculation
- Trend analysis and forecasting
- Custom analytics reports
"""
from django.db.models import When
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict
from dataclasses import dataclass, field

from django.utils import timezone
from django.db import models
from django.db.models import Q, Count, Sum, Avg, Max, Min, F, Expression, FloatField
from django.core.cache import cache
from django.contrib.auth import get_user_model

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .exceptions import PostbackException

logger = logging.getLogger(__name__)
User = get_user_model()


class AnalyticsEngine:
    """
    Advanced analytics engine for postback data.
    
    Provides comprehensive analytics capabilities including
    real-time processing, trend analysis, and forecasting.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.metrics_calculators = self._setup_metric_calculators()
        self.analyzers = self._setup_analyzers()
        self.forecasters = self._setup_forecasters()
    
    def _setup_metric_calculators(self) -> Dict[str, Callable]:
        """Setup metric calculators."""
        return {
            'conversion_rate': self._calculate_conversion_rate,
            'revenue_metrics': self._calculate_revenue_metrics,
            'performance_metrics': self._calculate_performance_metrics,
            'user_engagement': self._calculate_user_engagement,
            'network_health': self._calculate_network_health,
            'anomaly_metrics': self._calculate_anomaly_metrics,
        }
    
    def _setup_analyzers(self) -> Dict[str, Callable]:
        """Setup analyzers."""
        return {
            'trend_analysis': self._analyze_trends,
            'pattern_detection': self._detect_patterns,
            'correlation_analysis': self._analyze_correlations,
            'segmentation': self._analyze_segments,
            'funnel_analysis': self._analyze_funnels,
        }
    
    def _setup_forecasters(self) -> Dict[str, Callable]:
        """Setup forecasters."""
        return {
            'volume_forecast': self._forecast_volume,
            'revenue_forecast': self._forecast_revenue,
            'trend_forecast': self._forecast_trends,
        }
    
    def calculate_metrics(self, metric_type: str, start_date: datetime = None, 
                        end_date: datetime = None, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Calculate specific metrics.
        
        Args:
            metric_type: Type of metric to calculate
            start_date: Start date for calculation
            end_date: End date for calculation
            filters: Additional filters
            
        Returns:
            Calculated metrics
        """
        if metric_type not in self.metrics_calculators:
            raise PostbackException(f"Unknown metric type: {metric_type}")
        
        calculator = self.metrics_calculators[metric_type]
        return calculator(start_date, end_date, filters)
    
    def analyze_data(self, analysis_type: str, data: Any = None, 
                     start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        """
        Analyze data using specified analysis type.
        
        Args:
            analysis_type: Type of analysis
            data: Data to analyze
            start_date: Start date
            end_date: End date
            
        Returns:
            Analysis results
        """
        if analysis_type not in self.analyzers:
            raise PostbackException(f"Unknown analysis type: {analysis_type}")
        
        analyzer = self.analyzers[analysis_type]
        return analyzer(data, start_date, end_date)
    
    def forecast(self, forecast_type: str, historical_data: List[Dict[str, Any]] = None,
                  forecast_period: int = 30) -> Dict[str, Any]:
        """
        Generate forecasts.
        
        Args:
            forecast_type: Type of forecast
            historical_data: Historical data points
            forecast_period: Number of periods to forecast
            
        Returns:
            Forecast results
        """
        if forecast_type not in self.forecasters:
            raise PostbackException(f"Unknown forecast type: {forecast_type}")
        
        forecaster = self.forecasters[forecast_type]
        return forecaster(historical_data, forecast_period)
    
    def generate_comprehensive_report(self, start_date: datetime = None, 
                                   end_date: datetime = None, include_forecasts: bool = True) -> Dict[str, Any]:
        """
        Generate comprehensive analytics report.
        
        Args:
            start_date: Start date
            end_date: End date
            include_forecasts: Whether to include forecasts
            
        Returns:
            Comprehensive report
        """
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        report = {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': (end_date - start_date).days,
            },
            'metrics': {},
            'analysis': {},
            'forecasts': {},
            'generated_at': timezone.now().isoformat(),
        }
        
        # Calculate all metrics
        for metric_type in self.metrics_calculators.keys():
            try:
                report['metrics'][metric_type] = self.calculate_metrics(
                    metric_type, start_date, end_date
                )
            except Exception as e:
                self.logger.error(f"Error calculating {metric_type}: {str(e)}")
                report['metrics'][metric_type] = {'error': str(e)}
        
        # Run all analyses
        for analysis_type in self.analyzers.keys():
            try:
                report['analysis'][analysis_type] = self.analyze_data(
                    analysis_type, start_date=start_date, end_date=end_date
                )
            except Exception as e:
                self.logger.error(f"Error in {analysis_type}: {str(e)}")
                report['analysis'][analysis_type] = {'error': str(e)}
        
        # Generate forecasts
        if include_forecasts:
            for forecast_type in self.forecasters.keys():
                try:
                    report['forecasts'][forecast_type] = self.forecast(forecast_type, forecast_period=30)
                except Exception as e:
                    self.logger.error(f"Error in {forecast_type}: {str(e)}")
                    report['forecasts'][forecast_type] = {'error': str(e)}
        
        return report
    
    def _calculate_conversion_rate(self, start_date: datetime = None, 
                                 end_date: datetime = None, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Calculate conversion rate metrics."""
        queryset = PostbackLog.objects.all()
        
        if start_date and end_date:
            queryset = queryset.filter(received_at__gte=start_date, received_at__lte=end_date)
        
        if filters:
            for field, value in filters.items():
                if field == 'network_key':
                    queryset = queryset.filter(network__network_key=value)
                elif field == 'status':
                    if isinstance(value, list):
                        queryset = queryset.filter(status__in=value)
                    else:
                        queryset = queryset.filter(status=value)
        
        # Calculate conversion rates
        total_count = queryset.count()
        if total_count == 0:
            return {
                'overall_rate': 0.0,
                'total_postbacks': 0,
                'rewarded_count': 0,
                'rejected_count': 0,
                'failed_count': 0,
                'by_network': {},
                'by_date': {},
            }
        
        rewarded_count = queryset.filter(status='rewarded').count()
        rejected_count = queryset.filter(status='rejected').count()
        failed_count = queryset.filter(status='failed').count()
        
        overall_rate = (rewarded_count / total_count) * 100
        
        # By network
        network_stats = queryset.values('network__network_key').annotate(
            total=Count('id'),
            rewarded=Count(models.Case(When(status='rewarded', then=1), default=0, output_field=models.IntegerField())),
        )
        
        by_network = {}
        for stat in network_stats:
            network_key = stat['network__network_key']
            rate = (stat['rewarded'] / stat['total']) * 100 if stat['total'] > 0 else 0
            by_network[network_key] = {
                'total': stat['total'],
                'rewarded': stat['rewarded'],
                'rate': rate,
            }
        
        # By date
        date_stats = queryset.extra(
            {'date': models.TruncDate('received_at')}
        ).values('date').annotate(
            total=Count('id'),
            rewarded=Count(models.Case(When(status='rewarded', then=1), default=0, output_field=models.IntegerField())),
        ).order_by('date')
        
        by_date = {}
        for stat in date_stats:
            date_str = stat['date'].isoformat()
            rate = (stat['rewarded'] / stat['total']) * 100 if stat['total'] > 0 else 0
            by_date[date_str] = {
                'total': stat['total'],
                'rewarded': stat['rewarded'],
                'rate': rate,
            }
        
        return {
            'overall_rate': round(overall_rate, 2),
            'total_postbacks': total_count,
            'rewarded_count': rewarded_count,
            'rejected_count': rejected_count,
            'failed_count': failed_count,
            'by_network': by_network,
            'by_date': by_date,
        }
    
    def _calculate_revenue_metrics(self, start_date: datetime = None, 
                                end_date: datetime = None, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Calculate revenue metrics."""
        queryset = PostbackLog.objects.filter(status='rewarded')
        
        if start_date and end_date:
            queryset = queryset.filter(received_at__gte=start_date, received_at__lte=end_date)
        
        if filters:
            for field, value in filters.items():
                if field == 'network_key':
                    queryset = queryset.filter(network__network_key=value)
        
        # Revenue calculations
        revenue_stats = queryset.aggregate(
            total_revenue=Sum('payout'),
            avg_payout=Avg('payout'),
            max_payout=Max('payout'),
            min_payout=Min('payout'),
            total_transactions=Count('id'),
        )
        
        # Revenue by network
        network_revenue = queryset.values('network__network_key').annotate(
            revenue=Sum('payout'),
            transactions=Count('id'),
            avg_payout=Avg('payout')
        ).order_by('-revenue')
        
        # Revenue by date
        daily_revenue = queryset.extra(
            {'date': models.TruncDate('received_at')}
        ).values('date').annotate(
            revenue=Sum('payout'),
            transactions=Count('id'),
            avg_payout=Avg('payout')
        ).order_by('date')
        
        return {
            'total_revenue': float(revenue_stats['total_revenue'] or 0),
            'avg_payout': float(revenue_stats['avg_payout'] or 0),
            'max_payout': float(revenue_stats['max_payout'] or 0),
            'min_payout': float(revenue_stats['min_payout'] or 0),
            'total_transactions': revenue_stats['total_transactions'],
            'by_network': [
                {
                    'network_key': item['network__network_key'],
                    'revenue': float(item['revenue'] or 0),
                    'transactions': item['transactions'],
                    'avg_payout': float(item['avg_payout'] or 0),
                }
                for item in network_revenue
            ],
            'by_date': [
                {
                    'date': item['date'].isoformat(),
                    'revenue': float(item['revenue'] or 0),
                    'transactions': item['transactions'],
                    'avg_payout': float(item['avg_payout'] or 0),
                }
                for item in daily_revenue
            ],
        }
    
    def _calculate_performance_metrics(self, start_date: datetime = None, 
                                   end_date: datetime = None, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Calculate performance metrics."""
        queryset = PostbackLog.objects.all()
        
        if start_date and end_date:
            queryset = queryset.filter(received_at__gte=start_date, received_at__lte=end_date)
        
        if filters:
            for field, value in filters.items():
                if field == 'network_key':
                    queryset = queryset.filter(network__network_key=value)
        
        # Processing time metrics
        processing_times = queryset.annotate(
            processing_time=models.ExpressionWrapper(
                models.F('processed_at') - models.F('received_at'),
                output_field=models.DurationField()
            )
        ).aggregate(
            avg_processing_time=Avg('processing_time'),
            max_processing_time=Max('processing_time'),
            min_processing_time=Min('processing_time'),
        )
        
        # Volume metrics
        volume_stats = queryset.extra(
            {'hour': models.TruncHour('received_at')}
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
        
        hourly_volumes = [item['count'] for item in volume_stats]
        
        # Calculate performance indicators
        avg_hourly_volume = sum(hourly_volumes) / len(hourly_volumes) if hourly_volumes else 0
        peak_hour = max(hourly_volumes) if hourly_volumes else 0
        volume_variance = self._calculate_variance(hourly_volumes) if len(hourly_volumes) > 1 else 0
        
        return {
            'avg_processing_time': str(processing_times['avg_processing_time'] or timedelta(0)),
            'max_processing_time': str(processing_times['max_processing_time'] or timedelta(0)),
            'min_processing_time': str(processing_times['min_processing_time'] or timedelta(0)),
            'avg_hourly_volume': round(avg_hourly_volume, 2),
            'peak_hour_volume': peak_hour,
            'volume_variance': round(volume_variance, 2),
            'total_processed': queryset.count(),
        }
    
    def _calculate_user_engagement(self, start_date: datetime = None, 
                                 end_date: datetime = None, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Calculate user engagement metrics."""
        queryset = PostbackLog.objects.filter(resolved_user__isnull=False)
        
        if start_date and end_date:
            queryset = queryset.filter(received_at__gte=start_date, received_at__lte=end_date)
        
        # User engagement metrics
        user_stats = queryset.values('resolved_user').annotate(
            postback_count=Count('id'),
            rewarded_count=Count(models.Case(When(status='rewarded', then=1), default=0, output_field=models.IntegerField())),
            total_payout=Sum('payout'),
        )
        
        # Calculate engagement metrics
        total_users = user_stats.count()
        active_users = user_stats.filter(postback_count__gte=5).count()
        
        if total_users == 0:
            return {
                'total_users': 0,
                'active_users': 0,
                'avg_postbacks_per_user': 0,
                'avg_payout_per_user': 0,
                'engagement_rate': 0,
                'user_segments': {},
            }
        
        # User segments
        user_segments = {
            'high_value': 0,    # High payout users
            'frequent': 0,      # Frequent users
            'new': 0,           # New users
            'churned': 0,       # Inactive users
        }
        
        for user in user_stats:
            if user['total_payout'] and user['total_payout'] > 100:
                user_segments['high_value'] += 1
            
            if user['postback_count'] >= 10:
                user_segments['frequent'] += 1
            elif user['postback_count'] <= 2:
                user_segments['new'] += 1
            else:
                user_segments['churned'] += 1
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'avg_postbacks_per_user': round(user_stats.aggregate(avg=Avg('postback_count'))['avg'] or 0, 2),
            'avg_payout_per_user': round(float(user_stats.aggregate(avg=Avg('total_payout'))['avg'] or 0), 2),
            'engagement_rate': round((active_users / total_users) * 100, 2),
            'user_segments': user_segments,
        }
    
    def _calculate_network_health(self, start_date: datetime = None, 
                               end_date: datetime = None, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Calculate network health metrics."""
        insights = PostbackInsight.objects.all()
        
        if start_date and end_date:
            insights = insights.filter(date__gte=start_date.date(), date__lte=end_date.date())
        
        # Health score distribution
        health_scores = list(insights.values_list('health_score', flat=True))
        
        if not health_scores:
            return {
                'avg_health_score': 0,
                'health_distribution': {},
                'anomaly_insights': 0,
                'network_health': {},
            }
        
        avg_health_score = sum(health_scores) / len(health_scores)
        
        # Health distribution
        health_distribution = {
            'excellent': len([s for s in health_scores if s >= 90]),
            'good': len([s for s in health_scores if 70 <= s < 90]),
            'fair': len([s for s in health_scores if 50 <= s < 70]),
            'poor': len([s for s in health_scores if s < 50]),
        }
        
        # Anomaly insights
        anomaly_insights = insights.filter(anomaly_detected=True).count()
        
        # Network-specific health
        network_health = insights.values('network__network_key', 'health_score').annotate(
            avg_score=Avg('health_score'),
            anomaly_count=Count(models.Case(When(anomaly_detected=True, then=1), default=0, output_field=models.IntegerField())),
        )
        
        return {
            'avg_health_score': round(avg_health_score, 2),
            'health_distribution': health_distribution,
            'anomaly_insights': anomaly_insights,
            'network_health': {
                item['network__network_key']: {
                    'avg_score': float(item['avg_score']),
                    'anomaly_count': item['anomaly_count'],
                }
                for item in network_health
            },
        }
    
    def _calculate_anomaly_metrics(self, start_date: datetime = None, 
                                 end_date: datetime = None, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Calculate anomaly metrics."""
        insights = PostbackInsight.objects.filter(anomaly_detected=True)
        
        if start_date and end_date:
            insights = insights.filter(date__gte=start_date.date(), date__lte=end_date.date())
        
        # Anomaly types
        anomaly_types = defaultdict(int)
        for insight in insights:
            if insight.anomaly_details:
                anomalies = insight.anomaly_details.get('anomalies', [])
                for anomaly in anomalies:
                    anomaly_type = anomaly.get('type', 'unknown')
                    anomaly_types[anomaly_type] += 1
        
        # Anomaly trends
        anomaly_trends = insights.extra(
            {'date': models.TruncDate('date')}
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        return {
            'total_anomalies': insights.count(),
            'anomaly_types': dict(anomaly_types),
            'anomaly_trends': [
                {
                    'date': item['date'].isoformat(),
                    'count': item['count'],
                }
                for item in anomaly_trends
            ],
            'most_common_type': max(anomaly_types.items(), key=lambda x: x[1])[0] if anomaly_types else None,
        }
    
    def _analyze_trends(self, data: Any = None, start_date: datetime = None, 
                        end_date: datetime = None) -> Dict[str, Any]:
        """Analyze trends in the data."""
        if not start_date or not end_date:
            return {'error': 'Start date and end date required for trend analysis'}
        
        # Get daily postback counts
        daily_counts = PostbackLog.objects.extra(
            {'date': models.TruncDate('received_at')}
        ).values('date').annotate(
            count=Count('id')
        ).filter(date__gte=start_date.date(), date__lte=end_date.date()).order_by('date')
        
        counts = [item['count'] for item in daily_counts]
        dates = [item['date'] for item in daily_counts]
        
        if len(counts) < 2:
            return {'error': 'Insufficient data for trend analysis'}
        
        # Calculate trend
        trend_direction = self._calculate_trend_direction(counts)
        trend_strength = self._calculate_trend_strength(counts)
        
        # Calculate growth rate
        growth_rate = self._calculate_growth_rate(counts)
        
        return {
            'trend_direction': trend_direction,
            'trend_strength': trend_strength,
            'growth_rate': growth_rate,
            'data_points': len(counts),
            'daily_data': [
                {
                    'date': dates[i].isoformat(),
                    'count': counts[i],
                }
                for i in range(len(counts))
            ],
        }
    
    def _detect_patterns(self, data: Any = None, start_date: datetime = None, 
                          end_date: datetime = None) -> Dict[str, Any]:
        """Detect patterns in the data."""
        patterns = {
            'seasonal_patterns': [],
            'cyclical_patterns': [],
            'anomaly_patterns': [],
            'recurring_patterns': [],
        }
        
        # Detect seasonal patterns (day of week)
        dow_patterns = PostbackLog.objects.extra(
            {'dow': models.Extract(models.F('received_at'), 'dow')}
        ).values('dow').annotate(
            count=Count('id')
        ).order_by('dow')
        
        dow_counts = [item['count'] for item in dow_patterns]
        if len(dow_counts) == 7:
            avg_count = sum(dow_counts) / 7
            for i, count in enumerate(dow_counts):
                if count > avg_count * 1.5:  # 50% above average
                    patterns['seasonal_patterns'].append({
                        'type': 'day_of_week',
                        'day': i,
                        'count': count,
                        'avg_count': avg_count,
                        'strength': round((count / avg_count - 1) * 100, 2),
                    })
        
        # Detect cyclical patterns (hourly)
        hourly_patterns = PostbackLog.objects.extra(
            {'hour': models.Extract(models.F('received_at'), 'hour')}
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
        
        hourly_counts = [item['count'] for item in hourly_patterns]
        if len(hourly_counts) == 24:
            avg_count = sum(hourly_counts) / 24
            for i, count in enumerate(hourly_counts):
                if count > avg_count * 2:  # 100% above average
                    patterns['cyclical_patterns'].append({
                        'type': 'hourly',
                        'hour': i,
                        'count': count,
                        'avg_count': avg_count,
                        'strength': round((count / avg_count - 1) * 100, 2),
                    })
        
        return patterns
    
    def _analyze_correlations(self, data: Any = None, start_date: datetime = None, 
                           end_date: datetime = None) -> Dict[str, Any]:
        """Analyze correlations between different metrics."""
        correlations = {}
        
        # Correlation between payout and reward rate
        network_correlations = PostbackLog.objects.values('network__network_key').annotate(
            total_count=Count('id'),
            rewarded_count=Count(models.Case(When(status='rewarded', then=1), default=0, output_field=models.IntegerField())),
            avg_payout=Avg('payout'),
        )
        
        for item in network_correlations:
            network_key = item['network__network_key']
            reward_rate = (item['rewarded_count'] / item['total_count']) * 100 if item['total_count'] > 0 else 0
            correlations[network_key] = {
                'reward_rate': reward_rate,
                'avg_payout': float(item['avg_payout'] or 0),
                'correlation_strength': 'high' if reward_rate > 70 and item['avg_payout'] > 5 else 'low',
            }
        
        return correlations
    
    def _analyze_segments(self, data: Any = None, start_date: datetime = None, 
                        end_date: datetime = None) -> Dict[str, Any]:
        """Analyze user or network segments."""
        segments = {
            'high_value_networks': [],
            'high_volume_networks': [],
            'problematic_networks': [],
            'user_segments': {},
        }
        
        # High value networks (high average payout)
        high_value = PostbackLog.objects.values('network__network_key').annotate(
            avg_payout=Avg('payout'),
            total_count=Count('id'),
        ).filter(avg_payout__gt=10).order_by('-avg_payout')[:10]
        
        segments['high_value_networks'] = [
            {
                'network_key': item['network__network_key'],
                'avg_payout': float(item['avg_payout']),
                'total_count': item['total_count'],
            }
            for item in high_value
        ]
        
        # High volume networks
        high_volume = PostbackLog.objects.values('network__network_key').annotate(
            total_count=Count('id'),
        ).filter(total_count__gt=1000).order_by('-total_count')[:10]
        
        segments['high_volume_networks'] = [
            {
                'network_key': item['network__network_key'],
                'total_count': item['total_count'],
            }
            for item in high_volume
        ]
        
        # Problematic networks (low health score)
        problematic_networks = PostbackInsight.objects.filter(
            health_score__lt=50
        ).values('network__network_key', 'health_score').order_by('health_score')[:10]
        
        segments['problematic_networks'] = [
            {
                'network_key': item['network__network_key'],
                'health_score': float(item['health_score']),
            }
            for item in problematic_networks
        ]
        
        return segments
    
    def _analyze_funnels(self, data: Any = None, start_date: datetime = None, 
                       end_date: datetime = None) -> Dict[str, Any]:
        """Analyze conversion funnels."""
        funnel_stages = [
            'received',
            'processed',
            'rewarded',
        ]
        
        funnel_data = {}
        
        for stage in funnel_stages:
            if stage == 'received':
                count = PostbackLog.objects.all().count()
            elif stage == 'processed':
                count = PostbackLog.objects.exclude(status='failed').count()
            elif stage == 'rewarded':
                count = PostbackLog.objects.filter(status='rewarded').count()
            
            funnel_data[stage] = count
        
        # Calculate conversion rates between stages
        conversion_rates = {}
        total = funnel_data.get('received', 1)
        
        for i, stage in enumerate(funnel_stages[1:], 1):
            prev_stage = funnel_stages[i-1]
            prev_count = funnel_data.get(prev_stage, 0)
            current_count = funnel_data.get(stage, 0)
            
            if prev_count > 0:
                conversion_rates[f'{prev_stage}_to_{stage}'] = (current_count / prev_count) * 100
        
        return {
            'stages': funnel_stages,
            'counts': funnel_data,
            'conversion_rates': conversion_rates,
            'overall_conversion': (funnel_data.get('rewarded', 0) / funnel_data.get('received', 1)) * 100,
        }
    
    def _forecast_volume(self, historical_data: List[Dict[str, Any]] = None, 
                        forecast_period: int = 30) -> Dict[str, Any]:
        """Forecast volume using historical data."""
        if not historical_data:
            # Get historical data if not provided
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=90)
            
            daily_data = PostbackLog.objects.extra(
                {'date': models.TruncDate('received_at')}
            ).values('date').annotate(
                count=Count('id')
            ).filter(date__gte=start_date, date__lte=end_date).order_by('date')
            
            historical_data = [
                {'date': item['date'].isoformat(), 'count': item['count']}
                for item in daily_data
            ]
        
        if len(historical_data) < 7:
            return {'error': 'Insufficient historical data for forecasting'}
        
        # Simple linear regression forecast
        counts = [item['count'] for item in historical_data]
        
        # Calculate trend
        x = list(range(len(counts)))
        n = len(counts)
        
        sum_x = sum(x)
        sum_y = sum(counts)
        sum_xy = sum(x[i] * counts[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))
        
        # Calculate slope (trend)
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2) if (n * sum_x2 - sum_x ** 2) != 0 else 0
        
        # Calculate intercept
        intercept = (sum_y - slope * sum_x) / n
        
        # Generate forecast
        forecast = []
        for i in range(forecast_period):
            future_x = len(counts) + i
            predicted_value = slope * future_x + intercept
            forecast.append(max(0, int(predicted_value)))  # Ensure non-negative
        
        # Calculate confidence intervals (simple approach)
        avg_value = sum(counts) / len(counts)
        std_dev = self._calculate_standard_deviation(counts)
        
        return {
            'forecast_period': forecast_period,
            'historical_period': len(historical_data),
            'forecast': forecast,
            'trend': slope,
            'intercept': intercept,
            'confidence_interval': {
                'upper': [int(val + 2 * std_dev) for val in forecast],
                'lower': [max(0, int(val - 2 * std_dev)) for val in forecast],
            },
            'accuracy_metrics': {
                'mape': self._calculate_mape(counts, [int(slope * i + intercept) for i in range(len(counts))]),
                'rmse': self._calculate_rmse(counts, [int(slope * i + intercept) for i in range(len(counts))]),
            },
        }
    
    def _forecast_revenue(self, historical_data: List[Dict[str, Any]] = None, 
                         forecast_period: int = 30) -> Dict[str, Any]:
        """Forecast revenue using historical data."""
        # Similar to volume forecast but for revenue
        if not historical_data:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=90)
            
            daily_revenue = PostbackLog.objects.filter(status='rewarded').extra(
                {'date': models.TruncDate('received_at')}
            ).values('date').annotate(
                revenue=Sum('payout')
            ).filter(date__gte=start_date, date__lte=end_date).order_by('date')
            
            historical_data = [
                {'date': item['date'].isoformat(), 'revenue': float(item['revenue'] or 0)}
                for item in daily_revenue
            ]
        
        if len(historical_data) < 7:
            return {'error': 'Insufficient historical data for revenue forecasting'}
        
        revenues = [item['revenue'] for item in historical_data]
        
        # Apply same forecasting logic as volume
        return self._forecast_volume(historical_data, forecast_period)
    
    def _forecast_trends(self, historical_data: List[Dict[str, Any]] = None, 
                         forecast_period: int = 30) -> Dict[str, Any]:
        """Forecast trends."""
        # This would implement more sophisticated trend forecasting
        # For now, return a simple trend forecast
        volume_forecast = self._forecast_volume(historical_data, forecast_period)
        
        # Determine trend direction
        forecast_values = volume_forecast.get('forecast', [])
        if len(forecast_values) > 1:
            first_half = forecast_values[:len(forecast_values)//2]
            second_half = forecast_values[len(forecast_values)//2:]
            
            first_avg = sum(first_half) / len(first_half) if first_half else 0
            second_avg = sum(second_half) / len(second_half) if second_half else 0
            
            trend_direction = 'increasing' if second_avg > first_avg else 'decreasing'
        else:
            trend_direction = 'stable'
        
        return {
            'trend_direction': trend_direction,
            'volume_forecast': volume_forecast,
            'confidence': 'medium',  # Would calculate based on historical accuracy
        }
    
    def _calculate_trend_direction(self, values: List[float]) -> str:
        """Calculate trend direction."""
        if len(values) < 2:
            return 'insufficient_data'
        
        # Simple linear trend
        x = list(range(len(values)))
        n = len(values)
        
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum(x[i] ** 2 for i in range(n)) - sum_x ** 2) if (n * sum(x[i] ** 2 for i in range(n)) - sum_x ** 2) != 0 else 0
        
        if slope > 0.1:
            return 'increasing'
        elif slope < -0.1:
            return 'decreasing'
        else:
            return 'stable'
    
    def _calculate_trend_strength(self, values: List[float]) -> float:
        """Calculate trend strength (R-squared)."""
        if len(values) < 3:
            return 0.0
        
        x = list(range(len(values)))
        n = len(values)
        
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))
        sum_y2 = sum(values[i] ** 2 for i in range(n))
        
        # Calculate R-squared
        numerator = (n * sum_xy - sum_x * sum_y) ** 2
        denominator = (n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)
        
        return numerator / denominator if denominator != 0 else 0
    
    def _calculate_growth_rate(self, values: List[float]) -> float:
        """Calculate growth rate."""
        if len(values) < 2:
            return 0.0
        
        first_value = values[0]
        last_value = values[-1]
        
        if first_value == 0:
            return 0.0
        
        return ((last_value - first_value) / first_value) * 100
    
    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance."""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)
    
    def _calculate_standard_deviation(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        return (self._calculate_variance(values)) ** 0.5
    
    def _calculate_mape(self, actual: List[float], predicted: List[float]) -> float:
        """Calculate Mean Absolute Percentage Error."""
        if len(actual) != len(predicted) or len(actual) == 0:
            return 0.0
        
        total_error = 0
        for a, p in zip(actual, predicted):
            if a != 0:
                total_error += abs((a - p) / a) * 100
        
        return total_error / len(actual)
    
    def _calculate_rmse(self, actual: List[float], predicted: List[float]) -> float:
        """Calculate Root Mean Square Error."""
        if len(actual) != len(predicted) or len(actual) == 0:
            return 0.0
        
        squared_errors = [(a - p) ** 2 for a, p in zip(actual, predicted)]
        return (sum(squared_errors) / len(actual)) ** 0.5


# Global analytics engine instance
analytics_engine = AnalyticsEngine()


# Convenience functions
def calculate_conversion_rate(start_date: datetime = None, end_date: datetime = None, 
                           filters: Dict[str, Any] = None) -> Dict[str, Any]:
    """Calculate conversion rate metrics."""
    return analytics_engine.calculate_metrics('conversion_rate', start_date, end_date, filters)


def calculate_revenue_metrics(start_date: datetime = None, end_date: datetime = None, 
                             filters: Dict[str, Any] = None) -> Dict[str, Any]:
    """Calculate revenue metrics."""
    return analytics_engine.calculate_metrics('revenue_metrics', start_date, end_date, filters)


def analyze_trends(start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
    """Analyze trends."""
    return analytics_engine.analyze_data('trend_analysis', start_date=start_date, end_date=end_date)


def detect_patterns(start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
    """Detect patterns."""
    return analytics_engine.analyze_data('pattern_detection', start_date=start_date, end_date=end_date)


def forecast_volume(forecast_period: int = 30) -> Dict[str, Any]:
    """Forecast volume."""
    return analytics_engine.forecast('volume_forecast', forecast_period=forecast_period)


def generate_comprehensive_report(start_date: datetime = None, end_date: datetime = None, 
                                 include_forecasts: bool = True) -> Dict[str, Any]:
    """Generate comprehensive analytics report."""
    return analytics_engine.generate_comprehensive_report(start_date, end_date, include_forecasts)


# Analytics utilities
def get_real_time_metrics() -> Dict[str, Any]:
    """Get real-time metrics for dashboard."""
    now = timezone.now()
    one_hour_ago = now - timedelta(hours=1)
    
    return {
        'last_hour': {
            'total_postbacks': PostbackLog.objects.filter(received_at__gte=one_hour_ago).count(),
            'rewarded_postbacks': PostbackLog.objects.filter(received_at__gte=one_hour_ago, status='rewarded').count(),
            'rejected_postbacks': PostbackLog.objects.filter(received_at__gte=one_hour_ago, status='rejected').count(),
            'total_revenue': float(PostbackLog.objects.filter(received_at__gte=one_hour_ago, status='rewarded').aggregate(total=Sum('payout'))['total'] or 0),
        },
        'current_status': {
            'active_networks': NetworkPostbackConfig.objects.filter(is_active=True).count(),
            'total_users': User.objects.filter(is_active=True).count(),
            'anomaly_count': PostbackInsight.objects.filter(anomaly_detected=True).count(),
        },
    }


def get_network_performance(network_key: str, days: int = 30) -> Dict[str, Any]:
    """Get network performance analytics."""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    return {
        'metrics': analytics_engine.calculate_metrics('conversion_rate', start_date, end_date, {'network_key': network_key}),
        'revenue': analytics_engine.calculate_metrics('revenue_metrics', start_date, end_date, {'network_key': network_key}),
        'health': analytics_engine.calculate_metrics('network_health', start_date, end_date, {'network_key': network_key}),
    }


def get_user_analytics(user_id: int, days: int = 30) -> Dict[str, Any]:
    """Get user-specific analytics."""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    return {
        'engagement': analytics_engine.calculate_metrics('user_engagement', start_date, end_date, {'user_id': user_id}),
        'postback_history': list(
            PostbackLog.objects.filter(
                resolved_user_id=user_id,
                received_at__gte=start_date,
                received_at__lte=end_date
            ).values('lead_id', 'status', 'payout', 'received_at').order_by('-received_at')
        ),
    }


# Analytics health check
def check_analytics_health() -> Dict[str, Any]:
    """Check analytics system health."""
    health_status = {
        'overall': 'healthy',
        'analytics_engine': 'healthy',
        'components': {},
        'issues': [],
    }
    
    # Test analytics engine
    try:
        # Test metric calculation
        metrics = analytics_engine.calculate_metrics('conversion_rate')
        health_status['analytics_engine'] = 'healthy'
        health_status['components']['metric_calculators'] = 'healthy'
    except Exception as e:
        health_status['analytics_engine'] = 'error'
        health_status['components']['metric_calculators'] = 'error'
        health_status['issues'].append(f"Analytics engine error: {str(e)}")
    
    if health_status['issues']:
        health_status['overall'] = 'unhealthy'
    
    return health_status
