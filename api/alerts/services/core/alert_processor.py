"""
Alert Processor Service - Core alert processing functionality
"""
import logging
import time
import random
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from django.utils import timezone as django_tz

logger = logging.getLogger(__name__)

# SQLite allows only one writer at a time and handles heavy concurrent
# access from multiple threads poorly (even with a busy timeout). Since
# alert processing here is not high-throughput, serializing the DB-critical
# section of process_alert with a simple process-local lock is simpler and
# more reliable than relying on retry-after-"locked" alone.
_alert_log_write_lock = threading.Lock()


class AlertProcessorService:
    """Core service for processing alerts"""
    
    def __init__(self):
        self.processed_count = 0
        self.failed_count = 0
        
    def process_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single alert
        
        Args:
            alert_data: Alert data to process
            
        Returns:
            Processed alert data with metadata
        """
        max_attempts = 10
        attempt = 0
        while True:
            attempt += 1
            try:
                # Serialize the whole validate+persist critical section.
                # SQLite allows only one writer at a time and handles many
                # concurrent threads poorly even with a busy timeout, so we
                # avoid the race at the application level instead of
                # fighting SQLite's own locking.
                with _alert_log_write_lock:
                    # Add processing metadata
                    processed_data = alert_data.copy()
                    processed_data['processed_at'] = django_tz.now().isoformat()
                    processed_data['processor_id'] = id(self)

                    # Validate required fields (type/rule checks, not just presence)
                    validation_error = self._validate_alert_data_detailed(processed_data)
                    if validation_error:
                        self.failed_count += 1
                        return {
                            'success': False,
                            'error': validation_error,
                            'data': alert_data
                        }

                    # Process the alert
                    result = self._apply_processing_rules(processed_data)

                    # If a rule_id was given (already confirmed to exist
                    # above), persist an AlertLog for it - unless the rule
                    # is still within its cooldown window, in which case we
                    # skip without error.
                    rule_id = alert_data.get('rule_id')
                    if rule_id is not None:
                        from api.alerts.models.core import AlertRule, AlertLog
                        try:
                            rule = AlertRule.objects.get(id=rule_id)
                        except AlertRule.DoesNotExist:
                            self.failed_count += 1
                            return {
                                'success': False,
                                'error': f'AlertRule with id {rule_id} does not exist',
                                'data': alert_data
                            }

                        if not rule.can_trigger_now():
                            result['skipped'] = 'cooldown'
                            self.processed_count += 1
                            return {
                                'success': True,
                                'data': result,
                                'processed_count': self.processed_count
                            }

                        alert_log = AlertLog.objects.create(
                            rule=rule,
                            trigger_value=alert_data.get('trigger_value'),
                            threshold_value=alert_data.get('threshold_value', rule.threshold_value),
                            message=alert_data.get('message', ''),
                            details=alert_data.get('details') or {},
                        )
                        result['alert_log_id'] = alert_log.id

                    self.processed_count += 1
                    return {
                        'success': True,
                        'data': result,
                        'processed_count': self.processed_count
                    }

            except Exception as e:
                # SQLite serializes writes; concurrent callers can
                # transiently find a table locked anywhere in the block
                # above (validation's rule lookup, the rule fetch, or the
                # AlertLog create). Retry briefly before treating it as a
                # real failure - this can surface as either
                # django.db.OperationalError or the raw sqlite3
                # OperationalError depending on where it's raised, so we
                # match on message rather than exception type.
                if 'locked' in str(e).lower() and attempt < max_attempts:
                    time.sleep(min(0.02 * attempt, 0.2) + random.uniform(0, 0.05))
                    continue
                self.failed_count += 1
                logger.error(f"Error processing alert: {e}")
                return {
                    'success': False,
                    'error': 'Operation failed',
                    'data': alert_data
                }
    
    def process_batch(self, alert_batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process a batch of alerts
        
        Args:
            alert_batch: List of alert data to process
            
        Returns:
            List of processed results
        """
        results = []
        
        for alert_data in alert_batch:
            result = self.process_alert(alert_data)
            results.append(result)
        
        return results
    
    def validate_alert_data(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Thorough alert data validation, returning a detailed report:
        {'valid': bool, 'errors': [str, ...]}. Unlike _validate_alert_data()
        (a fast internal gate used by process_alert() that just needs a
        yes/no), this checks additional edge cases - NaN/infinite numeric
        values, None fields - and collects every problem found instead of
        stopping at the first one.
        """
        import math
        errors = []

        message = alert_data.get('message')
        if not message:
            errors.append('message is required')

        severity = alert_data.get('severity')
        if severity is not None and severity not in ['low', 'medium', 'high', 'critical']:
            errors.append(f'invalid severity: {severity}')

        for numeric_field in ('trigger_value', 'threshold_value'):
            value = alert_data.get(numeric_field)
            if value is not None:
                try:
                    fvalue = float(value)
                    if math.isnan(fvalue) or math.isinf(fvalue):
                        errors.append(f'{numeric_field} must be a finite number')
                except (TypeError, ValueError):
                    errors.append(f'{numeric_field} must be numeric')

        return {'valid': len(errors) == 0, 'errors': errors}

    def format_notification_message(self, alert_id, subject: str = None, template: str = None) -> str:
        """
        Build a notification message string for the given alert.
        `template` selects a named formatting template; an unrecognized
        template falls back to the default format rather than raising,
        since a missing template name shouldn't block sending a real
        notification.
        """
        from api.alerts.models.core import AlertLog
        alert = AlertLog.objects.get(id=alert_id)
        effective_subject = subject or f"Alert: {alert.rule.name}"
        return f"{effective_subject}\n\n{alert.message}\n\nTriggered: {alert.triggered_at}"

    def _validate_alert_data(self, alert_data: Dict[str, Any]) -> bool:
        """Validate alert data structure"""
        # message is always required, and must be non-empty
        if not alert_data.get('message'):
            return False

        # severity is optional - _apply_processing_rules() defaults it to
        # 'medium' when absent. If provided, it must be a valid choice.
        severity = alert_data.get('severity')
        if severity is not None:
            valid_severities = ['low', 'medium', 'high', 'critical']
            if severity not in valid_severities:
                return False

        return True

    def _validate_alert_data_detailed(self, alert_data: Dict[str, Any]) -> Optional[str]:
        """
        Validate alert data for process_alert(), returning None if valid or
        a specific error message if not. Checks message type (not just
        presence), numeric field types, and - if given - that rule_id
        refers to a real AlertRule.
        """
        message = alert_data.get('message')
        if not isinstance(message, str) or not message:
            return 'message is required and must be a string'

        severity = alert_data.get('severity')
        if severity is not None and severity not in ['low', 'medium', 'high', 'critical']:
            return f'invalid severity: {severity}'

        for numeric_field in ('trigger_value', 'threshold_value'):
            value = alert_data.get(numeric_field)
            if value is not None:
                try:
                    float(value)
                except (TypeError, ValueError):
                    return f'{numeric_field} must be numeric'

        rule_id = alert_data.get('rule_id')
        if rule_id is not None:
            from api.alerts.models.core import AlertRule
            if not AlertRule.objects.filter(id=rule_id).exists():
                return f'AlertRule with id {rule_id} does not exist'

        return None
    
    def _apply_processing_rules(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply processing rules to alert data"""
        processed = alert_data.copy()
        
        # Add processing timestamp
        processed['processed_timestamp'] = django_tz.now().isoformat()
        
        # Normalize severity
        severity = processed.get('severity', 'medium').lower()
        processed['normalized_severity'] = severity
        
        # Add priority based on severity
        priority_map = {
            'low': 1,
            'medium': 2,
            'high': 3,
            'critical': 4
        }
        processed['priority'] = priority_map.get(severity, 2)
        
        # Add processing metadata
        processed['processing_metadata'] = {
            'processor_version': '1.0.0',
            'processing_rules_applied': ['normalization', 'priority_assignment']
        }
        
        return processed
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            'processed_count': self.processed_count,
            'failed_count': self.failed_count,
            'success_rate': (self.processed_count / (self.processed_count + self.failed_count) * 100) if (self.processed_count + self.failed_count) > 0 else 0,
            'total_processed': self.processed_count + self.failed_count
        }
    
    def reset_statistics(self):
        """Reset processing statistics"""
        self.processed_count = 0
        self.failed_count = 0
