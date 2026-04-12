"""
DR Integration Signals — Auto-trigger DR actions on Django model events.
"""
import logging
from django.dispatch import receiver
from django.db.models.signals import post_save

logger = logging.getLogger(__name__)


# Auto-log security events from api/security/ to DR audit log
try:
    from api.security.models import SecurityLog

    @receiver(post_save, sender=SecurityLog)
    def sync_security_log_to_dr(sender, instance, created, **kwargs):
        if created:
            try:
                from dr_integration.services import DRAuditBridge
                bridge = DRAuditBridge()
                bridge.log_security_event(
                    event_type='security_log_created',
                    actor_id=str(instance.user_id or 'system'),
                    description=str(instance)[:200],
                )
            except Exception as e:
                logger.debug(f"DR security sync error: {e}")
except ImportError:
    pass


# Auto-log fraud events to DR audit
try:
    from api.fraud_detection.models import FraudRule

    @receiver(post_save, sender=FraudRule)
    def sync_fraud_rule_to_dr_audit(sender, instance, created, **kwargs):
        if created:
            try:
                from dr_integration.services import DRAuditBridge
                bridge = DRAuditBridge()
                bridge.log(
                    actor_id='system',
                    action='fraud_rule.created',
                    resource_type='fraud_rule',
                    resource_id=str(instance.id),
                    new_values={'rule_type': instance.rule_type if hasattr(instance, 'rule_type') else ''},
                )
            except Exception as e:
                logger.debug(f"DR fraud rule sync error: {e}")
except ImportError:
    pass


# Notify DR alert bridge when existing api/alerts/ fires
try:
    from api.alerts.models import AlertLog

    @receiver(post_save, sender=AlertLog)
    def forward_alert_to_dr(sender, instance, created, **kwargs):
        if not created:
            return
        try:
            from dr_integration.services import DRAlertBridge
            severity = str(getattr(instance, 'severity', 'info')).lower()
            if severity in ('critical', 'error', 'warning'):
                DRAlertBridge().fire_alert(
                    rule_name=str(getattr(instance, 'rule_name', 'api_alert')),
                    severity=severity,
                    message=str(getattr(instance, 'message', str(instance)))[:500],
                    metric=str(getattr(instance, 'metric_name', '')),
                    value=getattr(instance, 'metric_value', None),
                    threshold=getattr(instance, 'threshold', None),
                )
        except Exception as e:
            logger.debug(f"DR alert forward error: {e}")
except ImportError:
    pass
