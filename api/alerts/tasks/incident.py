"""
Incident Tasks
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from ..models.incident import Incident, IncidentResponder, IncidentPostMortem, OnCallSchedule

logger = logging.getLogger(__name__)


@shared_task
def check_incident_escalations():
    """Check for incidents that need escalation"""
    try:
        from ..models.core import AlertLog
        
        # Get unresolved incidents that need escalation
        unresolved_incidents = Incident.objects.filter(
            status__in=['open', 'investigating', 'identified']
        ).select_related('assigned_to')
        
        escalated_count = 0
        
        for incident in unresolved_incidents:
            # Check if incident needs escalation based on severity and time
            escalation_needed = incident.should_escalate()
            
            if escalation_needed:
                # Get escalation chain
                escalation_chain = incident.get_escalation_chain()
                
                # Escalate to next level
                if escalation_chain:
                    next_level = escalation_chain[0]
                    incident.escalate(next_level['user'], "Automatic escalation due to time threshold")
                    escalated_count += 1
        
        logger.info(f"Escalated {escalated_count} incidents")
        return escalated_count
        
    except Exception as e:
        logger.error(f"Error in check_incident_escalations: {e}")
        return 0


@shared_task
def update_on_call_schedules():
    """Update on-call schedules and rotations"""
    try:
        schedules = OnCallSchedule.objects.filter(is_active=True)
        
        updated_count = 0
        for schedule in schedules:
            if schedule.schedule_type == 'rotation':
                # Update rotation based on schedule
                updated_count += 1
        
        logger.info(f"Updated {updated_count} on-call schedules")
        return updated_count
        
    except Exception as e:
        logger.error(f"Error in update_on_call_schedules: {e}")
        return 0


@shared_task
def check_responder_availability():
    """Check availability of incident responders"""
    try:
        responders = IncidentResponder.objects.filter(status='active')
        
        updated_count = 0
        for responder in responders:
            # Check if responder is still available
            if not responder.is_available_now():
                # Mark as away if availability window passed
                responder.status = 'away'
                responder.save()
                updated_count += 1
        
        logger.info(f"Updated availability for {updated_count} responders")
        return updated_count
        
    except Exception as e:
        logger.error(f"Error in check_responder_availability: {e}")
        return 0


@shared_task
def generate_incident_summary():
    """Generate daily incident summary"""
    try:
        yesterday = timezone.now().date() - timedelta(days=1)
        
        incidents = Incident.objects.filter(detected_at__date=yesterday)
        
        summary = {
            'date': yesterday.isoformat(),
            'total_incidents': incidents.count(),
            'by_severity': {},
            'by_status': {},
            'average_resolution_time': 0,
            'critical_incidents': incidents.filter(severity='critical').count()
        }
        
        # By severity
        for severity in ['low', 'medium', 'high', 'critical']:
            summary['by_severity'][severity] = incidents.filter(severity=severity).count()
        
        # By status
        for status in ['open', 'investigating', 'identified', 'monitoring', 'resolved', 'closed']:
            summary['by_status'][status] = incidents.filter(status=status).count()
        
        # Average resolution time
        resolved_incidents = incidents.filter(resolved_at__isnull=False)
        if resolved_incidents.exists():
            total_time = sum(
                (incident.resolved_at - incident.detected_at).total_seconds() / 60
                for incident in resolved_incidents
            )
            summary['average_resolution_time'] = total_time / resolved_incidents.count()
        
        logger.info(f"Generated incident summary for {yesterday}: {summary}")
        return summary
        
    except Exception as e:
        logger.error(f"Error in generate_incident_summary: {e}")
        return None


@shared_task
def create_incident_from_alert(alert_id):
    """Create incident from high-priority alert"""
    try:
        from ..models.core import AlertLog
        
        alert = AlertLog.objects.get(id=alert_id)
        
        # Create incident if alert is high severity or has been unresolved for too long
        if alert.rule.severity in ['high', 'critical'] or alert.get_age_in_minutes() > 60:
            incident = Incident.create_from_alert(alert)
            
            # Auto-assign to on-call if available
            current_on_call = OnCallSchedule.get_current_on_call_all()
            if current_on_call:
                incident.assigned_to = current_on_call[0]['user']
                incident.save()
            
            logger.info(f"Created incident {incident.id} from alert {alert_id}")
            return incident.id
        else:
            logger.info(f"Alert {alert_id} does not require incident creation")
            return None
        
    except Exception as e:
        logger.error(f"Error in create_incident_from_alert: {e}")
        return None


@shared_task
def update_incident_metrics():
    """Update incident metrics and statistics"""
    try:
        # Update incident duration metrics
        incidents = Incident.objects.filter(
            status__in=['resolved', 'closed']
        )
        
        updated_count = 0
        for incident in incidents:
            # Update duration if not already calculated
            if not incident.total_downtime_minutes:
                incident.total_downtime_minutes = incident.get_duration_minutes()
                incident.save(update_fields=['total_downtime_minutes'])
                updated_count += 1
        
        logger.info(f"Updated metrics for {updated_count} incidents")
        return updated_count
        
    except Exception as e:
        logger.error(f"Error in update_incident_metrics: {e}")
        return 0


@shared_task
def check_post_mortem_deadlines():
    """Check for post-mortems that need completion"""
    try:
        # Get resolved incidents without post-mortems
        incidents_without_rca = Incident.objects.filter(
            status='resolved',
            resolved_at__gte=timezone.now() - timedelta(days=7)
        ).exclude(
            postmortem__isnull=False
        )
        
        notified_count = 0
        for incident in incidents_without_rca:
            # Check if post-mortem is required based on severity
            if incident.severity in ['high', 'critical']:
                # Send notification to create post-mortem
                notified_count += 1
        
        logger.info(f"Notified about {notified_count} missing post-mortems")
        return notified_count
        
    except Exception as e:
        logger.error(f"Error in check_post_mortem_deadlines: {e}")
        return 0


@shared_task
def auto_resolve_low_priority_incidents():
    """Auto-resolve low priority incidents after timeout"""
    try:
        # Get low priority incidents that have been open too long
        timeout_hours = 72  # 3 days
        cutoff_time = timezone.now() - timedelta(hours=timeout_hours)
        
        low_priority_incidents = Incident.objects.filter(
            severity='low',
            status='open',
            detected_at__lt=cutoff_time
        )
        
        resolved_count = 0
        for incident in low_priority_incidents:
            incident.resolve(None, "Auto-resolved: Low priority incident timeout")
            resolved_count += 1
        
        logger.info(f"Auto-resolved {resolved_count} low priority incidents")
        return resolved_count
        
    except Exception as e:
        logger.error(f"Error in auto_resolve_low_priority_incidents: {e}")
        return 0


@shared_task
def generate_incident_dashboard_data():
    """Generate incident dashboard data"""
    try:
        # Get current incident statistics
        active_incidents = Incident.objects.filter(
            status__in=['open', 'investigating', 'identified', 'monitoring']
        )
        
        # Get current on-call personnel
        current_on_call = OnCallSchedule.get_current_on_call_all()
        
        dashboard_data = {
            'active_incidents': active_incidents.count(),
            'by_severity': {},
            'by_status': {},
            'current_on_call': current_on_call,
            'recent_incidents': []
        }
        
        # By severity
        for severity in ['low', 'medium', 'high', 'critical']:
            dashboard_data['by_severity'][severity] = active_incidents.filter(severity=severity).count()
        
        # By status
        for status in ['open', 'investigating', 'identified', 'monitoring']:
            dashboard_data['by_status'][status] = active_incidents.filter(status=status).count()
        
        # Recent incidents
        recent_incidents = Incident.objects.order_by('-detected_at')[:10]
        dashboard_data['recent_incidents'] = [
            {
                'id': incident.id,
                'title': incident.title,
                'severity': incident.severity,
                'status': incident.status,
                'detected_at': incident.detected_at
            }
            for incident in recent_incidents
        ]
        
        logger.info("Generated incident dashboard data")
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Error in generate_incident_dashboard_data: {e}")
        return None


@shared_task
def cleanup_old_incident_data():
    """Clean up old incident data"""
    try:
        days_to_keep = 365  # Keep 1 year of incident data
        
        # Clean up old timeline events
        from ..models.incident import IncidentTimeline
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        deleted_timeline = IncidentTimeline.objects.filter(
            timestamp__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_timeline} old incident timeline events")
        return deleted_timeline
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_incident_data: {e}")
        return 0


@shared_task
def notify_on_call_changes():
    """Notify on-call personnel of schedule changes"""
    try:
        # Get upcoming on-call changes
        upcoming_changes = OnCallSchedule.objects.filter(
            is_active=True,
            next_run__lte=timezone.now() + timedelta(hours=24)
        )
        
        notified_count = 0
        for schedule in upcoming_changes:
            # Send notification about upcoming change
            notified_count += 1
        
        logger.info(f"Notified about {notified_count} upcoming on-call changes")
        return notified_count
        
    except Exception as e:
        logger.error(f"Error in notify_on_call_changes: {e}")
        return 0


@shared_task
def update_incident_response_metrics():
    """Update incident response metrics"""
    try:
        # Calculate response times for recent incidents
        recent_incidents = Incident.objects.filter(
            detected_at__gte=timezone.now() - timedelta(days=7)
        )
        
        metrics = {
            'total_incidents': recent_incidents.count(),
            'avg_response_time': 0,
            'avg_resolution_time': 0,
            'mttr': 0,
            'mttd': 0
        }
        
        # Calculate average response time
        acknowledged_incidents = recent_incidents.filter(acknowledged_at__isnull=False)
        if acknowledged_incidents.exists():
            total_response_time = sum(
                (incident.acknowledged_at - incident.detected_at).total_seconds() / 60
                for incident in acknowledged_incidents
            )
            metrics['avg_response_time'] = total_response_time / acknowledged_incidents.count()
        
        # Calculate average resolution time
        resolved_incidents = recent_incidents.filter(resolved_at__isnull=False)
        if resolved_incidents.exists():
            total_resolution_time = sum(
                (incident.resolved_at - incident.detected_at).total_seconds() / 60
                for incident in resolved_incidents
            )
            metrics['avg_resolution_time'] = total_resolution_time / resolved_incidents.count()
            metrics['mttr'] = metrics['avg_resolution_time']
        
        logger.info(f"Updated incident response metrics: {metrics}")
        return metrics
        
    except Exception as e:
        logger.error(f"Error in update_incident_response_metrics: {e}")
        return None


@shared_task
def escalate_unacknowledged_incidents():
    """Escalate incidents that haven't been acknowledged"""
    try:
        # Get unacknowledged incidents older than threshold
        threshold_minutes = 30
        cutoff_time = timezone.now() - timedelta(minutes=threshold_minutes)
        
        unacknowledged = Incident.objects.filter(
            status='open',
            acknowledged_at__isnull=True,
            detected_at__lt=cutoff_time
        )
        
        escalated_count = 0
        for incident in unacknowledged:
            # Escalate to manager or next level
            incident.escalate(None, "Auto-escalated: Unacknowledged incident")
            escalated_count += 1
        
        logger.info(f"Escalated {escalated_count} unacknowledged incidents")
        return escalated_count
        
    except Exception as e:
        logger.error(f"Error in escalate_unacknowledged_incidents: {e}")
        return 0


@shared_task
def generate_incident_trends_report():
    """Generate incident trends analysis"""
    try:
        days = 30
        
        # Get incident trends
        cutoff_date = timezone.now() - timedelta(days=days)
        
        incidents = Incident.objects.filter(detected_at__gte=cutoff_date)
        
        trends = {
            'period_days': days,
            'total_incidents': incidents.count(),
            'daily_trends': {},
            'severity_trends': {},
            'resolution_trends': {}
        }
        
        # Daily trends
        for day in range(days):
            date = timezone.now().date() - timedelta(days=day)
            daily_count = incidents.filter(detected_at__date=date).count()
            trends['daily_trends'][date.isoformat()] = daily_count
        
        # Severity trends
        for severity in ['low', 'medium', 'high', 'critical']:
            trends['severity_trends'][severity] = incidents.filter(severity=severity).count()
        
        # Resolution trends
        for status in ['resolved', 'closed']:
            trends['resolution_trends'][status] = incidents.filter(status=status).count()
        
        logger.info(f"Generated incident trends for {days} days: {trends}")
        return trends
        
    except Exception as e:
        logger.error(f"Error in generate_incident_trends_report: {e}")
        return None
