"""
Enhanced Security Insight Service with comprehensive security model integration
Author: System Security Team
Version: 2.0.0

Advanced security analytics, reporting, and intelligence capabilities.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, date
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from django.db.models import Avg, Sum, Count, Q
from django.conf import settings

from ..models import SecurityInsight, SecurityLog, UserBan, IPBlacklist
from ..utils.cache_manager import CacheManager, handle_gracefully

logger = logging.getLogger(__name__)


class SecurityInsightService:
    """
    Service for managing security insights and analytics with defensive coding patterns
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_service_instance(cls):
        """Get singleton instance of the service"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """Initialize service with cache manager"""
        self.cache_manager = CacheManager.get_instance()
        self.logger = logging.getLogger(__name__)
    
    @handle_gracefully(default_return=None)
    def get_insight_by_date(self, insight_date: date) -> Optional[SecurityInsight]:
        """
        Get security insight for a specific date
        """
        try:
            cache_key = f"security_insight_{insight_date.isoformat()}"
            cached_result = self.cache_manager.get(cache_key)
            
            if cached_result is not None:
                return cached_result
            
            insight = SecurityInsight.objects.filter(date=insight_date).first()
            
            # Cache for 1 hour
            self.cache_manager.set(cache_key, insight, timeout=3600)
            
            return insight
            
        except Exception as e:
            self.logger.error(f"Error getting insight for {insight_date}: {e}")
            return None
    
    @handle_gracefully(default_return=False)
    def generate_daily_insight(self, target_date: date = None) -> bool:
        """
        Generate security insight for a specific date
        """
        try:
            if target_date is None:
                target_date = timezone.now().date()
            
            # Check if insight already exists
            existing_insight = SecurityInsight.objects.filter(date=target_date).first()
            if existing_insight:
                self.logger.info(f"Insight already exists for {target_date}")
                return True
            
            # Get security data for the day
            start_time = timezone.make_aware(
                datetime.combine(target_date, datetime.min.time())
            )
            end_time = timezone.make_aware(
                datetime.combine(target_date, datetime.max.time())
            )
            
            # Collect security metrics
            metrics = self._collect_daily_metrics(start_time, end_time)
            
            # Create or update insight
            insight, created = SecurityInsight.objects.update_or_create(
                date=target_date,
                defaults={
                    'total_events': metrics['total_events'],
                    'critical_count': metrics['critical_count'],
                    'high_count': metrics['high_count'],
                    'medium_count': metrics['medium_count'],
                    'low_count': metrics['low_count'],
                    'blocked_ips': metrics['blocked_ips'],
                    'locked_accounts': metrics['locked_accounts'],
                    'failed_logins': metrics['failed_logins'],
                    'successful_logins': metrics['successful_logins'],
                    'suspicious_activities': metrics['suspicious_activities'],
                    'fraud_attempts': metrics['fraud_attempts'],
                    'malware_detections': metrics['malware_detections'],
                    'phishing_attempts': metrics['phishing_attempts'],
                    'ddos_attacks': metrics['ddos_attacks'],
                    'data_breaches': metrics['data_breaches'],
                    'response_times': metrics['response_times'],
                    'system_load': metrics['system_load'],
                    'threat_intelligence': metrics['threat_intelligence'],
                    'compliance_status': metrics['compliance_status'],
                    'recommendations': metrics['recommendations']
                }
            )
            
            self.logger.info(f"Generated security insight for {target_date}: {created and 'created' or 'updated'}")
            
            # Clear cache
            cache_key = f"security_insight_{target_date.isoformat()}"
            self.cache_manager.delete(cache_key)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error generating daily insight for {target_date}: {e}")
            return False
    
    def _collect_daily_metrics(self, start_time, end_time) -> Dict[str, Any]:
        """
        Collect security metrics for a time period
        """
        try:
            metrics = {
                'total_events': 0,
                'critical_count': 0,
                'high_count': 0,
                'medium_count': 0,
                'low_count': 0,
                'blocked_ips': [],
                'locked_accounts': [],
                'failed_logins': 0,
                'successful_logins': 0,
                'suspicious_activities': 0,
                'fraud_attempts': 0,
                'malware_detections': 0,
                'phishing_attempts': 0,
                'ddos_attacks': 0,
                'data_breaches': 0,
                'response_times': {},
                'system_load': {},
                'threat_intelligence': {},
                'compliance_status': {},
                'recommendations': []
            }
            
            # Get security logs
            security_logs = SecurityLog.objects.filter(
                created_at__gte=start_time,
                created_at__lte=end_time
            )
            
            # Count events by severity
            severity_counts = security_logs.aggregate(
                total_count=Count('id'),
                critical_count=Count('id', filter=Q(severity='critical')),
                high_count=Count('id', filter=Q(severity='high')),
                medium_count=Count('id', filter=Q(severity='medium')),
                low_count=Count('id', filter=Q(severity='low'))
            )
            
            metrics.update({
                'total_events': severity_counts['total_count'] or 0,
                'critical_count': severity_counts['critical_count'] or 0,
                'high_count': severity_counts['high_count'] or 0,
                'medium_count': severity_counts['medium_count'] or 0,
                'low_count': severity_counts['low_count'] or 0
            })
            
            # Count specific event types
            event_type_counts = {}
            for log in security_logs:
                event_type = log.action_type
                if event_type not in event_type_counts:
                    event_type_counts[event_type] = 0
                event_type_counts[event_type] += 1
            
            metrics['failed_logins'] = event_type_counts.get('LOGIN_FAILED', 0)
            metrics['successful_logins'] = event_type_counts.get('LOGIN_SUCCESS', 0)
            metrics['suspicious_activities'] = event_type_counts.get('SUSPICIOUS_ACTIVITY', 0)
            metrics['fraud_attempts'] = event_type_counts.get('FRAUD_ATTEMPT', 0)
            metrics['malware_detections'] = event_type_counts.get('MALWARE_DETECTED', 0)
            metrics['phishing_attempts'] = event_type_counts.get('PHISHING_ATTEMPT', 0)
            metrics['ddos_attacks'] = event_type_counts.get('DDOS_ATTACK', 0)
            metrics['data_breaches'] = event_type_counts.get('DATA_BREACH', 0)
            
            # Get blocked IPs and locked accounts
            blocked_ips = IPBlacklist.objects.filter(
                created_at__gte=start_time,
                created_at__lte=end_time
            ).values_list('ip_address', flat=True)
            
            locked_accounts = UserBan.objects.filter(
                created_at__gte=start_time,
                created_at__lte=end_time
            ).values_list('user__username', flat=True)
            
            metrics['blocked_ips'] = list(blocked_ips)
            metrics['locked_accounts'] = list(locked_accounts)
            
            # Calculate response times (average response time for security events)
            response_times = security_logs.aggregate(
                avg_response_time=Avg('created_at')  # This is a placeholder
            )
            
            metrics['response_times'] = {
                'average_response_time': float(response_times['avg_response_time'] or 0)
            }
            
            # System load metrics (placeholder - would integrate with monitoring systems)
            metrics['system_load'] = {
                'cpu_usage': 0.0,  # Placeholder
                'memory_usage': 0.0,  # Placeholder
                'disk_usage': 0.0  # Placeholder
            }
            
            # Threat intelligence summary
            metrics['threat_intelligence'] = {
                'new_threats_detected': 0,  # Placeholder
                'threats_mitigated': 0,  # Placeholder
                'active_threats': 0  # Placeholder
            }
            
            # Compliance status
            metrics['compliance_status'] = {
                'overall_compliance': 'compliant',  # Placeholder
                'failed_checks': 0,  # Placeholder
                'critical_violations': 0  # Placeholder
            }
            
            # Generate recommendations based on metrics
            metrics['recommendations'] = self._generate_recommendations(metrics)
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error collecting daily metrics: {e}")
            return {
                'total_events': 0,
                'critical_count': 0,
                'high_count': 0,
                'medium_count': 0,
                'low_count': 0,
                'blocked_ips': [],
                'locked_accounts': [],
                'failed_logins': 0,
                'successful_logins': 0,
                'suspicious_activities': 0,
                'fraud_attempts': 0,
                'malware_detections': 0,
                'phishing_attempts': 0,
                'ddos_attacks': 0,
                'data_breaches': 0,
                'response_times': {},
                'system_load': {},
                'threat_intelligence': {},
                'compliance_status': {},
                'recommendations': []
            }
    
    def _generate_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """
        Generate security recommendations based on metrics
        """
        try:
            recommendations = []
            
            # High failure rate recommendation
            total_logins = metrics['failed_logins'] + metrics['successful_logins']
            if total_logins > 0:
                failure_rate = metrics['failed_logins'] / total_logins
                if failure_rate > 0.1:  # 10% failure rate
                    recommendations.append(
                        "High login failure rate detected. Consider implementing stronger authentication."
                    )
            
            # High critical events recommendation
            if metrics['critical_count'] > 5:
                recommendations.append(
                    "High number of critical security events. Immediate investigation recommended."
                )
            
            # Suspicious activity recommendation
            if metrics['suspicious_activities'] > 10:
                recommendations.append(
                    "Elevated suspicious activity detected. Review security logs and user behavior."
                )
            
            # Fraud attempts recommendation
            if metrics['fraud_attempts'] > 0:
                recommendations.append(
                    "Fraud attempts detected. Review transaction patterns and implement additional controls."
                )
            
            # Malware detection recommendation
            if metrics['malware_detections'] > 0:
                recommendations.append(
                    "Malware detected. Update antivirus definitions and scan affected systems."
                )
            
            # Phishing attempts recommendation
            if metrics['phishing_attempts'] > 0:
                recommendations.append(
                    "Phishing attempts detected. Review email security and user awareness training."
                )
            
            # DDoS attacks recommendation
            if metrics['ddos_attacks'] > 0:
                recommendations.append(
                    "DDoS attacks detected. Review network security and implement rate limiting."
                )
            
            # Data breaches recommendation
            if metrics['data_breaches'] > 0:
                recommendations.append(
                    "Data breaches detected. Immediate incident response and breach notification required."
                )
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Error generating recommendations: {e}")
            return []
    
    @handle_gracefully(default_return=[])
    def get_insights_trend(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get security insights trend for recent days
        """
        try:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)
            
            insights = SecurityInsight.objects.filter(
                date__gte=start_date,
                date__lte=end_date
            ).order_by('date')
            
            trend_data = []
            for insight in insights:
                trend_data.append({
                    'date': insight.date.isoformat(),
                    'total_events': insight.total_events,
                    'risk_score': insight.get_risk_score(),
                    'critical_count': insight.critical_count,
                    'high_count': insight.high_count,
                    'medium_count': insight.medium_count,
                    'low_count': insight.low_count
                })
            
            return trend_data
            
        except Exception as e:
            self.logger.error(f"Error getting insights trend: {e}")
            return []
    
    @handle_gracefully(default_return={})
    def get_security_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get comprehensive security summary for recent period
        """
        try:
            cache_key = f"security_summary_{days}"
            cached_result = self.cache_manager.get(cache_key)
            
            if cached_result is not None:
                return cached_result
            
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)
            
            # Get insights for the period
            insights = SecurityInsight.objects.filter(
                date__gte=start_date,
                date__lte=end_date
            ).order_by('date')
            
            if not insights:
                return {
                    'period': f"Last {days} days",
                    'total_events': 0,
                    'average_risk_score': 0.0,
                    'trend': 'insufficient_data',
                    'recommendations': ['No data available for analysis']
                }
            
            # Calculate summary statistics
            total_events = sum(insight.total_events for insight in insights)
            total_critical = sum(insight.critical_count for insight in insights)
            total_high = sum(insight.high_count for insight in insights)
            total_medium = sum(insight.medium_count for insight in insights)
            total_low = sum(insight.low_count for insight in insights)
            
            average_risk_score = sum(insight.get_risk_score() for insight in insights) / len(insights)
            
            # Calculate trend
            if len(insights) >= 2:
                recent_avg = sum(insights[-3:].total_events) / min(3, len(insights))
                older_avg = sum(insights[:-3].total_events) / max(1, len(insights) - 3)
                
                if recent_avg > older_avg * 1.2:
                    trend = 'increasing'
                elif recent_avg < older_avg * 0.8:
                    trend = 'decreasing'
                else:
                    trend = 'stable'
            else:
                trend = 'insufficient_data'
            
            # Generate period-specific recommendations
            recommendations = []
            if average_risk_score > 50:
                recommendations.append("High average risk score detected. Review security measures.")
            if total_critical > 0:
                recommendations.append(f"{total_critical} critical events in period. Immediate attention required.")
            if trend == 'increasing':
                recommendations.append("Security events trending upward. Monitor closely.")
            
            summary = {
                'period': f"Last {days} days",
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total_events': total_events,
                'average_risk_score': average_risk_score,
                'severity_breakdown': {
                    'critical': total_critical,
                    'high': total_high,
                    'medium': total_medium,
                    'low': total_low
                },
                'trend': trend,
                'days_analyzed': len(insights),
                'recommendations': recommendations
            }
            
            # Cache for 10 minutes
            self.cache_manager.set(cache_key, summary, timeout=600)
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting security summary: {e}")
            return {'error': str(e)}
    
    @handle_gracefully(default_return=0)
    def cleanup_old_insights(self, days_to_keep: int = 365) -> int:
        """
        Clean up old security insights
        """
        try:
            cutoff_date = timezone.now().date() - timedelta(days=days_to_keep)
            
            deleted_count = SecurityInsight.objects.filter(
                date__lt=cutoff_date
            ).delete()
            
            self.logger.info(f"Cleaned up {deleted_count} old security insights")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old insights: {e}")
            return 0
    
    @handle_gracefully(default_return={})
    def export_insights_report(self, start_date: date, end_date: date, 
                           format_type: str = 'json') -> Dict[str, Any]:
        """
        Export security insights report for a date range
        """
        try:
            insights = SecurityInsight.objects.filter(
                date__gte=start_date,
                date__lte=end_date
            ).order_by('date')
            
            if format_type.lower() == 'json':
                report_data = []
                for insight in insights:
                    report_data.append({
                        'date': insight.date.isoformat(),
                        'total_events': insight.total_events,
                        'risk_score': insight.get_risk_score(),
                        'event_breakdown': insight.get_event_breakdown(),
                        'trend_analysis': insight.get_trend_analysis()
                    })
                
                return {
                    'format': 'json',
                    'data': report_data,
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'total_records': len(report_data)
                }
            
            elif format_type.lower() == 'csv':
                # CSV format would require additional CSV generation logic
                return {
                    'format': 'csv',
                    'error': 'CSV export not implemented yet'
                }
            
            else:
                return {
                    'format': format_type,
                    'error': f'Unsupported format: {format_type}'
                }
                
        except Exception as e:
            self.logger.error(f"Error exporting insights report: {e}")
            return {'error': str(e)}