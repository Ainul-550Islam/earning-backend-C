"""
Alert Escalation System for alerts app - Advanced alert escalation management
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
import asyncio
import logging
import json
import uuid
import time
from enum import Enum
from datetime import timedelta

logger = logging.getLogger(__name__)


class EscalationLevel(Enum):
    """Escalation level enumeration"""
    LEVEL_1 = "level_1"
    LEVEL_2 = "level_2"
    LEVEL_3 = "level_3"
    LEVEL_4 = "level_4"
    LEVEL_5 = "level_5"


class EscalationStatus(Enum):
    """Escalation status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class EscalationRule:
    """Represents an escalation rule"""
    
    def __init__(self, name: str, alert_type: str, conditions: Dict[str, Any],
                 escalation_levels: List[Dict[str, Any]], enabled: bool = True):
        self.id = str(uuid.uuid4())
        self.name = name
        self.alert_type = alert_type
        self.conditions = conditions
        self.escalation_levels = escalation_levels
        self.enabled = enabled
        self.created_at = timezone.now()
        
    def matches_alert(self, alert: Dict[str, Any]) -> bool:
        """Check if alert matches escalation rule conditions"""
        if not self.enabled:
            return False
        
        # Check alert type
        if self.alert_type != alert.get('alert_type'):
            return False
        
        # Check conditions
        for condition_key, condition_value in self.conditions.items():
            alert_value = alert.get(condition_key)
            
            if condition_key == 'severity':
                if alert_value not in condition_value:
                    return False
            elif condition_key == 'threshold_value':
                if alert_value < condition_value:
                    return False
            elif condition_key == 'time_window_minutes':
                if alert_value > condition_value:
                    return False
            elif condition_key == 'custom_field':
                if not self._check_custom_condition(alert_value, condition_value):
                    return False
        
        return True
    
    def _check_custom_condition(self, alert_value: Any, condition_value: Any) -> bool:
        """Check custom condition"""
        if isinstance(condition_value, dict):
            operator = condition_value.get('operator', 'equals')
            value = condition_value.get('value')
            
            if operator == 'equals':
                return alert_value == value
            elif operator == 'greater_than':
                return alert_value > value
            elif operator == 'less_than':
                return alert_value < value
            elif operator == 'contains':
                return str(value) in str(alert_value)
        
        return alert_value == condition_value
    
    def get_next_level(self, current_level: EscalationLevel) -> Optional[Dict[str, Any]]:
        """Get next escalation level"""
        level_order = [
            EscalationLevel.LEVEL_1,
            EscalationLevel.LEVEL_2,
            EscalationLevel.LEVEL_3,
            EscalationLevel.LEVEL_4,
            EscalationLevel.LEVEL_5
        ]
        
        current_index = level_order.index(current_level)
        next_index = current_index + 1
        
        if next_index < len(self.escalation_levels):
            return self.escalation_levels[next_index]
        
        return None


class EscalationAction(ABC):
    """Abstract base class for escalation actions"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        self.enabled = config.get('enabled', True)
        
    @abstractmethod
    async def execute(self, escalation: 'Escalation', context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute escalation action"""
        pass
    
    def get_action_info(self) -> Dict[str, Any]:
        """Get action information"""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'config': self.config
        }


class NotificationEscalationAction(EscalationAction):
    """Notification escalation action"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.notification_channels = config.get('channels', ['email'])
        self.recipients = config.get('recipients', [])
        self.message_template = config.get('message_template', 'Alert escalated to level {level}')
        self.subject_template = config.get('subject_template', 'ESCALATION: {alert_type} - Level {level}')
        
    async def execute(self, escalation: 'Escalation', context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute notification escalation"""
        try:
            from .notification import get_notification_manager
            
            notification_manager = get_notification_manager()
            if not notification_manager:
                return {
                    'success': False,
                    'error': 'Notification manager not available'
                }
            
            # Prepare message
            message = self.message_template.format(
                level=escalation.current_level.value,
                alert_type=escalation.alert_type,
                alert_id=escalation.alert_id,
                **context
            )
            
            subject = self.subject_template.format(
                level=escalation.current_level.value,
                alert_type=escalation.alert_type,
                alert_id=escalation.alert_id,
                **context
            )
            
            # Send notifications
            results = []
            for recipient in self.recipients:
                for channel in self.notification_channels:
                    notification = notification_manager.create_notification(
                        recipient=recipient,
                        subject=subject,
                        message=message,
                        channel=channel,
                        priority='high'
                    )
                    
                    result = await notification_manager.send_notification(notification)
                    results.append(result)
            
            success_count = sum(1 for r in results if r['success'])
            
            return {
                'success': success_count > 0,
                'notifications_sent': success_count,
                'notifications_failed': len(results) - success_count,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Notification escalation error: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }


