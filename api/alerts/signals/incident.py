"""
Incident Signals
"""
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
import logging

from ..models.incident import (
    Incident, IncidentTimeline, IncidentResponder, IncidentPostMortem, OnCallSchedule
)

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Incident)
def incident_pre_save(sender, instance, **kwargs):
    """Signal handler before saving Incident"""
    try:
        if not instance.detected_at:
            instance.detected_at = timezone.now()
        if not instance.severity:
            instance.severity = 'medium'
        if not instance.impact:
            instance.impact = 'minor'
        if not instance.urgency:
            instance.urgency = 'medium'
        if not instance.status:
            instance.status = 'open'
        valid_severities = [c[0] for c in Incident._meta.get_field('severity').choices]
        if instance.severity not in valid_severities:
            logger.warning(f"Invalid severity '{instance.severity}' for Incident {instance.id}")
        valid_impacts = [c[0] for c in Incident._meta.get_field('impact').choices]
        if instance.impact not in valid_impacts:
            logger.warning(f"Invalid impact '{instance.impact}' for Incident {instance.id}")
        valid_urgencies = [c[0] for c in Incident._meta.get_field('urgency').choices]
        if instance.urgency not in valid_urgencies:
            logger.warning(f"Invalid urgency '{instance.urgency}' for Incident {instance.id}")
        valid_statuses = [c[0] for c in Incident._meta.get_field('status').choices]
        if instance.status not in valid_statuses:
            logger.warning(f"Invalid status '{instance.status}' for Incident {instance.id}")
    except Exception as e:
        logger.error(f"Error in incident_pre_save: {e}")


@receiver(post_save, sender=Incident)
def incident_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving Incident"""
    try:
        if created:
            logger.info(f"Created new Incident: {instance.title} ({instance.severity} severity)")
            IncidentTimeline.objects.create(
                incident=instance,
                event_type='detected',
                title='Incident Detected',
                description=f'Incident "{instance.title}" was detected',
                participants=[instance.assigned_to.id] if instance.assigned_to else []
            )
            from ..tasks.incident import check_incident_escalations
            check_incident_escalations.delay()

            # FIXED: notify on-call for all new incidents (was only critical before)
            from ..tasks.oncall_notify_tasks import notify_oncall_new_incident
            notify_oncall_new_incident.delay(instance.pk)

            if instance.severity == 'critical':
                from ..tasks.incident import notify_on_call_changes
                notify_on_call_changes.delay()
        else:
            logger.debug(f"Updated Incident: {instance.title}")
            if hasattr(instance, '_original_status') and instance._original_status != instance.status:
                IncidentTimeline.objects.create(
                    incident=instance,
                    event_type='status_change',
                    title=f'Status Changed to {instance.status.title()}',
                    description=f'Incident status changed from {instance._original_status} to {instance.status}',
                    participants=[instance.assigned_to.id] if instance.assigned_to else []
                )
            if instance.status in ['investigating', 'identified']:
                from ..tasks.incident import check_incident_escalations
                check_incident_escalations.delay()

            # FIXED: when incident resolves, recalculate SLA and MTTR
            if hasattr(instance, '_original_status') and instance.status == 'resolved' and instance._original_status != 'resolved':
                from ..tasks.reporting import check_sla_breaches, calculate_mttr_metrics
                check_sla_breaches.delay()
                calculate_mttr_metrics.delay()
                trigger_incident_metrics_update(instance)
                # Audit log resolution
                try:
                    from api.alerts.integration import get_audit_logger
                    from api.alerts.integration.integ_audit_logs import AuditEventType, AuditSeverity
                    al = get_audit_logger()
                    if al:
                        al.log_event(
                            event_type=AuditEventType.INCIDENT_RESOLVED,
                            severity=AuditSeverity.INFO,
                            description=f"Incident resolved: {instance.title}",
                            details={'incident_id': instance.pk, 'severity': instance.severity}
                        )
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Error in incident_post_save: {e}")


@receiver(pre_save, sender=IncidentTimeline)
def incident_timeline_pre_save(sender, instance, **kwargs):
    """Signal handler before saving IncidentTimeline"""
    try:
        if not instance.timestamp:
            instance.timestamp = timezone.now()
        if not instance.event_type:
            instance.event_type = 'update'
        valid_types = [c[0] for c in IncidentTimeline._meta.get_field('event_type').choices]
        if instance.event_type not in valid_types:
            logger.warning(f"Invalid event type '{instance.event_type}' for IncidentTimeline {instance.id}")
    except Exception as e:
        logger.error(f"Error in incident_timeline_pre_save: {e}")


@receiver(post_save, sender=IncidentTimeline)
def incident_timeline_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving IncidentTimeline"""
    try:
        if created:
            logger.info(f"Created IncidentTimeline: {instance.event_type} for incident {instance.incident.title}")
            from ..tasks.incident import update_incident_metrics
            update_incident_metrics.delay()
        else:
            logger.debug(f"Updated IncidentTimeline: {instance.id}")
    except Exception as e:
        logger.error(f"Error in incident_timeline_post_save: {e}")


