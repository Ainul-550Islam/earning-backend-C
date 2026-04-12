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
        # Set default values if not provided
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
        
        # Validate severity
        valid_severities = ['low', 'medium', 'high', 'critical']
        if instance.severity not in valid_severities:
            logger.warning(f"Invalid severity '{instance.severity}' for Incident {instance.id}")
        
        # Validate impact
        valid_impacts = ['none', 'minimal', 'minor', 'major', 'severe', 'critical']
        if instance.impact not in valid_impacts:
            logger.warning(f"Invalid impact '{instance.impact}' for Incident {instance.id}")
        
        # Validate urgency
        valid_urgencies = ['low', 'medium', 'high', 'critical']
        if instance.urgency not in valid_urgencies:
            logger.warning(f"Invalid urgency '{instance.urgency}' for Incident {instance.id}")
        
        # Validate status
        valid_statuses = ['open', 'investigating', 'identified', 'monitoring', 'resolved', 'closed', 'false_positive']
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
            
            # Create initial timeline event
            IncidentTimeline.objects.create(
                incident=instance,
                event_type='detected',
                title='Incident Detected',
                description=f'Incident "{instance.title}" was detected',
                participants=[instance.assigned_to.id] if instance.assigned_to else []
            )
            
            # Trigger incident escalation check
            from ..tasks.incident import check_incident_escalations
            check_incident_escalations.delay()
            
            # Notify on-call personnel if critical
            if instance.severity == 'critical':
                from ..tasks.incident import notify_on_call_changes
                notify_on_call_changes.delay()
                
        else:
            logger.debug(f"Updated Incident: {instance.title}")
            
            # Create timeline event for status changes
            if hasattr(instance, '_original_status') and instance._original_status != instance.status:
                IncidentTimeline.objects.create(
                    incident=instance,
                    event_type='status_change',
                    title=f'Status Changed to {instance.status.title()}',
                    description=f'Incident status changed from {instance._original_status} to {instance.status}',
                    participants=[instance.assigned_to.id] if instance.assigned_to else []
                )
            
            # Trigger escalation if status changed to investigating or identified
            if instance.status in ['investigating', 'identified']:
                from ..tasks.incident import check_incident_escalations
                check_incident_escalations.delay()
            
    except Exception as e:
        logger.error(f"Error in incident_post_save: {e}")


@receiver(pre_save, sender=IncidentTimeline)
def incident_timeline_pre_save(sender, instance, **kwargs):
    """Signal handler before saving IncidentTimeline"""
    try:
        # Set default values if not provided
        if not instance.timestamp:
            instance.timestamp = timezone.now()
        
        if not instance.event_type:
            instance.event_type = 'update'
        
        # Validate event type
        valid_types = ['detected', 'acknowledged', 'investigating', 'identified', 'resolved', 'closed', 'escalated', 'status_change', 'update']
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
            
            # Update incident metrics
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
        # Set default values if not provided
        if not instance.assigned_at:
            instance.assigned_at = timezone.now()
        
        if not instance.role:
            instance.role = 'responder'
        
        if not instance.status:
            instance.status = 'assigned'
        
        if not instance.contact_method:
            instance.contact_method = 'email'
        
        # Validate role
        valid_roles = ['lead', 'responder', 'observer', 'escalation', 'manager']
        if instance.role not in valid_roles:
            logger.warning(f"Invalid role '{instance.role}' for IncidentResponder {instance.id}")
        
        # Validate status
        valid_statuses = ['assigned', 'active', 'away', 'completed', 'escalated']
        if instance.status not in valid_statuses:
            logger.warning(f"Invalid status '{instance.status}' for IncidentResponder {instance.id}")
        
        # Validate contact method
        valid_methods = ['email', 'sms', 'phone', 'slack', 'teams', 'webhook']
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
            
            # Create timeline event
            IncidentTimeline.objects.create(
                incident=instance.incident,
                event_type='responder_assigned',
                title=f'{instance.role.title()} Assigned',
                description=f'{instance.role.title()} {instance.user.get_full_name()} assigned to incident',
                participants=[instance.user.id]
            )
            
        else:
            logger.debug(f"Updated IncidentResponder: {instance.id}")
            
            # Create timeline event for status changes
            if hasattr(instance, '_original_status') and instance._original_status != instance.status:
                IncidentTimeline.objects.create(
                    incident=instance.incident,
                    event_type='responder_status_change',
                    title=f'Responder Status Changed',
                    description=f'{instance.user.get_full_name()} status changed from {instance._original_status} to {instance.status}',
                    participants=[instance.user.id]
                )
            
    except Exception as e:
        logger.error(f"Error in incident_responder_post_save: {e}")


