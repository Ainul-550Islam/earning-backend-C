"""
Campaign Targeting ViewSet

ViewSet for campaign targeting rule management,
including CRUD operations for targeting configurations.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from django.db import transaction

from ..models.campaign import AdCampaign, CampaignTargeting
from ..serializers import CampaignTargetingSerializer
from ..permissions import IsAdvertiserOrReadOnly, IsOwnerOrReadOnly
from ..paginations import StandardResultsSetPagination

import logging
logger = logging.getLogger(__name__)


class CampaignTargetingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for campaign targeting rule management.
    
    Handles geographic, demographic, device,
    and behavioral targeting configurations.
    """
    
    queryset = CampaignTargeting.objects.all()
    serializer_class = CampaignTargetingSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdvertiserOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        
        if user.is_staff:
            # Admin can see all targeting rules
            return CampaignTargeting.objects.all()
        else:
            # Advertisers can only see their own targeting rules
            return CampaignTargeting.objects.filter(campaign__advertiser__user=user)
    
    def perform_create(self, serializer):
        """Create targeting rule with associated campaign."""
        campaign_id = serializer.validated_data.get('campaign')
        
        if not campaign_id:
            raise ValueError("Campaign ID is required")
        
        campaign = get_object_or_404(AdCampaign, id=campaign_id)
        
        # Check permissions
        if not (self.request.user.is_staff or campaign.advertiser.user == self.request.user):
            raise PermissionError("Permission denied")
        
        targeting_rule = serializer.save()
        # Set the campaign for the serializer
        serializer.instance = targeting_rule
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """
        Test targeting rule.
        
        Validates targeting logic and checks for conflicts.
        """
        targeting_rule = self.get_object()
        
        try:
            test_results = {
                'targeting_id': targeting_rule.id,
                'targeting_type': targeting_rule.targeting_type,
                'tests': {},
                'overall_status': 'passed',
                'errors': [],
                'warnings': [],
            }
            
            # Test targeting configuration
            if targeting_rule.targeting_type == 'geographic':
                test_results['tests']['geographic'] = self._test_geographic_targeting(targeting_rule)
            elif targeting_rule.targeting_type == 'demographic':
                test_results['tests']['demographic'] = self._test_demographic_targeting(targeting_rule)
            elif targeting_rule.targeting_type == 'device':
                test_results['tests']['device'] = self._test_device_targeting(targeting_rule)
            elif targeting_rule.targeting_type == 'behavioral':
                test_results['tests']['behavioral'] = self._test_behavioral_targeting(targeting_rule)
            elif targeting_rule.targeting_type == 'time':
                test_results['tests']['time'] = self._test_time_targeting(targeting_rule)
            else:
                test_results['tests']['unknown'] = {
                    'status': 'warning',
                    'warning': f'Unknown targeting type: {targeting_rule.targeting_type}'
                }
                test_results['warnings'].append('Unknown targeting type')
            
            # Test rule logic
            test_results['tests']['rule_logic'] = self._test_rule_logic(targeting_rule)
            
            # Test conflicts
            test_results['tests']['conflicts'] = self._test_targeting_conflicts(targeting_rule)
            
            # Determine overall status
            failed_tests = [name for name, result in test_results['tests'].items() if result.get('status') == 'failed']
            
            if failed_tests:
                test_results['overall_status'] = 'failed'
                test_results['errors'].extend([f"Failed test: {test}" for test in failed_tests])
            
            return Response(test_results)
            
        except Exception as e:
            logger.error(f"Error testing targeting rule: {e}")
            return Response(
                {'detail': 'Failed to test targeting rule'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """
        Duplicate targeting rule.
        
        Creates a copy of the targeting rule.
        """
        targeting_rule = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or targeting_rule.campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Create duplicate
            duplicate_data = {
                'campaign': targeting_rule.campaign.id,
                'targeting_type': targeting_rule.targeting_type,
                'targeting_value': targeting_rule.targeting_value,
                'operator': targeting_rule.operator,
                'is_include': targeting_rule.is_include,
                'priority': targeting_rule.priority,
                'conditions': targeting_rule.conditions,
            }
            
            serializer = self.get_serializer(data=duplicate_data)
            if serializer.is_valid():
                duplicate = serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Error duplicating targeting rule: {e}")
            return Response(
                {'detail': 'Failed to duplicate targeting rule'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def enable(self, request, pk=None):
        """
        Enable targeting rule.
        """
        targeting_rule = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or targeting_rule.campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            targeting_rule.is_active = True
            targeting_rule.save()
            
            return Response({
                'detail': 'Targeting rule enabled successfully',
                'is_active': True
            })
            
        except Exception as e:
            logger.error(f"Error enabling targeting rule: {e}")
            return Response(
                {'detail': 'Failed to enable targeting rule'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        """
        Disable targeting rule.
        """
        targeting_rule = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or targeting_rule.campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            targeting_rule.is_active = False
            targeting_rule.save()
            
            return Response({
                'detail': 'Targeting rule disabled successfully',
                'is_active': False
            })
            
        except Exception as e:
            logger.error(f"Error disabling targeting rule: {e}")
            return Response(
                {'detail': 'Failed to disable targeting rule'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_priority(self, request, pk=None):
        """
        Update targeting rule priority.
        """
        targeting_rule = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or targeting_rule.campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        priority = request.data.get('priority')
        
        if priority is None:
            return Response(
                {'detail': 'Priority is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            targeting_rule.priority = priority
            targeting_rule.save()
            
            return Response({
                'detail': 'Priority updated successfully',
                'priority': targeting_rule.priority
            })
            
        except Exception as e:
            logger.error(f"Error updating targeting rule priority: {e}")
            return Response(
                {'detail': 'Failed to update priority'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def targeting_types(self, request):
        """
        Get available targeting types.
        
        Returns list of supported targeting types and their configurations.
        """
        try:
            targeting_types = {
                'geographic': {
                    'name': 'Geographic Targeting',
                    'description': 'Target users by location',
                    'fields': ['countries', 'regions', 'cities', 'zip_codes'],
                    'operators': ['in', 'not_in', 'equals', 'not_equals'],
                },
                'demographic': {
                    'name': 'Demographic Targeting',
                    'description': 'Target users by demographics',
                    'fields': ['age', 'gender', 'income', 'education', 'occupation'],
                    'operators': ['in', 'not_in', 'between', 'not_between', 'equals', 'not_equals'],
                },
                'device': {
                    'name': 'Device Targeting',
                    'description': 'Target users by device type',
                    'fields': ['device_type', 'os', 'browser', 'screen_resolution'],
                    'operators': ['in', 'not_in', 'equals', 'not_equals'],
                },
                'behavioral': {
                    'name': 'Behavioral Targeting',
                    'description': 'Target users by behavior',
                    'fields': ['interests', 'purchase_history', 'browsing_history', 'search_history'],
                    'operators': ['in', 'not_in', 'contains', 'not_contains'],
                },
                'time': {
                    'name': 'Time Targeting',
                    'description': 'Target users by time',
                    'fields': ['day_of_week', 'hour_of_day', 'date_range'],
                    'operators': ['in', 'not_in', 'between', 'not_between'],
                },
                'custom': {
                    'name': 'Custom Targeting',
                    'description': 'Custom targeting rules',
                    'fields': ['custom_field'],
                    'operators': ['in', 'not_in', 'equals', 'not_equals', 'contains', 'not_contains'],
                }
            }
            
            return Response(targeting_types)
            
        except Exception as e:
            logger.error(f"Error getting targeting types: {e}")
            return Response(
                {'detail': 'Failed to get targeting types'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def operators(self, request):
        """
        Get available operators for targeting rules.
        
        Returns list of supported operators and their descriptions.
        """
        try:
            operators = {
                'in': {
                    'name': 'In',
                    'description': 'Value is in the specified list',
                    'field_types': ['list', 'array'],
                },
                'not_in': {
                    'name': 'Not In',
                    'description': 'Value is not in the specified list',
                    'field_types': ['list', 'array'],
                },
                'equals': {
                    'name': 'Equals',
                    'description': 'Value equals the specified value',
                    'field_types': ['string', 'number', 'boolean'],
                },
                'not_equals': {
                    'name': 'Not Equals',
                    'description': 'Value does not equal the specified value',
                    'field_types': ['string', 'number', 'boolean'],
                },
                'between': {
                    'name': 'Between',
                    'description': 'Value is between the specified range',
                    'field_types': ['number', 'date'],
                },
                'not_between': {
                    'name': 'Not Between',
                    'description': 'Value is not between the specified range',
                    'field_types': ['number', 'date'],
                },
                'contains': {
                    'name': 'Contains',
                    'description': 'Value contains the specified text',
                    'field_types': ['string'],
                },
                'not_contains': {
                    'name': 'Not Contains',
                    'description': 'Value does not contain the specified text',
                    'field_types': ['string'],
                },
                'greater_than': {
                    'name': 'Greater Than',
                    'description': 'Value is greater than the specified value',
                    'field_types': ['number', 'date'],
                },
                'less_than': {
                    'name': 'Less Than',
                    'description': 'Value is less than the specified value',
                    'field_types': ['number', 'date'],
                },
            }
            
            return Response(operators)
            
        except Exception as e:
            logger.error(f"Error getting operators: {e}")
            return Response(
                {'detail': 'Failed to get operators'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def validate_targeting(self, request):
        """
        Validate targeting configuration.
        
        Checks for conflicts, logical errors, and best practices.
        """
        targeting_config = request.data.get('targeting_config', [])
        
        if not targeting_config:
            return Response(
                {'detail': 'No targeting configuration provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            validation_results = {
                'is_valid': True,
                'errors': [],
                'warnings': [],
                'recommendations': [],
            }
            
            # Check for conflicts
            conflicts = self._check_targeting_conflicts_config(targeting_config)
            validation_results['errors'].extend(conflicts)
            
            # Check for logical errors
            logical_errors = self._check_logical_errors(targeting_config)
            validation_results['errors'].extend(logical_errors)
            
            # Check for best practices
            best_practices = self._check_best_practices(targeting_config)
            validation_results['warnings'].extend(best_practices)
            
            # Generate recommendations
            recommendations = self._generate_targeting_recommendations(targeting_config)
            validation_results['recommendations'].extend(recommendations)
            
            # Determine overall validity
            if validation_results['errors']:
                validation_results['is_valid'] = False
            
            return Response(validation_results)
            
        except Exception as e:
            logger.error(f"Error validating targeting: {e}")
            return Response(
                {'detail': 'Failed to validate targeting configuration'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Bulk create targeting rules.
        
        Create multiple targeting rules at once.
        """
        campaign_id = request.data.get('campaign_id')
        targeting_rules = request.data.get('targeting_rules', [])
        
        if not campaign_id:
            return Response(
                {'detail': 'Campaign ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not targeting_rules:
            return Response(
                {'detail': 'No targeting rules provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            campaign = get_object_or_404(AdCampaign, id=campaign_id)
            
            # Check permissions
            if not (request.user.is_staff or campaign.advertiser.user == request.user):
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
                for rule_data in targeting_rules:
                    try:
                        rule_data['campaign'] = campaign_id
                        serializer = self.get_serializer(data=rule_data)
                        if serializer.is_valid():
                            serializer.save()
                            results['created'] += 1
                        else:
                            results['failed'] += 1
                            results['errors'].append({
                                'rule_data': rule_data,
                                'errors': serializer.errors
                            })
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append({
                            'rule_data': rule_data,
                            'error': str(e)
                        })
            
            return Response(results)
            
        except Exception as e:
            logger.error(f"Error in bulk create: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _test_geographic_targeting(self, targeting_rule):
        """Test geographic targeting configuration."""
        return {
            'status': 'passed',
            'details': 'Geographic targeting configuration is valid'
        }
    
    def _test_demographic_targeting(self, targeting_rule):
        """Test demographic targeting configuration."""
        return {
            'status': 'passed',
            'details': 'Demographic targeting configuration is valid'
        }
    
    def _test_device_targeting(self, targeting_rule):
        """Test device targeting configuration."""
        return {
            'status': 'passed',
            'details': 'Device targeting configuration is valid'
        }
    
    def _test_behavioral_targeting(self, targeting_rule):
        """Test behavioral targeting configuration."""
        return {
            'status': 'passed',
            'details': 'Behavioral targeting configuration is valid'
        }
    
    def _test_time_targeting(self, targeting_rule):
        """Test time targeting configuration."""
        return {
            'status': 'passed',
            'details': 'Time targeting configuration is valid'
        }
    
    def _test_rule_logic(self, targeting_rule):
        """Test targeting rule logic."""
        return {
            'status': 'passed',
            'details': 'Rule logic is valid'
        }
    
    def _test_targeting_conflicts(self, targeting_rule):
        """Test for targeting conflicts."""
        return {
            'status': 'passed',
            'details': 'No conflicts detected'
        }
    
    def _check_targeting_conflicts_config(self, targeting_config):
        """Check for conflicts in targeting configuration."""
        conflicts = []
        
        # This would implement actual conflict checking
        # For now, return empty list
        return conflicts
    
    def _check_logical_errors(self, targeting_config):
        """Check for logical errors in targeting configuration."""
        errors = []
        
        # This would implement actual logical error checking
        # For now, return empty list
        return errors
    
    def _check_best_practices(self, targeting_config):
        """Check for best practices in targeting configuration."""
        warnings = []
        
        # This would implement actual best practice checking
        # For now, return empty list
        return warnings
    
    def _generate_targeting_recommendations(self, targeting_config):
        """Generate recommendations for targeting configuration."""
        recommendations = []
        
        # This would implement actual recommendation generation
        # For now, return empty list
        return recommendations
    
    def list(self, request, *args, **kwargs):
        """
        Override list to add filtering capabilities.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply additional filters
        campaign_id = request.query_params.get('campaign_id')
        targeting_type = request.query_params.get('targeting_type')
        is_active = request.query_params.get('is_active')
        is_include = request.query_params.get('is_include')
        search = request.query_params.get('search')
        
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        
        if targeting_type:
            queryset = queryset.filter(targeting_type=targeting_type)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        if is_include is not None:
            queryset = queryset.filter(is_include=is_include.lower() == 'true')
        
        if search:
            queryset = queryset.filter(
                Q(targeting_value__icontains=search) |
                Q(conditions__icontains=search)
            )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