@receiver(pre_save, sender=IncidentResponder)
def incident_responder_pre_save(sender, instance, **kwargs):
    """Signal handler before saving IncidentResponder"""
    try:
        if not instance.assigned_at:
            instance.assigned_at = timezone.now()
        if not instance.role:
            instance.role = 'responder'
        if not instance.status:
            instance.status = 'assigned'
        if not instance.contact_method:
            instance.contact_method = 'email'
        valid_roles = [c[0] for c in IncidentResponder._meta.get_field('role').choices]
        if instance.role not in valid_roles:
            logger.warning(f"Invalid role '{instance.role}' for IncidentResponder {instance.id}")
        valid_statuses = [c[0] for c in IncidentResponder._meta.get_field('status').choices]
        if instance.status not in valid_statuses:
            logger.warning(f"Invalid status '{instance.status}' for IncidentResponder {instance.id}")
        valid_methods = [c[0] for c in IncidentResponder._meta.get_field('contact_method').choices]
        if instance.contact_method not in valid_methods:
            logger.warning(f"Invalid contact method '{instance.contact_method}' for IncidentResponder {instance.id}")
    except Exception as e:
        logger.error(f"Error in incident_responder_pre_save: {e}")


@receiver(post_save, sender=IncidentResponder)
def incident_responder_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving IncidentResponder"""
    try:
        if created:
            logger.info(f"Created IncidentResponder: {instance.role} {instance.user.get_full_name()} for incident {instance.incident.title}")
            IncidentTimeline.objects.create(
                incident=instance.incident,
                event_type='responder_assigned',
                title=f'{instance.role.title()} Assigned',
                description=f'{instance.role.title()} {instance.user.get_full_name()} assigned to incident',
                participants=[instance.user.id]
            )
            responder_assigned.send(sender=IncidentResponder, instance=instance)
            responder_created.send(sender=IncidentResponder, instance=instance)
        else:
            logger.debug(f"Updated IncidentResponder: {instance.id}")
            responder_updated.send(sender=IncidentResponder, instance=instance)
            if hasattr(instance, '_original_status') and instance._original_status != instance.status:
                IncidentTimeline.objects.create(
                    incident=instance.incident,
                    event_type='responder_status_change',
                    title='Responder Status Changed',
                    description=f'{instance.user.get_full_name()} status changed from {instance._original_status} to {instance.status}',
                    participants=[instance.user.id]
                )
    except Exception as e:
        logger.error(f"Error in incident_responder_post_save: {e}")


@receiver(pre_save, sender=IncidentPostMortem)
def incident_post_mortem_pre_save(sender, instance, **kwargs):
    """Signal handler before saving IncidentPostMortem"""
    try:
        if not instance.status:
            instance.status = 'draft'
        # Only default internal_only for new instances where it is None
        if instance.pk is None and instance.internal_only is None:
            instance.internal_only = True
        valid_statuses = [c[0] for c in IncidentPostMortem._meta.get_field('status').choices]
        if instance.status not in valid_statuses:
            logger.warning(f"Invalid status '{instance.status}' for IncidentPostMortem {instance.id}")
    except Exception as e:
        logger.error(f"Error in incident_post_mortem_pre_save: {e}")


@receiver(post_save, sender=IncidentPostMortem)
def incident_post_mortem_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving IncidentPostMortem"""
    try:
        if created:
            logger.info(f"Created IncidentPostMortem: {instance.title} for incident {instance.incident.title}")
            IncidentTimeline.objects.create(
                incident=instance.incident,
                event_type='post_mortem_started',
                title='Post-Mortem Started',
                description='Post-mortem analysis started for incident',
                participants=[instance.created_by.id] if instance.created_by else []
            )
            post_mortem_created.send(sender=IncidentPostMortem, instance=instance)
            # FIXED: schedule deadline reminder task when postmortem is created
            from ..tasks.incident import check_post_mortem_deadlines
            check_post_mortem_deadlines.apply_async(countdown=3600)  # check in 1 hour
        else:
            logger.debug(f"Updated IncidentPostMortem: {instance.title}")
            post_mortem_updated.send(sender=IncidentPostMortem, instance=instance)
            if hasattr(instance, '_original_status') and instance._original_status != instance.status:
                IncidentTimeline.objects.create(
                    incident=instance.incident,
                    event_type='post_mortem_status_change',
                    title='Post-Mortem Status Changed',
                    description=f'Post-mortem status changed from {instance._original_status} to {instance.status}',
                    participants=[instance.reviewed_by.id] if instance.reviewed_by else []
                )
            from ..tasks.incident import check_post_mortem_deadlines
            check_post_mortem_deadlines.delay()
    except Exception as e:
        logger.error(f"Error in incident_post_mortem_post_save: {e}")


