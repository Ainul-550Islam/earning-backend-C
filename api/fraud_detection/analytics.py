# =============================================================================
# fraud_detection/analytics.py
# =============================================================================
"""
Analytics Layer for Fraud Detection System.

Provides comprehensive analytics, data processing, and reporting
functionality for fraud detection insights and dashboard graphs.
"""

from __future__ import annotations

import logging
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple
from collections import defaultdict
from dataclasses import dataclass
import statistics

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Count, Avg, Max, Min, Sum, Q, F
from django.db.models.functions import Trunc, TruncDate, TruncHour, TruncDay

from api.fraud_detection.repositories import (
    fraud_case_repository, fraud_alert_repository, fraud_risk_profile_repository,
    fraud_device_fingerprint_repository, fraud_suspicious_ip_repository
)
from api.fraud_detection.selectors import (
    fraud_case_selector, fraud_alert_selector, fraud_risk_profile_selector,
    fraud_device_fingerprint_selector, fraud_suspicious_ip_selector
)
from api.fraud_detection.encryption import generate_integrity_hash
from api.fraud_detection.exceptions import AnalyticsError
from api.fraud_detection.constants import DASHBOARD_CONFIG


logger = logging.getLogger(__name__)


@dataclass
class AnalyticsDataPoint:
    """Data class for analytics data points."""
    timestamp: datetime
    value: Union[int, float]
    label: str
    metadata: Optional[Dict[str, Any]] = None


