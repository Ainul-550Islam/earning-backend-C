"""
Security Events Module
Event system for security operations
"""

import logging
import threading
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.dispatch import Signal
from django.conf import settings

from .models import SecurityLog, SecurityIncident, ThreatIntelligence
from .utils import SecurityUtils
from .helpers import TimeHelper, SecurityMetrics
from .monitoring import monitoring_manager

User = get_user_model()
logger = logging.getLogger('security.events')


class SecurityEvent:
    """Base security event class"""
    
    def __init__(self, event_type: str, data: Dict[str, Any] = None):
        self.event_type = event_type
        self.data = data or {}
        self.timestamp = timezone.now()
        self.id = SecurityUtils.generate_uuid()
        self.source = self.data.get('source', 'system')
        self.severity = self.data.get('severity', 'info')
        self.user = self.data.get('user')
        self.metadata = self.data.get('metadata', {})
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            'id': str(self.id),
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'severity': self.severity,
            'user': str(self.user.id) if self.user else None,
            'data': self.data,
            'metadata': self.metadata
        }
    
    def __str__(self):
        return f"{self.event_type} - {self.severity}"


class AuthenticationEvent(SecurityEvent):
    """Authentication event"""
    
    def __init__(self, auth_type: str, success: bool, user: User = None, **kwargs):
        event_type = f"auth_{auth_type}_{'success' if success else 'failed'}"
        severity = 'warning' if not success else 'info'
        
        data = {
            'auth_type': auth_type,
            'success': success,
            'user': user,
            'severity': severity,
            **kwargs
        }
        
        super().__init__(event_type, data)
    
    def get_risk_score(self) -> float:
        """Get authentication event risk score"""
        if not self.data.get('success'):
            return 30.0  # Failed authentication has higher risk
        
        auth_type = self.data.get('auth_type', 'unknown')
        if auth_type == 'login':
            return 10.0
        elif auth_type == 'api_access':
            return 15.0
        else:
            return 5.0


class DataAccessEvent(SecurityEvent):
    """Data access event"""
    
    def __init__(self, action: str, resource: str, user: User = None, **kwargs):
        event_type = f"data_{action}"
        severity = self._determine_severity(action, resource)
        
        data = {
            'action': action,
            'resource': resource,
            'user': user,
            'severity': severity,
            **kwargs
        }
        
        super().__init__(event_type, data)
    
    def _determine_severity(self, action: str, resource: str) -> str:
        """Determine event severity"""
        high_risk_actions = ['delete', 'modify', 'export']
        high_risk_resources = ['user_data', 'financial_data', 'personal_data']
        
        if action in high_risk_actions or resource in high_risk_resources:
            return 'high'
        elif action == 'read':
            return 'low'
        else:
            return 'medium'
    
    def get_risk_score(self) -> float:
        """Get data access event risk score"""
        action = self.data.get('action', 'unknown')
        resource = self.data.get('resource', 'unknown')
        
        base_score = 10.0
        
        # Action-based scoring
        if action == 'delete':
            base_score += 30.0
        elif action == 'modify':
            base_score += 20.0
        elif action == 'export':
            base_score += 25.0
        
        # Resource-based scoring
        if 'financial' in resource:
            base_score += 20.0
        elif 'personal' in resource:
            base_score += 15.0
        
        return min(100.0, base_score)


class ThreatEvent(SecurityEvent):
    """Threat detection event"""
    
    def __init__(self, threat_type: str, indicator: str, severity: str = 'medium', **kwargs):
        event_type = f"threat_{threat_type}"
        
        data = {
            'threat_type': threat_type,
            'indicator': indicator,
            'severity': severity,
            **kwargs
        }
        
        super().__init__(event_type, data)
    
    def get_risk_score(self) -> float:
        """Get threat event risk score"""
        severity_scores = {
            'low': 20.0,
            'medium': 40.0,
            'high': 60.0,
            'critical': 80.0
        }
        
        return severity_scores.get(self.severity, 40.0)


class IncidentEvent(SecurityEvent):
    """Security incident event"""
    
    def __init__(self, incident_type: str, action: str, incident: SecurityIncident = None, **kwargs):
        event_type = f"incident_{action}"
        severity = incident.severity if incident else 'medium'
        
        data = {
            'incident_type': incident_type,
            'action': action,
            'incident': incident,
            'severity': severity,
            **kwargs
        }
        
        super().__init__(event_type, data)
    
    def get_risk_score(self) -> float:
        """Get incident event risk score"""
        severity_scores = {
            'low': 30.0,
            'medium': 50.0,
            'high': 70.0,
            'critical': 90.0
        }
        
        return severity_scores.get(self.severity, 50.0)