@receiver(pre_save, sender=OnCallSchedule)
def oncall_schedule_pre_save(sender, instance, **kwargs):
    """Signal handler before saving OnCallSchedule"""
    try:
        if not instance.schedule_type:
            instance.schedule_type = 'rotation'
        if not instance.rotation_period_days:
            instance.rotation_period_days = 7
        if not instance.timezone:
            instance.timezone = 'UTC'
        if not instance.start_time:
            instance.start_time = '09:00'
        if not instance.end_time:
            instance.end_time = '17:00'
        if not instance.days_of_week:
            instance.days_of_week = [0, 1, 2, 3, 4]
        if not instance.is_active:
            instance.is_active = True
        valid_types = [c[0] for c in OnCallSchedule._meta.get_field('schedule_type').choices]
        if instance.schedule_type not in valid_types:
            logger.warning(f"Invalid schedule type '{instance.schedule_type}' for OnCallSchedule {instance.id}")
    except Exception as e:
        logger.error(f"Error in oncall_schedule_pre_save: {e}")


@receiver(post_save, sender=OnCallSchedule)
def oncall_schedule_post_save(sender, instance, created, **kwargs):
    """Signal handler after saving OnCallSchedule"""
    try:
        if created:
            logger.info(f"Created new OnCallSchedule: {instance.name} ({instance.schedule_type})")
            from ..tasks.incident import update_on_call_schedules
            update_on_call_schedules.delay()
            from api.alerts.signals.incident import oncall_schedule_created
            oncall_schedule_created.send(sender=sender, instance=instance)
        else:
            logger.debug(f"Updated OnCallSchedule: {instance.name}")
            from ..tasks.incident import notify_on_call_changes
            notify_on_call_changes.delay()
            from api.alerts.signals.incident import oncall_updated, oncall_rotation_changed
            oncall_updated.send(sender=sender, instance=instance)
            # FIXED: notify rotation change via dedicated oncall task
            from ..tasks.oncall_notify_tasks import notify_oncall_rotation_change
            notify_oncall_rotation_change.delay(instance.pk)
            oncall_rotation_changed.send(sender=sender, instance=instance)
    except Exception as e:
        logger.error(f"Error in oncall_schedule_post_save: {e}")


# ── Helper functions ─────────────────────────────────────────────────────────

def trigger_incident_escalation(incident, escalation_level=None):
    """Trigger incident escalation — creates timeline event and runs escalation task"""
    try:
        logger.info(f"Triggering escalation for incident {incident.title}")
        IncidentTimeline.objects.create(
            incident=incident,
            event_type='escalated',
            title='Incident Escalated',
            description=f'Incident escalated to level {escalation_level or incident.escalation_level}',
            participants=[incident.assigned_to.id] if incident.assigned_to else []
        )
        if escalation_level:
            incident.escalation_level = escalation_level
            incident.save(update_fields=['escalation_level'])
        from ..tasks.incident import check_incident_escalations
        check_incident_escalations.delay()
    except Exception as e:
        logger.error(f"Error in trigger_incident_escalation: {e}")


def trigger_incident_notification(incident, notification_type, message=None):
    """Create and dispatch an incident notification"""
    try:
        logger.info(f"Triggering {notification_type} notification for incident {incident.title}")
        from ..models.core import Notification
        notification = Notification.objects.create(
            notification_type='email',
            recipient="incident_team",
            subject=f"Incident {notification_type.title()}: {incident.title}",
            message=message or f"Incident {incident.title} has been {notification_type}",
            status='pending'
        )
        from ..tasks.notification import send_pending_notifications
        send_pending_notifications.delay()
        return notification
    except Exception as e:
        logger.error(f"Error in trigger_incident_notification: {e}")
        return None


