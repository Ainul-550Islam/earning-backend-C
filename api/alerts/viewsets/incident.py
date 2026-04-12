"""
Incident ViewSets
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
import logging

from ..models.incident import (
    Incident, IncidentTimeline, IncidentResponder, IncidentPostMortem, OnCallSchedule
)

logger = logging.getLogger(__name__)


class IncidentViewSet(viewsets.ModelViewSet):
    """Incident ViewSet for CRUD operations"""
    queryset = Incident.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('assigned_to', 'created_by', 'updated_by')
        
        # Apply filters
        severity = self.request.query_params.get('severity')
        impact = self.request.query_params.get('impact')
        status = self.request.query_params.get('status')
        assigned_to = self.request.query_params.get('assigned_to')
        
        if severity:
            queryset = queryset.filter(severity=severity)
        if impact:
            queryset = queryset.filter(impact=impact)
        if status:
            queryset = queryset.filter(status=status)
        if assigned_to:
            queryset = queryset.filter(assigned_to_id=assigned_to)
        
        return queryset.order_by('-detected_at')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.incident import IncidentSerializer
        return IncidentSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def get_permissions(self):
        if self.action in ['acknowledge', 'identify', 'resolve', 'close', 'mark_false_positive']:
            return [IsAuthenticated, IsAdminUser]
        return [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge incident"""
        try:
            incident = self.get_object()
            success = incident.acknowledge(request.user)
            
            if success:
                # Add timeline event
                IncidentTimeline.add_event(
                    incident, 'acknowledged', 'Incident Acknowledged',
                    f'Incident acknowledged by {request.user.get_full_name() or request.user.username}',
                    request.user
                )
                
                return Response({'success': True, 'acknowledged_at': incident.acknowledged_at})
            else:
                return Response({'error': 'Already acknowledged'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error acknowledging incident: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error identifying incident: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve incident"""
        try:
            incident = self.get_object()
            resolution_summary = request.data.get('resolution_summary', '')
            
            success = incident.resolve(request.user, resolution_summary)
            
            if success:
                # Add timeline event
                IncidentTimeline.add_event(
                    incident, 'resolved', 'Incident Resolved',
                    f'Incident resolved: {resolution_summary}',
                    request.user
                )
                
                return Response({
                    'success': True, 
                    'resolved_at': incident.resolved_at,
                    'total_downtime_minutes': incident.total_downtime_minutes
                })
            else:
                return Response({'error': 'Cannot resolve incident in current status'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error resolving incident: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close incident"""
        try:
            incident = self.get_object()
            success = incident.close(request.user)
            
            if success:
                # Add timeline event
                IncidentTimeline.add_event(
                    incident, 'closed', 'Incident Closed',
                    f'Incident closed by {request.user.get_full_name() or request.user.username}',
                    request.user
                )
                
                return Response({'success': True, 'closed_at': incident.closed_at})
            else:
                return Response({'error': 'Cannot close incident in current status'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error closing incident: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error marking incident as false positive: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error getting incident timeline: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error calculating severity score: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
            for status in ['open', 'investigating', 'identified', 'monitoring', 'resolved', 'closed', 'false_positive']:
                stats['by_status'][status] = incidents.filter(status=status).count()
            
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
        except Exception as e:
            logger.error(f"Error getting incident stats: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IncidentTimelineViewSet(viewsets.ModelViewSet):
    """IncidentTimeline ViewSet for CRUD operations"""
    queryset = IncidentTimeline.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('incident', 'created_by')
        
        # Apply filters
        incident_id = self.request.query_params.get('incident_id')
        event_type = self.request.query_params.get('event_type')
        
        if incident_id:
            queryset = queryset.filter(incident_id=incident_id)
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        return queryset.order_by('timestamp')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.incident import IncidentTimelineSerializer
        return IncidentTimelineSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['post'])
    def add_event(self, request):
        """Add timeline event to incident"""
        try:
            incident_id = request.data.get('incident_id')
            event_type = request.data.get('event_type')
            title = request.data.get('title')
            description = request.data.get('description', '')
            
            if not all([incident_id, event_type, title]):
                return Response({'error': 'incident_id, event_type, and title are required'}, status=status.HTTP_400_BAD_REQUEST)
            
            from ..models.incident import Incident
            incident = Incident.objects.get(id=incident_id)
            
            event = IncidentTimeline.add_event(
                incident, event_type, title, description, request.user,
                **request.data
            )
            
            return Response({'success': True, 'event_id': event.id})
        except Incident.DoesNotExist:
            return Response({'error': 'Incident not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error adding timeline event: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IncidentResponderViewSet(viewsets.ModelViewSet):
    """IncidentResponder ViewSet for CRUD operations"""
    queryset = IncidentResponder.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('incident', 'user')
        
        # Apply filters
        incident_id = self.request.query_params.get('incident_id')
        role = self.request.query_params.get('role')
        status = self.request.query_params.get('status')
        
        if incident_id:
            queryset = queryset.filter(incident_id=incident_id)
        if role:
            queryset = queryset.filter(role=role)
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('role', 'assigned_at')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.incident import IncidentResponderSerializer
        return IncidentResponderSerializer
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate responder"""
        try:
            responder = self.get_object()
            success = responder.activate()
            
            if success:
                return Response({'success': True, 'active_at': responder.active_at})
            else:
                return Response({'error': 'Cannot activate responder in current status'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error activating responder: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete responder assignment"""
        try:
            responder = self.get_object()
            success = responder.complete()
            
            if success:
                return Response({'success': True, 'completed_at': responder.completed_at})
            else:
                return Response({'error': 'Cannot complete responder in current status'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error completing responder: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        """Check responder availability"""
        try:
            responder = self.get_object()
            
            return Response({
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
        except Exception as e:
            logger.error(f"Error checking responder availability: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IncidentPostMortemViewSet(viewsets.ModelViewSet):
    """IncidentPostMortem ViewSet for CRUD operations"""
    queryset = IncidentPostMortem.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('incident', 'created_by', 'reviewed_by', 'approved_by')
        
        # Apply filters
        incident_id = self.request.query_params.get('incident_id')
        status = self.request.query_params.get('status')
        
        if incident_id:
            queryset = queryset.filter(incident_id=incident_id)
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-created_at')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.incident import IncidentPostMortemSerializer
        return IncidentPostMortemSerializer
    
    def get_permissions(self):
        if self.action in ['submit_for_review', 'approve', 'publish']:
            return [IsAuthenticated, IsAdminUser]
        return [IsAuthenticated]
    
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
        except Exception as e:
            logger.error(f"Error submitting post-mortem for review: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error approving post-mortem: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error publishing post-mortem: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def completion_score(self, request, pk=None):
        """Get post-mortem completion score"""
        try:
            post_mortem = self.get_object()
            score = post_mortem.get_completion_score()
            
            return Response({'completion_score': score})
        except Exception as e:
            logger.error(f"Error calculating completion score: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OnCallScheduleViewSet(viewsets.ModelViewSet):
    """OnCallSchedule ViewSet for CRUD operations"""
    queryset = OnCallSchedule.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('primary_users', 'backup_users', 'escalation_users')
        
        # Apply filters
        schedule_type = self.request.query_params.get('schedule_type')
        is_active = self.request.query_params.get('is_active')
        
        if schedule_type:
            queryset = queryset.filter(schedule_type=schedule_type)
        if is_active is not None and is_active != '':
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.order_by('name')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.incident import OnCallScheduleSerializer
        return OnCallScheduleSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def current_on_call(self, request, pk=None):
        """Get current on-call person"""
        try:
            schedule = self.get_object()
            current_on_call = schedule.get_current_on_call()
            
            if current_on_call:
                return Response({
                    'user_id': current_on_call.id,
                    'username': current_on_call.username,
                    'full_name': current_on_call.get_full_name(),
                    'email': current_on_call.email
                })
            else:
                return Response({'message': 'No one currently on call'})
        except Exception as e:
            logger.error(f"Error getting current on-call: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def escalation_chain(self, request, pk=None):
        """Get escalation chain"""
        try:
            schedule = self.get_object()
            escalation_chain = schedule.get_escalation_chain()
            
            return Response(escalation_chain)
        except Exception as e:
            logger.error(f"Error getting escalation chain: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def upcoming_schedule(self, request, pk=None):
        """Get upcoming on-call schedule"""
        try:
            schedule = self.get_object()
            days = int(request.query_params.get('days', 30))
            
            upcoming = schedule.get_upcoming_schedule(days)
            
            return Response(upcoming)
        except Exception as e:
            logger.error(f"Error getting upcoming schedule: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def is_on_call(self, request, pk=None):
        """Check if user is on call"""
        try:
            schedule = self.get_object()
            user_id = request.data.get('user_id')
            
            if not user_id:
                return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            
            is_on_call = schedule.is_on_call(user)
            
            return Response({'is_on_call': is_on_call})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error checking on-call status: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def all_current_on_call(self, request):
        """Get all current on-call personnel"""
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
                            'id': current.id,
                            'username': current.username,
                            'full_name': current.get_full_name(),
                            'email': current.email
                        }
                    })
            
            return Response(current_on_calls)
        except Exception as e:
            logger.error(f"Error getting all current on-calls: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
