"""
Security Logic Module
Core business logic for security operations
"""

import logging
from typing import Dict, List, Any, Optional, Type, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache

from .models import SecurityLog, SecurityIncident, ThreatIntelligence, UserBan, DeviceInfo
from .utils import SecurityUtils
from .helpers import SecurityMetrics, TimeHelper
from .validators import SecurityValidator
from .exceptions import SecurityException
# DeviceInfo stub — replace with real import if available
try:
    from api.security.models import DeviceInfo
except ImportError:
    class DeviceInfo:
        pass



User = get_user_model()
logger = logging.getLogger('security.logic')


class SecurityLogicEngine:
    """Main security logic engine"""
    
    def __init__(self):
        self.validators = {}
        self.rules = {}
        self.policies = {}
        self.cache_timeout = 300  # 5 minutes
    
    def analyze_security_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze security event and determine risk level"""
        try:
            # Extract key information
            event_type = event_data.get('security_type')
            user_id = event_data.get('user_id')
            ip_address = event_data.get('ip_address')
            user_agent = event_data.get('user_agent')
            
            # Calculate risk score
            risk_score = self._calculate_risk_score(event_data)
            
            # Check for anomalies
            anomalies = self._detect_anomalies(event_data)
            
            # Determine severity
            severity = self._determine_severity(event_type, risk_score, anomalies)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(event_data, risk_score, anomalies)
            
            return {
                'risk_score': risk_score,
                'severity': severity,
                'anomalies': anomalies,
                'recommendations': recommendations,
                'analysis_timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing security event: {e}")
            return {
                'error': 'Analysis failed',
                'details': str(e)
            }
    
    def _calculate_risk_score(self, event_data: Dict[str, Any]) -> float:
        """Calculate risk score for security event"""
        base_score = 0.0
        
        # Event type risk
        event_type_risks = {
            'login': 10.0,
            'failed_login': 30.0,
            'password_change': 20.0,
            'account_locked': 50.0,
            'data_access': 15.0,
            'data_modified': 40.0,
            'api_access': 10.0,
            'security_policy_violation': 60.0,
            'threat_detected': 80.0,
            'incident_created': 70.0
        }
        
        event_type = event_data.get('security_type', '')
        base_score += event_type_risks.get(event_type, 20.0)
        
        # IP address risk
        ip_address = event_data.get('ip_address')
        if ip_address:
            ip_risk = self._assess_ip_risk(ip_address)
            base_score += ip_risk
        
        # User agent risk
        user_agent = event_data.get('user_agent', '')
        if user_agent:
            ua_risk = self._assess_user_agent_risk(user_agent)
            base_score += ua_risk
        
        # Time-based risk
        event_time = event_data.get('created_at', timezone.now())
        time_risk = self._assess_time_risk(event_time)
        base_score += time_risk
        
        # User history risk
        user_id = event_data.get('user_id')
        if user_id:
            user_risk = self._assess_user_risk(user_id)
            base_score += user_risk
        
        # Cap at 100
        return min(100.0, max(0.0, base_score))
    
    def _assess_ip_risk(self, ip_address: str) -> float:
        """Assess IP address risk"""
        # Check if IP is in blacklist
        from .models import IPBlacklist
        
        if IPBlacklist.objects.filter(ip_address=ip_address, is_active=True).exists():
            return 40.0
        
        # Check for suspicious patterns
        if self._is_private_ip(ip_address):
            return 5.0
        elif self._is_vpn_ip(ip_address):
            return 15.0
        elif self._is_proxy_ip(ip_address):
            return 25.0
        
        return 0.0
    
    def _assess_user_agent_risk(self, user_agent: str) -> float:
        """Assess user agent risk"""
        suspicious_patterns = [
            'bot', 'crawler', 'spider', 'scraper',
            'automated', 'script', 'curl', 'wget'
        ]
        
        user_agent_lower = user_agent.lower()
        
        for pattern in suspicious_patterns:
            if pattern in user_agent_lower:
                return 20.0
        
        # Check for empty or missing user agent
        if not user_agent:
            return 15.0
        
        return 0.0
    
    def _assess_time_risk(self, event_time: datetime) -> float:
        """Assess time-based risk"""
        # Check for unusual hours (2 AM - 6 AM)
        hour = event_time.hour
        if 2 <= hour <= 6:
            return 10.0
        
        # Check for weekend activity
        if event_time.weekday() >= 5:  # Saturday or Sunday
            return 5.0
        
        return 0.0
    
    def _assess_user_risk(self, user_id: Union[int, str]) -> float:
        """Assess user risk based on history"""
        try:
            user = User.objects.get(id=user_id)
            
            # Check recent failed login attempts
            recent_failures = SecurityLog.objects.filter(
                user=user,
                security_type='failed_login',
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            failure_risk = min(30.0, recent_failures * 5.0)
            
            # Check account age
            account_age = timezone.now() - user.date_joined
            if account_age.days < 7:
                age_risk = 20.0
            elif account_age.days < 30:
                age_risk = 10.0
            else:
                age_risk = 0.0
            
            # Check for previous bans
            if UserBan.objects.filter(user=user, is_active=True).exists():
                ban_risk = 40.0
            else:
                ban_risk = 0.0
            
            return failure_risk + age_risk + ban_risk
            
        except User.DoesNotExist:
            return 25.0  # Unknown user risk
    
    def _detect_anomalies(self, event_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect anomalies in security event"""
        anomalies = []
        
        # Geographic anomaly
        ip_address = event_data.get('ip_address')
        user_id = event_data.get('user_id')
        
        if ip_address and user_id:
            geo_anomaly = self._detect_geographic_anomaly(user_id, ip_address)
            if geo_anomaly:
                anomalies.append(geo_anomaly)
        
        # Device anomaly
        user_agent = event_data.get('user_agent')
        if user_agent and user_id:
            device_anomaly = self._detect_device_anomaly(user_id, user_agent)
            if device_anomaly:
                anomalies.append(device_anomaly)
        
        # Frequency anomaly
        event_type = event_data.get('security_type')
        if event_type and user_id:
            freq_anomaly = self._detect_frequency_anomaly(user_id, event_type)
            if freq_anomaly:
                anomalies.append(freq_anomaly)
        
        # Pattern anomaly
        pattern_anomaly = self._detect_pattern_anomaly(event_data)
        if pattern_anomaly:
            anomalies.append(pattern_anomaly)
        
        return anomalies
    
    def _detect_geographic_anomaly(self, user_id: Union[int, str], ip_address: str) -> Optional[Dict[str, Any]]:
        """Detect geographic location anomaly"""
        try:
            # Get user's typical location
            typical_locations = SecurityLog.objects.filter(
                user_id=user_id,
                ip_address__isnull=False
            ).values('ip_address').distinct()
            
            if not typical_locations.exists():
                return None  # No history to compare
            
            # Get current location
            current_location = self._get_ip_location(ip_address)
            
            # Compare with typical locations
            for location in typical_locations:
                typical_location = self._get_ip_location(location['ip_address'])
                if typical_location:
                    distance = self._calculate_distance(current_location, typical_location)
                    if distance > 1000:  # More than 1000km away
                        return {
                            'type': 'geographic_anomaly',
                            'description': 'Login from unusual geographic location',
                            'severity': 'medium',
                            'details': {
                                'current_location': current_location,
                                'typical_location': typical_location,
                                'distance_km': distance
                            }
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting geographic anomaly: {e}")
            return None
    
    def _detect_device_anomaly(self, user_id: Union[int, str], user_agent: str) -> Optional[Dict[str, Any]]:
        """Detect device anomaly"""
        try:
            # Get user's typical devices
            typical_devices = SecurityLog.objects.filter(
                user_id=user_id,
                user_agent__isnull=False
            ).values('user_agent').distinct()
            
            if not typical_devices.exists():
                return None  # No history to compare
            
            # Check if current device is new
            device_seen = False
            for device in typical_devices:
                if self._are_similar_user_agents(user_agent, device['user_agent']):
                    device_seen = True
                    break
            
            if not device_seen:
                return {
                    'type': 'device_anomaly',
                    'description': 'Login from new device',
                    'severity': 'low',
                    'details': {
                        'new_user_agent': user_agent,
                        'first_time_device': True
                    }
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting device anomaly: {e}")
            return None
    
    def _detect_frequency_anomaly(self, user_id: Union[int, str], event_type: str) -> Optional[Dict[str, Any]]:
        """Detect frequency anomaly"""
        try:
            # Get recent event frequency
            recent_events = SecurityLog.objects.filter(
                user_id=user_id,
                security_type=event_type,
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            # Get typical frequency
            typical_frequency = SecurityLog.objects.filter(
                user_id=user_id,
                security_type=event_type,
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count() / 7  # Average per day
            
            # Convert to hourly rate
            typical_hourly = typical_frequency / 24
            
            # Check for anomaly (more than 10x typical rate)
            if typical_hourly > 0 and recent_events > typical_hourly * 10:
                return {
                    'type': 'frequency_anomaly',
                    'description': f'Unusual frequency of {event_type} events',
                    'severity': 'high',
                    'details': {
                        'recent_count': recent_events,
                        'typical_hourly': typical_hourly,
                        'multiplier': recent_events / typical_hourly
                    }
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting frequency anomaly: {e}")
            return None
    
    def _detect_pattern_anomaly(self, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Detect pattern anomaly"""
        try:
            # Check for suspicious patterns
            patterns = [
                self._check_brute_force_pattern,
                self._check_data_exfiltration_pattern,
                self._check_privilege_escalation_pattern,
                self._check_lateral_movement_pattern
            ]
            
            for pattern_check in patterns:
                anomaly = pattern_check(event_data)
                if anomaly:
                    return anomaly
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting pattern anomaly: {e}")
            return None
    
    def _check_brute_force_pattern(self, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check for brute force pattern"""
        if event_data.get('security_type') != 'failed_login':
            return None
        
        user_id = event_data.get('user_id')
        ip_address = event_data.get('ip_address')
        
        if not user_id or not ip_address:
            return None
        
        # Check for multiple failed attempts
        recent_failures = SecurityLog.objects.filter(
            user_id=user_id,
            ip_address=ip_address,
            security_type='failed_login',
            created_at__gte=timezone.now() - timedelta(minutes=15)
        ).count()
        
        if recent_failures >= 5:
            return {
                'type': 'brute_force_pattern',
                'description': 'Possible brute force attack detected',
                'severity': 'high',
                'details': {
                    'failed_attempts': recent_failures,
                    'time_window': '15 minutes',
                    'ip_address': ip_address
                }
            }
        
        return None
    
    def _check_data_exfiltration_pattern(self, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check for data exfiltration pattern"""
        if event_data.get('security_type') != 'data_access':
            return None
        
        user_id = event_data.get('user_id')
        
        if not user_id:
            return None
        
        # Check for unusual data access patterns
        recent_access = SecurityLog.objects.filter(
            user_id=user_id,
            security_type='data_access',
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        typical_access = SecurityLog.objects.filter(
            user_id=user_id,
            security_type='data_access',
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count() / 7 / 24  # Average per hour
        
        if typical_access > 0 and recent_access > typical_access * 20:
            return {
                'type': 'data_exfiltration_pattern',
                'description': 'Unusual data access pattern detected',
                'severity': 'critical',
                'details': {
                    'recent_access_count': recent_access,
                    'typical_hourly_access': typical_access,
                    'multiplier': recent_access / typical_access
                }
            }
        
        return None
    
    def _check_privilege_escalation_pattern(self, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check for privilege escalation pattern"""
        if event_data.get('security_type') not in ['permission_denied', 'api_access']:
            return None
        
        user_id = event_data.get('user_id')
        
        if not user_id:
            return None
        
        # Check for repeated permission denied events
        recent_denied = SecurityLog.objects.filter(
            user_id=user_id,
            security_type='permission_denied',
            created_at__gte=timezone.now() - timedelta(minutes=30)
        ).count()
        
        if recent_denied >= 10:
            return {
                'type': 'privilege_escalation_pattern',
                'description': 'Possible privilege escalation attempt',
                'severity': 'high',
                'details': {
                    'denied_attempts': recent_denied,
                    'time_window': '30 minutes'
                }
            }
        
        return None
    
    def _check_lateral_movement_pattern(self, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check for lateral movement pattern"""
        user_id = event_data.get('user_id')
        ip_address = event_data.get('ip_address')
        
        if not user_id or not ip_address:
            return None
        
        # Check for access from multiple IPs in short time
        recent_ips = SecurityLog.objects.filter(
            user_id=user_id,
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).values('ip_address').distinct().count()
        
        if recent_ips >= 3:
            return {
                'type': 'lateral_movement_pattern',
                'description': 'Possible lateral movement detected',
                'severity': 'medium',
                'details': {
                    'unique_ips': recent_ips,
                    'time_window': '1 hour'
                }
            }
        
        return None
    
    def _determine_severity(self, event_type: str, risk_score: float, anomalies: List[Dict[str, Any]]) -> str:
        """Determine event severity"""
        # Base severity from risk score
        if risk_score >= 80:
            base_severity = 'critical'
        elif risk_score >= 60:
            base_severity = 'high'
        elif risk_score >= 40:
            base_severity = 'medium'
        else:
            base_severity = 'low'
        
        # Upgrade severity based on anomalies
        for anomaly in anomalies:
            if anomaly['severity'] == 'critical':
                return 'critical'
            elif anomaly['severity'] == 'high' and base_severity != 'critical':
                base_severity = 'high'
        
        # Event type overrides
        critical_events = ['threat_detected', 'incident_created', 'account_locked']
        if event_type in critical_events:
            return 'critical'
        
        high_events = ['security_policy_violation', 'data_modified']
        if event_type in high_events and base_severity != 'critical':
            return 'high'
        
        return base_severity
    
    def _generate_recommendations(self, event_data: Dict[str, Any], risk_score: float, anomalies: List[Dict[str, Any]]) -> List[str]:
        """Generate security recommendations"""
        recommendations = []
        
        # Risk-based recommendations
        if risk_score >= 80:
            recommendations.extend([
                'Immediate investigation required',
                'Consider temporary account suspension',
                'Enable additional authentication factors'
            ])
        elif risk_score >= 60:
            recommendations.extend([
                'Enhanced monitoring recommended',
                'Review user activity patterns',
                'Consider security policy review'
            ])
        elif risk_score >= 40:
            recommendations.extend([
                'Monitor for suspicious activity',
                'Review security configurations'
            ])
        
        # Anomaly-based recommendations
        for anomaly in anomalies:
            if anomaly['type'] == 'geographic_anomaly':
                recommendations.append('Verify user identity for new location')
            elif anomaly['type'] == 'device_anomaly':
                recommendations.append('Register new device or investigate unauthorized access')
            elif anomaly['type'] == 'frequency_anomaly':
                recommendations.append('Implement rate limiting')
            elif anomaly['type'] == 'brute_force_pattern':
                recommendations.append('Block IP address and enforce account lockout')
            elif anomaly['type'] == 'data_exfiltration_pattern':
                recommendations.append('Immediate data access audit and containment')
            elif anomaly['type'] == 'privilege_escalation_pattern':
                recommendations.append('Review and restrict user permissions')
            elif anomaly['type'] == 'lateral_movement_pattern':
                recommendations.append('Network segmentation and access control review')
        
        return list(set(recommendations))  # Remove duplicates
    
    def _is_private_ip(self, ip_address: str) -> bool:
        """Check if IP is private"""
        try:
            import ipaddress
            ip = ipaddress.ip_address(ip_address)
            return ip.is_private
        except:
            return False
    
    def _is_vpn_ip(self, ip_address: str) -> bool:
        """Check if IP is VPN"""
        # This would integrate with VPN detection service
        # For now, return False
        return False
    
    def _is_proxy_ip(self, ip_address: str) -> bool:
        """Check if IP is proxy"""
        # This would integrate with proxy detection service
        # For now, return False
        return False
    
    def _get_ip_location(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """Get IP location information"""
        # This would integrate with geolocation service
        # For now, return dummy data
        return {
            'country': 'Unknown',
            'city': 'Unknown',
            'latitude': 0.0,
            'longitude': 0.0
        }
    
    def _calculate_distance(self, loc1: Dict[str, Any], loc2: Dict[str, Any]) -> float:
        """Calculate distance between two locations"""
        try:
            from math import radians, sin, cos, sqrt, atan2
            
            lat1, lon1 = radians(loc1['latitude']), radians(loc1['longitude'])
            lat2, lon2 = radians(loc2['latitude']), radians(loc2['longitude'])
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            
            # Earth's radius in kilometers
            r = 6371.0
            
            return r * c
        except:
            return 0.0
    
    def _are_similar_user_agents(self, ua1: str, ua2: str) -> bool:
        """Check if two user agents are similar"""
        # Simple similarity check - in production, use more sophisticated method
        return ua1 == ua2


class SecurityRuleEngine:
    """Security rule engine for evaluating security policies"""
    
    def __init__(self):
        self.rules = {}
        self.cache_timeout = 300  # 5 minutes
    
    def evaluate_rules(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate all applicable security rules"""
        results = {
            'passed': [],
            'failed': [],
            'warnings': [],
            'actions': []
        }
        
        # Get applicable rules
        applicable_rules = self._get_applicable_rules(context)
        
        for rule in applicable_rules:
            try:
                result = self._evaluate_rule(rule, context)
                
                if result['status'] == 'passed':
                    results['passed'].append(result)
                elif result['status'] == 'failed':
                    results['failed'].append(result)
                    if result.get('action'):
                        results['actions'].append(result['action'])
                elif result['status'] == 'warning':
                    results['warnings'].append(result)
                
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.get('name', 'unknown')}: {e}")
        
        return results
    
    def _get_applicable_rules(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get rules applicable to the context"""
        # This would load rules from database or configuration
        # For now, return basic rules
        
        return [
            {
                'name': 'failed_login_limit',
                'description': 'Limit failed login attempts',
                'conditions': {
                    'security_type': 'failed_login',
                    'max_attempts': 5,
                    'time_window': 300  # 5 minutes
                },
                'action': {
                    'type': 'block_ip',
                    'duration': 3600  # 1 hour
                }
            },
            {
                'name': 'suspicious_ip_block',
                'description': 'Block suspicious IP addresses',
                'conditions': {
                    'risk_score_min': 70
                },
                'action': {
                    'type': 'block_ip',
                    'duration': 7200  # 2 hours
                }
            },
            {
                'name': 'unusual_location_alert',
                'description': 'Alert for unusual locations',
                'conditions': {
                    'anomaly_type': 'geographic_anomaly'
                },
                'action': {
                    'type': 'send_alert',
                    'severity': 'medium'
                }
            }
        ]
    
    def _evaluate_rule(self, rule: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a single rule"""
        conditions = rule.get('conditions', {})
        
        # Check all conditions
        for condition_key, condition_value in conditions.items():
            if not self._check_condition(condition_key, condition_value, context):
                return {
                    'rule_name': rule.get('name'),
                    'status': 'passed',
                    'message': 'Rule conditions not met'
                }
        
        # All conditions met - rule triggered
        return {
            'rule_name': rule.get('name'),
            'status': 'failed' if rule.get('action') else 'warning',
            'message': rule.get('description', 'Rule triggered'),
            'action': rule.get('action')
        }
    
    def _check_condition(self, condition_key: str, condition_value: Any, context: Dict[str, Any]) -> bool:
        """Check a single condition"""
        context_value = context.get(condition_key)
        
        if context_value is None:
            return False
        
        # Handle different condition types
        if condition_key.endswith('_min'):
            return context_value >= condition_value
        elif condition_key.endswith('_max'):
            return context_value <= condition_value
        elif condition_key.endswith('_type'):
            return context_value == condition_value
        else:
            return context_value == condition_value


# Global instances
security_logic_engine = SecurityLogicEngine()
security_rule_engine = SecurityRuleEngine()


# Export symbols
__all__ = [
    'SecurityLogicEngine',
    'SecurityRuleEngine',
    'security_logic_engine',
    'security_rule_engine'
]