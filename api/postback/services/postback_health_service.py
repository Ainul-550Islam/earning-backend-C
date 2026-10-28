"""
postback_health_service.py – Postback health monitoring service.

Provides comprehensive health monitoring and success rate tracking for postback processing.
Handles real-time monitoring, alerting, and performance metrics.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from django.db import models
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Avg, Count, Q, F, Sum

from api.postback.models import NetworkPostbackConfig, PostbackLog, PostbackInsight
from api.postback.choices import PostbackStatus, RejectionReason

logger = logging.getLogger(__name__)


class PostbackHealthService:
    """Service for monitoring postback health and success rates."""

    @staticmethod
    def get_network_health_score(network: NetworkPostbackConfig, hours: int = 24) -> Dict:
        """
        Calculate comprehensive health score for a network over specified hours.
        Returns detailed health metrics and overall score (0-100).
        """
        end_time = timezone.now()
        start_time = end_time - timedelta(hours=hours)
        
        # Get postback logs for the period
        logs = PostbackLog.objects.filter(
            network=network,
            received_at__gte=start_time,
            received_at__lt=end_time
        )
        
        if not logs.exists():
            return {
                'network_key': network.network_key,
                'period_hours': hours,
                'overall_score': 0,
                'total_requests': 0,
                'metrics': {
                    'success_rate': 0,
                    'processing_time_avg': 0,
                    'error_rate': 0,
                    'duplicate_rate': 0,
                    'timeout_rate': 0
                },
                'status_breakdown': {},
                'rejection_reasons': {},
                'health_indicators': {
                    'processing_speed': 'unknown',
                    'error_frequency': 'unknown',
                    'duplicate_frequency': 'unknown',
                    'overall_stability': 'unknown'
                }
            }
        
        # Calculate basic metrics
        total_requests = logs.count()
        rewarded_count = logs.filter(status=PostbackStatus.REWARDED).count()
        rejected_count = logs.filter(status=PostbackStatus.REJECTED).count()
        duplicate_count = logs.filter(status=PostbackStatus.DUPLICATE).count()
        failed_count = logs.filter(status=PostbackStatus.FAILED).count()
        
        # Success rate (excluding duplicates as they're expected)
        non_duplicate_requests = total_requests - duplicate_count
        success_rate = (rewarded_count / non_duplicate_requests * 100) if non_duplicate_requests > 0 else 0
        
        # Error rate (rejected + failed)
        error_rate = ((rejected_count + failed_count) / total_requests * 100) if total_requests > 0 else 0
        
        # Duplicate rate
        duplicate_rate = (duplicate_count / total_requests * 100) if total_requests > 0 else 0
        
        # Processing time metrics
        processed_logs = logs.filter(
            processed_at__isnull=False,
            received_at__isnull=False
        )
        
        avg_processing_time = 0
        if processed_logs.exists():
            total_time = sum(
                (log.processed_at - log.received_at).total_seconds()
                for log in processed_logs
            )
            avg_processing_time = total_time / processed_logs.count()
        
        # Timeout rate (processing time > 30 seconds)
        timeout_count = 0
        for log in processed_logs:
            if (log.processed_at - log.received_at).total_seconds() > 30:
                timeout_count += 1
        
        timeout_rate = (timeout_count / processed_logs.count() * 100) if processed_logs.exists() else 0
        
        # Status breakdown
        status_breakdown = {
            'received': logs.filter(status=PostbackStatus.RECEIVED).count(),
            'validated': logs.filter(status=PostbackStatus.VALIDATED).count(),
            'rewarded': rewarded_count,
            'rejected': rejected_count,
            'duplicate': duplicate_count,
            'failed': failed_count
        }
        
        # Rejection reason breakdown
        rejection_breakdown = {}
        if rejected_count > 0:
            rejected_logs = logs.filter(status=PostbackStatus.REJECTED)
            for reason, count in rejected_logs.values('rejection_reason').annotate(count=Count('id')):
                rejection_breakdown[reason] = count
        
        # Calculate health indicators
        health_indicators = {
            'processing_speed': 'good' if avg_processing_time < 5 else 'warning' if avg_processing_time < 15 else 'critical',
            'error_frequency': 'good' if error_rate < 5 else 'warning' if error_rate < 15 else 'critical',
            'duplicate_frequency': 'good' if duplicate_rate < 10 else 'warning' if duplicate_rate < 25 else 'critical',
            'overall_stability': 'good' if success_rate > 85 else 'warning' if success_rate > 70 else 'critical'
        }
        
        # Calculate overall health score
        score_components = {
            'success_rate_weight': 0.4,
            'processing_speed_weight': 0.2,
            'error_rate_weight': 0.3,
            'duplicate_rate_weight': 0.1
        }
        
        # Normalize each component to 0-100 scale
        success_score = min(100, success_rate)
        speed_score = max(0, 100 - (avg_processing_time * 2))  # 50s = 0 score
        error_score = max(0, 100 - (error_rate * 2))  # 50% error = 0 score
        duplicate_score = max(0, 100 - (duplicate_rate * 2))  # 50% duplicate = 0 score
        
        overall_score = (
            success_score * score_components['success_rate_weight'] +
            speed_score * score_components['processing_speed_weight'] +
            error_score * score_components['error_rate_weight'] +
            duplicate_score * score_components['duplicate_rate_weight']
        )
        
        return {
            'network_key': network.network_key,
            'period_hours': hours,
            'overall_score': round(overall_score, 2),
            'total_requests': total_requests,
            'metrics': {
                'success_rate': round(success_rate, 2),
                'processing_time_avg': round(avg_processing_time, 2),
                'error_rate': round(error_rate, 2),
                'duplicate_rate': round(duplicate_rate, 2),
                'timeout_rate': round(timeout_rate, 2)
            },
            'status_breakdown': status_breakdown,
            'rejection_reasons': rejection_breakdown,
            'health_indicators': health_indicators
        }

    @staticmethod
    def get_real_time_health_metrics(network: NetworkPostbackConfig) -> Dict:
        """
        Get real-time health metrics for a network.
        Uses cached data for performance.
        """
        cache_key = f"postback_health_metrics:{network.id}"
        
        # Try to get from cache first
        cached_metrics = cache.get(cache_key)
        if cached_metrics:
            return cached_metrics
        
        # Get last hour of data
        health_data = PostbackHealthService.get_network_health_score(network, hours=1)
        
        # Add real-time specific metrics
        recent_logs = PostbackLog.objects.filter(
            network=network,
            received_at__gte=timezone.now() - timedelta(minutes=5)
        )
        
        health_data['real_time'] = {
            'last_5_minutes': {
                'requests': recent_logs.count(),
                'success_rate': 0,
                'avg_processing_time': 0
            }
        }
        
        if recent_logs.exists():
            recent_rewarded = recent_logs.filter(status=PostbackStatus.REWARDED).count()
            recent_processed = recent_logs.filter(
                processed_at__isnull=False,
                received_at__isnull=False
            )
            
            health_data['real_time']['last_5_minutes']['success_rate'] = (
                (recent_rewarded / recent_logs.count() * 100) if recent_logs.count() > 0 else 0
            )
            
            if recent_processed.exists():
                recent_total_time = sum(
                    (log.processed_at - log.received_at).total_seconds()
                    for log in recent_processed
                )
                health_data['real_time']['last_5_minutes']['avg_processing_time'] = (
                    recent_total_time / recent_processed.count()
                )
        
        # Cache for 30 seconds
        cache.set(cache_key, health_data, timeout=30)
        
        return health_data

    @staticmethod
    def get_health_trends(network: NetworkPostbackConfig, days: int = 7) -> Dict:
        """
        Get health trends over time for a network.
        Returns hourly breakdown and trend analysis.
        """
        end_time = timezone.now()
        start_time = end_time - timedelta(days=days)
        
        # Get hourly health scores
        hourly_data = []
        current_time = start_time
        
        while current_time < end_time:
            hour_end = current_time + timedelta(hours=1)
            
            logs = PostbackLog.objects.filter(
                network=network,
                received_at__gte=current_time,
                received_at__lt=hour_end
            )
            
            if logs.exists():
                total = logs.count()
                rewarded = logs.filter(status=PostbackStatus.REWARDED).count()
                rejected = logs.filter(status=PostbackStatus.REJECTED).count()
                failed = logs.filter(status=PostbackStatus.FAILED).count()
                duplicate = logs.filter(status=PostbackStatus.DUPLICATE).count()
                
                success_rate = (rewarded / (total - duplicate) * 100) if (total - duplicate) > 0 else 0
                error_rate = ((rejected + failed) / total * 100) if total > 0 else 0
                
                # Calculate processing time
                processed_logs = logs.filter(
                    processed_at__isnull=False,
                    received_at__isnull=False
                )
                avg_processing_time = 0
                if processed_logs.exists():
                    total_time = sum(
                        (log.processed_at - log.received_at).total_seconds()
                        for log in processed_logs
                    )
                    avg_processing_time = total_time / processed_logs.count()
                
                hourly_data.append({
                    'hour': current_time.isoformat(),
                    'requests': total,
                    'success_rate': round(success_rate, 2),
                    'error_rate': round(error_rate, 2),
                    'avg_processing_time': round(avg_processing_time, 2)
                })
            
            current_time = hour_end
        
        # Calculate trend analysis
        if len(hourly_data) >= 2:
            recent_avg = sum(d['success_rate'] for d in hourly_data[-12:]) / min(12, len(hourly_data))
            older_avg = sum(d['success_rate'] for d in hourly_data[:12]) / min(12, len(hourly_data))
            
            trend = 'stable'
            if recent_avg > older_avg + 5:
                trend = 'improving'
            elif recent_avg < older_avg - 5:
                trend = 'declining'
        else:
            trend = 'insufficient_data'
        
        return {
            'network_key': network.network_key,
            'period_days': days,
            'hourly_data': hourly_data,
            'trend': trend,
            'summary': {
                'total_hours': len(hourly_data),
                'avg_success_rate': round(sum(d['success_rate'] for d in hourly_data) / len(hourly_data), 2) if hourly_data else 0,
                'avg_error_rate': round(sum(d['error_rate'] for d in hourly_data) / len(hourly_data), 2) if hourly_data else 0,
                'peak_hour': max(hourly_data, key=lambda x: x['requests'])['hour'] if hourly_data else None,
                'lowest_hour': min(hourly_data, key=lambda x: x['requests'])['hour'] if hourly_data else None
            }
        }

    @staticmethod
    def get_network_comparison(networks: List[NetworkPostbackConfig]) -> Dict:
        """
        Compare health metrics across multiple networks.
        Returns ranking and comparative analysis.
        """
        network_scores = []
        
        for network in networks:
            health_data = PostbackHealthService.get_network_health_score(network, hours=24)
            network_scores.append({
                'network_key': network.network_key,
                'network_id': str(network.id),
                'overall_score': health_data['overall_score'],
                'total_requests': health_data['total_requests'],
                'success_rate': health_data['metrics']['success_rate'],
                'error_rate': health_data['metrics']['error_rate'],
                'processing_time': health_data['metrics']['processing_time_avg']
            })
        
        # Sort by overall score
        network_scores.sort(key=lambda x: x['overall_score'], reverse=True)
        
        # Calculate averages
        if network_scores:
            avg_score = sum(n['overall_score'] for n in network_scores) / len(network_scores)
            avg_success_rate = sum(n['success_rate'] for n in network_scores) / len(network_scores)
            avg_error_rate = sum(n['error_rate'] for n in network_scores) / len(network_scores)
            avg_processing_time = sum(n['processing_time'] for n in network_scores) / len(network_scores)
        else:
            avg_score = avg_success_rate = avg_error_rate = avg_processing_time = 0
        
        return {
            'comparison_period': '24 hours',
            'total_networks': len(network_scores),
            'rankings': network_scores,
            'averages': {
                'overall_score': round(avg_score, 2),
                'success_rate': round(avg_success_rate, 2),
                'error_rate': round(avg_error_rate, 2),
                'processing_time': round(avg_processing_time, 2)
            },
            'best_performer': network_scores[0] if network_scores else None,
            'worst_performer': network_scores[-1] if network_scores else None
        }

    @staticmethod
    def detect_health_anomalies(network: NetworkPostbackConfig) -> Dict:
        """
        Detect health anomalies for a network.
        Returns alerts and recommendations.
        """
        current_health = PostbackHealthService.get_network_health_score(network, hours=1)
        trends = PostbackHealthService.get_health_trends(network, days=7)
        
        anomalies = []
        alerts = []
        recommendations = []
        
        # Check for sudden drops in success rate
        if len(trends['hourly_data']) >= 2:
            recent_success = trends['hourly_data'][-1]['success_rate']
            previous_success = trends['hourly_data'][-2]['success_rate']
            
            if previous_success > 0 and recent_success < (previous_success * 0.7):  # 30% drop
                anomalies.append({
                    'type': 'success_rate_drop',
                    'severity': 'high',
                    'description': f"Success rate dropped from {previous_success:.1f}% to {recent_success:.1f}%",
                    'current_value': recent_success,
                    'previous_value': previous_success
                })
                alerts.append("Critical: Success rate has dropped significantly in the last hour")
                recommendations.append("Investigate recent postback failures and check network connectivity")
        
        # Check for high error rates
        if current_health['metrics']['error_rate'] > 20:
            anomalies.append({
                'type': 'high_error_rate',
                'severity': 'critical',
                'description': f"Error rate is {current_health['metrics']['error_rate']:.1f}%",
                'current_value': current_health['metrics']['error_rate']
            })
            alerts.append("Critical: Error rate is above 20%")
            recommendations.append("Check postback validation rules and network configuration")
        elif current_health['metrics']['error_rate'] > 10:
            anomalies.append({
                'type': 'elevated_error_rate',
                'severity': 'medium',
                'description': f"Error rate is {current_health['metrics']['error_rate']:.1f}%",
                'current_value': current_health['metrics']['error_rate']
            })
            alerts.append("Warning: Error rate is elevated")
            recommendations.append("Monitor error patterns and consider adjusting validation rules")
        
        # Check for slow processing
        if current_health['metrics']['processing_time_avg'] > 10:
            anomalies.append({
                'type': 'slow_processing',
                'severity': 'medium',
                'description': f"Average processing time is {current_health['metrics']['processing_time_avg']:.1f}s",
                'current_value': current_health['metrics']['processing_time_avg']
            })
            alerts.append("Warning: Processing time is slow")
            recommendations.append("Check database performance and external service connectivity")
        
        # Check for high duplicate rate
        if current_health['metrics']['duplicate_rate'] > 30:
            anomalies.append({
                'type': 'high_duplicate_rate',
                'severity': 'medium',
                'description': f"Duplicate rate is {current_health['metrics']['duplicate_rate']:.1f}%",
                'current_value': current_health['metrics']['duplicate_rate']
            })
            alerts.append("Warning: High duplicate rate detected")
            recommendations.append("Review deduplication configuration and partner integration")
        
        # Check for low volume (might indicate issues)
        if current_health['total_requests'] < 10 and trends['summary']['avg_success_rate'] > 0:
            anomalies.append({
                'type': 'low_volume',
                'severity': 'low',
                'description': f"Only {current_health['total_requests']} requests in the last hour",
                'current_value': current_health['total_requests']
            })
            alerts.append("Info: Low request volume detected")
            recommendations.append("Check if this is expected or if there are connectivity issues")
        
        return {
            'network_key': network.network_key,
            'timestamp': timezone.now().isoformat(),
            'anomalies': anomalies,
            'alerts': alerts,
            'recommendations': recommendations,
            'current_health': current_health
        }

    @staticmethod
    def get_health_summary(network: NetworkPostbackConfig) -> Dict:
        """
        Get comprehensive health summary for a network.
        Combines current status, trends, and anomalies.
        """
        current_health = PostbackHealthService.get_network_health_score(network, hours=24)
        real_time = PostbackHealthService.get_real_time_health_metrics(network)
        trends = PostbackHealthService.get_health_trends(network, days=7)
        anomalies = PostbackHealthService.detect_health_anomalies(network)
        
        # Determine overall status
        overall_status = 'healthy'
        if current_health['overall_score'] < 50:
            overall_status = 'critical'
        elif current_health['overall_score'] < 70:
            overall_status = 'warning'
        elif current_health['overall_score'] < 85:
            overall_status = 'caution'
        
        return {
            'network_key': network.network_key,
            'timestamp': timezone.now().isoformat(),
            'overall_status': overall_status,
            'health_score': current_health['overall_score'],
            'current_metrics': current_health['metrics'],
            'real_time_metrics': real_time.get('real_time', {}),
            'trend_analysis': {
                'direction': trends['trend'],
                'summary': trends['summary']
            },
            'active_alerts': anomalies['alerts'],
            'anomaly_count': len(anomalies['anomalies']),
            'recommendations': anomalies['recommendations']
        }

    @staticmethod
    def get_system_health_dashboard() -> Dict:
        """
        Get system-wide health dashboard for all networks.
        Returns overview and network-specific details.
        """
        from django.db.models import Avg, Count, Q
        
        networks = NetworkPostbackConfig.objects.filter(status='ACTIVE')
        
        network_health = []
        system_metrics = {
            'total_networks': networks.count(),
            'healthy_networks': 0,
            'warning_networks': 0,
            'critical_networks': 0,
            'total_requests_24h': 0,
            'avg_success_rate': 0,
            'avg_processing_time': 0
        }
        
        success_rates = []
        processing_times = []
        
        for network in networks:
            health = PostbackHealthService.get_health_score(network, hours=24)
            
            # Categorize network health
            if health['overall_score'] >= 85:
                system_metrics['healthy_networks'] += 1
                status = 'healthy'
            elif health['overall_score'] >= 70:
                system_metrics['warning_networks'] += 1
                status = 'warning'
            else:
                system_metrics['critical_networks'] += 1
                status = 'critical'
            
            network_health.append({
                'network_key': network.network_key,
                'network_id': str(network.id),
                'status': status,
                'health_score': health['overall_score'],
                'requests': health['total_requests'],
                'success_rate': health['metrics']['success_rate'],
                'error_rate': health['metrics']['error_rate']
            })
            
            # Accumulate for system metrics
            system_metrics['total_requests_24h'] += health['total_requests']
            success_rates.append(health['metrics']['success_rate'])
            processing_times.append(health['metrics']['processing_time_avg'])
        
        # Calculate system averages
        if success_rates:
            system_metrics['avg_success_rate'] = sum(success_rates) / len(success_rates)
        if processing_times:
            system_metrics['avg_processing_time'] = sum(processing_times) / len(processing_times)
        
        # Sort networks by health score
        network_health.sort(key=lambda x: x['health_score'], reverse=True)
        
        return {
            'timestamp': timezone.now().isoformat(),
            'system_metrics': system_metrics,
            'network_health': network_health,
            'top_performers': network_health[:3],
            'needs_attention': [n for n in network_health if n['status'] in ['warning', 'critical']]
        }

    @staticmethod
    def generate_health_report(network: NetworkPostbackConfig, days: int = 7) -> Dict:
        """
        Generate comprehensive health report for a network.
        Suitable for periodic health monitoring and reporting.
        """
        report_period = f"{days} days"
        end_time = timezone.now()
        start_time = end_time - timedelta(days=days)
        
        # Get comprehensive data
        health_summary = PostbackHealthService.get_health_summary(network)
        trends = PostbackHealthService.get_health_trends(network, days)
        anomalies = PostbackHealthService.detect_health_anomalies(network)
        
        # Get detailed statistics
        logs = PostbackLog.objects.filter(
            network=network,
            received_at__gte=start_time,
            received_at__lt=end_time
        )
        
        # Hourly distribution
        hourly_distribution = defaultdict(int)
        for log in logs:
            hour = log.received_at.hour
            hourly_distribution[hour] += 1
        
        # Peak hours
        peak_hours = sorted(hourly_distribution.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Rejection patterns
        rejection_patterns = {}
        rejected_logs = logs.filter(status=PostbackStatus.REJECTED)
        for reason in RejectionReason:
            count = rejected_logs.filter(rejection_reason=reason).count()
            if count > 0:
                rejection_patterns[reason.value] = count
        
        # Processing time distribution
        processing_times = []
        processed_logs = logs.filter(
            processed_at__isnull=False,
            received_at__isnull=False
        )
        
        for log in processed_logs:
            processing_time = (log.processed_at - log.received_at).total_seconds()
            processing_times.append(processing_time)
        
        processing_time_stats = {}
        if processing_times:
            processing_times.sort()
            processing_time_stats = {
                'min': min(processing_times),
                'max': max(processing_times),
                'avg': sum(processing_times) / len(processing_times),
                'median': processing_times[len(processing_times) // 2],
                'p95': processing_times[int(len(processing_times) * 0.95)],
                'p99': processing_times[int(len(processing_times) * 0.99)]
            }
        
        return {
            'report_metadata': {
                'network_key': network.network_key,
                'report_period': report_period,
                'generated_at': end_time.isoformat(),
                'total_requests': logs.count()
            },
            'executive_summary': {
                'overall_health_score': health_summary['health_score'],
                'overall_status': health_summary['overall_status'],
                'key_metrics': health_summary['current_metrics'],
                'trend_direction': trends['trend'],
                'active_alerts': len(health_summary['active_alerts'])
            },
            'detailed_analysis': {
                'traffic_patterns': {
                    'hourly_distribution': dict(hourly_distribution),
                    'peak_hours': peak_hours,
                    'daily_average': logs.count() / days
                },
                'performance_metrics': {
                    'processing_time_stats': processing_time_stats,
                    'success_rate_trends': trends['hourly_data'][-24:] if len(trends['hourly_data']) >= 24 else trends['hourly_data']
                },
                'error_analysis': {
                    'rejection_patterns': rejection_patterns,
                    'anomalies_detected': anomalies['anomalies'],
                    'recommendations': anomalies['recommendations']
                }
            },
            'recommendations': {
                'immediate': anomalies['recommendations'][:3] if anomalies['recommendations'] else [],
                'short_term': [],
                'long_term': []
            }
        }