@receiver(pre_save, sender=IncidentPostMortem)
def incident_post_mortem_pre_save(sender, instance, **kwargs):
    """Signal handler before saving IncidentPostMortem"""
    try:
        # Set default values if not provided
        if not instance.status:
            instance.status = 'draft'
        
        if not instance.internal_only:
            instance.internal_only = True
        
        # Validate status
        valid_statuses = ['draft', 'in_progress', 'submitted_for_review', 'approved', 'published', 'rejected']
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
            
            # Create timeline event
            IncidentTimeline.objects.create(
                incident=instance.incident,
                event_type='post_mortem_started',
                title='Post-Mortem Started',
                description=f'Post-mortem analysis started for incident',
                participants=[instance.created_by.id] if instance.created_by else []
            )
            
        else:
            logger.debug(f"Updated IncidentPostMortem: {instance.title}")
            
            # Create timeline event for status changes
            if hasattr(instance, '_original_status') and instance._original_status != instance.status:
                IncidentTimeline.objects.create(
                    incident=instance.incident,
                    event_type='post_mortem_status_change',
                    title=f'Post-Mortem Status Changed',
                    description=f'Post-mortem status changed from {instance._original_status} to {instance.status}',
                    participants=[instance.reviewed_by.id] if instance.reviewed_by else []
                )
            
            # Check post-mortem deadlines
            from ..tasks.incident import check_post_mortem_deadlines
            check_post_mortem_deadlines.delay()
            
    except Exception as e:
        logger.error(f"Error in incident_post_mortem_post_save: {e}")


@receiver(pre_save, sender=OnCallSchedule)
def oncall_schedule_pre_save(sender, instance, **kwargs):
    """Signal handler before saving OnCallSchedule"""
    try:
        # Set default values if not provided
        if not instance.schedule_type:
            instance.schedule_type = 'rotation'
        
        if not instance.rotation_period_days:
            instance.rotation_period_days = 7  # Weekly rotation default
        
        if not instance.timezone:
            instance.timezone = 'UTC'
        
        if not instance.start_time:
            instance.start_time = '09:00'
        
        if not instance.end_time:
            instance.end_time = '17:00'
        
        if not instance.days_of_week:
            instance.days_of_week = [0, 1, 2, 3, 4]  # Monday to Friday
        
        if not instance.is_active:
            instance.is_active = True
        
        # Validate schedule type
        valid_types = ['rotation', 'fixed', 'on_demand', 'auto']
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
            
            # Trigger on-call schedule update
            from ..tasks.incident import update_on_call_schedules
            update_on_call_schedules.delay()
            
        else:
            logger.debug(f"Updated OnCallSchedule: {instance.name}")
            
            # Trigger on-call change notification
            from ..tasks.incident import notify_on_call_changes
            notify_on_call_changes.delay()
            
    except Exception as e:
        logger.error(f"Error in oncall_schedule_post_save: {e}")


# Custom signal handlers for incident business logic
def trigger_incident_escalation(incident, escalation_level=None):
    """Custom function to trigger incident escalation"""
    try:
        logger.info(f"Triggering escalation for incident {incident.title}")
        
        # Create escalation timeline event
        IncidentTimeline.objects.create(
            incident=incident,
            event_type='escalated',
            title='Incident Escalated',
            description=f'Incident escalated to level {escalation_level or incident.escalation_level}',
            participants=[incident.assigned_to.id] if incident.assigned_to else []
        )
        
        # Update incident escalation level
        if escalation_level:
            incident.escalation_level = escalation_level
            incident.save(update_fields=['escalation_level'])
        
        # Trigger escalation task
        from ..tasks.incident import check_incident_escalations
        check_incident_escalations.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_incident_escalation: {e}")


