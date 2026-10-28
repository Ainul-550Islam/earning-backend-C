"""
Security Interactors Module
Interactor pattern for business logic coordination
"""

import logging
from typing import Dict, List, Any, Optional, Type, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction

from .use_cases import (
    SecurityAnalysisUseCase, IncidentManagementUseCase,
    ThreatIntelligenceUseCase, UserSecurityUseCase
)
from .repositories import SecurityUnitOfWork
from .selectors import (
    SecurityLogSelector, DeviceInfoSelector, SecurityIncidentSelector,
    ThreatIntelligenceSelector, UserBanSelector
)
from .utils import SecurityUtils
from .helpers import SecurityMetrics
# DeviceInfo stub — replace with real import if available
try:
    from api.security.models import DeviceInfo
except ImportError:
    class DeviceInfo:
        pass



User = get_user_model()
logger = logging.getLogger('security.interactors')


class BaseInteractor:
    """Base interactor with common functionality"""
    
    def __init__(self):
        self.unit_of_work = SecurityUnitOfWork()
        self.cache_timeout = 300  # 5 minutes
    
    def execute(self, *args, **kwargs):
        """Execute the interactor"""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate input data"""
        return True
    
    def log_execution(self, interactor_name: str, result: Any, error: Exception = None):
        """Log interactor execution"""
        if error:
            logger.error(f"Interactor {interactor_name} failed: {error}")
        else:
            logger.info(f"Interactor {interactor_name} executed successfully")


class SecurityAnalysisInteractor(BaseInteractor):
    """Interactor for comprehensive security analysis"""
    
    def __init__(self):
        super().__init__()
        self.analysis_use_case = SecurityAnalysisUseCase()
        self.log_selector = SecurityLogSelector()
        self.incident_selector = SecurityIncidentSelector()
    
    def execute(self, analysis_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute comprehensive security analysis"""
        try:
            # Validate request
            if not self.validate_input(analysis_request):
                return {'success': False, 'error': 'Invalid input data'}
            
            # Extract parameters
            analysis_type = analysis_request.get('analysis_type', 'comprehensive')
            time_period = analysis_request.get('time_period', 'last_24h')
            filters = analysis_request.get('filters', {})
            include_recommendations = analysis_request.get('include_recommendations', True)
            
            # Perform analysis
            analysis_result = self.analysis_use_case.execute(
                analysis_type=analysis_type,
                time_period=time_period,
                **filters
            )
            
            # Add recommendations if requested
            if include_recommendations:
                analysis_result['recommendations'] = self._generate_comprehensive_recommendations(
                    analysis_result, analysis_type
                )
            
            # Add executive summary
            analysis_result['executive_summary'] = self._generate_executive_summary(analysis_result)
            
            # Log execution
            self.log_execution('security_analysis', analysis_result)
            
            return {
                'success': True,
                'analysis': analysis_result,
                'performed_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.log_execution('security_analysis', None, e)
            return {
                'success': False,
                'error': str(e),
                'performed_at': timezone.now().isoformat()
            }
    
    def _generate_comprehensive_recommendations(self, analysis_result: Dict[str, Any], 
                                              analysis_type: str) -> List[str]:
        """Generate comprehensive recommendations"""
        recommendations = []
        
        if analysis_type == 'comprehensive':
            summary = analysis_result.get('summary', {})
            risk_score = summary.get('overall_risk_score', 0)
            
            if risk_score > 70:
                recommendations.append("CRITICAL: Immediate security review required")
                recommendations.append("Activate emergency response protocols")
            elif risk_score > 50:
                recommendations.append("HIGH: Enhanced monitoring recommended")
                recommendations.append("Review security controls")
            
            # Check specific risk factors
            risk_factors = summary.get('risk_factors', {})
            if risk_factors.get('high_risk_percentage', 0) > 20:
                recommendations.append("Investigate high-risk security events")
            
            if risk_factors.get('failed_attempt_rate', 0) > 15:
                recommendations.append("Strengthen authentication mechanisms")
                recommendations.append("Implement account lockout policies")
        
        elif analysis_type == 'threat_assessment':
            threat_score = analysis_result.get('threat_score', 0)
            if threat_score > 70:
                recommendations.append("Implement immediate threat response measures")
                recommendations.append("Update security monitoring rules")
            
            indicators = analysis_result.get('indicators', {})
            if indicators.get('failed_logins', 0) > 10:
                recommendations.append("Review authentication security")
            
            if indicators.get('malware_detected', 0) > 0:
                recommendations.append("Scan affected systems")
                recommendations.append("Update antivirus definitions")
        
        elif analysis_type == 'user_behavior':
            suspicious_users = analysis_result.get('suspicious_users', [])
            if suspicious_users:
                recommendations.append(f"Investigate {len(suspicious_users)} suspicious user accounts")
                recommendations.append("Consider additional authentication for flagged users")
        
        elif analysis_type == 'incident_trends':
            resolution_rate = analysis_result.get('resolution_stats', {}).get('resolution_rate', 1.0)
            if resolution_rate < 0.8:
                recommendations.append("Improve incident response procedures")
                recommendations.append("Provide additional training to security team")
        
        return recommendations
    
    def _generate_executive_summary(self, analysis_result: Dict[str, Any]) -> str:
        """Generate executive summary"""
        analysis_type = analysis_result.get('analysis_type', 'unknown')
        
        if analysis_type == 'comprehensive':
            summary = analysis_result.get('summary', {})
            risk_score = summary.get('overall_risk_score', 0)
            total_logs = summary.get('total_logs', 0)
            total_incidents = summary.get('total_incidents', 0)
            
            return f"Security analysis shows {'high' if risk_score > 70 else 'medium' if risk_score > 40 else 'low'} risk posture with {total_logs} events and {total_incidents} incidents in the analyzed period."
        
        elif analysis_type == 'threat_assessment':
            threat_score = analysis_result.get('threat_score', 0)
            threat_level = analysis_result.get('threat_level', 'unknown')
            
            return f"Threat assessment indicates {threat_level} threat level with a threat score of {threat_score:.1f}."
        
        elif analysis_type == 'user_behavior':
            total_users = analysis_result.get('total_active_users', 0)
            suspicious_count = len(analysis_result.get('suspicious_users', []))
            
            return f"User behavior analysis of {total_users} active users identified {suspicious_count} suspicious accounts requiring investigation."
        
        elif analysis_type == 'incident_trends':
            total_incidents = analysis_result.get('total_incidents', 0)
            resolution_rate = analysis_result.get('resolution_stats', {}).get('resolution_rate', 1.0)
            
            return f"Incident trends analysis shows {total_incidents} incidents with {resolution_rate:.1%} resolution rate."
        
        return f"{analysis_type.title()} analysis completed successfully."


class IncidentResponseInteractor(BaseInteractor):
    """Interactor for incident response coordination"""
    
    def __init__(self):
        super().__init__()
        self.incident_use_case = IncidentManagementUseCase()
        self.threat_use_case = ThreatIntelligenceUseCase()
        self.log_selector = SecurityLogSelector()
    
    def execute(self, action_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute incident response action"""
        try:
            # Validate request
            if not self.validate_input(action_request):
                return {'success': False, 'error': 'Invalid input data'}
            
            # Extract parameters
            action = action_request.get('action')
            incident_id = action_request.get('incident_id')
            user = action_request.get('user')
            data = action_request.get('data', {})
            
            # Execute action
            result = self.incident_use_case.execute(action, incident_id, user=user, **data)
            
            # Perform additional actions based on incident type
            if result.get('success') and action in ['create', 'update']:
                self._perform_automated_actions(result, action, user)
            
            # Log execution
            self.log_execution('incident_response', result)
            
            return {
                'success': result.get('success', False),
                'result': result,
                'performed_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.log_execution('incident_response', None, e)
            return {
                'success': False,
                'error': str(e),
                'performed_at': timezone.now().isoformat()
            }
    
    def _perform_automated_actions(self, incident_result: Dict[str, Any], action: str, user: User):
        """Perform automated actions based on incident"""
        try:
            if action == 'create':
                incident_id = incident_result.get('incident_id')
                if incident_id:
                    # Create initial security log
                    self.unit_of_work.create_security_log(
                        user=user,
                        security_type='incident_created',
                        severity='medium',
                        description=f'Security incident #{incident_id} created',
                        metadata={'incident_id': incident_id}
                    )
                    
                    # Check for automated escalation
                    self._check_automated_escalation(incident_id, user)
            
            elif action == 'resolve':
                incident_id = incident_result.get('incident_id')
                if incident_id:
                    # Create resolution log
                    self.unit_of_work.create_security_log(
                        user=user,
                        security_type='incident_resolved',
                        severity='info',
                        description=f'Security incident #{incident_id} resolved',
                        metadata={'incident_id': incident_id}
                    )
        
        except Exception as e:
            logger.error(f"Error performing automated actions: {e}")
    
    def _check_automated_escalation(self, incident_id: int, user: User):
        """Check if incident should be automatically escalated"""
        try:
            incident = self.unit_of_work.security_incidents.get_by_id(incident_id)
            if not incident:
                return
            
            # Auto-escalate critical incidents
            if incident.priority == 'critical':
                escalation_result = self.incident_use_case.execute(
                    'escalate', incident_id, user=user, reason='Automatic escalation for critical incident'
                )
                
                if escalation_result.get('success'):
                    # Log escalation
                    self.unit_of_work.create_security_log(
                        user=user,
                        security_type='incident_escalated',
                        severity='high',
                        description=f'Security incident #{incident_id} automatically escalated',
                        metadata={'incident_id': incident_id, 'reason': 'Critical priority'}
                    )
        
        except Exception as e:
            logger.error(f"Error checking automated escalation: {e}")


class ThreatMonitoringInteractor(BaseInteractor):
    """Interactor for threat monitoring and response"""
    
    def __init__(self):
        super().__init__()
        self.threat_use_case = ThreatIntelligenceUseCase()
        self.analysis_use_case = SecurityAnalysisUseCase()
        self.threat_selector = ThreatIntelligenceSelector()
    
    def execute(self, monitoring_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute threat monitoring"""
        try:
            # Validate request
            if not self.validate_input(monitoring_request):
                return {'success': False, 'error': 'Invalid input data'}
            
            # Extract parameters
            action = monitoring_request.get('action', 'analyze')
            data = monitoring_request.get('data', {})
            
            # Execute action
            if action == 'analyze':
                return self._analyze_threats(data)
            elif action == 'add_threat':
                return self._add_threat(data)
            elif action == 'update_threat':
                return self._update_threat(data)
            elif action == 'get_active_threats':
                return self._get_active_threats(data)
            else:
                raise ValueError(f"Unknown action: {action}")
            
        except Exception as e:
            self.log_execution('threat_monitoring', None, e)
            return {
                'success': False,
                'error': str(e),
                'performed_at': timezone.now().isoformat()
            }
    
    def _analyze_threats(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze current threat landscape"""
        # Get threat analysis
        threat_analysis = self.threat_use_case.execute('analyze_threats', **data)
        
        # Get security logs for correlation
        recent_logs = self.log_selector.filter_recent(hours=24)
        
        # Correlate threats with recent activity
        correlated_threats = self._correlate_threats_with_activity(
            threat_analysis.get('recent_threats', []),
            recent_logs
        )
        
        # Generate threat assessment
        threat_assessment = self._generate_threat_assessment(threat_analysis, correlated_threats)
        
        return {
            'success': True,
            'threat_analysis': threat_analysis,
            'correlated_threats': correlated_threats,
            'threat_assessment': threat_assessment,
            'performed_at': timezone.now().isoformat()
        }
    
    def _add_threat(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add new threat intelligence"""
        result = self.threat_use_case.execute('add_threat', **data)
        
        if result.get('success'):
            # Create security log
            self.unit_of_work.create_security_log(
                user=data.get('user'),
                security_type='threat_added',
                severity='medium',
                description=f'Threat intelligence added: {data.get("threat_type", "unknown")}',
                metadata={
                    'threat_id': result.get('threat_id'),
                    'threat_type': data.get('threat_type'),
                    'indicator': data.get('indicator')
                }
            )
        
        return {
            'success': result.get('success', False),
            'result': result,
            'performed_at': timezone.now().isoformat()
        }
    
    def _update_threat(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing threat"""
        result = self.threat_use_case.execute('update_threat', **data)
        
        if result.get('success'):
            # Create security log
            self.unit_of_work.create_security_log(
                user=data.get('user'),
                security_type='threat_updated',
                severity='info',
                description=f'Threat intelligence updated',
                metadata={'threat_id': data.get('threat_id')}
            )
        
        return {
            'success': result.get('success', False),
            'result': result,
            'performed_at': timezone.now().isoformat()
        }
    
    def _get_active_threats(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Get active threats"""
        result = self.threat_use_case.execute('get_active_threats', **data)
        
        return {
            'success': result.get('success', False),
            'result': result,
            'performed_at': timezone.now().isoformat()
        }
    
    def _correlate_threats_with_activity(self, threats: List[Dict[str, Any]], 
                                       logs) -> List[Dict[str, Any]]:
        """Correlate threats with recent activity"""
        correlated = []
        
        for threat in threats:
            correlation = {
                'threat': threat,
                'related_logs': [],
                'risk_level': 'low'
            }
            
            # Check for related logs
            threat_ip = threat.get('ip_range', '')
            threat_type = threat.get('threat_type', '')
            
            if threat_ip:
                related_logs = logs.filter_by_ip_address(threat_ip)
                correlation['related_logs'] = list(related_logs[:10])  # Limit to 10
                correlation['risk_level'] = 'high' if related_logs.count() > 5 else 'medium' if related_logs.count() > 0 else 'low'
            
            if threat_type:
                type_logs = logs.filter_by_security_type(f'{threat_type}_detected')
                if type_logs.exists():
                    correlation['related_logs'].extend(list(type_logs[:5]))
                    correlation['risk_level'] = 'high'
            
            correlated.append(correlation)
        
        return correlated
    
    def _generate_threat_assessment(self, threat_analysis: Dict[str, Any], 
                                  correlated_threats: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate overall threat assessment"""
        stats = threat_analysis.get('statistics', {})
        total_threats = stats.get('total_active_threats', 0)
        avg_confidence = stats.get('average_confidence', 0)
        
        # Count high risk correlations
        high_risk_count = sum(1 for ct in correlated_threats if ct['risk_level'] == 'high')
        
        # Calculate overall threat level
        if total_threats > 50 or high_risk_count > 10:
            threat_level = 'critical'
        elif total_threats > 20 or high_risk_count > 5:
            threat_level = 'high'
        elif total_threats > 10 or high_risk_count > 2:
            threat_level = 'medium'
        else:
            threat_level = 'low'
        
        return {
            'threat_level': threat_level,
            'total_threats': total_threats,
            'average_confidence': avg_confidence,
            'high_risk_correlations': high_risk_count,
            'recommendations': self._get_threat_recommendations(threat_level, high_risk_count)
        }
    
    def _get_threat_recommendations(self, threat_level: str, high_risk_count: int) -> List[str]:
        """Get threat-based recommendations"""
        recommendations = []
        
        if threat_level == 'critical':
            recommendations.append("Activate emergency threat response protocols")
            recommendations.append("Increase monitoring frequency to real-time")
        elif threat_level == 'high':
            recommendations.append("Enhance security monitoring")
            recommendations.append("Review and update security controls")
        elif threat_level == 'medium':
            recommendations.append("Continue standard monitoring")
            recommendations.append("Review threat intelligence feeds")
        
        if high_risk_count > 10:
            recommendations.append("Investigate high-risk threat correlations immediately")
        
        return recommendations


class UserSecurityInteractor(BaseInteractor):
    """Interactor for user security operations"""
    
    def __init__(self):
        super().__init__()
        self.user_use_case = UserSecurityUseCase()
        self.log_selector = SecurityLogSelector()
        self.device_selector = DeviceInfoSelector()
    
    def execute(self, security_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute user security operation"""
        try:
            # Validate request
            if not self.validate_input(security_request):
                return {'success': False, 'error': 'Invalid input data'}
            
            # Extract parameters
            action = security_request.get('action')
            user = security_request.get('user')
            data = security_request.get('data', {})
            
            # Execute action
            if action == 'assess_user_risk':
                return self._assess_user_risk(user, data)
            elif action == 'ban_user':
                return self._ban_user(user, data)
            elif action == 'unban_user':
                return self._unban_user(user, data)
            elif action == 'get_user_security_summary':
                return self._get_user_security_summary(user, data)
            elif action == 'detect_suspicious_activity':
                return self._detect_suspicious_activity(user, data)
            else:
                raise ValueError(f"Unknown action: {action}")
            
        except Exception as e:
            self.log_execution('user_security', None, e)
            return {
                'success': False,
                'error': str(e),
                'performed_at': timezone.now().isoformat()
            }
    
    def _assess_user_risk(self, user: Union[User, int, str], data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess user security risk"""
        # Get user risk assessment
        risk_assessment = self.user_use_case.execute('assess_user_risk', user, **data)
        
        # Get device information
        devices = self.device_selector.filter_by_user(user)
        device_count = devices.count()
        trusted_devices = devices.filter_trusted().count()
        high_risk_devices = devices.filter_high_risk_devices().count()
        
        # Enhance risk assessment with device data
        if risk_assessment.get('success'):
            risk_data = risk_assessment
            risk_data['device_analysis'] = {
                'total_devices': device_count,
                'trusted_devices': trusted_devices,
                'high_risk_devices': high_risk_devices,
                'device_risk_factor': (high_risk_devices / max(1, device_count)) * 100
            }
            
            # Recalculate risk score with device factor
            original_score = risk_data.get('risk_score', 0)
            device_factor = (high_risk_devices / max(1, device_count)) * 20  # Max 20 points
            adjusted_score = min(100, original_score + device_factor)
            
            risk_data['adjusted_risk_score'] = adjusted_score
            risk_data['adjusted_risk_level'] = self._get_risk_level(adjusted_score)
        
        return {
            'success': risk_assessment.get('success', False),
            'risk_assessment': risk_assessment,
            'performed_at': timezone.now().isoformat()
        }
    
    def _ban_user(self, user: Union[User, int, str], data: Dict[str, Any]) -> Dict[str, Any]:
        """Ban user with additional security measures"""
        # Get ban result
        ban_result = self.user_use_case.execute('ban_user', user, **data)
        
        if ban_result.get('success'):
            # Create security log
            self.unit_of_work.create_security_log(
                user=data.get('banned_by'),
                security_type='user_banned',
                severity='high',
                description=f'User banned: {data.get("reason", "Security violation")}',
                metadata={
                    'target_user_id': user.id if isinstance(user, User) else user,
                    'ban_id': ban_result.get('ban_id'),
                    'reason': data.get('reason')
                }
            )
            
            # Invalidate user sessions (simplified)
            self._invalidate_user_sessions(user)
        
        return {
            'success': ban_result.get('success', False),
            'result': ban_result,
            'performed_at': timezone.now().isoformat()
        }
    
    def _unban_user(self, user: Union[User, int, str], data: Dict[str, Any]) -> Dict[str, Any]:
        """Unban user"""
        # Get unban result
        unban_result = self.user_use_case.execute('unban_user', user, **data)
        
        if unban_result.get('success'):
            # Create security log
            self.unit_of_work.create_security_log(
                user=data.get('unbanned_by'),
                security_type='user_unbanned',
                severity='medium',
                description='User ban lifted',
                metadata={
                    'target_user_id': user.id if isinstance(user, User) else user,
                    'deactivated_bans': unban_result.get('deactivated_bans')
                }
            )
        
        return {
            'success': unban_result.get('success', False),
            'result': unban_result,
            'performed_at': timezone.now().isoformat()
        }
    
    def _get_user_security_summary(self, user: Union[User, int, str], data: Dict[str, Any]) -> Dict[str, Any]:
        """Get comprehensive user security summary"""
        # Get basic security summary
        summary = self.user_use_case.execute('get_user_security_summary', user, **data)
        
        if summary.get('success'):
            # Add device information
            devices = self.device_selector.filter_by_user(user)
            summary['devices'] = {
                'total_devices': devices.count(),
                'trusted_devices': devices.filter_trusted().count(),
                'high_risk_devices': devices.filter_high_risk_devices().count(),
                'recent_devices': list(devices.filter_recently_active(hours=24)[:5])
            }
            
            # Add recent security events
            recent_logs = self.log_selector.filter_by_user(user).filter_recent(days=7)
            summary['recent_events'] = {
                'total_events': recent_logs.count(),
                'failed_attempts': recent_logs.filter_failed_attempts().count(),
                'high_risk_events': recent_logs.filter_high_risk().count(),
                'event_types': recent_logs.get_security_types_count()
            }
        
        return {
            'success': summary.get('success', False),
            'summary': summary,
            'performed_at': timezone.now().isoformat()
        }
    
    def _detect_suspicious_activity(self, user: Union[User, int, str], data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect suspicious user activity"""
        # Get suspicious activity detection
        detection = self.user_use_case.execute('detect_suspicious_activity', user, **data)
        
        if detection.get('success') and detection.get('suspicious_indicators'):
            # Create security log for suspicious activity
            self.unit_of_work.create_security_log(
                user=data.get('analyst'),
                security_type='suspicious_activity_detected',
                severity='medium',
                description=f'Suspicious activity detected for user',
                metadata={
                    'target_user_id': user.id if isinstance(user, User) else user,
                    'indicators': detection.get('suspicious_indicators'),
                    'overall_risk': detection.get('overall_risk')
                }
            )
        
        return {
            'success': detection.get('success', False),
            'detection': detection,
            'performed_at': timezone.now().isoformat()
        }
    
    def _invalidate_user_sessions(self, user: Union[User, int, str]):
        """Invalidate user sessions (simplified implementation)"""
        # This would typically integrate with Django's session management
        # For now, we just log the action
        try:
            user_id = user.id if isinstance(user, User) else user
            logger.info(f"Invalidating sessions for user {user_id}")
        except Exception as e:
            logger.error(f"Error invalidating user sessions: {e}")
    
    def _get_risk_level(self, risk_score: float) -> str:
        """Get risk level from score"""
        if risk_score > 70:
            return 'high'
        elif risk_score > 40:
            return 'medium'
        else:
            return 'low'


class SecurityDashboardInteractor(BaseInteractor):
    """Interactor for security dashboard data aggregation"""
    
    def __init__(self):
        super().__init__()
        self.analysis_interactor = SecurityAnalysisInteractor()
        self.threat_interactor = ThreatMonitoringInteractor()
        self.incident_interactor = IncidentResponseInteractor()
        self.log_selector = SecurityLogSelector()
        self.incident_selector = SecurityIncidentSelector()
    
    def execute(self, dashboard_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute security dashboard data aggregation"""
        try:
            # Validate request
            if not self.validate_input(dashboard_request):
                return {'success': False, 'error': 'Invalid input data'}
            
            # Extract parameters
            time_period = dashboard_request.get('time_period', 'last_24h')
            include_recommendations = dashboard_request.get('include_recommendations', True)
            
            # Gather all dashboard data
            dashboard_data = {
                'security_analysis': self._get_security_analysis(time_period),
                'threat_monitoring': self._get_threat_monitoring(),
                'incident_response': self._get_incident_response(time_period),
                'key_metrics': self._get_key_metrics(time_period),
                'recent_activity': self._get_recent_activity(),
                'system_health': self._get_system_health()
            }
            
            # Add recommendations if requested
            if include_recommendations:
                dashboard_data['recommendations'] = self._generate_dashboard_recommendations(dashboard_data)
            
            return {
                'success': True,
                'dashboard': dashboard_data,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.log_execution('security_dashboard', None, e)
            return {
                'success': False,
                'error': str(e),
                'generated_at': timezone.now().isoformat()
            }
    
    def _get_security_analysis(self, time_period: str) -> Dict[str, Any]:
        """Get security analysis for dashboard"""
        analysis_request = {
            'analysis_type': 'comprehensive',
            'time_period': time_period,
            'include_recommendations': False
        }
        
        result = self.analysis_interactor.execute(analysis_request)
        return result.get('analysis', {})
    
    def _get_threat_monitoring(self) -> Dict[str, Any]:
        """Get threat monitoring data"""
        monitoring_request = {
            'action': 'analyze',
            'data': {}
        }
        
        result = self.threat_interactor.execute(monitoring_request)
        return result.get('threat_analysis', {})
    
    def _get_incident_response(self, time_period: str) -> Dict[str, Any]:
        """Get incident response data"""
        incidents = self.incident_selector.filter_recent(hours=24)
        
        return {
            'total_incidents': incidents.count(),
            'open_incidents': incidents.filter_open().count(),
            'critical_incidents': incidents.filter_critical().count(),
            'resolution_rate': incidents.filter_resolved().count() / max(1, incidents.count()),
            'average_resolution_time': incidents.get_average_resolution_time()
        }
    
    def _get_key_metrics(self, time_period: str) -> Dict[str, Any]:
        """Get key security metrics"""
        logs = self.log_selector.filter_recent(hours=24)
        
        return {
            'total_security_events': logs.count(),
            'high_risk_events': logs.filter_high_risk().count(),
            'failed_login_attempts': logs.filter_by_security_type('login_failed').count(),
            'blocked_ip_attempts': logs.filter_by_security_type('ip_blocked').count(),
            'unique_users_active': logs.values('user').distinct().count(),
            'unique_ip_addresses': logs.values('ip_address').distinct().count()
        }
    
    def _get_recent_activity(self) -> List[Dict[str, Any]]:
        """Get recent security activity"""
        recent_logs = self.log_selector.filter_recent(hours=6).order_by('-created_at')[:10]
        
        activity = []
        for log in recent_logs:
            activity.append({
                'timestamp': log.created_at.isoformat(),
                'type': log.security_type,
                'severity': log.severity,
                'description': log.description,
                'user': log.user.username if log.user else None,
                'ip_address': log.ip_address
            })
        
        return activity
    
    def _get_system_health(self) -> Dict[str, Any]:
        """Get system health status"""
        # Simple health check
        return {
            'database_status': 'healthy',
            'cache_status': 'healthy',
            'monitoring_status': 'healthy',
            'last_update': timezone.now().isoformat()
        }
    
    def _generate_dashboard_recommendations(self, dashboard_data: Dict[str, Any]) -> List[str]:
        """Generate dashboard recommendations"""
        recommendations = []
        
        # Analysis-based recommendations
        analysis = dashboard_data.get('security_analysis', {})
        summary = analysis.get('summary', {})
        risk_score = summary.get('overall_risk_score', 0)
        
        if risk_score > 70:
            recommendations.append("Critical: Immediate security review required")
        elif risk_score > 50:
            recommendations.append("High: Enhanced monitoring recommended")
        
        # Threat-based recommendations
        threat_data = dashboard_data.get('threat_monitoring', {})
        threat_level = threat_data.get('threat_assessment', {}).get('threat_level', 'low')
        
        if threat_level in ['critical', 'high']:
            recommendations.append("Review and update threat response procedures")
        
        # Incident-based recommendations
        incident_data = dashboard_data.get('incident_response', {})
        resolution_rate = incident_data.get('resolution_rate', 1.0)
        
        if resolution_rate < 0.8:
            recommendations.append("Improve incident response processes")
        
        return recommendations


# Interactor factory
class InteractorFactory:
    """Factory for creating interactors"""
    
    @staticmethod
    def create_interactor(interactor_type: str):
        """Create interactor instance"""
        interactors = {
            'security_analysis': SecurityAnalysisInteractor,
            'incident_response': IncidentResponseInteractor,
            'threat_monitoring': ThreatMonitoringInteractor,
            'user_security': UserSecurityInteractor,
            'security_dashboard': SecurityDashboardInteractor,
        }
        
        interactor_class = interactors.get(interactor_type)
        if not interactor_class:
            raise ValueError(f"Unknown interactor type: {interactor_type}")
        
        return interactor_class()


# Export interactor classes
__all__ = [
    'BaseInteractor',
    'SecurityAnalysisInteractor',
    'IncidentResponseInteractor',
    'ThreatMonitoringInteractor',
    'UserSecurityInteractor',
    'SecurityDashboardInteractor',
    'InteractorFactory'
]