def trigger_incident_metrics_update(incident):
    """Update incident metrics and regenerate dashboard data"""
    try:
        logger.info(f"Updating metrics for incident {incident.title}")
        from ..tasks.incident import update_incident_metrics
        update_incident_metrics.delay()
        from ..tasks.incident import generate_incident_dashboard_data
        generate_incident_dashboard_data.delay()
    except Exception as e:
        logger.error(f"Error in trigger_incident_metrics_update: {e}")


def trigger_post_mortem_reminder(incident):
    """Send post-mortem required notification to incident manager"""
    try:
        logger.info(f"Triggering post-mortem reminder for incident {incident.title}")
        from ..models.core import Notification
        notification = Notification.objects.create(
            notification_type='email',
            recipient="incident_manager",
            subject=f"Post-Mortem Required: {incident.title}",
            message=f"Post-mortem analysis is required for incident {incident.title} (Severity: {incident.severity})",
            status='pending'
        )
        from ..tasks.notification import send_pending_notifications
        send_pending_notifications.delay()
        return notification
    except Exception as e:
        logger.error(f"Error in trigger_post_mortem_reminder: {e}")
        return None


def trigger_on_call_rotation_change(schedule):
    """Notify on-call team of rotation change"""
    try:
        logger.info(f"Triggering on-call rotation change for schedule {schedule.name}")
        current_on_call = schedule.get_current_on_call()
        upcoming_schedule = schedule.get_upcoming_schedule(7)
        if current_on_call and upcoming_schedule:
            from ..models.core import Notification
            notification = Notification.objects.create(
                notification_type='email',
                recipient="on_call_team",
                subject=f"On-Call Rotation Change: {schedule.name}",
                message=(
                    f"On-call rotation changing from {current_on_call.get_full_name()} "
                    f"to {upcoming_schedule[0]['user'].get_full_name() if upcoming_schedule else 'Unknown'}"
                ),
                status='pending'
            )
            from ..tasks.notification import send_pending_notifications
            send_pending_notifications.delay()
            return notification
    except Exception as e:
        logger.error(f"Error in trigger_on_call_rotation_change: {e}")
        return None


def trigger_incident_auto_resolution(incident):
    """Auto-resolve an incident and update metrics"""
    try:
        logger.info(f"Auto-resolving incident {incident.title}")
        IncidentTimeline.objects.create(
            incident=incident,
            event_type='auto_resolved',
            title='Auto-Resolved',
            description='Incident automatically resolved due to timeout or criteria',
            participants=[]
        )
        incident.resolve(None, "Auto-resolved: System timeout")
        from ..tasks.incident import update_incident_metrics
        update_incident_metrics.delay()
    except Exception as e:
        logger.error(f"Error in trigger_incident_auto_resolution: {e}")


def register_incident_signals():
    """Register all incident signals"""
    try:
        logger.info("Incident signals registered successfully")
    except Exception as e:
        logger.error(f"Error registering incident signals: {e}")


register_incident_signals()


from django.dispatch import Signal

incident_created          = Signal()
incident_updated          = Signal()
incident_acknowledged     = Signal()
incident_escalated        = Signal()
incident_resolved         = Signal()
incident_closed           = Signal()
timeline_created          = Signal()
responder_created         = Signal()
responder_updated         = Signal()
post_mortem_created       = Signal()
post_mortem_updated       = Signal()
oncall_schedule_created   = Signal()
oncall_updated            = Signal()
oncall_rotation_changed   = Signal()
post_mortem_required      = Signal()
auto_resolution_triggered = Signal()
timeline_event_added      = Signal()
responder_assigned        = Signal()

from django.db.models.signals import post_save as _post_save

try:
    from ..models.incident import Incident as _I, IncidentTimeline as _IT
    _post_save.connect(lambda sender, instance, created, **kw: (incident_created if created else incident_updated).send(sender=sender, instance=instance), sender=_I, weak=False)
    _post_save.connect(lambda sender, instance, created, **kw: timeline_created.send(sender=sender, instance=instance) if created else None, sender=_IT, weak=False)
except Exception:
    pass