class EmailEscalationAction(EscalationAction):
    """Email escalation action"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.recipients = config.get('recipients', [])
        self.template_name = config.get('template_name', 'escalation_email')
        self.subject = config.get('subject', 'Alert Escalation')
        
    async def execute(self, escalation: 'Escalation', context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute email escalation"""
        try:
            from .email_service import get_email_service
            
            email_service = get_email_service()
            if not email_service:
                return {
                    'success': False,
                    'error': 'Email service not available'
                }
            
            # Send emails
            results = []
            for recipient in self.recipients:
                email = email_service.create_email_from_template(
                    template_name=self.template_name,
                    to_email=recipient,
                    context={
                        'escalation': escalation,
                        'alert': context.get('alert', {}),
                        'level': escalation.current_level.value
                    }
                )
                
                result = await email_service.send_email(email)
                results.append(result)
            
            success_count = sum(1 for r in results if r['success'])
            
            return {
                'success': success_count > 0,
                'emails_sent': success_count,
                'emails_failed': len(results) - success_count,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Email escalation error: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }


class WebhookEscalationAction(EscalationAction):
    """Webhook escalation action"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.webhook_url = config.get('webhook_url')
        self.method = config.get('method', 'POST')
        self.headers = config.get('headers', {})
        self.payload_template = config.get('payload_template', {})
        
    async def execute(self, escalation: 'Escalation', context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute webhook escalation"""
        try:
            import requests
            
            # Prepare payload
            payload = {
                'escalation_id': escalation.id,
                'alert_id': escalation.alert_id,
                'alert_type': escalation.alert_type,
                'escalation_level': escalation.current_level.value,
                'escalation_status': escalation.status.value,
                'created_at': escalation.created_at.isoformat(),
                'context': context
            }
            
            # Merge with template
            payload.update(self.payload_template)
            
            # Send webhook
            response = requests.request(
                method=self.method,
                url=self.webhook_url,
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            return {
                'success': response.status_code in [200, 201, 202],
                'status_code': response.status_code,
                'response': response.text[:500]  # Limit response size
            }
            
        except Exception as e:
            logger.error(f"Webhook escalation error: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }


class ScriptEscalationAction(EscalationAction):
    """Script execution escalation action"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.script_path = config.get('script_path')
        self.script_args = config.get('script_args', [])
        self.timeout = config.get('timeout', 60)
        
    async def execute(self, escalation: 'Escalation', context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute script escalation"""
        try:
            import os
            import subprocess

            # Running a script named in escalation configuration is remote-code-execution by
            # configuration, so it is disabled unless the project allow-lists directories:
            #   ESCALATION_SCRIPT_ALLOWED_DIRS = ['/opt/alerts/scripts']
            allowed_dirs = [os.path.realpath(d) for d in getattr(settings, 'ESCALATION_SCRIPT_ALLOWED_DIRS', []) or []]
            script = os.path.realpath(self.script_path) if self.script_path else ''
            if not allowed_dirs or not script or not os.path.isfile(script) or not any(
                    os.path.commonpath([script, d]) == d for d in allowed_dirs):
                logger.warning("Script escalation refused: path not inside ESCALATION_SCRIPT_ALLOWED_DIRS")
                return {'success': False, 'error': 'Script not permitted'}
            
            # Prepare script arguments
            args = [script]
            args.extend(self.script_args)
            
            # Add escalation context
            args.extend([
                '--escalation-id', str(escalation.id),
                '--alert-id', str(escalation.alert_id),
                '--level', escalation.current_level.value
            ])
            
            # Execute script
            result = subprocess.run(
                args,  # nosec B603 - script path restricted to ESCALATION_SCRIPT_ALLOWED_DIRS, no shell
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            return {
                'success': result.returncode == 0,
                'return_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f'Script execution timed out after {self.timeout} seconds'
            }
        except Exception as e:
            logger.error(f"Script escalation error: {e}")
            return {
                'success': False,
                'error': 'Operation failed'
            }


class Escalation:
    """Represents an escalation instance"""
    
    def __init__(self, alert_id: int, alert_type: str, rule: EscalationRule):
        self.id = str(uuid.uuid4())
        self.alert_id = alert_id
        self.alert_type = alert_type
        self.rule = rule
        self.current_level = EscalationLevel.LEVEL_1
        self.status = EscalationStatus.PENDING
        self.created_at = timezone.now()
        self.updated_at = timezone.now()
        self.escalation_history = []
        self.timeout_minutes = 30  # Default timeout for each level
        self.max_level = EscalationLevel.LEVEL_5
        
    def can_escalate(self) -> bool:
        """Check if escalation can proceed to next level"""
        return self.current_level != self.max_level and self.status in [EscalationStatus.PENDING, EscalationStatus.IN_PROGRESS]
    
    def get_next_level(self) -> Optional[EscalationLevel]:
        """Get next escalation level"""
        level_order = [
            EscalationLevel.LEVEL_1,
            EscalationLevel.LEVEL_2,
            EscalationLevel.LEVEL_3,
            EscalationLevel.LEVEL_4,
            EscalationLevel.LEVEL_5
        ]
        
        current_index = level_order.index(self.current_level)
        next_index = current_index + 1
        
        if next_index < len(level_order):
            return level_order[next_index]
        
        return None
    
    def escalate(self, actions: List[Dict[str, Any]], context: Dict[str, Any] = None):
        """Escalate to next level"""
        if not self.can_escalate():
            return False
        
        next_level = self.get_next_level()
        if not next_level:
            return False
        
        # Update escalation
        self.current_level = next_level
        self.status = EscalationStatus.ESCALATED
        self.updated_at = timezone.now()
        
        # Add to history
        self.escalation_history.append({
            'level': next_level.value,
            'timestamp': timezone.now().isoformat(),
            'actions': actions,
            'context': context or {}
        })
        
        return True
    
    def resolve(self):
        """Mark escalation as resolved"""
        self.status = EscalationStatus.RESOLVED
        self.updated_at = timezone.now()
        
        # Add to history
        self.escalation_history.append({
            'level': self.current_level.value,
            'timestamp': timezone.now().isoformat(),
            'action': 'resolved'
        })
    
    def cancel(self):
        """Cancel escalation"""
        self.status = EscalationStatus.CANCELLED
        self.updated_at = timezone.now()
        
        # Add to history
        self.escalation_history.append({
            'level': self.current_level.value,
            'timestamp': timezone.now().isoformat(),
            'action': 'cancelled'
        })
    
    def is_timeout(self) -> bool:
        """Check if escalation has timed out"""
        if self.status != EscalationStatus.IN_PROGRESS:
            return False
        
        timeout_time = self.updated_at + timezone.timedelta(minutes=self.timeout_minutes)
        return timezone.now() > timeout_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'alert_id': self.alert_id,
            'alert_type': self.alert_type,
            'rule_name': self.rule.name,
            'current_level': self.current_level.value,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'escalation_history': self.escalation_history,
            'timeout_minutes': self.timeout_minutes,
            'can_escalate': self.can_escalate(),
            'is_timeout': self.is_timeout()
        }


class EscalationManager:
    """Main escalation management system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.rules = {}
        self.actions = {}
        self.escalations = {}
        self.enabled = config.get('enabled', True)
        self.default_timeout = config.get('default_timeout', 30)
        self.max_concurrent_escalations = config.get('max_concurrent_escalations', 100)
        
        # Initialize rules
        self._initialize_rules()
        
        # Initialize actions
        self._initialize_actions()
        
        # Start escalation processor
        self.processor_running = False
        
    def _initialize_rules(self):
        """Initialize escalation rules from configuration"""
        rule_configs = self.config.get('rules', {})
        
        for rule_name, rule_config in rule_configs.items():
            rule = EscalationRule(
                name=rule_name,
                alert_type=rule_config.get('alert_type'),
                conditions=rule_config.get('conditions', {}),
                escalation_levels=rule_config.get('escalation_levels', []),
                enabled=rule_config.get('enabled', True)
            )
            
            self.rules[rule_name] = rule
            logger.info(f"Initialized escalation rule: {rule_name}")
    
    def _initialize_actions(self):
        """Initialize escalation actions from configuration"""
        action_configs = self.config.get('actions', {})
        
        for action_name, action_config in action_configs.items():
            action_type = action_config.get('type', 'notification')
            
            if action_type == 'notification':
                action = NotificationEscalationAction(action_config)
            elif action_type == 'email':
                action = EmailEscalationAction(action_config)
            elif action_type == 'webhook':
                action = WebhookEscalationAction(action_config)
            elif action_type == 'script':
                action = ScriptEscalationAction(action_config)
            else:
                logger.error(f"Unknown action type: {action_type}")
                continue
            
            self.actions[action_name] = action
            logger.info(f"Initialized escalation action: {action_name}")
    
    def create_escalation(self, alert_id: int, alert_type: str, alert_data: Dict[str, Any]) -> Optional[Escalation]:
        """Create escalation for alert"""
        # Find matching rule
        matching_rule = None
        for rule in self.rules.values():
            if rule.matches_alert(alert_data):
                matching_rule = rule
                break
        
        if not matching_rule:
            logger.info(f"No escalation rule found for alert {alert_id} of type {alert_type}")
            return None
        
        # Check escalation limit
        if len(self.escalations) >= self.max_concurrent_escalations:
            logger.warning(f"Maximum concurrent escalations reached: {self.max_concurrent_escalations}")
            return None
        
        # Create escalation
        escalation = Escalation(alert_id, alert_type, matching_rule)
        escalation.timeout_minutes = matching_rule.escalation_levels[0].get('timeout_minutes', self.default_timeout)
        
        # Store escalation
        self.escalations[escalation.id] = escalation
        
        logger.info(f"Created escalation {escalation.id} for alert {alert_id}")
        
        # Start escalation
        asyncio.create_task(self.process_escalation(escalation, alert_data))
        
        return escalation
    
    async def process_escalation(self, escalation: Escalation, alert_data: Dict[str, Any]):
        """Process escalation through levels"""
        if not self.enabled:
            return
        
        try:
            escalation.status = EscalationStatus.IN_PROGRESS
            
            # Get current level configuration
            level_index = [
                EscalationLevel.LEVEL_1,
                EscalationLevel.LEVEL_2,
                EscalationLevel.LEVEL_3,
                EscalationLevel.LEVEL_4,
                EscalationLevel.LEVEL_5
            ].index(escalation.current_level)
            
            level_config = escalation.rule.escalation_levels[level_index]
            
            # Execute actions for current level
            action_names = level_config.get('actions', [])
            action_results = []
            
            for action_name in action_names:
                action = self.actions.get(action_name)
                if not action:
                    logger.error(f"Action {action_name} not found")
                    continue
                
                if not action.enabled:
                    continue
                
                try:
                    result = await action.execute(escalation, {'alert': alert_data})
                    action_results.append({
                        'action': action_name,
                        'result': result
                    })
                except Exception as e:
                    logger.error(f"Error executing action {action_name}: {e}")
                    action_results.append({
                        'action': action_name,
                        'result': {'success': False, 'error': str(e)}
                    })
            
            # Wait for timeout or manual resolution
            await self._wait_for_level_completion(escalation)
            
            # Check if escalation should continue
            if escalation.status == EscalationStatus.RESOLVED:
                logger.info(f"Escalation {escalation.id} resolved")
                return
            
            if escalation.status == EscalationStatus.CANCELLED:
                logger.info(f"Escalation {escalation.id} cancelled")
                return
            
            # Check timeout
            if escalation.is_timeout():
                escalation.status = EscalationStatus.TIMEOUT
                logger.warning(f"Escalation {escalation.id} timed out")
                return
            
            # Escalate to next level
            if escalation.can_escalate():
                escalation.escalate(action_results, {'alert': alert_data})
                
                # Process next level
                await self.process_escalation(escalation, alert_data)
            
        except Exception as e:
            logger.error(f"Error processing escalation {escalation.id}: {e}")
            escalation.status = EscalationStatus.FAILED if hasattr(EscalationStatus, 'FAILED') else EscalationStatus.CANCELLED
    
    async def _wait_for_level_completion(self, escalation: Escalation):
        """Wait for escalation level completion"""
        timeout_time = escalation.updated_at + timezone.timedelta(minutes=escalation.timeout_minutes)
        
        while timezone.now() < timeout_time:
            if escalation.status in [EscalationStatus.RESOLVED, EscalationStatus.CANCELLED]:
                return
            
            await asyncio.sleep(10)  # Check every 10 seconds
    
    def get_escalation(self, escalation_id: str) -> Optional[Escalation]:
        """Get escalation by ID"""
        return self.escalations.get(escalation_id)
    
    def get_escalations_by_alert(self, alert_id: int) -> List[Escalation]:
        """Get escalations for specific alert"""
        return [e for e in self.escalations.values() if e.alert_id == alert_id]
    
    def resolve_escalation(self, escalation_id: str) -> bool:
        """Resolve escalation"""
        escalation = self.escalations.get(escalation_id)
        if escalation:
            escalation.resolve()
            logger.info(f"Resolved escalation {escalation_id}")
            return True
        return False
    
    def cancel_escalation(self, escalation_id: str) -> bool:
        """Cancel escalation"""
        escalation = self.escalations.get(escalation_id)
        if escalation:
            escalation.cancel()
            logger.info(f"Cancelled escalation {escalation_id}")
            return True
        return False
    
    def get_manager_status(self) -> Dict[str, Any]:
        """Get escalation manager status"""
        active_escalations = [e for e in self.escalations.values() if e.status in [EscalationStatus.PENDING, EscalationStatus.IN_PROGRESS]]
        
        return {
            'manager_enabled': self.enabled,
            'total_rules': len(self.rules),
            'enabled_rules': len([r for r in self.rules.values() if r.enabled]),
            'total_actions': len(self.actions),
            'enabled_actions': len([a for a in self.actions.values() if a.enabled]),
            'total_escalations': len(self.escalations),
            'active_escalations': len(active_escalations),
            'max_concurrent_escalations': self.max_concurrent_escalations,
            'default_timeout': self.default_timeout,
            'rules': {
                name: {
                    'name': rule.name,
                    'alert_type': rule.alert_type,
                    'enabled': rule.enabled,
                    'levels': len(rule.escalation_levels)
                }
                for name, rule in self.rules.items()
            },
            'actions': {
                name: action.get_action_info()
                for name, action in self.actions.items()
            },
            'timestamp': timezone.now().isoformat()
        }
    
    def add_rule(self, rule: EscalationRule):
        """Add escalation rule"""
        self.rules[rule.name] = rule
        logger.info(f"Added escalation rule: {rule.name}")
    
    def remove_rule(self, rule_name: str):
        """Remove escalation rule"""
        if rule_name in self.rules:
            del self.rules[rule_name]
            logger.info(f"Removed escalation rule: {rule_name}")
    
    def add_action(self, action_name: str, action: EscalationAction):
        """Add escalation action"""
        self.actions[action_name] = action
        logger.info(f"Added escalation action: {action_name}")
    
    def remove_action(self, action_name: str):
        """Remove escalation action"""
        if action_name in self.actions:
            del self.actions[action_name]
            logger.info(f"Removed escalation action: {action_name}")


# Global escalation manager
escalation_manager = None


def get_escalation_manager() -> Optional[EscalationManager]:
    """Get the global escalation manager"""
    return escalation_manager


def initialize_escalation_system():
    """Initialize escalation system from settings"""
    from django.conf import settings
    
    global escalation_manager
    
    config = getattr(settings, 'ESCALATION_CONFIG', {
        'enabled': True,
        'default_timeout': 30,
        'max_concurrent_escalations': 100,
        'rules': {
            'high_severity_alerts': {
                'alert_type': 'server_error',
                'conditions': {
                    'severity': ['high', 'critical'],
                    'threshold_value': 5
                },
                'escalation_levels': [
                    {
                        'timeout_minutes': 5,
                        'actions': ['notification']
                    },
                    {
                        'timeout_minutes': 10,
                        'actions': ['email', 'webhook']
                    },
                    {
                        'timeout_minutes': 15,
                        'actions': ['email', 'webhook', 'script']
                    }
                ]
            }
        },
        'actions': {
            'notification': {
                'type': 'notification',
                'channels': ['email', 'sms'],
                'recipients': ['admin@example.com'],
                'subject_template': 'ESCALATION: {alert_type} - Level {level}'
            },
            'email': {
                'type': 'email',
                'recipients': ['manager@example.com'],
                'template_name': 'escalation_email'
            }
        }
    })
    
    try:
        escalation_manager = EscalationManager(config)
        logger.info("Escalation system initialized")
    except Exception as e:
        logger.error(f"Error initializing escalation system: {e}")


# Initialize on module import
try:
    initialize_escalation_system()
except Exception as e:
    logger.error(f"Error initializing escalation system: {e}")
