"""
Security Hooks Module
Hook system for extending security functionality
"""

import logging
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.conf import settings

from .models import SecurityLog, SecurityIncident, ThreatIntelligence
from .utils import SecurityUtils
from .helpers import TimeHelper, SecurityMetrics
from .monitoring import monitoring_manager

User = get_user_model()
logger = logging.getLogger('security.hooks')


class SecurityHook:
    """Base security hook class"""
    
    def __init__(self, hook_name: str, description: str = ""):
        self.hook_name = hook_name
        self.description = description
        self.enabled = True
        self.priority = 50  # 0-100, higher priority runs first
        self.config = {}
        self.execution_count = 0
        self.last_executed = None
        self.execution_errors = []
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute hook - override in subclasses"""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def can_execute(self, context: Dict[str, Any]) -> bool:
        """Check if hook can execute in given context"""
        return self.enabled
    
    def before_execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Called before hook execution"""
        return context
    
    def after_execute(self, context: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """Called after hook execution"""
        return result
    
    def on_error(self, context: Dict[str, Any], error: Exception) -> Dict[str, Any]:
        """Called when hook execution fails"""
        error_info = {
            'error': str(error),
            'timestamp': timezone.now().isoformat(),
            'context': context
        }
        self.execution_errors.append(error_info)
        
        # Keep only last 10 errors
        if len(self.execution_errors) > 10:
            self.execution_errors.pop(0)
        
        return error_info
    
    def enable(self):
        """Enable hook"""
        self.enabled = True
    
    def disable(self):
        """Disable hook"""
        self.enabled = False
    
    def set_priority(self, priority: int):
        """Set hook priority"""
        self.priority = max(0, min(100, priority))
    
    def set_config(self, config: Dict[str, Any]):
        """Set hook configuration"""
        self.config = config
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get hook execution statistics"""
        return {
            'hook_name': self.hook_name,
            'enabled': self.enabled,
            'priority': self.priority,
            'execution_count': self.execution_count,
            'last_executed': self.last_executed.isoformat() if self.last_executed else None,
            'error_count': len(self.execution_errors),
            'recent_errors': self.execution_errors[-3:] if self.execution_errors else []
        }


class AuthenticationHook(SecurityHook):
    """Authentication security hook"""
    
    def __init__(self):
        super().__init__(
            "authentication_hook",
            "Hook for authentication security events"
        )
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute authentication hook"""
        try:
            auth_type = context.get('auth_type', 'unknown')
            success = context.get('success', False)
            user = context.get('user')
            ip_address = context.get('ip_address')
            
            # Record authentication event
            SecurityLog.objects.create(
                user=user,
                security_type=f'auth_{auth_type}',
                severity='warning' if not success else 'info',
                description=f"Authentication {'success' if success else 'failure'}: {auth_type}",
                metadata={
                    'ip_address': ip_address,
                    'user_agent': context.get('user_agent', ''),
                    'hook_name': self.hook_name
                }
            )
            
            # Check for suspicious patterns
            if not success:
                self._check_suspicious_login(context)
            
            return {
                'status': 'success',
                'action': 'authentication_processed',
                'auth_type': auth_type,
                'success': success
            }
            
        except Exception as e:
            logger.error(f"Error in authentication hook: {e}")
            raise
    
    def _check_suspicious_login(self, context: Dict[str, Any]):
        """Check for suspicious login patterns"""
        ip_address = context.get('ip_address')
        username = context.get('username', '')
        
        if not ip_address:
            return
        
        # Check for multiple failed attempts from same IP
        recent_failures = SecurityLog.objects.filter(
            security_type='auth_login_failed',
            metadata__ip_address=ip_address,
            created_at__gte=timezone.now() - timedelta(minutes=15)
        ).count()
        
        if recent_failures >= 5:
            # Create security incident
            SecurityIncident.objects.create(
                title=f"Suspicious Login Activity from {ip_address}",
                incident_type='brute_force',
                severity='medium',
                priority='medium',
                description=f"Multiple failed login attempts detected from IP: {ip_address}",
                metadata={
                    'ip_address': ip_address,
                    'failed_attempts': recent_failures,
                    'time_window': '15 minutes'
                }
            )


class DataAccessHook(SecurityHook):
    """Data access security hook"""
    
    def __init__(self):
        super().__init__(
            "data_access_hook",
            "Hook for data access security events"
        )
        self.priority = 70  # Higher priority for data access
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute data access hook"""
        try:
            action = context.get('action', 'unknown')
            resource = context.get('resource', 'unknown')
            user = context.get('user')
            ip_address = context.get('ip_address')
            
            # Determine severity based on action and resource
            severity = self._determine_severity(action, resource)
            
            # Record data access event
            SecurityLog.objects.create(
                user=user,
                security_type=f'data_{action}',
                severity=severity,
                description=f"Data {action}: {resource}",
                metadata={
                    'resource': resource,
                    'ip_address': ip_address,
                    'hook_name': self.hook_name
                }
            )
            
            # Check for unusual access patterns
            self._check_unusual_access(context)
            
            return {
                'status': 'success',
                'action': 'data_access_processed',
                'action_type': action,
                'resource': resource,
                'severity': severity
            }
            
        except Exception as e:
            logger.error(f"Error in data access hook: {e}")
            raise
    
    def _determine_severity(self, action: str, resource: str) -> str:
        """Determine event severity"""
        high_risk_actions = ['delete', 'modify', 'export', 'download']
        high_risk_resources = ['user_data', 'financial_data', 'personal_data', 'sensitive_data']
        
        if action in high_risk_actions or any(risk in resource for risk in high_risk_resources):
            return 'high'
        elif action == 'read':
            return 'low'
        else:
            return 'medium'
    
    def _check_unusual_access(self, context: Dict[str, Any]):
        """Check for unusual data access patterns"""
        user = context.get('user')
        if not user:
            return
        
        # Get recent data access events for user
        recent_access = SecurityLog.objects.filter(
            user=user,
            security_type__startswith='data_',
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        if recent_access > 100:  # More than 100 data accesses in 1 hour
            SecurityLog.objects.create(
                user=user,
                security_type='unusual_access_pattern',
                severity='medium',
                description=f"Unusual data access pattern detected",
                metadata={
                    'access_count': recent_access,
                    'time_window': '1 hour',
                    'hook_name': self.hook_name
                }
            )


class ThreatDetectionHook(SecurityHook):
    """Threat detection security hook"""
    
    def __init__(self):
        super().__init__(
            "threat_detection_hook",
            "Hook for threat detection events"
        )
        self.priority = 90  # High priority for threats
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute threat detection hook"""
        try:
            threat_type = context.get('threat_type', 'unknown')
            indicator = context.get('indicator', '')
            severity = context.get('severity', 'medium')
            source = context.get('source', 'hook_system')
            
            # Create or update threat intelligence
            threat, created = ThreatIntelligence.objects.update_or_create(
                indicator=indicator,
                defaults={
                    'threat_type': threat_type,
                    'indicator_type': self._get_indicator_type(indicator),
                    'severity': severity,
                    'source': source,
                    'description': f"Threat detected via {self.hook_name}",
                    'is_active': True
                }
            )
            
            action = 'created' if created else 'updated'
            
            # Record threat detection event
            SecurityLog.objects.create(
                security_type='threat_detected',
                severity='high',
                description=f"Threat intelligence {action}: {indicator}",
                metadata={
                    'threat_id': str(threat.id),
                    'threat_type': threat_type,
                    'indicator': indicator,
                    'hook_name': self.hook_name
                }
            )
            
            # Trigger alerts for high severity threats
            if severity in ['high', 'critical']:
                self._trigger_threat_alert(threat, context)
            
            return {
                'status': 'success',
                'action': f'threat_{action}',
                'threat_id': str(threat.id),
                'threat_type': threat_type,
                'indicator': indicator
            }
            
        except Exception as e:
            logger.error(f"Error in threat detection hook: {e}")
            raise
    
    def _get_indicator_type(self, indicator: str) -> str:
        """Determine indicator type from indicator value"""
        if '.' in indicator and len(indicator.split('.')) == 4:
            return 'ip_address'
        elif '@' in indicator:
            return 'email'
        elif indicator.startswith('http'):
            return 'url'
        elif len(indicator) in [32, 40, 64]:
            return 'hash'
        else:
            return 'unknown'
    
    def _trigger_threat_alert(self, threat: ThreatIntelligence, context: Dict[str, Any]):
        """Trigger threat alert"""
        # Create security incident for critical threats
        if threat.severity == 'critical':
            SecurityIncident.objects.create(
                title=f"Critical Threat Detected: {threat.indicator}",
                incident_type='threat_detected',
                severity='critical',
                priority='critical',
                description=f"Critical threat detected: {threat.threat_type} - {threat.indicator}",
                metadata={
                    'threat_id': str(threat.id),
                    'hook_name': self.hook_name,
                    'context': context
                }
            )


class IncidentManagementHook(SecurityHook):
    """Incident management security hook"""
    
    def __init__(self):
        super().__init__(
            "incident_management_hook",
            "Hook for incident management events"
        )
        self.priority = 80  # High priority for incidents
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute incident management hook"""
        try:
            incident_action = context.get('action', 'unknown')
            incident = context.get('incident')
            user = context.get('user')
            
            if not incident:
                return {
                    'status': 'error',
                    'message': 'Incident not provided'
                }
            
            # Process incident action
            if incident_action == 'created':
                self._handle_incident_created(incident, context)
            elif incident_action == 'updated':
                self._handle_incident_updated(incident, context)
            elif incident_action == 'resolved':
                self._handle_incident_resolved(incident, context)
            elif incident_action == 'escalated':
                self._handle_incident_escalated(incident, context)
            
            # Record incident management event
            SecurityLog.objects.create(
                user=user,
                security_type=f'incident_{incident_action}',
                severity=incident.severity,
                description=f"Incident {incident_action}: {incident.title}",
                metadata={
                    'incident_id': str(incident.id),
                    'incident_type': incident.incident_type,
                    'hook_name': self.hook_name
                }
            )
            
            return {
                'status': 'success',
                'action': f'incident_{incident_action}',
                'incident_id': str(incident.id),
                'incident_type': incident.incident_type
            }
            
        except Exception as e:
            logger.error(f"Error in incident management hook: {e}")
            raise
    
    def _handle_incident_created(self, incident: SecurityIncident, context: Dict[str, Any]):
        """Handle incident creation"""
        # Update monitoring metrics
        monitoring_manager.record_event('incident_created', incident.severity)
        
        # Trigger notifications for critical incidents
        if incident.severity == 'critical':
            self._trigger_incident_alert(incident, 'created')
    
    def _handle_incident_updated(self, incident: SecurityIncident, context: Dict[str, Any]):
        """Handle incident update"""
        # Log update details
        update_fields = context.get('update_fields', [])
        logger.info(f"Incident {incident.id} updated: {update_fields}")
    
    def _handle_incident_resolved(self, incident: SecurityIncident, context: Dict[str, Any]):
        """Handle incident resolution"""
        # Update resolved timestamp
        incident.resolved_at = timezone.now()
        incident.save(update_fields=['resolved_at'])
        
        # Calculate resolution time
        if incident.opened_at:
            resolution_time = (incident.resolved_at - incident.opened_at).total_seconds()
            logger.info(f"Incident {incident.id} resolved in {resolution_time} seconds")
    
    def _handle_incident_escalated(self, incident: SecurityIncident, context: Dict[str, Any]):
        """Handle incident escalation"""
        # Update priority if needed
        if incident.priority != 'critical':
            incident.priority = 'critical'
            incident.save(update_fields=['priority'])
        
        # Trigger escalation alert
        self._trigger_incident_alert(incident, 'escalated')
    
    def _trigger_incident_alert(self, incident: SecurityIncident, action: str):
        """Trigger incident alert"""
        # This would implement incident alert logic
        logger.warning(f"Incident alert: {incident.title} - {action}")


class SystemHealthHook(SecurityHook):
    """System health monitoring hook"""
    
    def __init__(self):
        super().__init__(
            "system_health_hook",
            "Hook for system health monitoring"
        )
        self.priority = 30  # Lower priority for system health
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute system health hook"""
        try:
            health_check = context.get('health_check', 'unknown')
            status = context.get('status', 'unknown')
            metrics = context.get('metrics', {})
            
            # Determine severity based on status
            severity = self._determine_health_severity(status)
            
            # Record system health event
            SecurityLog.objects.create(
                security_type=f'system_{health_check}',
                severity=severity,
                description=f"System health check: {health_check} - {status}",
                metadata={
                    'status': status,
                    'metrics': metrics,
                    'hook_name': self.hook_name
                }
            )
            
            # Update monitoring system
            monitoring_manager.update_system_health(health_check, status, metrics)
            
            # Trigger alerts for critical health issues
            if severity == 'critical':
                self._trigger_health_alert(health_check, status, metrics)
            
            return {
                'status': 'success',
                'action': 'health_check_processed',
                'health_check': health_check,
                'status': status,
                'severity': severity
            }
            
        except Exception as e:
            logger.error(f"Error in system health hook: {e}")
            raise
    
    def _determine_health_severity(self, status: str) -> str:
        """Determine health check severity"""
        critical_statuses = ['error', 'failure', 'down', 'critical']
        warning_statuses = ['warning', 'degraded', 'unusual']
        
        if status in critical_statuses:
            return 'critical'
        elif status in warning_statuses:
            return 'warning'
        else:
            return 'info'
    
    def _trigger_health_alert(self, health_check: str, status: str, metrics: Dict[str, Any]):
        """Trigger health alert"""
        # Create security incident for critical health issues
        SecurityIncident.objects.create(
            title=f"System Health Alert: {health_check}",
            incident_type='system_health',
            severity='critical',
            priority='high',
            description=f"System health issue detected: {health_check} - {status}",
            metadata={
                'health_check': health_check,
                'status': status,
                'metrics': metrics,
                'hook_name': self.hook_name
            }
        )


class HookManager:
    """Manager for security hooks"""
    
    def __init__(self):
        self.hooks = {}
        self.hook_chains = {}
        self.execution_history = []
        self.max_history = 1000
        self.enabled = True
        self._initialize_hooks()
    
    def _initialize_hooks(self):
        """Initialize built-in hooks"""
        self.register_hook(AuthenticationHook())
        self.register_hook(DataAccessHook())
        self.register_hook(ThreatDetectionHook())
        self.register_hook(IncidentManagementHook())
        self.register_hook(SystemHealthHook())
    
    def register_hook(self, hook: SecurityHook):
        """Register a security hook"""
        self.hooks[hook.hook_name] = hook
        logger.info(f"Registered security hook: {hook.hook_name}")
    
    def unregister_hook(self, hook_name: str) -> bool:
        """Unregister a security hook"""
        if hook_name in self.hooks:
            del self.hooks[hook_name]
            logger.info(f"Unregistered security hook: {hook_name}")
            return True
        return False
    
    def get_hook(self, hook_name: str) -> Optional[SecurityHook]:
        """Get hook by name"""
        return self.hooks.get(hook_name)
    
    def execute_hook(self, hook_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific hook"""
        hook = self.get_hook(hook_name)
        
        if not hook:
            return {
                'status': 'error',
                'message': f'Hook not found: {hook_name}'
            }
        
        if not hook.can_execute(context):
            return {
                'status': 'skipped',
                'message': f'Hook cannot execute: {hook_name}'
            }
        
        try:
            # Record execution start
            execution_start = timezone.now()
            
            # Before execution
            modified_context = hook.before_execute(context)
            
            # Execute hook
            result = hook.execute(modified_context)
            
            # After execution
            final_result = hook.after_execute(modified_context, result)
            
            # Update hook statistics
            hook.execution_count += 1
            hook.last_executed = execution_start
            
            # Record execution
            execution_record = {
                'hook_name': hook_name,
                'execution_time': execution_start.isoformat(),
                'duration': (timezone.now() - execution_start).total_seconds(),
                'status': 'success',
                'result': final_result
            }
            
            self.execution_history.append(execution_record)
            if len(self.execution_history) > self.max_history:
                self.execution_history.pop(0)
            
            final_result['execution_time'] = execution_start.isoformat()
            final_result['duration'] = execution_record['duration']
            
            return final_result
            
        except Exception as e:
            # Handle error
            error_result = hook.on_error(context, e)
            
            execution_record = {
                'hook_name': hook_name,
                'execution_time': execution_start.isoformat(),
                'duration': (timezone.now() - execution_start).total_seconds(),
                'status': 'error',
                'error': error_result
            }
            
            self.execution_history.append(execution_record)
            if len(self.execution_history) > self.max_history:
                self.execution_history.pop(0)
            
            logger.error(f"Error executing hook {hook_name}: {e}")
            
            return {
                'status': 'error',
                'message': str(e),
                'execution_time': execution_start.isoformat(),
                'duration': execution_record['duration']
            }
    
    def execute_hooks_by_type(self, hook_type: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute all hooks of a specific type"""
        results = []
        
        # Find hooks that match the type
        matching_hooks = []
        for hook_name, hook in self.hooks.items():
            if hook_type in hook_name or hook_name.startswith(hook_type):
                matching_hooks.append(hook)
        
        # Sort by priority (higher priority first)
        matching_hooks.sort(key=lambda h: h.priority, reverse=True)
        
        # Execute hooks in priority order
        for hook in matching_hooks:
            if hook.can_execute(context):
                result = self.execute_hook(hook.hook_name, context)
                results.append(result)
        
        return results
    
    def get_hook_statistics(self) -> Dict[str, Any]:
        """Get statistics for all hooks"""
        return {
            'total_hooks': len(self.hooks),
            'enabled_hooks': len([h for h in self.hooks.values() if h.enabled]),
            'total_executions': sum(h.execution_count for h in self.hooks.values()),
            'hooks': {
                name: hook.get_statistics()
                for name, hook in self.hooks.items()
            }
        }
    
    def get_execution_history(self, hook_name: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get hook execution history"""
        history = self.execution_history
        
        if hook_name:
            history = [e for e in history if e['hook_name'] == hook_name]
        
        return history[-limit:]
    
    def enable_all_hooks(self):
        """Enable all hooks"""
        for hook in self.hooks.values():
            hook.enable()
        
        self.enabled = True
        logger.info("All hooks enabled")
    
    def disable_all_hooks(self):
        """Disable all hooks"""
        for hook in self.hooks.values():
            hook.disable()
        
        self.enabled = False
        logger.info("All hooks disabled")
    
    def enable_hook(self, hook_name: str) -> bool:
        """Enable a specific hook"""
        hook = self.get_hook(hook_name)
        if hook:
            hook.enable()
            return True
        return False
    
    def disable_hook(self, hook_name: str) -> bool:
        """Disable a specific hook"""
        hook = self.get_hook(hook_name)
        if hook:
            hook.disable()
            return True
        return False


# Global hook manager
hook_manager = HookManager()


# Export symbols
__all__ = [
    'SecurityHook',
    'AuthenticationHook',
    'DataAccessHook',
    'ThreatDetectionHook',
    'IncidentManagementHook',
    'SystemHealthHook',
    'HookManager',
    'hook_manager'
]