class SystemEvent(SecurityEvent):
    """System security event"""
    
    def __init__(self, system_type: str, status: str, **kwargs):
        event_type = f"system_{system_type}_{status}"
        severity = self._determine_severity(system_type, status)
        
        data = {
            'system_type': system_type,
            'status': status,
            'severity': severity,
            **kwargs
        }
        
        super().__init__(event_type, data)
    
    def _determine_severity(self, system_type: str, status: str) -> str:
        """Determine event severity"""
        critical_statuses = ['error', 'failure', 'breach', 'compromise']
        warning_statuses = ['warning', 'degraded', 'unusual']
        
        if status in critical_statuses:
            return 'critical'
        elif status in warning_statuses:
            return 'warning'
        else:
            return 'info'
    
    def get_risk_score(self) -> float:
        """Get system event risk score"""
        severity_scores = {
            'info': 5.0,
            'warning': 25.0,
            'critical': 60.0
        }
        
        return severity_scores.get(self.severity, 5.0)


class EventManager:
    """Security event management system"""
    
    def __init__(self):
        self.events = []
        self.event_handlers = {}
        self.event_filters = {}
        self.max_events = 10000
        self.lock = threading.Lock()
        self.enabled = True
        
        # Initialize built-in handlers
        self._initialize_handlers()
    
    def _initialize_handlers(self):
        """Initialize built-in event handlers"""
        self.register_handler('auth_*', self._handle_authentication_event)
        self.register_handler('data_*', self._handle_data_access_event)
        self.register_handler('threat_*', self._handle_threat_event)
        self.register_handler('incident_*', self._handle_incident_event)
        self.register_handler('system_*', self._handle_system_event)
    
    def emit_event(self, event: SecurityEvent) -> bool:
        """Emit a security event"""
        if not self.enabled:
            return False
        
        with self.lock:
            try:
                # Add to event buffer
                self.events.append(event)
                
                # Maintain buffer size
                if len(self.events) > self.max_events:
                    self.events.pop(0)
                
                # Process event through handlers
                self._process_event(event)
                
                # Log event
                self._log_event(event)
                
                logger.debug(f"Emitted event: {event.event_type}")
                return True
                
            except Exception as e:
                logger.error(f"Error emitting event: {e}")
                return False
    
    def _process_event(self, event: SecurityEvent):
        """Process event through handlers"""
        # Find matching handlers
        matching_handlers = []
        
        for pattern, handlers in self.event_handlers.items():
            if self._pattern_matches(event.event_type, pattern):
                matching_handlers.extend(handlers)
        
        # Apply filters
        filtered_handlers = []
        for handler in matching_handlers:
            if self._passes_filters(event, handler):
                filtered_handlers.append(handler)
        
        # Execute handlers
        for handler in filtered_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")
    
    def _pattern_matches(self, event_type: str, pattern: str) -> bool:
        """Check if event type matches pattern"""
        if '*' in pattern:
            # Simple wildcard matching
            import fnmatch
            return fnmatch.fnmatch(event_type, pattern)
        else:
            return event_type == pattern
    
    def _passes_filters(self, event: SecurityEvent, handler: Callable) -> bool:
        """Check if event passes handler filters"""
        # This would implement filter logic
        # For now, return True
        return True
    
    def _log_event(self, event: SecurityEvent):
        """Log event to security logs"""
        try:
            SecurityLog.objects.create(
                user=event.user,
                security_type=event.event_type,
                severity=event.severity,
                description=f"Security event: {event.event_type}",
                metadata=event.to_dict()
            )
        except Exception as e:
            logger.error(f"Error logging event: {e}")
    
    def register_handler(self, pattern: str, handler: Callable):
        """Register event handler"""
        if pattern not in self.event_handlers:
            self.event_handlers[pattern] = []
        
        self.event_handlers[pattern].append(handler)
        logger.info(f"Registered handler for pattern: {pattern}")
    
    def unregister_handler(self, pattern: str, handler: Callable):
        """Unregister event handler"""
        if pattern in self.event_handlers:
            try:
                self.event_handlers[pattern].remove(handler)
                logger.info(f"Unregistered handler for pattern: {pattern}")
            except ValueError:
                logger.warning(f"Handler not found for pattern: {pattern}")
    
    def register_filter(self, pattern: str, filter_func: Callable):
        """Register event filter"""
        if pattern not in self.event_filters:
            self.event_filters[pattern] = []
        
        self.event_filters[pattern].append(filter_func)
        logger.info(f"Registered filter for pattern: {pattern}")
    
    def get_events(self, event_type: str = None, 
                  start_time: datetime = None, 
                  end_time: datetime = None,
                  severity: str = None,
                  user: User = None) -> List[SecurityEvent]:
        """Get events with filtering"""
        with self.lock:
            events = self.events.copy()
        
        # Apply filters
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]
        
        if severity:
            events = [e for e in events if e.severity == severity]
        
        if user:
            events = [e for e in events if e.user == user]
        
        return events
    
    def get_event_statistics(self) -> Dict[str, Any]:
        """Get event statistics"""
        with self.lock:
            total_events = len(self.events)
            
            # Count by type
            type_counts = {}
            for event in self.events:
                type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1
            
            # Count by severity
            severity_counts = {}
            for event in self.events:
                severity_counts[event.severity] = severity_counts.get(event.severity, 0) + 1
            
            # Count by source
            source_counts = {}
            for event in self.events:
                source_counts[event.source] = source_counts.get(event.source, 0) + 1
            
            return {
                'total_events': total_events,
                'buffer_size': len(self.events),
                'max_buffer_size': self.max_events,
                'type_counts': type_counts,
                'severity_counts': severity_counts,
                'source_counts': source_counts,
                'enabled': self.enabled
            }
    
    def clear_events(self, event_type: str = None):
        """Clear events"""
        with self.lock:
            if event_type:
                self.events = [e for e in self.events if e.event_type != event_type]
                logger.info(f"Cleared events of type: {event_type}")
            else:
                self.events.clear()
                logger.info("Cleared all events")
    
    def enable(self):
        """Enable event manager"""
        self.enabled = True
        logger.info("Event manager enabled")
    
    def disable(self):
        """Disable event manager"""
        self.enabled = False
        logger.info("Event manager disabled")
    
    # Built-in handlers
    def _handle_authentication_event(self, event: SecurityEvent):
        """Handle authentication event"""
        try:
            auth_type = event.data.get('auth_type')
            success = event.data.get('success', False)
            
            if not success:
                # Check for brute force
                self._check_brute_force(event)
            
            # Update monitoring
            monitoring_manager.record_event(event.event_type, event.severity)
            
        except Exception as e:
            logger.error(f"Error handling authentication event: {e}")
    
    def _handle_data_access_event(self, event: SecurityEvent):
        """Handle data access event"""
        try:
            action = event.data.get('action')
            resource = event.data.get('resource')
            
            # Check for unusual access patterns
            if action in ['delete', 'export']:
                self._check_unusual_access(event)
            
            # Update analytics
            security_analytics.record_data_access(action, resource, event.user)
            
        except Exception as e:
            logger.error(f"Error handling data access event: {e}")
    
    def _handle_threat_event(self, event: SecurityEvent):
        """Handle threat event"""
        try:
            threat_type = event.data.get('threat_type')
            indicator = event.data.get('indicator')
            
            # Create threat intelligence record
            ThreatIntelligence.objects.get_or_create(
                indicator=indicator,
                defaults={
                    'threat_type': threat_type,
                    'indicator_type': self._get_indicator_type(indicator),
                    'severity': event.severity,
                    'source': 'event_system',
                    'description': f"Threat detected via event: {event.event_type}",
                    'is_active': True
                }
            )
            
            # Trigger alerts for high severity threats
            if event.severity in ['high', 'critical']:
                self._trigger_threat_alert(event)
            
        except Exception as e:
            logger.error(f"Error handling threat event: {e}")
    
    def _handle_incident_event(self, event: SecurityEvent):
        """Handle incident event"""
        try:
            action = event.data.get('action')
            incident = event.data.get('incident')
            
            if incident:
                # Update incident status if needed
                if action == 'resolved':
                    incident.status = 'resolved'
                    incident.resolved_at = timezone.now()
                    incident.save()
                elif action == 'escalated':
                    incident.priority = 'critical' if incident.priority != 'critical' else 'high'
                    incident.save()
            
            # Update monitoring
            monitoring_manager.record_event(event.event_type, event.severity)
            
        except Exception as e:
            logger.error(f"Error handling incident event: {e}")
    
    def _handle_system_event(self, event: SecurityEvent):
        """Handle system event"""
        try:
            system_type = event.data.get('system_type')
            status = event.data.get('status')
            
            # Handle critical system events
            if event.severity == 'critical':
                self._trigger_system_alert(event)
            
            # Update system health
            monitoring_manager.update_system_health(system_type, status)
            
        except Exception as e:
            logger.error(f"Error handling system event: {e}")
    
    def _check_brute_force(self, event: SecurityEvent):
        """Check for brute force attacks"""
        user = event.user
        if not user:
            return
        
        # Count recent failed attempts
        recent_failures = self.get_events(
            event_type='auth_*_failed',
            start_time=timezone.now() - timedelta(minutes=15),
            user=user
        )
        
        if len(recent_failures) >= 5:
            # Create security incident
            SecurityIncident.objects.create(
                title=f"Brute Force Attack on User {user.username}",
                incident_type='brute_force',
                severity='high',
                priority='high',
                description=f"Multiple failed authentication attempts detected for user {user.username}",
                user=user,
                metadata={
                    'failed_attempts': len(recent_failures),
                    'time_window': '15 minutes'
                }
            )
    
    def _check_unusual_access(self, event: SecurityEvent):
        """Check for unusual access patterns"""
        user = event.user
        if not user:
            return
        
        # Get recent access events
        recent_access = self.get_events(
            event_type='data_*',
            start_time=timezone.now() - timedelta(hours=1),
            user=user
        )
        
        if len(recent_access) > 100:  # More than 100 accesses in 1 hour
            # Create security incident
            SecurityIncident.objects.create(
                title=f"Unusual Data Access Pattern - User {user.username}",
                incident_type='unusual_access',
                severity='medium',
                priority='medium',
                description=f"Unusual data access pattern detected for user {user.username}",
                user=user,
                metadata={
                    'access_count': len(recent_access),
                    'time_window': '1 hour'
                }
            )
    
    def _trigger_threat_alert(self, event: SecurityEvent):
        """Trigger threat alert"""
        # This would implement threat alert logic
        logger.warning(f"Threat alert triggered: {event.event_type}")
    
    def _trigger_system_alert(self, event: SecurityEvent):
        """Trigger system alert"""
        # This would implement system alert logic
        logger.critical(f"System alert triggered: {event.event_type}")
    
    def _get_indicator_type(self, indicator: str) -> str:
        """Get indicator type from indicator value"""
        if '.' in indicator and len(indicator.split('.')) == 4:
            return 'ip_address'
        elif '@' in indicator:
            return 'email'
        elif indicator.startswith('http'):
            return 'url'
        elif len(indicator) == 32 or len(indicator) == 40 or len(indicator) == 64:
            return 'hash'
        else:
            return 'unknown'


