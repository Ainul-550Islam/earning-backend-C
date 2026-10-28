"""
Incident Management Service - Handles incident lifecycle and coordination
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from django.db import transaction
from django.utils import timezone as django_tz
from django.core.cache import cache
from django.contrib.auth import get_user_model

from api.alerts.models.incident import (
    Incident, IncidentResponder, IncidentTimeline, IncidentPostmortem
)
from api.alerts.models.core import AlertLog
from api.alerts.services.notification import NotificationService

logger = logging.getLogger(__name__)
User = get_user_model()


class IncidentManager:
    """Manages incident lifecycle and coordination"""
    
    def __init__(self):
        self.notification_service = NotificationService()
        self.cache_timeout = 3600  # 1 hour
    
    def create_incident(self, title: str, description: str, severity: str, 
                       alert_logs: List[AlertLog] = None, assigned_to: User = None,
                       created_by: User = None, tenant=None) -> Incident:
        """
        Create a new incident from alert logs
        
        Args:
            title: Incident title
            description: Incident description
            severity: Incident severity (low, medium, high, critical)
            alert_logs: List of related alert logs
            assigned_to: User assigned to handle the incident
            created_by: User who created the incident
            tenant: Tenant instance
        
        Returns:
            Created incident instance
        """
        try:
            with transaction.atomic():
                incident = Incident.objects.create(
                    title=title,
                    description=description,
                    severity=severity,
                    status='open',
                    assigned_to=assigned_to,
                    created_by=created_by,
                    tenant=tenant
                )
                
                # Add related alerts
                if alert_logs:
                    incident.related_alerts.add(*alert_logs)
                
                # Create initial timeline entry
                self._add_timeline_entry(
                    incident,
                    'incident_created',
                    f'Incident created with severity {severity}',
                    created_by
                )
                
                # Send notification to assigned user
                if assigned_to:
                    self._send_incident_notification(incident, 'assigned')
                
                # Cache incident for quick access
                self._cache_incident(incident)
                
                logger.info(f"Created incident {incident.id}: {title}")
                return incident
                
        except Exception as e:
            logger.error(f"Error creating incident: {e}")
            raise
    
    @staticmethod
    def update_status(incident, status, user, notes=""):
        """
        Transition an incident's status, delegating to the Incident
        model's own acknowledge()/resolve()/close() methods so their
        escalation, timeline, and audit-trail side effects all still
        run. Returns True on success, False if the incident is already
        past the requested state (e.g. asked to acknowledge something
        already resolved/closed) so callers can tell "nothing to do"
        apart from a real error.
        """
        if status == 'acknowledged':
            if incident.status in ('resolved', 'closed'):
                return False
            return incident.acknowledge(user, notes=notes)
        elif status == 'resolved':
            if incident.status == 'closed':
                return False
            return incident.resolve(user, resolution_summary=notes)
        elif status == 'closed':
            return incident.close(user, notes=notes)
        else:
            raise ValueError(f"Unsupported status transition: {status}")

    def update_incident_status(self, incident: Incident, status: str, 
                             updated_by: User, comment: str = None) -> Incident:
        """
        Update incident status
        
        Args:
            incident: Incident to update
            status: New status (open, investigating, resolved, closed)
            updated_by: User making the update
            comment: Optional comment about the update
        
        Returns:
            Updated incident
        """
        try:
            old_status = incident.status
            incident.status = status
            incident.updated_by = updated_by
            incident.updated_at = django_tz.now()
            
            if status == 'resolved':
                incident.resolved_at = django_tz.now()
                incident.resolved_by = updated_by
            elif status == 'closed':
                incident.closed_at = django_tz.now()
                incident.closed_by = updated_by
            
            incident.save()
            
            # Add timeline entry
            self._add_timeline_entry(
                incident,
                'status_changed',
                f'Status changed from {old_status} to {status}',
                updated_by,
                comment=comment
            )
            
            # Send notification
            self._send_incident_notification(incident, f'status_{status}')
            
            # Update cache
            self._cache_incident(incident)
            
            logger.info(f"Updated incident {incident.id} status to {status}")
            return incident
            
        except Exception as e:
            logger.error(f"Error updating incident status: {e}")
            raise
    
    def acknowledge_incident(self, incident_id: int, acknowledged_by: User = None, note: str = '') -> Incident:
        """Acknowledge an incident by ID"""
        incident = Incident.objects.get(pk=incident_id)
        incident.acknowledge(acknowledged_by, note)
        return incident

    def resolve_incident(self, incident_id: int, resolved_by: User = None, resolution_note: str = '') -> Incident:
        """Resolve an incident by ID"""
        incident = Incident.objects.get(pk=incident_id)
        incident.resolve(resolved_by, resolution_note)
        return incident

    def close_incident(self, incident_id: int, closed_by: User = None, close_note: str = '') -> Incident:
        """Close an incident by ID"""
        incident = Incident.objects.get(pk=incident_id)
        incident.close(closed_by, close_note)
        return incident

    def add_responder(self, incident: Incident, user: User, role: str = 'responder',
                     added_by: User = None) -> IncidentResponder:
        """
        Add a responder to an incident
        
        Args:
            incident: Incident to add responder to
            user: User to add as responder
            role: Responder role (lead, responder, observer)
            added_by: User who added the responder
        
        Returns:
            Created incident responder
        """
        try:
            responder, created = IncidentResponder.objects.get_or_create(
                incident=incident,
                user=user,
                defaults={
                    'role': role,
                    'tenant': incident.tenant
                }
            )
            
            if created:
                # Add timeline entry
                self._add_timeline_entry(
                    incident,
                    'responder_added',
                    f'{user.username} added as {role}',
                    added_by
                )
                
                # Send notification to new responder
                self._send_responder_notification(incident, user, role)
                
                logger.info(f"Added responder {user.username} to incident {incident.id}")
            
            return responder
            
        except Exception as e:
            logger.error(f"Error adding responder to incident: {e}")
            raise
    
    def add_timeline_entry(self, incident: Incident, entry_type: str, 
                           message: str, created_by: User, comment: str = None,
                           metadata: Dict[str, Any] = None) -> IncidentTimeline:
        """
        Add a timeline entry to an incident
        
        Args:
            incident: Incident to add entry to
            entry_type: Type of entry (incident_created, status_changed, etc.)
            message: Timeline message
            created_by: User who created the entry
            comment: Optional comment
            metadata: Optional metadata
        
        Returns:
            Created timeline entry
        """
        return self._add_timeline_entry(
            incident, entry_type, message, created_by, comment, metadata
        )
    
    def create_postmortem(self, incident: Incident, summary: str, root_cause: str,
                         timeline: str, lessons_learned: str, action_items: str,
                         created_by: User, reviewed_by: User = None) -> IncidentPostmortem:
        """
        Create a postmortem for a resolved incident
        
        Args:
            incident: Incident to create postmortem for
            summary: Incident summary
            root_cause: Root cause analysis
            timeline: Detailed timeline
            lessons_learned: Lessons learned
            action_items: Action items
            created_by: User who created the postmortem
            reviewed_by: User who reviewed the postmortem
        
        Returns:
            Created postmortem
        """
        try:
            postmortem = IncidentPostmortem.objects.create(
                incident=incident,
                summary=summary,
                root_cause=root_cause,
                timeline=timeline,
                lessons_learned=lessons_learned,
                action_items=action_items,
                created_by=created_by,
                reviewed_by=reviewed_by,
                tenant=incident.tenant
            )
            
            # Add timeline entry
            self._add_timeline_entry(
                incident,
                'postmortem_created',
                'Postmortem created and reviewed',
                created_by
            )
            
            logger.info(f"Created postmortem for incident {incident.id}")
            return postmortem
            
        except Exception as e:
            logger.error(f"Error creating postmortem: {e}")
            raise
    
    def get_incident_statistics(self, tenant=None, time_period: int = 30) -> Dict[str, Any]:
        """
        Get incident statistics
        
        Args:
            tenant: Optional tenant filter
            time_period: Time period in days
        
        Returns:
            Dictionary with incident statistics
        """
        try:
            from django.db.models import Count, Q
            from datetime import timedelta
            
            start_date = django_tz.now() - timedelta(days=time_period)
            
            queryset = Incident.objects.filter(
                created_at__gte=start_date
            )
            
            if tenant:
                queryset = queryset.filter(tenant=tenant)
            
            stats = {
                'total_incidents': queryset.count(),
                'by_status': dict(queryset.values('status').annotate(count=Count('id')).values_list('status', 'count')),
                'by_severity': dict(queryset.values('severity').annotate(count=Count('id')).values_list('severity', 'count')),
                'resolved_count': queryset.filter(status='resolved').count(),
                'closed_count': queryset.filter(status='closed').count(),
                'average_resolution_time': self._calculate_average_resolution_time(queryset),
                'time_period_days': time_period
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating incident statistics: {e}")
            return {}
    
    def get_active_incidents(self, tenant=None, assigned_to: User = None) -> List[Incident]:
        """
        Get active incidents
        
        Args:
            tenant: Optional tenant filter
            assigned_to: Optional assigned user filter
        
        Returns:
            List of active incidents
        """
        try:
            queryset = Incident.objects.filter(
                status__in=['open', 'investigating']
            ).order_by('-created_at')
            
            if tenant:
                queryset = queryset.filter(tenant=tenant)
            
            if assigned_to:
                queryset = queryset.filter(assigned_to=assigned_to)
            
            return list(queryset)
            
        except Exception as e:
            logger.error(f"Error getting active incidents: {e}")
            return []
    
    def _add_timeline_entry(self, incident: Incident, entry_type: str,
                           message: str, created_by: User = None, comment: str = None,
                           metadata: Dict[str, Any] = None) -> IncidentTimeline:
        """Internal method to add timeline entry"""
        try:
            return IncidentTimeline.objects.create(
                incident=incident,
                event_type=entry_type if entry_type in [
                    'detected','acknowledged','investigation_started','identified',
                    'communication_sent','mitigation_applied','monitoring',
                    'resolved','closed','update','escalation','de_escalation'
                ] else 'update',
                title=message[:200] if message else 'Update',
                description=comment or message or '',
                participants=[created_by.id] if created_by else [],
            )
        except Exception as e:
            logger.error(f"Error adding timeline entry: {e}")
            return None
    
    def _send_incident_notification(self, incident: Incident, notification_type: str):
        """Send incident notification"""
        try:
            # Implementation would depend on your notification system
            # This is a placeholder for the actual notification logic
            pass
        except Exception as e:
            logger.error(f"Error sending incident notification: {e}")
    
    def _send_responder_notification(self, incident: Incident, user: User, role: str):
        """Send responder notification"""
        try:
            # Implementation would depend on your notification system
            # This is a placeholder for the actual notification logic
            pass
        except Exception as e:
            logger.error(f"Error sending responder notification: {e}")
    
    def _cache_incident(self, incident: Incident):
        """Cache incident for quick access"""
        try:
            cache_key = f"incident_{incident.id}"
            cache.set(cache_key, incident, self.cache_timeout)
        except Exception as e:
            logger.error(f"Error caching incident: {e}")
    
    def _calculate_average_resolution_time(self, queryset) -> float:
        """Calculate average resolution time in hours"""
        try:
            from django.db.models import F, ExpressionWrapper, DurationField
            from django.db.models.functions import Coalesce
            
            resolved_incidents = queryset.filter(
                status__in=['resolved', 'closed']
            ).annotate(
                resolution_time=ExpressionWrapper(
                    Coalesce(F('resolved_at'), F('closed_at')) - F('created_at'),
                    output_field=DurationField()
                )
            )
            
            if not resolved_incidents.exists():
                return 0.0
            
            total_seconds = sum([
                incident.resolution_time.total_seconds() 
                for incident in resolved_incidents
            ])
            
            return total_seconds / len(resolved_incidents) / 3600  # Convert to hours
            
        except Exception as e:
            logger.error(f"Error calculating average resolution time: {e}")
            return 0.0
