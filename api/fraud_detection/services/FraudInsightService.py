# =============================================================================
# fraud_detection/services/FraudInsightService.py
# =============================================================================
"""
Fraud Insight Service.

Comprehensive service for generating fraud analytics, insights,
and reports including trend analysis and predictive analytics.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Avg, Count, Max, Min, Sum, Q, F
from django.utils import timezone
from django.core.cache import cache

from api.fraud_detection.models import (
    FraudAttempt, FraudAlert, FraudCase, UserRiskProfile,
    DeviceFingerprint, IPReputation, OfferCompletion
)
from api.fraud_detection.choices import FraudAttemptStatus, CaseStatus
from api.fraud_detection.constants import RISK_THRESHOLDS

logger = logging.getLogger(__name__)


class FraudInsightService:
    """Service for generating fraud analytics and insights."""
    
    def __init__(self):
        self.cache_ttl = 1800  # 30 minutes
    
    def get_fraud_overview(self, days: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive fraud overview statistics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with overview statistics
        """
        try:
            cutoff = timezone.now() - timedelta(days=days)
            
            overview = {}
            
            # Fraud attempts
            attempts = FraudAttempt.objects.filter(created_at__gte=cutoff)
            overview['total_attempts'] = attempts.count()
            overview['confirmed_fraud'] = attempts.filter(status='confirmed').count()
            overview['false_positives'] = attempts.filter(status='false_positive').count()
            overview['pending_review'] = attempts.filter(status='reviewing').count()
            
            # Fraud cases
            cases = FraudCase.objects.filter(opened_at__gte=cutoff)
            overview['total_cases'] = cases.count()
            overview['resolved_cases'] = cases.filter(status__in=[CaseStatus.RESOLVED, CaseStatus.CLOSED]).count()
            overview['open_cases'] = cases.filter(status=CaseStatus.OPEN).count()
            overview['critical_cases'] = cases.filter(priority='critical').count()
            
            # Alerts
            alerts = FraudAlert.objects.filter(created_at__gte=cutoff)
            overview['total_alerts'] = alerts.count()
            overview['high_priority_alerts'] = alerts.filter(priority='high').count()
            overview['critical_alerts'] = alerts.filter(priority='critical').count()
            
            # User risk profiles
            overview['high_risk_users'] = UserRiskProfile.objects.filter(
                overall_risk_score__gte=RISK_THRESHOLDS['high']
            ).count()
            overview['flagged_users'] = UserRiskProfile.objects.filter(
                is_flagged=True
            ).count()
            
            # Financial impact
            overview['total_financial_impact'] = attempts.aggregate(
                total=Sum('amount_involved')
            )['total'] or 0
            
            # Detection rates
            if overview['total_attempts'] > 0:
                overview['detection_rate'] = (overview['confirmed_fraud'] / overview['total_attempts']) * 100
                overview['false_positive_rate'] = (overview['false_positives'] / overview['total_attempts']) * 100
            else:
                overview['detection_rate'] = 0
                overview['false_positive_rate'] = 0
            
            # Average resolution time
            resolved_cases = cases.filter(
                status__in=[CaseStatus.RESOLVED, CaseStatus.CLOSED],
                resolved_at__isnull=False
            )
            
            if resolved_cases.exists():
                resolution_times = [
                    (case.resolved_at - case.opened_at).total_seconds() / 3600  # hours
                    for case in resolved_cases
                ]
                overview['avg_resolution_time_hours'] = sum(resolution_times) / len(resolution_times)
            else:
                overview['avg_resolution_time_hours'] = 0
            
            return overview
            
        except Exception as e:
            logger.error(f"Error generating fraud overview: {e}")
            return {}
    
    def get_fraud_trends(self, days: int = 30, granularity: str = 'daily') -> Dict[str, Any]:
        """
        Get fraud trends over time.
        
        Args:
            days: Number of days to analyze
            granularity: Time granularity ('hourly', 'daily', 'weekly')
            
        Returns:
            Dictionary with trend data
        """
        try:
            cutoff = timezone.now() - timedelta(days=days)
            
            trends = {
                'period': f"{days} days",
                'granularity': granularity,
                'data': []
            }
            
            # Determine time grouping
            if granularity == 'hourly':
                time_format = '%Y-%m-%d %H:00'
                time_delta = timedelta(hours=1)
            elif granularity == 'daily':
                time_format = '%Y-%m-%d'
                time_delta = timedelta(days=1)
            else:  # weekly
                time_format = '%Y-W%U'
                time_delta = timedelta(weeks=1)
            
            # Generate time buckets
            current_time = cutoff
            while current_time <= timezone.now():
                period_end = current_time + time_delta
                
                # Get fraud attempts for this period
                attempts = FraudAttempt.objects.filter(
                    created_at__gte=current_time,
                    created_at__lt=period_end
                )
                
                # Get cases for this period
                cases = FraudCase.objects.filter(
                    opened_at__gte=current_time,
                    opened_at__lt=period_end
                )
                
                trend_data = {
                    'period': current_time.strftime(time_format),
                    'attempts': attempts.count(),
                    'confirmed_fraud': attempts.filter(status='confirmed').count(),
                    'cases_opened': cases.count(),
                    'financial_impact': attempts.aggregate(
                        total=Sum('amount_involved')
                    )['total'] or 0,
                }
                
                # Calculate detection rate
                if trend_data['attempts'] > 0:
                    trend_data['detection_rate'] = (trend_data['confirmed_fraud'] / trend_data['attempts']) * 100
                else:
                    trend_data['detection_rate'] = 0
                
                trends['data'].append(trend_data)
                current_time = period_end
            
            return trends
            
        except Exception as e:
            logger.error(f"Error generating fraud trends: {e}")
            return {}
    
    def get_top_risk_factors(self, days: int = 30, limit: int = 10) -> Dict[str, Any]:
        """
        Get top risk factors contributing to fraud.
        
        Args:
            days: Number of days to analyze
            limit: Maximum number of factors to return
            
        Returns:
            Dictionary with top risk factors
        """
        try:
            cutoff = timezone.now() - timedelta(days=days)
            
            risk_factors = {
                'attempt_types': [],
                'ip_addresses': [],
                'devices': [],
                'users': [],
                'patterns': []
            }
            
            # Top attempt types
            attempt_types = FraudAttempt.objects.filter(
                created_at__gte=cutoff
            ).values('attempt_type').annotate(
                count=Count('id'),
                avg_score=Avg('fraud_score'),
                total_impact=Sum('amount_involved')
            ).order_by('-count')[:limit]
            
            risk_factors['attempt_types'] = [
                {
                    'type': item['attempt_type'],
                    'count': item['count'],
                    'avg_score': item['avg_score'] or 0,
                    'total_impact': item['total_impact'] or 0,
                }
                for item in attempt_types
            ]
            
            # Top risky IP addresses
            risky_ips = IPReputation.objects.filter(
                last_seen__gte=cutoff
            ).filter(
                Q(fraud_score__gte=50) | Q(fraud_attempts__gt=0)
            ).order_by('-fraud_score')[:limit]
            
            risk_factors['ip_addresses'] = [
                {
                    'ip_address': ip.ip_address,
                    'fraud_score': ip.fraud_score,
                    'fraud_attempts': ip.fraud_attempts,
                    'total_requests': ip.total_requests,
                    'is_blacklisted': ip.is_blacklisted,
                }
                for ip in risky_ips
            ]
            
            # Top risky devices
            risky_devices = DeviceFingerprint.objects.filter(
                last_seen__gte=cutoff
            ).filter(
                Q(trust_score__lte=50) | Q(user__risk_profile__overall_risk_score__gte=50)
            ).select_related('user').order_by('trust_score')[:limit]
            
            risk_factors['devices'] = [
                {
                    'device_id': device.device_id,
                    'trust_score': device.trust_score,
                    'user_id': device.user.id if device.user else None,
                    'user_risk_score': device.user.risk_profile.overall_risk_score if device.user and hasattr(device.user, 'risk_profile') else 0,
                    'last_seen': device.last_seen.isoformat(),
                }
                for device in risky_devices
            ]
            
            # Top risky users
            risky_users = UserRiskProfile.objects.filter(
                user__last_login__gte=cutoff
            ).filter(
                overall_risk_score__gte=50
            ).select_related('user').order_by('-overall_risk_score')[:limit]
            
            risk_factors['users'] = [
                {
                    'user_id': profile.user.id,
                    'username': profile.user.username,
                    'risk_score': profile.overall_risk_score,
                    'monitoring_level': profile.monitoring_level,
                    'is_flagged': profile.is_flagged,
                    'total_attempts': profile.total_fraud_attempts,
                }
                for profile in risky_users
            ]
            
            # Common fraud patterns (simplified)
            risk_factors['patterns'] = self._analyze_common_patterns(cutoff, limit)
            
            return risk_factors
            
        except Exception as e:
            logger.error(f"Error getting top risk factors: {e}")
            return {}
    
    def get_geographic_analysis(self, days: int = 30) -> Dict[str, Any]:
        """
        Get geographic fraud analysis.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with geographic analysis
        """
        try:
            cutoff = timezone.now() - timedelta(days=days)
            
            geo_analysis = {
                'top_countries': [],
                'risk_by_country': [],
                'anomalies': []
            }
            
            # Top countries by fraud attempts
            top_countries = IPReputation.objects.filter(
                last_seen__gte=cutoff,
                fraud_attempts__gt=0
            ).values('country').annotate(
                attempts=Count('id'),
                avg_score=Avg('fraud_score'),
                total_impact=Sum('fraud_attempts')
            ).order_by('-attempts')[:20]
            
            geo_analysis['top_countries'] = [
                {
                    'country': item['country'],
                    'attempts': item['attempts'],
                    'avg_score': item['avg_score'] or 0,
                    'total_impact': item['total_impact'] or 0,
                }
                for item in top_countries
            ]
            
            # Risk level by country
            risk_by_country = IPReputation.objects.filter(
                last_seen__gte=cutoff,
                country__isnull=False
            ).values('country').annotate(
                total_ips=Count('id'),
                avg_fraud_score=Avg('fraud_score'),
                blacklisted_count=Count('id', filter=Q(is_blacklisted=True)),
                high_risk_count=Count('id', filter=Q(fraud_score__gte=70))
            ).order_by('-avg_fraud_score')[:50]
            
            geo_analysis['risk_by_country'] = [
                {
                    'country': item['country'],
                    'total_ips': item['total_ips'],
                    'avg_fraud_score': item['avg_fraud_score'] or 0,
                    'blacklisted_count': item['blacklisted_count'],
                    'high_risk_count': item['high_risk_count'],
                    'risk_percentage': (item['high_risk_count'] / item['total_ips'] * 100) if item['total_ips'] > 0 else 0,
                }
                for item in risk_by_country
            ]
            
            # Geographic anomalies
            geo_analysis['anomalies'] = self._detect_geographic_anomalies(cutoff)
            
            return geo_analysis
            
        except Exception as e:
            logger.error(f"Error generating geographic analysis: {e}")
            return {}
    
    def get_performance_metrics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get fraud detection performance metrics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with performance metrics
        """
        try:
            cutoff = timezone.now() - timedelta(days=days)
            
            metrics = {}
            
            # Detection accuracy
            attempts = FraudAttempt.objects.filter(created_at__gte=cutoff)
            total_attempts = attempts.count()
            confirmed = attempts.filter(status='confirmed').count()
            false_positives = attempts.filter(status='false_positive').count()
            
            if total_attempts > 0:
                metrics['accuracy'] = (confirmed / total_attempts) * 100
                metrics['false_positive_rate'] = (false_positives / total_attempts) * 100
                metrics['precision'] = (confirmed / (confirmed + false_positives)) * 100 if (confirmed + false_positives) > 0 else 0
            else:
                metrics['accuracy'] = 0
                metrics['false_positive_rate'] = 0
                metrics['precision'] = 0
            
            # Response time metrics
            cases = FraudCase.objects.filter(opened_at__gte=cutoff)
            resolved_cases = cases.filter(
                status__in=[CaseStatus.RESOLVED, CaseStatus.CLOSED],
                resolved_at__isnull=False
            )
            
            if resolved_cases.exists():
                resolution_times = [
                    (case.resolved_at - case.opened_at).total_seconds() / 3600
                    for case in resolved_cases
                ]
                metrics['avg_resolution_time_hours'] = sum(resolution_times) / len(resolution_times)
                metrics['min_resolution_time_hours'] = min(resolution_times)
                metrics['max_resolution_time_hours'] = max(resolution_times)
            else:
                metrics['avg_resolution_time_hours'] = 0
                metrics['min_resolution_time_hours'] = 0
                metrics['max_resolution_time_hours'] = 0
            
            # System performance
            metrics['total_alerts_generated'] = FraudAlert.objects.filter(
                created_at__gte=cutoff
            ).count()
            
            metrics['alerts_per_attempt'] = (
                metrics['total_alerts_generated'] / total_attempts
            ) if total_attempts > 0 else 0
            
            # Cost savings (estimated)
            confirmed_amount = attempts.filter(
                status='confirmed'
            ).aggregate(total=Sum('amount_involved'))['total'] or 0
            
            metrics['estimated_savings'] = confirmed_amount * 0.95  # Assume 95% of fraud would have succeeded
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error generating performance metrics: {e}")
            return {}
    
    def get_predictive_insights(self, days: int = 30) -> Dict[str, Any]:
        """
        Get predictive insights and forecasts.
        
        Args:
            days: Number of days to analyze for prediction
            
        Returns:
            Dictionary with predictive insights
        """
        try:
            insights = {
                'forecasts': {},
                'risk_predictions': [],
                'recommendations': []
            }
            
            # Simple trend analysis for forecasting
            historical_data = self.get_fraud_trends(days * 2, 'daily')
            recent_data = historical_data['data'][-days:] if len(historical_data['data']) >= days else historical_data['data']
            
            if len(recent_data) >= 7:
                # Calculate trend for next 7 days
                trend_slope = self._calculate_trend_slope(recent_data)
                last_value = recent_data[-1]['attempts']
                
                forecasts = []
                for day in range(1, 8):
                    predicted_value = last_value + (trend_slope * day)
                    forecasts.append({
                        'day': day,
                        'predicted_attempts': max(0, int(predicted_value)),
                        'confidence': max(0.5, min(0.95, 1 - (day * 0.1)))  # Decreasing confidence
                    })
                
                insights['forecasts']['next_7_days'] = forecasts
            
            # Risk predictions for high-risk entities
            insights['risk_predictions'] = self._predict_risk_entities(days)
            
            # System recommendations
            insights['recommendations'] = self._generate_system_recommendations(days)
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating predictive insights: {e}")
            return {}
    
    def export_analytics_data(self, format_type: str = 'json', days: int = 30) -> Dict[str, Any]:
        """
        Export analytics data in specified format.
        
        Args:
            format_type: Export format ('json', 'csv', 'excel')
            days: Number of days to include
            
        Returns:
            Export data dictionary
        """
        try:
            cutoff = timezone.now() - timedelta(days=days)
            
            export_data = {
                'overview': self.get_fraud_overview(days),
                'trends': self.get_fraud_trends(days),
                'risk_factors': self.get_top_risk_factors(days),
                'geographic': self.get_geographic_analysis(days),
                'performance': self.get_performance_metrics(days),
                'predictive': self.get_predictive_insights(days),
                'export_metadata': {
                    'format': format_type,
                    'period_days': days,
                    'generated_at': timezone.now().isoformat(),
                    'data_sources': ['FraudAttempt', 'FraudCase', 'FraudAlert', 'UserRiskProfile']
                }
            }
            
            if format_type == 'json':
                return {'data': json.dumps(export_data, indent=2, default=str)}
            elif format_type == 'csv':
                # Convert to CSV format (simplified)
                return {'data': self._convert_to_csv(export_data)}
            elif format_type == 'excel':
                # Return data for Excel export (simplified)
                return {'data': export_data}
            else:
                raise ValueError(f"Unsupported format: {format_type}")
                
        except Exception as e:
            logger.error(f"Error exporting analytics data: {e}")
            return {'error': str(e)}
    
    # =============================================================================
    # PRIVATE HELPER METHODS
    # =============================================================================
    
    def _analyze_common_patterns(self, cutoff: timezone.datetime, limit: int) -> List[Dict]:
        """Analyze common fraud patterns."""
        patterns = []
        
        try:
            # Pattern 1: Multiple accounts from same IP
            ip_users = FraudAttempt.objects.filter(
                created_at__gte=cutoff
            ).values('evidence_data').annotate(
                user_count=Count('user_id', distinct=True)
            ).filter(user_count__gt=3)[:limit]
            
            patterns.append({
                'pattern': 'Multiple accounts from same IP',
                'count': ip_users.count(),
                'description': 'Same IP address used by multiple users',
                'severity': 'high'
            })
            
            # Pattern 2: Rapid successive attempts
            rapid_attempts = self._detect_rapid_attempts(cutoff)
            patterns.append({
                'pattern': 'Rapid successive attempts',
                'count': rapid_attempts,
                'description': 'Multiple attempts in short time period',
                'severity': 'medium'
            })
            
            # Pattern 3: High value targeting
            high_value_attempts = FraudAttempt.objects.filter(
                created_at__gte=cutoff,
                amount_involved__gte=1000
            ).count()
            
            patterns.append({
                'pattern': 'High value targeting',
                'count': high_value_attempts,
                'description': 'Attempts involving large amounts',
                'severity': 'critical'
            })
            
        except Exception as e:
            logger.error(f"Error analyzing common patterns: {e}")
        
        return patterns
    
    def _detect_geographic_anomalies(self, cutoff: timezone.datetime) -> List[Dict]:
        """Detect geographic anomalies."""
        anomalies = []
        
        try:
            # Anomaly 1: Unusual country combinations
            # This is simplified - in production, use more sophisticated analysis
            country_changes = FraudAttempt.objects.filter(
                created_at__gte=cutoff
            ).values('user_id').annotate(
                country_count=Count('ip_address__country', distinct=True)
            ).filter(country_count__gt=3)
            
            if country_changes.exists():
                anomalies.append({
                    'type': 'Multiple countries',
                    'count': country_changes.count(),
                    'description': 'Users accessing from multiple countries',
                    'severity': 'high'
                })
            
        except Exception as e:
            logger.error(f"Error detecting geographic anomalies: {e}")
        
        return anomalies
    
    def _detect_rapid_attempts(self, cutoff: timezone.datetime) -> int:
        """Detect rapid successive attempts."""
        try:
            # Simplified rapid attempt detection
            rapid_count = 0
            
            users = FraudAttempt.objects.filter(
                created_at__gte=cutoff
            ).values_list('user_id', flat=True).distinct()
            
            for user_id in users:
                attempts = FraudAttempt.objects.filter(
                    user_id=user_id,
                    created_at__gte=cutoff
                ).order_by('created_at')
                
                if attempts.count() > 1:
                    for i in range(1, attempts.count()):
                        time_diff = attempts[i].created_at - attempts[i-1].created_at
                        if time_diff.total_seconds() < 300:  # 5 minutes
                            rapid_count += 1
                            break
            
            return rapid_count
            
        except Exception as e:
            logger.error(f"Error detecting rapid attempts: {e}")
            return 0
    
    def _calculate_trend_slope(self, data: List[Dict]) -> float:
        """Calculate simple linear trend slope."""
        try:
            if len(data) < 2:
                return 0
            
            x = list(range(len(data)))
            y = [item['attempts'] for item in data]
            
            n = len(data)
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(x[i] * y[i] for i in range(n))
            sum_x2 = sum(x[i] ** 2 for i in range(n))
            
            # Calculate slope
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
            
            return slope
            
        except Exception as e:
            logger.error(f"Error calculating trend slope: {e}")
            return 0
    
    def _predict_risk_entities(self, days: int) -> List[Dict]:
        """Predict risk for high-risk entities."""
        predictions = []
        
        try:
            cutoff = timezone.now() - timedelta(days=days)
            
            # Predict users at risk of escalation
            high_risk_users = UserRiskProfile.objects.filter(
                overall_risk_score__gte=60,
                overall_risk_score__lt=80
            ).select_related('user')[:10]
            
            for profile in high_risk_users:
                # Simple prediction based on trend
                recent_attempts = FraudAttempt.objects.filter(
                    user=profile.user,
                    created_at__gte=cutoff
                ).count()
                
                if recent_attempts >= 3:
                    predictions.append({
                        'entity_type': 'user',
                        'entity_id': profile.user.id,
                        'entity_name': profile.user.username,
                        'current_risk': profile.overall_risk_score,
                        'predicted_risk': min(100, profile.overall_risk_score + 15),
                        'confidence': 0.75,
                        'reason': 'Increasing fraud attempt frequency'
                    })
            
        except Exception as e:
            logger.error(f"Error predicting risk entities: {e}")
        
        return predictions
    
    def _generate_system_recommendations(self, days: int) -> List[Dict]:
        """Generate system recommendations based on analytics."""
        recommendations = []
        
        try:
            overview = self.get_fraud_overview(days)
            
            # Recommendation based on false positive rate
            if overview.get('false_positive_rate', 0) > 20:
                recommendations.append({
                    'type': 'tuning',
                    'priority': 'high',
                    'title': 'Reduce False Positives',
                    'description': 'False positive rate is high. Consider adjusting detection thresholds.',
                    'action': 'Review and optimize fraud detection rules'
                })
            
            # Recommendation based on resolution time
            if overview.get('avg_resolution_time_hours', 0) > 48:
                recommendations.append({
                    'type': 'process',
                    'priority': 'medium',
                    'title': 'Improve Resolution Time',
                    'description': 'Average case resolution time is high. Consider automation.',
                    'action': 'Implement automated case assignment and escalation'
                })
            
            # Recommendation based on detection rate
            if overview.get('detection_rate', 0) < 50:
                recommendations.append({
                    'type': 'detection',
                    'priority': 'critical',
                    'title': 'Improve Detection Rate',
                    'description': 'Detection rate is low. Review detection algorithms.',
                    'action': 'Enhance ML models and detection patterns'
                })
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
        
        return recommendations
    
    def _convert_to_csv(self, data: Dict) -> str:
        """Convert data to CSV format (simplified)."""
        # This is a simplified CSV conversion
        # In production, use proper CSV generation
        csv_lines = ["Metric,Value"]
        
        for key, value in data.get('overview', {}).items():
            csv_lines.append(f"{key},{value}")
        
        return "\n".join(csv_lines)