def trigger_incident_notification(incident, notification_type, message=None):
    """Custom function to trigger incident notification"""
    try:
        logger.info(f"Triggering {notification_type} notification for incident {incident.title}")
        
        # Create notification
        from ..models.core import Notification
        
        notification = Notification.objects.create(
            notification_type='email',
            recipient="incident_team",  # Would be resolved by routing
            subject=f"Incident {notification_type.title()}: {incident.title}",
            message=message or f"Incident {incident.title} has been {notification_type}",
            status='pending'
        )
        
        # Trigger notification sending
        from ..tasks.notification import send_pending_notifications
        send_pending_notifications.delay()
        
        return notification
        
    except Exception as e:
        logger.error(f"Error in trigger_incident_notification: {e}")
        return None


def trigger_incident_metrics_update(incident):
    """Custom function to trigger incident metrics update"""
    try:
        logger.info(f"Updating metrics for incident {incident.title}")
        
        # Calculate and update incident metrics
        from ..tasks.incident import update_incident_metrics
        update_incident_metrics.delay()
        
        # Generate incident dashboard data
        from ..tasks.incident import generate_incident_dashboard_data
        generate_incident_dashboard_data.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_incident_metrics_update: {e}")


def trigger_post_mortem_reminder(incident):
    """Custom function to trigger post-mortem reminder"""
    try:
        logger.info(f"Triggering post-mortem reminder for incident {incident.title}")
        
        # Create notification for post-mortem
        from ..models.core import Notification
        
        notification = Notification.objects.create(
            notification_type='email',
            recipient="incident_manager",  # Would be resolved by routing
            subject=f"Post-Mortem Required: {incident.title}",
            message=f"Post-mortem analysis is required for incident {incident.title} (Severity: {incident.severity})",
            status='pending'
        )
        
        # Trigger notification sending
        from ..tasks.notification import send_pending_notifications
        send_pending_notifications.delay()
        
        return notification
        
    except Exception as e:
        logger.error(f"Error in trigger_post_mortem_reminder: {e}")
        return None


def trigger_on_call_rotation_change(schedule):
    """Custom function to trigger on-call rotation change"""
    try:
        logger.info(f"Triggering on-call rotation change for schedule {schedule.name}")
        
        # Get current and next on-call
        current_on_call = schedule.get_current_on_call()
        upcoming_schedule = schedule.get_upcoming_schedule(7)
        
        # Create notification about rotation change
        if current_on_call and upcoming_schedule:
            from ..models.core import Notification
            
            notification = Notification.objects.create(
                notification_type='email',
                recipient="on_call_team",  # Would be resolved by routing
                subject=f"On-Call Rotation Change: {schedule.name}",
                message=f"On-call rotation changing from {current_on_call.get_full_name()} to {upcoming_schedule[0]['user'].get_full_name() if upcoming_schedule else 'Unknown'}",
                status='pending'
            )
            
            # Trigger notification sending
            from ..tasks.notification import send_pending_notifications
            send_pending_notifications.delay()
            
            return notification
        
    except Exception as e:
        logger.error(f"Error in trigger_on_call_rotation_change: {e}")
        return None


def trigger_incident_auto_resolution(incident):
    """Custom function to trigger incident auto-resolution"""
    try:
        logger.info(f"Auto-resolving incident {incident.title}")
        
        # Create timeline event
        IncidentTimeline.objects.create(
            incident=incident,
            event_type='auto_resolved',
            title='Auto-Resolved',
            description='Incident automatically resolved due to timeout or criteria',
            participants=[]
        )
        
        # Update incident status
        incident.resolve(None, "Auto-resolved: System timeout")
        
        # Trigger metrics update
        from ..tasks.incident import update_incident_metrics
        update_incident_metrics.delay()
        
    except Exception as e:
        logger.error(f"Error in trigger_incident_auto_resolution: {e}")


# Signal registration
def register_incident_signals():
    """Register all incident signals"""
    try:
        logger.info("Incident signals registered successfully")
    except Exception as e:
        logger.error(f"Error registering incident signals: {e}")


# Auto-register signals when module is imported
register_incident_signals()
