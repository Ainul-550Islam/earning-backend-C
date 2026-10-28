"""
Incident ViewSets
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from ..permissions import (
    IsAlertManager, CanResolveAlerts, CanAcknowledgeAlerts,
    IsInAlertTeam, CanViewSensitiveData,
)
from django.utils import timezone
from datetime import timedelta
import logging

from ..models.incident import (
    Incident, IncidentTimeline, IncidentResponder, IncidentPostMortem, OnCallSchedule
)
from ..services.incident.incident_manager import IncidentManager
from .mixins import PASSTHROUGH_EXCEPTIONS  # re-raise 404/403/400 instead of 500

from api.alerts.mixins import TenantIsolationMixin

logger = logging.getLogger(__name__)


class IncidentViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """Incident ViewSet — tenant-scoped CRUD"""
    queryset = Incident.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().select_related('assigned_to', 'created_by', 'updated_by')

        severity = self.request.query_params.get('severity')
        impact = self.request.query_params.get('impact')
        filter_status = self.request.query_params.get('status')
        assigned_to = self.request.query_params.get('assigned_to')

        if severity:
            queryset = queryset.filter(severity=severity)
        if impact:
            queryset = queryset.filter(impact=impact)
        if filter_status:
            queryset = queryset.filter(status=filter_status)
        if assigned_to:
            queryset = queryset.filter(assigned_to_id=assigned_to)

        return queryset.order_by('-detected_at')

    def get_serializer_class(self):
        from ..serializers.incident import IncidentSerializer
        return IncidentSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, **self.tenant_save_kwargs())

    def get_permissions(self):
        """
        list / retrieve / timeline        → IsInAlertTeam (sensitive data)
        create / update / destroy         → IsAlertManager
        acknowledge                        → CanAcknowledgeAlerts
        identify / resolve / close        → CanResolveAlerts
        mark_false_positive               → IsAlertManager
        """
        if self.action in ['acknowledge']:
            return [IsAuthenticated(), CanAcknowledgeAlerts()]
        if self.action in ['identify', 'resolve', 'close']:
            return [IsAuthenticated(), CanResolveAlerts()]
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                            'mark_false_positive', 'assign']:
            return [IsAuthenticated(), IsAlertManager()]
        if self.action in ['list', 'retrieve', 'timeline']:
            return [IsAuthenticated(), IsInAlertTeam()]
        return [IsAuthenticated()]


    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge incident — delegates to IncidentManager.update_status"""
        try:
            incident = self.get_object()
            notes = request.data.get('notes', '')
            # Delegate to IncidentManager so escalation, timeline, and audit all happen in one place
            updated = IncidentManager.update_status(incident, 'acknowledged', request.user, notes=notes)
            if updated:
                return Response({'success': True, 'acknowledged_at': incident.acknowledged_at})
            else:
                return Response({'error': 'Already acknowledged'}, status=status.HTTP_400_BAD_REQUEST)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except ValueError as ve:
            return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error acknowledging incident: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def identify(self, request, pk=None):
        """Mark incident as identified"""
        try:
            incident = self.get_object()
            root_cause = request.data.get('root_cause', '')
            
            success = incident.identify(request.user, root_cause)
            
            if success:
                # Add timeline event
                IncidentTimeline.add_event(
                    incident, 'identified', 'Root Cause Identified',
                    f'Root cause identified: {root_cause}',
                    request.user
                )
                
                return Response({'success': True, 'identified_at': incident.identified_at})
            else:
                return Response({'error': 'Cannot identify incident in current status'}, status=status.HTTP_400_BAD_REQUEST)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error identifying incident: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve incident — delegates to IncidentManager.update_status"""
        try:
            incident = self.get_object()
            resolution_summary = request.data.get('resolution_summary', '')
            updated = IncidentManager.update_status(
                incident, 'resolved', request.user, notes=resolution_summary
            )
            if updated:
                return Response({
                    'success': True,
                    'resolved_at': incident.resolved_at,
                    'total_downtime_minutes': incident.total_downtime_minutes
                })
            else:
                return Response({'error': 'Cannot resolve incident in current status'}, status=status.HTTP_400_BAD_REQUEST)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except ValueError as ve:
            return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error resolving incident: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close incident — delegates to IncidentManager.update_status"""
        try:
            incident = self.get_object()
            notes = request.data.get('notes', '')
            updated = IncidentManager.update_status(incident, 'closed', request.user, notes=notes)
            if updated:
                return Response({'success': True, 'closed_at': incident.closed_at})
            else:
                return Response({'error': 'Cannot close incident in current status'}, status=status.HTTP_400_BAD_REQUEST)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except ValueError as ve:
            return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error closing incident: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def mark_false_positive(self, request, pk=None):
        """Mark incident as false positive"""
        try:
            incident = self.get_object()
            incident.mark_false_positive(request.user)
            
            # Add timeline event
            IncidentTimeline.add_event(
                incident, 'update', 'Marked as False Positive',
                f'Incident marked as false positive by {request.user.get_full_name() or request.user.username}',
                request.user
            )
            
            return Response({'success': True, 'closed_at': incident.closed_at})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error marking incident as false positive: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        """Get incident timeline"""
        try:
            incident = self.get_object()
            timeline = IncidentTimeline.objects.filter(incident=incident).order_by('timestamp')
            
            timeline_data = []
            for event in timeline:
                timeline_data.append({
                    'id': event.id,
                    'event_type': event.event_type,
                    'title': event.title,
                    'description': event.description,
                    'timestamp': event.timestamp,
                    'created_by': event.created_by.get_full_name() if event.created_by else 'System',
                    'participants': event.participants,
                    'event_data': event.event_data
                })
            
            return Response(timeline_data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting incident timeline: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def severity_score(self, request, pk=None):
        """Get incident severity score"""
        try:
            incident = self.get_object()
            score = incident.get_severity_score()
            
            return Response({
                'severity_score': score,
                'severity': incident.severity,
                'impact': incident.impact,
                'urgency': incident.urgency
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error calculating severity score: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def escalation_chain(self, request, pk=None):
        """Get the current escalation state and responder chain for an incident"""
        try:
            incident = self.get_object()
            role_order = [
                'incident_commander', 'technical_lead', 'communications_lead',
                'subject_matter_expert', 'lead', 'manager', 'escalation',
                'stakeholder', 'responder', 'observer',
            ]
            responders = list(incident.get_responders())
            responders.sort(key=lambda r: (
                role_order.index(r.role) if r.role in role_order else len(role_order),
                r.assigned_at,
            ))
            return Response({
                'incident_id': incident.id,
                'escalation_level': incident.escalation_level,
                'escalation_reason': incident.escalation_reason,
                'escalated_at': incident.escalated_at,
                'should_escalate': incident.should_escalate(),
                'chain': [
                    {
                        'responder_id': r.id, 'user_id': r.user_id,
                        'role': r.role, 'status': r.status,
                        'assigned_at': r.assigned_at,
                    }
                    for r in responders
                ],
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting escalation chain for incident {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Incident statistics"""
        try:
            days = int(request.query_params.get('days', 30))
            cutoff_date = timezone.now() - timedelta(days=days)
            
            incidents = Incident.objects.filter(detected_at__gte=cutoff_date)
            
            stats = {
                'total_incidents': incidents.count(),
                'by_status': {},
                'by_severity': {},
                'by_impact': {},
                'average_resolution_time': 0,
                'mttr': 0
            }
            
            # By status
            for incident_status in ['open', 'investigating', 'identified', 'monitoring', 'resolved', 'closed', 'false_positive']:
                stats['by_status'][incident_status] = incidents.filter(status=incident_status).count()
            
            # By severity
            for severity in ['low', 'medium', 'high', 'critical']:
                stats['by_severity'][severity] = incidents.filter(severity=severity).count()
            
            # By impact
            for impact in ['none', 'minimal', 'minor', 'major', 'severe', 'critical']:
                stats['by_impact'][impact] = incidents.filter(impact=impact).count()
            
            # Average resolution time
            resolved_incidents = incidents.filter(resolved_at__isnull=False)
            if resolved_incidents.exists():
                total_time = sum(
                    (incident.resolved_at - incident.detected_at).total_seconds() / 60
                    for incident in resolved_incidents
                )
                stats['average_resolution_time'] = total_time / resolved_incidents.count()
                stats['mttr'] = stats['average_resolution_time']
            
            return Response(stats)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting incident stats: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IncidentTimelineViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """IncidentTimeline ViewSet — tenant-scoped CRUD"""
    queryset = IncidentTimeline.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().select_related('incident', 'created_by')

        incident_id = self.request.query_params.get('incident_id')
        event_type = self.request.query_params.get('event_type')

        if incident_id:
            queryset = queryset.filter(incident_id=incident_id)
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        return queryset.order_by('timestamp')

    def get_serializer_class(self):
        from ..serializers.incident import IncidentTimelineSerializer
        return IncidentTimelineSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, **self.tenant_save_kwargs())

    def get_permissions(self):
        """
        list / retrieve → IsInAlertTeam (incident data is sensitive)
        create / add_event / destroy → IsInAlertTeam (team members record events)
        update / partial_update → IsAlertManager (only managers edit history)
        """
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAlertManager()]
        return [IsAuthenticated(), IsInAlertTeam()]


    @action(detail=False, methods=['post'])
    def add_event(self, request, pk=None):
        """Add timeline event to incident.

        POST timelines/add_event/         -> incident_id comes from the body
        POST timelines/<pk>/add-event/    -> when the body has no incident_id, the event
                                             is added to the incident of timeline <pk>
        """
        from ..models.incident import Incident
        try:
            incident_id = request.data.get('incident_id')
            if not incident_id and pk is not None:
                incident_id = self.get_object().incident_id
            event_type = request.data.get('event_type')
            title = request.data.get('title')
            description = request.data.get('description', '')

            if not all([incident_id, event_type, title]):
                return Response({'error': 'incident_id, event_type, and title are required'}, status=status.HTTP_400_BAD_REQUEST)

            incident = Incident.objects.get(id=incident_id)

            # Only optional, client-settable columns are forwarded.  Splatting the whole
            # request body collided with the positional args (event_type/title/description
            # -> TypeError on every call) and let clients set id/incident/tenant.
            allowed_extra = (
                'timestamp', 'duration_minutes', 'participants', 'event_data',
                'attachments', 'users_affected', 'services_affected', 'metrics_affected',
            )
            extra = {k: request.data[k] for k in allowed_extra if k in request.data}
            event = IncidentTimeline.add_event(
                incident, event_type, title, description, request.user,
                **extra
            )

            return Response({'success': True, 'event_id': event.id})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Incident.DoesNotExist:
            return Response({'error': 'Incident not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error adding timeline event: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def by_incident(self, request, incident_id=None, **kwargs):
        iid = incident_id or self.kwargs.get('incident_id') or request.query_params.get('incident_id')
        qs = self.get_queryset()
        if iid:
            qs = qs.filter(incident_id=iid)
        from ..serializers.incident import IncidentTimelineSerializer
        return Response({'count': qs.count(), 'results': IncidentTimelineSerializer(qs, many=True).data})

    @action(detail=False, methods=['get'])
    def by_type(self, request, type=None, **kwargs):
        t = type or self.kwargs.get('type') or request.query_params.get('type', '')
        qs = self.get_queryset().filter(event_type=t)
        from ..serializers.incident import IncidentTimelineSerializer
        return Response({'count': qs.count(), 'results': IncidentTimelineSerializer(qs, many=True).data})

    @action(detail=True, methods=['post'])
    def add_participant(self, request, pk=None):
        """Add a user id to this timeline entry's participants list"""
        try:
            entry = self.get_object()
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({'error': 'user_id required'}, status=status.HTTP_400_BAD_REQUEST)
            if user_id not in entry.participants:
                entry.participants.append(user_id)
                entry.save(update_fields=['participants'])
            return Response({'success': True, 'participants': entry.participants})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error adding participant to timeline entry {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# NOTE: IncidentResponderViewSet used to be duplicate-defined here with a
# CRUD-only body plus a get_permissions() override. It was entirely shadowed
# (dead code) by the second IncidentResponderViewSet class later in this file,
# which is the one urls/incident.py actually resolves to at runtime. Its
# unique get_permissions() has been merged into that surviving definition
# below; the redundant duplicate class itself has been removed.


class IncidentPostMortemViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """IncidentPostMortem ViewSet — tenant-scoped CRUD"""
    queryset = IncidentPostMortem.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().select_related('incident', 'created_by', 'reviewed_by', 'approved_by')

        incident_id = self.request.query_params.get('incident_id')
        filter_status = self.request.query_params.get('status')

        if incident_id:
            queryset = queryset.filter(incident_id=incident_id)
        if filter_status:
            queryset = queryset.filter(status=filter_status)

        return queryset.order_by('-created_at')

    def get_serializer_class(self):
        from ..serializers.incident import IncidentPostMortemSerializer
        return IncidentPostMortemSerializer

    def get_permissions(self):
        """
        list / retrieve           → IsInAlertTeam
        create / update           → IsInAlertTeam (authors are team members)
        submit_for_review         → IsInAlertTeam
        approve / publish         → IsAlertManager (only managers approve/publish)
        destroy                   → IsAlertManager
        """
        if self.action in ['approve', 'publish', 'destroy']:
            return [IsAuthenticated(), IsAlertManager()]
        return [IsAuthenticated(), IsInAlertTeam()]


    @action(detail=True, methods=['post'])
    def submit_for_review(self, request, pk=None):
        """Submit post-mortem for review"""
        try:
            post_mortem = self.get_object()
            success = post_mortem.submit_for_review(request.user)
            
            if success:
                return Response({'success': True, 'status': post_mortem.status})
            else:
                return Response({'error': 'Cannot submit in current status'}, status=status.HTTP_400_BAD_REQUEST)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error submitting post-mortem for review: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve post-mortem"""
        try:
            post_mortem = self.get_object()
            success = post_mortem.approve(request.user)
            
            if success:
                return Response({'success': True, 'status': post_mortem.status, 'approved_at': timezone.now()})
            else:
                return Response({'error': 'Cannot approve in current status'}, status=status.HTTP_400_BAD_REQUEST)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error approving post-mortem: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject post-mortem"""
        try:
            post_mortem = self.get_object()
            note = request.data.get('note', '')
            success = post_mortem.reject(request.user, note)
            
            if success:
                return Response({'success': True, 'status': post_mortem.status})
            else:
                return Response({'error': 'Cannot reject in current status'}, status=status.HTTP_400_BAD_REQUEST)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error rejecting post-mortem: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def by_status(self, request, status=None, **kwargs):
        s = status or self.kwargs.get('status') or request.query_params.get('status', '')
        qs = self.get_queryset().filter(status=s)
        serializer = self.get_serializer(qs, many=True)
        return Response({'count': qs.count(), 'results': serializer.data})

    @action(detail=False, methods=['get'])
    def by_incident(self, request, incident_id=None, **kwargs):
        iid = incident_id or self.kwargs.get('incident_id') or request.query_params.get('incident_id')
        qs = self.get_queryset()
        if iid:
            qs = qs.filter(incident_id=iid)
        serializer = self.get_serializer(qs, many=True)
        return Response({'count': qs.count(), 'results': serializer.data})
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publish post-mortem"""
        try:
            post_mortem = self.get_object()
            internal_only = request.data.get('internal_only', True)
            success = post_mortem.publish(internal_only)
            
            if success:
                return Response({
                    'success': True, 
                    'status': post_mortem.status, 
                    'published_at': post_mortem.published_at,
                    'internal_only': post_mortem.internal_only
                })
            else:
                return Response({'error': 'Cannot publish in current status'}, status=status.HTTP_400_BAD_REQUEST)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error publishing post-mortem: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def completion_score(self, request, pk=None):
        """Get post-mortem completion score"""
        try:
            post_mortem = self.get_object()
            score = post_mortem.get_completion_score()
            
            return Response({'completion_score': score})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error calculating completion score: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# NOTE: OnCallScheduleViewSet used to be duplicate-defined here. It was
# entirely shadowed (dead code) by the second OnCallScheduleViewSet class
# later in this file, which is the one urls/incident.py actually resolves to
# at runtime. This definition's unique get_queryset (filtering + prefetch_related),
# perform_create (tenant scoping on create), get_permissions (IsAlertManager
# gating on create/update/destroy/rotate/deactivate/next_rotation), and the
# escalation_chain action have been merged into that surviving definition
# below; the redundant duplicate class itself has been removed.

from datetime import timedelta as _td
from django.utils import timezone as _tz


# IncidentViewSet missing actions
def _incident_active(self, request):
    """List all open/active incidents"""
    try:
        incidents = Incident.objects.filter(
            status__in=['open', 'acknowledged', 'identified']
        ).select_related('assigned_to', 'created_by').order_by('-detected_at')
        from ..serializers.incident import IncidentSerializer
        return Response({'count': incidents.count(), 'results': IncidentSerializer(incidents, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error listing active incidents: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

IncidentViewSet.active = action(detail=False, methods=['get'])(_incident_active)


def _incident_overdue(self, request):
    """List overdue incidents (open > 4h without resolution)"""
    try:
        threshold = _tz.now() - _td(hours=4)
        incidents = Incident.objects.filter(
            status__in=['open', 'acknowledged'],
            detected_at__lt=threshold
        ).select_related('assigned_to').order_by('detected_at')
        from ..serializers.incident import IncidentSerializer
        return Response({'count': incidents.count(), 'results': IncidentSerializer(incidents, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error listing overdue incidents: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

IncidentViewSet.overdue = action(detail=False, methods=['get'])(_incident_overdue)


def _incident_by_severity(self, request, severity=None, **kwargs):
    """Get incidents filtered by severity (URL path or query param)"""
    try:
        sev = severity or getattr(self, 'kwargs', {}).get('severity') or request.query_params.get('severity')
        if not sev:
            return Response({'error': 'severity param required'}, status=status.HTTP_400_BAD_REQUEST)
        incidents = Incident.objects.filter(severity=sev).order_by('-detected_at')
        from ..serializers.incident import IncidentSerializer
        return Response({'severity': sev, 'count': incidents.count(), 'results': IncidentSerializer(incidents, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting incidents by severity: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

IncidentViewSet.by_severity = action(detail=False, methods=['get'])(_incident_by_severity)


def _incident_by_status(self, request, **kwargs):
    """Get incidents filtered by status (URL path or query param)"""
    try:
        inc_status = kwargs.get('status') or getattr(self, 'kwargs', {}).get('status') or request.query_params.get('status')
        if not inc_status:
            return Response({'error': 'status param required'}, status=status.HTTP_400_BAD_REQUEST)
        incidents = Incident.objects.filter(status=inc_status).order_by('-detected_at')
        from ..serializers.incident import IncidentSerializer
        return Response({'status': inc_status, 'count': incidents.count(), 'results': IncidentSerializer(incidents, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting incidents by status: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

IncidentViewSet.by_status = action(detail=False, methods=['get'])(_incident_by_status)


def _incident_escalate(self, request, pk=None):
    """Escalate an incident to higher severity"""
    try:
        incident = self.get_object()
        new_severity = request.data.get('severity', 'critical')
        reason = request.data.get('reason', '')
        old_severity = incident.severity
        incident.severity = new_severity
        incident.save(update_fields=['severity'])
        IncidentTimeline.add_event(
            incident, 'escalated', 'Incident Escalated',
            f'Severity escalated from {old_severity} to {new_severity}. Reason: {reason}',
            request.user
        )
        return Response({'success': True, 'old_severity': old_severity, 'new_severity': new_severity})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error escalating incident {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

IncidentViewSet.escalate = action(detail=True, methods=['post'])(_incident_escalate)


def _incident_create_from_alert(self, request):
    """Create incident from one or more alert logs"""
    try:
        from ..models.core import AlertLog
        alert_log_ids = request.data.get('alert_log_ids', [])
        title = request.data.get('title', 'Auto-created incident')
        severity = request.data.get('severity', 'high')
        if not alert_log_ids:
            return Response({'error': 'alert_log_ids required'}, status=status.HTTP_400_BAD_REQUEST)
        logs = AlertLog.objects.filter(id__in=alert_log_ids)
        incident = Incident.objects.create(
            title=title, description=f'Created from {logs.count()} alert(s)',
            severity=severity, status='open', created_by=request.user,
        )
        for log in logs:
            if hasattr(incident, 'alert_logs'):
                incident.alert_logs.add(log)
        from ..serializers.incident import IncidentSerializer
        return Response(IncidentSerializer(incident).data, status=status.HTTP_201_CREATED)
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error creating incident from alert: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

IncidentViewSet.create_from_alert = action(detail=False, methods=['post'])(_incident_create_from_alert)


# IncidentResponderViewSet missing actions
def _responder_add_user(self, request, pk=None):
    """Add user as responder to incident"""
    try:
        responder = self.get_object()
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'user_id required'}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.get(id=user_id)
        responder.users.add(user) if hasattr(responder, 'users') else None
        return Response({'success': True, 'user_id': user_id})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error adding user to responder: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _responder_remove_user(self, request, pk=None):
    """Remove user from responder"""
    try:
        responder = self.get_object()
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'user_id required'}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.get(id=user_id)
        responder.users.remove(user) if hasattr(responder, 'users') else None
        return Response({'success': True})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error removing user from responder: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _responder_by_incident(self, request, incident_id=None, **kwargs):
    """Get responders for a specific incident (URL path or query param)"""
    try:
        iid = incident_id or getattr(self, 'kwargs', {}).get('incident_id') or request.query_params.get('incident_id')
        if not iid:
            return Response({'error': 'incident_id required'}, status=status.HTTP_400_BAD_REQUEST)
        responders = IncidentResponder.objects.filter(incident_id=iid)
        from ..serializers.incident import IncidentResponderSerializer
        return Response({'count': responders.count(), 'results': IncidentResponderSerializer(responders, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting responders by incident: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _responder_by_role(self, request, role=None, **kwargs):
    """Get responders filtered by role (URL path or query param)"""
    try:
        r = role or getattr(self, 'kwargs', {}).get('role') or request.query_params.get('role')
        if not r:
            return Response({'error': 'role param required'}, status=status.HTTP_400_BAD_REQUEST)
        responders = IncidentResponder.objects.filter(role=r)
        from ..serializers.incident import IncidentResponderSerializer
        return Response({'role': r, 'count': responders.count(), 'results': IncidentResponderSerializer(responders, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting responders by role: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IncidentResponderViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """IncidentResponder ViewSet — tenant-scoped. Includes add_user, remove_user, by_incident, by_role, reject, complete"""
    queryset = IncidentResponder.objects.all()
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """This model has no created_by field, unlike most other models here."""
        serializer.save(**self.tenant_save_kwargs())

    def get_queryset(self):
        queryset = super().get_queryset().select_related('incident', 'user')
        incident_id = self.request.query_params.get('incident_id')
        role = self.request.query_params.get('role')
        if incident_id:
            queryset = queryset.filter(incident_id=incident_id)
        if role:
            queryset = queryset.filter(role=role)
        return queryset.order_by('-assigned_at')

    def get_serializer_class(self):
        from ..serializers.incident import IncidentResponderSerializer
        return IncidentResponderSerializer

    def get_permissions(self):
        """All responder operations require active team membership."""
        if self.action in ['destroy']:
            return [IsAuthenticated(), IsAlertManager()]
        return [IsAuthenticated(), IsInAlertTeam()]

    add_user = action(detail=True, methods=['post'])(_responder_add_user)
    remove_user = action(detail=True, methods=['post'])(_responder_remove_user)
    by_incident = action(detail=False, methods=['get'])(_responder_by_incident)
    by_role = action(detail=False, methods=['get'])(_responder_by_role)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate responder"""
        try:
            responder = self.get_object()
            success = responder.activate()
            if success:
                return Response({'success': True, 'active_at': responder.active_at})
            return Response({'error': 'Cannot activate responder in current status'}, status=status.HTTP_400_BAD_REQUEST)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error activating responder {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Mark responder as away"""
        try:
            responder = self.get_object()
            success = responder.deactivate()
            if success:
                return Response({'success': True, 'status': responder.status})
            return Response({'error': 'Cannot deactivate responder in current status'}, status=status.HTTP_400_BAD_REQUEST)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error deactivating responder {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete responder assignment"""
        try:
            responder = self.get_object()
            success = responder.complete() if hasattr(responder, 'complete') else False
            if success:
                return Response({'success': True, 'completed_at': responder.completed_at})
            return Response({'error': 'Cannot complete responder in current status'}, status=status.HTTP_400_BAD_REQUEST)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error completing responder {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        """Check responder availability"""
        try:
            responder = self.get_object()
            return Response({
                'responder_id': responder.id,
                'is_available': responder.is_available_now(),
                'status': responder.status,
                'role': responder.role,
                'contact_method': responder.contact_method,
                'timezone': responder.timezone,
                'available_hours': {
                    'start': responder.available_hours_start,
                    'end': responder.available_hours_end
                }
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error checking responder availability {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a responder assignment"""
        try:
            responder = self.get_object()
            reason = request.data.get('reason', '')
            responder.status = 'rejected'
            responder.save(update_fields=['status'])
            return Response({'success': True, 'reason': reason})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error rejecting responder {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# OnCallSchedule missing actions
class OnCallScheduleViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """OnCallSchedule ViewSet — tenant-scoped. Includes current_oncall, is_oncall, next_rotation, rotate, deactivate"""
    queryset = OnCallSchedule.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        from ..serializers.incident import OnCallScheduleSerializer
        return OnCallScheduleSerializer

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('primary_users', 'backup_users', 'escalation_users')
        schedule_type = self.request.query_params.get('schedule_type')
        is_active = self.request.query_params.get('is_active')
        if schedule_type:
            queryset = queryset.filter(schedule_type=schedule_type)
        if is_active is not None and is_active != '':
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset.order_by('name')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, **self.tenant_save_kwargs())

    def get_permissions(self):
        """
        list / retrieve / current_oncall / is_oncall → IsInAlertTeam
        create / update / destroy / rotate           → IsAlertManager
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                            'rotate', 'deactivate', 'next_rotation']:
            return [IsAuthenticated(), IsAlertManager()]
        return [IsAuthenticated(), IsInAlertTeam()]

    @action(detail=True, methods=['get'])
    def escalation_chain(self, request, pk=None):
        """Get escalation chain for a schedule"""
        try:
            schedule = self.get_object()
            return Response(schedule.get_escalation_chain())
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting escalation chain {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def current_oncall(self, request, pk=None):
        """Get current on-call person for this schedule"""
        try:
            schedule = self.get_object()
            current = schedule.get_current_on_call()
            return Response({'schedule_id': schedule.id, 'current_oncall': str(current) if current else None})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting current on-call {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def current_on_call(self, request, pk=None):
        """Get current on-call person for this schedule (full detail)"""
        try:
            schedule = self.get_object()
            current = schedule.get_current_on_call()
            if current:
                return Response({
                    'user_id': current.id, 'username': current.username,
                    'full_name': current.get_full_name(), 'email': current.email,
                })
            return Response({'message': 'No one currently on call'})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting current on-call {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def upcoming_schedule(self, request, pk=None):
        """Get upcoming on-call schedule"""
        try:
            schedule = self.get_object()
            days = int(request.query_params.get('days', 30))
            return Response(schedule.get_upcoming_schedule(days))
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting upcoming schedule {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        """Get user availability summary for this schedule"""
        try:
            schedule = self.get_object()
            current = schedule.get_current_on_call()
            return Response({
                'schedule_id': schedule.id,
                'is_active': schedule.is_active,
                'users_count': schedule.get_users_count(),
                'current_on_call': current.id if current else None,
                'next_rotation': schedule.get_next_rotation(),
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting availability {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def add_user(self, request, pk=None):
        """Add a user to this schedule's primary rotation"""
        try:
            schedule = self.get_object()
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({'error': 'user_id required'}, status=status.HTTP_400_BAD_REQUEST)
            user = User.objects.get(id=user_id)
            schedule.add_user(user)
            return Response({'success': True, 'user_id': user_id})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error adding user to schedule {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def remove_user(self, request, pk=None):
        """Remove a user from this schedule's primary rotation"""
        try:
            schedule = self.get_object()
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({'error': 'user_id required'}, status=status.HTTP_400_BAD_REQUEST)
            user = User.objects.get(id=user_id)
            schedule.remove_user(user)
            return Response({'success': True})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error removing user from schedule {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def is_oncall(self, request, pk=None, user_id=None):
        """Check if a specific user is on-call now (user_id from URL path or query param)"""
        try:
            schedule = self.get_object()
            uid = user_id or self.kwargs.get('user_id') or request.query_params.get('user_id')
            if not uid:
                return Response({'error': 'user_id required'}, status=status.HTTP_400_BAD_REQUEST)
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=uid)
            result = schedule.is_user_on_call(user)
            return Response({'user_id': uid, 'is_oncall': result})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error checking on-call status {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def is_on_call(self, request, pk=None):
        """Check if a specific user is on-call now (accepts user_id as query param)"""
        try:
            schedule = self.get_object()
            user_id = request.query_params.get('user_id')
            if not user_id:
                return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            return Response({'is_on_call': schedule.is_on_call(user)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error checking on-call status {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def all_current_on_call(self, request):
        """Get all current on-call personnel across active schedules"""
        try:
            schedules = OnCallSchedule.objects.filter(is_active=True)
            current_on_calls = []
            for schedule in schedules:
                current = schedule.get_current_on_call()
                if current:
                    current_on_calls.append({
                        'schedule_id': schedule.id,
                        'schedule_name': schedule.name,
                        'schedule_type': schedule.schedule_type,
                        'user': {
                            'id': current.id, 'username': current.username,
                            'full_name': current.get_full_name(), 'email': current.email,
                        }
                    })
            return Response(current_on_calls)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting all current on-calls: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def next_rotation(self, request, pk=None):
        """Get next rotation info"""
        try:
            schedule = self.get_object()
            next_info = schedule.get_next_rotation() if hasattr(schedule, 'get_next_rotation') else {}
            return Response({'schedule_id': schedule.id, 'next_rotation': next_info})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting next rotation {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def rotate(self, request, pk=None):
        """Trigger manual rotation"""
        try:
            schedule = self.get_object()
            if hasattr(schedule, 'rotate'):
                schedule.rotate()
            return Response({'success': True, 'message': 'Rotation triggered'})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error rotating schedule {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """List active on-call schedules"""
        qs = self.get_queryset().filter(is_active=True)
        from ..serializers.incident import OnCallScheduleSerializer
        return Response(OnCallScheduleSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate an on-call schedule"""
        try:
            schedule = self.get_object()
            schedule.is_active = False
            schedule.save(update_fields=['is_active'])
            return Response({'success': True, 'is_active': False})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error deactivating schedule {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def by_type(self, request, type=None, **kwargs):
        """Get schedules by schedule_type (URL path or query param)"""
        try:
            t = type or self.kwargs.get('type') or request.query_params.get('type')
            qs = OnCallSchedule.objects.all()
            if t:
                qs = qs.filter(schedule_type=t)
            from ..serializers.incident import OnCallScheduleSerializer
            return Response({'count': qs.count(), 'results': OnCallScheduleSerializer(qs, many=True).data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting schedules by type: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
