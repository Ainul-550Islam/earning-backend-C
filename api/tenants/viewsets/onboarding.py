"""
Onboarding Viewsets

This module contains viewsets for onboarding-related models including
TenantOnboarding, TenantOnboardingStep, and TenantTrialExtension.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q

from ..models.onboarding import TenantOnboarding, TenantOnboardingStep, TenantTrialExtension
from ..serializers.onboarding import (
    TenantOnboardingSerializer, TenantOnboardingStepSerializer,
    TenantOnboardingStepCompleteSerializer, TenantTrialExtensionSerializer,
    TenantTrialExtensionCreateSerializer
)
from ..services import OnboardingService


class TenantOnboardingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenant onboarding.
    """
    serializer_class = TenantOnboardingSerializer
    queryset = TenantOnboarding.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'status', 'completion_pct']
    search_fields = ['notes', 'feedback']
    ordering_fields = ['created_at', 'completion_pct']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset to tenant's onboarding."""
        if self.request.user.is_superuser:
            return TenantOnboarding.objects.all()
        return TenantOnboarding.objects.filter(tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start onboarding process."""
        onboarding = self.get_object()
        
        if onboarding.status != 'not_started':
            return Response(
                {'error': 'Onboarding has already started'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        started_onboarding = OnboardingService.start_onboarding(onboarding.tenant, request.user)
        serializer = self.get_serializer(started_onboarding)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete onboarding process."""
        onboarding = self.get_object()
        
        if onboarding.status != 'in_progress':
            return Response(
                {'error': 'Onboarding must be in progress to complete'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        onboarding.complete_onboarding()
        serializer = self.get_serializer(onboarding)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause onboarding process."""
        onboarding = self.get_object()
        
        if onboarding.status != 'in_progress':
            return Response(
                {'error': 'Onboarding must be in progress to pause'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        onboarding.pause_onboarding()
        return Response({'message': 'Onboarding paused'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def skip_welcome(self, request, pk=None):
        """Skip welcome step."""
        onboarding = self.get_object()
        
        if not onboarding.skip_welcome:
            onboarding.skip_welcome = True
            onboarding.save(update_fields=['skip_welcome'])
        
        return Response({'message': 'Welcome step skipped'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def toggle_tips(self, request, pk=None):
        """Toggle onboarding tips."""
        onboarding = self.get_object()
        
        onboarding.enable_tips = not onboarding.enable_tips
        onboarding.save(update_fields=['enable_tips'])
        
        return Response({
            'enable_tips': onboarding.enable_tips,
            'message': f'Tips {"enabled" if onboarding.enable_tips else "disabled"}'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def toggle_reminders(self, request, pk=None):
        """Toggle onboarding reminders."""
        onboarding = self.get_object()
        
        onboarding.send_reminders = not onboarding.send_reminders
        onboarding.save(update_fields=['send_reminders'])
        
        return Response({
            'send_reminders': onboarding.send_reminders,
            'message': f'Reminders {"enabled" if onboarding.send_reminders else "disabled"}'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Get detailed onboarding progress."""
        onboarding = self.get_object()
        
        progress = OnboardingService.get_onboarding_progress(onboarding.tenant)
        return Response(progress, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def recommendations(self, request, pk=None):
        """Get onboarding recommendations."""
        onboarding = self.get_object()
        
        recommendations = OnboardingService.get_onboarding_recommendations(onboarding.tenant)
        return Response(recommendations, status=status.HTTP_200_OK)


class TenantOnboardingStepViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing onboarding steps.
    """
    serializer_class = TenantOnboardingStepSerializer
    queryset = TenantOnboardingStep.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'step_type', 'status', 'is_required']
    search_fields = ['label', 'description']
    ordering_fields = ['sort_order', 'step_key']
    ordering = ['sort_order', 'step_key']
    
    def get_queryset(self):
        """Filter queryset to tenant's onboarding steps."""
        if self.request.user.is_superuser:
            return TenantOnboardingStep.objects.all()
        return TenantOnboardingStep.objects.filter(tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete onboarding step."""
        step = self.get_object()
        
        if step.is_done:
            return Response(
                {'error': 'Step is already completed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        step_data = request.data.get('step_data', {})
        
        result = OnboardingService.complete_step(
            step.tenant, step.step_key, step_data, request.user
        )
        
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def skip(self, request, pk=None):
        """Skip onboarding step."""
        step = self.get_object()
        
        if step.is_done:
            return Response(
                {'error': 'Cannot skip completed step'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not step.can_skip:
            return Response(
                {'error': 'This step cannot be skipped'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason')
        
        result = OnboardingService.skip_step(
            step.tenant, step.step_key, reason, request.user
        )
        
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start onboarding step."""
        step = self.get_object()
        
        if step.is_done or step.status == 'in_progress':
            return Response(
                {'error': 'Step is already started or completed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        step.start_step()
        return Response({'message': 'Step started'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def help_resources(self, request, pk=None):
        """Get help resources for step."""
        step = self.get_object()
        
        resources = {
            'help_text': step.help_text,
            'video_url': step.video_url,
            'documentation_url': step.documentation_url,
            'validation_rules': step.validation_rules,
        }
        
        return Response(resources, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def time_spent(self, request, pk=None):
        """Get time spent on step."""
        step = self.get_object()
        
        if step.started_at and step.done_at:
            time_spent = step.done_at - step.started_at
            return Response({
                'time_spent_seconds': step.time_spent_seconds,
                'time_spent_display': step.time_spent_display,
                'started_at': step.started_at,
                'done_at': step.done_at,
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'time_spent_seconds': step.time_spent_seconds,
                'time_spent_display': step.time_spent_display,
                'started_at': step.started_at,
                'done_at': step.done_at,
            }, status=status.HTTP_200_OK)


class TenantTrialExtensionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing trial extensions.
    """
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'status', 'reason']
    search_fields = ['reason_details', 'notes']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return TenantTrialExtensionCreateSerializer
        return TenantTrialExtensionSerializer
    
    def get_queryset(self):
        """Filter queryset to tenant's trial extensions."""
        if self.request.user.is_superuser:
            return TenantTrialExtension.objects.all()
        return TenantTrialExtension.objects.filter(tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        elif self.action == 'create':
            return [permissions.IsAuthenticated]
        return [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        """Create trial extension request."""
        data = serializer.validated_data
        extension = OnboardingService.request_trial_extension(
            self.request.user.tenant,
            data['days_extended'],
            data['reason_details'],
            self.request.user
        )
        serializer.instance = extension
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve trial extension request."""
        extension = self.get_object()
        
        if extension.status != 'requested':
            return Response(
                {'error': 'Extension request is not in requested status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notes = request.data.get('notes')
        
        result = OnboardingService.approve_trial_extension(extension, request.user, notes)
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject trial extension request."""
        extension = self.get_object()
        
        if extension.status != 'requested':
            return Response(
                {'error': 'Extension request is not in requested status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason')
        
        extension.reject(request.user, reason)
        return Response({'message': 'Trial extension rejected'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel trial extension request."""
        extension = self.get_object()
        
        if extension.status not in ['requested', 'approved']:
            return Response(
                {'error': 'Cannot cancel extension in current status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        extension.cancel()
        return Response({'message': 'Trial extension cancelled'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def calculate_new_end_date(self, request, pk=None):
        """Calculate new trial end date."""
        extension = self.get_object()
        
        if extension.original_trial_end and extension.days_extended:
            from datetime import timedelta
            new_end = extension.original_trial_end + timedelta(days=extension.days_extended)
            
            return Response({
                'original_trial_end': extension.original_trial_end,
                'days_extended': extension.days_extended,
                'new_trial_end': new_end,
                'days_until_new_end': extension.days_until_new_trial_end,
            }, status=status.HTTP_200_OK)
        else:
            return Response(
                {'error': 'Unable to calculate new end date'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def pending_approvals(self, request):
        """Get pending trial extension approvals."""
        if not self.request.user.is_superuser:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        queryset = self.get_queryset().filter(status='requested')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get trial extension analytics."""
        if not self.request.user.is_superuser:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        analytics = OnboardingService.get_onboarding_analytics()
        
        # Filter trial extension specific data
        trial_data = {
            'total_extensions_requested': 0,
            'total_extensions_approved': 0,
            'total_extensions_rejected': 0,
            'average_days_requested': 0,
            'most_common_reason': None,
        }
        
        extensions = self.get_queryset()
        trial_data['total_extensions_requested'] = extensions.count()
        trial_data['total_extensions_approved'] = extensions.filter(status='approved').count()
        trial_data['total_extensions_rejected'] = extensions.filter(status='rejected').count()
        
        # Calculate average days requested
        approved_extensions = extensions.filter(status='approved')
        if approved_extensions.exists():
            avg_days = approved_extensions.aggregate(avg=models.Avg('days_extended'))
            trial_data['average_days_requested'] = avg_days['avg'] or 0
        
        # Most common reason
        from django.db.models import Count
        reason_counts = extensions.values('reason').annotate(count=Count('id')).order_by('-count')
        if reason_counts.exists():
            trial_data['most_common_reason'] = reason_counts.first()['reason']
        
        return Response(trial_data, status=status.HTTP_200_OK)