# Global event manager
event_manager = EventManager()


# Django signal integration
class DjangoEventBridge:
    """Bridge between Django signals and event system"""
    
    def __init__(self, event_manager: EventManager):
        self.event_manager = event_manager
        self._setup_django_signals()
    
    def _setup_django_signals(self):
        """Setup Django signal connections"""
        from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
        
        user_logged_in.connect(self._handle_user_login, sender=None)
        user_logged_out.connect(self._handle_user_logout, sender=None)
        user_login_failed.connect(self._handle_login_failed, sender=None)
    
    def _handle_user_login(self, sender, request, user, **kwargs):
        """Handle user login"""
        event = AuthenticationEvent(
            auth_type='login',
            success=True,
            user=user,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        self.event_manager.emit_event(event)
    
    def _handle_user_logout(self, sender, request, user, **kwargs):
        """Handle user logout"""
        event = AuthenticationEvent(
            auth_type='logout',
            success=True,
            user=user,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        self.event_manager.emit_event(event)
    
    def _handle_login_failed(self, sender, credentials, request, **kwargs):
        """Handle login failed"""
        event = AuthenticationEvent(
            auth_type='login',
            success=False,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            username=credentials.get('username', '')
        )
        self.event_manager.emit_event(event)
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# Initialize Django event bridge
django_event_bridge = DjangoEventBridge(event_manager)


# Export symbols
__all__ = [
    'SecurityEvent',
    'AuthenticationEvent',
    'DataAccessEvent',
    'ThreatEvent',
    'IncidentEvent',
    'SystemEvent',
    'EventManager',
    'event_manager',
    'DjangoEventBridge',
    'django_event_bridge'
]