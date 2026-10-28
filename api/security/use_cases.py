"""
Security Use Cases Module
Business logic use cases for security operations
"""
from django.db import models

import logging
from typing import Dict, List, Any, Optional, Type, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache

from .models import SecurityLog, SecurityIncident, ThreatIntelligence, UserBan
from .selectors import (
    SecurityLogSelector, DeviceInfoSelector, SecurityIncidentSelector,
    ThreatIntelligenceSelector, UserBanSelector
)
from .utils import SecurityUtils
from .helpers import SecurityMetrics, DataValidator
# DeviceInfo stub — replace with real import if available
try:
    from api.security.models import DeviceInfo
except ImportError:
    class DeviceInfo:
        pass



User = get_user_model()
logger = logging.getLogger('security.use_cases')


class BaseUseCase:
    """Base use case class with common functionality"""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
    
    def execute(self, *args, **kwargs):
        """Execute the use case"""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate input data"""
        return True
    
    def log_execution(self, use_case_name: str, result: Any, error: Exception = None):
        """Log use case execution"""
        if error:
            logger.error(f"Use case {use_case_name} failed: {error}")
        else:
            logger.info(f"Use case {use_case_name} executed successfully")


class SecurityAnalysisUseCase(BaseUseCase):
    """Use case for security analysis"""
    
    def __init__(self):
        super().__init__()
        self.log_selector = SecurityLogSelector()
        self.incident_selector = SecurityIncidentSelector()
    
    def execute(self, analysis_type: str = 'comprehensive', 
               time_period: str = 'last_24h', **kwargs) -> Dict[str, Any]:
        """Execute security analysis"""
        try:
            # Get time range
            start_date, end_date = self._get_time_range(time_period)
            
            # Perform analysis based on type
            if analysis_type == 'comprehensive':
                return self._comprehensive_analysis(start_date, end_date, **kwargs)
            elif analysis_type == 'threat_assessment':
                return self._threat_assessment(start_date, end_date, **kwargs)
            elif analysis_type == 'user_behavior':
                return self._user_behavior_analysis(start_date, end_date, **kwargs)
            elif analysis_type == 'incident_trends':
                return self._incident_trends_analysis(start_date, end_date, **kwargs)
            else:
                raise ValueError(f"Unknown analysis type: {analysis_type}")
                
        except Exception as e:
            self.log_execution('security_analysis', None, e)
            raise
    
    def _get_time_range(self, time_period: str) -> tuple:
        """Get time range for analysis"""
        now = timezone.now()
        
        if time_period == 'last_hour':
            start = now - timedelta(hours=1)
        elif time_period == 'last_24h':
            start = now - timedelta(hours=24)
        elif time_period == 'last_7d':
            start = now - timedelta(days=7)
        elif time_period == 'last_30d':
            start = now - timedelta(days=30)
        else:
            start = now - timedelta(hours=24)  # Default
        
        return start, now
    
    def _comprehensive_analysis(self, start_date: datetime, end_date: datetime, **kwargs) -> Dict[str, Any]:
        """Perform comprehensive security analysis"""
        # Get security logs
        logs = self.log_selector.filter_by_date_range(start_date, end_date)
        
        # Get incidents
        incidents = self.incident_selector.filter_by_date_opened(start_date, end_date)
        
        # Calculate metrics
        total_logs = logs.count()
        total_incidents = incidents.count()
        high_risk_logs = logs.filter_high_risk().count()
        failed_attempts = logs.filter_failed_attempts().count()
        
        # Get distributions
        severity_dist = logs.get_severity_distribution()
        type_dist = logs.get_security_types_count()
        incident_status_dist = incidents.get_status_distribution()
        
        # Get top activity
        top_ips = logs.get_top_ip_addresses(limit=10)
        top_users = logs.get_top_users(limit=10)
        
        # Calculate risk scores
        risk_factors = {
            'high_risk_percentage': (high_risk_logs / max(1, total_logs)) * 100,
            'failed_attempt_rate': (failed_attempts / max(1, total_logs)) * 100,
            'incident_rate': (total_incidents / max(1, total_logs)) * 100
        }
        
        overall_risk_score = SecurityMetrics.calculate_risk_score(risk_factors)
        
        return {
            'analysis_type': 'comprehensive',
            'time_period': f"{start_date} to {end_date}",
            'summary': {
                'total_logs': total_logs,
                'total_incidents': total_incidents,
                'high_risk_logs': high_risk_logs,
                'failed_attempts': failed_attempts,
                'overall_risk_score': overall_risk_score
            },
            'distributions': {
                'severity': severity_dist,
                'security_types': type_dist,
                'incident_status': incident_status_dist
            },
            'top_activity': {
                'ip_addresses': top_ips,
                'users': top_users
            },
            'risk_factors': risk_factors,
            'recommendations': self._generate_recommendations(overall_risk_score, risk_factors)
        }
    
    def _threat_assessment(self, start_date: datetime, end_date: datetime, **kwargs) -> Dict[str, Any]:
        """Perform threat assessment"""
        logs = self.log_selector.filter_by_date_range(start_date, end_date)
        
        # Get threat indicators
        failed_logins = logs.filter_by_security_type('login_failed').count()
        blocked_ips = logs.filter_by_security_type('ip_blocked').count()
        malware_detected = logs.filter_by_security_type('malware_detected').count()
        suspicious_activity = logs.filter_high_risk().count()
        
        # Calculate threat score
        threat_indicators = [
            {'type': 'failed_login', 'confidence': 0.8, 'severity': 'medium'},
            {'type': 'blocked_ip', 'confidence': 0.9, 'severity': 'high'},
            {'type': 'malware', 'confidence': 0.95, 'severity': 'critical'},
            {'type': 'suspicious_activity', 'confidence': 0.7, 'severity': 'medium'}
        ]
        
        threat_score = SecurityMetrics.calculate_threat_score(threat_indicators)
        
        return {
            'analysis_type': 'threat_assessment',
            'time_period': f"{start_date} to {end_date}",
            'threat_score': threat_score,
            'indicators': {
                'failed_logins': failed_logins,
                'blocked_ips': blocked_ips,
                'malware_detected': malware_detected,
                'suspicious_activity': suspicious_activity
            },
            'threat_level': self._get_threat_level(threat_score),
            'recommendations': self._get_threat_recommendations(threat_score)
        }
    
    def _user_behavior_analysis(self, start_date: datetime, end_date: datetime, **kwargs) -> Dict[str, Any]:
        """Analyze user behavior patterns"""
        logs = self.log_selector.filter_by_date_range(start_date, end_date)
        
        # Get user activity patterns
        user_activity = logs.values('user__username').annotate(
            count=models.Count('id'),
            failed_attempts=models.Count('id', filter=models.Q(security_type='login_failed')),
            unique_ips=models.Count('ip_address', distinct=True)
        ).order_by('-count')
        
        # Identify suspicious users
        suspicious_users = []
        for user_data in user_activity:
            if user_data['failed_attempts'] > 5 or user_data['unique_ips'] > 10:
                suspicious_users.append(user_data)
        
        # Get time-based patterns
        hourly_activity = logs.get_hourly_activity()
        
        return {
            'analysis_type': 'user_behavior',
            'time_period': f"{start_date} to {end_date}",
            'total_active_users': user_activity.count(),
            'suspicious_users': suspicious_users,
            'hourly_patterns': hourly_activity,
            'recommendations': self._get_behavior_recommendations(suspicious_users)
        }
    
    def _incident_trends_analysis(self, start_date: datetime, end_date: datetime, **kwargs) -> Dict[str, Any]:
        """Analyze incident trends"""
        incidents = self.incident_selector.filter_by_date_opened(start_date, end_date)
        
        # Get trend data
        daily_incidents = incidents.extra(
            select={'day': 'date(opened_at)'}
        ).values('day').annotate(count=models.Count('id')).order_by('day')
        
        # Get resolution statistics
        avg_resolution_time = incidents.get_average_resolution_time()
        resolution_rate = incidents.filter_resolved().count() / max(1, incidents.count())
        
        return {
            'analysis_type': 'incident_trends',
            'time_period': f"{start_date} to {end_date}",
            'total_incidents': incidents.count(),
            'daily_trends': list(daily_incidents),
            'resolution_stats': {
                'average_resolution_time': avg_resolution_time,
                'resolution_rate': resolution_rate
            },
            'recommendations': self._get_incident_recommendations(resolution_rate, avg_resolution_time)
        }
    
    def _generate_recommendations(self, risk_score: float, risk_factors: Dict[str, Any]) -> List[str]:
        """Generate security recommendations"""
        recommendations = []
        
        if risk_score > 70:
            recommendations.append("Immediate security review required - high risk detected")
        
        if risk_factors['high_risk_percentage'] > 20:
            recommendations.append("Investigate high-risk security events")
        
        if risk_factors['failed_attempt_rate'] > 10:
            recommendations.append("Implement stronger authentication measures")
        
        if risk_factors['incident_rate'] > 5:
            recommendations.append("Review incident response procedures")
        
        return recommendations
    
    def _get_threat_level(self, threat_score: float) -> str:
        """Get threat level based on score"""
        if threat_score > 80:
            return 'critical'
        elif threat_score > 60:
            return 'high'
        elif threat_score > 40:
            return 'medium'
        else:
            return 'low'
    
    def _get_threat_recommendations(self, threat_score: float) -> List[str]:
        """Get threat-based recommendations"""
        recommendations = []
        
        if threat_score > 80:
            recommendations.append("Activate emergency response protocols")
            recommendations.append("Increase monitoring frequency")
        elif threat_score > 60:
            recommendations.append("Review security controls")
            recommendations.append("Update threat intelligence")
        elif threat_score > 40:
            recommendations.append("Monitor for suspicious activity")
        
        return recommendations
    
    def _get_behavior_recommendations(self, suspicious_users: List[Dict]) -> List[str]:
        """Get behavior-based recommendations"""
        recommendations = []
        
        if suspicious_users:
            recommendations.append("Investigate suspicious user behavior")
            recommendations.append("Consider additional authentication for flagged users")
        
        return recommendations
    
    def _get_incident_recommendations(self, resolution_rate: float, avg_resolution_time) -> List[str]:
        """Get incident-based recommendations"""
        recommendations = []
        
        if resolution_rate < 0.8:
            recommendations.append("Improve incident response processes")
        
        if avg_resolution_time and avg_resolution_time.total_seconds() > 86400:  # More than 24 hours
            recommendations.append("Accelerate incident resolution procedures")
        
        return recommendations


class IncidentManagementUseCase(BaseUseCase):
    """Use case for incident management"""
    
    def __init__(self):
        super().__init__()
        self.incident_selector = SecurityIncidentSelector()
    
    def execute(self, action: str, incident_id: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """Execute incident management action"""
        try:
            if action == 'create':
                return self._create_incident(**kwargs)
            elif action == 'update':
                return self._update_incident(incident_id, **kwargs)
            elif action == 'assign':
                return self._assign_incident(incident_id, **kwargs)
            elif action == 'resolve':
                return self._resolve_incident(incident_id, **kwargs)
            elif action == 'escalate':
                return self._escalate_incident(incident_id, **kwargs)
            elif action == 'list':
                return self._list_incidents(**kwargs)
            else:
                raise ValueError(f"Unknown action: {action}")
                
        except Exception as e:
            self.log_execution('incident_management', None, e)
            raise
    
    def _create_incident(self, **kwargs) -> Dict[str, Any]:
        """Create new security incident"""
        with transaction.atomic():
            incident = SecurityIncident.objects.create(
                title=kwargs.get('title'),
                description=kwargs.get('description'),
                incident_type=kwargs.get('incident_type'),
                severity=kwargs.get('severity', 'medium'),
                priority=kwargs.get('priority', 'medium'),
                user=kwargs.get('user'),
                affected_systems=kwargs.get('affected_systems', []),
                metadata=kwargs.get('metadata', {})
            )
            
            # Log incident creation
            self._log_incident_action(incident, 'created', kwargs.get('user'))
            
            return {
                'success': True,
                'incident_id': incident.id,
                'message': 'Incident created successfully'
            }
    
    def _update_incident(self, incident_id: int, **kwargs) -> Dict[str, Any]:
        """Update existing incident"""
        try:
            incident = self.incident_selector.get_by_id(incident_id)
            if not incident:
                return {'success': False, 'error': 'Incident not found'}
            
            # Update fields
            for field, value in kwargs.items():
                if hasattr(incident, field) and field not in ['id', 'created_at']:
                    setattr(incident, field, value)
            
            incident.save()
            
            # Log update
            self._log_incident_action(incident, 'updated', kwargs.get('user'))
            
            return {
                'success': True,
                'incident_id': incident.id,
                'message': 'Incident updated successfully'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _assign_incident(self, incident_id: int, **kwargs) -> Dict[str, Any]:
        """Assign incident to user"""
        try:
            incident = self.incident_selector.get_by_id(incident_id)
            if not incident:
                return {'success': False, 'error': 'Incident not found'}
            
            assigned_to = kwargs.get('assigned_to')
            if not assigned_to:
                return {'success': False, 'error': 'Assigned user required'}
            
            incident.assigned_to = assigned_to
            incident.status = 'investigating'
            incident.save()
            
            # Log assignment
            self._log_incident_action(incident, 'assigned', kwargs.get('user'))
            
            return {
                'success': True,
                'incident_id': incident.id,
                'assigned_to': assigned_to.username if hasattr(assigned_to, 'username') else str(assigned_to)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _resolve_incident(self, incident_id: int, **kwargs) -> Dict[str, Any]:
        """Resolve incident"""
        try:
            incident = self.incident_selector.get_by_id(incident_id)
            if not incident:
                return {'success': False, 'error': 'Incident not found'}
            
            incident.status = 'resolved'
            incident.resolved_at = timezone.now()
            incident.resolution_notes = kwargs.get('resolution_notes', '')
            incident.save()
            
            # Log resolution
            self._log_incident_action(incident, 'resolved', kwargs.get('user'))
            
            return {
                'success': True,
                'incident_id': incident.id,
                'resolved_at': incident.resolved_at.isoformat()
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _escalate_incident(self, incident_id: int, **kwargs) -> Dict[str, Any]:
        """Escalate incident"""
        try:
            incident = self.incident_selector.get_by_id(incident_id)
            if not incident:
                return {'success': False, 'error': 'Incident not found'}
            
            # Update priority
            current_priority = incident.priority
            priority_order = ['low', 'medium', 'high', 'critical']
            
            try:
                current_index = priority_order.index(current_priority)
                if current_index < len(priority_order) - 1:
                    incident.priority = priority_order[current_index + 1]
            except ValueError:
                incident.priority = 'high'
            
            incident.status = 'investigating'
            incident.escalation_reason = kwargs.get('reason', '')
            incident.save()
            
            # Log escalation
            self._log_incident_action(incident, 'escalated', kwargs.get('user'))
            
            return {
                'success': True,
                'incident_id': incident.id,
                'new_priority': incident.priority
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _list_incidents(self, **kwargs) -> Dict[str, Any]:
        """List incidents with filters"""
        queryset = self.incident_selector.queryset
        
        # Apply filters
        status = kwargs.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        priority = kwargs.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        incident_type = kwargs.get('incident_type')
        if incident_type:
            queryset = queryset.filter(incident_type=incident_type)
        
        assigned_to = kwargs.get('assigned_to')
        if assigned_to:
            queryset = queryset.filter(assigned_to=assigned_to)
        
        # Pagination
        page = kwargs.get('page', 1)
        page_size = kwargs.get('page_size', 20)
        
        offset = (page - 1) * page_size
        total_count = queryset.count()
        items = list(queryset[offset:offset + page_size])
        
        return {
            'success': True,
            'items': items,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        }
    
    def _log_incident_action(self, incident: SecurityIncident, action: str, user: User):
        """Log incident action"""
        try:
            SecurityLog.objects.create(
                user=user,
                security_type='incident_management',
                severity='info',
                description=f'Incident {action}: {incident.title}',
                metadata={
                    'incident_id': incident.id,
                    'action': action,
                    'incident_type': incident.incident_type,
                    'severity': incident.severity
                }
            )
        except Exception as e:
            logger.error(f"Failed to log incident action: {e}")


class ThreatIntelligenceUseCase(BaseUseCase):
    """Use case for threat intelligence management"""
    
    def __init__(self):
        super().__init__()
        self.threat_selector = ThreatIntelligenceSelector()
    
    def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """Execute threat intelligence action"""
        try:
            if action == 'add_threat':
                return self._add_threat(**kwargs)
            elif action == 'update_threat':
                return self._update_threat(**kwargs)
            elif action == 'analyze_threats':
                return self._analyze_threats(**kwargs)
            elif action == 'get_active_threats':
                return self._get_active_threats(**kwargs)
            elif action == 'expire_threats':
                return self._expire_threats(**kwargs)
            else:
                raise ValueError(f"Unknown action: {action}")
                
        except Exception as e:
            self.log_execution('threat_intelligence', None, e)
            raise
    
    def _add_threat(self, **kwargs) -> Dict[str, Any]:
        """Add new threat intelligence"""
        with transaction.atomic():
            threat = ThreatIntelligence.objects.create(
                threat_type=kwargs.get('threat_type'),
                indicator_type=kwargs.get('indicator_type'),
                indicator=kwargs.get('indicator'),
                ip_range=kwargs.get('ip_range'),
                confidence=kwargs.get('confidence', 0.5),
                severity=kwargs.get('severity', 'medium'),
                source=kwargs.get('source'),
                description=kwargs.get('description'),
                expires_at=kwargs.get('expires_at'),
                metadata=kwargs.get('metadata', {})
            )
            
            return {
                'success': True,
                'threat_id': threat.id,
                'message': 'Threat added successfully'
            }
    
    def _update_threat(self, threat_id: int, **kwargs) -> Dict[str, Any]:
        """Update existing threat"""
        try:
            threat = self.threat_selector.get_by_id(threat_id)
            if not threat:
                return {'success': False, 'error': 'Threat not found'}
            
            # Update fields
            for field, value in kwargs.items():
                if hasattr(threat, field) and field not in ['id', 'created_at']:
                    setattr(threat, field, value)
            
            threat.save()
            
            return {
                'success': True,
                'threat_id': threat.id,
                'message': 'Threat updated successfully'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _analyze_threats(self, **kwargs) -> Dict[str, Any]:
        """Analyze threat intelligence"""
        threats = self.threat_selector.filter_active()
        
        # Get threat statistics
        type_dist = threats.get_type_distribution()
        severity_dist = threats.get_severity_distribution()
        source_dist = threats.get_source_distribution()
        avg_confidence = threats.get_average_confidence()
        
        # Get recent threats
        recent_threats = threats.filter_recently_added(hours=24)
        
        # Get expiring threats
        expiring_threats = threats.filter_expiring_soon(days=7)
        
        return {
            'success': True,
            'statistics': {
                'total_active_threats': threats.count(),
                'type_distribution': type_dist,
                'severity_distribution': severity_dist,
                'source_distribution': source_dist,
                'average_confidence': avg_confidence
            },
            'recent_threats': list(recent_threats[:10]),
            'expiring_threats': list(expiring_threats[:10])
        }
    
    def _get_active_threats(self, **kwargs) -> Dict[str, Any]:
        """Get active threats with filters"""
        queryset = self.threat_selector.filter_active()
        
        # Apply filters
        threat_type = kwargs.get('threat_type')
        if threat_type:
            queryset = queryset.filter(threat_type=threat_type)
        
        severity = kwargs.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        min_confidence = kwargs.get('min_confidence')
        if min_confidence:
            queryset = queryset.filter(confidence__gte=min_confidence)
        
        # Pagination
        page = kwargs.get('page', 1)
        page_size = kwargs.get('page_size', 20)
        
        offset = (page - 1) * page_size
        total_count = queryset.count()
        items = list(queryset[offset:offset + page_size])
        
        return {
            'success': True,
            'items': items,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        }
    
    def _expire_threats(self, **kwargs) -> Dict[str, Any]:
        """Expire outdated threats"""
        expired_count = self.threat_selector.filter_expired().update(is_active=False)
        
        return {
            'success': True,
            'expired_count': expired_count,
            'message': f'Expired {expired_count} threats'
        }


class UserSecurityUseCase(BaseUseCase):
    """Use case for user security operations"""
    
    def __init__(self):
        super().__init__()
        self.log_selector = SecurityLogSelector()
        self.ban_selector = UserBanSelector()
    
    def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """Execute user security action"""
        try:
            if action == 'assess_user_risk':
                return self._assess_user_risk(**kwargs)
            elif action == 'ban_user':
                return self._ban_user(**kwargs)
            elif action == 'unban_user':
                return self._unban_user(**kwargs)
            elif action == 'get_user_security_summary':
                return self._get_user_security_summary(**kwargs)
            elif action == 'detect_suspicious_activity':
                return self._detect_suspicious_activity(**kwargs)
            else:
                raise ValueError(f"Unknown action: {action}")
                
        except Exception as e:
            self.log_execution('user_security', None, e)
            raise
    
    def _assess_user_risk(self, user: Union[User, int, str], **kwargs) -> Dict[str, Any]:
        """Assess user security risk"""
        # Get user logs
        if isinstance(user, User):
            user_logs = self.log_selector.filter_by_user(user)
        elif isinstance(user, int):
            user_logs = self.log_selector.filter_by_user(user)
        else:
            user_logs = self.log_selector.filter_by_user(user)
        
        # Calculate risk factors
        total_logs = user_logs.count()
        failed_attempts = user_logs.filter_failed_attempts().count()
        high_risk_logs = user_logs.filter_high_risk().count()
        unique_ips = user_logs.values('ip_address').distinct().count()
        
        # Risk calculation
        risk_factors = {
            'failed_attempt_rate': (failed_attempts / max(1, total_logs)) * 100,
            'high_risk_rate': (high_risk_logs / max(1, total_logs)) * 100,
            'ip_diversity': unique_ips,
            'total_activity': total_logs
        }
        
        risk_score = SecurityMetrics.calculate_risk_score(risk_factors)
        
        # Get user bans
        active_bans = self.ban_selector.filter_by_banned_user(user).filter_active().count()
        
        return {
            'success': True,
            'user_id': user.id if isinstance(user, User) else user,
            'risk_score': risk_score,
            'risk_level': self._get_risk_level(risk_score),
            'risk_factors': risk_factors,
            'active_bans': active_bans,
            'recommendations': self._get_user_risk_recommendations(risk_score, risk_factors)
        }
    
    def _ban_user(self, user: Union[User, int, str], **kwargs) -> Dict[str, Any]:
        """Ban user"""
        try:
            # Get user object
            if isinstance(user, User):
                user_obj = user
            elif isinstance(user, int):
                user_obj = User.objects.get(id=user)
            else:
                user_obj = User.objects.get(username=user)
            
            # Check if already banned
            existing_ban = self.ban_selector.filter_by_banned_user(user_obj).filter_active().first()
            if existing_ban:
                return {'success': False, 'error': 'User already banned'}
            
            # Create ban
            ban = UserBan.objects.create(
                user=user_obj,
                reason=kwargs.get('reason', 'Security violation'),
                expires_at=kwargs.get('expires_at'),
                banned_by=kwargs.get('banned_by'),
                metadata=kwargs.get('metadata', {})
            )
            
            # Log ban
            self._log_user_action(user_obj, 'banned', kwargs.get('banned_by'))
            
            return {
                'success': True,
                'ban_id': ban.id,
                'expires_at': ban.expires_at.isoformat() if ban.expires_at else None
            }
            
        except User.DoesNotExist:
            return {'success': False, 'error': 'User not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _unban_user(self, user: Union[User, int, str], **kwargs) -> Dict[str, Any]:
        """Unban user"""
        try:
            # Get user object
            if isinstance(user, User):
                user_obj = user
            elif isinstance(user, int):
                user_obj = User.objects.get(id=user)
            else:
                user_obj = User.objects.get(username=user)
            
            # Deactivate bans
            deactivated_count = self.ban_selector.filter_by_banned_user(user_obj).filter_active().update(is_active=False)
            
            # Log unban
            self._log_user_action(user_obj, 'unbanned', kwargs.get('unbanned_by'))
            
            return {
                'success': True,
                'deactivated_bans': deactivated_count
            }
            
        except User.DoesNotExist:
            return {'success': False, 'error': 'User not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _get_user_security_summary(self, user: Union[User, int, str], **kwargs) -> Dict[str, Any]:
        """Get comprehensive user security summary"""
        # Get user logs
        if isinstance(user, User):
            user_obj = user
            user_logs = self.log_selector.filter_by_user(user)
        elif isinstance(user, int):
            user_obj = User.objects.get(id=user)
            user_logs = self.log_selector.filter_by_user(user)
        else:
            user_obj = User.objects.get(username=user)
            user_logs = self.log_selector.filter_by_user(user)
        
        # Get statistics
        recent_logs = user_logs.filter_recent(days=30)
        failed_attempts = recent_logs.filter_failed_attempts().count()
        unique_ips = recent_logs.values('ip_address').distinct().count()
        
        # Get ban history
        ban_history = self.ban_selector.filter_by_banned_user(user_obj)
        active_bans = ban_history.filter_active().count()
        
        return {
            'success': True,
            'user_id': user_obj.id,
            'username': user_obj.username,
            'summary': {
                'recent_activity': recent_logs.count(),
                'failed_attempts': failed_attempts,
                'unique_ip_addresses': unique_ips,
                'active_bans': active_bans,
                'total_bans': ban_history.count()
            },
            'last_activity': recent_logs.order_by('-created_at').first().created_at if recent_logs.exists() else None
        }
    
    def _detect_suspicious_activity(self, user: Union[User, int, str], **kwargs) -> Dict[str, Any]:
        """Detect suspicious user activity"""
        # Get recent logs
        if isinstance(user, User):
            user_logs = self.log_selector.filter_by_user(user)
        elif isinstance(user, int):
            user_logs = self.log_selector.filter_by_user(user)
        else:
            user_logs = self.log_selector.filter_by_user(user)
        
        recent_logs = user_logs.filter_recent(hours=24)
        
        # Suspicious patterns
        suspicious_indicators = []
        
        # Multiple failed logins
        failed_logins = recent_logs.filter_by_security_type('login_failed').count()
        if failed_logins > 5:
            suspicious_indicators.append({
                'type': 'multiple_failed_logins',
                'count': failed_logins,
                'severity': 'high'
            })
        
        # High number of unique IPs
        unique_ips = recent_logs.values('ip_address').distinct().count()
        if unique_ips > 10:
            suspicious_indicators.append({
                'type': 'high_ip_diversity',
                'count': unique_ips,
                'severity': 'medium'
            })
        
        # High risk activities
        high_risk_count = recent_logs.filter_high_risk().count()
        if high_risk_count > 3:
            suspicious_indicators.append({
                'type': 'high_risk_activities',
                'count': high_risk_count,
                'severity': 'high'
            })
        
        return {
            'success': True,
            'user_id': user.id if isinstance(user, User) else user,
            'suspicious_indicators': suspicious_indicators,
            'overall_risk': 'high' if any(i['severity'] == 'high' for i in suspicious_indicators) else 'medium' if suspicious_indicators else 'low'
        }
    
    def _get_risk_level(self, risk_score: float) -> str:
        """Get risk level from score"""
        if risk_score > 70:
            return 'high'
        elif risk_score > 40:
            return 'medium'
        else:
            return 'low'
    
    def _get_user_risk_recommendations(self, risk_score: float, risk_factors: Dict[str, Any]) -> List[str]:
        """Get user risk recommendations"""
        recommendations = []
        
        if risk_score > 70:
            recommendations.append("Consider temporary account suspension")
            recommendations.append("Require additional authentication")
        elif risk_score > 40:
            recommendations.append("Monitor user activity closely")
            recommendations.append("Review recent login attempts")
        
        if risk_factors['failed_attempt_rate'] > 20:
            recommendations.append("Investigate failed login attempts")
        
        if risk_factors['ip_diversity'] > 10:
            recommendations.append("Verify user identity from new locations")
        
        return recommendations
    
    def _log_user_action(self, user: User, action: str, performed_by: User):
        """Log user security action"""
        try:
            SecurityLog.objects.create(
                user=performed_by,
                security_type='user_security',
                severity='medium',
                description=f'User {action}: {user.username}',
                metadata={
                    'target_user_id': user.id,
                    'target_username': user.username,
                    'action': action
                }
            )
        except Exception as e:
            logger.error(f"Failed to log user action: {e}")


# Use case factory
class UseCaseFactory:
    """Factory for creating use cases"""
    
    @staticmethod
    def create_use_case(use_case_type: str):
        """Create use case instance"""
        use_cases = {
            'security_analysis': SecurityAnalysisUseCase,
            'incident_management': IncidentManagementUseCase,
            'threat_intelligence': ThreatIntelligenceUseCase,
            'user_security': UserSecurityUseCase,
        }
        
        use_case_class = use_cases.get(use_case_type)
        if not use_case_class:
            raise ValueError(f"Unknown use case type: {use_case_type}")
        
        return use_case_class()


# Export use case classes
__all__ = [
    'BaseUseCase',
    'SecurityAnalysisUseCase',
    'IncidentManagementUseCase',
    'ThreatIntelligenceUseCase',
    'UserSecurityUseCase',
    'UseCaseFactory'
]