class FraudAnalytics:
    """
    Comprehensive fraud analytics engine.
    
    Provides data processing, trend analysis, and reporting
    for fraud detection insights and dashboard visualization.
    """
    
    def __init__(self):
        """Initialize fraud analytics engine."""
        self.cache_ttl = getattr(settings, 'FRAUD_ANALYTICS_CACHE_TTL', 300)  # 5 minutes
        self.max_data_points = DASHBOARD_CONFIG.get('chart_data_points', 100)
        self.retention_days = getattr(settings, 'FRAUD_ANALYTICS_RETENTION_DAYS', 90)
        
        # Initialize analytics configuration
        self.analytics_config = self._load_analytics_config()
        self.report_templates = self._load_report_templates()
    
    def _load_analytics_config(self) -> Dict[str, Any]:
        """Load analytics configuration."""
        default_config = {
            'default_period_days': 30,
            'aggregation_intervals': ['hour', 'day', 'week', 'month'],
            'risk_score_buckets': [0, 20, 40, 60, 80, 100],
            'trend_analysis_periods': [7, 30, 90],
            'performance_metrics': ['response_time', 'detection_accuracy', 'false_positive_rate']
        }
        
        return getattr(settings, 'FRAUD_ANALYTICS_CONFIG', default_config)
    
    def _load_report_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load report templates."""
        default_templates = {
            'daily_summary': {
                'period': 'day',
                'metrics': ['cases', 'alerts', 'risk_scores'],
                'format': 'summary'
            },
            'weekly_trends': {
                'period': 'week',
                'metrics': ['trends', 'patterns', 'risk_distribution'],
                'format': 'trends'
            },
            'monthly_comprehensive': {
                'period': 'month',
                'metrics': ['all'],
                'format': 'comprehensive'
            }
        }
        
        return getattr(settings, 'FRAUD_REPORT_TEMPLATES', default_templates)
    
    def get_fraud_overview(self, period_days: int = None) -> Dict[str, Any]:
        """
        Get comprehensive fraud overview analytics.
        
        Args:
            period_days: Analysis period in days
            
        Returns:
            Fraud overview analytics data
        """
        if period_days is None:
            period_days = self.analytics_config['default_period_days']
        
        cache_key = f"fraud_overview_{period_days}d"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=period_days)
            
            overview_data = {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': period_days
                },
                'summary_statistics': self._get_summary_statistics(start_date, end_date),
                'risk_analysis': self._get_risk_analysis(start_date, end_date),
                'trend_analysis': self._get_trend_analysis(start_date, end_date),
                'geographic_analysis': self._get_geographic_analysis(start_date, end_date),
                'performance_metrics': self._get_performance_metrics(start_date, end_date),
                'case_analysis': self._get_case_analysis(start_date, end_date),
                'alert_analysis': self._get_alert_analysis(start_date, end_date)
            }
            
            # Cache the result
            cache.set(cache_key, overview_data, self.cache_ttl)
            
            return overview_data
            
        except Exception as e:
            logger.error(f"Failed to get fraud overview: {e}")
            raise AnalyticsError(f"Failed to get fraud overview: {e}")
    
    def get_risk_score_trends(self, period_days: int = 30, 
                              aggregation: str = 'day') -> List[AnalyticsDataPoint]:
        """
        Get risk score trends over time.
        
        Args:
            period_days: Analysis period
            aggregation: Aggregation interval (hour, day, week, month)
            
        Returns:
            List of risk score trend data points
        """
        cache_key = f"risk_trends_{period_days}d_{aggregation}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=period_days)
            
            # Get risk profiles within period
            risk_profiles = fraud_risk_profile_selector.list(
                filters={'last_updated__gte': start_date}
            )
            
            # Aggregate by specified interval
            trend_data = self._aggregate_temporal_data(
                risk_profiles, 'last_updated', 'risk_score', aggregation, start_date, end_date
            )
            
            # Convert to AnalyticsDataPoint objects
            data_points = [
                AnalyticsDataPoint(
                    timestamp=point['timestamp'],
                    value=point['value'],
                    label=point['timestamp'].strftime('%Y-%m-%d %H:%M' if aggregation == 'hour' else '%Y-%m-%d'),
                    metadata={'count': point['count']}
                )
                for point in trend_data
            ]
            
            # Cache the result
            cache.set(cache_key, data_points, self.cache_ttl)
            
            return data_points
            
        except Exception as e:
            logger.error(f"Failed to get risk score trends: {e}")
            raise AnalyticsError(f"Failed to get risk score trends: {e}")
    
    def get_fraud_case_trends(self, period_days: int = 30, 
                              aggregation: str = 'day') -> List[AnalyticsDataPoint]:
        """
        Get fraud case trends over time.
        
        Args:
            period_days: Analysis period
            aggregation: Aggregation interval
            
        Returns:
            List of fraud case trend data points
        """
        cache_key = f"case_trends_{period_days}d_{aggregation}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=period_days)
            
            # Get fraud cases within period
            fraud_cases = fraud_case_selector.list(
                filters={'created_at__gte': start_date}
            )
            
            # Aggregate by specified interval
            trend_data = self._aggregate_temporal_data(
                fraud_cases, 'created_at', 'risk_score', aggregation, start_date, end_date
            )
            
            # Convert to AnalyticsDataPoint objects
            data_points = [
                AnalyticsDataPoint(
                    timestamp=point['timestamp'],
                    value=point['count'],  # Number of cases
                    label=point['timestamp'].strftime('%Y-%m-%d %H:%M' if aggregation == 'hour' else '%Y-%m-%d'),
                    metadata={
                        'avg_risk_score': point['value'],
                        'max_risk_score': point.get('max_value', 0)
                    }
                )
                for point in trend_data
            ]
            
            # Cache the result
            cache.set(cache_key, data_points, self.cache_ttl)
            
            return data_points
            
        except Exception as e:
            logger.error(f"Failed to get fraud case trends: {e}")
            raise AnalyticsError(f"Failed to get fraud case trends: {e}")
    
    def get_alert_frequency_analysis(self, period_days: int = 7) -> Dict[str, Any]:
        """
        Get alert frequency analysis.
        
        Args:
            period_days: Analysis period
            
        Returns:
            Alert frequency analysis data
        """
        cache_key = f"alert_frequency_{period_days}d"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=period_days)
            
            # Get alerts within period
            alerts = fraud_alert_selector.list(
                filters={'created_at__gte': start_date}
            )
            
            # Analyze by type
            type_analysis = defaultdict(lambda: {'count': 0, 'total_severity': 0})
            for alert in alerts:
                alert_type = alert.alert_type or 'unknown'
                type_analysis[alert_type]['count'] += 1
                type_analysis[alert_type]['total_severity'] += alert.severity_score or 0
            
            # Calculate averages
            type_frequency = []
            for alert_type, data in type_analysis.items():
                avg_severity = data['total_severity'] / data['count'] if data['count'] > 0 else 0
                type_frequency.append({
                    'alert_type': alert_type,
                    'count': data['count'],
                    'average_severity': avg_severity,
                    'percentage': (data['count'] / len(alerts)) * 100 if alerts else 0
                })
            
            # Sort by frequency
            type_frequency.sort(key=lambda x: x['count'], reverse=True)
            
            # Hourly distribution
            hourly_distribution = defaultdict(int)
            for alert in alerts:
                hour = alert.created_at.hour
                hourly_distribution[hour] += 1
            
            # Fill missing hours with 0
            for hour in range(24):
                if hour not in hourly_distribution:
                    hourly_distribution[hour] = 0
            
            frequency_data = {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': period_days
                },
                'total_alerts': len(alerts),
                'type_frequency': type_frequency,
                'hourly_distribution': dict(hourly_distribution),
                'peak_hour': max(hourly_distribution, key=hourly_distribution.get) if hourly_distribution else 0,
                'alerts_per_day': len(alerts) / period_days if period_days > 0 else 0
            }
            
            # Cache the result
            cache.set(cache_key, frequency_data, self.cache_ttl)
            
            return frequency_data
            
        except Exception as e:
            logger.error(f"Failed to get alert frequency analysis: {e}")
            raise AnalyticsError(f"Failed to get alert frequency analysis: {e}")
    
    def get_device_fingerprint_analysis(self, period_days: int = 30) -> Dict[str, Any]:
        """
        Get device fingerprint analysis.
        
        Args:
            period_days: Analysis period
            
        Returns:
            Device fingerprint analysis data
        """
        cache_key = f"device_analysis_{period_days}d"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=period_days)
            
            # Get device fingerprints within period
            fingerprints = fraud_device_fingerprint_selector.list(
                filters={'last_seen__gte': start_date}
            )
            
            # Analyze multi-user devices
            multi_user_devices = [
                fp for fp in fingerprints if fp.user_count > 1
            ]
            
            # User count distribution
            user_count_distribution = defaultdict(int)
            for fp in fingerprints:
                user_count_distribution[fp.user_count] += 1
            
            # New devices per day
            daily_new_devices = defaultdict(int)
            for fp in fingerprints:
                day = fp.first_seen.date()
                daily_new_devices[day] += 1
            
            # Suspicious device patterns
            suspicious_devices = [
                fp for fp in fingerprints 
                if fp.user_count >= 3 or (hasattr(fp, 'risk_score') and getattr(fp, 'risk_score', 0) >= 70)
            ]
            
            analysis_data = {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': period_days
                },
                'total_devices': len(fingerprints),
                'multi_user_devices': len(multi_user_devices),
                'suspicious_devices': len(suspicious_devices),
                'user_count_distribution': dict(user_count_distribution),
                'daily_new_devices': {
                    date.isoformat(): count for date, count in daily_new_devices.items()
                },
                'multi_device_users': len([
                    user_count for user_count in user_count_distribution.keys() if user_count > 1
                ]),
                'average_users_per_device': sum(fp.user_count for fp in fingerprints) / len(fingerprints) if fingerprints else 0
            }
            
            # Cache the result
            cache.set(cache_key, analysis_data, self.cache_ttl)
            
            return analysis_data
            
        except Exception as e:
            logger.error(f"Failed to get device fingerprint analysis: {e}")
            raise AnalyticsError(f"Failed to get device fingerprint analysis: {e}")
    
    def generate_analytics_report(self, report_type: str, 
                                 period_days: int = None) -> Dict[str, Any]:
        """
        Generate comprehensive analytics report.
        
        Args:
            report_type: Type of report (daily_summary, weekly_trends, monthly_comprehensive)
            period_days: Analysis period (overrides template default)
            
        Returns:
            Generated report data
        """
        if report_type not in self.report_templates:
            raise AnalyticsError(f"Unknown report type: {report_type}")
        
        template = self.report_templates[report_type]
        
        if period_days is None:
            period_mapping = {'day': 1, 'week': 7, 'month': 30}
            period_days = period_mapping.get(template['period'], 30)
        
        try:
            report_data = {
                'report_type': report_type,
                'generated_at': timezone.now().isoformat(),
                'period_days': period_days,
                'template': template,
                'data': {}
            }
            
            # Generate required metrics
            metrics = template['metrics']
            
            if 'cases' in metrics or 'all' in metrics:
                report_data['data']['case_analysis'] = self._get_case_analysis(
                    timezone.now() - timedelta(days=period_days), timezone.now()
                )
            
            if 'alerts' in metrics or 'all' in metrics:
                report_data['data']['alert_analysis'] = self._get_alert_analysis(
                    timezone.now() - timedelta(days=period_days), timezone.now()
                )
            
            if 'risk_scores' in metrics or 'all' in metrics:
                report_data['data']['risk_analysis'] = self._get_risk_analysis(
                    timezone.now() - timedelta(days=period_days), timezone.now()
                )
            
            if 'trends' in metrics or 'all' in metrics:
                report_data['data']['trend_analysis'] = self._get_trend_analysis(
                    timezone.now() - timedelta(days=period_days), timezone.now()
                )
            
            if 'patterns' in metrics or 'all' in metrics:
                report_data['data']['pattern_analysis'] = self._get_pattern_analysis(
                    timezone.now() - timedelta(days=period_days), timezone.now()
                )
            
            if 'risk_distribution' in metrics or 'all' in metrics:
                report_data['data']['risk_distribution'] = self._get_risk_distribution()
            
            # Add report integrity hash
            report_data['integrity_hash'] = generate_integrity_hash(report_data)
            
            return report_data
            
        except Exception as e:
            logger.error(f"Failed to generate analytics report: {e}")
            raise AnalyticsError(f"Failed to generate analytics report: {e}")
    
    def _get_summary_statistics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get summary statistics for the period."""
        # Get cases and alerts in period
        cases = fraud_case_selector.list(
            filters={'created_at__gte': start_date, 'created_at__lte': end_date}
        )
        alerts = fraud_alert_selector.list(
            filters={'created_at__gte': start_date, 'created_at__lte': end_date}
        )
        
        # Calculate statistics
        total_cases = len(cases)
        total_alerts = len(alerts)
        
        high_risk_cases = len([case for case in cases if case.risk_score >= 70])
        critical_alerts = len([alert for alert in alerts if alert.severity_score >= 80])
        
        avg_case_risk = sum(case.risk_score for case in cases) / total_cases if total_cases > 0 else 0
        avg_alert_severity = sum(alert.severity_score for alert in alerts) / total_alerts if total_alerts > 0 else 0
        
        return {
            'total_cases': total_cases,
            'total_alerts': total_alerts,
            'high_risk_cases': high_risk_cases,
            'critical_alerts': critical_alerts,
            'average_case_risk_score': avg_case_risk,
            'average_alert_severity': avg_alert_severity,
            'cases_per_day': total_cases / ((end_date - start_date).days + 1),
            'alerts_per_day': total_alerts / ((end_date - start_date).days + 1)
        }
    
    def _get_risk_analysis(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get risk analysis for the period."""
        risk_profiles = fraud_risk_profile_selector.list(
            filters={'last_updated__gte': start_date, 'last_updated__lte': end_date}
        )
        
        if not risk_profiles:
            return {
                'total_profiles': 0,
                'risk_distribution': {'low': 0, 'medium': 0, 'high': 0, 'critical': 0},
                'average_risk_score': 0,
                'risk_score_trend': []
            }
        
        # Risk distribution
        distribution = {'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
        risk_scores = []
        
        for profile in risk_profiles:
            score = profile.risk_score
            risk_scores.append(score)
            
            if score >= 80:
                distribution['critical'] += 1
            elif score >= 60:
                distribution['high'] += 1
            elif score >= 40:
                distribution['medium'] += 1
            else:
                distribution['low'] += 1
        
        # Risk score statistics
        avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0
        max_risk = max(risk_scores) if risk_scores else 0
        min_risk = min(risk_scores) if risk_scores else 0
        
        return {
            'total_profiles': len(risk_profiles),
            'risk_distribution': distribution,
            'average_risk_score': avg_risk,
            'max_risk_score': max_risk,
            'min_risk_score': min_risk,
            'risk_score_statistics': {
                'median': statistics.median(risk_scores) if risk_scores else 0,
                'std_dev': statistics.stdev(risk_scores) if len(risk_scores) > 1 else 0
            }
        }
    
    def _get_trend_analysis(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get trend analysis for the period."""
        # Get daily trends
        daily_cases = defaultdict(int)
        daily_alerts = defaultdict(int)
        daily_risk_scores = defaultdict(list)
        
        cases = fraud_case_selector.list(
            filters={'created_at__gte': start_date, 'created_at__lte': end_date}
        )
        alerts = fraud_alert_selector.list(
            filters={'created_at__gte': start_date, 'created_at__lte': end_date}
        )
        
        for case in cases:
            day = case.created_at.date()
            daily_cases[day] += 1
            daily_risk_scores[day].append(case.risk_score)
        
        for alert in alerts:
            day = alert.created_at.date()
            daily_alerts[day] += 1
        
        # Calculate daily averages and trends
        trend_data = []
        current_date = start_date.date()
        
        while current_date <= end_date.date():
            cases_count = daily_cases.get(current_date, 0)
            alerts_count = daily_alerts.get(current_date, 0)
            day_risk_scores = daily_risk_scores.get(current_date, [])
            avg_risk = sum(day_risk_scores) / len(day_risk_scores) if day_risk_scores else 0
            
            trend_data.append({
                'date': current_date.isoformat(),
                'cases': cases_count,
                'alerts': alerts_count,
                'average_risk_score': avg_risk
            })
            
            current_date += timedelta(days=1)
        
        # Calculate trend directions
        if len(trend_data) > 1:
            case_trend = self._calculate_trend([point['cases'] for point in trend_data])
            alert_trend = self._calculate_trend([point['alerts'] for point in trend_data])
            risk_trend = self._calculate_trend([point['average_risk_score'] for point in trend_data])
        else:
            case_trend = alert_trend = risk_trend = 'stable'
        
        return {
            'daily_trends': trend_data,
            'trend_directions': {
                'cases': case_trend,
                'alerts': alert_trend,
                'risk_scores': risk_trend
            },
            'period_summary': {
                'total_days': len(trend_data),
                'peak_cases_day': max(trend_data, key=lambda x: x['cases'])['date'] if trend_data else None,
                'peak_alerts_day': max(trend_data, key=lambda x: x['alerts'])['date'] if trend_data else None
            }
        }
    
    def _get_geographic_analysis(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get geographic analysis (simplified)."""
        # In practice, this would analyze IP geolocation data
        # For now, return placeholder data
        
        return {
            'top_countries': [
                {'country': 'US', 'count': 150, 'risk_score': 45},
                {'country': 'GB', 'count': 80, 'risk_score': 38},
                {'country': 'CA', 'count': 60, 'risk_score': 42},
                {'country': 'AU', 'count': 40, 'risk_score': 35},
                {'country': 'DE', 'count': 35, 'risk_score': 40}
            ],
            'high_risk_regions': ['APAC', 'Eastern Europe'],
            'total_countries': 25,
            'international_percentage': 65.5
        }
    
    def _get_performance_metrics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get performance metrics."""
        # In practice, this would analyze system performance
        # For now, return placeholder data
        
        return {
            'detection_accuracy': 94.5,
            'false_positive_rate': 3.2,
            'average_response_time_ms': 250,
            'system_uptime_percentage': 99.8,
            'throughput_per_second': 1250
        }
    
    def _get_case_analysis(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get detailed case analysis."""
        cases = fraud_case_selector.list(
            filters={'created_at__gte': start_date, 'created_at__lte': end_date}
        )
        
        if not cases:
            return {
                'total_cases': 0,
                'status_distribution': {},
                'severity_distribution': {},
                'resolution_metrics': {}
            }
        
        # Status distribution
        status_counts = defaultdict(int)
        severity_counts = defaultdict(int)
        resolution_times = []
        
        for case in cases:
            status_counts[case.status] += 1
            severity_counts[case.severity] += 1
            
            if case.status == 'resolved' and hasattr(case, 'resolved_at') and case.resolved_at:
                resolution_time = (case.resolved_at - case.created_at).total_seconds()
                resolution_times.append(resolution_time)
        
        return {
            'total_cases': len(cases),
            'status_distribution': dict(status_counts),
            'severity_distribution': dict(severity_counts),
            'resolution_metrics': {
                'average_resolution_hours': sum(resolution_times) / len(resolution_times) / 3600 if resolution_times else 0,
                'resolved_cases': len([case for case in cases if case.status == 'resolved']),
                'resolution_rate': (len([case for case in cases if case.status == 'resolved']) / len(cases)) * 100 if cases else 0
            }
        }
    
    def _get_alert_analysis(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get detailed alert analysis."""
        alerts = fraud_alert_selector.list(
            filters={'created_at__gte': start_date, 'created_at__lte': end_date}
        )
        
        if not alerts:
            return {
                'total_alerts': 0,
                'type_distribution': {},
                'severity_distribution': {},
                'acknowledgment_rate': 0
            }
        
        # Type and severity distribution
        type_counts = defaultdict(int)
        severity_counts = defaultdict(int)
        acknowledged_count = 0
        
        for alert in alerts:
            type_counts[alert.alert_type] += 1
            severity_counts[alert.severity] += 1
            if alert.acknowledged:
                acknowledged_count += 1
        
        return {
            'total_alerts': len(alerts),
            'type_distribution': dict(type_counts),
            'severity_distribution': dict(severity_counts),
            'acknowledgment_rate': (acknowledged_count / len(alerts)) * 100 if alerts else 0,
            'unacknowledged_alerts': len(alerts) - acknowledged_count
        }
    
    def _get_pattern_analysis(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get pattern analysis."""
        # In practice, this would analyze fraud patterns
        # For now, return placeholder data
        
        return {
            'detected_patterns': [
                {'pattern': 'multi_account', 'frequency': 25, 'risk_level': 'high'},
                {'pattern': 'suspicious_timing', 'frequency': 18, 'risk_level': 'medium'},
                {'pattern': 'device_anomaly', 'frequency': 12, 'risk_level': 'medium'},
                {'pattern': 'geographic_anomaly', 'frequency': 8, 'risk_level': 'low'}
            ],
            'new_patterns_detected': 3,
            'pattern_accuracy': 87.5
        }
    
    def _get_risk_distribution(self) -> Dict[str, Any]:
        """Get current risk distribution."""
        risk_profiles = fraud_risk_profile_selector.list(limit=None)
        
        distribution = {'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
        
        for profile in risk_profiles:
            score = profile.risk_score
            if score >= 80:
                distribution['critical'] += 1
            elif score >= 60:
                distribution['high'] += 1
            elif score >= 40:
                distribution['medium'] += 1
            else:
                distribution['low'] += 1
        
        total = sum(distribution.values())
        
        return {
            'distribution': distribution,
            'percentages': {
                key: (count / total * 100) if total > 0 else 0
                for key, count in distribution.items()
            },
            'total_profiles': total
        }
    
    def _aggregate_temporal_data(self, queryset, date_field, value_field, 
                                aggregation, start_date, end_date) -> List[Dict[str, Any]]:
        """Aggregate temporal data by specified interval."""
        data_points = []
        
        # Group data by time interval
        grouped_data = defaultdict(lambda: {'values': [], 'count': 0})
        
        for item in queryset:
            date_value = getattr(item, date_field)
            value = getattr(item, value_field)
            
            if aggregation == 'hour':
                key = date_value.replace(minute=0, second=0, microsecond=0)
            elif aggregation == 'day':
                key = date_value.replace(hour=0, minute=0, second=0, microsecond=0)
            elif aggregation == 'week':
                key = date_value - timedelta(days=date_value.weekday())
                key = key.replace(hour=0, minute=0, second=0, microsecond=0)
            else:  # month
                key = date_value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            grouped_data[key]['values'].append(value)
            grouped_data[key]['count'] += 1
        
        # Generate data points
        current_time = start_date
        while current_time <= end_date:
            if aggregation == 'hour':
                next_time = current_time + timedelta(hours=1)
            elif aggregation == 'day':
                next_time = current_time + timedelta(days=1)
            elif aggregation == 'week':
                next_time = current_time + timedelta(weeks=1)
            else:  # month
                next_time = current_time + timedelta(days=32)
                next_time = next_time.replace(day=1)
            
            if current_time in grouped_data:
                values = grouped_data[current_time]['values']
                count = grouped_data[current_time]['count']
                
                data_points.append({
                    'timestamp': current_time,
                    'value': sum(values) / len(values) if values else 0,
                    'count': count,
                    'max_value': max(values) if values else 0,
                    'min_value': min(values) if values else 0
                })
            
            current_time = next_time
        
        return data_points
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from values."""
        if len(values) < 2:
            return 'stable'
        
        # Simple linear regression to determine trend
        n = len(values)
        x = list(range(n))
        
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))
        
        # Calculate slope
        if n * sum_x2 - sum_x ** 2 != 0:
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
        else:
            slope = 0
        
        # Determine trend
        if slope > 0.1:
            return 'increasing'
        elif slope < -0.1:
            return 'decreasing'
        else:
            return 'stable'


# Global analytics instance
_fraud_analytics = None


def get_fraud_analytics() -> FraudAnalytics:
    """Get or create fraud analytics instance."""
    global _fraud_analytics
    if _fraud_analytics is None:
        _fraud_analytics = FraudAnalytics()
    return _fraud_analytics


def get_fraud_overview(period_days: int = 30) -> Dict[str, Any]:
    """
    Convenience function for getting fraud overview.
    
    Args:
        period_days: Analysis period in days
        
    Returns:
        Fraud overview data
    """
    analytics = get_fraud_analytics()
    return analytics.get_fraud_overview(period_days)


def generate_fraud_report(report_type: str, period_days: int = None) -> Dict[str, Any]:
    """
    Convenience function for generating fraud reports.
    
    Args:
        report_type: Type of report
        period_days: Analysis period
        
    Returns:
        Generated report data
    """
    analytics = get_fraud_analytics()
    return analytics.generate_analytics_report(report_type, period_days)
