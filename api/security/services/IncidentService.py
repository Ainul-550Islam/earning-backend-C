"""
Incident Service
Automatically creates SecurityIncident from fraud detection and manages incident lifecycle
Version: 1.0.0
"""

import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.contrib.auth import get_user_model

from ..models import SecurityIncident, SecurityLog, UserBan
from ..constants import IncidentManagement, CacheSettings
from ..choices import IncidentStatus, IncidentSeverity, SecurityEventType
from ..utils.cache_manager import CacheManager, handle_gracefully

logger = logging.getLogger(__name__)


class IncidentService:
    """
    Incident Management Service with defensive coding patterns
    Automatically creates incidents from fraud detection and manages incident lifecycle
    """
    
    def __init__(self):
        """Initialize Incident Service"""
        try:
            self.cache_prefix = "incident_service"
            self.auto_creation_enabled = getattr(settings, 'AUTO_INCIDENT_CREATION', True)
            self.fraud_threshold = getattr(settings, 'FRAUD_INCIDENT_THRESHOLD', 50)
            
            logger.info("IncidentService initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize IncidentService: {e}")
            self.auto_creation_enabled = False
            self.fraud_threshold = 50
    
    @handle_gracefully(default_return=None, log_errors=True)
    def create_incident_from_fraud_detection(self, user, fraud_result: Dict[str, Any], 
                                          detected_by: str = 'system') -> Optional[SecurityIncident]:
        """
        Automatically create SecurityIncident from fraud detection result
        Integrates with existing FraudDetectionEngine
        """
        try:
            if not self.auto_creation_enabled:
                logger.debug("Auto incident creation is disabled")
                return None
            
            # Check if fraud score meets threshold
            fraud_score = fraud_result.get('score', 0)
            if fraud_score < self.fraud_threshold:
                logger.debug(f"Fraud score {fraud_score} below threshold {self.fraud_threshold}")
                return None
            
            # Check if similar incident already exists
            existing_incident = self._check_existing_incident(user, fraud_result)
            if existing_incident:
                logger.info(f"Similar incident already exists: {existing_incident.incident_id}")
                return existing_incident
            
            # Create new incident
            incident = SecurityIncident.create_from_fraud_detection(user, fraud_result, detected_by)
            
            # Link to related security events
            self._link_to_security_events(incident, user, fraud_result)
            
            # Check for escalation conditions
            self._check_escalation_conditions(incident, fraud_result)
            
            # Send notifications
            self._send_incident_notifications(incident)
            
            # Clear related cache
            self._clear_user_incident_cache(user.id)
            
            logger.info(f"Created fraud incident {incident.incident_id} for user {user.id}")
            return incident
            
        except Exception as e:
            logger.error(f"Failed to create incident from fraud detection: {e}")
            return None
    
    def _check_existing_incident(self, user, fraud_result: Dict[str, Any]) -> Optional[SecurityIncident]:
        """Check if similar incident already exists"""
        try:
            # Look for recent fraud incidents for the same user
            recent_time = timezone.now() - timedelta(hours=1)
            
            existing = SecurityIncident.objects.filter(
                user=user,
                incident_type='fraud_detection',
                created_at__gte=recent_time,
                status__in=['open', 'investigating']
            ).first()
            
            if existing:
                # Check if the fraud reasons are similar
                existing_reasons = existing.evidence.get('reasons', [])
                current_reasons = fraud_result.get('reasons', [])
                
                # If there's overlap in reasons, consider it the same incident
                if set(existing_reasons) & set(current_reasons):
                    return existing
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking existing incident: {e}")
            return None
    
    def _link_to_security_events(self, incident: SecurityIncident, user, fraud_result: Dict[str, Any]):
        """Link incident to related security events"""
        try:
            # Get recent security logs for the user
            time_window = timedelta(hours=24)
            recent_logs = SecurityLog.objects.filter(
                user=user,
                created_at__gte=timezone.now() - time_window
            ).order_by('-created_at')[:10]
            
            # Link relevant logs
            for log in recent_logs:
                try:
                    # Check if log is related to fraud indicators
                    if self._is_log_related_to_fraud(log, fraud_result):
                        incident.security_logs.add(log)
                        
                except Exception as e:
                    logger.warning(f"Error linking security log {log.id}: {e}")
                    continue
            
            # Link to recent user bans if any
            recent_bans = UserBan.objects.filter(
                user=user,
                created_at__gte=timezone.now() - time_window
            )
            
            for ban in recent_bans:
                incident.user_bans.add(ban)
            
            logger.info(f"Linked {incident.security_logs.count()} security logs and {incident.user_bans.count()} bans to incident {incident.incident_id}")
            
        except Exception as e:
            logger.error(f"Error linking security events: {e}")
    
    def _is_log_related_to_fraud(self, log: SecurityLog, fraud_result: Dict[str, Any]) -> bool:
        """Check if security log is related to fraud indicators"""
        try:
            # Check IP address match
            if 'metadata' in fraud_result and 'ip_address' in fraud_result['metadata']:
                if log.ip_address == fraud_result['metadata']['ip_address']:
                    return True
            
            # Check event type match
            fraud_events = SecurityEventType.get_fraud_events()
            if log.security_type in fraud_events:
                return True
            
            # Check time proximity (within last hour)
            if log.created_at >= timezone.now() - timedelta(hours=1):
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking log relation: {e}")
            return False
    
    def _check_escalation_conditions(self, incident: SecurityIncident, fraud_result: Dict[str, Any]):
        """Check if incident should be escalated"""
        try:
            escalation_reasons = []
            
            # High fraud score
            if fraud_result.get('score', 0) >= 80:
                escalation_reasons.append("High fraud score")
            
            # Multiple fraud reasons
            if len(fraud_result.get('reasons', [])) >= 3:
                escalation_reasons.append("Multiple fraud indicators")
            
            # User has previous incidents
            previous_incidents = SecurityIncident.objects.filter(
                user=incident.user,
                incident_type='fraud_detection',
                status__in=['resolved', 'closed']
            ).count()
            
            if previous_incidents >= 2:
                escalation_reasons.append(f"Repeat offender ({previous_incidents} previous incidents)")
            
            # Escalate if conditions met
            if escalation_reasons:
                incident.status = 'escalated'
                incident.notes += f"\n\nEscalation reasons: {', '.join(escalation_reasons)}"
                incident.save()
                
                logger.warning(f"Escalated incident {incident.incident_id}: {', '.join(escalation_reasons)}")
                
        except Exception as e:
            logger.error(f"Error checking escalation conditions: {e}")
    
    def _send_incident_notifications(self, incident: SecurityIncident):
        """Send incident notifications"""
        try:
            from ..utils.device import send_security_alert
            
            # Send security alert
            alert_sent = send_security_alert(
                user=incident.user,
                security_type='incident_created',
                description=f"Security incident {incident.incident_id} created: {incident.title}",
                metadata={
                    'incident_id': incident.incident_id,
                    'severity': incident.severity,
                    'incident_type': incident.incident_type,
                    'auto_created': True
                }
            )
            
            if alert_sent:
                logger.info(f"Sent notification for incident {incident.incident_id}")
            
        except Exception as e:
            logger.error(f"Error sending incident notifications: {e}")
    
    def _clear_user_incident_cache(self, user_id: int):
        """Clear incident cache for user"""
        try:
            cache_keys = [
                CacheManager.generate_key(self.cache_prefix, "user_incidents", user_id),
                CacheManager.generate_key(self.cache_prefix, "active_incidents", "user", user_id),
            ]
            
            for key in cache_keys:
                CacheManager.delete(key)
                
        except Exception as e:
            logger.debug(f"Error clearing user incident cache: {e}")
    
    @handle_gracefully(default_return=[], log_errors=True)
    def get_user_incidents(self, user_id: int, include_resolved: bool = False, limit: int = 50) -> List[Dict[str, Any]]:
        """Get incidents for a specific user"""
        try:
            cache_key = CacheManager.generate_key(self.cache_prefix, "user_incidents", user_id, include_resolved, limit)
            
            # Try cache first
            cached_result = CacheManager.get(cache_key)
            if cached_result:
                return cached_result
            
            # Build queryset
            queryset = SecurityIncident.objects.filter(user_id=user_id)
            
            if not include_resolved:
                from ..choices import IncidentStatus
                queryset = queryset.filter(status__in=IncidentStatus.get_active_statuses())
            
            incidents = queryset.order_by('-opened_at')[:limit]
            
            # Convert to dict format
            result = []
            for incident in incidents:
                try:
                    result.append({
                        'incident_id': incident.incident_id,
                        'title': incident.title,
                        'description': incident.description[:200] + '...' if len(incident.description) > 200 else incident.description,
                        'incident_type': incident.incident_type,
                        'severity': incident.severity,
                        'status': incident.status,
                        'opened_at': incident.opened_at.isoformat(),
                        'detected_at': incident.detected_at.isoformat(),
                        'resolved_at': incident.resolved_at.isoformat() if incident.resolved_at else None,
                        'duration_hours': incident.get_duration().total_seconds() / 3600,
                        'is_overdue': incident.is_overdue(),
                        'priority_score': incident.get_priority_score(),
                        'assigned_to': incident.assigned_to.username if incident.assigned_to else None,
                        'impact_score': incident.impact_score,
                        'confidence_level': float(incident.confidence_level),
                        'notes': incident.notes[:100] + '...' if len(incident.notes) > 100 else incident.notes
                    })
                except Exception as e:
                    logger.warning(f"Error processing incident {incident.id}: {e}")
                    continue
            
            # Cache the result
            cache_ttl = CacheSettings.get_cache_ttl('incident_data')
            CacheManager.set(cache_key, result, cache_ttl)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get user incidents: {e}")
            return []
    
    @handle_gracefully(default_return=[], log_errors=True)
    def get_active_incidents(self, severity: str = None, assigned_to: int = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get active incidents with filtering options"""
        try:
            cache_key = CacheManager.generate_key(self.cache_prefix, "active_incidents", severity or "all", assigned_to or "none", limit)
            
            # Try cache first
            cached_result = CacheManager.get(cache_key)
            if cached_result:
                return cached_result
            
            incidents = SecurityIncident.get_active_incidents(severity)
            
            # Filter by assigned user if specified
            if assigned_to:
                incidents = [inc for inc in incidents if inc.assigned_to_id == assigned_to]
            
            # Limit results
            incidents = incidents[:limit]
            
            # Convert to dict format
            result = []
            for incident in incidents:
                try:
                    result.append({
                        'incident_id': incident.incident_id,
                        'title': incident.title,
                        'incident_type': incident.incident_type,
                        'severity': incident.severity,
                        'status': incident.status,
                        'opened_at': incident.opened_at.isoformat(),
                        'detected_at': incident.detected_at.isoformat(),
                        'duration_hours': incident.get_duration().total_seconds() / 3600,
                        'is_overdue': incident.is_overdue(),
                        'priority_score': incident.get_priority_score(),
                        'user': {
                            'id': incident.user.id,
                            'username': incident.user.username,
                            'email': incident.user.email
                        } if incident.user else None,
                        'assigned_to': {
                            'id': incident.assigned_to.id,
                            'username': incident.assigned_to.username
                        } if incident.assigned_to else None,
                        'assigned_team': incident.assigned_team,
                        'impact_score': incident.impact_score,
                        'confidence_level': float(incident.confidence_level),
                        'threat_category': incident.threat_category,
                        'affected_users_count': incident.affected_users.count(),
                        'security_logs_count': incident.security_logs.count(),
                        'user_bans_count': incident.user_bans.count()
                    })
                except Exception as e:
                    logger.warning(f"Error processing incident {incident.id}: {e}")
                    continue
            
            # Sort by priority score
            result.sort(key=lambda x: x['priority_score'], reverse=True)
            
            # Cache the result
            cache_ttl = CacheSettings.get_cache_ttl('incident_data')
            CacheManager.set(cache_key, result, cache_ttl)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get active incidents: {e}")
            return []
    
    @handle_gracefully(default_return=False, log_errors=True)
    def update_incident_status(self, incident_id: str, new_status: str, updated_by, 
                             resolution_summary: str = "", notes: str = "") -> bool:
        """Update incident status with validation"""
        try:
            with transaction.atomic():
                # Get incident
                incident = SecurityIncident.objects.get(incident_id=incident_id)
                
                # Validate status transition
                from ..choices import IncidentStatus
                if not IncidentStatus.can_transition(incident.status, new_status):
                    logger.warning(f"Invalid status transition from {incident.status} to {new_status} for incident {incident_id}")
                    return False
                
                # Update incident
                old_status = incident.status
                incident.status = new_status
                incident.updated_by = updated_by
                incident.last_activity = timezone.now()
                
                # Add resolution summary if resolving
                if new_status in ['resolved', 'closed'] and resolution_summary:
                    incident.resolution_summary = resolution_summary
                
                # Add notes
                if notes:
                    timestamp = timezone.now().isoformat()
                    incident.notes += f"\n\n[{timestamp}] Updated by {updated_by.username}: {notes}"
                
                incident.save()
                
                # Log the change
                logger.info(f"Incident {incident_id} status changed from {old_status} to {new_status} by {updated_by.username}")
                
                # Clear related cache
                self._clear_incident_cache(incident.id)
                
                # Send status change notification
                self._send_status_change_notification(incident, old_status, new_status)
                
                return True
                
        except SecurityIncident.DoesNotExist:
            logger.error(f"Incident {incident_id} not found")
            return False
        except Exception as e:
            logger.error(f"Failed to update incident status: {e}")
            return False
    
    def _send_status_change_notification(self, incident: SecurityIncident, old_status: str, new_status: str):
        """Send status change notification"""
        try:
            from ..utils.device import send_security_alert
            
            # Send notification to incident user if applicable
            if incident.user:
                send_security_alert(
                    user=incident.user,
                    security_type='incident_updated',
                    description=f"Incident {incident.incident_id} status changed from {old_status} to {new_status}",
                    metadata={
                        'incident_id': incident.incident_id,
                        'old_status': old_status,
                        'new_status': new_status
                    }
                )
            
        except Exception as e:
            logger.error(f"Error sending status change notification: {e}")
    
    def _clear_incident_cache(self, incident_id: str):
        """Clear incident-related cache"""
        try:
            # Clear various cache keys related to incidents
            cache_patterns = [
                "active_incidents",
                "user_incidents",
                "incident_statistics"
            ]
            
            for pattern in cache_patterns:
                # This would ideally use pattern deletion, but we'll clear specific keys
                pass  # Implementation depends on cache backend
                
        except Exception as e:
            logger.debug(f"Error clearing incident cache: {e}")
    
    @handle_gracefully(default_return={}, log_errors=True)
    def get_incident_statistics(self) -> Dict[str, Any]:
        """Get incident management statistics"""
        try:
            cache_key = CacheManager.generate_key(self.cache_prefix, "statistics")
            
            # Try cache first
            cached_stats = CacheManager.get(cache_key)
            if cached_stats:
                return cached_stats
            
            # Calculate statistics
            total_incidents = SecurityIncident.objects.count()
            
            # Active incidents
            from ..choices import IncidentStatus
            active_incidents = SecurityIncident.objects.filter(
                status__in=IncidentStatus.get_active_statuses()
            ).count()
            
            # Overdue incidents
            overdue_incidents = len(SecurityIncident.get_overdue_incidents())
            
            # Group by status
            incidents_by_status = {}
            for status, _ in IncidentStatus.get_choices():
                count = SecurityIncident.objects.filter(status=status).count()
                incidents_by_status[status] = count
            
            # Group by severity
            incidents_by_severity = {}
            for severity, _ in IncidentSeverity.get_choices():
                count = SecurityIncident.objects.filter(severity=severity).count()
                incidents_by_severity[severity] = count
            
            # Group by type
            incidents_by_type = {}
            for incident_type, _ in SecurityIncident.INCIDENT_TYPES:
                count = SecurityIncident.objects.filter(incident_type=incident_type).count()
                incidents_by_type[incident_type] = count
            
            # Recent activity (last 24 hours)
            recent_time = timezone.now() - timedelta(hours=24)
            recent_incidents = SecurityIncident.objects.filter(
                opened_at__gte=recent_time
            ).count()
            
            # Average resolution time
            resolved_incidents = SecurityIncident.objects.filter(
                status__in=['resolved', 'closed'],
                resolved_at__isnull=False
            )
            
            avg_resolution_time = 0
            if resolved_incidents.exists():
                total_time = sum(
                    (inc.resolved_at - inc.opened_at).total_seconds()
                    for inc in resolved_incidents
                )
                avg_resolution_time = total_time / resolved_incidents.count() / 3600  # Convert to hours
            
            stats = {
                'total_incidents': total_incidents,
                'active_incidents': active_incidents,
                'overdue_incidents': overdue_incidents,
                'recent_incidents_24h': recent_incidents,
                'avg_resolution_time_hours': round(avg_resolution_time, 2),
                'incidents_by_status': incidents_by_status,
                'incidents_by_severity': incidents_by_severity,
                'incidents_by_type': incidents_by_type,
                'last_updated': timezone.now().isoformat()
            }
            
            # Cache the statistics
            cache_ttl = CacheSettings.get_cache_ttl('incident_data')
            CacheManager.set(cache_key, stats, cache_ttl)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get incident statistics: {e}")
            return {
                'error': str(e),
                'last_updated': timezone.now().isoformat()
            }
    
    @handle_gracefully(default_return=False, log_errors=True)
    def assign_incident(self, incident_id: str, assigned_to, assigned_by, team: str = "") -> bool:
        """Assign incident to a user"""
        try:
            with transaction.atomic():
                incident = SecurityIncident.objects.get(incident_id=incident_id)
                
                old_assigned_to = incident.assigned_to
                incident.assigned_to = assigned_to
                incident.assigned_team = team
                incident.updated_by = assigned_by
                incident.last_activity = timezone.now()
                
                # Add assignment note
                timestamp = timezone.now().isoformat()
                old_assignee = old_assigned_to.username if old_assigned_to else "Unassigned"
                new_assignee = assigned_to.username
                incident.notes += f"\n\n[{timestamp}] Assigned from {old_assignee} to {new_assignee} by {assigned_by.username}"
                
                incident.save()
                
                logger.info(f"Incident {incident_id} assigned to {assigned_to.username}")
                
                # Clear cache
                self._clear_incident_cache(incident.id)
                
                return True
                
        except SecurityIncident.DoesNotExist:
            logger.error(f"Incident {incident_id} not found")
            return False
        except Exception as e:
            logger.error(f"Failed to assign incident: {e}")
            return False
    
    @classmethod
    def get_service_instance(cls) -> 'IncidentService':
        """Get singleton instance of the service"""
        if not hasattr(cls, '_instance'):
            cls._instance = cls()
        return cls._instance