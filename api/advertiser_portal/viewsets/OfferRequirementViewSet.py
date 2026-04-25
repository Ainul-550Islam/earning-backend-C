"""
Offer Requirement ViewSet

ViewSet for offer requirement management,
including CRUD operations for offer requirements.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from django.db import transaction

from ..models.offer import AdvertiserOffer, OfferRequirement
from ..serializers import OfferRequirementSerializer
from ..permissions import IsAdvertiserOrReadOnly, IsOwnerOrReadOnly
from ..paginations import StandardResultsSetPagination

import logging
logger = logging.getLogger(__name__)


class OfferRequirementViewSet(viewsets.ModelViewSet):
    """
    ViewSet for offer requirement management.
    
    Handles requirement creation, validation,
    and completion tracking.
    """
    
    queryset = OfferRequirement.objects.all()
    serializer_class = OfferRequirementSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdvertiserOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        
        if user.is_staff:
            # Admin can see all requirements
            return OfferRequirement.objects.all()
        else:
            # Advertisers can only see their own requirements
            return OfferRequirement.objects.filter(offer__advertiser__user=user)
    
    def perform_create(self, serializer):
        """Create requirement with associated offer."""
        offer_id = serializer.validated_data.get('offer')
        
        if not offer_id:
            raise ValueError("Offer ID is required")
        
        offer = get_object_or_404(AdvertiserOffer, id=offer_id)
        
        # Check permissions
        if not (self.request.user.is_staff or offer.advertiser.user == self.request.user):
            raise PermissionError("Permission denied")
        
        requirement = serializer.save()
        # Set the offer for the serializer
        serializer.instance = requirement
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Approve requirement.
        
        Only staff members can approve requirements.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        requirement = self.get_object()
        
        if requirement.status == 'active':
            return Response(
                {'detail': 'Requirement is already approved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            requirement.status = 'active'
            requirement.approved_at = timezone.now()
            requirement.approved_by = request.user
            requirement.save()
            
            serializer = self.get_serializer(requirement)
            return Response({
                'detail': 'Requirement approved successfully',
                'requirement': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error approving requirement: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Reject requirement.
        
        Only staff members can reject requirements.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        requirement = self.get_object()
        reason = request.data.get('reason', '')
        
        if not reason:
            return Response(
                {'detail': 'Rejection reason is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            requirement.status = 'rejected'
            requirement.rejection_reason = reason
            requirement.rejected_at = timezone.now()
            requirement.rejected_by = request.user
            requirement.save()
            
            serializer = self.get_serializer(requirement)
            return Response({
                'detail': 'Requirement rejected',
                'requirement': serializer.data,
                'rejection_reason': reason
            })
            
        except Exception as e:
            logger.error(f"Error rejecting requirement: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """
        Activate requirement.
        
        Makes requirement available for users.
        """
        requirement = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or requirement.offer.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if requirement.status == 'active':
            return Response(
                {'detail': 'Requirement is already active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            requirement.status = 'active'
            requirement.save()
            
            return Response({
                'detail': 'Requirement activated successfully',
                'status': requirement.status
            })
            
        except Exception as e:
            logger.error(f"Error activating requirement: {e}")
            return Response(
                {'detail': 'Failed to activate requirement'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """
        Deactivate requirement.
        
        Makes requirement unavailable for users.
        """
        requirement = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or requirement.offer.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if requirement.status != 'active':
            return Response(
                {'detail': 'Requirement is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            requirement.status = 'draft'
            requirement.save()
            
            return Response({
                'detail': 'Requirement deactivated successfully',
                'status': requirement.status
            })
            
        except Exception as e:
            logger.error(f"Error deactivating requirement: {e}")
            return Response(
                {'detail': 'Failed to deactivate requirement'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_instructions(self, request, pk=None):
        """
        Update requirement instructions.
        
        Updates the instructions for completing the requirement.
        """
        requirement = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or requirement.offer.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        instructions = request.data.get('instructions')
        
        if not instructions:
            return Response(
                {'detail': 'Instructions are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            requirement.instructions = instructions
            requirement.save()
            
            serializer = self.get_serializer(requirement)
            return Response({
                'detail': 'Instructions updated successfully',
                'requirement': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error updating instructions: {e}")
            return Response(
                {'detail': 'Failed to update instructions'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_proof_requirements(self, request, pk=None):
        """
        Update proof requirements.
        
        Updates whether proof is required and proof instructions.
        """
        requirement = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or requirement.offer.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        proof_required = request.data.get('proof_required')
        proof_instructions = request.data.get('proof_instructions')
        
        try:
            if proof_required is not None:
                requirement.proof_required = proof_required
            
            if proof_instructions is not None:
                requirement.proof_instructions = proof_instructions
            
            requirement.save()
            
            serializer = self.get_serializer(requirement)
            return Response({
                'detail': 'Proof requirements updated successfully',
                'requirement': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error updating proof requirements: {e}")
            return Response(
                {'detail': 'Failed to update proof requirements'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_validation_rules(self, request, pk=None):
        """
        Update validation rules.
        
        Updates the validation logic for the requirement.
        """
        requirement = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or requirement.offer.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        validation_rules = request.data.get('validation_rules')
        
        if validation_rules is None:
            return Response(
                {'detail': 'Validation rules are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            requirement.validation_rules = validation_rules
            requirement.save()
            
            serializer = self.get_serializer(requirement)
            return Response({
                'detail': 'Validation rules updated successfully',
                'requirement': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error updating validation rules: {e}")
            return Response(
                {'detail': 'Failed to update validation rules'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_time_settings(self, request, pk=None):
        """
        Update time settings.
        
        Updates completion time limit and cooldown period.
        """
        requirement = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or requirement.offer.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        completion_time_limit = request.data.get('completion_time_limit')
        retry_attempts = request.data.get('retry_attempts')
        cooldown_period = request.data.get('cooldown_period')
        
        try:
            if completion_time_limit is not None:
                requirement.completion_time_limit = completion_time_limit
            
            if retry_attempts is not None:
                requirement.retry_attempts = retry_attempts
            
            if cooldown_period is not None:
                requirement.cooldown_period = cooldown_period
            
            requirement.save()
            
            serializer = self.get_serializer(requirement)
            return Response({
                'detail': 'Time settings updated successfully',
                'requirement': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error updating time settings: {e}")
            return Response(
                {'detail': 'Failed to update time settings'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def set_reward(self, request, pk=None):
        """
        Set reward for requirement completion.
        
        Updates reward amount and type.
        """
        requirement = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or requirement.offer.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        reward_amount = request.data.get('reward_amount')
        reward_type = request.data.get('reward_type')
        
        try:
            if reward_amount is not None:
                requirement.reward_amount = reward_amount
            
            if reward_type is not None:
                requirement.reward_type = reward_type
            
            requirement.save()
            
            serializer = self.get_serializer(requirement)
            return Response({
                'detail': 'Reward set successfully',
                'requirement': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error setting reward: {e}")
            return Response(
                {'detail': 'Failed to set reward'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_dates(self, request, pk=None):
        """
        Update requirement dates.
        
        Updates start and end dates for the requirement.
        """
        requirement = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or requirement.offer.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        
        try:
            if start_date is not None:
                requirement.start_date = start_date
            
            if end_date is not None:
                requirement.end_date = end_date
            
            requirement.save()
            
            serializer = self.get_serializer(requirement)
            return Response({
                'detail': 'Dates updated successfully',
                'requirement': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error updating dates: {e}")
            return Response(
                {'detail': 'Failed to update dates'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def completion_stats(self, request, pk=None):
        """
        Get requirement completion statistics.
        
        Returns completion rates and performance metrics.
        """
        requirement = self.get_object()
        
        try:
            # This would implement actual completion tracking
            # For now, return placeholder data
            stats = {
                'requirement_id': requirement.id,
                'requirement_type': requirement.requirement_type,
                'status': requirement.status,
                'total_attempts': 0,
                'successful_completions': 0,
                'failed_completions': 0,
                'completion_rate': 0.0,
                'average_completion_time': 0.0,
                'reward_payout_total': 0.0,
                'period_days': 30,
                'daily_breakdown': {},
            }
            
            return Response(stats)
            
        except Exception as e:
            logger.error(f"Error getting completion stats: {e}")
            return Response(
                {'detail': 'Failed to get completion statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def validation_summary(self, request, pk=None):
        """
        Get validation summary.
        
        Returns validation rules and requirements summary.
        """
        requirement = self.get_object()
        
        try:
            summary = {
                'requirement_id': requirement.id,
                'requirement_type': requirement.requirement_type,
                'instructions': requirement.instructions,
                'proof_required': requirement.proof_required,
                'proof_instructions': requirement.proof_instructions,
                'validation_rules': requirement.validation_rules,
                'completion_time_limit': requirement.completion_time_limit,
                'retry_attempts': requirement.retry_attempts,
                'cooldown_period': requirement.cooldown_period,
                'reward_amount': float(requirement.reward_amount) if requirement.reward_amount else None,
                'reward_type': requirement.reward_type,
                'start_date': requirement.start_date.isoformat() if requirement.start_date else None,
                'end_date': requirement.end_date.isoformat() if requirement.end_date else None,
                'is_active': requirement.status == 'active',
                'created_at': requirement.created_at.isoformat(),
            }
            
            return Response(summary)
            
        except Exception as e:
            logger.error(f"Error getting validation summary: {e}")
            return Response(
                {'detail': 'Failed to get validation summary'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def requirement_types(self, request):
        """
        Get available requirement types.
        
        Returns list of supported requirement types and their configurations.
        """
        try:
            requirement_types = {
                'email_signup': {
                    'name': 'Email Signup',
                    'description': 'User must sign up for email newsletter',
                    'default_proof_required': True,
                    'default_completion_time': 300,  # 5 minutes
                    'common_fields': ['email', 'name', 'consent'],
                },
                'app_install': {
                    'name': 'App Install',
                    'description': 'User must install mobile application',
                    'default_proof_required': True,
                    'default_completion_time': 600,  # 10 minutes
                    'common_fields': ['device_id', 'app_version', 'install_timestamp'],
                },
                'survey_completion': {
                    'name': 'Survey Completion',
                    'description': 'User must complete survey questions',
                    'default_proof_required': True,
                    'default_completion_time': 900,  # 15 minutes
                    'common_fields': ['survey_id', 'responses', 'completion_timestamp'],
                },
                'video_watch': {
                    'name': 'Video Watch',
                    'description': 'User must watch video content',
                    'default_proof_required': True,
                    'default_completion_time': 600,  # 10 minutes
                    'common_fields': ['video_id', 'watch_time', 'completion_percentage'],
                },
                'social_follow': {
                    'name': 'Social Follow',
                    'description': 'User must follow social media account',
                    'default_proof_required': True,
                    'default_completion_time': 180,  # 3 minutes
                    'common_fields': ['social_platform', 'username', 'follow_timestamp'],
                },
                'form_submission': {
                    'name': 'Form Submission',
                    'description': 'User must submit lead form',
                    'default_proof_required': True,
                    'default_completion_time': 300,  # 5 minutes
                    'common_fields': ['form_id', 'field_values', 'submission_timestamp'],
                },
                'content_engagement': {
                    'name': 'Content Engagement',
                    'description': 'User must engage with content',
                    'default_proof_required': True,
                    'default_completion_time': 300,  # 5 minutes
                    'common_fields': ['content_id', 'engagement_type', 'engagement_timestamp'],
                },
                'purchase_action': {
                    'name': 'Purchase Action',
                    'description': 'User must make a purchase',
                    'default_proof_required': True,
                    'default_completion_time': 1800,  # 30 minutes
                    'common_fields': ['order_id', 'purchase_amount', 'transaction_timestamp'],
                },
                'custom': {
                    'name': 'Custom Requirement',
                    'description': 'Custom requirement with custom validation',
                    'default_proof_required': False,
                    'default_completion_time': 300,  # 5 minutes
                    'common_fields': [],
                },
            }
            
            return Response(requirement_types)
            
        except Exception as e:
            logger.error(f"Error getting requirement types: {e}")
            return Response(
                {'detail': 'Failed to get requirement types'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def validate_requirement_config(self, request):
        """
        Validate requirement configuration.
        
        Checks for logical errors and best practices.
        """
        config = request.data.get('config', {})
        
        if not config:
            return Response(
                {'detail': 'No configuration provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            validation_results = {
                'is_valid': True,
                'errors': [],
                'warnings': [],
                'recommendations': [],
            }
            
            # Check required fields
            required_fields = ['requirement_type', 'instructions']
            for field in required_fields:
                if field not in config:
                    validation_results['errors'].append(f'Missing required field: {field}')
                    validation_results['is_valid'] = False
            
            # Check requirement type
            requirement_type = config.get('requirement_type')
            if requirement_type:
                valid_types = ['email_signup', 'app_install', 'survey_completion', 'video_watch', 
                               'social_follow', 'form_submission', 'content_engagement', 'purchase_action', 'custom']
                if requirement_type not in valid_types:
                    validation_results['errors'].append(f'Invalid requirement type: {requirement_type}')
                    validation_results['is_valid'] = False
            
            # Check completion time limit
            completion_time = config.get('completion_time_limit')
            if completion_time is not None:
                if completion_time <= 0:
                    validation_results['errors'].append('Completion time limit must be positive')
                    validation_results['is_valid'] = False
                elif completion_time > 3600:  # 1 hour
                    validation_results['warnings'].append('Very long completion time limit may affect user experience')
            
            # Check retry attempts
            retry_attempts = config.get('retry_attempts')
            if retry_attempts is not None:
                if retry_attempts < 0:
                    validation_results['errors'].append('Retry attempts cannot be negative')
                    validation_results['is_valid'] = False
                elif retry_attempts > 10:
                    validation_results['warnings'].append('High number of retry attempts may be excessive')
            
            # Check cooldown period
            cooldown_period = config.get('cooldown_period')
            if cooldown_period is not None:
                if cooldown_period < 0:
                    validation_results['errors'].append('Cooldown period cannot be negative')
                    validation_results['is_valid'] = False
                elif cooldown_period > 86400:  # 24 hours
                    validation_results['warnings'].append('Very long cooldown period may limit user engagement')
            
            # Check reward settings
            reward_amount = config.get('reward_amount')
            if reward_amount is not None and reward_amount <= 0:
                validation_results['errors'].append('Reward amount must be positive')
                validation_results['is_valid'] = False
            
            # Generate recommendations
            if validation_results['is_valid']:
                if not config.get('proof_required', True):
                    validation_results['recommendations'].append('Consider requiring proof for better tracking')
                
                if not config.get('completion_time_limit'):
                    validation_results['recommendations'].append('Set a completion time limit to prevent abuse')
                
                if not config.get('retry_attempts'):
                    validation_results['recommendations'].append('Set retry attempts to allow users to complete requirement')
            
            return Response(validation_results)
            
        except Exception as e:
            logger.error(f"Error validating requirement config: {e}")
            return Response(
                {'detail': 'Failed to validate configuration'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Bulk create requirements for an offer.
        
        Create multiple requirements at once.
        """
        offer_id = request.data.get('offer_id')
        requirements = request.data.get('requirements', [])
        
        if not offer_id:
            return Response(
                {'detail': 'Offer ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not requirements:
            return Response(
                {'detail': 'No requirements provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            offer = get_object_or_404(AdvertiserOffer, id=offer_id)
            
            # Check permissions
            if not (request.user.is_staff or offer.advertiser.user == request.user):
                return Response(
                    {'detail': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            results = {
                'created': 0,
                'failed': 0,
                'errors': []
            }
            
            with transaction.atomic():
                for req_data in requirements:
                    try:
                        req_data['offer'] = offer_id
                        serializer = self.get_serializer(data=req_data)
                        if serializer.is_valid():
                            serializer.save()
                            results['created'] += 1
                        else:
                            results['failed'] += 1
                            results['errors'].append({
                                'requirement_data': req_data,
                                'errors': serializer.errors
                            })
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append({
                            'requirement_data': req_data,
                            'error': str(e)
                        })
            
            return Response(results)
            
        except Exception as e:
            logger.error(f"Error in bulk create: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def list(self, request, *args, **kwargs):
        """
        Override list to add filtering capabilities.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply additional filters
        offer_id = request.query_params.get('offer_id')
        requirement_type = request.query_params.get('requirement_type')
        status = request.query_params.get('status')
        proof_required = request.query_params.get('proof_required')
        search = request.query_params.get('search')
        
        if offer_id:
            queryset = queryset.filter(offer_id=offer_id)
        
        if requirement_type:
            queryset = queryset.filter(requirement_type=requirement_type)
        
        if status:
            queryset = queryset.filter(status=status)
        
        if proof_required is not None:
            queryset = queryset.filter(proof_required=proof_required.lower() == 'true')
        
        if search:
            queryset = queryset.filter(
                Q(instructions__icontains=search) |
                Q(requirement_type__icontains=search)
            )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
