"""
Security Analytics Module
Advanced analytics and reporting for security data
"""
from django.conf import settings

import logging
from typing import Dict, List, Any, Optional, Type, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import models
from django.core.cache import cache
from django.db.models import Count, Avg, Max, Min, Sum, Q, F, Func, Value
from django.db.models.functions import Extract, Trunc, Cast

from .models import SecurityLog, SecurityIncident, ThreatIntelligence, UserBan, DeviceInfo
from .selectors import SecurityLogSelector, SecurityIncidentSelector, ThreatIntelligenceSelector
from .utils import SecurityUtils
from .helpers import SecurityMetrics, TimeHelper
# DeviceInfo stub — replace with real import if available
try:
    from api.security.models import DeviceInfo
except ImportError:
    class DeviceInfo:
        pass



User = get_user_model()
logger = logging.getLogger('security.analytics')


class SecurityAnalytics:
    """Main analytics class for security data"""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
        self.log_selector = SecurityLogSelector()
        self.incident_selector = SecurityIncidentSelector()
        self.threat_selector = ThreatIntelligenceSelector()
    
    def get_overview_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive overview statistics"""
        cache_key = f"security_overview_{days}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        start_date = timezone.now() - timedelta(days=days)
        
        # Basic counts
        total_logs = self.log_selector.filter_by_date_range(start_date, timezone.now()).count()
        total_incidents = self.incident_selector.filter_by_date_opened(start_date, timezone.now()).count()
        total_threats = self.threat_selector.filter_recently_added(hours=days*24).count()
        
        # Risk metrics
        high_risk_logs = self.log_selector.filter_high_risk(70).count()
        failed_attempts = self.log_selector.filter_failed_attempts().count()
        
        # User metrics
        unique_users = self.log_selector.filter_by_date_range(start_date, timezone.now()).values('user').distinct().count()
        unique_ips = self.log_selector.filter_by_date_range(start_date, timezone.now()).values('ip_address').distinct().count()
        
        # Calculate risk score
        risk_factors = {
            'high_risk_percentage': (high_risk_logs / max(1, total_logs)) * 100,
            'failed_attempt_rate': (failed_attempts / max(1, total_logs)) * 100,
            'incident_rate': (total_incidents / max(1, total_logs)) * 100
        }
        
        overall_risk_score = SecurityMetrics.calculate_risk_score(risk_factors)
        
        overview = {
            'period_days': days,
            'summary': {
                'total_events': total_logs,
                'total_incidents': total_incidents,
                'total_threats': total_threats,
                'unique_users': unique_users,
                'unique_ips': unique_ips,
                'overall_risk_score': overall_risk_score
            },
            'risk_metrics': risk_factors,
            'trend_data': self._get_trend_data(days),
            'top_threats': self._get_top_threats(days),
            'security_health_score': self._calculate_security_health_score(risk_factors)
        }
        
        cache.set(cache_key, overview, self.cache_timeout)
        return overview
    
    def get_security_health_score(self) -> Dict[str, Any]:
        """Get detailed security health score"""
        cache_key = "security_health_score"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        # Get various metrics
        last_24h_logs = self.log_selector.filter_recent(hours=24)
        last_24h_incidents = self.incident_selector.filter_recently_opened(hours=24)
        
        # Calculate health components
        components = {
            'log_analysis': self._calculate_log_analysis_score(last_24h_logs),
            'incident_response': self._calculate_incident_response_score(last_24h_incidents),
            'threat_detection': self._calculate_threat_detection_score(),
            'user_behavior': self._calculate_user_behavior_score(),
            'system_performance': self._calculate_system_performance_score()
        }
        
        # Calculate overall score
        weights = {
            'log_analysis': 0.25,
            'incident_response': 0.20,
            'threat_detection': 0.25,
            'user_behavior': 0.15,
            'system_performance': 0.15
        }
        
        overall_score = sum(components[component] * weight for component, weight in weights.items())
        
        health_data = {
            'overall_score': overall_score,
            'components': components,
            'grade': self._get_health_grade(overall_score),
            'recommendations': self._get_health_recommendations(overall_score, components),
            'calculated_at': timezone.now().isoformat()
        }
        
        cache.set(cache_key, health_data, self.cache_timeout)
        return health_data
    
    def get_user_behavior_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get user behavior analytics"""
        cache_key = f"user_behavior_analytics_{days}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        start_date = timezone.now() - timedelta(days=days)
        logs = self.log_selector.filter_by_date_range(start_date, timezone.now())
        
        # User activity patterns
        user_activity = logs.values('user__username').annotate(
            total_events=Count('id'),
            failed_attempts=Count('id', filter=Q(security_type='login_failed')),
            unique_ips=Count('ip_address', distinct=True),
            avg_risk_score=Avg('risk_score'),
            last_activity=Max('created_at')
        ).order_by('-total_events')[:50]
        
        # Time-based patterns
        hourly_patterns = self._get_hourly_user_patterns(logs)
        
        # Geographic patterns
        geographic_patterns = self._get_geographic_user_patterns(logs)
        
        # Risk distribution
        risk_distribution = self._get_user_risk_distribution(logs)
        
        # Suspicious users
        suspicious_users = self._identify_suspicious_users(logs)
        
        analytics = {
            'period_days': days,
            'user_activity': list(user_activity),
            'hourly_patterns': hourly_patterns,
            'geographic_patterns': geographic_patterns,
            'risk_distribution': risk_distribution,
            'suspicious_users': suspicious_users,
            'summary': {
                'total_active_users': user_activity.count(),
                'avg_events_per_user': user_activity.aggregate(avg=Avg('total_events'))['avg'],
                'high_risk_users': len([u for u in user_activity if u['avg_risk_score'] > 70])
            }
        }
        
        cache.set(cache_key, analytics, self.cache_timeout)
        return analytics
    
    def get_threat_intelligence_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get threat intelligence analytics"""
        cache_key = f"threat_intelligence_analytics_{days}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        threats = self.threat_selector.filter_recently_added(hours=days*24)
        
        # Threat trends
        threat_trends = self._get_threat_trends(threats)
        
        # Threat sources
        threat_sources = self._get_threat_sources(threats)
        
        # Threat severity distribution
        severity_distribution = threats.get_severity_distribution()
        
        # Threat effectiveness
        effectiveness = self._calculate_threat_effectiveness(threats)
        
        # Emerging threats
        emerging_threats = self._identify_emerging_threats(threats)
        
        analytics = {
            'period_days': days,
            'total_threats': threats.count(),
            'threat_trends': threat_trends,
            'threat_sources': threat_sources,
            'severity_distribution': severity_distribution,
            'threat_effectiveness': effectiveness,
            'emerging_threats': emerging_threats,
            'summary': {
                'average_confidence': threats.get_average_confidence(),
                'high_confidence_threats': threats.filter_high_confidence(0.8).count(),
                'critical_threats': threats.filter_critical_threats().count()
            }
        }
        
        cache.set(cache_key, analytics, self.cache_timeout)
        return analytics
    
    def get_incident_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get incident analytics"""
        cache_key = f"incident_analytics_{days}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        incidents = self.incident_selector.filter_by_date_opened(
            timezone.now() - timedelta(days=days),
            timezone.now()
        )
        
        # Incident trends
        incident_trends = self._get_incident_trends(incidents)
        
        # Resolution metrics
        resolution_metrics = self._get_resolution_metrics(incidents)
        
        # Incident types
        type_distribution = incidents.get_type_distribution()
        
        # Priority distribution
        priority_distribution = incidents.get_priority_distribution()
        
        # Top affected systems
        affected_systems = self._get_affected_systems(incidents)
        
        analytics = {
            'period_days': days,
            'total_incidents': incidents.count(),
            'incident_trends': incident_trends,
            'resolution_metrics': resolution_metrics,
            'type_distribution': type_distribution,
            'priority_distribution': priority_distribution,
            'affected_systems': affected_systems,
            'summary': {
                'open_incidents': incidents.filter_open().count(),
                'critical_incidents': incidents.filter_critical().count(),
                'average_resolution_time': incidents.get_average_resolution_time(),
                'resolution_rate': resolution_metrics.get('resolution_rate', 0)
            }
        }
        
        cache.set(cache_key, analytics, self.cache_timeout)
        return analytics
    
    def get_compliance_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get compliance analytics"""
        cache_key = f"compliance_analytics_{days}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        # Compliance metrics
        logs = self.log_selector.filter_recent(days=days)
        
        compliance_metrics = {
            'audit_trail_completeness': self._calculate_audit_completeness(logs),
            'data_retention_compliance': self._calculate_retention_compliance(logs),
            'access_control_compliance': self._calculate_access_control_compliance(logs),
            'encryption_compliance': self._calculate_encryption_compliance(logs),
            'logging_compliance': self._calculate_logging_compliance(logs)
        }
        
        # Overall compliance score
        weights = {
            'audit_trail_completeness': 0.25,
            'data_retention_compliance': 0.20,
            'access_control_compliance': 0.25,
            'encryption_compliance': 0.20,
            'logging_compliance': 0.10
        }
        
        overall_score = sum(compliance_metrics[metric] * weight for metric, weight in weights.items())
        
        analytics = {
            'period_days': days,
            'compliance_metrics': compliance_metrics,
            'overall_compliance_score': overall_score,
            'compliance_grade': self._get_compliance_grade(overall_score),
            'violations': self._get_compliance_violations(logs),
            'recommendations': self._get_compliance_recommendations(compliance_metrics)
        }
        
        cache.set(cache_key, analytics, self.cache_timeout)
        return analytics
    
    def get_performance_analytics(self, days: int = 7) -> Dict[str, Any]:
        """Get performance analytics"""
        cache_key = f"performance_analytics_{days}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        logs = self.log_selector.filter_recent(days=days)
        
        # Performance metrics
        performance_metrics = {
            'average_response_time': logs.aggregate(avg=Avg('response_time_ms'))['avg'],
            'slow_requests': logs.filter_slow_responses(1000).count(),
            'error_rate': self._calculate_error_rate(logs),
            'throughput': self._calculate_throughput(logs),
            'resource_utilization': self._calculate_resource_utilization()
        }
        
        # Performance trends
        performance_trends = self._get_performance_trends(logs)
        
        # Bottlenecks
        bottlenecks = self._identify_performance_bottlenecks(logs)
        
        analytics = {
            'period_days': days,
            'performance_metrics': performance_metrics,
            'performance_trends': performance_trends,
            'bottlenecks': bottlenecks,
            'performance_grade': self._get_performance_grade(performance_metrics),
            'optimization_recommendations': self._get_optimization_recommendations(performance_metrics)
        }
        
        cache.set(cache_key, analytics, self.cache_timeout)
        return analytics
    
    def _get_trend_data(self, days: int) -> Dict[str, Any]:
        """Get trend data for overview"""
        daily_data = []
        
        for i in range(days):
            date = timezone.now() - timedelta(days=i)
            start_time = timezone.make_aware(datetime.combine(date, datetime.min.time()))
            end_time = start_time + timedelta(days=1)
            
            logs = self.log_selector.filter_by_date_range(start_time, end_time)
            incidents = self.incident_selector.filter_by_date_opened(start_time, end_time)
            
            daily_data.append({
                'date': date.isoformat(),
                'events': logs.count(),
                'incidents': incidents.count(),
                'high_risk': logs.filter_high_risk().count(),
                'failed_attempts': logs.filter_failed_attempts().count()
            })
        
        return daily_data
    
    def _get_top_threats(self, days: int) -> List[Dict[str, Any]]:
        """Get top threats"""
        threats = self.threat_selector.filter_recently_added(hours=days*24)
        
        return list(
            threats.values('threat_type')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
            .values('threat_type', 'count')
        )
    
    def _calculate_security_health_score(self, risk_factors: Dict[str, Any]) -> float:
        """Calculate security health score"""
        # Base score starts at 100
        score = 100.0
        
        # Deduct points for risk factors
        score -= risk_factors.get('high_risk_percentage', 0) * 0.5
        score -= risk_factors.get('failed_attempt_rate', 0) * 0.3
        score -= risk_factors.get('incident_rate', 0) * 0.2
        
        return max(0.0, min(100.0, score))
    
    def _calculate_log_analysis_score(self, logs) -> float:
        """Calculate log analysis score"""
        if not logs.exists():
            return 0.0
        
        # Check for proper logging
        total_logs = logs.count()
        logged_with_metadata = logs.filter(metadata__has_key='request_id').count()
        
        metadata_score = (logged_with_metadata / total_logs) * 100 if total_logs > 0 else 0
        
        # Check for timely logging
        recent_logs = logs.filter_recent(hours=1)
        timely_score = min(100, (recent_logs.count() / 10) * 100)  # Expect at least 10 logs per hour
        
        return (metadata_score + timely_score) / 2
    
    def _calculate_incident_response_score(self, incidents) -> float:
        """Calculate incident response score"""
        if not incidents.exists():
            return 100.0
        
        # Resolution rate
        resolved_count = incidents.filter_resolved().count()
        resolution_rate = (resolved_count / incidents.count()) * 100
        
        # Resolution time
        avg_resolution_time = incidents.get_average_resolution_time()
        if avg_resolution_time:
            # Convert to hours and score (better score for faster resolution)
            resolution_hours = avg_resolution_time.total_seconds() / 3600
            time_score = max(0, 100 - (resolution_hours / 24) * 100)  # Deduct points for each day
        else:
            time_score = 50  # Neutral score
        
        return (resolution_rate + time_score) / 2
    
    def _calculate_threat_detection_score(self) -> float:
        """Calculate threat detection score"""
        active_threats = self.threat_selector.filter_active()
        
        if not active_threats.exists():
            return 100.0
        
        # Check threat intelligence quality
        avg_confidence = active_threats.get_average_confidence()
        confidence_score = avg_confidence * 100
        
        # Check coverage
        total_threat_types = len(set(active_threats.values_list('threat_type', flat=True)))
        coverage_score = min(100, (total_threat_types / 10) * 100)  # Expect at least 10 threat types
        
        return (confidence_score + coverage_score) / 2
    
    def _calculate_user_behavior_score(self) -> float:
        """Calculate user behavior score"""
        recent_logs = self.log_selector.filter_recent(hours=24)
        
        if not recent_logs.exists():
            return 100.0
        
        # Check for normal behavior patterns
        failed_rate = (recent_logs.filter_failed_attempts().count() / recent_logs.count()) * 100
        behavior_score = max(0, 100 - failed_rate * 2)  # Deduct points for failed attempts
        
        # Check for unusual patterns
        unique_ips = recent_logs.values('ip_address').distinct().count()
        total_users = recent_logs.values('user').distinct().count()
        
        if total_users > 0:
            avg_ips_per_user = unique_ips / total_users
            pattern_score = max(0, 100 - (avg_ips_per_user - 2) * 10)  # Expect ~2 IPs per user
        else:
            pattern_score = 100
        
        return (behavior_score + pattern_score) / 2
    
    def _calculate_system_performance_score(self) -> float:
        """Calculate system performance score"""
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_score = max(0, 100 - cpu_percent)
            
            # Memory usage
            memory_percent = psutil.virtual_memory().percent
            memory_score = max(0, 100 - memory_percent)
            
            # Disk usage
            disk_percent = psutil.disk_usage('/').percent
            disk_score = max(0, 100 - disk_percent)
            
            return (cpu_score + memory_score + disk_score) / 3
            
        except ImportError:
            return 75.0  # Default score if psutil not available
        except Exception:
            return 50.0  # Low score on error
    
    def _get_health_grade(self, score: float) -> str:
        """Get health grade from score"""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'
    
    def _get_health_recommendations(self, score: float, components: Dict[str, Any]) -> List[str]:
        """Get health recommendations"""
        recommendations = []
        
        if score < 70:
            recommendations.append("Overall security health requires attention")
        
        # Component-specific recommendations
        if components.get('log_analysis', 0) < 70:
            recommendations.append("Improve log completeness and metadata")
        
        if components.get('incident_response', 0) < 70:
            recommendations.append("Enhance incident response procedures")
        
        if components.get('threat_detection', 0) < 70:
            recommendations.append("Update threat intelligence sources")
        
        if components.get('user_behavior', 0) < 70:
            recommendations.append("Monitor user behavior patterns")
        
        if components.get('system_performance', 0) < 70:
            recommendations.append("Optimize system performance")
        
        return recommendations
    
    def _get_hourly_user_patterns(self, logs) -> List[Dict[str, Any]]:
        """Get hourly user activity patterns"""
        hourly_data = []
        
        for hour in range(24):
            hour_logs = logs.filter(created_at__hour=hour)
            
            hourly_data.append({
                'hour': hour,
                'total_events': hour_logs.count(),
                'unique_users': hour_logs.values('user').distinct().count(),
                'failed_attempts': hour_logs.filter_failed_attempts().count()
            })
        
        return hourly_data
    
    def _get_geographic_user_patterns(self, logs) -> Dict[str, Any]:
        """Get geographic user patterns"""
        geo_data = {}
        
        for log in logs[:1000]:  # Limit to prevent performance issues
            country = log.metadata.get('country', 'Unknown')
            
            if country not in geo_data:
                geo_data[country] = {
                    'count': 0,
                    'unique_users': set(),
                    'failed_attempts': 0
                }
            
            geo_data[country]['count'] += 1
            if log.user:
                geo_data[country]['unique_users'].add(log.user.id)
            
            if log.security_type == 'login_failed':
                geo_data[country]['failed_attempts'] += 1
        
        # Convert sets to counts
        for country in geo_data:
            geo_data[country]['unique_users'] = len(geo_data[country]['unique_users'])
        
        return geo_data
    
    def _get_user_risk_distribution(self, logs) -> Dict[str, int]:
        """Get user risk distribution"""
        risk_dist = {
            'low': 0,
            'medium': 0,
            'high': 0,
            'critical': 0
        }
        
        for log in logs[:1000]:  # Limit to prevent performance issues
            if log.risk_score:
                if log.risk_score < 30:
                    risk_dist['low'] += 1
                elif log.risk_score < 70:
                    risk_dist['medium'] += 1
                elif log.risk_score < 90:
                    risk_dist['high'] += 1
                else:
                    risk_dist['critical'] += 1
        
        return risk_dist
    
    def _identify_suspicious_users(self, logs) -> List[Dict[str, Any]]:
        """Identify suspicious users"""
        suspicious_users = []
        
        user_stats = {}
        
        # Calculate user statistics
        for log in logs[:1000]:  # Limit to prevent performance issues
            if log.user:
                user_id = log.user.id
                
                if user_id not in user_stats:
                    user_stats[user_id] = {
                        'username': log.user.username,
                        'total_events': 0,
                        'failed_attempts': 0,
                        'unique_ips': set(),
                        'high_risk_events': 0,
                        'avg_risk_score': 0
                    }
                
                user_stats[user_id]['total_events'] += 1
                
                if log.security_type == 'login_failed':
                    user_stats[user_id]['failed_attempts'] += 1
                
                if log.ip_address:
                    user_stats[user_id]['unique_ips'].add(log.ip_address)
                
                if log.risk_score and log.risk_score > 70:
                    user_stats[user_id]['high_risk_events'] += 1
        
        # Identify suspicious patterns
        for user_id, stats in user_stats.items():
            suspicious_indicators = []
            
            # High failed attempt rate
            if stats['total_events'] > 0:
                failed_rate = stats['failed_attempts'] / stats['total_events']
                if failed_rate > 0.3:  # More than 30% failed
                    suspicious_indicators.append('high_failed_rate')
            
            # Many unique IPs
            if len(stats['unique_ips']) > 10:
                suspicious_indicators.append('many_unique_ips')
            
            # Many high risk events
            if stats['high_risk_events'] > 5:
                suspicious_indicators.append('many_high_risk_events')
            
            if suspicious_indicators:
                suspicious_users.append({
                    'user_id': user_id,
                    'username': stats['username'],
                    'suspicious_indicators': suspicious_indicators,
                    'total_events': stats['total_events'],
                    'failed_attempts': stats['failed_attempts'],
                    'unique_ips': len(stats['unique_ips']),
                    'high_risk_events': stats['high_risk_events']
                })
        
        return suspicious_users
    
    # Additional helper methods for other analytics functions
    def _get_threat_trends(self, threats) -> List[Dict[str, Any]]:
        """Get threat trends"""
        return list(
            threats.extra(
                select={'day': Trunc('created_at', 'day')}
            ).values('day')
            .annotate(count=Count('id'))
            .order_by('day')
            .values('day', 'count')
        )
    
    def _get_threat_sources(self, threats) -> List[Dict[str, Any]]:
        """Get threat sources"""
        return list(
            threats.values('source')
            .annotate(count=Count('id'))
            .order_by('-count')
            .values('source', 'count')
        )
    
    def _calculate_threat_effectiveness(self, threats) -> Dict[str, Any]:
        """Calculate threat effectiveness"""
        # This would involve checking if threats were blocked/prevented
        # Simplified implementation
        return {
            'blocked_threats': threats.filter(is_active=False).count(),
            'active_threats': threats.filter(is_active=True).count(),
            'effectiveness_rate': 0.85  # Placeholder
        }
    
    def _identify_emerging_threats(self, threats) -> List[Dict[str, Any]]:
        """Identify emerging threats"""
        # Recently added threats with high confidence
        return list(
            threats.filter_recently_added(hours=168)  # Last week
            .filter_high_confidence(0.8)
            .values('threat_type', 'indicator', 'confidence')
            .order_by('-created_at')[:10]
        )
    
    def _get_incident_trends(self, incidents) -> List[Dict[str, Any]]:
        """Get incident trends"""
        return list(
            incidents.extra(
                select={'day': Trunc('opened_at', 'day')}
            ).values('day')
            .annotate(count=Count('id'))
            .order_by('day')
            .values('day', 'count')
        )
    
    def _get_resolution_metrics(self, incidents) -> Dict[str, Any]:
        """Get resolution metrics"""
        resolved = incidents.filter_resolved()
        
        if not resolved.exists():
            return {
                'resolution_rate': 0,
                'average_resolution_time': None,
                'median_resolution_time': None
            }
        
        resolution_times = []
        for incident in resolved:
            if incident.resolved_at and incident.opened_at:
                resolution_times.append(
                    (incident.resolved_at - incident.opened_at).total_seconds()
                )
        
        if resolution_times:
            resolution_times.sort()
            median_time = resolution_times[len(resolution_times) // 2]
        else:
            median_time = 0
        
        return {
            'resolution_rate': (resolved.count() / incidents.count()) * 100,
            'average_resolution_time': incidents.get_average_resolution_time(),
            'median_resolution_time': timedelta(seconds=median_time) if median_time > 0 else None
        }
    
    def _get_affected_systems(self, incidents) -> List[Dict[str, Any]]:
        """Get affected systems"""
        system_stats = {}
        
        for incident in incidents:
            for system in incident.affected_systems:
                if system not in system_stats:
                    system_stats[system] = 0
                system_stats[system] += 1
        
        return [
            {'system': system, 'count': count}
            for system, count in sorted(system_stats.items(), key=lambda x: x[1], reverse=True)
        ]
    
    def _calculate_audit_completeness(self, logs) -> float:
        """Calculate audit trail completeness"""
        # Check for required audit fields
        required_fields = ['user', 'ip_address', 'created_at']
        
        complete_logs = 0
        for log in logs[:1000]:  # Sample for performance
            if all(getattr(log, field, None) for field in required_fields):
                complete_logs += 1
        
        return (complete_logs / min(1000, logs.count())) * 100
    
    def _calculate_retention_compliance(self, logs) -> float:
        """Calculate data retention compliance"""
        # Check if logs are within retention period
        retention_days = getattr(settings, 'SECURITY_LOG_RETENTION_DAYS', 90)
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        old_logs = logs.filter(created_at__lt=cutoff_date).count()
        
        # Compliance score based on how many old logs exist (should be minimal)
        if logs.count() > 0:
            compliance = 100 - ((old_logs / logs.count()) * 100)
        else:
            compliance = 100
        
        return max(0, compliance)
    
    def _calculate_access_control_compliance(self, logs) -> float:
        """Calculate access control compliance"""
        # Check for proper access logging
        access_logs = logs.filter(security_type__in=['access_granted', 'access_denied'])
        
        if access_logs.count() == 0:
            return 100
        
        # Check if access logs have required fields
        compliant_logs = access_logs.filter(
            user__isnull=False,
            ip_address__isnull=False
        ).count()
        
        return (compliant_logs / access_logs.count()) * 100
    
    def _calculate_encryption_compliance(self, logs) -> float:
        """Calculate encryption compliance"""
        # This would check if sensitive data is encrypted
        # Simplified implementation
        return 85.0  # Placeholder
    
    def _calculate_logging_compliance(self, logs) -> float:
        """Calculate logging compliance"""
        # Check if all security events are logged
        expected_events = ['login_success', 'login_failed', 'access_denied', 'permission_denied']
        logged_events = set(logs.values_list('security_type', flat=True))
        
        compliance = len(set(expected_events) & logged_events) / len(expected_events) * 100
        
        return compliance
    
    def _get_compliance_grade(self, score: float) -> str:
        """Get compliance grade"""
        if score >= 95:
            return 'Excellent'
        elif score >= 85:
            return 'Good'
        elif score >= 75:
            return 'Fair'
        elif score >= 65:
            return 'Poor'
        else:
            return 'Non-compliant'
    
    def _get_compliance_violations(self, logs) -> List[Dict[str, Any]]:
        """Get compliance violations"""
        violations = []
        
        # Check for missing user information
        missing_user = logs.filter(user__isnull=True).count()
        if missing_user > 0:
            violations.append({
                'type': 'missing_user',
                'count': missing_user,
                'severity': 'high'
            })
        
        # Check for missing IP information
        missing_ip = logs.filter(ip_address__isnull=True).count()
        if missing_ip > 0:
            violations.append({
                'type': 'missing_ip',
                'count': missing_ip,
                'severity': 'medium'
            })
        
        return violations
    
    def _get_compliance_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """Get compliance recommendations"""
        recommendations = []
        
        for metric, score in metrics.items():
            if score < 80:
                if metric == 'audit_trail_completeness':
                    recommendations.append("Improve audit trail completeness")
                elif metric == 'data_retention_compliance':
                    recommendations.append("Review data retention policies")
                elif metric == 'access_control_compliance':
                    recommendations.append("Enhance access control logging")
                elif metric == 'encryption_compliance':
                    recommendations.append("Implement data encryption")
                elif metric == 'logging_compliance':
                    recommendations.append("Improve security event logging")
        
        return recommendations
    
    def _calculate_error_rate(self, logs) -> float:
        """Calculate error rate"""
        error_logs = logs.filter(severity='error').count()
        return (error_logs / logs.count()) * 100 if logs.count() > 0 else 0
    
    def _calculate_throughput(self, logs) -> float:
        """Calculate throughput (events per second)"""
        if logs.count() == 0:
            return 0
        
        time_range = logs.aggregate(
            min_time=Min('created_at'),
            max_time=Max('created_at')
        )
        
        if time_range['min_time'] and time_range['max_time']:
            duration = (time_range['max_time'] - time_range['min_time']).total_seconds()
            return logs.count() / duration if duration > 0 else 0
        
        return 0
    
    def _calculate_resource_utilization(self) -> Dict[str, float]:
        """Calculate resource utilization"""
        try:
            import psutil
            
            return {
                'cpu': psutil.cpu_percent(),
                'memory': psutil.virtual_memory().percent,
                'disk': psutil.disk_usage('/').percent
            }
        except ImportError:
            return {'cpu': 0, 'memory': 0, 'disk': 0}
    
    def _get_performance_trends(self, logs) -> List[Dict[str, Any]]:
        """Get performance trends"""
        return list(
            logs.extra(
                select={'hour': Extract('created_at', 'hour')}
            ).values('hour')
            .annotate(
                avg_response_time=Avg('response_time_ms'),
                slow_requests=Count('id', filter=Q(response_time_ms__gt=1000))
            )
            .order_by('hour')
            .values('hour', 'avg_response_time', 'slow_requests')
        )
    
    def _identify_performance_bottlenecks(self, logs) -> List[Dict[str, Any]]:
        """Identify performance bottlenecks"""
        bottlenecks = []
        
        # Slow endpoints
        slow_endpoints = logs.filter(response_time_ms__gt=1000).values('metadata__endpoint').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        for endpoint in slow_endpoints:
            bottlenecks.append({
                'type': 'slow_endpoint',
                'endpoint': endpoint['endpoint'],
                'slow_requests': endpoint['count']
            })
        
        return bottlenecks
    
    def _get_performance_grade(self, metrics: Dict[str, Any]) -> str:
        """Get performance grade"""
        avg_response = metrics.get('average_response_time', 0)
        error_rate = metrics.get('error_rate', 0)
        
        if avg_response < 100 and error_rate < 1:
            return 'A'
        elif avg_response < 500 and error_rate < 5:
            return 'B'
        elif avg_response < 1000 and error_rate < 10:
            return 'C'
        elif avg_response < 2000 and error_rate < 20:
            return 'D'
        else:
            return 'F'
    
    def _get_optimization_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """Get optimization recommendations"""
        recommendations = []
        
        if metrics.get('average_response_time', 0) > 500:
            recommendations.append("Optimize database queries and add caching")
        
        if metrics.get('error_rate', 0) > 5:
            recommendations.append("Improve error handling and logging")
        
        if metrics.get('slow_requests', 0) > 100:
            recommendations.append("Identify and optimize slow endpoints")
        
        return recommendations


# Global analytics instance
security_analytics = SecurityAnalytics()


# Export classes and utilities
__all__ = [
    'SecurityAnalytics',
    'security_analytics'
]